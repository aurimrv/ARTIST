"""
File and directory utilities for the API Test Generator System.
"""

import shutil
from pathlib import Path
from typing import Optional, Union


def ensure_directory(path: Union[str, Path]) -> Path:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        path: Directory path
    
    Returns:
        Path object for the directory
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def copy_directory(src: Union[str, Path], dst: Union[str, Path]) -> Path:
    """
    Copy a directory and all its contents.
    
    Args:
        src: Source directory path
        dst: Destination directory path
    
    Returns:
        Path object for the destination directory
    """
    src = Path(src)
    dst = Path(dst)
    
    if dst.exists():
        shutil.rmtree(dst)
    
    shutil.copytree(src, dst)
    return dst


def read_file(path: Union[str, Path], encoding: str = 'utf-8') -> str:
    """
    Read text content from a file.
    
    Args:
        path: File path
        encoding: Text encoding
    
    Returns:
        File content as string
    """
    path = Path(path)
    return path.read_text(encoding=encoding)


def write_file(
    path: Union[str, Path], 
    content: str, 
    encoding: str = 'utf-8',
    create_dirs: bool = True
) -> Path:
    """
    Write text content to a file.
    
    Args:
        path: File path
        content: Content to write
        encoding: Text encoding
        create_dirs: Whether to create parent directories
    
    Returns:
        Path object for the file
    """
    path = Path(path)
    
    if create_dirs:
        path.parent.mkdir(parents=True, exist_ok=True)
    
    path.write_text(content, encoding=encoding)
    return path


def find_files(
    directory: Union[str, Path],
    pattern: str = "*",
    recursive: bool = True
) -> list[Path]:
    """
    Find files matching a pattern in a directory.
    
    Args:
        directory: Directory to search
        pattern: File pattern (glob style)
        recursive: Whether to search recursively
    
    Returns:
        List of matching file paths
    """
    directory = Path(directory)
    
    if recursive:
        return list(directory.rglob(pattern))
    else:
        return list(directory.glob(pattern))


def get_relative_path(path: Union[str, Path], base: Union[str, Path]) -> Path:
    """
    Get relative path from base directory.
    
    Args:
        path: Target path
        base: Base directory
    
    Returns:
        Relative path
    """
    path = Path(path).resolve()
    base = Path(base).resolve()
    
    try:
        return path.relative_to(base)
    except ValueError:
        # If paths are not related, return absolute path
        return path


def is_java_file(path: Union[str, Path]) -> bool:
    """
    Check if a file is a Java source file.
    
    Args:
        path: File path
    
    Returns:
        True if file has .java extension
    """
    return Path(path).suffix.lower() == '.java'


def is_xml_file(path: Union[str, Path]) -> bool:
    """
    Check if a file is an XML file.
    
    Args:
        path: File path
    
    Returns:
        True if file has .xml extension
    """
    return Path(path).suffix.lower() == '.xml'


def is_yaml_file(path: Union[str, Path]) -> bool:
    """
    Check if a file is a YAML file.
    
    Args:
        path: File path
    
    Returns:
        True if file has .yaml or .yml extension
    """
    suffix = Path(path).suffix.lower()
    return suffix in ['.yaml', '.yml']


def is_json_file(path: Union[str, Path]) -> bool:
    """
    Check if a file is a JSON file.
    
    Args:
        path: File path
    
    Returns:
        True if file has .json extension
    """
    return Path(path).suffix.lower() == '.json'

