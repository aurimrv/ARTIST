"""
Additional methods for PlannerAgent to handle dependency-aware scenario generation.
"""

from typing import Any, Dict, List
from ..config.models import TestScenario


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
    workflows = dependency_analysis.get('workflows', [])
    if workflows:
        workflow_scenarios = self.dependency_analyzer.generate_workflow_scenarios(workflows)
        scenarios.extend(workflow_scenarios)
        self.logger.info(f"Generated {len(workflow_scenarios)} workflow-based scenarios")
    
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


# Add these methods to the PlannerAgent class
def add_dependency_methods_to_planner_agent():
    """Add the dependency-aware methods to PlannerAgent class."""
    import types
    from .planner_agent import PlannerAgent
    
    # Add methods to the class
    PlannerAgent._generate_scenarios_with_dependencies = _generate_scenarios_with_dependencies
    PlannerAgent._generate_scenarios_from_openapi_with_examples = _generate_scenarios_from_openapi_with_examples
    PlannerAgent._extract_parameters_with_examples_priority = _extract_parameters_with_examples_priority
    PlannerAgent._determine_expected_status = _determine_expected_status
    PlannerAgent._deduplicate_scenarios_preserving_workflows = _deduplicate_scenarios_preserving_workflows

