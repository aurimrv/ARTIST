"""
Compiler_Corrector Agent for fixing compilation errors.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base_agent import BaseAgent
from ..config.models import AgentConfig, SystemConfig
from ..utils import OpenRouterClient, CodeSanitizer
from ..utils.maven_runner import MavenRunner, CompilationError


class CompilerCorrectorAgent(BaseAgent):
    """
    Compiler_Corrector Agent responsible for detecting and fixing compilation errors.
    
    This agent compiles the generated test code, identifies compilation errors,
    and uses LLM assistance to fix them automatically. It iterates until all
    compilation errors are resolved or a maximum number of attempts is reached.
    """
    
    def __init__(self, config: AgentConfig, system_config: SystemConfig):
        """Initialize the Compiler_Corrector Agent."""
        super().__init__(config, system_config)
        self.maven_runner = MavenRunner()
        self.code_sanitizer = CodeSanitizer()
        self.openrouter_client = None
        self.max_correction_attempts = 3
    
    async def _initialize_impl(self):
        """Initialize the compiler corrector agent components."""
        self.logger.info("Initializing Compiler_Corrector Agent")
        
        # Initialize OpenRouter client for LLM-assisted error correction
        if self.system_config.openrouter.api_key:
            self.openrouter_client = OpenRouterClient(self.system_config.openrouter)
            self.logger.info("OpenRouter client initialized for compilation error correction")
        else:
            self.logger.warning("No OpenRouter API key provided - using rule-based correction only")
        
        # Check Maven availability
        maven_version = self.maven_runner.get_maven_version()
        if maven_version:
            self.logger.info(f"Maven {maven_version} detected")
        else:
            self.logger.warning("Maven not found - compilation features may be limited")
        
        self.logger.info("Compiler_Corrector Agent initialization complete")
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main processing method for the Compiler_Corrector Agent.
        
        Args:
            input_data: Dictionary containing:
                - project_dir: Path to the Maven project
                - generated_files: List of generated test files
        
        Returns:
            Dictionary with correction results
        """
        try:
            # Validate input
            validation_errors = self.validate_input(input_data)
            if validation_errors:
                return {
                    'success': False,
                    'error': f"Input validation failed: {', '.join(validation_errors)}",
                    'corrected_files': [],
                    'compilation_successful': False
                }
            
            project_dir = Path(input_data['project_dir'])
            generated_files = [Path(f) for f in input_data['generated_files']]
            
            self.log_progress("Starting compilation error detection and correction")
            
            # Step 1: Initial compilation check
            self.log_progress("Running initial compilation", 1, 4)
            compilation_result = await self._compile_project(project_dir)
            
            if compilation_result['success']:
                self.logger.info("Initial compilation successful - no corrections needed")
                return {
                    'success': True,
                    'message': "Compilation successful - no errors to correct",
                    'errors': [],
                    'corrected_files': [],
                    'compilation_successful': True,
                    'attempts': 0
                }
            
            # Step 2: Analyze compilation errors
            self.log_progress("Analyzing compilation errors", 2, 4)
            errors = compilation_result['errors']
            self.logger.info(f"Found {len(errors)} compilation errors")

            # Guard: if the regex parser found nothing but Maven clearly failed,
            # pass the raw compiler output to the LLM so it can still attempt
            # a correction using the full compiler message as context.
            raw_compiler_output = compilation_result.get('output', '')
            if not errors and raw_compiler_output:
                self.logger.warning(
                    "Compilation failed but no structured errors were parsed. "
                    "Will pass raw compiler output to LLM for correction."
                )

            # Step 3: Fix compilation errors iteratively
            self.log_progress("Fixing compilation errors", 3, 4)
            scenarios = input_data['scenarios']
            correction_result = await self._fix_compilation_errors(
                project_dir, generated_files, errors, scenarios,
                raw_compiler_output=raw_compiler_output
            )
            
            # Step 4: Final compilation verification
            self.log_progress("Verifying final compilation", 4, 4)
            final_result = await self._compile_project(project_dir)
            
            return {
                'success': final_result['success'],
                'message': correction_result['message'],
                'errors': final_result.get('errors', []),
                'corrected_files': correction_result['corrected_files'],
                'compilation_successful': final_result['success'],
                'attempts': correction_result['attempts'],
                'remaining_errors': len(final_result.get('errors', [])),
                'final_compilation_output': final_result.get('output', '')
            }
            
        except Exception as e:
            self.log_error("Unexpected error in compiler corrector process", e)
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}",
                'errors': [f"Compilation system error: {str(e)}"],
                'corrected_files': [],
                'compilation_successful': False
            }
    
    def validate_input(self, input_data: Dict[str, Any]) -> List[str]:
        """
        Validate input data for the compiler corrector agent.
        
        Args:
            input_data: Input data to validate
        
        Returns:
            List of validation errors
        """
        errors = super().validate_input(input_data)
        
        required_fields = ['project_dir', 'generated_files', 'scenarios']     
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
        
        # Validate generated files
        if 'generated_files' in input_data:
            files = input_data['generated_files']
            if not isinstance(files, list):
                errors.append("Generated files must be a list")
            else:
                for file_path in files:
                    if not Path(file_path).exists():
                        errors.append(f"Generated file not found: {file_path}")
        
        return errors
    
    async def _compile_project(self, project_dir: Path) -> Dict[str, Any]:
        """
        Compile the Maven project and analyze results.
        
        Args:
            project_dir: Path to the Maven project
        
        Returns:
            Compilation result dictionary
        """
        try:
            self.logger.info(f"Compiling Maven project: {project_dir}")
            
            # Run Maven compilation
            maven_result = await self.maven_runner.compile_project(project_dir)
            
            result = {
                'success': maven_result.success,
                'exit_code': maven_result.exit_code,
                'output': maven_result.stdout + "\n" + maven_result.stderr,
                'execution_time': maven_result.execution_time,
                'errors': []
            }
            
            if not maven_result.success:
                # Parse compilation errors
                compilation_errors = self.maven_runner.parse_compilation_errors(maven_result)
                result['errors'] = compilation_errors
                
                self.logger.warning(
                    f"Compilation failed with {len(compilation_errors)} errors "
                    f"(exit code: {maven_result.exit_code})"
                )
            else:
                self.logger.info(f"Compilation successful in {maven_result.execution_time:.2f}s")
            
            return result
            
        except Exception as e:
            self.log_error("Failed to compile project", e)
            return {
                'success': False,
                'exit_code': -1,
                'output': f"Compilation failed: {str(e)}",
                'execution_time': 0.0,
                'errors': []
            }
    
    async def _fix_compilation_errors(
        self,
        project_dir: Path,
        generated_files: List[Path],
        errors: List[CompilationError],
        scenarios: str,
        raw_compiler_output: str = ""
    ) -> Dict[str, Any]:
        """
        Fix compilation errors iteratively.

        Args:
            project_dir: Project directory
            generated_files: List of generated files
            errors: List of compilation errors parsed from Maven output
            scenarios: Test scenarios string
            raw_compiler_output: Full raw Maven output, used as fallback context
                when the structured parser could not extract any errors but the
                build still failed (e.g. due to a format the regex did not match).

        Returns:
            Correction result dictionary
        """
        corrected_files = []
        attempts = 0
        current_errors = errors.copy()
        current_raw_output = raw_compiler_output

        # When the structured parser returns no errors but the build failed,
        # synthesise a single "unparsed" error entry per generated file so the
        # while-loop below can still execute and forward the raw output to the
        # LLM for correction.
        if not current_errors and current_raw_output:
            self.logger.warning(
                "No structured errors available — synthesising raw-output entries "
                f"for {len(generated_files)} file(s) so LLM correction can proceed."
            )
            for gf in generated_files:
                current_errors.append(CompilationError(
                    file_path=str(gf),
                    line_number=0,
                    column_number=0,
                    error_type="unparsed",
                    message=current_raw_output[:4000],   # truncate to avoid token bloat
                    full_error=current_raw_output[:4000]
                ))

        while current_errors and attempts < self.max_correction_attempts:
            attempts += 1
            self.logger.info(f"Correction attempt {attempts}/{self.max_correction_attempts}")

            # Group errors by file
            errors_by_file = self._group_errors_by_file(current_errors)

            files_corrected_this_round = []

            for file_path, file_errors in errors_by_file.items():
                self.logger.info(f"Fixing {len(file_errors)} errors in {file_path}")

                # Attempt to fix errors in this file
                correction_successful = await self._fix_file_errors(
                    Path(file_path), file_errors, scenarios
                )

                if correction_successful:
                    files_corrected_this_round.append(file_path)
                    if file_path not in corrected_files:
                        corrected_files.append(file_path)

            # Re-compile to check if errors are fixed
            compilation_result = await self._compile_project(project_dir)
            current_errors = compilation_result.get('errors', [])
            current_raw_output = compilation_result.get('output', '')

            # If structured errors are still empty but build is still failing,
            # re-synthesise raw-output entries for the next iteration.
            if not compilation_result['success'] and not current_errors and current_raw_output:
                self.logger.warning(
                    f"After attempt {attempts}: build still failing but parser returned 0 errors. "
                    "Re-synthesising raw-output entries for next LLM attempt."
                )
                for gf in generated_files:
                    current_errors.append(CompilationError(
                        file_path=str(gf),
                        line_number=0,
                        column_number=0,
                        error_type="unparsed",
                        message=current_raw_output[:4000],
                        full_error=current_raw_output[:4000]
                    ))

            if compilation_result['success']:
                self.logger.info(f"All compilation errors fixed after {attempts} attempts")
                break
            else:
                self.logger.info(
                    f"After attempt {attempts}: {len(current_errors)} errors remaining"
                )

        # Prepare result message
        if not current_errors:
            message = f"Successfully fixed all compilation errors in {attempts} attempts"
        elif attempts >= self.max_correction_attempts:
            message = f"Reached maximum attempts ({self.max_correction_attempts}). {len(current_errors)} errors remain"
        else:
            message = f"Fixed some errors in {attempts} attempts. {len(current_errors)} errors remain"

        return {
            'message': message,
            'corrected_files': corrected_files,
            'attempts': attempts,
            'remaining_errors': len(current_errors)
        }
    
    def _group_errors_by_file(self, errors: List[CompilationError]) -> Dict[str, List[CompilationError]]:
        """Group compilation errors by file path."""
        errors_by_file = {}
        
        for error in errors:
            file_path = error.file_path
            if file_path not in errors_by_file:
                errors_by_file[file_path] = []
            errors_by_file[file_path].append(error)
        
        return errors_by_file
    
    async def _fix_file_errors(
        self,
        file_path: Path,
        errors: List[CompilationError],
        scenarios: str
    ) -> bool:
        """
        Fix compilation errors in a single file.
        
        Args:
            file_path: Path to the file with errors
            errors: List of errors in this file
        
        Returns:
            True if correction was attempted, False otherwise
        """
        try:
            if not file_path.exists():
                self.logger.error(f"File not found: {file_path}")
                return False
            
            # Read current file content
            original_content = file_path.read_text(encoding='utf-8')
            
            # Attempt different correction strategies
            corrected_content = None
            
            # Strategy 1: LLM-based correction (if available)
            if self.openrouter_client:
                corrected_content = await self._fix_with_llm(
                    original_content, errors, file_path, scenarios
                )
            
            # Strategy 2: Rule-based correction (fallback)
            if not corrected_content:
                corrected_content = await self._fix_with_rules(
                    original_content, errors, file_path
                )
            
            # Apply corrections if any were made
            if corrected_content and corrected_content != original_content:
                # Write corrected content (versioning is handled by TestVersionManager)
                file_path.write_text(corrected_content, encoding='utf-8')
                
                self.logger.info(f"Applied corrections to {file_path}")
                return True
            else:
                self.logger.warning(f"No corrections could be applied to {file_path}")
                return False
                
        except Exception as e:
            self.log_error(f"Failed to fix errors in {file_path}", e)
            return False
    
    async def _fix_with_llm(
        self,
        content: str,
        errors: List[CompilationError],
        file_path: Path,
        scenarios: str
    ) -> Optional[str]:
        """
        Fix compilation errors using LLM.
        
        Args:
            content: Original file content
            errors: List of compilation errors
            file_path: Path to the file
        
        Returns:
            Corrected content or None if correction failed
        """
        try:
            # Format errors for LLM
            error_descriptions = []
            for error in errors:
                error_descriptions.append(
                    f"Line {error.line_number}: {error.message}"
                )
            
            errors_text = "\n".join(error_descriptions)
            
            # Generate corrected code using LLM
            corrected_content = await self.openrouter_client.fix_compilation_errors(
                code=content,
                errors=errors_text,
                scenarios=scenarios,
                model=self.get_model_name(),
                max_tokens=self.get_max_tokens(),
                temperature=self.get_temperature()
            )
            
            #print(f"#### compiler fix_with_llm corrected_content:{corrected_content}")

            # Sanitize LLM output to remove commentary and extract only code
            if corrected_content:
                self.logger.info(f"Sanitizing LLM correction output for {file_path}")
                corrected_content = self.code_sanitizer.sanitize_java_code(corrected_content)
            
            # Validate the corrected content
            if corrected_content and self._is_valid_java_code(corrected_content):
                # Enforce status-code immutability: revert any method where the
                # LLM changed a .statusCode(N) value and add @Ignore with reason.
                corrected_content, sc_violations = (
                    self.code_sanitizer.enforce_status_code_immutability(
                        content, corrected_content
                    )
                )
                if sc_violations:
                    self.logger.warning(
                        f"[status-code guard] {len(sc_violations)} violation(s) reverted "
                        f"in {file_path}: {sc_violations}"
                    )
                self.logger.info(f"LLM correction successful for {file_path}")
                return corrected_content
            else:
                self.logger.warning(f"LLM correction failed validation for {file_path}")
                return None
                
        except Exception as e:
            self.log_error(f"LLM correction failed for {file_path}", e)
            return None
    
    async def _fix_with_rules(
        self,
        content: str,
        errors: List[CompilationError],
        file_path: Path
    ) -> Optional[str]:
        """
        Fix compilation errors using rule-based approach.
        
        Args:
            content: Original file content
            errors: List of compilation errors
            file_path: Path to the file
        
        Returns:
            Corrected content or None if no corrections applied
        """
        corrected_content = content
        corrections_applied = False
        
        for error in errors:
            # Apply specific fixes based on error type
            if error.error_type == "package_not_found":
                fix = self._fix_missing_package(corrected_content, error)
                if fix:
                    corrected_content = fix
                    corrections_applied = True
            
            elif error.error_type == "symbol_not_found":
                fix = self._fix_missing_symbol(corrected_content, error)
                if fix:
                    corrected_content = fix
                    corrections_applied = True
            
            elif error.error_type == "method_signature":
                fix = self._fix_method_signature(corrected_content, error)
                if fix:
                    corrected_content = fix
                    corrections_applied = True
        
        return corrected_content if corrections_applied else None
    
    def _fix_missing_package(self, content: str, error: CompilationError) -> Optional[str]:
        """Fix missing package imports."""
        # Common package mappings
        package_fixes = {
            'RestAssured': 'import static io.restassured.RestAssured.*;',
            'ContentType': 'import io.restassured.http.ContentType;',
            'Response': 'import io.restassured.response.Response;',
            'RequestSpecification': 'import io.restassured.specification.RequestSpecification;',
            'Matchers': 'import static org.hamcrest.Matchers.*;',
            'Assert': 'import static org.junit.Assert.*;'
        }
        
        for symbol, import_statement in package_fixes.items():
            if symbol in error.message and import_statement not in content:
                # Find the package declaration
                package_match = re.search(r'^package\s+[^;]+;', content, re.MULTILINE)
                if package_match:
                    # Insert import after package declaration
                    insert_pos = package_match.end()
                    return content[:insert_pos] + '\n\n' + import_statement + content[insert_pos:]
        
        return None
    
    def _fix_missing_symbol(self, content: str, error: CompilationError) -> Optional[str]:
        """Fix missing symbol errors."""
        # Common symbol fixes
        if "given" in error.message and "import static io.restassured.RestAssured.*;" not in content:
            return self._add_import(content, "import static io.restassured.RestAssured.*;")
        
        if "lessThan" in error.message and "import static org.hamcrest.Matchers.*;" not in content:
            return self._add_import(content, "import static org.hamcrest.Matchers.*;")
        
        if "assertEquals" in error.message and "import static org.junit.Assert.*;" not in content:
            return self._add_import(content, "import static org.junit.Assert.*;")
        
        return None
    
    def _fix_method_signature(self, content: str, error: CompilationError) -> Optional[str]:
        """Fix method signature errors."""
        # This is a complex fix that would require more sophisticated analysis
        # For now, just log the error
        self.logger.info(f"Method signature error detected but not automatically fixable: {error.message}")
        return None
    
    def _add_import(self, content: str, import_statement: str) -> str:
        """Add an import statement to Java code."""
        if import_statement in content:
            return content
        
        # Find the package declaration
        package_match = re.search(r'^package\s+[^;]+;', content, re.MULTILINE)
        if package_match:
            # Insert import after package declaration
            insert_pos = package_match.end()
            return content[:insert_pos] + '\n\n' + import_statement + content[insert_pos:]
        else:
            # No package declaration, add at the beginning
            return import_statement + '\n\n' + content
    
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
    
    def get_correction_statistics(
        self,
        corrected_files: List[str],
        attempts: int,
        remaining_errors: int
    ) -> Dict[str, Any]:
        """
        Get statistics about the correction process.
        
        Args:
            corrected_files: List of corrected files
            attempts: Number of correction attempts
            remaining_errors: Number of remaining errors
        
        Returns:
            Correction statistics
        """
        return {
            'files_corrected': len(corrected_files),
            'correction_attempts': attempts,
            'remaining_errors': remaining_errors,
            'success_rate': (len(corrected_files) / max(1, attempts)) * 100,
            'corrected_files': corrected_files
        }

