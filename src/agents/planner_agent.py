"""
Planner Agent for analyzing APIs and creating test scenarios.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent
from ..config.models import AgentConfig, SystemConfig, TestScenario
from ..parsers import OpenAPIParser, JavaParser, MavenParser
from ..utils import OpenRouterClient


# ---------------------------------------------------------------------------
# HTTP status code classification helpers
# ---------------------------------------------------------------------------

# Priority order for selecting the "best" success status from a set of codes
_SUCCESS_STATUS_PRIORITY = ['200', '201', '202', '204', '206']

# Priority order for selecting the "best" client-error status for negative tests
_CLIENT_ERROR_STATUS_PRIORITY = ['400', '422', '409', '404', '401', '403']

# Fallback success status per HTTP method when the spec has no 2xx defined
_METHOD_DEFAULT_SUCCESS: Dict[str, int] = {
    'GET':     200,
    'POST':    201,
    'PUT':     200,
    'PATCH':   200,
    'DELETE':  204,
    'HEAD':    200,
    'OPTIONS': 200,
}

# What each status range means (used in scenario descriptions)
_STATUS_DESCRIPTIONS: Dict[int, str] = {
    # 2xx – Success
    200: 'OK',
    201: 'Created',
    202: 'Accepted',
    204: 'No Content',
    206: 'Partial Content',
    # 3xx – Redirection
    301: 'Moved Permanently',
    302: 'Found',
    304: 'Not Modified',
    307: 'Temporary Redirect',
    308: 'Permanent Redirect',
    # 4xx – Client Error
    400: 'Bad Request',
    401: 'Unauthorized',
    403: 'Forbidden',
    404: 'Not Found',
    405: 'Method Not Allowed',
    409: 'Conflict',
    410: 'Gone',
    415: 'Unsupported Media Type',
    422: 'Unprocessable Entity',
    429: 'Too Many Requests',
    # 5xx – Server Error
    500: 'Internal Server Error',
    502: 'Bad Gateway',
    503: 'Service Unavailable',
    504: 'Gateway Timeout',
}


def _classify_status(code: int) -> str:
    """Return the broad category of an HTTP status code."""
    if 100 <= code < 200:
        return 'informational'
    if 200 <= code < 300:
        return 'success'
    if 300 <= code < 400:
        return 'redirection'
    if 400 <= code < 500:
        return 'client_error'
    if 500 <= code < 600:
        return 'server_error'
    return 'unknown'


def _parse_response_codes(responses: Dict[str, Any]) -> Dict[str, List[int]]:
    """
    Parse raw OpenAPI *responses* dict and return codes grouped by category.

    Codes that cannot be converted to int (e.g. the erroneous '0' present in
    some specs) are silently ignored.
    """
    grouped: Dict[str, List[int]] = {
        'informational': [],
        'success': [],
        'redirection': [],
        'client_error': [],
        'server_error': [],
    }
    for raw_code in responses:
        try:
            code = int(raw_code)
        except (ValueError, TypeError):
            continue
        category = _classify_status(code)
        if category in grouped:
            grouped[category].append(code)

    # Sort each group for deterministic behaviour
    for key in grouped:
        grouped[key].sort()

    return grouped


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

        if self.system_config.openrouter.api_key:
            self.openrouter_client = OpenRouterClient(self.system_config.openrouter)
            self.logger.info("OpenRouter client initialized")
        else:
            self.logger.warning(
                "No OpenRouter API key provided – using basic scenario generation only"
            )

        self.logger.info("Planner Agent initialization complete")

    # ===========================================================
    # DEBUG: Salva snapshots de cenários em llm_interactions
    # ===========================================================
    def set_output_dir(self, output_dir: str) -> None:
        """Set the output directory for llm_interactions snapshot files.
        
        Called by the coordinator before the planning phase starts, so that
        all scenario snapshots are written inside the run-specific output
        directory (same level as maven-project/) instead of ./llm_interactions.
        Also propagates the directory to the OpenRouter client if available.
        
        Args:
            output_dir: Path to the run output directory.
        """
        self._output_dir = output_dir
        llm_dir = os.path.join(output_dir, 'llm_interactions')
        os.makedirs(llm_dir, exist_ok=True)
        self.logger.debug(f"PlannerAgent llm_interactions set to: {llm_dir}")
        if self.openrouter_client is not None:
            self.openrouter_client.set_output_dir(output_dir)

    def _llm_interactions_dir(self) -> str:
        """Return the path to the llm_interactions directory for this run."""
        if getattr(self, '_output_dir', None):
            return os.path.join(self._output_dir, 'llm_interactions')
        return './llm_interactions'

    def _save_scenarios_snapshot(self, stage: str, scenarios: List) -> None:
        """Save a JSON snapshot of scenarios at a given pipeline stage."""
        try:
            llm_dir = self._llm_interactions_dir()
            os.makedirs(llm_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
            filename = os.path.join(llm_dir, f"{timestamp}_scenarios_{stage}.json")
            data = {
                "stage": stage,
                "count": len(scenarios),
                "scenarios": [
                    {
                        "name": s.name,
                        "description": s.description,
                        "endpoint": s.endpoint,
                        "method": s.method,
                        "parameters": s.parameters,
                        "expected_status": s.expected_status,
                        "is_negative_test": s.is_negative_test,
                        "test_data": s.test_data,
                    }
                    for s in scenarios
                ],
            }
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"[DEBUG] Saved {len(scenarios)} scenarios snapshot → {filename}")
        except Exception as e:
            self.logger.warning(f"[DEBUG] Failed to save scenarios snapshot ({stage}): {e}")
    # ===========================================================

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
            self.log_progress("Parsing API specification", 1, 4)
            api_spec_path = input_data.get('api_spec_path')

            if not api_spec_path:
                return {
                    'success': False,
                    'error': "API specification path is required",
                    'scenarios': [],
                }

            self.logger.info(f"Parsing API specification: {api_spec_path}")
            api_spec = self.openapi_parser.parse_file(api_spec_path)

            if not api_spec:
                return {
                    'success': False,
                    'error': "Failed to parse API specification",
                    'scenarios': [],
                }

            implementation_analysis = None
            api_src_path = input_data.get('api_src_path')

            if api_src_path:
                self.log_progress("Analyzing API implementation", 2, 4)
                implementation_analysis = await self._analyze_implementation(api_src_path)
            else:
                self.logger.info(
                    "No API source code provided – generating tests based only on specification"
                )

            base_url = input_data.get('base_url', 'http://localhost:8080')

            self.log_progress("Generating test scenarios", 3, 4)
            scenarios = await self._generate_scenarios(api_spec, implementation_analysis, base_url)

            self.log_progress("Enhancing scenarios", 4, 4)
            if self.openrouter_client and scenarios:
                enhanced_scenarios = await self._enhance_scenarios_with_llm(
                    scenarios, api_spec, base_url
                )
                if enhanced_scenarios:
                    # FIX #5: If LLM returns fewer scenarios than the original set,
                    # fall back to the original rather than silently losing coverage.
                    if len(enhanced_scenarios) < len(scenarios):
                        self.logger.warning(
                            f"LLM enhancement reduced scenario count from {len(scenarios)} to "
                            f"{len(enhanced_scenarios)}. Falling back to original scenarios to "
                            f"preserve maximum coverage."
                        )
                        # Keep the original scenarios but do NOT discard the LLM output completely;
                        # merge them so we get both the original deterministic set and any new LLM
                        # scenarios that were not already present.
                        merged = self._merge_scenarios(scenarios, enhanced_scenarios)
                        scenarios = merged
                        self.logger.info(
                            f"Merged scenarios: {len(scenarios)} total after combining "
                            f"original + LLM-enhanced sets."
                        )
                    else:
                        scenarios = enhanced_scenarios
                        self.logger.info("Enhanced scenarios with LLM analysis")

            # ===========================================================
            # DEBUG: Snapshot 3 – cenários após enriquecimento com LLM
            self._save_scenarios_snapshot("3_llm_enhanced", scenarios)
            # ===========================================================

            self.logger.info(f"Generated {len(scenarios)} test scenarios")

            return {
                'success': True,
                'message': f"Successfully generated {len(scenarios)} test scenarios",
                'scenarios': scenarios,
                'api_spec_summary': self._create_api_summary(api_spec),
                'implementation_summary': (
                    self._create_implementation_summary(implementation_analysis)
                    if implementation_analysis
                    else None
                ),
            }

        except Exception as e:
            self.log_error("Unexpected error in planner process", e)
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}",
                'scenarios': [],
            }

    # ------------------------------------------------------------------
    # Implementation analysis
    # ------------------------------------------------------------------

    async def _analyze_implementation(self, api_src_path: str) -> Dict[str, Any]:
        """Analyze API implementation source code."""
        try:
            src_path = Path(api_src_path)
            maven_analysis = self.maven_parser.parse_project(src_path)
            java_classes = self.java_parser.parse_project(src_path)
            rest_endpoints = self.java_parser.extract_rest_endpoints(java_classes)
            return {
                'maven_project': maven_analysis,
                'java_classes': java_classes,
                'rest_endpoints': rest_endpoints,
            }
        except Exception as e:
            self.logger.error(f"Error analyzing implementation: {e}")
            return {}

    # ------------------------------------------------------------------
    # Scenario generation orchestration
    # ------------------------------------------------------------------

    def _extract_dependencies(self, api_spec: Any) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """
        Extract setup and teardown dependencies for each endpoint path.

        The algorithm analyses the full path hierarchy to determine which
        ancestor resources must be created (via POST) before a given endpoint
        can be exercised, and which resources must be deleted (via DELETE)
        after the test is complete.

        Strategy
        --------
        1. Build a map of ``path -> set of HTTP methods`` from the spec.
        2. For every path, walk up the path hierarchy (removing the last
           segment at each step) to collect all ancestor paths.
        3. A path is a *creatable ancestor* if it supports POST and at least
           one of its path segments is a parameter (``{param}``) — meaning it
           represents a named resource that must be created before child
           resources can be accessed.
        4. Setup dependencies are the ordered list of POST calls needed to
           create the full resource hierarchy (root ancestor first).
        5. Teardown dependencies are the DELETE calls in reverse order
           (deepest resource first, then parents), using the most specific
           DELETE available for each level.

        Returns a mapping: path -> {'setup': [...], 'teardown': [...]}
        """
        dependencies: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

        # ── Step 1: collect all paths and their available methods ──────────
        path_methods: Dict[str, set] = {}
        for endpoint in api_spec.endpoints:
            path = endpoint.path
            if path not in path_methods:
                path_methods[path] = set()
            path_methods[path].add(endpoint.method.upper())

        # ── Step 2 & 3: for each path, build the ancestor hierarchy ────────
        for path in path_methods.keys():
            setup: List[Dict[str, Any]] = []
            teardown: List[Dict[str, Any]] = []

            # Collect all ancestor paths (from root down to the direct parent)
            parts = path.split('/')
            ancestor_paths: List[str] = []
            for i in range(1, len(parts)):
                ancestor = '/'.join(parts[:i])
                if ancestor and ancestor in path_methods:
                    ancestor_paths.append(ancestor)

            # ── Setup: POST calls in top-down order ────────────────────────
            # An ancestor needs a POST setup call when:
            #   a) it supports POST, AND
            #   b) its last segment is a path parameter (it is a named resource
            #      that must be explicitly created, not just a collection)
            #      OR it is the direct parent of the current path and the
            #      current path itself has path parameters.
            for anc in ancestor_paths:
                anc_parts = anc.split('/')
                last_seg = anc_parts[-1] if anc_parts else ''
                # The ancestor is a named-resource endpoint if its last segment
                # is a path parameter (e.g. /products/{productName})
                is_named_resource = last_seg.startswith('{') and last_seg.endswith('}')
                if 'POST' in path_methods[anc] and is_named_resource:
                    setup.append({'method': 'POST', 'endpoint': anc})

            # Also include a POST on the direct parent when the current path
            # itself has path parameters and the parent supports POST
            # (handles the case where the parent is a collection, e.g. /products)
            if len(parts) > 1:
                direct_parent = '/'.join(parts[:-1])
                if (direct_parent in path_methods
                        and 'POST' in path_methods[direct_parent]
                        and not any(d['endpoint'] == direct_parent for d in setup)):
                    # Only add if the current path has at least one param segment
                    if any(seg.startswith('{') and seg.endswith('}') for seg in parts):
                        setup.append({'method': 'POST', 'endpoint': direct_parent})

            # ── Teardown: DELETE calls in bottom-up order ──────────────────
            # Delete the current resource first (if DELETE is available),
            # then walk up the ancestor list in reverse order.
            if 'DELETE' in path_methods[path]:
                teardown.append({'method': 'DELETE', 'endpoint': path})

            for anc in reversed(ancestor_paths):
                anc_parts = anc.split('/')
                last_seg = anc_parts[-1] if anc_parts else ''
                is_named_resource = last_seg.startswith('{') and last_seg.endswith('}')
                if 'DELETE' in path_methods[anc] and is_named_resource:
                    teardown.append({'method': 'DELETE', 'endpoint': anc})

            dependencies[path] = {'setup': setup, 'teardown': teardown}

        return dependencies

    async def _generate_scenarios(
        self,
        api_spec: Any,
        implementation_analysis: Dict[str, Any],
        base_url: str,
    ) -> List[TestScenario]:
        """Generate test scenarios from API specification and source code."""
        scenarios: List[TestScenario] = []

        # Extract dependencies from spec
        dependencies = self._extract_dependencies(api_spec)

        spec_scenarios = self._generate_scenarios_from_spec(api_spec, base_url)
        
        # Inject dependencies into scenarios
        for scenario in spec_scenarios:
            path_deps = dependencies.get(scenario.endpoint, {})
            scenario.setup_dependencies = path_deps.get('setup', [])
            scenario.teardown_dependencies = path_deps.get('teardown', [])
            
        scenarios.extend(spec_scenarios)
        self.logger.info(
            f"Generated {len(spec_scenarios)} scenarios from OpenAPI specification"
        )

        if implementation_analysis:
            source_scenarios = self._generate_scenarios_from_source(
                implementation_analysis, base_url
            )
            
            # Inject dependencies into source scenarios
            for scenario in source_scenarios:
                path_deps = dependencies.get(scenario.endpoint, {})
                scenario.setup_dependencies = path_deps.get('setup', [])
                scenario.teardown_dependencies = path_deps.get('teardown', [])
                
            scenarios.extend(source_scenarios)
            self.logger.info(
                f"Generated {len(source_scenarios)} scenarios from source code analysis"
            )

        # ===========================================================
        # DEBUG: Snapshot 1 – cenários brutos (spec + source code)
        self._save_scenarios_snapshot("1_raw", scenarios)
        # ===========================================================

        unique_scenarios = self._remove_duplicates(scenarios)
        self.logger.info(
            f"Total scenarios after deduplication: {len(unique_scenarios)}"
        )

        # ===========================================================
        # DEBUG: Snapshot 2 – cenários após deduplicação
        self._save_scenarios_snapshot("2_deduplicated", unique_scenarios)
        # ===========================================================

        return unique_scenarios

    # ------------------------------------------------------------------
    # Spec-based scenario generation
    # ------------------------------------------------------------------

    def _generate_scenarios_from_spec(self, api_spec: Any, base_url: str) -> List[TestScenario]:
        """Generate test scenarios from OpenAPI specification."""
        scenarios: List[TestScenario] = []

        for endpoint in api_spec.endpoints:
            responses: Dict[str, Any] = getattr(endpoint, 'responses', {})
            grouped_codes = _parse_response_codes(responses)

            # ── Operation-level x-parameter-examples (MANDATORY) ───────────
            # When the spec provides x-parameter-examples at the operation level,
            # these are MANDATORY test scenarios that MUST be generated using
            # the exact parameter values provided by the spec author.
            # One scenario is created per example entry (each element in the list).
            #
            # op_examples structure (after parser fix):
            #   { "200": [{"_name": "typical", "n": 2, "x": 1.5}, ...],
            #     "400": [{"_name": "invalid", "n": -1, "x": 0.0}, ...] }
            op_examples: Dict[str, List[Dict[str, Any]]] = getattr(
                endpoint, 'operation_parameter_examples', {}
            )
            mandatory_status_codes: set = set()

            # Count total mandatory scenarios across all status codes
            total_mandatory = sum(len(v) for v in op_examples.values())
            if op_examples:
                self.logger.info(
                    f"Generating {total_mandatory} mandatory scenario(s) from "
                    f"x-parameter-examples for {endpoint.method} {endpoint.path}"
                )

            for status_str, example_list in op_examples.items():
                try:
                    status_int = int(status_str)
                except (ValueError, TypeError):
                    self.logger.warning(
                        f"Skipping x-parameter-examples entry with non-integer "
                        f"status key '{status_str}' on {endpoint.path}"
                    )
                    continue

                # Skip 5xx — handled exclusively by *500Test.java pipeline
                if 500 <= status_int < 600:
                    continue

                mandatory_status_codes.add(status_int)
                is_negative = status_int >= 400
                status_label = _STATUS_DESCRIPTIONS.get(status_int, 'error').lower().replace(' ', '_')

                for idx, param_values in enumerate(example_list):
                    # Use _name from the example dict as the scenario suffix if present.
                    # Always prefix with the status code to avoid name collisions when
                    # the same _name (e.g. 'invalid_type') appears under multiple status
                    # codes (e.g. 401, 403, 404) for the same endpoint.
                    example_name = param_values.get('_name', '')
                    if example_name:
                        suffix = f"{status_int}_{self._sanitize_path(example_name)}"
                    elif is_negative:
                        suffix = f"{status_int}_{status_label}_{idx + 1}" if len(example_list) > 1 else f"{status_int}_{status_label}"
                    else:
                        suffix = f"{status_int}_spec_example_{idx + 1}" if len(example_list) > 1 else f"{status_int}_spec_example"

                    scenario_name = (
                        f"test_{endpoint.method.lower()}_"
                        f"{self._sanitize_path(endpoint.path)}_"
                        f"{suffix}"
                    )
                    # Strip _name from the parameters passed to the test
                    clean_params = {k: v for k, v in param_values.items() if k != '_name'}
                    description = (
                        f"Test {endpoint.method} {endpoint.path} – "
                        f"spec-provided x-parameter-examples for status {status_int} "
                        f"{_STATUS_DESCRIPTIONS.get(status_int, '')} "
                        f"(mandatory: values from API specification"
                        + (f", example '{example_name}'" if example_name else "")
                        + ")"
                    )
                    scenarios.append(
                        TestScenario(
                            name=scenario_name,
                            description=description,
                            endpoint=endpoint.path,
                            method=endpoint.method,
                            parameters=clean_params,
                            expected_status=status_int,
                            is_negative_test=is_negative,
                            test_data=clean_params,
                            content_type=endpoint.content_type,
                        )
                    )

            # ── Positive / success scenario (if not already covered) ────────
            # Use operation_parameter_examples[success_status] values if available,
            # otherwise fall back to parameter_examples and heuristics.
            # When the spec provides multiple success examples, the first one is
            # already emitted above as a mandatory scenario; we only add the
            # generic success scenario when NO mandatory success example exists.
            success_status = self._pick_success_status(grouped_codes, endpoint)
            if success_status not in mandatory_status_codes:
                parameters = self._extract_parameters_with_examples(
                    endpoint, None  # no single-example override; use per-param examples
                )
                scenarios.append(
                    TestScenario(
                        name=f"test_{endpoint.method.lower()}_{self._sanitize_path(endpoint.path)}_success",
                        description=(
                            f"Test {endpoint.method} {endpoint.path} – "
                            f"success case ({success_status} "
                            f"{_STATUS_DESCRIPTIONS.get(success_status, '')})"
                        ),
                        endpoint=endpoint.path,
                        method=endpoint.method,
                        parameters=parameters,
                        expected_status=success_status,
                        is_negative_test=False,
                        test_data=parameters,
                        content_type=endpoint.content_type,
                    )
                )
                # Use these parameters as the primary values for extra-example scenarios
            else:
                # Use the first mandatory success example's parameters as the primary
                # values for generating extra per-parameter example scenarios below
                first_success_examples = op_examples.get(str(success_status), [{}])
                parameters = {
                    k: v
                    for k, v in (first_success_examples[0] if first_success_examples else {}).items()
                    if k != '_name'
                }

            # ── Additional scenarios from per-parameter examples ────────────
            # When the spec provides multiple example values for individual
            # parameters via param.x-parameter-examples, generate one extra
            # success scenario per additional example value beyond the first.
            extra_scenarios = self._generate_extra_example_scenarios(
                endpoint, success_status, parameters
            )
            scenarios.extend(extra_scenarios)

            # ── Negative / error scenarios ─────────────────────────────────
            if self.system_config.test_generation.generate_negative_tests:
                negative_scenarios = self._generate_negative_scenarios(
                    endpoint, grouped_codes, op_examples, mandatory_status_codes
                )
                scenarios.extend(negative_scenarios)

        return scenarios

    def _generate_extra_example_scenarios(
        self,
        endpoint: Any,
        success_status: int,
        primary_parameters: Dict[str, Any],
    ) -> List[TestScenario]:
        """
        Generate additional test scenarios for each extra example value provided
        in the OpenAPI specification via ``x-parameter-examples`` (or any of the
        standard examples fields extracted by the parser).

        The first example value is already used in the primary success scenario.
        This method creates one additional scenario per *extra* example value
        (index 1, 2, …) for every parameter that has multiple examples, combining
        them with the primary values of all other parameters.

        Only non-5xx success scenarios are generated here; 5xx scenarios are
        handled separately by the *500Test.java generation pipeline.
        """
        extra: List[TestScenario] = []
        pre_extracted: Dict[str, list] = getattr(endpoint, 'parameter_examples', {})

        for param_name, example_values in pre_extracted.items():
            # Skip if there is only one example (already covered by primary scenario)
            if len(example_values) <= 1:
                continue

            for idx, extra_value in enumerate(example_values[1:], start=2):
                # Build parameter dict: use extra value for this param,
                # keep primary values for all other params.
                params_for_scenario = dict(primary_parameters)
                params_for_scenario[param_name] = extra_value

                scenario_name = (
                    f"test_{endpoint.method.lower()}_"
                    f"{self._sanitize_path(endpoint.path)}_"
                    f"{param_name}_example{idx}"
                )
                description = (
                    f"Test {endpoint.method} {endpoint.path} – "
                    f"success case with spec-provided example value #{idx} "
                    f"for parameter '{param_name}' "
                    f"(expected {success_status} "
                    f"{_STATUS_DESCRIPTIONS.get(success_status, '')})"
                )
                extra.append(
                    TestScenario(
                        name=scenario_name,
                        description=description,
                        endpoint=endpoint.path,
                        method=endpoint.method,
                        parameters=params_for_scenario,
                        expected_status=success_status,
                        is_negative_test=False,
                        test_data=params_for_scenario,
                        content_type=endpoint.content_type,
                    )
                )

        return extra

    # ------------------------------------------------------------------
    # Source-based scenario generation
    # ------------------------------------------------------------------

    def _generate_scenarios_from_source(
        self, implementation_analysis: Dict[str, Any], base_url: str
    ) -> List[TestScenario]:
        """Generate test scenarios from source code analysis."""
        scenarios: List[TestScenario] = []

        for endpoint_data in implementation_analysis.get('rest_endpoints', []):
            if isinstance(endpoint_data, dict):
                endpoint_path = endpoint_data.get('path', '')
                endpoint_method = endpoint_data.get('method', 'GET')
            else:
                endpoint_path = getattr(endpoint_data, 'path', '')
                endpoint_method = getattr(endpoint_data, 'method', 'GET')

            if not self._is_valid_endpoint(endpoint_path):
                self.logger.debug(f"Skipping invalid endpoint: {endpoint_path}")
                continue

            default_success = _METHOD_DEFAULT_SUCCESS.get(endpoint_method.upper(), 200)

            scenarios.append(
                TestScenario(
                    name=f"test_{endpoint_method.lower()}_{self._sanitize_path(endpoint_path)}_source",
                    description=f"Test {endpoint_method} {endpoint_path} (from source code)",
                    endpoint=endpoint_path,
                    method=endpoint_method,
                    parameters={},
                    expected_status=default_success,
                    is_negative_test=False,
                    test_data={},
                    content_type=getattr(endpoint_data, 'content_type', None),
                )
            )

        return scenarios

    # ------------------------------------------------------------------
    # Status-code resolution helpers
    # ------------------------------------------------------------------

    def _pick_success_status(
        self, grouped_codes: Dict[str, List[int]], endpoint: Any
    ) -> int:
        """
        Choose the most appropriate 2xx status for a positive test scenario.

        Resolution order:
        1. First match in the priority list [200, 201, 202, 204, 206]
        2. Any other 2xx code present in the spec
        3. Static method-based fallback
        """
        success_codes = grouped_codes.get('success', [])

        for priority_code in _SUCCESS_STATUS_PRIORITY:
            if int(priority_code) in success_codes:
                return int(priority_code)

        if success_codes:
            return success_codes[0]

        # Fallback: derive from HTTP method
        method = getattr(endpoint, 'method', 'GET').upper()
        return _METHOD_DEFAULT_SUCCESS.get(method, 200)

    def _pick_client_error_status(self, grouped_codes: Dict[str, List[int]]) -> int:
        """
        Choose the most appropriate 4xx status for a negative test scenario.

        Resolution order:
        1. 400 Bad Request  – best match for invalid-parameter tests
        2. 422 Unprocessable Entity – semantic validation failures
        3. 409 Conflict     – duplicate / state conflicts
        4. 404 Not Found    – resource does not exist
        5. 401 Unauthorized – missing or invalid credentials
        6. 403 Forbidden    – insufficient permissions
        7. Any other 4xx present in the spec
        8. Hardcoded 400 as last resort
        """
        client_error_codes = grouped_codes.get('client_error', [])

        for priority_code in _CLIENT_ERROR_STATUS_PRIORITY:
            if int(priority_code) in client_error_codes:
                return int(priority_code)

        if client_error_codes:
            return client_error_codes[0]

        return 400

    # ------------------------------------------------------------------
    # Negative scenario generation
    # ------------------------------------------------------------------

    def _generate_negative_scenarios(
        self,
        endpoint: Any,
        grouped_codes: Dict[str, List[int]],
        op_examples: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        mandatory_status_codes: Optional[set] = None,
    ) -> List[TestScenario]:
        """
        Generate negative test scenarios for an endpoint.

        Covers:
        - Invalid / missing required parameters  → 400 / 422
        - Unauthorized access                    → 401  (if in spec)
        - Forbidden access                       → 403  (if in spec)
        - Resource not found                     → 404  (if in spec)
        - Server errors                          → 5xx  (if in spec, informational only)

        When ``op_examples`` is provided, the parameter values from
        ``x-parameter-examples`` are used for the corresponding status codes.
        Status codes already covered by mandatory scenarios (from x-parameter-examples)
        are skipped to avoid duplicates.

        Note: ``op_examples`` is now ``Dict[str, List[Dict[str, Any]]]`` (list of
        example dicts per status code). All mandatory scenarios for those status codes
        are already generated in ``_generate_scenarios_from_spec``; this method only
        generates fallback generic scenarios for status codes NOT covered by mandatory
        examples.
        """
        scenarios: List[TestScenario] = []
        op_examples = op_examples or {}
        mandatory_status_codes = mandatory_status_codes or set()

        # ── 1. Invalid parameters scenario ────────────────────────────────────
        if endpoint.parameters:
            error_status = self._pick_client_error_status(grouped_codes)

            # Skip if this error status was already covered by a mandatory
            # x-parameter-examples scenario
            if error_status not in mandatory_status_codes:
                # For this generic fallback scenario, use None values (invalid/missing)
                # since all specific examples are already emitted as mandatory scenarios
                invalid_params = {
                    param.get('name', 'unknown'): None for param in endpoint.parameters
                }
                param_source = "invalid/missing parameters"

                scenarios.append(
                    TestScenario(
                        name=(
                            f"test_{endpoint.method.lower()}_"
                            f"{self._sanitize_path(endpoint.path)}_invalid_params"
                        ),
                        description=(
                            f"Test {endpoint.method} {endpoint.path} – "
                            f"{param_source} "
                            f"(expected {error_status} "
                            f"{_STATUS_DESCRIPTIONS.get(error_status, 'Client Error')})"
                        ),
                        endpoint=endpoint.path,
                        method=endpoint.method,
                        parameters=invalid_params,
                        expected_status=error_status,
                        is_negative_test=True,
                        test_data=invalid_params,
                        content_type=endpoint.content_type,
                    )
                )

        # ── 2. Unauthorized scenario (401) ─────────────────────────────────
        if 401 in grouped_codes.get('client_error', []) and 401 not in mandatory_status_codes:
            scenarios.append(
                TestScenario(
                    name=(
                        f"test_{endpoint.method.lower()}_"
                        f"{self._sanitize_path(endpoint.path)}_unauthorized"
                    ),
                    description=(
                        f"Test {endpoint.method} {endpoint.path} – "
                        "unauthorized access (expected 401 Unauthorized)"
                    ),
                    endpoint=endpoint.path,
                    method=endpoint.method,
                    parameters={},
                    expected_status=401,
                    is_negative_test=True,
                    test_data={},
                    content_type=endpoint.content_type,
                )
            )

        # ── 3. Forbidden scenario (403) ────────────────────────────────────
        if 403 in grouped_codes.get('client_error', []) and 403 not in mandatory_status_codes:
            scenarios.append(
                TestScenario(
                    name=(
                        f"test_{endpoint.method.lower()}_"
                        f"{self._sanitize_path(endpoint.path)}_forbidden"
                    ),
                    description=(
                        f"Test {endpoint.method} {endpoint.path} – "
                        "forbidden access (expected 403 Forbidden)"
                    ),
                    endpoint=endpoint.path,
                    method=endpoint.method,
                    parameters={},
                    expected_status=403,
                    is_negative_test=True,
                    test_data={},
                    content_type=endpoint.content_type,
                )
            )

        # ── 4. Not-found scenario (404) ────────────────────────────────────
        if 404 in grouped_codes.get('client_error', []) and 404 not in mandatory_status_codes:
            # Build a path that forces a 404 (non-existent resource)
            not_found_path = endpoint.path + '/non-existent-resource'
            scenarios.append(
                TestScenario(
                    name=(
                        f"test_{endpoint.method.lower()}_"
                        f"{self._sanitize_path(endpoint.path)}_not_found"
                    ),
                    description=(
                        f"Test {endpoint.method} {not_found_path} – "
                        "resource not found (expected 404 Not Found)"
                    ),
                    endpoint=not_found_path,
                    method=endpoint.method,
                    parameters={},
                    expected_status=404,
                    is_negative_test=True,
                    test_data={},
                    content_type=endpoint.content_type,
                )
            )

        # ── 5. Server-error scenarios (5xx) ─────────────────────────────────
        #   These are informational: we document what the server may return
        #   but do not actively trigger them in automated tests.
        for server_error_code in grouped_codes.get('server_error', []):
            self.logger.debug(
                f"Endpoint {endpoint.method} {endpoint.path} declares "
                f"server error {server_error_code} – skipping active test generation"
            )

        return scenarios

    # ------------------------------------------------------------------
    # Parameter helpers
    # ------------------------------------------------------------------

    def _extract_parameters_with_examples(
        self,
        endpoint: Any,
        op_example_override: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Extract parameters with priority for examples from OpenAPI specification.

        Priority order (highest → lowest):
        0. ``op_example_override``                — operation-level x-parameter-examples
           for the specific status code (e.g. the 200 entry).  When provided,
           these values are used directly and override all other sources.
        1. ``endpoint.parameter_examples[name]``  — pre-extracted by the parser
           (covers ``param.example``, ``param.examples``,
           ``param.x-parameter-examples``, ``param.schema.example``,
           ``param.schema.examples``)
        2. ``param.schema.enum[0]``               — first enum value
        3. Heuristic realistic value              — generated from name/type
        """
        parameters: Dict[str, Any] = {}

        # Pre-extracted examples map from the parser (may be empty dict)
        pre_extracted: Dict[str, list] = getattr(endpoint, 'parameter_examples', {})

        for param in endpoint.parameters:
            param_name = param.get('name', 'unknown')
            param_schema = param.get('schema', {})
            param_type = param_schema.get('type', 'string')

            # 0. Operation-level x-parameter-examples override (highest priority)
            if op_example_override and param_name in op_example_override:
                parameters[param_name] = op_example_override[param_name]
            # 1. Use pre-extracted per-parameter examples (first value)
            elif param_name in pre_extracted and pre_extracted[param_name]:
                parameters[param_name] = pre_extracted[param_name][0]
            # 2. Enum fallback
            elif 'enum' in param_schema and param_schema['enum']:
                parameters[param_name] = param_schema['enum'][0]
            # 3. Heuristic realistic value
            else:
                parameters[param_name] = self._generate_realistic_value(
                    param_name, param_type
                )

        return parameters

    def _generate_realistic_value(self, param_name: str, param_type: str) -> Any:
        """Generate realistic parameter values based on name and type."""
        param_name_lower = param_name.lower()

        if param_type == 'string':
            if 'name' in param_name_lower:
                return 'smartphone'
            if 'id' in param_name_lower:
                return 'test-id-123'
            if 'feature' in param_name_lower:
                return 'camera'
            if 'config' in param_name_lower:
                return 'premium'
            if 'date' in param_name_lower:
                return '2024-01-01'
            if 'organization' in param_name_lower:
                return 'acme-corp'
            if 'language' in param_name_lower:
                return 'Python'
            if 'limit' in param_name_lower:
                return '10'
            if 'offset' in param_name_lower:
                return '0'
            if 'sort' in param_name_lower:
                return 'name'
            return 'test-value'

        if param_type == 'integer':
            if 'limit' in param_name_lower:
                return 10
            if 'offset' in param_name_lower:
                return 0
            return 123

        if param_type == 'boolean':
            return True

        return 'test-value'

    # ------------------------------------------------------------------
    # Endpoint validation helpers
    # ------------------------------------------------------------------

    def _is_valid_endpoint(self, endpoint_path: str) -> bool:
        """Check if an endpoint path is valid."""
        if not endpoint_path:
            return False

        path = endpoint_path.lstrip('/')

        if not path or path == '/':
            return True

        segments = path.split('/')
        first_segment = segments[0]

        if first_segment.startswith('{') and first_segment.endswith('}'):
            return False

        invalid_names = [
            'id', 'name', 'productname', 'username', 'featurename',
            'configurationname', 'constraintid', 'requires', 'excludes',
        ]
        if first_segment.lower() in invalid_names:
            return False

        return True

    def _sanitize_path(self, path: str) -> str:
        """Sanitize path for use in test method names."""
        sanitized = (
            path.lstrip('/')
            .replace('/', '_')
            .replace('{', '')
            .replace('}', '')
        )
        sanitized = '_'.join(filter(None, sanitized.split('_')))
        return sanitized or 'root'

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def _remove_duplicates(self, scenarios: List[TestScenario]) -> List[TestScenario]:
        """
        Remove duplicate scenarios.

        Two scenarios are considered duplicates only when they share the same
        *name* **and** the same (method, endpoint, is_negative_test,
        expected_status) tuple.  Using the name as the primary key ensures that
        multiple mandatory scenarios derived from ``x-parameter-examples`` for
        the same status code are all preserved (they have distinct names such as
        ``test_get_..._typical`` vs ``test_get_..._edge_case``).
        """
        unique_scenarios: List[TestScenario] = []
        seen_names: set = set()
        seen_signatures: set = set()

        for scenario in scenarios:
            name = scenario.name
            signature = (
                scenario.method,
                scenario.endpoint,
                scenario.is_negative_test,
                scenario.expected_status,
            )

            # A scenario is a duplicate only if its name was already seen.
            # If the name is unique but the signature matches an existing
            # scenario, we still keep it (different example values, same status).
            if name not in seen_names:
                unique_scenarios.append(scenario)
                seen_names.add(name)
                seen_signatures.add(signature)

        return unique_scenarios

    # ------------------------------------------------------------------
    # Scenario merging (FIX #5 support)
    # ------------------------------------------------------------------

    def _merge_scenarios(
        self,
        original: List[TestScenario],
        enhanced: List[TestScenario],
    ) -> List[TestScenario]:
        """
        Merge original and LLM-enhanced scenario lists.

        Strategy:
        - Start with all original scenarios (guarantees baseline coverage).
        - Append any enhanced scenario whose signature is not already present
          (brings in genuinely new LLM-generated scenarios).
        - The result is deduplicated to avoid exact duplicates.

        Args:
            original: The deterministically generated scenario list.
            enhanced: The LLM-enhanced scenario list (may be smaller).

        Returns:
            Merged, deduplicated list with at least as many entries as *original*.
        """
        merged = list(original)
        # Use scenario name as the primary deduplication key so that multiple
        # mandatory x-parameter-examples scenarios for the same status code are
        # all preserved (they have distinct names).
        seen_names: set = {s.name for s in original}

        for scenario in enhanced:
            if scenario.name not in seen_names:
                merged.append(scenario)
                seen_names.add(scenario.name)

        return merged

    # ------------------------------------------------------------------
    # LLM enhancement
    # ------------------------------------------------------------------

    async def _enhance_scenarios_with_llm(
        self,
        scenarios: List[TestScenario],
        api_spec: Any,
        base_url: str,
    ) -> Optional[List[TestScenario]]:
        """Enhance scenarios using LLM analysis."""
        try:
            context = self._prepare_llm_context(scenarios, api_spec, base_url)
            prompt = self._build_enhancement_prompt(context)

            # FIX #4: Pass scenario_count so the OpenRouterClient can embed
            # the minimum-count enforcement into its system message.
            response = await self.openrouter_client.generate_enhanced_test_scenarios(
                prompt=prompt,
                model=self.get_model_name(),
                max_tokens=self.get_max_tokens(),
                temperature=self.get_temperature(),
                scenario_count=len(scenarios),
            )

            if response:
                enhanced_data = self._parse_llm_response(response)
                if enhanced_data:
                    return self._create_enhanced_scenarios(enhanced_data, scenarios)

        except Exception as e:
            self.logger.error(f"Error enhancing scenarios with LLM: {e}")

        return None

    def _prepare_llm_context(
        self, scenarios: List[TestScenario], api_spec: Any, base_url: str
    ) -> Dict[str, Any]:
        """Prepare context for LLM analysis."""
        api_endpoints = [
            {
                'path': ep.path,
                'method': ep.method,
                'parameters': [p.get('name', 'unknown') for p in ep.parameters],
                'description': ep.description or f"{ep.method} {ep.path}",
                'responses': list(getattr(ep, 'responses', {}).keys()),
            }
            for ep in api_spec.endpoints
        ]

        scenario_info = [
            {
                'name': s.name,
                'endpoint': s.endpoint,
                'method': s.method,
                'parameters': s.parameters,
                'expected_status': s.expected_status,
                'is_negative_test': s.is_negative_test,
                'description': s.description,
            }
            for s in scenarios
        ]

        # ── Collect spec-level examples to enrich the LLM context ───────────
        spec_examples: Dict[str, Any] = {}
        for ep in api_spec.endpoints:
            ep_key = f"{ep.method} {ep.path}"
            ep_examples: Dict[str, Any] = {}

            param_ex = getattr(ep, 'parameter_examples', {})
            if param_ex:
                ep_examples['parameter_examples'] = param_ex

            resp_ex = getattr(ep, 'response_examples', {})
            if resp_ex:
                # Truncate large response bodies to keep the context manageable
                truncated_resp: Dict[str, Any] = {}
                for status, ex_list in resp_ex.items():
                    truncated_resp[status] = [
                        ex if not isinstance(ex, (dict, list)) else
                        (ex if len(str(ex)) <= 500 else '<truncated>')
                        for ex in ex_list[:2]  # at most 2 examples per status
                    ]
                ep_examples['response_examples'] = truncated_resp

            rb_ex = getattr(ep, 'request_body_examples', [])
            if rb_ex:
                ep_examples['request_body_examples'] = [
                    ex if not isinstance(ex, (dict, list)) else
                    (ex if len(str(ex)) <= 500 else '<truncated>')
                    for ex in rb_ex[:2]
                ]

            if ep_examples:
                spec_examples[ep_key] = ep_examples

        return {
            'base_url': base_url,
            'api_endpoints': api_endpoints,
            'current_scenarios': scenario_info,
            'api_title': getattr(api_spec, 'title', 'API'),
            'api_description': getattr(api_spec, 'description', ''),
            'spec_examples': spec_examples,
        }

    @staticmethod
    def _build_enhancement_prompt(context: Dict[str, Any]) -> str:
        """Build prompt for LLM scenario enhancement."""
        scenario_count = len(context.get('current_scenarios', []))

        # Build the optional spec-examples block only when examples are present
        spec_examples = context.get('spec_examples', {})
        if spec_examples:
            examples_block = (
                "\nSpec-Provided Examples (USE THESE VALUES IN YOUR SCENARIOS):\n"
                + json.dumps(spec_examples, indent=2)
                + "\n"
            )
        else:
            examples_block = ""

        return f"""
You are an expert API testing specialist. Analyze the following API specification and test scenarios to improve them.

API Information:
- Title: {context['api_title']}
- Description: {context['api_description']}
- Base URL: {context['base_url']}

API Endpoints (with declared response codes):
{json.dumps(context['api_endpoints'], indent=2)}
{examples_block}
Current Test Scenarios ({scenario_count} scenarios – you MUST preserve all of them):
{json.dumps(context['current_scenarios'], indent=2)}

Your task is to:
1. Identify realistic test flows (Create → Read → Update → Delete)
2. Ensure parameter values are realistic and consistent
3. Ensure AT LEAST ONE SCENARIO EXISTS FOR EACH API ENDPOINT
4. Explore all possibilities for POST, PUT, GET, and DELETE methods
5. Set expected_status accurately using the declared response codes:
   - 2xx for positive/success scenarios  (200 OK, 201 Created, 204 No Content …)
   - 4xx for negative/client-error scenarios (400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found …)
   - Do NOT include 5xx scenarios (500, 502, 503, etc.) — HTTP 500 tests require a
     dedicated Jersey+Mockito class (*500Test.java) generated separately. Omit all 5xx scenarios.
6. Add dependency information between scenarios
7. Improve scenario descriptions
8. CRITICAL — Mandatory x-parameter-examples scenarios:
   Some scenarios in the input list have descriptions containing the phrase
   "(mandatory: values from API specification)". These scenarios were generated
   directly from the "x-parameter-examples" OpenAPI extension and their parameter
   values are EXACT values provided by the API author.
   You MUST:
   a) PRESERVE every mandatory scenario in the output — never remove or merge them.
   b) NEVER change the "parameters" or "expected_status" of a mandatory scenario.
   c) You MAY improve the "description" field only.
   d) You MAY add NEW additional scenarios alongside the mandatory ones.
9. IMPORTANT: When the spec provides "parameter_examples" for an endpoint, you MUST use
   those exact values as the primary test inputs for that parameter. You MAY also create
   ADDITIONAL scenarios that use alternative values from the examples list (when multiple
   examples are provided) to maximise coverage.
10. When the spec provides "response_examples", use them to validate response body structure
    in the scenario description and test_data fields.
11. Replace any remaining generic placeholder values (e.g. "test-value") with domain-realistic
    values appropriate to the endpoint semantics.

Rules:
- Endpoints must start with valid paths (never with bare path parameters like /{{param}})
- Use consistent parameter values across related scenarios
- Do NOT invent status codes not present in the spec responses
- Do NOT generate scenarios with expected_status 500 or any other 5xx code
- CRITICAL — setup_dependencies and teardown_dependencies MUST only reference endpoints that
  actually exist in the OpenAPI specification. Never invent endpoints. For example, if the
  spec has POST /products/{{productName}} but NOT POST /products, use
  POST /products/{{productName}} (with a concrete value like "smartphone") in
  setup_dependencies. Using a non-existent endpoint causes invalid @Before code.
- The output enhanced_scenarios array MUST contain AT LEAST {scenario_count} entries
- You MUST include an improved version of every input scenario
- You MAY add new scenarios beyond the {scenario_count} minimum
- When multiple parameter examples are available, create one scenario per distinct example
  value to maximise input coverage
- NEVER alter the parameters or expected_status of any scenario whose description
  contains "(mandatory: values from API specification)"

Return ONLY a JSON object with this structure:
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
            "test_data": {{"param": "value"}},
            "setup_dependencies": [{{"method": "POST", "endpoint": "/api/parent"}}],
            "teardown_dependencies": [{{"method": "DELETE", "endpoint": "/api/parent/{{id}}"}}]
        }}
    ]
}}

Focus on creating realistic, executable test scenarios that follow proper API usage patterns.
"""

    def _parse_llm_response(self, content: str) -> Optional[Dict[str, Any]]:
        """
        Parse LLM response using multiple fallback strategies to handle
        common LLM output issues such as markdown code fences, surrounding
        prose, and unescaped double-quotes inside JSON string values.
        """
        try:
            content = content.strip()

            # Strategy 1: strip markdown code fences (```json...``` or ```...```)
            code_block_pattern = r'^```(?:json)?\s*\n?(.*?)\n?```\s*$'
            match = re.match(code_block_pattern, content, re.DOTALL)
            if match:
                content = match.group(1).strip()

            # Strategy 2: direct parse
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass

            # Strategy 3: extract the outermost JSON object with regex
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

            # Strategy 4: fix unescaped double-quotes inside JSON string values
            # (the root cause of 'Expecting comma delimiter' errors from LLMs)
            try:
                fixed = self._fix_unescaped_quotes(content)
                return json.loads(fixed)
            except (json.JSONDecodeError, Exception):
                pass

            # Strategy 5: combine regex extraction + quote fixing
            if json_match:
                try:
                    fixed = self._fix_unescaped_quotes(json_match.group())
                    return json.loads(fixed)
                except (json.JSONDecodeError, Exception):
                    pass

            self.logger.error(
                "Could not parse LLM response after all recovery strategies"
            )
            return None

        except Exception as e:
            self.logger.error(f"Error parsing LLM response: {e}")
            return None

    @staticmethod
    def _fix_unescaped_quotes(content: str) -> str:
        """
        Attempt to fix unescaped double-quotes inside JSON string values.

        Walks the content character-by-character, tracking whether the
        parser is currently inside a JSON string.  When a double-quote is
        encountered while inside a string, the method looks ahead to decide
        whether it is a legitimate closing quote (followed by a JSON
        structural character: colon, comma, closing brace/bracket) or an
        unescaped interior quote that must be escaped.

        This handles the most common LLM failure mode that produces the
        ``Expecting ',' delimiter`` JSON decode error.
        """
        result: list = []
        in_string = False
        i = 0
        while i < len(content):
            char = content[i]
            # Preserve already-escaped sequences intact
            if char == '\\' and i + 1 < len(content):
                result.append(char)
                result.append(content[i + 1])
                i += 2
                continue
            if char == '"':
                if not in_string:
                    in_string = True
                    result.append(char)
                else:
                    # Look ahead past whitespace to find the next structural char
                    j = i + 1
                    while j < len(content) and content[j] in ' \t\n\r':
                        j += 1
                    if j >= len(content) or content[j] in ':,}]':
                        # Legitimate closing quote
                        in_string = False
                        result.append(char)
                    else:
                        # Interior unescaped quote – escape it
                        result.append('\\"')
            else:
                result.append(char)
            i += 1
        return ''.join(result)

    def _create_enhanced_scenarios(
        self,
        enhanced_data: Dict[str, Any],
        original_scenarios: List[TestScenario],
    ) -> List[TestScenario]:
        """Create enhanced scenarios from LLM response."""
        enhanced_scenarios: List[TestScenario] = []

        try:
            for scenario_data in enhanced_data.get('enhanced_scenarios', []):
                scenario = TestScenario(
                    name=scenario_data.get('name', 'unknown_test'),
                    description=scenario_data.get('description', ''),
                    endpoint=scenario_data.get('endpoint', '/'),
                    method=scenario_data.get('method', 'GET'),
                    parameters=scenario_data.get('parameters', {}),
                    expected_status=scenario_data.get('expected_status', 200),
                    is_negative_test=scenario_data.get('is_negative_test', False),
                    test_data=scenario_data.get('test_data', {}),
                    setup_dependencies=scenario_data.get('setup_dependencies', []),
                    teardown_dependencies=scenario_data.get('teardown_dependencies', []),
                    content_type=scenario_data.get('content_type'),
                )
                enhanced_scenarios.append(scenario)

        except Exception as e:
            self.logger.error(f"Error creating enhanced scenarios: {e}")
            return original_scenarios

        return enhanced_scenarios if enhanced_scenarios else original_scenarios

    # ------------------------------------------------------------------
    # Summary helpers
    # ------------------------------------------------------------------

    def _create_api_summary(self, api_spec: Any) -> Dict[str, Any]:
        """Create API specification summary."""
        return {
            'title': getattr(api_spec, 'title', 'Unknown API'),
            'version': getattr(api_spec, 'version', 'Unknown'),
            'description': getattr(api_spec, 'description', ''),
            'endpoint_count': len(api_spec.endpoints) if hasattr(api_spec, 'endpoints') else 0,
            'base_path': getattr(api_spec, 'base_path', '/'),
        }

    def _create_implementation_summary(
        self, implementation_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create implementation analysis summary."""
        maven_project = implementation_analysis.get('maven_project')
        maven_artifact_id = getattr(maven_project, 'artifact_id', 'Unknown') if maven_project else 'Unknown'

        return {
            'java_classes_count': len(implementation_analysis.get('java_classes', [])),
            'rest_endpoints_count': len(implementation_analysis.get('rest_endpoints', [])),
            'maven_project': maven_artifact_id,
        }
