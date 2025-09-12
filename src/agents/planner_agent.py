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
        
        # Initialize OpenRouter client for LLM-assisted scenario generation
        if self.system_config.openrouter.api_key:
            self.openrouter_client = OpenRouterClient(self.system_config.openrouter)
            self.logger.info("OpenRouter client initialized")
        else:
            self.logger.warning("No OpenRouter API key provided - using basic scenario generation only")
        
        self.logger.info("Planner Agent initialization complete")

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process API specification and implementation to generate test scenarios.
        
        Args:
            input_data: Dictionary containing:
                - api_spec_path: Path to API specification file
                - api_src_path: Optional path to API source code
                - base_url: Base URL for the API
                
        Returns:
            Dictionary containing generated test scenarios and analysis results
        """
        try:
            # Step 1: Parse API specification
            self.log_progress("Parsing API specification", 1, 4)
            api_spec_path = input_data.get('api_spec_path')
            
            if not api_spec_path:
                return {
                    'success': False,
                    'error': "API specification path is required",
                    'scenarios': []
                }

            self.logger.info(f"Parsing API specification: {api_spec_path}")
            api_spec = self.openapi_parser.parse_file(api_spec_path)
            
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

            # Extract base URL from input data
            base_url = input_data.get('base_url', 'http://localhost:8080')
            
            # Step 3: Generate test scenarios
            self.log_progress("Generating test scenarios", 3, 4)
            scenarios = await self._generate_scenarios(api_spec, implementation_analysis, base_url)
            
            # Step 4: Enhance scenarios with LLM if available
            self.log_progress("Enhancing scenarios", 4, 4)
            if self.openrouter_client and scenarios:
                enhanced_scenarios = await self._enhance_scenarios_with_llm(scenarios, api_spec, base_url)
                if enhanced_scenarios:
                    scenarios = enhanced_scenarios
                    self.logger.info(f"Enhanced scenarios with LLM analysis")

            self.logger.info(f"Generated {len(scenarios)} test scenarios")

            return {
                'success': True,
                'message': f"Successfully generated {len(scenarios)} test scenarios",
                'scenarios': scenarios,
                'api_spec_summary': self._create_api_summary(api_spec),
                'implementation_summary': self._create_implementation_summary(implementation_analysis) if implementation_analysis else None
            }

        except Exception as e:
            self.log_error("Unexpected error in planner process", e)
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}",
                'scenarios': []
            }

    async def _analyze_implementation(self, api_src_path: str) -> Dict[str, Any]:
        """Analyze API implementation source code."""
        try:
            src_path = Path(api_src_path)
            
            # Parse Maven project
            maven_analysis = self.maven_parser.parse_project(src_path)
            
            # Parse Java source code
            java_classes = self.java_parser.parse_project(src_path)
            
            # Extract REST endpoints from Java classes
            rest_endpoints = self.java_parser.extract_rest_endpoints(java_classes)
            
            return {
                'maven_project': maven_analysis,
                'java_classes': java_classes,
                'rest_endpoints': rest_endpoints
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing implementation: {e}")
            return {}

    async def _generate_scenarios(
        self,
        api_spec: Any,
        implementation_analysis: Dict[str, Any],
        base_url: str
    ) -> List[TestScenario]:
        """Generate test scenarios from API specification and source code."""
        scenarios = []
        
        # Generate scenarios from OpenAPI specification
        spec_scenarios = self._generate_scenarios_from_spec(api_spec, base_url)
        scenarios.extend(spec_scenarios)
        self.logger.info(f"Generated {len(spec_scenarios)} scenarios from OpenAPI specification")
        
        # Generate scenarios from source code analysis (if available)
        if implementation_analysis:
            source_scenarios = self._generate_scenarios_from_source(implementation_analysis, base_url)
            scenarios.extend(source_scenarios)
            self.logger.info(f"Generated {len(source_scenarios)} scenarios from source code analysis")
        
        # Remove duplicates
        unique_scenarios = self._remove_duplicates(scenarios)
        self.logger.info(f"Total scenarios after deduplication: {len(unique_scenarios)}")
        
        return unique_scenarios

    def _generate_scenarios_from_spec(self, api_spec: Any, base_url: str) -> List[TestScenario]:
        """Generate test scenarios from OpenAPI specification."""
        scenarios = []

        for endpoint in api_spec.endpoints:
            # Extract parameters with priority for examples
            parameters = self._extract_parameters_with_examples(endpoint)
            
            # Generate positive test scenario
            scenarios.append(TestScenario(
                name=f"test_{endpoint.method.lower()}_{self._sanitize_path(endpoint.path)}_success",
                description=f"Test {endpoint.method} {endpoint.path} - success case",
                endpoint=endpoint.path,
                method=endpoint.method,
                parameters=parameters,
                expected_status=self._get_expected_status(endpoint.method),
                is_negative_test=False,
                test_data=parameters
            ))

            # Generate negative test scenarios if enabled
            if self.system_config.test_generation.generate_negative_tests:
                negative_scenarios = self._generate_negative_scenarios(endpoint)
                scenarios.extend(negative_scenarios)

        return scenarios

    def _generate_scenarios_from_source(self, implementation_analysis: Dict[str, Any], base_url: str) -> List[TestScenario]:
        """Generate test scenarios from source code analysis."""
        scenarios = []
        
        rest_endpoints = implementation_analysis.get('rest_endpoints', [])
        
        for endpoint_data in rest_endpoints:
            # Handle both dict and object formats
            if isinstance(endpoint_data, dict):
                endpoint_path = endpoint_data.get('path', '')
                endpoint_method = endpoint_data.get('method', 'GET')
            else:
                endpoint_path = getattr(endpoint_data, 'path', '')
                endpoint_method = getattr(endpoint_data, 'method', 'GET')
            
            # Skip invalid endpoints
            if not self._is_valid_endpoint(endpoint_path):
                self.logger.debug(f"Skipping invalid endpoint: {endpoint_path}")
                continue
            
            # Create scenario
            scenario = TestScenario(
                name=f"test_{endpoint_method.lower()}_{self._sanitize_path(endpoint_path)}_source",
                description=f"Test {endpoint_method} {endpoint_path} (from source code)",
                endpoint=endpoint_path,
                method=endpoint_method,
                parameters={},
                expected_status=200,
                is_negative_test=False,
                test_data={}
            )
            
            scenarios.append(scenario)
        
        return scenarios

    def _is_valid_endpoint(self, endpoint_path: str) -> bool:
        """Check if an endpoint path is valid."""
        if not endpoint_path:
            return False
        
        # Remove leading slash
        path = endpoint_path.lstrip('/')
        
        # Root path is valid
        if not path or path == '/':
            return True
        
        # Split into segments
        segments = path.split('/')
        first_segment = segments[0]
        
        # Check if first segment is a parameter
        if first_segment.startswith('{') and first_segment.endswith('}'):
            return False
        
        # Check for parameter-like names
        invalid_names = [
            'id', 'name', 'productname', 'username', 'featurename', 
            'configurationname', 'constraintid', 'requires', 'excludes'
        ]
        
        if first_segment.lower() in invalid_names:
            return False
        
        return True

    def _extract_parameters_with_examples(self, endpoint) -> Dict[str, Any]:
        """Extract parameters with priority for examples from OpenAPI specification."""
        parameters = {}

        for param in endpoint.parameters:
            param_name = param.get('name', 'unknown')
            param_schema = param.get('schema', {})
            param_type = param_schema.get('type', 'string')

            # Priority 1: Use example from parameter schema
            if 'example' in param_schema:
                parameters[param_name] = param_schema['example']
                continue

            # Priority 2: Use example from parameter itself
            if 'example' in param:
                parameters[param_name] = param['example']
                continue

            # Priority 3: Use enum values
            if 'enum' in param_schema and param_schema['enum']:
                parameters[param_name] = param_schema['enum'][0]
                continue

            # Priority 4: Generate realistic values
            parameters[param_name] = self._generate_realistic_value(param_name, param_type)

        return parameters

    def _generate_realistic_value(self, param_name: str, param_type: str) -> Any:
        """Generate realistic parameter values based on name and type."""
        param_name_lower = param_name.lower()
        
        # String parameters
        if param_type == 'string':
            if 'name' in param_name_lower:
                return 'smartphone'
            elif 'id' in param_name_lower:
                return 'test-id-123'
            elif 'feature' in param_name_lower:
                return 'camera'
            elif 'config' in param_name_lower:
                return 'premium'
            else:
                return 'test-value'
        
        # Integer parameters
        elif param_type == 'integer':
            return 123
        
        # Boolean parameters
        elif param_type == 'boolean':
            return True
        
        # Default
        else:
            return 'test-value'

    def _generate_negative_scenarios(self, endpoint) -> List[TestScenario]:
        """Generate negative test scenarios for an endpoint."""
        scenarios = []
        
        # Invalid parameter scenario
        if endpoint.parameters:
            invalid_params = {}
            for param in endpoint.parameters:
                param_name = param.get('name', 'unknown')
                invalid_params[param_name] = None  # Invalid value
            
            scenarios.append(TestScenario(
                name=f"test_{endpoint.method.lower()}_{self._sanitize_path(endpoint.path)}_invalid_params",
                description=f"Test {endpoint.method} {endpoint.path} - invalid parameters",
                endpoint=endpoint.path,
                method=endpoint.method,
                parameters=invalid_params,
                expected_status=400,
                is_negative_test=True,
                test_data=invalid_params
            ))
        
        return scenarios

    def _get_expected_status(self, method: str) -> int:
        """Get expected status code for HTTP method."""
        status_map = {
            'GET': 200,
            'POST': 201,
            'PUT': 200,
            'PATCH': 200,
            'DELETE': 204
        }
        return status_map.get(method.upper(), 200)

    def _sanitize_path(self, path: str) -> str:
        """Sanitize path for use in test method names."""
        # Remove leading slash and replace special characters
        sanitized = path.lstrip('/').replace('/', '_').replace('{', '').replace('}', '')
        # Replace multiple underscores with single
        sanitized = '_'.join(filter(None, sanitized.split('_')))
        return sanitized or 'root'

    def _remove_duplicates(self, scenarios: List[TestScenario]) -> List[TestScenario]:
        """Remove duplicate scenarios."""
        unique_scenarios = []
        seen_signatures = set()
        
        for scenario in scenarios:
            # Create signature based on method, endpoint, and test type
            signature = (
                scenario.method,
                scenario.endpoint,
                scenario.is_negative_test
            )
            
            if signature not in seen_signatures:
                unique_scenarios.append(scenario)
                seen_signatures.add(signature)
        
        return unique_scenarios

    async def _enhance_scenarios_with_llm(
        self,
        scenarios: List[TestScenario],
        api_spec: Any,
        base_url: str
    ) -> Optional[List[TestScenario]]:
        """Enhance scenarios using LLM analysis."""
        try:
            # Prepare context for LLM
            context = self._prepare_llm_context(scenarios, api_spec, base_url)
            
            # Get LLM enhancement
            prompt = self._build_enhancement_prompt(context)
            
            response = await self.openrouter_client.generate_text(
                prompt=prompt,
                model=self.config.model,
                max_tokens=8000,
                temperature=0.1
            )
            
            if response:
                enhanced_data = self._parse_llm_response(response)
                if enhanced_data:
                    return self._create_enhanced_scenarios(enhanced_data, scenarios)
            
        except Exception as e:
            self.logger.error(f"Error enhancing scenarios with LLM: {e}")
        
        return None

    def _prepare_llm_context(self, scenarios: List[TestScenario], api_spec: Any, base_url: str) -> Dict[str, Any]:
        """Prepare context for LLM analysis."""
        # Extract API endpoints
        api_endpoints = []
        for endpoint in api_spec.endpoints:
            api_endpoints.append({
                'path': endpoint.path,
                'method': endpoint.method,
                'parameters': [p.get('name', 'unknown') for p in endpoint.parameters],
                'description': endpoint.description or f"{endpoint.method} {endpoint.path}"
            })
        
        # Extract scenario information
        scenario_info = []
        for scenario in scenarios:
            scenario_info.append({
                'name': scenario.name,
                'endpoint': scenario.endpoint,
                'method': scenario.method,
                'parameters': scenario.parameters,
                'description': scenario.description
            })
        
        return {
            'base_url': base_url,
            'api_endpoints': api_endpoints,
            'current_scenarios': scenario_info,
            'api_title': getattr(api_spec, 'title', 'API'),
            'api_description': getattr(api_spec, 'description', '')
        }

    @staticmethod
    def _build_enhancement_prompt(context: Dict[str, Any]) -> str:
        """Build prompt for LLM scenario enhancement."""
        return f"""
