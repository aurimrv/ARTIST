"""
OpenAPI/Swagger specification parser for the API Test Generator System.
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass

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
    """
    
    def __init__(self):
        """Initialize the OpenAPI parser."""
        self.logger.info("Initializing OpenAPI parser")
    
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
        
        # Load the specification content
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
    
    def _parse_specification(self, spec_data: Dict[str, Any]) -> APISpecification:
        """
        Parse the specification data into an APISpecification object.
        
        Args:
            spec_data: Raw specification data
        
        Returns:
            Parsed API specification
        """
        # Detect OpenAPI version
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
    
    def _parse_openapi_3x(self, spec_data: Dict[str, Any]) -> APISpecification:
        """Parse OpenAPI 3.x specification."""
        info = spec_data.get('info', {})
        
        # Parse basic info
        title = info.get('title', 'Unknown API')
        version = info.get('version', '1.0.0')
        description = info.get('description')
        
        # Parse servers
        servers = spec_data.get('servers', [])
        base_url = servers[0].get('url') if servers else None
        
        # Parse paths/endpoints
        endpoints = self._parse_paths_openapi_3x(spec_data.get('paths', {}))
        
        # Parse schemas
        schemas = self._parse_schemas_openapi_3x(
            spec_data.get('components', {}).get('schemas', {})
        )
        
        # Parse security schemes
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
        
        # Parse basic info
        title = info.get('title', 'Unknown API')
        version = info.get('version', '1.0.0')
        description = info.get('description')
        
        # Build base URL from host, basePath, and schemes
        host = spec_data.get('host', 'localhost')
        base_path = spec_data.get('basePath', '')
        schemes = spec_data.get('schemes', ['http'])
        base_url = f"{schemes[0]}://{host}{base_path}"
        
        servers = [{'url': base_url}]
        
        # Parse paths/endpoints
        endpoints = self._parse_paths_swagger_2x(spec_data.get('paths', {}))
        
        # Parse definitions (schemas)
        schemas = self._parse_schemas_swagger_2x(spec_data.get('definitions', {}))
        
        # Parse security definitions
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
    
    def _parse_paths_openapi_3x(self, paths: Dict[str, Any]) -> List[APIEndpoint]:
        """Parse paths from OpenAPI 3.x specification."""
        endpoints = []
        
        for path, path_item in paths.items():
            # Skip path-level parameters for now
            for method, operation in path_item.items():
                if method.lower() in ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']:
                    endpoint = self._parse_operation_openapi_3x(path, method.upper(), operation)
                    endpoints.append(endpoint)
        
        return endpoints
    
    def _parse_paths_swagger_2x(self, paths: Dict[str, Any]) -> List[APIEndpoint]:
        """Parse paths from Swagger 2.x specification."""
        endpoints = []
        
        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method.lower() in ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']:
                    endpoint = self._parse_operation_swagger_2x(path, method.upper(), operation)
                    endpoints.append(endpoint)
        
        return endpoints
    
    def _parse_operation_openapi_3x(self, path: str, method: str, operation: Dict[str, Any]) -> APIEndpoint:
        """Parse a single operation from OpenAPI 3.x."""
        return APIEndpoint(
            path=path,
            method=method,
            summary=operation.get('summary'),
            description=operation.get('description'),
            parameters=operation.get('parameters', []),
            request_body=operation.get('requestBody'),
            responses=operation.get('responses', {}),
            tags=operation.get('tags', []),
            operation_id=operation.get('operationId')
        )
    
    def _parse_operation_swagger_2x(self, path: str, method: str, operation: Dict[str, Any]) -> APIEndpoint:
        """Parse a single operation from Swagger 2.x."""
        return APIEndpoint(
            path=path,
            method=method,
            summary=operation.get('summary'),
            description=operation.get('description'),
            parameters=operation.get('parameters', []),
            request_body=None,  # Swagger 2.x uses parameters for request body
            responses=operation.get('responses', {}),
            tags=operation.get('tags', []),
            operation_id=operation.get('operationId')
        )
    
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
    
    def get_endpoint_by_path_and_method(
        self, 
        spec: APISpecification, 
        path: str, 
        method: str
    ) -> Optional[APIEndpoint]:
        """
        Find an endpoint by path and method.
        
        Args:
            spec: API specification
            path: Endpoint path
            method: HTTP method
        
        Returns:
            Matching endpoint or None
        """
        for endpoint in spec.endpoints:
            if endpoint.path == path and endpoint.method.upper() == method.upper():
                return endpoint
        return None
    
    def get_endpoints_by_tag(self, spec: APISpecification, tag: str) -> List[APIEndpoint]:
        """
        Get all endpoints with a specific tag.
        
        Args:
            spec: API specification
            tag: Tag name
        
        Returns:
            List of matching endpoints
        """
        return [endpoint for endpoint in spec.endpoints if tag in endpoint.tags]
    
    def get_schema_by_name(self, spec: APISpecification, name: str) -> Optional[APISchema]:
        """
        Get a schema by name.
        
        Args:
            spec: API specification
            name: Schema name
        
        Returns:
            Matching schema or None
        """
        return spec.schemas.get(name)

