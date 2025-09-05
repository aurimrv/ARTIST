"""
Dependency Analyzer for API Endpoints

This module analyzes API endpoints to understand their dependencies and 
generates realistic test scenarios that respect the API workflow.
"""

import json
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from pathlib import Path

from ..config.models import TestScenario
from ..utils import OpenRouterClient


@dataclass
class EndpointDependency:
    """Represents a dependency between two endpoints."""
    source_endpoint: str
    source_method: str
    target_endpoint: str
    target_method: str
    dependency_type: str  # 'creates', 'requires', 'modifies', 'deletes'
    parameter_mapping: Dict[str, str]  # Maps response field to request parameter
    description: str


@dataclass
class APIWorkflow:
    """Represents a workflow of API calls that should be executed in order."""
    name: str
    description: str
    steps: List[Dict[str, Any]]  # Each step is an endpoint call
    setup_data: Dict[str, Any]  # Data needed to initialize the workflow


class DependencyAnalyzer:
    """Analyzes API endpoints to understand dependencies and generate realistic workflows."""
    
    def __init__(self, openrouter_client: Optional[OpenRouterClient] = None):
        """
        Initialize the dependency analyzer.
        
        Args:
            openrouter_client: Client for LLM-based analysis
        """
        self.openrouter_client = openrouter_client
        self.dependencies: List[EndpointDependency] = []
        self.workflows: List[APIWorkflow] = []
    
    async def analyze_api_dependencies(
        self, 
        api_spec: Any, 
        implementation_analysis: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze API dependencies using LLM and specification analysis.
        
        Args:
            api_spec: Parsed API specification
            implementation_analysis: Optional implementation analysis
            
        Returns:
            Dictionary with dependency analysis results
        """
        # Step 1: Extract endpoint information
        endpoints_info = self._extract_endpoints_info(api_spec)
        
        # Step 2: Use LLM to analyze dependencies
        if self.openrouter_client:
            llm_analysis = await self._analyze_dependencies_with_llm(endpoints_info, api_spec)
            self.dependencies = llm_analysis.get('dependencies', [])
            self.workflows = llm_analysis.get('workflows', [])
        
        # Step 3: Infer additional dependencies from patterns
        pattern_dependencies = self._infer_dependencies_from_patterns(endpoints_info)
        self.dependencies.extend(pattern_dependencies)
        
        return {
            'dependencies': self.dependencies,
            'workflows': self.workflows,
            'endpoint_groups': self._group_endpoints_by_resource(endpoints_info)
        }
    
    def _extract_endpoints_info(self, api_spec: Any) -> List[Dict[str, Any]]:
        """Extract structured information about endpoints."""
        endpoints_info = []
        
        for endpoint in api_spec.endpoints:
            # Extract parameters with examples
            parameters = []
            for param in endpoint.parameters:
                param_info = {
                    'name': param.get('name'),
                    'type': param.get('schema', {}).get('type', 'string'),
                    'required': param.get('required', False),
                    'location': param.get('in', 'query'),
                    'example': param.get('schema', {}).get('example'),
                    'description': param.get('description', '')
                }
                parameters.append(param_info)
            
            # Extract response schemas
            responses = {}
            for status_code, response in endpoint.responses.items():
                if status_code in ['200', '201', '202']:
                    responses[status_code] = {
                        'description': response.get('description', ''),
                        'schema': response.get('content', {})
                    }
            
            endpoint_info = {
                'path': endpoint.path,
                'method': endpoint.method,
                'summary': endpoint.summary,
                'description': endpoint.description,
                'operation_id': endpoint.operation_id,
                'parameters': parameters,
                'responses': responses,
                'tags': endpoint.tags
            }
            endpoints_info.append(endpoint_info)
        
        return endpoints_info
    
    async def _analyze_dependencies_with_llm(
        self, 
        endpoints_info: List[Dict[str, Any]], 
        api_spec: Any
    ) -> Dict[str, Any]:
        """Use LLM to analyze endpoint dependencies and generate workflows."""
        
        # Format endpoints for LLM analysis
        endpoints_text = self._format_endpoints_for_llm(endpoints_info)
        
        prompt = f"""Analyze the following API endpoints to understand their dependencies and generate realistic test workflows.

API: {api_spec.title} v{api_spec.version}
Description: {api_spec.description or 'No description provided'}

Endpoints:
{endpoints_text}

Please analyze and provide:

1. **Dependencies**: Identify which endpoints depend on others (e.g., GET /users/{{id}} requires POST /users to create the user first)

2. **Workflows**: Create realistic test workflows that demonstrate proper API usage

Consider these dependency types:
- **creates**: Endpoint creates a resource that others can reference
- **requires**: Endpoint needs a resource to exist (created by another endpoint)
- **modifies**: Endpoint modifies an existing resource
- **deletes**: Endpoint removes a resource

For each dependency, identify:
- Source endpoint (creates/provides the resource)
- Target endpoint (requires/uses the resource)
- Parameter mapping (how response data maps to request parameters)

For workflows, create realistic scenarios like:
- Create → Read → Update → Delete (CRUD)
- Setup data → Execute operations → Cleanup
- Multi-step business processes

Return your analysis in this JSON format:
{{
    "dependencies": [
        {{
            "source_endpoint": "/users",
            "source_method": "POST",
            "target_endpoint": "/users/{{id}}",
            "target_method": "GET",
            "dependency_type": "creates",
            "parameter_mapping": {{"id": "id"}},
            "description": "POST /users creates a user that can be retrieved by GET /users/{{id}}"
        }}
    ],
    "workflows": [
        {{
            "name": "User CRUD Workflow",
            "description": "Complete user lifecycle: create, read, update, delete",
            "steps": [
                {{
                    "step": 1,
                    "endpoint": "/users",
                    "method": "POST",
                    "description": "Create a new user",
                    "test_data": {{"name": "John Doe", "email": "john@example.com"}},
                    "expected_status": 201,
                    "extract_data": {{"user_id": "id"}}
                }},
                {{
                    "step": 2,
                    "endpoint": "/users/{{user_id}}",
                    "method": "GET",
                    "description": "Retrieve the created user",
                    "expected_status": 200,
                    "validate_data": {{"name": "John Doe"}}
                }}
            ],
            "setup_data": {{}}
        }}
    ]
}}

Focus on realistic API usage patterns. If this is a REST API, follow REST conventions. If endpoints use specific business logic, respect that in the workflows."""

        try:
            response = await self.openrouter_client.generate_text(
                prompt=prompt,
                model="openai/gpt-4o",
                max_tokens=4000,
                temperature=0.1
            )
            
            # Parse JSON response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                analysis = json.loads(json_str)
                
                # Convert to internal objects
                dependencies = []
                for dep_data in analysis.get('dependencies', []):
                    dependency = EndpointDependency(
                        source_endpoint=dep_data.get('source_endpoint'),
                        source_method=dep_data.get('source_method'),
                        target_endpoint=dep_data.get('target_endpoint'),
                        target_method=dep_data.get('target_method'),
                        dependency_type=dep_data.get('dependency_type'),
                        parameter_mapping=dep_data.get('parameter_mapping', {}),
                        description=dep_data.get('description', '')
                    )
                    dependencies.append(dependency)
                
                workflows = []
                for workflow_data in analysis.get('workflows', []):
                    workflow = APIWorkflow(
                        name=workflow_data.get('name'),
                        description=workflow_data.get('description'),
                        steps=workflow_data.get('steps', []),
                        setup_data=workflow_data.get('setup_data', {})
                    )
                    workflows.append(workflow)
                
                return {
                    'dependencies': dependencies,
                    'workflows': workflows
                }
        
        except Exception as e:
            print(f"LLM dependency analysis failed: {e}")
        
        return {'dependencies': [], 'workflows': []}
    
    def _format_endpoints_for_llm(self, endpoints_info: List[Dict[str, Any]]) -> str:
        """Format endpoints information for LLM consumption."""
        formatted_endpoints = []
        
        for endpoint in endpoints_info:
            endpoint_text = f"{endpoint['method']} {endpoint['path']}"
            
            if endpoint['summary']:
                endpoint_text += f" - {endpoint['summary']}"
            
            if endpoint['parameters']:
                params = []
                for param in endpoint['parameters']:
                    param_str = f"{param['name']} ({param['type']})"
                    if param['required']:
                        param_str += " [required]"
                    if param['example']:
                        param_str += f" example: {param['example']}"
                    params.append(param_str)
                endpoint_text += f"\n  Parameters: {', '.join(params)}"
            
            if endpoint['responses']:
                responses = []
                for status, response in endpoint['responses'].items():
                    responses.append(f"{status}: {response['description']}")
                endpoint_text += f"\n  Responses: {', '.join(responses)}"
            
            formatted_endpoints.append(endpoint_text)
        
        return "\n\n".join(formatted_endpoints)
    
    def _infer_dependencies_from_patterns(
        self, 
        endpoints_info: List[Dict[str, Any]]
    ) -> List[EndpointDependency]:
        """Infer dependencies based on common REST patterns."""
        dependencies = []
        
        # Group endpoints by resource (based on path patterns)
        resource_groups = self._group_endpoints_by_resource(endpoints_info)
        
        for resource, endpoints in resource_groups.items():
            # Find CRUD patterns
            post_endpoint = None
            get_endpoints = []
            put_endpoints = []
            delete_endpoints = []
            
            for endpoint in endpoints:
                if endpoint['method'] == 'POST':
                    post_endpoint = endpoint
                elif endpoint['method'] == 'GET':
                    get_endpoints.append(endpoint)
                elif endpoint['method'] in ['PUT', 'PATCH']:
                    put_endpoints.append(endpoint)
                elif endpoint['method'] == 'DELETE':
                    delete_endpoints.append(endpoint)
            
            # POST creates resources that GET/PUT/DELETE can use
            if post_endpoint:
                for get_endpoint in get_endpoints:
                    if '{' in get_endpoint['path']:  # Parameterized path
                        dependency = EndpointDependency(
                            source_endpoint=post_endpoint['path'],
                            source_method=post_endpoint['method'],
                            target_endpoint=get_endpoint['path'],
                            target_method=get_endpoint['method'],
                            dependency_type='creates',
                            parameter_mapping={'id': 'id'},  # Common pattern
                            description=f"POST {post_endpoint['path']} creates resource for GET {get_endpoint['path']}"
                        )
                        dependencies.append(dependency)
                
                for put_endpoint in put_endpoints:
                    if '{' in put_endpoint['path']:
                        dependency = EndpointDependency(
                            source_endpoint=post_endpoint['path'],
                            source_method=post_endpoint['method'],
                            target_endpoint=put_endpoint['path'],
                            target_method=put_endpoint['method'],
                            dependency_type='creates',
                            parameter_mapping={'id': 'id'},
                            description=f"POST {post_endpoint['path']} creates resource for PUT {put_endpoint['path']}"
                        )
                        dependencies.append(dependency)
                
                for delete_endpoint in delete_endpoints:
                    if '{' in delete_endpoint['path']:
                        dependency = EndpointDependency(
                            source_endpoint=post_endpoint['path'],
                            source_method=post_endpoint['method'],
                            target_endpoint=delete_endpoint['path'],
                            target_method=delete_endpoint['method'],
                            dependency_type='creates',
                            parameter_mapping={'id': 'id'},
                            description=f"POST {post_endpoint['path']} creates resource for DELETE {delete_endpoint['path']}"
                        )
                        dependencies.append(dependency)
        
        return dependencies
    
    def _group_endpoints_by_resource(
        self, 
        endpoints_info: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group endpoints by resource based on path patterns."""
        resource_groups = {}
        
        for endpoint in endpoints_info:
            # Extract resource name from path
            path_parts = endpoint['path'].strip('/').split('/')
            if path_parts:
                # Use first path segment as resource name
                resource = path_parts[0]
                # Remove parameter placeholders
                resource = resource.split('{')[0].rstrip('/')
                
                if resource not in resource_groups:
                    resource_groups[resource] = []
                resource_groups[resource].append(endpoint)
        
        return resource_groups
    
    def generate_workflow_scenarios(self, workflows: List[APIWorkflow]) -> List[TestScenario]:
        """Generate test scenarios based on analyzed workflows."""
        scenarios = []
        
        for workflow in workflows:
            # Create a test scenario for each workflow step
            for i, step in enumerate(workflow.steps):
                scenario_name = f"test_{workflow.name.lower().replace(' ', '_')}_step_{step['step']}"
                
                scenario = TestScenario(
                    name=scenario_name,
                    description=f"{workflow.description} - {step['description']}",
                    endpoint=step['endpoint'],
                    method=step['method'],
                    parameters=step.get('test_data', {}),
                    expected_status=step.get('expected_status', 200),
                    is_negative_test=False,
                    test_data=step.get('test_data'),
                    workflow_step=step['step'],
                    workflow_name=workflow.name,
                    depends_on_previous_step=i > 0
                )
                scenarios.append(scenario)
        
        return scenarios

