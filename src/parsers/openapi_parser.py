"""
OpenAPI/Swagger specification parser for the API Test Generator System.
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field

from ..utils.logger import LoggerMixin
from ..utils.file_utils import is_yaml_file, is_json_file


@dataclass
class APIEndpoint:
    """Represents an API endpoint."""
    path: str
    method: str
    summary: Optional[str]
    description: Optional[str]
    parameters: List[Dict[str, Any]]
    request_body: Optional[Dict[str, Any]]
    responses: Dict[str, Dict[str, Any]]
    tags: List[str]
    operation_id: Optional[str]
    # ── New: consolidated examples extracted from the spec ──────────────────
    # Maps parameter name → list of concrete example values.
    # Populated from: param.example, param.examples[*].value,
    # param.x-parameter-examples[*], and schema.examples[*].
    parameter_examples: Dict[str, List[Any]] = field(default_factory=dict)
    # Maps HTTP status code (str) → list of response body examples.
    # Populated from: responses[status].content[*].examples[*].value
    # and responses[status].content[*].example.
    response_examples: Dict[str, List[Any]] = field(default_factory=dict)
    # Raw request body examples extracted from requestBody.content[*].examples
    request_body_examples: List[Any] = field(default_factory=list)
    # Operation-level x-parameter-examples extension.
    # Maps HTTP status code (str) → dict of {param_name: value}.
    # Example: {"200": {"n": 5, "x": 3.14}, "400": {"n": -1, "x": 0.0}}
    # This allows the spec author to provide concrete input sets per expected
    # response code, which the planner uses to generate mandatory test scenarios.
    operation_parameter_examples: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # Inferred Content-Type for the request body based on OpenAPI/Swagger rules
    content_type: Optional[str] = None


@dataclass
class APISchema:
    """Represents an API schema/model."""
    name: str
    type: str
    properties: Dict[str, Any]
    required: List[str]
    description: Optional[str]


@dataclass
class APISpecification:
    """Represents a complete API specification."""
    title: str
    version: str
    description: Optional[str]
    base_url: Optional[str]
    servers: List[Dict[str, Any]]
    endpoints: List[APIEndpoint]
    schemas: Dict[str, APISchema]
    security_schemes: Dict[str, Any]


class OpenAPIParser(LoggerMixin):
    """
    Parser for OpenAPI/Swagger specifications.

    Supports both YAML and JSON formats, OpenAPI 3.x and Swagger 2.x.

    In addition to the standard fields, the parser now extracts all example
    values declared in the specification:

    * **Parameter examples** — collected from (in priority order):
      1. ``param.example`` (single scalar value)
      2. ``param.examples`` (OpenAPI 3.x map of Example Objects)
      3. ``param.x-parameter-examples`` (custom extension, list or map)
      4. ``param.schema.examples`` (JSON Schema draft-07 array)
      5. ``param.schema.example`` (single scalar value)

    * **Response body examples** — collected from:
      1. ``responses[status].content[mediaType].examples[*].value``
      2. ``responses[status].content[mediaType].example``

    * **Request body examples** — collected from:
      1. ``requestBody.content[mediaType].examples[*].value``
      2. ``requestBody.content[mediaType].example``
    """

    def __init__(self):
        """Initialize the OpenAPI parser."""
        self.logger.info("Initializing OpenAPI parser")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_file(self, file_path: Union[str, Path]) -> APISpecification:
        """
        Parse an OpenAPI specification file.

        Args:
            file_path: Path to the OpenAPI specification file

        Returns:
            Parsed API specification

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file format is not supported
            yaml.YAMLError: If YAML parsing fails
            json.JSONDecodeError: If JSON parsing fails
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"API specification file not found: {file_path}")

        self.logger.info(f"Parsing OpenAPI specification: {file_path}")

        if is_yaml_file(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                spec_data = yaml.safe_load(f)
        elif is_json_file(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                spec_data = json.load(f)
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")

        return self._parse_specification(spec_data)

    def parse_dict(self, spec_data: Dict[str, Any]) -> APISpecification:
        """
        Parse an OpenAPI specification from a dictionary.

        Args:
            spec_data: OpenAPI specification as dictionary

        Returns:
            Parsed API specification
        """
        return self._parse_specification(spec_data)

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    def _parse_specification(self, spec_data: Dict[str, Any]) -> APISpecification:
        """Parse the specification data into an APISpecification object."""
        openapi_version = spec_data.get('openapi')
        swagger_version = spec_data.get('swagger')

        if openapi_version:
            self.logger.info(f"Detected OpenAPI version: {openapi_version}")
            return self._parse_openapi_3x(spec_data)
        elif swagger_version:
            self.logger.info(f"Detected Swagger version: {swagger_version}")
            return self._parse_swagger_2x(spec_data)
        else:
            raise ValueError("Unable to detect OpenAPI/Swagger version")

    # ------------------------------------------------------------------
    # OpenAPI 3.x
    # ------------------------------------------------------------------

    def _parse_openapi_3x(self, spec_data: Dict[str, Any]) -> APISpecification:
        """Parse OpenAPI 3.x specification."""
        info = spec_data.get('info', {})
        title = info.get('title', 'Unknown API')
        version = info.get('version', '1.0.0')
        description = info.get('description')

        servers = spec_data.get('servers', [])
        base_url = servers[0].get('url') if servers else None

        endpoints = self._parse_paths_openapi_3x(spec_data.get('paths', {}))
        schemas = self._parse_schemas_openapi_3x(
            spec_data.get('components', {}).get('schemas', {})
        )
        security_schemes = spec_data.get('components', {}).get('securitySchemes', {})

        return APISpecification(
            title=title,
            version=version,
            description=description,
            base_url=base_url,
            servers=servers,
            endpoints=endpoints,
            schemas=schemas,
            security_schemes=security_schemes
        )

    def _parse_swagger_2x(self, spec_data: Dict[str, Any]) -> APISpecification:
        """Parse Swagger 2.x specification."""
        info = spec_data.get('info', {})
        title = info.get('title', 'Unknown API')
        version = info.get('version', '1.0.0')
        description = info.get('description')

        host = spec_data.get('host', 'localhost')
        base_path = spec_data.get('basePath', '')
        schemes = spec_data.get('schemes', ['http'])
        base_url = f"{schemes[0]}://{host}{base_path}"
        servers = [{'url': base_url}]

        global_consumes = spec_data.get('consumes', [])
        endpoints = self._parse_paths_swagger_2x(spec_data.get('paths', {}), global_consumes)
        schemas = self._parse_schemas_swagger_2x(spec_data.get('definitions', {}))
        security_schemes = spec_data.get('securityDefinitions', {})

        return APISpecification(
            title=title,
            version=version,
            description=description,
            base_url=base_url,
            servers=servers,
            endpoints=endpoints,
            schemas=schemas,
            security_schemes=security_schemes
        )

    # ------------------------------------------------------------------
    # Path parsing
    # ------------------------------------------------------------------

    def _parse_paths_openapi_3x(self, paths: Dict[str, Any]) -> List[APIEndpoint]:
        """Parse paths from OpenAPI 3.x specification."""
        endpoints = []
        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method.lower() in ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']:
                    endpoint = self._parse_operation_openapi_3x(path, method.upper(), operation)
                    endpoints.append(endpoint)
        return endpoints

    def _parse_paths_swagger_2x(self, paths: Dict[str, Any], global_consumes: List[str] = None) -> List[APIEndpoint]:
        """Parse paths from Swagger 2.x specification."""
        endpoints = []
        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method.lower() in ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']:
                    endpoint = self._parse_operation_swagger_2x(path, method.upper(), operation, global_consumes)
                    endpoints.append(endpoint)
        return endpoints

    # ------------------------------------------------------------------
    # Operation parsing
    # ------------------------------------------------------------------

    def _parse_operation_openapi_3x(
        self, path: str, method: str, operation: Dict[str, Any]
    ) -> APIEndpoint:
        """Parse a single operation from OpenAPI 3.x."""
        parameters = operation.get('parameters', [])
        request_body = operation.get('requestBody')
        responses = operation.get('responses', {})

        parameter_examples = self._extract_parameter_examples(parameters)
        response_examples = self._extract_response_examples(responses)
        request_body_examples = self._extract_request_body_examples(request_body)
        operation_parameter_examples = self._extract_operation_parameter_examples(operation)

        # Infer Content-Type for OpenAPI 3.x
        content_type = None
        if request_body and 'content' in request_body:
            content_keys = list(request_body['content'].keys())
            if content_keys:
                # Prefer application/json if available, otherwise take the first one
                if 'application/json' in content_keys:
                    content_type = 'application/json'
                else:
                    content_type = content_keys[0]

        return APIEndpoint(
            path=path,
            method=method,
            summary=operation.get('summary'),
            description=operation.get('description'),
            parameters=parameters,
            request_body=request_body,
            responses=responses,
            tags=operation.get('tags', []),
            operation_id=operation.get('operationId'),
            parameter_examples=parameter_examples,
            response_examples=response_examples,
            request_body_examples=request_body_examples,
            operation_parameter_examples=operation_parameter_examples,
            content_type=content_type,
        )

    def _parse_operation_swagger_2x(
        self, path: str, method: str, operation: Dict[str, Any], global_consumes: List[str] = None
    ) -> APIEndpoint:
        """Parse a single operation from Swagger 2.x."""
        parameters = operation.get('parameters', [])
        responses = operation.get('responses', {})

        parameter_examples = self._extract_parameter_examples(parameters)
        response_examples = self._extract_response_examples(responses)
        operation_parameter_examples = self._extract_operation_parameter_examples(operation)

        # Infer Content-Type for Swagger 2.x
        content_type = None
        has_form_data = False
        has_file = False
        has_body = False
        
        for param in parameters:
            param_in = param.get('in')
            if param_in == 'formData':
                has_form_data = True
                if param.get('type') == 'file':
                    has_file = True
            elif param_in == 'body':
                has_body = True
                
        if has_form_data:
            if has_file:
                content_type = 'multipart/form-data'
            else:
                content_type = 'application/x-www-form-urlencoded'
        elif has_body:
            consumes = operation.get('consumes', global_consumes or [])
            if consumes:
                content_type = consumes[0]
            else:
                content_type = 'application/json'

        return APIEndpoint(
            path=path,
            method=method,
            summary=operation.get('summary'),
            description=operation.get('description'),
            parameters=parameters,
            request_body=None,  # Swagger 2.x uses parameters for request body
            responses=responses,
            tags=operation.get('tags', []),
            operation_id=operation.get('operationId'),
            parameter_examples=parameter_examples,
            response_examples=response_examples,
            request_body_examples=[],
            operation_parameter_examples=operation_parameter_examples,
            content_type=content_type,
        )

    # ------------------------------------------------------------------
    # Example extraction helpers
    # ------------------------------------------------------------------

    def _extract_parameter_examples(
        self, parameters: List[Dict[str, Any]]
    ) -> Dict[str, List[Any]]:
        """
        Extract all example values for each parameter.

        Collects from (in order, all sources are merged):
        1. ``param.example``                  — single scalar
        2. ``param.examples[*].value``         — OpenAPI 3.x Example Objects map
        3. ``param.x-parameter-examples``      — custom extension (list or map)
        4. ``param.schema.example``            — single scalar in schema
        5. ``param.schema.examples``           — JSON Schema array

        Returns a dict mapping parameter name → deduplicated list of example values.
        """
        result: Dict[str, List[Any]] = {}

        for param in parameters:
            name = param.get('name')
            if not name:
                continue

            examples: List[Any] = []
            seen: set = set()

            def _add(val: Any) -> None:
                """Add a value if it is not None and not already seen."""
                if val is None:
                    return
                key = repr(val)
                if key not in seen:
                    seen.add(key)
                    examples.append(val)

            # 1. param.example (single value)
            if 'example' in param:
                _add(param['example'])

            # 2. param.examples (OpenAPI 3.x map of Example Objects)
            for ex_obj in param.get('examples', {}).values():
                if isinstance(ex_obj, dict) and 'value' in ex_obj:
                    _add(ex_obj['value'])
                elif not isinstance(ex_obj, dict):
                    _add(ex_obj)

            # 3. param.x-parameter-examples (custom extension)
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

            # 4 & 5. param.schema.example / param.schema.examples
            schema = param.get('schema', {})
            if isinstance(schema, dict):
                if 'example' in schema:
                    _add(schema['example'])
                for v in schema.get('examples', []):
                    _add(v)

            if examples:
                result[name] = examples

        return result

    def _extract_operation_parameter_examples(
        self, operation: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract operation-level ``x-parameter-examples`` extension.

        This extension is placed directly on the operation object (not inside
        individual parameters) and maps each expected HTTP status code to one
        or more complete sets of parameter values that should produce that
        response.

        Two formats are supported:

        **Array format** (preferred — multiple named examples per status code)::

            get:
              x-parameter-examples:
                "200":
                  - {"_name": "typical", "n": 2, "x": 1.5}
                  - {"_name": "edge_case", "n": 0, "x": 1e-10}
                "400":
                  - {"_name": "invalid_type", "n": "abc", "x": 2.0}

        **Dict format** (legacy — single example per status code)::

            get:
              x-parameter-examples:
                "200": {"n": 5, "x": 3.14159}
                "400": {"n": -1, "x": 0.0}

        Returns a dict mapping status code string → list of param dicts.
        Each param dict contains the parameter names as keys; the reserved
        ``_name`` key (if present) is preserved as a scenario label.
        Returns an empty dict if the extension is absent or malformed.
        """
        raw = operation.get('x-parameter-examples')
        if not isinstance(raw, dict):
            return {}

        result: Dict[str, List[Dict[str, Any]]] = {}
        for status_code, param_set in raw.items():
            key = str(status_code)
            if isinstance(param_set, list):
                # Array format: each element is a named example dict
                entries: List[Dict[str, Any]] = []
                for item in param_set:
                    if isinstance(item, dict):
                        entries.append(dict(item))
                if entries:
                    result[key] = entries
            elif isinstance(param_set, dict):
                # Legacy dict format: wrap in a list for uniform handling
                result[key] = [dict(param_set)]
            # Other types are silently ignored (malformed extension)
        return result

    def _extract_response_examples(
        self, responses: Dict[str, Any]
    ) -> Dict[str, List[Any]]:
        """
        Extract response body examples for each HTTP status code.

        Collects from:
        * ``responses[status].content[mediaType].examples[*].value``
        * ``responses[status].content[mediaType].example``

        Returns a dict mapping status code string → list of example values.
        Only the first media type with examples is used per status code.
        """
        result: Dict[str, List[Any]] = {}

        for status_code, response_obj in responses.items():
            if not isinstance(response_obj, dict):
                continue
            examples: List[Any] = []
            seen: set = set()

            def _add(val: Any) -> None:
                if val is None:
                    return
                key = repr(val)[:200]  # cap key length for large objects
                if key not in seen:
                    seen.add(key)
                    examples.append(val)

            content = response_obj.get('content', {})
            for media_obj in content.values():
                if not isinstance(media_obj, dict):
                    continue
                # examples map
                for ex_obj in media_obj.get('examples', {}).values():
                    if isinstance(ex_obj, dict) and 'value' in ex_obj:
                        _add(ex_obj['value'])
                    elif not isinstance(ex_obj, dict):
                        _add(ex_obj)
                # single example
                if 'example' in media_obj:
                    _add(media_obj['example'])

            if examples:
                result[str(status_code)] = examples

        return result

    def _extract_request_body_examples(
        self, request_body: Optional[Dict[str, Any]]
    ) -> List[Any]:
        """
        Extract request body examples.

        Collects from:
        * ``requestBody.content[mediaType].examples[*].value``
        * ``requestBody.content[mediaType].example``

        Returns a deduplicated list of example values.
        """
        if not request_body or not isinstance(request_body, dict):
            return []

        examples: List[Any] = []
        seen: set = set()

        def _add(val: Any) -> None:
            if val is None:
                return
            key = repr(val)[:200]
            if key not in seen:
                seen.add(key)
                examples.append(val)

        for media_obj in request_body.get('content', {}).values():
            if not isinstance(media_obj, dict):
                continue
            for ex_obj in media_obj.get('examples', {}).values():
                if isinstance(ex_obj, dict) and 'value' in ex_obj:
                    _add(ex_obj['value'])
                elif not isinstance(ex_obj, dict):
                    _add(ex_obj)
            if 'example' in media_obj:
                _add(media_obj['example'])

        return examples

    # ------------------------------------------------------------------
    # Schema parsing
    # ------------------------------------------------------------------

    def _parse_schemas_openapi_3x(self, schemas: Dict[str, Any]) -> Dict[str, APISchema]:
        """Parse schemas from OpenAPI 3.x components."""
        parsed_schemas = {}
        for name, schema in schemas.items():
            parsed_schemas[name] = APISchema(
                name=name,
                type=schema.get('type', 'object'),
                properties=schema.get('properties', {}),
                required=schema.get('required', []),
                description=schema.get('description')
            )
        return parsed_schemas

    def _parse_schemas_swagger_2x(self, definitions: Dict[str, Any]) -> Dict[str, APISchema]:
        """Parse schemas from Swagger 2.x definitions."""
        parsed_schemas = {}
        for name, definition in definitions.items():
            parsed_schemas[name] = APISchema(
                name=name,
                type=definition.get('type', 'object'),
                properties=definition.get('properties', {}),
                required=definition.get('required', []),
                description=definition.get('description')
            )
        return parsed_schemas

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_endpoint_by_path_and_method(
        self,
        spec: APISpecification,
        path: str,
        method: str
    ) -> Optional[APIEndpoint]:
        """Find an endpoint by path and method."""
        for endpoint in spec.endpoints:
            if endpoint.path == path and endpoint.method.upper() == method.upper():
                return endpoint
        return None

    def get_endpoints_by_tag(self, spec: APISpecification, tag: str) -> List[APIEndpoint]:
        """Get all endpoints with a specific tag."""
        return [endpoint for endpoint in spec.endpoints if tag in endpoint.tags]

    def get_schema_by_name(self, spec: APISpecification, name: str) -> Optional[APISchema]:
        """Get a schema by name."""
        return spec.schemas.get(name)