You are an expert API testing specialist. Analyze the following API specification and test scenarios to improve them.

API Information:
- Title: {context['api_title']}
- Description: {context['api_description']}
- Base URL: {context['base_url']}

API Endpoints:
{json.dumps(context['api_endpoints'], indent=2)}

Current Test Scenarios:
{json.dumps(context['current_scenarios'], indent=2)}

Your task is to:
1. Identify realistic test flows (Create → Read → Update → Delete)
2. Ensure parameter values are realistic and consistent
3. WE MUST HAVE AT LEAST ONE SCENARIO FOR EACH API ENDPOINT
4. Explore all possibilities available for POST, PUT, GET and DELETE methods
5. Add dependency information between scenarios and update TestScenarios
6. Improve scenario descriptions

Rules:
- Ensure all endpoints start with valid paths (not with parameters like /{{param}})
- Use consistent parameter values across related scenarios

Return ONLY the JSON object with this structure:
{{
    "enhanced_scenarios": [
        {{
            "name": "test_method_name",
            "description": "Clear description of what this test does",
            "endpoint": "/valid/endpoint/path",
            "method": "HTTP_METHOD",
            "parameters": {{"param": "value"}},
            "expected_status": 200,
            "is_negative_test": false,
            "test_data": {{"param": "value"}}
        }}
    ]
}}

