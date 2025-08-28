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
    
    async def _initialize_impl(self):
        """Initialize the planner agent components."""
        self.logger.info("Initializing Planner Agent")
        
        # Initialize OpenRouter client
        if self.system_config.openrouter.api_key:
            self.openrouter_client = OpenRouterClient(self.system_config.openrouter)
            self.logger.info("OpenRouter client initialized")
        else:
            self.logger.warning("No OpenRouter API key provided - LLM features disabled")
        
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
            
            # Step 2: Analyze implementation
            self.log_progress("Analyzing API implementation", 2, 4)
            implementation_analysis = await self._analyze_implementation(input_data['api_src_path'])
            
            # Step 3: Generate test scenarios
            self.log_progress("Generating test scenarios", 3, 4)
            scenarios = await self._generate_test_scenarios(
                api_spec, 
                implementation_analysis, 
                input_data.get('base_url', '')
            )
            
            # Step 4: Validate and enrich scenarios
            self.log_progress("Validating and enriching scenarios", 4, 4)
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
        
        required_fields = ['api_spec_path', 'api_src_path']
        
        for field in required_fields:
            if field not in input_data:
                errors.append(f"Missing required field: {field}")
            elif not input_data[field]:
                errors.append(f"Empty value for required field: {field}")
        
        # Validate paths exist
        if 'api_spec_path' in input_data:
            spec_path = Path(input_data['api_spec_path'])
            if not spec_path.exists():
                errors.append(f"API specification file not found: {spec_path}")
        
        if 'api_src_path' in input_data:
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
        implementation_analysis: Dict[str, Any],
        base_url: str
    ) -> List[TestScenario]:
        """
        Generate comprehensive test scenarios based on API specification.
        
        Args:
            api_spec: Parsed API specification
            implementation_analysis: Analysis of the implementation
            base_url: Base URL for the API
        
        Returns:
            List of test scenarios
        """
        try:
            # Always prioritize rule-based generation from OpenAPI spec
            scenarios = await self._generate_scenarios_from_openapi(api_spec, base_url)
            
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
                parameters=self._extract_parameters(endpoint),
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
                parameters=self._extract_parameters(endpoint),
                expected_status=200,
                is_negative_test=False
            ))
            
            # Generate negative test scenarios if enabled
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
                
                # Not found test for endpoints with path parameters
                if '{' in endpoint.path:
                    scenarios.append(TestScenario(
                        name=f"test_{endpoint.method.lower()}_{self._sanitize_path(endpoint.path)}_not_found",
                        description=f"Test {endpoint.method} {endpoint.path} - resource not found",
                        endpoint=endpoint.path,
                        method=endpoint.method,
                        parameters=self._generate_not_found_parameters(endpoint),
                        expected_status=404,
                        is_negative_test=True
                    ))
        
        self.logger.info(f"Generated {len(scenarios)} scenarios from OpenAPI specification")
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
    
    def _generate_not_found_parameters(self, endpoint) -> Dict[str, Any]:
        """Generate parameters that should result in 404 responses."""
        params = {}
        for param in endpoint.parameters:
            if param.get('in') == 'path':
                param_name = param.get('name', 'id')
                # Use values that are unlikely to exist
                if 'id' in param_name.lower():
                    params[param_name] = '999999'
                elif 'name' in param_name.lower():
                    params[param_name] = 'NonExistentResource'
                elif 'code' in param_name.lower():
                    params[param_name] = 'INVALID'
                else:
                    params[param_name] = 'NotFound'
        return params

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
    
    def _extract_parameters(self, endpoint) -> Dict[str, Any]:
        """Extract parameters from endpoint specification."""
        parameters = {}
        
        for param in endpoint.parameters:
            param_name = param.get('name', 'unknown')
            param_type = param.get('schema', {}).get('type', 'string')
            
            # Generate sample value based on type
            if param_type == 'integer':
                parameters[param_name] = 1
            elif param_type == 'boolean':
                parameters[param_name] = True
            else:
                parameters[param_name] = 'sample_value'
        
        return parameters

