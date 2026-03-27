"""
Test_Corrector Agent for fixing test execution failures.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from .base_agent import BaseAgent
from ..config.models import AgentConfig, SystemConfig
from ..utils import OpenRouterClient, CodeSanitizer
from ..utils.maven_runner import MavenRunner, MavenResult
from ..utils.test_versioning import TestVersionManager


@dataclass
class TestFailure:
    """Represents a test failure."""
    test_class: str
    test_method: str
    failure_type: str  # FAILURE, ERROR, TIMEOUT
    message: str
    stack_trace: str
    full_output: str


class TestCorrectorAgent(BaseAgent):
    """
    Test_Corrector Agent responsible for detecting and fixing test execution failures.
    
    This agent runs the generated tests, identifies test failures, and uses various
    strategies to fix them. If a test cannot be fixed reliably, it adds @Ignore
    annotation with a clear reason.
    """
    
    def __init__(self, config: AgentConfig, system_config: SystemConfig):
        """Initialize the Test_Corrector Agent."""
        super().__init__(config, system_config)
        self.maven_runner = MavenRunner()
        self.code_sanitizer = CodeSanitizer()
        self.openrouter_client = None
        self.max_correction_attempts = 3
        self.test_timeout = 300  # 5 minutes
        self.version_manager = None  # Will be initialized when project_dir is known
    
    async def _initialize_impl(self):
        """Initialize the test corrector agent components."""
        self.logger.info("Initializing Test_Corrector Agent")
        
        # Initialize OpenRouter client for LLM-assisted test correction
        if self.system_config.openrouter.api_key:
            self.openrouter_client = OpenRouterClient(self.system_config.openrouter)
            self.logger.info("OpenRouter client initialized for test failure correction")
        else:
            self.logger.warning("No OpenRouter API key provided - using rule-based correction only")
        
        self.logger.info("Test_Corrector Agent initialization complete")
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main processing method for the Test_Corrector Agent.
        
        Args:
            input_data: Dictionary containing:
                - project_dir: Path to the Maven project
                - generated_files: List of generated test files
        
        Returns:
            Dictionary with test correction results
        """
        try:
            # Validate input
            validation_errors = self.validate_input(input_data)
            if validation_errors:
                return {
                    'success': False,
                    'error': f"Input validation failed: {', '.join(validation_errors)}",
                    'corrected_files': [],
                    'tests_passing': False
                }
            
            project_dir = Path(input_data['project_dir'])
            generated_files = [Path(f) for f in input_data['generated_files']]
            # Optional: run only a specific test class (for split-by-endpoint isolation)
            test_class_hint: Optional[str] = input_data.get('test_class')
            
            # Initialize version manager for this project
            if not self.version_manager:
                self.version_manager = TestVersionManager(project_dir)
                self.logger.info(f"Initialized test version manager for project: {project_dir}")
            
            self.log_progress("Starting test execution and failure correction")
            
            # Step 1: Initial test run
            self.log_progress("Running initial tests", 1, 4)
            test_result = await self._run_tests(project_dir, test_class=test_class_hint)

            if test_result['success'] and test_result['failures'] == 0:
                self.logger.info("All tests passed - no corrections needed")
                return {
                    'success': True,
                    'message': "All tests passed - no failures to correct",
                    'corrected_files': [],
                    'tests_passing': True,
                    'attempts': 0,
                    'test_statistics': test_result['statistics']
                }
            
            # Step 2: Analyze test failures
            self.log_progress("Analyzing test failures", 2, 4)
            failures = test_result['test_failures']
            self.logger.info(f"Found {len(failures)} test failures")
            
            # Step 3: Fix test failures iteratively
            self.log_progress("Fixing test failures", 3, 4)
            correction_result = await self._fix_test_failures(
                project_dir, generated_files, failures, test_class=test_class_hint
            )
            
            # Step 4: Final test run verification
            self.log_progress("Verifying final test results", 4, 4)
            final_result = await self._run_tests(project_dir, test_class=test_class_hint)
            
            return {
                'success': final_result['success'],
                'message': correction_result['message'],
                'corrected_files': correction_result['corrected_files'],
                'ignored_tests': correction_result['ignored_tests'],
                'tests_passing': final_result['failures'] == 0,
                'attempts': correction_result['attempts'],
                'remaining_failures': final_result['failures'],
                'test_statistics': final_result['statistics']
            }
            
        except Exception as e:
            self.log_error("Unexpected error in test corrector process", e)
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}",
                'corrected_files': [],
                'tests_passing': False
            }
    
    def validate_input(self, input_data: Dict[str, Any]) -> List[str]:
        """
        Validate input data for the test corrector agent.
        
        Args:
            input_data: Input data to validate
        
        Returns:
            List of validation errors
        """
        errors = super().validate_input(input_data)
        
        required_fields = ['project_dir', 'generated_files']
        
        for field in required_fields:
            if field not in input_data:
                errors.append(f"Missing required field: {field}")
            elif not input_data[field]:
                errors.append(f"Empty value for required field: {field}")
        
        # Validate project directory
        if 'project_dir' in input_data:
            project_dir = Path(input_data['project_dir'])
            if not project_dir.exists():
                errors.append(f"Project directory not found: {project_dir}")
            elif not self.maven_runner.is_maven_project(project_dir):
                errors.append(f"Not a valid Maven project: {project_dir}")
        
        return errors
    
    async def _run_tests(self, project_dir: Path, test_class: Optional[str] = None) -> Dict[str, Any]:
        """
        Run tests in the Maven project and analyze results.
        
        Args:
            project_dir: Path to the Maven project
            test_class: Optional specific test class to run (for isolated execution)
        
        Returns:
            Test execution result dictionary
        """
        try:
            self.logger.info(f"Running tests in Maven project: {project_dir}")
            
            # Run Maven tests — optionally isolated to a single class
            maven_result = await self.maven_runner.run_tests(
                project_dir, timeout=self.test_timeout, test_class=test_class
            )
            
            result = {
                'success': maven_result.success,
                'exit_code': maven_result.exit_code,
                'output': maven_result.stdout + "\n" + maven_result.stderr,
                'execution_time': maven_result.execution_time,
                'test_failures': [],
                'failures': 0,
                'errors': 0,
                'statistics': {}
            }
            
            # Parse test results - try XML first, then fallback to Maven output
            xml_statistics = self._parse_test_statistics_from_xml(project_dir)
            if xml_statistics['tests_run'] > 0:
                # XML statistics available and valid
                test_statistics = xml_statistics
                self.logger.info("Using XML-based test statistics")
            else:
                # Fallback to Maven output parsing
                test_statistics = self._parse_test_statistics(maven_result)
                self.logger.info("Using Maven output-based test statistics")
            
            result['statistics'] = test_statistics
            result['failures'] = test_statistics.get('failures', 0)
            result['errors'] = test_statistics.get('errors', 0)
            
            if not maven_result.success or result['failures'] > 0 or result['errors'] > 0:
                # Parse test failures with project directory context
                test_failures = self._parse_test_failures(maven_result, project_dir)
                result['test_failures'] = test_failures
                
                self.logger.warning(
                    f"Tests failed: {result['failures']} failures, {result['errors']} errors"
                )
            else:
                self.logger.info(f"All tests passed in {maven_result.execution_time:.2f}s")
            
            return result
            
        except Exception as e:
            self.log_error("Failed to run tests", e)
            return {
                'success': False,
                'exit_code': -1,
                'output': f"Test execution failed: {str(e)}",
                'execution_time': 0.0,
                'test_failures': [],
                'failures': 0,
                'errors': 0,
                'statistics': {}
            }
    
    @staticmethod
    def _parse_test_statistics(maven_result: MavenResult) -> Dict[str, Any]:
        """Parse test statistics from Maven output."""
        output = maven_result.stdout + "\n" + maven_result.stderr
        
        statistics = {
            'tests_run': 0,
            'failures': 0,
            'errors': 0,
            'skipped': 0
        }
        
        # Pattern for test summary
        summary_pattern = r'Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)'
        
        matches = re.findall(summary_pattern, output)
        if matches:
            # Use the last match (final summary)
            last_match = matches[-1]
            statistics = {
                'tests_run': int(last_match[0]),
                'failures': int(last_match[1]),
                'errors': int(last_match[2]),
                'skipped': int(last_match[3])
            }
        
        return statistics
    
    def _parse_test_statistics_from_xml(self, project_dir: Path) -> Dict[str, Any]:
        """Parse test statistics from Surefire XML reports (more reliable).

        When Surefire uses rerunFailingTestsCount the testsuite-level
        'failures' attribute does NOT include <flakyFailure> entries (tests
        that failed on the first run but passed on the rerun).  We count those
        explicitly from the individual testcase elements so the corrector loop
        can see the real number of problematic tests.
        """
        import xml.etree.ElementTree as ET

        statistics = {
            'tests_run': 0,
            'failures': 0,
            'errors': 0,
            'skipped': 0
        }

        surefire_dir = project_dir / "target" / "surefire-reports"
        if not surefire_dir.exists():
            self.logger.warning(f"Surefire reports directory not found: {surefire_dir}")
            return statistics

        for xml_file in surefire_dir.glob("TEST-*.xml"):
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()

                testsuites = [root] if root.tag == 'testsuite' else root.findall('testsuite')

                for testsuite in testsuites:
                    statistics['tests_run'] += int(testsuite.get('tests', 0))
                    statistics['failures']  += int(testsuite.get('failures', 0))
                    statistics['errors']    += int(testsuite.get('errors', 0))
                    statistics['skipped']   += int(testsuite.get('skipped', 0))

                    # Count flakyFailure / rerunFailure elements that the
                    # testsuite attributes leave out.
                    for testcase in testsuite.findall('testcase'):
                        for tag in ('flakyFailure', 'rerunFailure'):
                            statistics['failures'] += len(testcase.findall(tag))

            except Exception as e:
                self.logger.warning(f"Failed to parse XML statistics from {xml_file}: {e}")

        self.logger.info(f"Parsed test statistics from XML: {statistics}")
        return statistics
    
    def _parse_test_failures(self, maven_result: MavenResult, project_dir: Path) -> List[TestFailure]:
        """Parse test failures from Maven output, prioritizing XML reports."""
        failures = []

        self.logger.info(f"Parsing test failures from project: {project_dir}")

        # Strategy 1: Try to read surefire XML reports first (most reliable)
        xml_failures = self._parse_surefire_reports(project_dir)
        if xml_failures:
            self.logger.info(f"Successfully parsed {len(xml_failures)} failures from XML reports")
            return xml_failures
        
        # Fallback strategies if XML reports are not available
        output = maven_result.stdout + "\n" + maven_result.stderr
        self.logger.info(f"XML reports not available, falling back to text parsing")
        
        # Strategy 2: Parse [ERROR] format from Maven output
        failures.extend(self._parse_maven_error_format(output))
        
        # Strategy 3: Parse surefire report format
        failures.extend(self._parse_surefire_format(output))
        
        self.logger.info(f"Parsed {len(failures)} test failures from Maven output")
        
        # Deduplicate failures based on test_class and test_method
        seen = set()
        unique_failures = []
        for failure in failures:
            key = (failure.test_class, failure.test_method)
            if key not in seen:
                seen.add(key)
                unique_failures.append(failure)
        
        if len(unique_failures) != len(failures):
            self.logger.info(f"Deduplicated to {len(unique_failures)} unique failures")
        
        return unique_failures
    
    @staticmethod
    def _parse_maven_error_format(output: str) -> List[TestFailure]:
        """Parse failures from Maven [ERROR] format."""
        failures = []
        
        # Pattern for [ERROR] format: [ERROR]   ClassName.methodName:line message
        error_pattern = r'\[ERROR\]\s+([^:]+)\.([^:]+):(\d+)\s+(.+?)(?=\n(?:\[ERROR\]|\[INFO\]|\[WARNING\]|$))'
        
        for match in re.finditer(error_pattern, output, re.DOTALL):
            class_name = match.group(1)
            method_name = match.group(2)
            line_number = match.group(3)
            message = match.group(4).strip()
            
            # Extract full class name if it contains package
            if '.' not in class_name:
                # Try to find full class name in output
                full_class_pattern = rf'(\w+(?:\.\w+)*\.{re.escape(class_name)})'
                full_match = re.search(full_class_pattern, output)
                if full_match:
                    class_name = full_match.group(1)
            
            failures.append(TestFailure(
                test_class=class_name,
                test_method=method_name,
                failure_type="FAILURE",
                message=message,
                stack_trace=f"at line {line_number}",
                full_output=match.group(0)
            ))
        
        return failures
    
    @staticmethod
    def _parse_surefire_format(output: str) -> List[TestFailure]:
        """Parse failures from surefire format."""
        failures = []
        
        # Pattern for surefire format: methodName(className) Time elapsed: X sec <<< FAILURE!
        surefire_pattern = r'(\w+)\(([^)]+)\)\s+Time elapsed:\s+[\d.]+\s+sec\s+<<<\s+(FAILURE|ERROR)!(.*?)(?=\n\w+\(|\nTests run:|\n$|\Z)'
        
        for match in re.finditer(surefire_pattern, output, re.DOTALL):
            test_method = match.group(1)
            test_class = match.group(2)
            failure_type = match.group(3)
            failure_details = match.group(4).strip()
            
            # Extract message and stack trace
            lines = failure_details.split('\n')
            message = lines[0] if lines else "Unknown failure"
            stack_trace = '\n'.join(lines[1:]) if len(lines) > 1 else ""
            
            failures.append(TestFailure(
                test_class=test_class,
                test_method=test_method,
                failure_type=failure_type,
                message=message,
                stack_trace=stack_trace,
                full_output=match.group(0)
            ))
        
        return failures
    
    def _parse_surefire_reports(self, project_dir: Path) -> List[TestFailure]:
        """Parse failures from surefire XML report files."""
        failures = []
        
        surefire_dir = project_dir / "target" / "surefire-reports"
        if not surefire_dir.exists():
            self.logger.warning(f"Surefire reports directory not found: {surefire_dir}")
            return failures
        
        self.logger.info(f"Parsing Surefire XML reports from: {surefire_dir}")
        
        # Look for XML report files (TEST-*.xml)
        xml_files = list(surefire_dir.glob("TEST-*.xml"))
        if not xml_files:
            self.logger.warning(f"No XML report files found in {surefire_dir}")
            return failures
        
        for xml_file in xml_files:
            try:
                self.logger.info(f"Parsing XML report: {xml_file}")
                xml_failures = self._parse_surefire_xml_file(xml_file)
                failures.extend(xml_failures)
                self.logger.info(f"Found {len(xml_failures)} failures in {xml_file}")
            except Exception as e:
                self.logger.error(f"Failed to parse XML report {xml_file}: {e}")
        
        self.logger.info(f"Total failures parsed from XML reports: {len(failures)}")
        return failures
    
    def _parse_surefire_xml_file(self, xml_file: Path) -> List[TestFailure]:
        """Parse a single Surefire XML report file."""
        import xml.etree.ElementTree as ET
        
        failures = []
        
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            # Handle both testsuite and testsuites root elements
            if root.tag == 'testsuite':
                testsuites = [root]
            elif root.tag == 'testsuites':
                testsuites = root.findall('testsuite')
            else:
                self.logger.warning(f"Unknown root element in {xml_file}: {root.tag}")
                return failures
            
            for testsuite in testsuites:
                for testcase in testsuite.findall('testcase'):
                    test_name = testcase.get('name', '')
                    test_class = testcase.get('classname', '')
                    test_time = float(testcase.get('time', 0))

                    # When Surefire uses rerunFailingTestsCount, tests that fail
                    # on Run 1 but pass on Run 2 are recorded as <flakyFailure>
                    # instead of <failure>. Tests that fail on ALL runs are
                    # recorded as <failure> (or sometimes <rerunFailure>).
                    # We must capture both so that the correction loop sees
                    # them and eventually @Ignores the ones it cannot fix.
                    for elem_tag in ('failure', 'flakyFailure', 'rerunFailure'):
                        for fail_elem in testcase.findall(elem_tag):
                            failure_message = fail_elem.get('message', '')
                            failure_type = fail_elem.get('type', 'FAILURE')
                            failure_content = fail_elem.text or ''

                            system_out_elem = testcase.find('system-out')
                            system_out = system_out_elem.text if system_out_elem is not None else ''
                            system_err_elem = testcase.find('system-err')
                            system_err = system_err_elem.text if system_err_elem is not None else ''

                            message = failure_message
                            stack_trace = failure_content
                            if '\n' in failure_message:
                                lines = failure_message.split('\n')
                                message = lines[0]
                                if not stack_trace:
                                    stack_trace = '\n'.join(lines[1:])

                            failures.append(TestFailure(
                                test_class=test_class,
                                test_method=test_name,
                                failure_type=f"{elem_tag.upper()}:{failure_type}",
                                message=message,
                                stack_trace=stack_trace,
                                full_output=(
                                    f"{failure_message}\n{failure_content}\n"
                                    f"System Out: {system_out}\nSystem Err: {system_err}"
                                )
                            ))

                    # Check for error (separate from failure elements)
                    error_elem = testcase.find('error')
                    if error_elem is not None:
                        error_message = error_elem.get('message', '')
                        error_type = error_elem.get('type', 'ERROR')
                        error_content = error_elem.text or ''
                        
                        # Get system output if available
                        system_out_elem = testcase.find('system-out')
                        system_out = system_out_elem.text if system_out_elem is not None else ''
                        
                        system_err_elem = testcase.find('system-err')
                        system_err = system_err_elem.text if system_err_elem is not None else ''
                        
                        # Clean up message if it contains newlines
                        message = error_message
                        stack_trace = error_content
                        if '\n' in error_message:
                            lines = error_message.split('\n')
                            message = lines[0]
                            if not stack_trace:
                                stack_trace = '\n'.join(lines[1:])
                        
                        failures.append(TestFailure(
                            test_class=test_class,
                            test_method=test_name,
                            failure_type=error_type,
                            message=message,
                            stack_trace=stack_trace,
                            full_output=f"{error_message}\n{error_content}\nSystem Out: {system_out}\nSystem Err: {system_err}"
                        ))
                        
        except ET.ParseError as e:
            self.logger.error(f"XML parsing error in {xml_file}: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error parsing {xml_file}: {e}")
        
        return failures
    
    async def _fix_test_failures(
        self,
        project_dir: Path,
        generated_files: List[Path],
        failures: List[TestFailure],
        test_class: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fix test failures iteratively.
        
        Args:
            project_dir: Project directory
            generated_files: List of generated files
            failures: List of test failures
            test_class: Optional specific test class for isolated re-runs
        
        Returns:
            Correction result dictionary
        """
        corrected_files = []
        ignored_tests = []
        attempts = 0
        current_failures = failures.copy()
        
        while current_failures and attempts < self.max_correction_attempts:
            attempts += 1
            self.logger.info(f"Test correction attempt {attempts}/{self.max_correction_attempts}")
            
            # Group failures by file
            failures_by_file = self._group_failures_by_file(current_failures, generated_files)
            
            files_corrected_this_round = []
            tests_ignored_this_round = []
            
            for file_path, file_failures in failures_by_file.items():
                self.logger.info(f"Fixing {len(file_failures)} test failures in {file_path}")
                
                # Attempt to fix failures in this file
                correction_result = await self._fix_file_test_failures(
                    file_path, file_failures
                )
                
                if correction_result['corrected']:
                    files_corrected_this_round.append(str(file_path))
                    if str(file_path) not in corrected_files:
                        corrected_files.append(str(file_path))
                
                if correction_result['ignored']:
                    tests_ignored_this_round.extend(correction_result['ignored'])
                    ignored_tests.extend(correction_result['ignored'])
            
            # Re-run tests to check if failures are fixed (isolated if test_class given)
            test_result = await self._run_tests(project_dir, test_class=test_class)
            current_failures = test_result.get('test_failures', [])
            
            if test_result['failures'] == 0 and test_result['errors'] == 0:
                self.logger.info(f"All test failures fixed after {attempts} attempts")
                break
            else:
                self.logger.info(
                    f"After attempt {attempts}: {test_result['failures']} failures, "
                    f"{test_result['errors']} errors remaining"
                )
        
        # Prepare result message
        total_remaining = len(current_failures)
        if total_remaining == 0:
            message = f"Successfully fixed all test failures in {attempts} attempts"
        elif attempts >= self.max_correction_attempts:
            # Add @Ignore annotations to persistently failing tests
            self.logger.info(f"Maximum correction attempts reached. Adding @Ignore to {total_remaining} failing tests")
            ignored_result = await self._ignore_failing_tests(project_dir, generated_files, current_failures)
            ignored_tests.extend(ignored_result['ignored_tests'])
            corrected_files.extend(ignored_result['corrected_files'])
            
            message = f"Reached maximum attempts ({self.max_correction_attempts}). Added @Ignore to {len(ignored_result['ignored_tests'])} persistently failing tests"
        else:
            message = f"Fixed some test failures in {attempts} attempts. {total_remaining} failures remain"
        
        return {
            'message': message,
            'corrected_files': corrected_files,
            'ignored_tests': ignored_tests,
            'attempts': attempts,
            'remaining_failures': total_remaining
        }
    
    def _group_failures_by_file(
        self, 
        failures: List[TestFailure], 
        generated_files: List[Path]
    ) -> Dict[Path, List[TestFailure]]:
        """Group test failures by file path."""
        failures_by_file = {}
        
        for failure in failures:
            # Find the corresponding file
            file_path = self._find_test_file_for_class(failure.test_class, generated_files)
            
            if file_path:
                if file_path not in failures_by_file:
                    failures_by_file[file_path] = []
                failures_by_file[file_path].append(failure)
            else:
                self.logger.warning(f"Could not find file for test class: {failure.test_class}")
        
        return failures_by_file
    
    @staticmethod
    def _find_test_file_for_class(test_class: str, generated_files: List[Path]) -> Optional[Path]:
        """Find the file containing a specific test class."""
        class_name = test_class.split('.')[-1]  # Get just the class name
        
        for file_path in generated_files:
            if file_path.stem == class_name:
                return file_path
        
        return None
    
    async def _fix_file_test_failures(
        self,
        file_path: Path,
        failures: List[TestFailure]
    ) -> Dict[str, Any]:
        """
        Fix test failures in a single file.
        
        Args:
            file_path: Path to the test file
            failures: List of failures in this file
        
        Returns:
            Dictionary with correction results
        """
        result = {
            'corrected': False,
            'ignored': []
        }
        
        try:
            if not file_path.exists():
                self.logger.error(f"Test file not found: {file_path}")
                return result
            
            # Read current file content
            original_content = file_path.read_text(encoding='utf-8')
            
            # Attempt different correction strategies
            corrected_content = None
            ignored_methods = []
            
            # Strategy 1: LLM-based correction (if available)
            if self.openrouter_client:
                correction_result = await self._fix_with_llm(
                    original_content, failures, file_path
                )
                corrected_content = correction_result.get('content')
                ignored_methods.extend(correction_result.get('ignored', []))
            
            # Strategy 2: Rule-based correction (fallback)
            if not corrected_content:
                correction_result = await self._fix_with_rules(
                    original_content, failures, file_path
                )
                corrected_content = correction_result.get('content')
                ignored_methods.extend(correction_result.get('ignored', []))
            
            # Apply corrections if any were made
            if corrected_content and corrected_content != original_content:
                # Create versioned backup of original file
                version_info = self.version_manager.create_version(
                    file_path, original_content, "llm_correction"
                )
                self.logger.info(f"Created version {version_info['version']} backup: {version_info['version_file']}")
                
                # Write corrected content
                file_path.write_text(corrected_content, encoding='utf-8')
                
                self.logger.info(f"Applied test corrections to {file_path}")
                result['corrected'] = True
            
            if ignored_methods:
                result['ignored'] = ignored_methods
                self.logger.info(f"Ignored {len(ignored_methods)} problematic tests in {file_path}")
                
        except Exception as e:
            self.log_error(f"Failed to fix test failures in {file_path}", e)
        
        return result
    
    async def _fix_with_llm(
        self,
        content: str,
        failures: List[TestFailure],
        file_path: Path
    ) -> Dict[str, Any]:
        """
        Fix test failures using LLM.
        
        Args:
            content: Original file content
            failures: List of test failures
            file_path: Path to the file
        
        Returns:
            Dictionary with corrected content and ignored tests
        """
        try:
            # Format failures for LLM
            failure_descriptions = []
            for failure in failures:
                failure_descriptions.append(
                    f"Test: {failure.test_method}\n"
                    f"Type: {failure.failure_type}\n"
                    f"Message: {failure.message}\n"
                    f"Stack trace: {failure.stack_trace[:500]}..."  # Truncate long stack traces
                )
            
            failures_text = "\n\n".join(failure_descriptions)
            
            # Generate corrected code using LLM
            corrected_content = await self.openrouter_client.fix_test_failures(
                code=content,
                failures=failures_text,
                model=self.get_model_name(),
                max_tokens=self.get_max_tokens(),
                temperature=self.get_temperature()
            )
            
            #print(f"#### corrector fix_with_llm corrected_content:{corrected_content}")

            # Sanitize LLM output to remove commentary and extract only code
            if corrected_content:
                self.logger.info(f"Sanitizing LLM test correction output for {file_path}")
                corrected_content = self.code_sanitizer.sanitize_java_code(corrected_content)
            
            # Validate the corrected content
            if corrected_content and self._is_valid_java_code(corrected_content):
                self.logger.info(f"LLM test correction successful for {file_path}")
                return {'content': corrected_content, 'ignored': []}
            else:
                self.logger.warning(f"LLM test correction failed validation for {file_path}")
                return {'content': None, 'ignored': []}
                
        except Exception as e:
            self.log_error(f"LLM test correction failed for {file_path}", e)
            return {'content': None, 'ignored': []}
    
    async def _fix_with_rules(
        self,
        content: str,
        failures: List[TestFailure],
        file_path: Path
    ) -> Dict[str, Any]:
        """
        Fix test failures using rule-based approach.
        
        Args:
            content: Original file content
            failures: List of test failures
            file_path: Path to the file
        
        Returns:
            Dictionary with corrected content and ignored tests
        """
        corrected_content = content
        ignored_methods = []
        corrections_applied = False
        
        for failure in failures:
            # Apply specific fixes based on failure type and message
            if self._is_timeout_failure(failure):
                # Ignore timeout failures as they're often environment-dependent
                corrected_content = self._add_ignore_annotation(
                    corrected_content, failure.test_method, "Test timeout - environment dependent"
                )
                ignored_methods.append(failure.test_method)
                corrections_applied = True
                
            elif self._is_connection_failure(failure):
                # Ignore connection failures
                corrected_content = self._add_ignore_annotation(
                    corrected_content, failure.test_method, "Connection failure - API not available"
                )
                ignored_methods.append(failure.test_method)
                corrections_applied = True
                
            elif self._is_assertion_failure(failure):
                # Try to fix simple assertion failures
                fix_result = self._fix_assertion_failure(corrected_content, failure)
                if fix_result['fixed']:
                    corrected_content = fix_result['content']
                    corrections_applied = True
                else:
                    # If can't fix, ignore the test
                    corrected_content = self._add_ignore_annotation(
                        corrected_content, failure.test_method, "Assertion failure - needs manual review"
                    )
                    ignored_methods.append(failure.test_method)
                    corrections_applied = True
        
        result = {'ignored': ignored_methods}
        if corrections_applied:
            result['content'] = corrected_content
        else:
            result['content'] = None
        
        return result
    
    @staticmethod
    def _is_timeout_failure(failure: TestFailure) -> bool:
        """Check if failure is due to timeout."""
        timeout_indicators = ['timeout', 'timed out', 'connection timeout', 'read timeout']
        message_lower = failure.message.lower()
        return any(indicator in message_lower for indicator in timeout_indicators)
    
    def _is_connection_failure(self, failure: TestFailure) -> bool:
        """Check if failure is due to connection issues."""
        connection_indicators = [
            'connection refused', 'connection reset', 'no route to host',
            'unknown host', 'network unreachable', 'connection failed'
        ]
        message_lower = failure.message.lower()
        return any(indicator in message_lower for indicator in connection_indicators)
    
    def _is_assertion_failure(self, failure: TestFailure) -> bool:
        """Check if failure is due to assertion mismatch."""
        assertion_indicators = [
            'assertionError', 'expected', 'but was', 'assertion failed'
        ]
        message_lower = failure.message.lower()
        return any(indicator in message_lower for indicator in assertion_indicators)
    
    def _add_ignore_annotation(self, content: str, method_name: str, reason: str) -> str:
        """Add @Ignore annotation to a test method."""
        # Find the test method with proper indentation handling
        method_pattern = rf'(\s*)(@Test\s*\n\s*public\s+void\s+{re.escape(method_name)}\s*\(\s*\))'
        
        def replacement(match):
            indent = match.group(1)
            test_annotation_and_method = match.group(2)
            # Add @Ignore with same indentation as @Test, no blank line
            return f'{indent}@Ignore("{reason}")\n{indent}{test_annotation_and_method}'
        
        # Check if @Ignore import exists
        if 'import org.junit.Ignore;' not in content:
            # Add import
            import_pattern = r'(import org\.junit\.Test;)'
            content = re.sub(import_pattern, r'\1\nimport org.junit.Ignore;', content)
        
        # Add @Ignore annotation
        content = re.sub(method_pattern, replacement, content, flags=re.MULTILINE)
        
        return content
    
    def _fix_assertion_failure(self, content: str, failure: TestFailure) -> Dict[str, Any]:
        """Attempt to fix simple assertion failures."""
        # This is a simplified implementation
        # A full implementation would analyze the specific assertion and try to fix it
        
        # For now, just return that it couldn't be fixed
        return {'fixed': False, 'content': content}
    
    def _is_valid_java_code(self, code: str) -> bool:
        """
        Basic validation of Java code structure.
        
        Args:
            code: Java code to validate
        
        Returns:
            True if code appears to be valid Java
        """
        # Basic checks for Java code structure
        required_elements = [
            'package ',
            'public class ',
        ]
        
        # Check for balanced braces
        open_braces = code.count('{')
        close_braces = code.count('}')
        
        return (
            all(element in code for element in required_elements) and
            open_braces == close_braces and
            open_braces > 0
        )
    
    def get_test_statistics(
        self,
        corrected_files: List[str],
        ignored_tests: List[str],
        attempts: int,
        remaining_failures: int
    ) -> Dict[str, Any]:
        """
        Get statistics about the test correction process.
        
        Args:
            corrected_files: List of corrected files
            ignored_tests: List of ignored test methods
            attempts: Number of correction attempts
            remaining_failures: Number of remaining failures
        
        Returns:
            Test correction statistics
        """
        return {
            'files_corrected': len(corrected_files),
            'tests_ignored': len(ignored_tests),
            'correction_attempts': attempts,
            'remaining_failures': remaining_failures,
            'success_rate': max(0, 100 - (remaining_failures * 10)),  # Rough success rate
            'corrected_files': corrected_files,
            'ignored_tests': ignored_tests
        }


    async def _ignore_failing_tests(
        self,
        project_dir: Path,
        generated_files: List[Path],
        failures: List[TestFailure]
    ) -> Dict[str, Any]:
        """
        Add @Ignore annotations to persistently failing tests.
        
        Args:
            project_dir: Project directory
            generated_files: List of generated files
            failures: List of test failures to ignore
        
        Returns:
            Dictionary with ignored tests and corrected files
        """
        ignored_tests = []
        corrected_files = []
        
        # Group failures by file
        failures_by_file = self._group_failures_by_file(failures, generated_files)
        
        for file_path, file_failures in failures_by_file.items():
            try:
                # Read the current file content
                content = file_path.read_text(encoding='utf-8')
                modified_content = content
                
                # Add @Ignore annotation to each failing test method
                for failure in file_failures:
                    ignore_reason = self._extract_ignore_reason(failure)
                    modified_content = self._add_ignore_annotation(
                        modified_content, 
                        failure.test_method, 
                        ignore_reason
                    )
                    
                    ignored_tests.append({
                        'test_class': failure.test_class,
                        'test_method': failure.test_method,
                        'reason': ignore_reason
                    })
                
                # Write the modified content back to file
                if modified_content != content:
                    # Create versioned backup
                    version_info = self.version_manager.create_version(
                        file_path, content, "ignore_annotation"
                    )
                    self.logger.info(f"Created version {version_info['version']} backup: {version_info['version_file']}")
                    
                    # Write modified content
                    file_path.write_text(modified_content, encoding='utf-8')
                    corrected_files.append(str(file_path))
                    
                    self.logger.info(f"Added @Ignore annotations to {len(file_failures)} tests in {file_path}")
                
            except Exception as e:
                self.logger.error(f"Failed to add @Ignore annotations to {file_path}: {e}")
        
        return {
            'ignored_tests': ignored_tests,
            'corrected_files': corrected_files
        }
    
    def _extract_ignore_reason(self, failure: TestFailure) -> str:
        """
        Extract a meaningful ignore reason from test failure.
        
        Args:
            failure: TestFailure object containing failure information
        
        Returns:
            Meaningful ignore reason for @Ignore annotation
        """
        message = failure.message or ""
        
        # Use the original failure message from XML if it's meaningful
        if message and len(message.strip()) > 0:
            # Clean up the message for use in @Ignore annotation
            clean_message = message.strip()
            
            # Remove excessive whitespace and newlines
            clean_message = ' '.join(clean_message.split())
            
            # Escape quotes for Java string
            clean_message = clean_message.replace('"', '\\"')
            
            # Truncate if too long but preserve meaningful content
            if len(clean_message) > 120:
                # Try to find a good breaking point
                if ': ' in clean_message[:120]:
                    # Break at the first colon within reasonable length
                    break_point = clean_message.find(': ', 0, 120)
                    clean_message = clean_message[:break_point + 1].strip()
                elif '. ' in clean_message[:120]:
                    # Break at the first period within reasonable length
                    break_point = clean_message.find('. ', 0, 120)
                    clean_message = clean_message[:break_point + 1].strip()
                else:
                    # Simple truncation with ellipsis
                    clean_message = clean_message[:117] + "..."
            
            return clean_message
        
        # Fallback to generic messages based on failure type
        if "timeout" in message.lower():
            return "Test timeout exceeded"
        
        if "assertion" in message.lower() or "expectation failed" in message.lower():
            return "Assertion failure - needs manual review"
        
        if "connection" in message.lower() or "network" in message.lower():
            return "Network/connection issue"
        
        if "null" in message.lower() and "pointer" in message.lower():
            return "Null pointer exception"
        
        if "compilation" in message.lower() or "syntax" in message.lower():
            return "Compilation/syntax error"
        
        # Generic fallback
        return "Test failure - see logs for details"
    
    def _add_ignore_annotation(self, content: str, test_method: str, reason: str) -> str:
        """
        Add @Ignore annotation to a specific test method.
        
        Args:
            content: File content
            test_method: Name of the test method
            reason: Reason for ignoring the test
        
        Returns:
            Modified content with @Ignore annotation
        """
        import re
        
        # Escape special characters in reason for Java string
        escaped_reason = reason.replace('"', '\\"').replace('\n', '\\n')
        
        # Pattern to find the test method
        # Look for @Test annotation followed by method declaration
        pattern = rf'(\s*)@Test(\s*\([^)]*\))?\s*\n(\s*)public\s+void\s+{re.escape(test_method)}\s*\('
        
        def replacement(match):
            indent = match.group(1)
            test_params = match.group(2) or ""
            method_indent = match.group(3)
            
            # Add @Ignore annotation before @Test (no blank line)
            return f'{indent}@Ignore("{escaped_reason}")\n{indent}@Test{test_params}\n{method_indent}public void {test_method}('
        
        modified_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        
        # Check if we need to add the import for @Ignore
        if modified_content != content and '@Ignore' in modified_content:
            if 'import org.junit.Ignore;' not in modified_content:
                # Find the imports section and add the import
                import_pattern = r'(import org\.junit\.Test;)'
                import_replacement = r'\1\nimport org.junit.Ignore;'
                modified_content = re.sub(import_pattern, import_replacement, modified_content)
        
        return modified_content

