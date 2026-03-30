"""
Maven runner utility for executing Maven commands and analyzing results.
"""

import subprocess
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from .logger import LoggerMixin


@dataclass
class MavenResult:
    """Result of a Maven command execution."""
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    execution_time: float
    command: str


@dataclass
class CompilationError:
    """Represents a compilation error."""
    file_path: str
    line_number: int
    column_number: int
    error_type: str
    message: str
    full_error: str


class MavenRunner(LoggerMixin):
    """
    Utility for running Maven commands and analyzing results.
    
    Provides methods for compilation, testing, and error analysis
    with proper timeout handling and result parsing.
    """
    
    def __init__(self, maven_home: Optional[str] = None, java_home: Optional[str] = None):
        """
        Initialize the Maven runner.
        
        Args:
            maven_home: Path to Maven installation
            java_home: Path to Java installation
        """
        self.maven_home = Path(maven_home) if maven_home else None
        self.java_home = Path(java_home) if java_home else None

        # Determine Maven executable
        self.maven_executable = self._find_maven_executable()
        
        self.logger.info(f"Initialized Maven runner with executable: {self.maven_executable}")
    
    def _find_maven_executable(self) -> str:
        """Find the Maven executable."""
        if self.maven_home:
            maven_bin = self.maven_home / "bin" / "mvn"
            if maven_bin.exists():
                return str(maven_bin)
        
        # Try system PATH
        try:
            result = subprocess.run(
                ["which", "mvn"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Default to 'mvn' and hope it's in PATH
        return "mvn"
    
    async def compile_project(
        self, 
        project_dir: Path, 
        timeout: int = 300
    ) -> MavenResult:
        """
        Compile a Maven project.
        
        Args:
            project_dir: Path to the Maven project directory
            timeout: Timeout in seconds
        
        Returns:
            Maven execution result
        """
        return await self._run_maven_command(
            project_dir, 
            ["test-compile"], 
            timeout=timeout
        )
    
    async def run_tests(
        self, 
        project_dir: Path, 
        timeout: int = 300,
        test_class: Optional[str] = None
    ) -> MavenResult:
        """
        Run tests in a Maven project.
        
        Args:
            project_dir: Path to the Maven project directory
            timeout: Timeout in seconds
            test_class: Specific test class to run (optional)
        
        Returns:
            Maven execution result
        """
        command = ["test"]
        
        if test_class:
            command.append(f"-Dtest={test_class}")
        
        return await self._run_maven_command(
            project_dir, 
            command, 
            timeout=timeout
        )
    
    async def clean_project(self, project_dir: Path, timeout: int = 60) -> MavenResult:
        """
        Clean a Maven project.
        
        Args:
            project_dir: Path to the Maven project directory
            timeout: Timeout in seconds
        
        Returns:
            Maven execution result
        """
        return await self._run_maven_command(
            project_dir, 
            ["clean"], 
            timeout=timeout
        )
    
    async def validate_project(self, project_dir: Path, timeout: int = 60) -> MavenResult:
        """
        Validate a Maven project.
        
        Args:
            project_dir: Path to the Maven project directory
            timeout: Timeout in seconds
        
        Returns:
            Maven execution result
        """
        return await self._run_maven_command(
            project_dir, 
            ["validate"], 
            timeout=timeout
        )
    
    async def _run_maven_command(
        self, 
        project_dir: Path, 
        command_args: List[str], 
        timeout: int = 300
    ) -> MavenResult:
        """
        Run a Maven command.
        
        Args:
            project_dir: Project directory
            command_args: Maven command arguments
            timeout: Timeout in seconds
        
        Returns:
            Maven execution result
        """
        import time
        
        start_time = time.time()
        command = [self.maven_executable] + command_args
        command_str = " ".join(command)
        
        self.logger.info(f"Running Maven command: {command_str}")
        self.logger.debug(f"Working directory: {project_dir}")
        
        # Prepare environment
        env = self._prepare_environment()
        
        try:
            # Run the command
            process = subprocess.run(
                command,
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )
            
            execution_time = time.time() - start_time
            
            result = MavenResult(
                success=process.returncode == 0,
                exit_code=process.returncode,
                stdout=process.stdout,
                stderr=process.stderr,
                execution_time=execution_time,
                command=command_str
            )
            
            if result.success:
                self.logger.info(f"Maven command completed successfully in {execution_time:.2f}s")
            else:
                self.logger.warning(f"Maven command failed with exit code {process.returncode}")
                self.logger.debug(f"STDOUT: {process.stdout}")
                self.logger.debug(f"STDERR: {process.stderr}")
            
            return result
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            self.logger.error(f"Maven command timed out after {timeout}s")
            
            return MavenResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {timeout} seconds",
                execution_time=execution_time,
                command=command_str
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"Failed to run Maven command: {command_str}: {e}")
            
            return MavenResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Command execution failed: {str(e)}",
                execution_time=execution_time,
                command=command_str
            )
    
    def _prepare_environment(self) -> Dict[str, str]:
        """Prepare environment variables for Maven execution."""
        import os
        
        env = os.environ.copy()
        
        if self.java_home:
            env['JAVA_HOME'] = str(self.java_home)
        
        if self.maven_home:
            env['M2_HOME'] = str(self.maven_home)
            env['MAVEN_HOME'] = str(self.maven_home)
        
        return env
    
    def parse_compilation_errors(self, maven_result: MavenResult) -> List[CompilationError]:
        """
        Parse compilation errors from Maven output.
        
        Args:
            maven_result: Maven execution result
        
        Returns:
            List of parsed compilation errors
        """
        errors = []
        
        # Combine stdout and stderr for analysis
        output = maven_result.stdout + "\n" + maven_result.stderr
        
        # Maven emits Java compiler errors in two possible formats:
        #
        # Format A (javac via maven-compiler-plugin, most common):
        #   [ERROR] /path/to/File.java:[42,15] error: cannot find symbol
        #
        # Format B (older maven-compiler-plugin or certain configurations):
        #   [ERROR] /path/to/File.java:42: error: cannot find symbol
        #
        # Both formats must be captured.

        # Format A: [ERROR] <path>:[<line>,<col>] <message>
        pattern_a = re.compile(
            r'^\[ERROR\]\s+([^\[]+):\[(\d+),(\d+)\]\s+(?:error:\s*)?(.+)$',
            re.MULTILINE
        )
        # Format B: [ERROR] <path>:<line>: <message>
        pattern_b = re.compile(
            r'^\[ERROR\]\s+([^:\[]+):(\d+):\s+(?:error:\s*)?(.+)$',
            re.MULTILINE
        )

        seen = set()  # deduplicate by (file, line, message)

        def _classify(message: str) -> str:
            msg = message.lower()
            if "cannot find symbol" in msg:
                return "symbol_not_found"
            if "package does not exist" in msg:
                return "package_not_found"
            if "method" in msg and "cannot be applied" in msg:
                return "method_signature"
            if "incompatible types" in msg:
                return "type_mismatch"
            return "compilation"

        for match in pattern_a.finditer(output):
            file_path    = match.group(1).strip()
            line_number  = int(match.group(2))
            column_number = int(match.group(3))
            error_message = match.group(4).strip()
            key = (file_path, line_number, error_message)
            if key in seen:
                continue
            seen.add(key)
            errors.append(CompilationError(
                file_path=file_path,
                line_number=line_number,
                column_number=column_number,
                error_type=_classify(error_message),
                message=error_message,
                full_error=match.group(0)
            ))

        for match in pattern_b.finditer(output):
            file_path    = match.group(1).strip()
            line_number  = int(match.group(2))
            error_message = match.group(3).strip()
            key = (file_path, line_number, error_message)
            if key in seen:
                continue
            seen.add(key)
            errors.append(CompilationError(
                file_path=file_path,
                line_number=line_number,
                column_number=0,
                error_type=_classify(error_message),
                message=error_message,
                full_error=match.group(0)
            ))

        return errors
    
    def parse_test_failures(self, maven_result: MavenResult) -> List[Dict[str, Any]]:
        """
        Parse test failures from Maven output.
        
        Args:
            maven_result: Maven execution result
        
        Returns:
            List of parsed test failures
        """
        failures = []
        
        # Combine stdout and stderr for analysis
        output = maven_result.stdout + "\n" + maven_result.stderr
        
        # Pattern for test failures
        failure_pattern = r'Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)'
        
        for match in re.finditer(failure_pattern, output):
            tests_run = int(match.group(1))
            failures_count = int(match.group(2))
            errors_count = int(match.group(3))
            skipped_count = int(match.group(4))
            
            if failures_count > 0 or errors_count > 0:
                failures.append({
                    'tests_run': tests_run,
                    'failures': failures_count,
                    'errors': errors_count,
                    'skipped': skipped_count,
                    'context': match.group(0)
                })
        
        # Look for specific test method failures
        method_failure_pattern = r'(\w+\.\w+)\s+Time elapsed:\s+[\d.]+\s+sec\s+<<<\s+(FAILURE|ERROR)!'
        
        for match in re.finditer(method_failure_pattern, output):
            test_method = match.group(1)
            failure_type = match.group(2)
            
            failures.append({
                'test_method': test_method,
                'failure_type': failure_type,
                'context': match.group(0)
            })
        
        return failures
    
    def get_maven_version(self) -> Optional[str]:
        """
        Get Maven version.
        
        Returns:
            Maven version string or None if unable to determine
        """
        try:
            result = subprocess.run(
                [self.maven_executable, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # Extract version from first line
                first_line = result.stdout.split('\n')[0]
                version_match = re.search(r'Apache Maven ([\d.]+)', first_line)
                if version_match:
                    return version_match.group(1)
            
        except Exception as e:
            self.logger.error(f"Failed to get Maven version: {e}")
        
        return None
    
    def is_maven_project(self, directory: Path) -> bool:
        """
        Check if a directory contains a Maven project.
        
        Args:
            directory: Directory to check
        
        Returns:
            True if directory contains a Maven project
        """
        pom_file = directory / "pom.xml"
        return pom_file.exists() and pom_file.is_file()
    
    def get_project_info(self, project_dir: Path) -> Dict[str, Any]:
        """
        Get basic information about a Maven project.
        
        Args:
            project_dir: Project directory
        
        Returns:
            Project information dictionary
        """
        info = {
            'is_maven_project': self.is_maven_project(project_dir),
            'pom_exists': (project_dir / "pom.xml").exists(),
            'src_main_java_exists': (project_dir / "src" / "main" / "java").exists(),
            'src_test_java_exists': (project_dir / "src" / "test" / "java").exists(),
            'target_exists': (project_dir / "target").exists()
        }
        
        return info

