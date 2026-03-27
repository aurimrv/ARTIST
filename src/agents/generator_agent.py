"""
Generator Agent for creating JUnit 4 test code with Rest Assured.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent
from ..config.models import AgentConfig, SystemConfig, TestScenario, ProjectContext
from ..templates import MavenProjectTemplate
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
        self.maven_template = MavenProjectTemplate()  # Still needed for project structure
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
            self.log_progress("Creating Maven project structure", 1, 3)
            project_dir = await self._create_maven_project(context)
            
            if not project_dir:
                return {
                    'success': False,
                    'error': "Failed to create Maven project structure",
                    'generated_files': []
                }
            
            # Step 2: Generate test classes directly with LLM
            self.log_progress("Generating test classes with LLM", 2, 3)
            if context.split_by_endpoint:
                # In split mode, coordinator handles per-group generation;
                # here we just call the normal path which now groups by endpoint.
                generated_files = await self._generate_test_classes_with_llm(context, scenarios)
            else:
                generated_files = await self._generate_test_classes_with_llm(context, scenarios)

            if not generated_files:
                return {
                    'success': False,
                    'error': "Failed to generate test classes with LLM",
                    'generated_files': []
                }
            
            # Step 3: Validate generated code
            self.log_progress("Validating generated code", 3, 3)
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
    
    async def _generate_test_classes_with_llm(
        self, 
        context: ProjectContext, 
        scenarios: List[TestScenario]
    ) -> List[Path]:
        """
        Generate test classes directly using LLM from scenarios.
        
        Args:
            context: Project context
            scenarios: List of test scenarios from planner_agent
        
        Returns:
            List of generated file paths
        """
        generated_files = []
        
        try:
            if not self.openrouter_client:
                self.logger.error("OpenRouter client not available - cannot generate tests with LLM")
                return []
            
            # Group scenarios by test class (for now, put all in main test class)
            test_classes = self._group_scenarios_by_class(scenarios, context)
            
            for class_name, class_scenarios in test_classes.items():
                self.logger.info(f"Generating test class with LLM: {class_name}")
                
                # Generate test class content directly with LLM
                test_content = await self._generate_single_test_class_with_llm(
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
                else:
                    self.logger.error(f"Failed to generate test class {class_name} with LLM")
            
            return generated_files
            
        except Exception as e:
            self.log_error("Failed to generate test classes with LLM", e)
            return []
    
    def _group_scenarios_by_class(
        self, 
        scenarios: List[TestScenario], 
        context: ProjectContext
    ) -> Dict[str, List[TestScenario]]:
        """
        Group scenarios by test class.
        When split_by_endpoint is True, groups by endpoint.
        Otherwise, puts all in the main test class.
        """
        if context.split_by_endpoint:
            return self._group_scenarios_by_endpoint(scenarios, context)
        return {context.main_test_class_name: scenarios}

    def _group_scenarios_by_endpoint(
        self,
        scenarios: List[TestScenario],
        context: ProjectContext
    ) -> Dict[str, List[TestScenario]]:
        """
        Group scenarios by endpoint, normalizing endpoints against the OpenAPI spec.

        Returns:
            OrderedDict mapping class names to lists of scenarios, preserving insertion order.
        """
        from collections import OrderedDict
        import re

        # Load spec endpoints for normalization
        spec_endpoints: List[str] = self._load_spec_endpoints(context)

        groups: Dict[str, List[TestScenario]] = OrderedDict()
        for scenario in scenarios:
            normalized = self._normalize_endpoint(scenario.endpoint, spec_endpoints)
            class_name = self._endpoint_to_class_name(normalized)
            groups.setdefault(class_name, []).append(scenario)

        return groups

    def _load_spec_endpoints(self, context: ProjectContext) -> List[str]:
        """Load path keys from the OpenAPI spec."""
        try:
            import json
            spec_path = context.api_spec_path
            if spec_path and spec_path.exists():
                with open(spec_path, 'r', encoding='utf-8') as f:
                    spec = json.load(f)
                return list(spec.get('paths', {}).keys())
        except Exception as e:
            self.logger.warning(f"Could not load spec endpoints for normalization: {e}")
        return []

    def _normalize_endpoint(self, endpoint: str, spec_endpoints: List[str]) -> str:
        """
        Normalize an endpoint against the OpenAPI spec.

        Step 1: Try structural match against spec endpoints (same number of fixed
                segments in same positions). Use the spec version if found.
        Step 2: Otherwise, replace concrete-looking segments with {param}.
        """
        import re

        def segments(path: str) -> List[str]:
            return [s for s in path.split('/') if s]

        endpoint_segs = segments(endpoint)
        n = len(endpoint_segs)

        # Build set of all fixed segment values used anywhere in spec
        all_fixed_spec_segs: set = set()
        for sp in spec_endpoints:
            for seg in segments(sp):
                if not (seg.startswith('{') and seg.endswith('}')):
                    all_fixed_spec_segs.add(seg)

        # Step 1: structural match
        for spec_ep in spec_endpoints:
            spec_segs = segments(spec_ep)
            if len(spec_segs) != n:
                continue
            match = True
            for s_seg, e_seg in zip(spec_segs, endpoint_segs):
                is_spec_param = s_seg.startswith('{') and s_seg.endswith('}')
                if not is_spec_param:
                    # Fixed spec segment must match concrete endpoint segment
                    if s_seg != e_seg:
                        match = False
                        break
                # param segments can match anything
            if match:
                return spec_ep

        # Step 2: substitute concrete segments that don't appear as fixed spec segments
        normalized_segs = []
        for seg in endpoint_segs:
            if seg.startswith('{') and seg.endswith('}'):
                normalized_segs.append(seg)
            elif seg in all_fixed_spec_segs:
                normalized_segs.append(seg)
            else:
                # Looks like a concrete value — replace with {param}
                normalized_segs.append('{param}')
        return '/' + '/'.join(normalized_segs)

    @staticmethod
    def _endpoint_to_class_name(endpoint: str) -> str:
        """
        Convert a normalized endpoint path to a Java test class name.

        Rules:
          - Remove all {param} segments
          - Split by '/', discard empty segments
          - CamelCase each remaining segment
          - Concatenate + 'Test' suffix
          - Special case: '/' or empty → 'RootTest'
        """
        import re

        segs = [s for s in endpoint.split('/') if s and not (s.startswith('{') and s.endswith('}'))]
        if not segs:
            return 'RootTest'

        def to_camel(seg: str) -> str:
            # Split on non-alphanumeric and capitalize each part
            parts = re.split(r'[^a-zA-Z0-9]+', seg)
            return ''.join(p.capitalize() for p in parts if p)

        return ''.join(to_camel(s) for s in segs) + 'Test'

    
    async def _generate_single_test_class_with_llm(
        self,
        context: ProjectContext,
        class_name: str,
        scenarios: List[TestScenario],
        focused: bool = False
    ) -> Optional[str]:
        """
        Generate a single test class directly using LLM.
        
        Args:
            context: Project context
            class_name: Name of the test class
            scenarios: Scenarios for this class
            focused: If True, generate ONLY the listed scenarios without extra expansion
                     (used in split_by_endpoint mode to avoid truncation)
        
        Returns:
            Generated test class content or None if generation fails
        """
        try:
            # Prepare contexts for LLM using centralized formatting
            # In focused/split mode, use a compact format that does NOT encourage expansion
            if focused:
                scenarios_context = self._format_scenarios_for_llm_focused(scenarios)
            else:
                scenarios_context = self._format_scenarios_for_llm(scenarios)
            openapi_context = self._format_openapi_context_for_llm(context)
            
            # Prepare project context as dictionary
            project_context_dict = {
                'package_name': context.package_name,
                'class_name': class_name,
                'base_url': context.base_url,
                'output_dir': str(context.output_dir)
            }

            self.logger.info(f"Generator MAX_TOKENS: {self.get_max_tokens()} focused={focused}")

            # Use centralized method from openrouter_client with full context
            if focused:
                test_content = await self.openrouter_client.generate_test_code_focused(
                    scenarios_context=scenarios_context,
                    project_context=project_context_dict,
                    openapi_context=openapi_context,
                    model=self.get_model_name(),
                    max_tokens=self.get_max_tokens(),
                    temperature=self.get_temperature(),
                    seed=self.get_seed()
                )
            else:
                test_content = await self.openrouter_client.generate_test_code_with_full_context(
                    scenarios_context=scenarios_context,
                    project_context=project_context_dict,
                    openapi_context=openapi_context,
                    model=self.get_model_name(),
                    max_tokens=self.get_max_tokens(),
                    temperature=self.get_temperature(),
                    seed=self.get_seed()
                )

            print(f"#### generator simple_test_class test_content:{test_content}")

            # Sanitize LLM output to remove commentary and extract only code
            if test_content:
                self.logger.info(f"Sanitizing LLM output for {class_name}")
                test_content = self.code_sanitizer.sanitize_java_code(test_content)
            
            # Validate generated content
            if test_content and self._is_valid_java_code(test_content):
                self.logger.info(f"Successfully generated test class {class_name} with LLM")
                return test_content
            else:
                self.logger.error(f"LLM generated invalid Java code for {class_name}")
                return None
            
        except Exception as e:
            self.log_error(f"Failed to generate test class {class_name} with LLM", e)
            return None
    
    def _format_scenarios_for_llm(self, scenarios: List[TestScenario]) -> str:
        """Format test scenarios for LLM consumption with explicit coverage requirements."""
        total = len(scenarios)
        positive = sum(1 for s in scenarios if not s.is_negative_test)
        negative = sum(1 for s in scenarios if s.is_negative_test)

        scenarios_text = (
            f"MANDATORY TEST COVERAGE REQUIREMENT:\n"
            f"You MUST generate AT LEAST {total} @Test methods in total.\n"
            f"There are {total} scenarios below ({positive} positive, {negative} negative).\n"
            f"Each scenario MUST produce at least one dedicated @Test method.\n"
            f"You are STRONGLY ENCOURAGED to generate MORE than {total} @Test methods by:\n"
            f"  - Adding boundary-value tests (min, max, zero, empty, null) for each parameter\n"
            f"  - Adding data-type validation tests (non-numeric, special characters, very long strings)\n"
            f"  - Adding combined-parameter tests where multiple parameters interact\n"
            f"  - Splitting complex scenarios into multiple focused test methods\n"
            f"NEVER merge, skip, or omit any of the {total} scenarios listed below.\n\n"
            f"Test Scenarios ({total} total):\n\n"
        )

        for i, scenario in enumerate(scenarios, 1):
            scenarios_text += f"Scenario {i}/{total}:\n"
            scenarios_text += f"- Name: {scenario.name}\n"
            scenarios_text += f"- Description: {scenario.description}\n"
            scenarios_text += f"- Method: {scenario.method}\n"
            scenarios_text += f"- Endpoint: {scenario.endpoint}\n"
            scenarios_text += f"- Expected Status: {scenario.expected_status}\n"
            scenarios_text += f"- Is Negative Test: {scenario.is_negative_test}\n"

            if scenario.parameters:
                scenarios_text += f"- Parameters: {scenario.parameters}\n"

            if scenario.test_data:
                scenarios_text += f"- Test Data: {scenario.test_data}\n"

            scenarios_text += "\n"

        scenarios_text += (
            f"FINAL REMINDER: The generated class MUST contain at least {total} @Test methods "
            f"(one per scenario above). Aim for significantly more by exploring boundary values "
            f"and parameter combinations for each endpoint.\n"
        )

        return scenarios_text

    def _format_scenarios_for_llm_focused(self, scenarios: List[TestScenario]) -> str:
        """
        Format test scenarios for focused (split_by_endpoint) generation.
        In this mode we do NOT encourage the LLM to expand beyond the listed scenarios,
        because each group is small and expansion causes token-limit truncation.
        Generate EXACTLY the listed scenarios — one @Test method per scenario.
        Extra tests are allowed only if they are minimal and do not risk truncation.
        """
        total = len(scenarios)
        positive = sum(1 for s in scenarios if not s.is_negative_test)
        negative = sum(1 for s in scenarios if s.is_negative_test)

        scenarios_text = (
            f"TEST COVERAGE REQUIREMENT:\n"
            f"Generate exactly {total} @Test methods — one per scenario listed below.\n"
            f"There are {total} scenarios ({positive} positive, {negative} negative).\n"
            f"Each scenario MUST have its own dedicated @Test method.\n"
            f"Do NOT add extra boundary/edge-case tests beyond what is listed — "
            f"keep the class small to avoid output truncation.\n"
            f"NEVER merge, skip, or omit any of the {total} scenarios listed below.\n\n"
            f"Test Scenarios ({total} total):\n\n"
        )

        for i, scenario in enumerate(scenarios, 1):
            scenarios_text += f"Scenario {i}/{total}:\n"
            scenarios_text += f"- Name: {scenario.name}\n"
            scenarios_text += f"- Description: {scenario.description}\n"
            scenarios_text += f"- Method: {scenario.method}\n"
            scenarios_text += f"- Endpoint: {scenario.endpoint}\n"
            scenarios_text += f"- Expected Status: {scenario.expected_status}\n"
            scenarios_text += f"- Is Negative Test: {scenario.is_negative_test}\n"

            if scenario.parameters:
                scenarios_text += f"- Parameters: {scenario.parameters}\n"

            if scenario.test_data:
                scenarios_text += f"- Test Data: {scenario.test_data}\n"

            scenarios_text += "\n"

        scenarios_text += (
            f"FINAL REMINDER: Generate exactly {total} @Test methods — one per scenario. "
            f"Do NOT add more. Keep the class concise and complete.\n"
        )

        return scenarios_text


    def _format_openapi_context_for_llm(self, context: ProjectContext) -> str:
        """
        Format OpenAPI specification context for LLM consumption.

        In addition to content-type and schema information, this method now
        extracts all example values declared in the specification:

        * ``param.example`` / ``param.examples[*].value``
        * ``param.x-parameter-examples``
        * ``requestBody.content[*].examples[*].value``
        * ``responses[status].content[*].examples[*].value``

        These examples are injected into the prompt so the LLM can use
        real, spec-provided values when generating test assertions and
        request payloads.
        """
        try:
            # Try to access OpenAPI specification from context
            if hasattr(context, 'api_spec_path') and context.api_spec_path:
                from pathlib import Path
                import json
                
                spec_path = Path(context.api_spec_path)
                if spec_path.exists():
                    with open(spec_path, 'r', encoding='utf-8') as f:
                        api_spec = json.load(f)
                    
                    # Extract relevant information from OpenAPI spec
                    openapi_context = "OpenAPI Specification Context:\n\n"
                    
                    # Basic API info
                    if 'info' in api_spec:
                        info = api_spec['info']
                        openapi_context += f"API Title: {info.get('title', 'Unknown')}\n"
                        openapi_context += f"API Version: {info.get('version', 'Unknown')}\n"
                        if 'description' in info:
                            openapi_context += f"API Description: {info['description']}\n"
                    
                    # Global consumes/produces (OpenAPI 2.0)
                    global_consumes = api_spec.get('consumes', [])
                    global_produces = api_spec.get('produces', [])
                    
                    if global_consumes:
                        openapi_context += f"\nGlobal Consumes (Request Content-Types): {', '.join(global_consumes)}\n"
                    if global_produces:
                        openapi_context += f"Global Produces (Response Content-Types): {', '.join(global_produces)}\n"
                    
                    # Paths and operations
                    if 'paths' in api_spec:
                        openapi_context += "\nAPI Endpoints and Content Type Information:\n"
                        for path, methods in api_spec['paths'].items():
                            openapi_context += f"\nPath: {path}\n"
                            for method, operation in methods.items():
                                if isinstance(operation, dict):
                                    openapi_context += f"  {method.upper()}:\n"
                                    
                                    # Operation-specific consumes/produces (OpenAPI 2.0)
                                    operation_consumes = operation.get('consumes', global_consumes)
                                    operation_produces = operation.get('produces', global_produces)
                                    
                                    if operation_consumes:
                                        openapi_context += f"    Consumes (Request Content-Types): {', '.join(operation_consumes)}\n"
                                    if operation_produces:
                                        openapi_context += f"    Produces (Response Content-Types): {', '.join(operation_produces)}\n"
                                    
                                    # Request body (OpenAPI 3.0)
                                    if 'requestBody' in operation:
                                        request_body = operation['requestBody']
                                        openapi_context += "    Request Body:\n"
                                        if 'content' in request_body:
                                            for content_type, content in request_body['content'].items():
                                                openapi_context += f"      Content-Type: {content_type}\n"
                                                if 'schema' in content:
                                                    schema_info = self._format_schema_info(content['schema'])
                                                    openapi_context += f"        Schema: {schema_info}\n"
                                        required = request_body.get('required', False)
                                        openapi_context += f"      Required: {required}\n"
                                    
                                    # Parameters (with examples)
                                    if 'parameters' in operation:
                                        openapi_context += "    Parameters:\n"
                                        for param in operation['parameters']:
                                            param_name = param.get('name', 'unknown')
                                            param_type = param.get('type', param.get('schema', {}).get('type', 'unknown'))
                                            param_required = param.get('required', False)
                                            param_in = param.get('in', 'unknown')
                                            openapi_context += f"      - {param_name} ({param_type}) in {param_in} {'[required]' if param_required else '[optional]'}"
                                            # Collect all available examples for this parameter
                                            param_examples = self._collect_param_examples(param)
                                            if param_examples:
                                                openapi_context += f" [examples: {param_examples}]"
                                            openapi_context += "\n"

                                    # Request body examples
                                    if 'requestBody' in operation:
                                        rb_examples = self._collect_request_body_examples(operation['requestBody'])
                                        if rb_examples:
                                            import json as _json
                                            openapi_context += "    Request Body Examples:\n"
                                            for ex in rb_examples[:2]:
                                                ex_str = _json.dumps(ex, ensure_ascii=False)
                                                if len(ex_str) > 400:
                                                    ex_str = ex_str[:400] + '...'
                                                openapi_context += f"      {ex_str}\n"
                                    
                                    # Responses
                                    if 'responses' in operation:
                                        openapi_context += "    Responses:\n"
                                        for status_code, response in operation['responses'].items():
                                            openapi_context += f"      {status_code}: {response.get('description', 'No description')}\n"

                                            # Response content (OpenAPI 3.0)
                                            if 'content' in response:
                                                for content_type, content in response['content'].items():
                                                    openapi_context += f"        Content-Type: {content_type}\n"
                                                    if 'schema' in content:
                                                        schema = content['schema']
                                                        openapi_context += f"        Schema: {self._format_schema_info(schema)}\n"
                                                    # Response body examples
                                                    resp_examples = self._collect_media_examples(content)
                                                    if resp_examples:
                                                        import json as _json
                                                        openapi_context += f"        Response Examples ({status_code}):\n"
                                                        for ex in resp_examples[:1]:
                                                            ex_str = _json.dumps(ex, ensure_ascii=False)
                                                            if len(ex_str) > 400:
                                                                ex_str = ex_str[:400] + '...'
                                                            openapi_context += f"          {ex_str}\n"

                                            # Response headers
                                            if 'headers' in response:
                                                openapi_context += "        Headers:\n"
                                                for header_name, header_spec in response['headers'].items():
                                                    header_type = header_spec.get('type', header_spec.get('schema', {}).get('type', 'string'))
                                                    openapi_context += f"          {header_name}: {header_type}\n"
                    
                    # Components/schemas
                    if 'components' in api_spec and 'schemas' in api_spec['components']:
                        openapi_context += "\nData Models:\n"
                        for schema_name, schema in api_spec['components']['schemas'].items():
                            openapi_context += f"  {schema_name}: {self._format_schema_info(schema)}\n"
                    
                    # Definitions (OpenAPI 2.0)
                    elif 'definitions' in api_spec:
                        openapi_context += "\nData Models:\n"
                        for schema_name, schema in api_spec['definitions'].items():
                            openapi_context += f"  {schema_name}: {self._format_schema_info(schema)}\n"
                    
                    openapi_context += "\nIMPORTANT CONTENT-TYPE GUIDELINES:\n"
                    openapi_context += "- Use the correct Content-Type headers for requests based on 'consumes' or 'requestBody.content'\n"
                    openapi_context += "- Expect the correct Content-Type in responses based on 'produces' or 'responses.content'\n"
                    openapi_context += "- For JSON APIs, typically use 'application/json' for both request and response\n"
                    openapi_context += "- For form data, use 'application/x-www-form-urlencoded' or 'multipart/form-data'\n"
                    openapi_context += "- Always validate response Content-Type matches expected values\n"
                    openapi_context += "- Do NOT assume fields like 'id' exist unless specified in the response schema\n"
                    openapi_context += "\nIMPORTANT EXAMPLES USAGE GUIDELINES:\n"
                    openapi_context += "- When a parameter has [examples: ...] listed above, USE those exact values in your test methods.\n"
                    openapi_context += "- When multiple example values are listed for a parameter, create separate @Test methods\n"
                    openapi_context += "  for each distinct value to maximise input coverage.\n"
                    openapi_context += "- When 'Request Body Examples' are provided, use them as the request payload in your tests.\n"
                    openapi_context += "- When 'Response Examples' are provided, use them to build body assertions (e.g. body(\"field\", equalTo(\"value\"))).\n"
                    openapi_context += "- Prefer spec-provided examples over invented test data at all times.\n"
                    
                    return openapi_context
                else:
                    self.logger.warning(f"OpenAPI specification file not found: {spec_path}")
            
            return "OpenAPI Specification: Not available - use careful response validation and standard Content-Types in tests.\n"
            
        except Exception as e:
            self.logger.warning(f"Failed to load OpenAPI specification: {e}")
            return "OpenAPI Specification: Failed to load - use careful response validation and standard Content-Types in tests.\n"

    # ------------------------------------------------------------------
    # Example collection helpers (used by _format_openapi_context_for_llm)
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_param_examples(param: dict) -> list:
        """
        Collect all example values for a single parameter object.

        Sources (in order):
        1. ``param.example``
        2. ``param.examples[*].value``  (OpenAPI 3.x Example Objects)
        3. ``param.x-parameter-examples``  (custom extension)
        4. ``param.schema.example``
        5. ``param.schema.examples``  (JSON Schema array)
        """
        examples: list = []
        seen: set = set()

        def _add(val):
            if val is None:
                return
            key = repr(val)
            if key not in seen:
                seen.add(key)
                examples.append(val)

        if 'example' in param:
            _add(param['example'])

        for ex_obj in param.get('examples', {}).values():
            if isinstance(ex_obj, dict) and 'value' in ex_obj:
                _add(ex_obj['value'])
            elif not isinstance(ex_obj, dict):
                _add(ex_obj)

        x_examples = param.get('x-parameter-examples')
        if x_examples is not None:
            if isinstance(x_examples, list):
                for v in x_examples:
                    _add(v)
            elif isinstance(x_examples, dict):
                for ex_obj in x_examples.values():
                    if isinstance(ex_obj, dict) and 'value' in ex_obj:
                        _add(ex_obj['value'])
                    else:
                        _add(ex_obj)
            else:
                _add(x_examples)

        schema = param.get('schema', {})
        if isinstance(schema, dict):
            if 'example' in schema:
                _add(schema['example'])
            for v in schema.get('examples', []):
                _add(v)

        return examples

    @staticmethod
    def _collect_media_examples(media_obj: dict) -> list:
        """
        Collect example values from a media-type object
        (``requestBody.content[mediaType]`` or ``responses[status].content[mediaType]``).
        """
        examples: list = []
        seen: set = set()

        def _add(val):
            if val is None:
                return
            key = repr(val)[:200]
            if key not in seen:
                seen.add(key)
                examples.append(val)

        for ex_obj in media_obj.get('examples', {}).values():
            if isinstance(ex_obj, dict) and 'value' in ex_obj:
                _add(ex_obj['value'])
            elif not isinstance(ex_obj, dict):
                _add(ex_obj)

        if 'example' in media_obj:
            _add(media_obj['example'])

        return examples

    def _collect_request_body_examples(self, request_body: dict) -> list:
        """Collect all examples from a requestBody object."""
        examples: list = []
        for media_obj in request_body.get('content', {}).values():
            if isinstance(media_obj, dict):
                examples.extend(self._collect_media_examples(media_obj))
        return examples

    # ------------------------------------------------------------------

    def _format_schema_info(self, schema: dict) -> str:
        """Format schema information for LLM context."""
        if not isinstance(schema, dict):
            return str(schema)
        
        schema_info = ""
        
        if 'type' in schema:
            schema_info += f"type: {schema['type']}"
        
        if 'properties' in schema:
            properties = []
            for prop_name, prop_schema in schema['properties'].items():
                prop_type = prop_schema.get('type', 'unknown')
                properties.append(f"{prop_name}({prop_type})")
            schema_info += f" properties: [{', '.join(properties)}]"
        
        if 'items' in schema:
            items_info = self._format_schema_info(schema['items'])
            schema_info += f" items: {items_info}"
        
        return schema_info if schema_info else "unknown schema"

    # ------------------------------------------------------------------
    # HTTP 500 Test Generation (Mockito + Jersey)
    # ------------------------------------------------------------------

    async def generate_test500_classes(
        self,
        context: ProjectContext
    ) -> List[Path]:
        """
        Detect all endpoints in the OpenAPI spec that document a 500 response,
        then generate one *Test500.java file per test-class group using
        Mockito + Jersey Test Framework.

        The generated files are placed alongside the regular test classes in
        the same Maven project directory.  Their names follow the same
        endpoint-to-class-name convention used for regular tests, but with
        the suffix '500' inserted before '.java'.

        For example, if the regular class is ``V1AlphaTest``, the 500 class
        will be ``V1AlphaTest500``.

        Args:
            context: Project context (must have api_spec_path set)

        Returns:
            List of generated file paths (may be empty if no 500 endpoints found)
        """
        if not self.openrouter_client:
            self.logger.warning("OpenRouter client not available — skipping Test500 generation")
            return []

        endpoints_by_class = self._collect_500_endpoints_by_class(context)
        if not endpoints_by_class:
            self.logger.info("No endpoints with documented HTTP 500 found — skipping Test500 generation")
            return []

        generated_files: List[Path] = []
        openapi_context = self._format_openapi_context_for_llm(context)

        for class_name, endpoints in endpoints_by_class.items():
            class_name_500 = class_name.replace('Test', 'Test500') if 'Test' in class_name else class_name + '500'
            self.logger.info(f"Generating Test500 class: {class_name_500} ({len(endpoints)} endpoints)")

            project_context_dict = {
                'package_name': context.package_name,
                'class_name': class_name_500,
                'base_url': context.base_url,
            }

            try:
                test_content = await self.openrouter_client.generate_test500_code(
                    endpoints_500=endpoints,
                    project_context=project_context_dict,
                    openapi_context=openapi_context,
                    model=self.get_model_name(),
                    max_tokens=self.get_max_tokens(),
                    temperature=self.get_temperature(),
                    seed=self.get_seed()
                )

                if test_content:
                    test_content = self.code_sanitizer.sanitize_java_code(test_content)

                if test_content and self._is_valid_java_code_500(test_content):
                    self.maven_template.add_test_class(
                        context.maven_project_dir,
                        context.package_name,
                        class_name_500,
                        test_content
                    )
                    file_path = self.maven_template.get_test_class_path(
                        context.maven_project_dir, context.package_name, class_name_500
                    )
                    generated_files.append(file_path)
                    self.logger.info(f"Generated Test500 class: {file_path}")
                else:
                    self.logger.error(f"LLM generated invalid Java code for {class_name_500}")

            except Exception as e:
                self.log_error(f"Failed to generate Test500 class {class_name_500}", e)

        return generated_files

    def _collect_500_endpoints_by_class(
        self,
        context: ProjectContext
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Parse the OpenAPI spec and return a mapping of test-class-name to
        a list of endpoint descriptors for endpoints that document HTTP 500.

        Each endpoint descriptor is a dict with keys:
          path, method, resource_class, service_class, service_method,
          path_params, query_params, operation_id
        """
        import json
        import re
        from collections import OrderedDict

        result: Dict[str, List[Dict[str, Any]]] = OrderedDict()

        try:
            spec_path = context.api_spec_path
            if not spec_path or not spec_path.exists():
                self.logger.warning("api_spec_path not set or file not found — cannot detect 500 endpoints")
                return result

            with open(spec_path, 'r', encoding='utf-8') as f:
                spec = json.load(f)

            spec_endpoints = list(spec.get('paths', {}).keys())

            for path, methods in spec.get('paths', {}).items():
                for method, operation in methods.items():
                    if not isinstance(operation, dict):
                        continue
                    responses = operation.get('responses', {})
                    if '500' not in responses and 500 not in responses:
                        continue

                    # Derive class names from the endpoint path
                    normalized = self._normalize_endpoint(path, spec_endpoints)
                    class_name = self._endpoint_to_class_name(normalized)

                    # Infer resource/service class names from operationId or path
                    operation_id = operation.get('operationId', '')
                    resource_class = self._infer_resource_class(path, operation_id, context.package_name)
                    service_class = self._infer_service_class(path, operation_id, context.package_name)
                    service_method = self._infer_service_method(operation_id, method, path)

                    # Collect parameters
                    path_params = [
                        p['name'] for p in operation.get('parameters', [])
                        if p.get('in') == 'path'
                    ]
                    query_params = [
                        p['name'] for p in operation.get('parameters', [])
                        if p.get('in') == 'query'
                    ]

                    descriptor = {
                        'path': path,
                        'method': method.upper(),
                        'operation_id': operation_id,
                        'resource_class': resource_class,
                        'service_class': service_class,
                        'service_method': service_method,
                        'path_params': path_params,
                        'query_params': query_params,
                    }

                    result.setdefault(class_name, []).append(descriptor)

        except Exception as e:
            self.log_error("Failed to collect 500 endpoints from spec", e)

        return result

    @staticmethod
    def _infer_resource_class(path: str, operation_id: str, package_name: str) -> str:
        """
        Infer a plausible JAX-RS resource class name from the endpoint path or operationId.
        Falls back to a generic name if nothing better can be derived.
        """
        import re
        # Try operationId first: e.g. 'getAlpha' -> 'AlphaResource'
        if operation_id:
            # Strip leading verb (get/post/put/delete/create/update/list/find)
            name = re.sub(r'^(get|post|put|delete|create|update|list|find|fetch)', '', operation_id, flags=re.IGNORECASE)
            if name:
                return name[0].upper() + name[1:] + 'Resource'

        # Fall back to path segments
        segs = [s for s in path.split('/') if s and not (s.startswith('{') and s.endswith('}'))]
        if segs:
            return ''.join(s.capitalize() for s in segs[-2:]) + 'Resource'
        return 'ApiResource'

    @staticmethod
    def _infer_service_class(path: str, operation_id: str, package_name: str) -> str:
        """Infer a plausible service class name."""
        import re
        if operation_id:
            name = re.sub(r'^(get|post|put|delete|create|update|list|find|fetch)', '', operation_id, flags=re.IGNORECASE)
            if name:
                return name[0].upper() + name[1:] + 'Service'
        segs = [s for s in path.split('/') if s and not (s.startswith('{') and s.endswith('}'))]
        if segs:
            return ''.join(s.capitalize() for s in segs[-2:]) + 'Service'
        return 'ApiService'

    @staticmethod
    def _infer_service_method(operation_id: str, http_method: str, path: str) -> str:
        """Infer a plausible service method name."""
        if operation_id:
            return operation_id
        segs = [s for s in path.split('/') if s and not (s.startswith('{') and s.endswith('}'))]
        suffix = ''.join(s.capitalize() for s in segs[-1:]) if segs else 'Resource'
        return http_method.lower() + suffix

    def _is_valid_java_code_500(self, code: str) -> bool:
        """
        Validate generated Test500 Java code structure.
        Relaxed variant: does NOT require Rest Assured imports (uses Jersey client instead).
        """
        if not code or not code.strip():
            return False

        required_elements = ['package ', 'import ', 'public class ', '@Test']
        for element in required_elements:
            if element not in code:
                self.logger.warning(f"Test500: Missing required element: {element}")
                return False

        # Must extend JerseyTest
        if 'JerseyTest' not in code:
            self.logger.warning("Test500: Missing JerseyTest base class")
            return False

        # Must have balanced braces
        if code.count('{') != code.count('}'):
            self.logger.warning("Test500: Unbalanced braces")
            return False

        return True

    # ------------------------------------------------------------------

    def _is_valid_java_code(self, code: str) -> bool:
        """
        Enhanced validation of Java code structure.
        
        Args:
            code: Java code to validate
        
        Returns:
            True if code appears to be valid Java
        """
        if not code or not code.strip():
            return False
        
        # Basic checks for Java code structure
        required_elements = [
            'package ',
            'import ',
            'public class ',
            '@Test'
        ]
        
        # Check for required elements
        for element in required_elements:
            if element not in code:
                self.logger.warning(f"Missing required element in Java code: {element}")
                return False
        
        # Check for proper class structure
        if not self._has_proper_class_structure(code):
            return False
        
        # Check for Rest Assured imports
        rest_assured_imports = [
            'io.restassured',
            'static io.restassured.RestAssured'
        ]
        
        has_rest_assured = any(imp in code for imp in rest_assured_imports)
        if not has_rest_assured:
            self.logger.warning("Missing Rest Assured imports in Java code")
            return False
        
        # Check for JUnit imports
        junit_imports = [
            'org.junit',
            '@Test',
            '@BeforeClass'
        ]
        
        has_junit = any(imp in code for imp in junit_imports)
        if not has_junit:
            self.logger.warning("Missing JUnit imports/annotations in Java code")
            return False
        
        return True
    
    def _has_proper_class_structure(self, code: str) -> bool:
        """
        Check if the Java code has proper class structure.
        
        Args:
            code: Java code to check
        
        Returns:
            True if class structure is valid
        """
        # Count braces to ensure they are balanced
        open_braces = code.count('{')
        close_braces = code.count('}')
        
        if open_braces != close_braces:
            self.logger.warning(f"Unbalanced braces in Java code: {open_braces} open, {close_braces} close")
            return False
        
        # Check for class declaration
        if 'public class ' not in code:
            self.logger.warning("Missing public class declaration")
            return False
        
        # Check for at least one test method
        if '@Test' not in code:
            self.logger.warning("Missing @Test annotation")
            return False
        
        # Check for setup method
        setup_indicators = ['@Before', '@BeforeClass', 'setupTestData', 'setUp']
        has_setup = any(indicator in code for indicator in setup_indicators)
        if not has_setup:
            self.logger.warning("Missing setup method indicators")
            return False
        
        return True
    
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

