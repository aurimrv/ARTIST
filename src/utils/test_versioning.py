"""
Test File Versioning Utilities

Utilities for creating versioned backups of test files during corrections.
"""

from pathlib import Path
from typing import Optional, List, Dict
import re
import json
from datetime import datetime


class TestVersionManager:
    """Manages versioned backups of test files with metadata tracking."""
    
    def __init__(self, project_dir: Path):
        """
        Initialize the version manager.
        
        Args:
            project_dir: Root directory of the Maven project
        """
        self.project_dir = project_dir
        self.versions_dir = project_dir / ".test-versions"
        self.metadata_file = self.versions_dir / "versions.json"
        
        # Ensure versions directory exists
        self.versions_dir.mkdir(exist_ok=True)
    
    def create_version(self, file_path: Path, content: str, correction_type: str = "unknown") -> Dict[str, any]:
        """
        Create a new version of a test file.
        
        Args:
            file_path: Path to the test file
            content: Current content of the file
            correction_type: Type of correction being applied
            
        Returns:
            Dictionary with version information
        """
        # Get relative path from project root
        try:
            rel_path = file_path.relative_to(self.project_dir)
        except ValueError:
            # File is outside project directory
            rel_path = file_path
        
        # Load existing metadata
        metadata = self._load_metadata()
        
        # Get file metadata
        file_key = str(rel_path)
        if file_key not in metadata:
            metadata[file_key] = {
                'versions': [],
                'current_version': 0
            }
        
        # Increment version number
        version_number = metadata[file_key]['current_version'] + 1
        metadata[file_key]['current_version'] = version_number
        
        # Create version file path
        version_filename = f"{file_path.stem}.v{version_number}{file_path.suffix}"
        version_path = self.versions_dir / version_filename
        
        # Write version file
        version_path.write_text(content, encoding='utf-8')
        
        # Add version metadata
        version_info = {
            'version': version_number,
            'timestamp': datetime.now().isoformat(),
            'correction_type': correction_type,
            'file_path': str(rel_path),
            'version_file': version_filename,
            'size': len(content),
            'lines': len(content.splitlines()),
            'test_methods': content.count('@Test'),
            'ignore_annotations': content.count('@Ignore')
        }
        
        metadata[file_key]['versions'].append(version_info)
        
        # Save metadata
        self._save_metadata(metadata)
        
        return version_info
    
    def get_version_history(self, file_path: Path) -> List[Dict[str, any]]:
        """
        Get version history for a test file.
        
        Args:
            file_path: Path to the test file
            
        Returns:
            List of version information dictionaries
        """
        try:
            rel_path = file_path.relative_to(self.project_dir)
        except ValueError:
            rel_path = file_path
        
        metadata = self._load_metadata()
        file_key = str(rel_path)
        
        if file_key in metadata:
            return metadata[file_key]['versions']
        
        return []
    
    def get_version_content(self, file_path: Path, version_number: int) -> Optional[str]:
        """
        Get content of a specific version.
        
        Args:
            file_path: Path to the test file
            version_number: Version number to retrieve
            
        Returns:
            Content of the version or None if not found
        """
        history = self.get_version_history(file_path)
        
        for version_info in history:
            if version_info['version'] == version_number:
                version_file = self.versions_dir / version_info['version_file']
                if version_file.exists():
                    return version_file.read_text(encoding='utf-8')
        
        return None
    
    def get_version_diff_summary(self, file_path: Path, version1: int, version2: int) -> Optional[Dict[str, any]]:
        """
        Get a summary of differences between two versions.
        
        Args:
            file_path: Path to the test file
            version1: First version number
            version2: Second version number
            
        Returns:
            Dictionary with diff summary or None if versions don't exist
        """
        content1 = self.get_version_content(file_path, version1)
        content2 = self.get_version_content(file_path, version2)
        
        if not content1 or not content2:
            return None
        
        lines1 = content1.splitlines()
        lines2 = content2.splitlines()
        
        # Simple diff statistics
        lines_added = len(lines2) - len(lines1)
        
        # Count @Ignore annotations
        ignore_count1 = content1.count('@Ignore')
        ignore_count2 = content2.count('@Ignore')
        ignore_diff = ignore_count2 - ignore_count1
        
        # Count test methods
        test_count1 = content1.count('@Test')
        test_count2 = content2.count('@Test')
        
        return {
            'version1': version1,
            'version2': version2,
            'lines_added': lines_added,
            'ignore_annotations_added': ignore_diff,
            'test_methods_v1': test_count1,
            'test_methods_v2': test_count2,
            'size_v1': len(content1),
            'size_v2': len(content2)
        }
    
    def cleanup_old_versions(self, file_path: Path, keep_versions: int = 10) -> int:
        """
        Clean up old versions, keeping only the most recent ones.
        
        Args:
            file_path: Path to the test file
            keep_versions: Number of versions to keep
            
        Returns:
            Number of versions deleted
        """
        history = self.get_version_history(file_path)
        
        if len(history) <= keep_versions:
            return 0
        
        # Sort by version number and keep only the most recent
        history.sort(key=lambda x: x['version'])
        versions_to_delete = history[:-keep_versions]
        
        deleted_count = 0
        for version_info in versions_to_delete:
            version_file = self.versions_dir / version_info['version_file']
            try:
                if version_file.exists():
                    version_file.unlink()
                    deleted_count += 1
            except Exception:
                pass  # Ignore errors when deleting
        
        # Update metadata
        try:
            rel_path = file_path.relative_to(self.project_dir)
        except ValueError:
            rel_path = file_path
        
        metadata = self._load_metadata()
        file_key = str(rel_path)
        
        if file_key in metadata:
            metadata[file_key]['versions'] = history[-keep_versions:]
            self._save_metadata(metadata)
        
        return deleted_count
    
    def restore_version(self, file_path: Path, version_number: int) -> bool:
        """
        Restore a specific version of a test file.
        
        Args:
            file_path: Path to the test file
            version_number: Version number to restore
            
        Returns:
            True if restoration was successful
        """
        content = self.get_version_content(file_path, version_number)
        
        if not content:
            return False
        
        try:
            # Create backup of current version first
            current_content = file_path.read_text(encoding='utf-8')
            self.create_version(file_path, current_content, "pre_restore_backup")
            
            # Restore the version
            file_path.write_text(content, encoding='utf-8')
            
            return True
        except Exception:
            return False
    
    def get_correction_summary(self, file_path: Path) -> Dict[str, any]:
        """
        Get a summary of all corrections applied to a file.
        
        Args:
            file_path: Path to the test file
            
        Returns:
            Dictionary with correction summary
        """
        history = self.get_version_history(file_path)
        
        if not history:
            return {
                'total_versions': 0,
                'correction_types': {},
                'total_ignores_added': 0,
                'first_correction': None,
                'last_correction': None
            }
        
        # Count correction types
        correction_types = {}
        for version_info in history:
            correction_type = version_info.get('correction_type', 'unknown')
            correction_types[correction_type] = correction_types.get(correction_type, 0) + 1
        
        # Calculate total ignores added
        first_ignores = history[0].get('ignore_annotations', 0) if history else 0
        last_ignores = history[-1].get('ignore_annotations', 0) if history else 0
        total_ignores_added = last_ignores - first_ignores
        
        return {
            'total_versions': len(history),
            'correction_types': correction_types,
            'total_ignores_added': total_ignores_added,
            'first_correction': history[0]['timestamp'] if history else None,
            'last_correction': history[-1]['timestamp'] if history else None
        }
    
    def _load_metadata(self) -> Dict[str, any]:
        """Load version metadata from file."""
        if self.metadata_file.exists():
            try:
                return json.loads(self.metadata_file.read_text(encoding='utf-8'))
            except Exception:
                pass
        
        return {}
    
    def _save_metadata(self, metadata: Dict[str, any]) -> None:
        """Save version metadata to file."""
        try:
            self.metadata_file.write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
        except Exception:
            pass  # Ignore save errors

