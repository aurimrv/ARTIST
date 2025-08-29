"""
Generator Agent for creating JUnit 4 test code with Rest Assured.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent
from ..config.models import AgentConfig, SystemConfig, TestScenario, ProjectContext
from ..templates import JUnitTemplate, MavenProjectTemplate, RestAssuredTemplate
from ..utils import OpenRouterClient, CodeSanitizer


class GeneratorAgent(BaseAgent):
    """
    Generator Agent responsible for generating test cases based on scenarios.
    
    This agent creates JUnit 4 test code using Rest Assured framework,
    generates complete Maven projects, and ensures compatibility with Java 8.
    Each test method validates only a single scenario, with success and failure
    cases placed in separate methods.
    """
    
    def __init__(self, config: AgentConfig, system_config: SystemConfig):
        """Initialize the Generator Agent."""
        super().__init__(config, system_config)
        self.junit_template = JUnitTemplate()
        self.maven_template = MavenProjectTemplate()
        self.rest_assured_template = RestAssuredTemplate()
        self.code_sanitizer = CodeSanitizer()
        self.openrouter_client = None
    
    async def _initialize_impl(self):
        """Initialize the generator agent components."""
        self.logger.info("Initializing Generator Agent")
        
        # Initialize OpenRouter client for LLM-assisted generation
        if self.system_config.openrouter.api_key:
            self.openrouter_client = OpenRouterClient(self.system_config.openrouter)
            self.logger.info("OpenRouter client initialized for LLM-assisted generation")
        else:
            self.logger.warning("No OpenRouter API key provided - using template-based generation only")
        
        self.logger.info("Generator Agent initialization complete")
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main processing method for the Generator Agent.
        
        Args:
            input_data: Dictionary containing:
                - context: ProjectContext object
                - scenarios: List of TestScenario objects
        
        Returns:
            Dictionary with generation results
        """
        try:
            # Validate input
            validation_errors = self.validate_input(input_data)
            if validation_errors:
                return {
                    'success': False,
                    'error': f"Input validation failed: {', '.join(validation_errors)}",
                    'generated_files': []
                }
            
            context = input_data['context']
            scenarios = input_data['scenarios']
            
            self.log_progress(f"Starting test code generation for {len(scenarios)} scenarios")
            
            # Step 1: Create Maven project structure
            self.log_progress("Creating Maven project structure", 1, 4)
            project_dir = await self._create_maven_project(context)
            
            if not project_dir:
                return {
                    'success': False,
                    'error': "Failed to create Maven project structure",
                    'generated_files': []
                }
            
            # Step 2: Generate test classes
            self.log_progress("Generating test classes", 2, 4)
            generated_files = await self._generate_test_classes(context, scenarios)

            # Step 3: Enhance with LLM if available
            if self.openrouter_client and generated_files:
                self.log_progress("Enhancing tests with LLM", 3, 4)
                enhanced_files = await self._enhance_tests_with_llm(context, generated_files)
                if enhanced_files:
                    generated_files = enhanced_files
            
            # Step 4: Validate generated code
            self.log_progress("Validating generated code", 4, 4)
            validation_result = await self._validate_generated_code(project_dir, generated_files)
            
            self.logger.info(f"Generated {len(generated_files)} test files")
            
            return {
                'success': True,
                'message': f"Successfully generated {len(generated_files)} test files",
                'generated_files': generated_files,
                'project_dir': str(project_dir),
                'validation_result': validation_result
            }
            
        except Exception as e:
            self.log_error("Unexpected error in generator process", e)
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}",
                'generated_files': []
            }
    
    def validate_input(self, input_data: Dict[str, Any]) -> List[str]:
        """
        Validate input data for the generator agent.
        
        Args:
            input_data: Input data to validate
        
        Returns:
            List of validation errors
        """
        errors = super().validate_input(input_data)
        
        required_fields = ['context', 'scenarios']
        
        for field in required_fields:
            if field not in input_data:
                errors.append(f"Missing required field: {field}")
            elif not input_data[field]:
                errors.append(f"Empty value for required field: {field}")
        
        # Validate context type
        if 'context' in input_data and not isinstance(input_data['context'], ProjectContext):
            errors.append("Context must be a ProjectContext instance")
        
        # Validate scenarios type
        if 'scenarios' in input_data:
            scenarios = input_data['scenarios']
            if not isinstance(scenarios, list):
                errors.append("Scenarios must be a list")
            elif scenarios and not all(isinstance(s, TestScenario) for s in scenarios):
                errors.append("All scenarios must be TestScenario instances")
        
        return errors
    
    async def _create_maven_project(self, context: ProjectContext) -> Optional[Path]:
        """
        Create the Maven project structure.
        
        Args:
            context: Project context
        
        Returns:
            Path to the created project or None if creation fails
        """
        try:
            self.logger.info(f"Creating Maven project at: {context.maven_project_dir}")
            
            # API info for project generation
            api_info = {
                'title': 'API',
                'version': '1.0.0',
                'description': 'Generated API tests'
            }
            
            # Create the Maven project
            project_dir = self.maven_template.create_maven_project(context, api_info)
            
            # Validate project structure
            if self.maven_template.validate_project_structure(project_dir):
                self.logger.info("Maven project created and validated successfully")
                return project_dir
            else:
                self.logger.error("Maven project validation failed")
                return None
                
        except Exception as e:
            self.log_error("Failed to create Maven project", e)
            return None
    
    async def _generate_test_classes(
        self, 
        context: ProjectContext, 
        scenarios: List[TestScenario]
    ) -> List[Path]:
        """
        Generate test classes from scenarios.
        
        Args:
            context: Project context
            scenarios: List of test scenarios
        
        Returns:
            List of generated file paths
        """
        generated_files = []
        
        try:
            # Group scenarios by test class (for now, put all in main test class)
            test_classes = self._group_scenarios_by_class(scenarios, context)
            
            for class_name, class_scenarios in test_classes.items():
                self.logger.info(f"Generating test class: {class_name}")
                
                # Generate test class content
                test_content = await self._generate_single_test_class(
                    context, class_name, class_scenarios
                )
                
                if test_content:
                    # Write test class to file
                    test_file_path = self.maven_template.get_test_class_path(
                        context.maven_project_dir, context.package_name, class_name
                    )
                    
                    self.maven_template.add_test_class(
                        context.maven_project_dir, 
                        context.package_name, 
                        class_name, 
                        test_content
                    )
                    
                    generated_files.append(test_file_path)
                    self.logger.info(f"Generated test class: {test_file_path}")
            
            return generated_files
            
        except Exception as e:
            self.log_error("Failed to generate test classes", e)
            return []
    
    def _group_scenarios_by_class(
        self, 
        scenarios: List[TestScenario], 
        context: ProjectContext
    ) -> Dict[str, List[TestScenario]]:
        """
        Group scenarios by test class.
        
        Args:
            scenarios: List of test scenarios
            context: Project context
        
        Returns:
            Dictionary mapping class names to scenarios
        """
        # For now, put all scenarios in the main test class
        # In the future, could group by endpoint or functionality
        return {
            context.main_test_class_name: scenarios
        }
    
    async def _generate_single_test_class(
        self,
        context: ProjectContext,
        class_name: str,
        scenarios: List[TestScenario]
    ) -> Optional[str]:
        """
        Generate a single test class.
        
        Args:
            context: Project context
            class_name: Name of the test class
            scenarios: Scenarios for this class
        
        Returns:
            Generated test class content or None if generation fails
        """
        try:
            # API info for template
            api_info = {
                'title': 'API',
                'version': '1.0.0'
            }
            
            # Generate test class using template
            test_content = self.junit_template.generate_test_class(
                context, scenarios, api_info
            )
            
            return test_content
            
        except Exception as e:
            self.log_error(f"Failed to generate test class {class_name}", e)
            return None
    
    async def _enhance_tests_with_llm(
        self,
        context: ProjectContext,
        generated_files: List[Path]
    ) -> Optional[List[Path]]:
        """
        Enhance generated tests using LLM.
        
        Args:
            context: Project context
            generated_files: List of generated test files
        
        Returns:
            List of enhanced file paths or None if enhancement fails
        """
        try:
            enhanced_files = []
            
            for file_path in generated_files:
                self.logger.info(f"Enhancing test file with LLM: {file_path}")
                
                # Read current content
                current_content = file_path.read_text(encoding='utf-8')
                
                # Prepare context for LLM
                project_context_str = self._format_project_context_for_llm(context)

                self.logger.info(f"Generator MAX_TOKENS: {self.get_max_tokens()}")

                # Generate enhanced code using LLM
                enhanced_content = await self.openrouter_client.generate_test_code(
                    scenarios=current_content,  # Use current content as scenarios
                    project_context=project_context_str,
                    model=self.get_model_name(),
                    max_tokens=self.get_max_tokens(),
                    temperature=self.get_temperature()
                )


                # Sanitize LLM output to remove commentary and extract only code
                if enhanced_content:
                    self.logger.info(f"Sanitizing LLM output for {file_path}")
                    enhanced_content = self.code_sanitizer.sanitize_java_code(enhanced_content)
                
                # Validate and write enhanced content
                if enhanced_content and self._is_valid_java_code(enhanced_content):
                    file_path.write_text(enhanced_content, encoding='utf-8')
                    enhanced_files.append(file_path)
                    self.logger.info(f"Enhanced test file: {file_path}")
                else:
                    self.logger.warning(f"LLM enhancement failed for {file_path}, keeping original")
                    enhanced_files.append(file_path)

            return enhanced_files
            
        except Exception as e:
            self.log_error("Failed to enhance tests with LLM", e)
            return None
    
    def _format_project_context_for_llm(self, context: ProjectContext) -> str:
        """Format project context for LLM consumption."""
        return f"""Project Context:
- Package: {context.package_name}
- Main Test Class: {context.main_test_class_name}
- Base URL: {context.base_url}
- Output Directory: {context.output_dir}

Requirements:
- Use JUnit 4 annotations
- Use Rest Assured for HTTP requests
- Java 8 compatibility
- Separate methods for positive and negative tests
- Proper error handling and assertions"""
    
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
            'import ',
            'public class ',
            '@Test'
        ]
        
        return all(element in code for element in required_elements)
    
    async def _validate_generated_code(
        self,
        project_dir: Path,
        generated_files: List[Path]
    ) -> Dict[str, Any]:
        """
        Validate the generated code.
        
        Args:
            project_dir: Project directory
            generated_files: List of generated files
        
        Returns:
            Validation result dictionary
        """
        validation_result = {
            'valid_files': [],
            'invalid_files': [],
            'warnings': [],
            'total_files': len(generated_files)
        }
        
        for file_path in generated_files:
            try:
                if file_path.exists() and file_path.stat().st_size > 0:
                    # Read and validate content
                    content = file_path.read_text(encoding='utf-8')
                    
                    if self._is_valid_java_code(content):
                        validation_result['valid_files'].append(str(file_path))
                    else:
                        validation_result['invalid_files'].append(str(file_path))
                        validation_result['warnings'].append(f"Invalid Java code structure: {file_path}")
                else:
                    validation_result['invalid_files'].append(str(file_path))
                    validation_result['warnings'].append(f"Empty or missing file: {file_path}")
                    
            except Exception as e:
                validation_result['invalid_files'].append(str(file_path))
                validation_result['warnings'].append(f"Failed to validate {file_path}: {str(e)}")
        
        # Validate Maven project structure
        if not self.maven_template.validate_project_structure(project_dir):
            validation_result['warnings'].append("Maven project structure validation failed")
        
        return validation_result
    
    def get_generated_test_methods_count(self, scenarios: List[TestScenario]) -> int:
        """
        Calculate the number of test methods that will be generated.
        
        Args:
            scenarios: List of test scenarios
        
        Returns:
            Number of test methods
        """
        # Each scenario generates one test method
        return len(scenarios)
    
    def get_project_statistics(self, context: ProjectContext, scenarios: List[TestScenario]) -> Dict[str, Any]:
        """
        Get statistics about the generated project.
        
        Args:
            context: Project context
            scenarios: List of test scenarios
        
        Returns:
            Project statistics
        """
        positive_tests = sum(1 for s in scenarios if not s.is_negative_test)
        negative_tests = sum(1 for s in scenarios if s.is_negative_test)
        
        return {
            'package_name': context.package_name,
            'main_test_class': context.main_test_class_name,
            'base_url': context.base_url,
            'total_scenarios': len(scenarios),
            'positive_tests': positive_tests,
            'negative_tests': negative_tests,
            'test_methods_count': self.get_generated_test_methods_count(scenarios),
            'project_dir': str(context.maven_project_dir)
        }

