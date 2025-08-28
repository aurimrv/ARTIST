"""
Java source code parser for the API Test Generator System.
"""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass

from ..utils.logger import LoggerMixin
from ..utils.file_utils import find_files, is_java_file


@dataclass
class JavaMethod:
    """Represents a Java method."""
    name: str
    return_type: str
    parameters: List[Dict[str, str]]
    annotations: List[str]
    visibility: str
    is_static: bool
    body: str
    line_number: int


@dataclass
class JavaClass:
    """Represents a Java class."""
    name: str
    package: str
    imports: List[str]
    annotations: List[str]
    extends: Optional[str]
    implements: List[str]
    methods: List[JavaMethod]
    fields: List[Dict[str, Any]]
    is_interface: bool
    is_abstract: bool
    file_path: Path


@dataclass
class RestEndpoint:
    """Represents a REST endpoint found in Java code."""
    path: str
    method: str
    java_method: str
    java_class: str
    parameters: List[Dict[str, str]]
    return_type: str
    annotations: List[str]


class JavaParser(LoggerMixin):
    """
    Basic Java source code parser.
    
    Focuses on extracting REST endpoints and method signatures
    for test generation purposes.
    """
    
    def __init__(self):
        """Initialize the Java parser."""
        self.logger.info("Initializing Java parser")
        
        # Common JAX-RS annotations
        self.rest_annotations = {
            '@GET', '@POST', '@PUT', '@DELETE', '@PATCH', '@HEAD', '@OPTIONS'
        }
        
        # Path annotations
        self.path_annotations = {'@Path'}
        
        # Parameter annotations
        self.param_annotations = {
            '@PathParam', '@QueryParam', '@FormParam', '@HeaderParam', '@CookieParam'
        }
    
    def parse_project(self, project_path: Union[str, Path]) -> List[JavaClass]:
        """
        Parse all Java files in a project.
        
        Args:
            project_path: Path to the Java project
        
        Returns:
            List of parsed Java classes
        """
        project_path = Path(project_path)
        self.logger.info(f"Parsing Java project: {project_path}")
        
        java_files = find_files(project_path, "*.java", recursive=True)
        self.logger.info(f"Found {len(java_files)} Java files")
        
        classes = []
        for java_file in java_files:
            try:
                java_class = self.parse_file(java_file)
                if java_class:
                    classes.append(java_class)
            except Exception as e:
                self.logger.warning(f"Failed to parse {java_file}: {e}")
        
        self.logger.info(f"Successfully parsed {len(classes)} Java classes")
        return classes
    
    def parse_file(self, file_path: Union[str, Path]) -> Optional[JavaClass]:
        """
        Parse a single Java file.
        
        Args:
            file_path: Path to the Java file
        
        Returns:
            Parsed Java class or None if parsing fails
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Java file not found: {file_path}")
        
        if not is_java_file(file_path):
            raise ValueError(f"Not a Java file: {file_path}")
        
        self.logger.debug(f"Parsing Java file: {file_path}")
        
        try:
            content = file_path.read_text(encoding='utf-8')
            return self._parse_content(content, file_path)
        except Exception as e:
            self.logger.error(f"Failed to parse Java file {file_path}: {e}")
            return None
    
    def _parse_content(self, content: str, file_path: Path) -> Optional[JavaClass]:
        """
        Parse Java content and extract class information.
        
        Args:
            content: Java source code content
            file_path: Path to the source file
        
        Returns:
            Parsed Java class or None
        """
        lines = content.split('\n')
        
        # Extract package
        package = self._extract_package(content)
        
        # Extract imports
        imports = self._extract_imports(content)
        
        # Extract class information
        class_info = self._extract_class_info(content)
        if not class_info:
            return None
        
        # Extract methods
        methods = self._extract_methods(content)
        
        # Extract fields
        fields = self._extract_fields(content)
        
        return JavaClass(
            name=class_info['name'],
            package=package,
            imports=imports,
            annotations=class_info['annotations'],
            extends=class_info['extends'],
            implements=class_info['implements'],
            methods=methods,
            fields=fields,
            is_interface=class_info['is_interface'],
            is_abstract=class_info['is_abstract'],
            file_path=file_path
        )
    
    def _extract_package(self, content: str) -> str:
        """Extract package declaration."""
        match = re.search(r'package\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s*;', content)
        return match.group(1) if match else ""
    
    def _extract_imports(self, content: str) -> List[str]:
        """Extract import statements."""
        imports = []
        for match in re.finditer(r'import\s+(?:static\s+)?([a-zA-Z_][a-zA-Z0-9_.*]*)\s*;', content):
            imports.append(match.group(1))
        return imports
    
    def _extract_class_info(self, content: str) -> Optional[Dict[str, Any]]:
        """Extract class declaration information."""
        # Remove comments and strings to avoid false matches
        cleaned_content = self._remove_comments_and_strings(content)
        
        # Find class declaration - exclude annotations from the match
        class_pattern = r'(?:(public|private|protected)\s+)?(?:(abstract|final)\s+)?(class|interface)\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([^{]+))?'
        
        match = re.search(class_pattern, cleaned_content, re.MULTILINE)
        if not match:
            return None
        
        visibility, modifier, class_type, name, extends, implements = match.groups()
        
        # Extract annotations before class declaration
        annotations = self._extract_annotations_before_position(content, match.start())
        
        # Parse implements clause
        implements_list = []
        if implements:
            implements_list = [impl.strip() for impl in implements.split(',')]
        
        return {
            'name': name,
            'annotations': annotations,
            'extends': extends,
            'implements': implements_list,
            'is_interface': class_type == 'interface',
            'is_abstract': modifier == 'abstract'
        }
    
    def _extract_methods(self, content: str) -> List[JavaMethod]:
        """Extract method declarations with improved REST annotation support."""
        methods = []
        
        # Remove comments to avoid false matches
        cleaned_content = self._remove_comments_and_strings(content)
        
        # More robust method pattern that handles annotations better
        # Look for method signatures that may span multiple lines
        lines = cleaned_content.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines and non-method lines
            if not line or line.startswith('//') or line.startswith('/*'):
                i += 1
                continue
            
            # Check if this could be the start of a method (annotation or method signature)
            if line.startswith('@') or self._looks_like_method_signature(line):
                method_info = self._extract_method_at_position(lines, i)
                if method_info:
                    methods.append(method_info['method'])
                    i = method_info['next_line']
                else:
                    i += 1
            else:
                i += 1
        
        return methods
    
    def _looks_like_method_signature(self, line: str) -> bool:
        """Check if a line looks like a method signature."""
        # Look for patterns like: public Object methodName(
        method_pattern = r'(?:public|private|protected)?\s*(?:static|final|abstract)?\s*\w+(?:<[^>]*>)?\s+\w+\s*\('
        return bool(re.search(method_pattern, line))
    
    def _extract_method_at_position(self, lines: List[str], start_line: int) -> Optional[Dict[str, Any]]:
        """Extract a method starting at the given line position."""
        annotations = []
        method_line = start_line
        
        # Collect annotations
        i = start_line
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('@'):
                annotations.append(line)
                i += 1
            elif line and not line.startswith('//'):
                method_line = i
                break
            else:
                i += 1
        
        if method_line >= len(lines):
            return None
        
        # Find the complete method signature (may span multiple lines)
        method_signature = ""
        brace_count = 0
        paren_count = 0
        found_opening_brace = False
        
        j = method_line
        while j < len(lines):
            line = lines[j].strip()
            method_signature += " " + line
            
            # Count parentheses to find end of parameter list
            paren_count += line.count('(') - line.count(')')
            
            # Look for opening brace
            if '{' in line:
                found_opening_brace = True
                break
            
            # If we have balanced parentheses and see a semicolon, it's an abstract method
            if paren_count == 0 and ';' in line:
                break
            
            j += 1
        
        if not found_opening_brace and ';' not in method_signature:
            return None
        
        # Parse the method signature
        method = self._parse_method_signature(method_signature.strip(), annotations, method_line + 1)
        if method:
            return {
                'method': method,
                'next_line': j + 1
            }
        
        return None
    
    def _parse_method_signature(self, signature: str, annotations: List[str], line_number: int) -> Optional[JavaMethod]:
        """Parse a complete method signature."""
        # Remove throws clause if present
        signature = re.sub(r'\s+throws\s+[^{;]+', '', signature)
        
        # Extract method components
        # Pattern: [visibility] [modifiers] return_type method_name(parameters)
        pattern = r'(?:(public|private|protected)\s+)?(?:(static|final|abstract)\s+)?(\w+(?:<[^>]*>)?)\s+(\w+)\s*\(([^)]*)\)'
        
        match = re.search(pattern, signature)
        if not match:
            return None
        
        visibility, modifier, return_type, name, params_str = match.groups()
        
        # Parse parameters with annotations
        parameters = self._parse_parameters_with_annotations(params_str or "")
        
        # Extract method body (simplified - just mark as present)
        body = "{ ... }" if '{' in signature else ""
        
        return JavaMethod(
            name=name,
            return_type=return_type or "void",
            parameters=parameters,
            annotations=annotations,
            visibility=visibility or "package",
            is_static=modifier == "static",
            body=body,
            line_number=line_number
        )
    
    def _parse_parameters_with_annotations(self, params_str: str) -> List[Dict[str, str]]:
        """Parse method parameters including JAX-RS annotations."""
        if not params_str.strip():
            return []
        
        parameters = []
        
        # Split parameters more carefully to handle annotations
        param_parts = []
        current_param = ""
        paren_depth = 0
        
        for char in params_str:
            if char == ',' and paren_depth == 0:
                param_parts.append(current_param.strip())
                current_param = ""
            else:
                if char == '(':
                    paren_depth += 1
                elif char == ')':
                    paren_depth -= 1
                current_param += char
        
        if current_param.strip():
            param_parts.append(current_param.strip())
        
        for param in param_parts:
            param = param.strip()
            if not param:
                continue
            
            # Extract annotations from parameter
            annotations = []
            remaining_param = param
            
            # Find all annotations at the beginning
            while remaining_param.strip().startswith('@'):
                annotation_match = re.match(r'@\w+(?:\([^)]*\))?\s*', remaining_param)
                if annotation_match:
                    annotations.append(annotation_match.group().strip())
                    remaining_param = remaining_param[annotation_match.end():].strip()
                else:
                    break
            
            # Extract type and name from remaining parameter
            parts = remaining_param.split()
            if len(parts) >= 2:
                param_type = ' '.join(parts[:-1])
                param_name = parts[-1]
                
                parameters.append({
                    'type': param_type,
                    'name': param_name,
                    'annotations': annotations
                })
        
        return parameters
    
    def _extract_fields(self, content: str) -> List[Dict[str, Any]]:
        """Extract field declarations."""
        fields = []
        
        # Simplified field extraction
        field_pattern = r'(?:(public|private|protected)\s+)?(?:(static|final)\s+)?(\w+(?:<[^>]*>)?)\s+(\w+)(?:\s*=\s*[^;]+)?\s*;'
        
        for match in re.finditer(field_pattern, content, re.MULTILINE):
            visibility, modifier, field_type, name = match.groups()
            
            fields.append({
                'name': name,
                'type': field_type,
                'visibility': visibility or "package",
                'is_static': modifier == "static",
                'is_final': modifier == "final"
            })
        
        return fields
    
    def _extract_annotations_before_position(self, content: str, position: int) -> List[str]:
        """Extract annotations before a given position in the content."""
        # Look backwards from the position to find annotations
        before_content = content[:position]
        lines = before_content.split('\n')
        
        annotations = []
        for line in reversed(lines):
            line = line.strip()
            if line.startswith('@'):
                annotations.insert(0, line)
            elif line and not line.startswith('//') and not line.startswith('/*'):
                break
        
        return annotations
    
    def _parse_parameters(self, params_str: str) -> List[Dict[str, str]]:
        """Parse method parameters."""
        if not params_str.strip():
            return []
        
        parameters = []
        param_parts = params_str.split(',')
        
        for param in param_parts:
            param = param.strip()
            if param:
                # Extract annotations
                annotations = []
                while param.startswith('@'):
                    annotation_match = re.match(r'@\w+(?:\([^)]*\))?\s*', param)
                    if annotation_match:
                        annotations.append(annotation_match.group().strip())
                        param = param[annotation_match.end():].strip()
                    else:
                        break
                
                # Extract type and name
                parts = param.split()
                if len(parts) >= 2:
                    param_type = ' '.join(parts[:-1])
                    param_name = parts[-1]
                    
                    parameters.append({
                        'type': param_type,
                        'name': param_name,
                        'annotations': annotations
                    })
        
        return parameters
    
    def _extract_method_body(self, content: str, start_pos: int) -> str:
        """Extract method body (simplified - just returns first few lines)."""
        remaining_content = content[start_pos:]
        lines = remaining_content.split('\n')
        
        # Return first 5 lines of method body for analysis
        body_lines = []
        brace_count = 1
        
        for line in lines:
            if not body_lines and not line.strip():
                continue
            
            body_lines.append(line)
            brace_count += line.count('{') - line.count('}')
            
            if brace_count == 0 or len(body_lines) >= 10:
                break
        
        return '\n'.join(body_lines)
    
    def _remove_comments_and_strings(self, content: str) -> str:
        """Remove comments and string literals to avoid false matches."""
        # This is a simplified implementation
        # Remove single-line comments
        content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
        
        # Remove multi-line comments
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        
        # Remove string literals (simplified)
        content = re.sub(r'"[^"]*"', '""', content)
        content = re.sub(r"'[^']*'", "''", content)
        
        return content
    
    def extract_rest_endpoints(self, java_classes: List[JavaClass]) -> List[RestEndpoint]:
        """
        Extract REST endpoints from parsed Java classes.
        
        Args:
            java_classes: List of parsed Java classes
        
        Returns:
            List of REST endpoints
        """
        endpoints = []
        
        for java_class in java_classes:
            # Check if class has @Path annotation
            class_path = self._extract_path_from_annotations(java_class.annotations)
            
            for method in java_class.methods:
                # Check if method has REST annotations
                http_method = self._extract_http_method(method.annotations)
                if http_method:
                    method_path = self._extract_path_from_annotations(method.annotations)
                    
                    # Combine class path and method path
                    full_path = self._combine_paths(class_path, method_path)
                    
                    endpoints.append(RestEndpoint(
                        path=full_path,
                        method=http_method,
                        java_method=method.name,
                        java_class=java_class.name,
                        parameters=method.parameters,
                        return_type=method.return_type,
                        annotations=method.annotations
                    ))
        
        return endpoints
    
    def _extract_path_from_annotations(self, annotations: List[str]) -> str:
        """Extract path from @Path annotation."""
        for annotation in annotations:
            if annotation.startswith('@Path'):
                # Extract path value
                match = re.search(r'@Path\s*\(\s*"([^"]+)"\s*\)', annotation)
                if match:
                    return match.group(1)
        return ""
    
    def _extract_http_method(self, annotations: List[str]) -> Optional[str]:
        """Extract HTTP method from REST annotations."""
        for annotation in annotations:
            annotation_name = annotation.split('(')[0].strip()
            if annotation_name in self.rest_annotations:
                return annotation_name[1:]  # Remove @ prefix
        return None
    
    def _combine_paths(self, class_path: str, method_path: str) -> str:
        """Combine class and method paths."""
        if not class_path and not method_path:
            return "/"
        
        if not class_path:
            return method_path if method_path.startswith('/') else f"/{method_path}"
        
        if not method_path:
            return class_path if class_path.startswith('/') else f"/{class_path}"
        
        # Ensure proper path combination
        if class_path.endswith('/'):
            class_path = class_path[:-1]
        
        if not method_path.startswith('/'):
            method_path = f"/{method_path}"
        
        return f"{class_path}{method_path}"

