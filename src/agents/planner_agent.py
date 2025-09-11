"""
Planner Agent for analyzing APIs and creating test scenarios.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent
from ..config.models import AgentConfig, SystemConfig, TestScenario
from ..parsers import OpenAPIParser, JavaParser, MavenParser
from ..utils import OpenRouterClient
from .dependency_analyzer import DependencyAnalyzer


class PlannerAgent(BaseAgent):
    """
    Planner Agent responsible for interpreting API specifications and implementation code,
    and creating realistic integration testing scenarios.

    This agent analyzes both the API specification (OpenAPI/Swagger) and the actual
    Java implementation to create comprehensive test scenarios that cover various
    test cases including positive, negative, and edge cases.
    """

    def __init__(self, config: AgentConfig, system_config: SystemConfig):
        """Initialize the Planner Agent."""
        super().__init__(config, system_config)
        self.openapi_parser = OpenAPIParser()
        self.java_parser = JavaParser()
        self.maven_parser = MavenParser()
        self.openrouter_client = None
        self.dependency_analyzer = None

    async def _initialize_impl(self):
        """Initialize the planner agent components."""
        self.logger.info("Initializing Planner Agent")
        
        # Initialize OpenRouter client for LLM-assisted scenario generation
        if self.system_config.openrouter.api_key:
            self.openrouter_client = OpenRouterClient(self.system_config.openrouter)
            self.logger.info("OpenRouter client initialized")
            
            # Initialize dependency analyzer with LLM support
            self.dependency_analyzer = DependencyAnalyzer(self.openrouter_client)
        else:
            self.logger.warning("No OpenRouter API key provided - using rule-based scenario generation only")
            self.dependency_analyzer = DependencyAnalyzer()
        
        self.logger.info("Planner Agent initialization complete")

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main processing method for the Planner Agent.

        Args:
            input_data: Dictionary containing:
                - api_spec_path: Path to API specification file
                - api_src_path: Path to API source code
                - base_url: Base URL for the API

        Returns:
            Dictionary with planning results including test scenarios
        """
        try:
            # Validate input
            validation_errors = self.validate_input(input_data)
            if validation_errors:
                return {
                    'success': False,
                    'error': f"Input validation failed: {', '.join(validation_errors)}",
                    'scenarios': []
                }

            self.log_progress("Starting API analysis and test scenario planning")

            # Step 1: Parse API specification
            self.log_progress("Parsing API specification", 1, 4)
            api_spec = await self._parse_api_specification(input_data['api_spec_path'])

            if not api_spec:
                return {
                    'success': False,
                    'error': "Failed to parse API specification",
                    'scenarios': []
                }

            # Step 2: Analyze implementation (optional)
            implementation_analysis = None
            api_src_path = input_data.get('api_src_path')

            if api_src_path:
                self.log_progress("Analyzing API implementation", 2, 4)
                implementation_analysis = await self._analyze_implementation(api_src_path)
            else:
                self.logger.info("No API source code provided - generating tests based only on specification")

            # Step 3: Analyze API dependencies and generate workflows
            self.log_progress("Analyzing API dependencies and workflows", 3, 5)
            dependency_analysis = await self.dependency_analyzer.analyze_api_dependencies(
                api_spec, implementation_analysis
            )
            
            # Extract base URL from input data
            base_url = input_data.get('base_url', 'http://localhost:8080')
            
            # Step 4: Generate test scenarios with dependency awareness
            self.log_progress("Generating dependency-aware test scenarios", 4, 5)
            scenarios = await self._generate_scenarios_with_dependencies(
                api_spec, implementation_analysis, dependency_analysis, base_url
            )
            
            # Step 5: Validate and enrich scenarios
            self.log_progress("Validating and enriching scenarios", 5, 5)
            validated_scenarios = await self._validate_scenarios(scenarios, api_spec)

            self.logger.info(f"Generated {len(validated_scenarios)} test scenarios")

            return {
                'success': True,
                'message': f"Successfully generated {len(validated_scenarios)} test scenarios",
                'scenarios': validated_scenarios,
                'api_spec_summary': self._create_api_summary(api_spec),
                'implementation_summary': implementation_analysis
            }

        except Exception as e:
            self.log_error("Unexpected error in planner process", e)
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}",
                'scenarios': []
            }

    def validate_input(self, input_data: Dict[str, Any]) -> List[str]:
        """
        Validate input data for the planner agent.

        Args:
            input_data: Input data to validate

        Returns:
            List of validation errors
        """
        errors = super().validate_input(input_data)

        # Only api_spec_path is required, api_src_path is optional
        required_fields = ['api_spec_path']

        for field in required_fields:
            if field not in input_data:
                errors.append(f"Missing required field: {field}")
            elif not input_data[field]:
                errors.append(f"Empty required field: {field}")

        # Validate paths exist if provided
        if 'api_spec_path' in input_data and input_data['api_spec_path']:
            spec_path = Path(input_data['api_spec_path'])
            if not spec_path.exists():
                errors.append(f"API specification file not found: {spec_path}")

        if 'api_src_path' in input_data and input_data['api_src_path']:
            src_path = Path(input_data['api_src_path'])
            if not src_path.exists():
                errors.append(f"API source directory not found: {src_path}")

        return errors

    async def _parse_api_specification(self, spec_path: str) -> Optional[Any]:
        """
        Parse the API specification file.

        Args:
            spec_path: Path to the API specification file

        Returns:
            Parsed API specification or None if parsing fails
        """
        try:
            spec_path = Path(spec_path)
            self.logger.info(f"Parsing API specification: {spec_path}")

            api_spec = self.openapi_parser.parse_file(spec_path)

            self.logger.info(
                f"Successfully parsed API specification: {api_spec.title} v{api_spec.version} "
                f"with {len(api_spec.endpoints)} endpoints"
            )

            return api_spec

        except Exception as e:
            self.log_error(f"Failed to parse API specification {spec_path}", e)
            return None

    async def _analyze_implementation(self, src_path: str) -> Dict[str, Any]:
        """
        Analyze the API implementation source code.

        Args:
            src_path: Path to the API source code

        Returns:
            Implementation analysis results
        """
        try:
            src_path = Path(src_path)
            self.logger.info(f"Analyzing API implementation: {src_path}")

            analysis = {
                'maven_project': None,
                'java_classes': [],
                'rest_endpoints': [],
                'framework_info': {},
                'summary': ""
            }

            # Parse Maven project
            maven_project = self.maven_parser.parse_project(src_path)
            if maven_project:
                analysis['maven_project'] = {
                    'group_id': maven_project.group_id,
                    'artifact_id': maven_project.artifact_id,
                    'version': maven_project.version,
                    'packaging': maven_project.packaging,
                    'is_web_project': self.maven_parser.is_web_project(maven_project),
                    'is_spring_project': self.maven_parser.is_spring_project(maven_project),
                    'is_jaxrs_project': self.maven_parser.is_jaxrs_project(maven_project)
                }

                self.logger.info(f"Analyzed Maven project: {maven_project.artifact_id}")

            # Parse Java source files
            java_classes = self.java_parser.parse_project(src_path)
            analysis['java_classes'] = [
                {
                    'name': cls.name,
                    'package': cls.package,
                    'methods': len(cls.methods),
                    'is_rest_controller': self._is_rest_controller(cls)
                }
                for cls in java_classes
            ]

            # Extract REST endpoints
            rest_endpoints = self.java_parser.extract_rest_endpoints(java_classes)
            analysis['rest_endpoints'] = [
                {
                    'path': endpoint.path,
                    'method': endpoint.method,
                    'java_method': endpoint.java_method,
                    'java_class': endpoint.java_class,
                    'parameters': endpoint.parameters,
                    'return_type': endpoint.return_type
                }
                for endpoint in rest_endpoints
            ]

            self.logger.info(
                f"Found {len(java_classes)} Java classes and {len(rest_endpoints)} REST endpoints"
            )

            # Create summary
            analysis['summary'] = self._create_implementation_summary(analysis)

            return analysis

        except Exception as e:
            self.log_error(f"Failed to analyze implementation {src_path}", e)
            return {
                'maven_project': None,
                'java_classes': [],
                'rest_endpoints': [],
                'framework_info': {},
                'summary': f"Analysis failed: {str(e)}"
            }

    async def _generate_test_scenarios(
        self,
        api_spec: Any,
        implementation_analysis: Optional[Dict[str, Any]],
        base_url: str
    ) -> List[TestScenario]:
        """
        Generate comprehensive test scenarios based on API specification.

        Args:
            api_spec: Parsed API specification
            implementation_analysis: Analysis of the implementation (optional)
            base_url: Base URL for the API

        Returns:
            List of test scenarios
        """
        try:
            # Always prioritize rule-based generation from OpenAPI spec
            scenarios = await self._generate_scenarios_from_openapi(api_spec, base_url)

            # If we have implementation analysis, try to add scenarios from source code
            if implementation_analysis and implementation_analysis.get('rest_endpoints'):
                source_scenarios = await self._generate_scenarios_from_source_code(
                    implementation_analysis, base_url
                )
                scenarios.extend(source_scenarios)
                self.logger.info(f"Added {len(source_scenarios)} scenarios from source code analysis")

            if len(scenarios) < len(api_spec.endpoints):
                self.logger.warning("Rule-based generation incomplete, trying LLM enhancement")

                # Use LLM to enhance scenarios if available
                if self.openrouter_client:
                    enhanced_scenarios = await self._generate_scenarios_with_llm(
                        api_spec, implementation_analysis, base_url
                    )
                    # Merge scenarios, prioritizing rule-based ones
                    scenarios = self._merge_scenarios(scenarios, enhanced_scenarios)

            self.logger.info(f"Generated {len(scenarios)} test scenarios")
            return scenarios

        except Exception as e:
            self.log_error("Failed to generate test scenarios", e)
            # Fallback to basic scenarios
            return await self._generate_basic_scenarios(api_spec, base_url)

    async def _generate_scenarios_with_llm(
        self,
        api_spec: Any,
        implementation_analysis: Dict[str, Any],
        base_url: str
    ) -> List[TestScenario]:
        """Generate test scenarios using LLM."""
        try:
            # Prepare API specification summary
            api_spec_text = self._format_api_spec_for_llm(api_spec)

            # Prepare implementation analysis
            impl_text = json.dumps(implementation_analysis, indent=2)

            # Generate scenarios using LLM
            response = await self.openrouter_client.generate_test_scenarios(
                api_spec=api_spec_text,
                implementation_info=impl_text,
                model=self.get_model_name(),
                max_tokens=self.get_max_tokens(),
                temperature=self.get_temperature()
            )

            # Parse LLM response
            scenarios = self._parse_llm_scenarios_response(response, base_url)

            return scenarios

        except Exception as e:
            self.log_error("LLM scenario generation failed", e)
            return []

    async def _generate_scenarios_rule_based(
        self,
        api_spec: Any,
        implementation_analysis: Dict[str, Any],
        base_url: str
    ) -> List[TestScenario]:
        """Generate test scenarios using rule-based approach."""
        scenarios = []

        for endpoint in api_spec.endpoints:
            # Generate positive test scenario
            scenarios.append(TestScenario(
                name=f"test_{endpoint.method.lower()}_{self._sanitize_path(endpoint.path)}",
                description=f"Test {endpoint.method} {endpoint.path} - positive case",
                endpoint=endpoint.path,
                method=endpoint.method,
                parameters=await self._extract_parameters(endpoint),
                expected_status=200,
                is_negative_test=False
            ))

            # Generate negative test scenarios
            if self.system_config.test_generation.generate_negative_tests:
                # Invalid parameter test
                scenarios.append(TestScenario(
                    name=f"test_{endpoint.method.lower()}_{self._sanitize_path(endpoint.path)}_invalid_params",
                    description=f"Test {endpoint.method} {endpoint.path} - invalid parameters",
                    endpoint=endpoint.path,
                    method=endpoint.method,
                    parameters={'invalid': 'parameter'},
                    expected_status=400,
                    is_negative_test=True
                ))

        return scenarios

    async def _generate_basic_scenarios(self, api_spec: Any, base_url: str) -> List[TestScenario]:
        """Generate basic scenarios as fallback."""
        scenarios = []

        for endpoint in api_spec.endpoints[:5]:  # Limit to first 5 endpoints
            scenarios.append(TestScenario(
                name=f"test_{endpoint.method.lower()}_{self._sanitize_path(endpoint.path)}",
                description=f"Basic test for {endpoint.method} {endpoint.path}",
                endpoint=endpoint.path,
                method=endpoint.method,
                parameters={},
                expected_status=200,
                is_negative_test=False
            ))

        return scenarios

    async def _generate_scenarios_from_openapi(
        self,
        api_spec: Any,
        base_url: str
    ) -> List[TestScenario]:
        """
        Generate test scenarios directly from OpenAPI specification.

        Args:
            api_spec: Parsed API specification
            base_url: Base URL for the API

        Returns:
            List of test scenarios
        """
        scenarios = []

        for endpoint in api_spec.endpoints:
            # Generate positive test scenario
            scenarios.append(TestScenario(
                name=f"test_{endpoint.method.lower()}_{self._sanitize_path(endpoint.path)}_success",
                description=f"Test {endpoint.method} {endpoint.path} - success case",
                endpoint=endpoint.path,
                method=endpoint.method,
                parameters=await self._extract_parameters(endpoint),
                expected_status=200,
                is_negative_test=False
            ))

            # Generate negative test scenarios based on endpoint characteristics
            if self.system_config.test_generation.generate_negative_tests:
                negative_scenarios = await self._generate_negative_scenarios_for_endpoint(endpoint)
                scenarios.extend(negative_scenarios)

        return scenarios

    async def _generate_scenarios_from_source_code(
        self,
        implementation_analysis: Dict[str, Any],
        base_url: str
    ) -> List[TestScenario]:
        """
        Generate test scenarios from source code analysis (additional endpoints not in spec).

        Args:
            implementation_analysis: Analysis of the implementation
            base_url: Base URL for the API

        Returns:
            List of test scenarios for additional endpoints
        """
        scenarios = []

        rest_endpoints = implementation_analysis.get('rest_endpoints', [])

        for endpoint in rest_endpoints:
            # Create a basic test scenario for each endpoint found in source code
            # but not covered by the OpenAPI specification
            endpoint_method = endpoint.get('method', 'GET')
            endpoint_path = endpoint.get('path', '/')

            scenario_name = f"test_{endpoint_method.lower()}_{self._sanitize_path(endpoint_path)}_source_code"

            scenarios.append(TestScenario(
                name=scenario_name,
                description=f"Test {endpoint_method} {endpoint_path} (found in source code)",
                endpoint=endpoint_path,
                method=endpoint_method,
                parameters={},
                expected_status=200,
                is_negative_test=False
            ))

        self.logger.info(f"Generated {len(scenarios)} scenarios from source code analysis")
        return scenarios

    def _merge_scenarios(self, primary_scenarios: List[TestScenario], secondary_scenarios: List[TestScenario]) -> List[TestScenario]:
        """
        Merge two lists of scenarios, avoiding duplicates.

        Args:
            primary_scenarios: Primary scenarios (higher priority)
            secondary_scenarios: Secondary scenarios

        Returns:
            Merged list of scenarios
        """
        merged = primary_scenarios.copy()
        primary_names = {scenario.name for scenario in primary_scenarios}

        for scenario in secondary_scenarios:
            if scenario.name not in primary_names:
                merged.append(scenario)

        return merged

    async def _generate_negative_scenarios_for_endpoint(self, endpoint) -> List[TestScenario]:
        """
        Generate negative test scenarios based on endpoint characteristics and response codes.

        Args:
            endpoint: API endpoint specification

        Returns:
            List of negative test scenarios
        """
        scenarios = []

        # Only generate parameter-based tests if endpoint has parameters
        if endpoint.parameters and len(endpoint.parameters) > 0:
            # Analyze response codes to determine what negative tests to generate
            response_codes = endpoint.responses.keys() if endpoint.responses else []

            # Generate 400 Bad Request tests if defined in responses
            if '400' in response_codes:
                bad_request_scenarios = await self._generate_bad_request_scenarios(endpoint)
                scenarios.extend(bad_request_scenarios)

            # Generate 404 Not Found tests if defined in responses
            if '404' in response_codes:
                not_found_scenarios = await self._generate_not_found_scenarios(endpoint)
                scenarios.extend(not_found_scenarios)

        # Generate other error scenarios based on response codes
        for status_code in endpoint.responses.keys() if endpoint.responses else []:
            if status_code.startswith('4') and status_code not in ['400', '404']:
                # Generate scenarios for other 4xx errors
                scenarios.extend(await self._generate_custom_error_scenarios(endpoint, status_code))
            elif status_code.startswith('5'):
                # Generate scenarios for 5xx errors (usually server errors, harder to test)
                pass  # Skip server errors for now

        return scenarios

    async def _generate_bad_request_scenarios(self, endpoint) -> List[TestScenario]:
        """Generate scenarios that should result in 400 Bad Request."""
        scenarios = []

        for param in endpoint.parameters:
            param_name = param.get('name', 'unknown')
            param_description = param.get('description', '').lower()
            param_schema = param.get('schema', {})

            # Generate format-invalid parameters based on description
            invalid_params = await self._generate_format_invalid_parameters(endpoint)

            scenarios.append(TestScenario(
                name=f"test_{endpoint.method.lower()}_{self._sanitize_path(endpoint.path)}_bad_request_{param_name}",
                description=f"Test {endpoint.method} {endpoint.path} - bad request with invalid {param_name}",
                endpoint=endpoint.path,
                method=endpoint.method,
                parameters=invalid_params,
                expected_status=400,
                is_negative_test=True
            ))

            # Only generate one 400 test per endpoint to avoid duplication
            break

        return scenarios

    async def _generate_not_found_scenarios(self, endpoint) -> List[TestScenario]:
        """Generate scenarios that should result in 404 Not Found."""
        scenarios = []

        # Only generate 404 tests for endpoints with path parameters
        if '{' in endpoint.path:
            not_found_params = await self._generate_not_found_parameters_smart(endpoint)

            scenarios.append(TestScenario(
                name=f"test_{endpoint.method.lower()}_{self._sanitize_path(endpoint.path)}_not_found",
                description=f"Test {endpoint.method} {endpoint.path} - resource not found",
                endpoint=endpoint.path,
                method=endpoint.method,
                parameters=not_found_params,
                expected_status=404,
                is_negative_test=True
            ))

        return scenarios

    async def _generate_custom_error_scenarios(self, endpoint, status_code: str) -> List[TestScenario]:
        """Generate scenarios for custom error codes."""
        # For now, skip custom error scenarios as they're usually edge cases
        return []

    async def _generate_format_invalid_parameters(self, endpoint) -> Dict[str, Any]:
        """Generate parameters that are format-invalid (should cause 400)."""
        parameters = {}

        for param in endpoint.parameters:
            param_name = param.get('name', 'unknown')
            param_description = param.get('description', '').lower()
            param_schema = param.get('schema', {})
            param_type = param_schema.get('type', 'string')

            # Generate format-invalid values based on parameter description
            if 'iso' in param_description and 'alpha' in param_description:
                # For ISO codes, use values that are too long (should be 2-3 chars)
                if 'alpha-2' in param_description:
                    parameters[param_name] = 'TOOLONG'  # Too long for alpha-2
                elif 'alpha-3' in param_description:
                    parameters[param_name] = 'WAYTOOLONG'  # Too long for alpha-3
                else:
                    parameters[param_name] = 'INVALIDFORMAT123'  # Invalid format
            elif 'currency' in param_description and 'iso' in param_description:
                # For ISO currency codes, use invalid format
                parameters[param_name] = 'INVALID_CURRENCY_FORMAT'
            elif 'language' in param_description and 'iso' in param_description:
                # For ISO language codes, use invalid format
                parameters[param_name] = 'INVALID_LANG_FORMAT'
            elif param_type == 'integer':
                # For integers, use string that can't be parsed
                parameters[param_name] = 'not_a_number'
            elif param_type == 'boolean':
                # For booleans, use invalid string
                parameters[param_name] = 'not_a_boolean'
            else:
                # For other string parameters, use special characters that might cause parsing issues
                parameters[param_name] = '!@#$%^&*()'

        return parameters

    async def _generate_not_found_parameters_smart(self, endpoint) -> Dict[str, Any]:
        """Generate parameters that are format-valid but should result in 404."""
        parameters = {}

        for param in endpoint.parameters:
            param_name = param.get('name', 'unknown')
            param_description = param.get('description', '').lower()
            param_schema = param.get('schema', {})

            # Generate format-valid but non-existent values
            if 'iso' in param_description and 'alpha' in param_description:
                # For ISO codes, use valid format but non-existent country codes
                if 'alpha-2' in param_description:
                    parameters[param_name] = 'ZZ'  # Valid format, non-existent country
                elif 'alpha-3' in param_description:
                    parameters[param_name] = 'ZZZ'  # Valid format, non-existent country
                else:
                    parameters[param_name] = 'XX'  # Generic non-existent code
            elif 'currency' in param_description:
                # For currency codes, use valid format but non-existent currency
                parameters[param_name] = 'zzz'  # Valid format, non-existent currency
            elif 'language' in param_description:
                # For language codes, use valid format but non-existent language
                parameters[param_name] = 'zz'  # Valid format, non-existent language
            elif 'country' in param_description or param_name.lower() in ['name', 'country']:
                # For country names, use non-existent country
                parameters[param_name] = 'NonExistentCountry'
            elif 'capital' in param_description or param_name.lower() == 'capital':
                # For capital cities, use non-existent capital
                parameters[param_name] = 'NonExistentCapital'
            elif 'region' in param_description or param_name.lower() == 'region':
                # For regions, use non-existent region
                parameters[param_name] = 'NonExistentRegion'
            else:
                # Generic non-existent value
                parameters[param_name] = 'NonExistent'

        return parameters

    def _merge_scenarios(self, primary_scenarios: List[TestScenario], secondary_scenarios: List[TestScenario]) -> List[TestScenario]:
        """
        Merge two lists of scenarios, avoiding duplicates.

        Args:
            primary_scenarios: Primary scenarios (higher priority)
            secondary_scenarios: Secondary scenarios

        Returns:
            Merged list of scenarios
        """
        merged = primary_scenarios.copy()
        primary_names = {scenario.name for scenario in primary_scenarios}

        for scenario in secondary_scenarios:
            if scenario.name not in primary_names:
                merged.append(scenario)

        return merged

    async def _validate_scenarios(self, scenarios: List[TestScenario], api_spec: Any) -> List[TestScenario]:
        """
        Validate and enrich test scenarios.

        Args:
            scenarios: Generated test scenarios
            api_spec: API specification

        Returns:
            Validated and enriched scenarios
        """
        validated_scenarios = []

        for scenario in scenarios:
            # Find matching endpoint (handle parameterized paths)
            endpoint = self._find_matching_endpoint(api_spec, scenario.endpoint, scenario.method)

            if endpoint:
                # Enrich scenario with specification details
                if not scenario.expected_response_schema and endpoint.responses:
                    success_response = endpoint.responses.get('200') or endpoint.responses.get('201')
                    if success_response:
                        scenario.expected_response_schema = success_response.get('content', {})

                validated_scenarios.append(scenario)
                self.logger.debug(f"Validated scenario: {scenario.method} {scenario.endpoint}")
            else:
                # Check if this is a scenario from source code analysis
                if "source_code" in scenario.name:
                    # Keep scenarios from source code analysis even if not in specification
                    validated_scenarios.append(scenario)
                    self.logger.info(f"Keeping source code scenario: {scenario.method} {scenario.endpoint}")
                else:
                    # For scenarios generated from OpenAPI spec, they should always be valid
                    # Only warn for LLM-generated scenarios that don't match
                    if not any(scenario.endpoint == ep.path for ep in api_spec.endpoints):
                        self.logger.warning(
                            f"Scenario endpoint not found in specification: {scenario.method} {scenario.endpoint}"
                        )
                    else:
                        # This is likely a scenario generated from the spec, keep it
                        validated_scenarios.append(scenario)

        return validated_scenarios

    async def _generate_scenarios_with_dependencies(
        self,
        api_spec: Any,
        implementation_analysis: Dict[str, Any],
        dependency_analysis: Dict[str, Any],
        base_url: str
    ) -> List[TestScenario]:
        """
        Generate test scenarios with dependency awareness.
        
        Args:
            api_spec: Parsed API specification
            implementation_analysis: Implementation analysis results
            dependency_analysis: Dependency analysis results
            base_url: Base URL for the API
            
        Returns:
            List of dependency-aware test scenarios
        """
        scenarios = []
        
        # Generate workflow-based scenarios first (these are dependency-aware)
        #workflows = dependency_analysis.get('workflows', [])
        #if workflows:
        #    workflow_scenarios = self.dependency_analyzer.generate_workflow_scenarios(workflows)
        #    scenarios.extend(workflow_scenarios)
        #    self.logger.info(f"Generated {len(workflow_scenarios)} workflow-based scenarios")
        
        # Generate scenarios from OpenAPI specification with parameter examples
        spec_scenarios = await self._generate_scenarios_from_openapi_with_examples(api_spec, base_url)
        scenarios.extend(spec_scenarios)
        self.logger.info(f"Generated {len(spec_scenarios)} scenarios from OpenAPI specification")
        
        # Generate scenarios from source code analysis
        if implementation_analysis:
            source_scenarios = await self._generate_scenarios_from_source_code(implementation_analysis, base_url)
            scenarios.extend(source_scenarios)
            self.logger.info(f"Generated {len(source_scenarios)} scenarios from source code analysis")
        
        # Remove duplicates while preserving workflow scenarios
        unique_scenarios = self._deduplicate_scenarios_preserving_workflows(scenarios)
        
        self.logger.info(f"Generated {len(scenarios)} total scenarios, {len(unique_scenarios)} after deduplication")
        return unique_scenarios

    async def _generate_scenarios_from_openapi_with_examples(
        self,
        api_spec: Any,
        base_url: str
    ) -> List[TestScenario]:
        """
        Generate test scenarios from OpenAPI specification, prioritizing parameter examples.
        
        Args:
            api_spec: Parsed API specification
            base_url: Base URL for the API
            
        Returns:
            List of test scenarios with example-based parameters
        """
        scenarios = []

        for endpoint in api_spec.endpoints:
            # Extract parameters with priority for examples
            parameters = await self._extract_parameters_with_examples_priority(endpoint)
            
            # Generate positive test scenario
            scenarios.append(TestScenario(
                name=f"test_{endpoint.method.lower()}_{self._sanitize_path(endpoint.path)}_success",
                description=f"Test {endpoint.method} {endpoint.path} - success case with example data",
                endpoint=endpoint.path,
                method=endpoint.method,
                parameters=parameters,
                expected_status=self._determine_expected_status(endpoint.method),
                is_negative_test=False,
                test_data=parameters
            ))

            # Generate negative test scenarios if enabled
            if self.system_config.test_generation.generate_negative_tests:
                negative_scenarios = await self._generate_negative_scenarios_for_endpoint(endpoint)
                scenarios.extend(negative_scenarios)

        return scenarios

    async def _extract_parameters_with_examples_priority(self, endpoint) -> Dict[str, Any]:
        """
        Extract parameters with priority for examples from OpenAPI specification.
        
        Args:
            endpoint: API endpoint specification
            
        Returns:
            Dictionary of parameter values with examples prioritized
        """
        parameters = {}

        for param in endpoint.parameters:
            param_name = param.get('name', 'unknown')
            param_schema = param.get('schema', {})
            param_type = param_schema.get('type', 'string')

            # Priority 1: Use example from parameter schema
            if 'example' in param_schema:
                parameters[param_name] = param_schema['example']
                self.logger.debug(f"Using example for {param_name}: {param_schema['example']}")
                continue

            # Priority 2: Use example from parameter itself (Swagger 2.0 style)
            if 'example' in param:
                parameters[param_name] = param['example']
                self.logger.debug(f"Using parameter example for {param_name}: {param['example']}")
                continue

            # Priority 3: Use enum values
            if 'enum' in param_schema and param_schema['enum']:
                parameters[param_name] = param_schema['enum'][0]
                self.logger.debug(f"Using enum value for {param_name}: {param_schema['enum'][0]}")
                continue

            # Priority 4: Generate realistic values based on parameter name and type
            realistic_value = self._generate_realistic_parameter_value(
                param_name, param_type, param.get('description', '')
            )

            # Priority 5: Use LLM as fallback for complex parameters
            if realistic_value == 'test_value' and self.openrouter_client:
                llm_value = await self._generate_parameter_with_llm(
                    param_name, param_type, param.get('description', ''), endpoint.path
                )
                if llm_value:
                    realistic_value = llm_value

            parameters[param_name] = realistic_value
            self.logger.debug(f"Generated value for {param_name}: {realistic_value}")

        return parameters

    def _determine_expected_status(self, method: str) -> int:
        """
        Determine expected status code based on HTTP method.
        
        Args:
            method: HTTP method
            
        Returns:
            Expected status code
        """
        status_map = {
            'GET': 200,
            'POST': 201,  # Created
            'PUT': 200,   # Updated
            'PATCH': 200, # Updated
            'DELETE': 204 # No Content
        }
        return status_map.get(method.upper(), 200)

    def _deduplicate_scenarios_preserving_workflows(self, scenarios: List[TestScenario]) -> List[TestScenario]:
        """
        Remove duplicate scenarios while preserving workflow-based scenarios.
        
        Args:
            scenarios: List of scenarios to deduplicate
            
        Returns:
            Deduplicated list of scenarios
        """
        unique_scenarios = []
        seen_keys = set()
        
        # First pass: Add workflow scenarios (these have priority)
        for scenario in scenarios:
            if hasattr(scenario, 'workflow_name') and scenario.workflow_name:
                unique_scenarios.append(scenario)
                # Create a key based on method and path for deduplication
                key = f"{scenario.method}_{scenario.endpoint}"
                seen_keys.add(key)
        
        # Second pass: Add non-workflow scenarios if not already covered
        for scenario in scenarios:
            if not (hasattr(scenario, 'workflow_name') and scenario.workflow_name):
                key = f"{scenario.method}_{scenario.endpoint}"
                if key not in seen_keys:
                    unique_scenarios.append(scenario)
                    seen_keys.add(key)
                else:
                    self.logger.debug(f"Skipping duplicate scenario: {scenario.name}")
        
        original_count = len(scenarios)
        final_count = len(unique_scenarios)
        
        if original_count != final_count:
            self.logger.info(f"Deduplicated scenarios: {original_count} -> {final_count}")
        
        return unique_scenarios

    def _find_matching_endpoint(self, api_spec: Any, path: str, method: str) -> Optional[Any]:
        """
        Find an endpoint that matches the given path and method, handling parameterized paths.

        Args:
            api_spec: API specification
            path: Request path (may contain actual values instead of parameters)
            method: HTTP method

        Returns:
            Matching endpoint or None
        """
        for endpoint in api_spec.endpoints:
            if endpoint.method.upper() == method.upper():
                # Exact match
                if endpoint.path == path:
                    return endpoint

                # Check if this could be a parameterized path match
                if self._paths_match_with_parameters(endpoint.path, path):
                    return endpoint

        return None

    def _paths_match_with_parameters(self, spec_path: str, request_path: str) -> bool:
        """
        Check if a request path matches a specification path with parameters.

        Args:
            spec_path: Path from specification (e.g., "/v2/name/{name}")
            request_path: Actual request path (e.g., "/v2/name/France")

        Returns:
            True if paths match
        """
        spec_parts = spec_path.split('/')
        request_parts = request_path.split('/')

        if len(spec_parts) != len(request_parts):
            return False

        for spec_part, request_part in zip(spec_parts, request_parts):
            # If spec part is a parameter (contains {}), it matches any value
            if '{' in spec_part and '}' in spec_part:
                continue
            # Otherwise, parts must match exactly
            elif spec_part != request_part:
                return False

        return True

    def _is_rest_controller(self, java_class) -> bool:
        """Check if a Java class is a REST controller."""
        rest_annotations = ['@RestController', '@Controller', '@Path']

        for annotation in java_class.annotations:
            if any(rest_ann in annotation for rest_ann in rest_annotations):
                return True

        return False

    def _create_implementation_summary(self, analysis: Dict[str, Any]) -> str:
        """Create a summary of the implementation analysis."""
        maven_info = analysis.get('maven_project', {})
        java_classes = analysis.get('java_classes', [])
        rest_endpoints = analysis.get('rest_endpoints', [])

        summary_parts = []

        if maven_info:
            summary_parts.append(f"Maven project: {maven_info.get('artifact_id', 'unknown')}")
            if maven_info.get('is_spring_project'):
                summary_parts.append("Framework: Spring")
            elif maven_info.get('is_jaxrs_project'):
                summary_parts.append("Framework: JAX-RS")

        summary_parts.append(f"Java classes: {len(java_classes)}")
        summary_parts.append(f"REST endpoints: {len(rest_endpoints)}")

        return "; ".join(summary_parts)

    def _create_api_summary(self, api_spec: Any) -> Dict[str, Any]:
        """Create a summary of the API specification."""
        return {
            'title': api_spec.title,
            'version': api_spec.version,
            'description': api_spec.description,
            'base_url': api_spec.base_url,
            'endpoints_count': len(api_spec.endpoints),
            'schemas_count': len(api_spec.schemas),
            'endpoints': [
                {
                    'path': endpoint.path,
                    'method': endpoint.method,
                    'summary': endpoint.summary
                }
                for endpoint in api_spec.endpoints[:10]  # First 10 endpoints
            ]
        }

    def _format_api_spec_for_llm(self, api_spec: Any) -> str:
        """Format API specification for LLM consumption."""
        spec_parts = [
            f"API: {api_spec.title} v{api_spec.version}",
            f"Description: {api_spec.description or 'No description'}",
            f"Base URL: {api_spec.base_url or 'Not specified'}",
            "",
            "Endpoints:"
        ]

        for endpoint in api_spec.endpoints:
            spec_parts.append(f"- {endpoint.method} {endpoint.path}")
            if endpoint.summary:
                spec_parts.append(f"  Summary: {endpoint.summary}")
            if endpoint.parameters:
                spec_parts.append(f"  Parameters: {len(endpoint.parameters)} parameters")

        return "\n".join(spec_parts)

    def _parse_llm_scenarios_response(self, response: str, base_url: str) -> List[TestScenario]:
        """Parse LLM response into test scenarios."""
        try:
            # Try to extract JSON from the response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)

                scenarios = []
                for scenario_data in data.get('scenarios', []):
                    scenario = TestScenario(
                        name=scenario_data.get('name', 'unnamed_test'),
                        description=scenario_data.get('description', ''),
                        endpoint=scenario_data.get('endpoint', '/'),
                        method=scenario_data.get('method', 'GET'),
                        parameters=scenario_data.get('parameters', {}),
                        expected_status=scenario_data.get('expected_status', 200),
                        expected_response_schema=scenario_data.get('expected_response_schema'),
                        is_negative_test=scenario_data.get('is_negative_test', False),
                        test_data=scenario_data.get('test_data')
                    )
                    scenarios.append(scenario)

                return scenarios

        except json.JSONDecodeError as e:
            self.log_error("Failed to parse LLM response as JSON", e)
        except Exception as e:
            self.log_error("Failed to parse LLM scenarios response", e)

        return []

    def _sanitize_path(self, path: str) -> str:
        """Sanitize path for use in method names."""
        return path.replace('/', '_').replace('{', '').replace('}', '').replace('-', '_')

    async def _extract_parameters(self, endpoint) -> Dict[str, Any]:
        """Extract valid parameters from endpoint specification using examples or LLM inference."""
        return await self._extract_valid_parameters(endpoint)

    async def _extract_valid_parameters(self, endpoint) -> Dict[str, Any]:
        """Extract valid parameters for success test cases."""
        parameters = {}

        for param in endpoint.parameters:
            param_name = param.get('name', 'unknown')
            param_schema = param.get('schema', {})
            param_type = param_schema.get('type', 'string')

            # First, try to use example from specification
            if 'example' in param_schema:
                parameters[param_name] = param_schema['example']
                continue

            # Second, try to use enum values
            if 'enum' in param_schema and param_schema['enum']:
                parameters[param_name] = param_schema['enum'][0]  # Use first enum value
                continue

            # Third, generate realistic values based on parameter name and type
            realistic_value = self._generate_realistic_parameter_value(param_name, param_type, param.get('description', ''))

            # Fourth, use LLM as fallback if we couldn't generate a good value
            if realistic_value == 'test_value' and self.openrouter_client:
                llm_value = await self._generate_parameter_with_llm(param_name, param_type, param.get('description', ''), endpoint.path)
                if llm_value:
                    realistic_value = llm_value

            parameters[param_name] = realistic_value

        return parameters

    async def _generate_parameter_with_llm(self, param_name: str, param_type: str, description: str, endpoint_path: str) -> Optional[str]:
        """Use LLM to generate realistic parameter values when rule-based approach fails."""
        try:
            prompt = f"""Generate a realistic value for the API parameter:

Parameter name: {param_name}
Parameter type: {param_type}
Description: {description}
Endpoint: {endpoint_path}

Requirements:
1. The value must be realistic and likely to exist in a real API
2. For country-related APIs, use real country data
3. For codes, use valid format (e.g., ISO codes)
4. Return ONLY the parameter value, no explanations

Example responses:
- For country name: "portugal"
- For country code: "pt"
- For currency: "eur"
- For language: "pt"
- For region: "europe"

Parameter value:"""

            response = await self.openrouter_client.generate_text(
                prompt=prompt,
                model=self.get_model_name(),
                max_tokens=50,
                temperature=0.1  # Low temperature for consistent results
            )

            if response and len(response.strip()) > 0:
                # Clean the response and return first word/value
                value = response.strip().split()[0].strip('"\'')
                return value

        except Exception as e:
            self.logger.warning(f"LLM parameter generation failed: {e}")

        return None

    def _extract_invalid_parameters(self, endpoint) -> Dict[str, Any]:
        """Extract invalid parameters for negative test cases."""
        parameters = {}

        for param in endpoint.parameters:
            param_name = param.get('name', 'unknown')
            param_schema = param.get('schema', {})
            param_type = param_schema.get('type', 'string')

            # Generate truly invalid values that should cause 400 errors
            invalid_value = self._generate_invalid_parameter_value(param_name, param_type, param.get('description', ''))
            parameters[param_name] = invalid_value

        return parameters

    def _generate_realistic_parameter_value(self, param_name: str, param_type: str, description: str) -> Any:
        """Generate realistic parameter values based on name, type, and description."""
        param_name_lower = param_name.lower()
        description_lower = description.lower()

        # Handle different parameter types
        if param_type == 'integer':
            if 'id' in param_name_lower:
                return 1
            elif 'page' in param_name_lower:
                return 1
            elif 'limit' in param_name_lower or 'size' in param_name_lower:
                return 10
            else:
                return 1

        elif param_type == 'boolean':
            return True

        elif param_type == 'number':
            return 1.0

        else:  # string type
            # Country-specific parameters
            if param_name_lower in ['name', 'country', 'countryname']:
                return 'portugal'
            elif param_name_lower in ['code', 'alpha', 'countrycode', 'alpha2', 'alpha3']:
                return 'pt'
            elif param_name_lower in ['currency', 'currencycode']:
                return 'eur'
            elif param_name_lower in ['language', 'lang', 'languagecode']:
                return 'pt'
            elif param_name_lower in ['capital', 'capitalcity']:
                return 'lisbon'
            elif param_name_lower in ['region', 'regionname']:
                return 'europe'

            # Generic parameters based on description
            elif 'iso' in description_lower and 'alpha' in description_lower:
                return 'pt'
            elif 'currency' in description_lower:
                return 'eur'
            elif 'language' in description_lower:
                return 'pt'
            elif 'region' in description_lower:
                return 'europe'
            elif 'capital' in description_lower:
                return 'lisbon'
            elif 'country' in description_lower:
                return 'portugal'

            # Generic fallbacks
            elif 'id' in param_name_lower:
                return '123'
            elif 'email' in param_name_lower:
                return 'test@example.com'
            elif 'phone' in param_name_lower:
                return '+1234567890'
            elif 'url' in param_name_lower:
                return 'https://example.com'
            else:
                return 'test_value'

    def _generate_invalid_parameter_value(self, param_name: str, param_type: str, description: str) -> Any:
        """Generate invalid parameter values that should cause 400 errors."""
        param_name_lower = param_name.lower()

        # Handle different parameter types
        if param_type == 'integer':
            return 'not_a_number'  # String instead of integer

        elif param_type == 'boolean':
            return 'not_a_boolean'  # String instead of boolean

        elif param_type == 'number':
            return 'not_a_number'  # String instead of number

        else:  # string type
            # Generate values that are syntactically invalid for the expected format
            if 'email' in param_name_lower:
                return 'invalid_email'
            elif 'url' in param_name_lower:
                return 'not_a_url'
            elif 'phone' in param_name_lower:
                return 'invalid_phone'
            elif 'code' in param_name_lower and ('iso' in description.lower() or 'alpha' in description.lower()):
                return '123456789'  # Too long for ISO codes
            elif 'currency' in param_name_lower or 'currency' in description.lower():
                return 'INVALID_CURRENCY_CODE'
            else:
                # Use special characters that might cause parsing issues
                return '!@#$%^&*()'