Focus on creating realistic, executable test scenarios that follow proper API usage patterns.
"""

    def _parse_llm_response(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse LLM response."""
        try:
            # Clean up response
            content = content.strip()
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            
            return json.loads(content)
        except Exception as e:
            self.logger.error(f"Error parsing LLM response: {e}")
            return None

    def _create_enhanced_scenarios(
        self,
        enhanced_data: Dict[str, Any],
        original_scenarios: List[TestScenario]
    ) -> List[TestScenario]:
        """Create enhanced scenarios from LLM response."""
        enhanced_scenarios = []
        
        try:
            scenarios_data = enhanced_data.get('enhanced_scenarios', [])
            
            for scenario_data in scenarios_data:
                scenario = TestScenario(
                    name=scenario_data.get('name', 'unknown_test'),
                    description=scenario_data.get('description', ''),
                    endpoint=scenario_data.get('endpoint', '/'),
                    method=scenario_data.get('method', 'GET'),
                    parameters=scenario_data.get('parameters', {}),
                    expected_status=scenario_data.get('expected_status', 200),
                    is_negative_test=scenario_data.get('is_negative_test', False),
                    test_data=scenario_data.get('test_data', {})
                )
                enhanced_scenarios.append(scenario)
        
        except Exception as e:
            self.logger.error(f"Error creating enhanced scenarios: {e}")
            return original_scenarios
        
        return enhanced_scenarios if enhanced_scenarios else original_scenarios

    def _create_api_summary(self, api_spec: Any) -> Dict[str, Any]:
        """Create API specification summary."""
        return {
            'title': getattr(api_spec, 'title', 'Unknown API'),
            'version': getattr(api_spec, 'version', 'Unknown'),
            'description': getattr(api_spec, 'description', ''),
            'endpoint_count': len(api_spec.endpoints) if hasattr(api_spec, 'endpoints') else 0,
            'base_path': getattr(api_spec, 'base_path', '/')
        }

    def _create_implementation_summary(self, implementation_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Create implementation analysis summary."""
        maven_project = implementation_analysis.get('maven_project')
        maven_artifact_id = 'Unknown'
        
        if maven_project:
            # MavenProject is a dataclass, access attributes directly
            maven_artifact_id = getattr(maven_project, 'artifact_id', 'Unknown')
        
        return {
            'java_classes_count': len(implementation_analysis.get('java_classes', [])),
            'rest_endpoints_count': len(implementation_analysis.get('rest_endpoints', [])),
            'maven_project': maven_artifact_id
        }

