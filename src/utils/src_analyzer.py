"""
Utility for analyzing Java source code to extract JAX-RS endpoint-to-class mappings.

This module scans a Java source tree looking for:
  - Classes annotated with @Path (JAX-RS resource classes)
  - Methods annotated with @GET/@POST/@PUT/@DELETE/@PATCH
  - Singleton service classes (with getInstance() pattern)
  - Method signatures for each endpoint
  - Application subclasses (extends Application / ResourceConfig) to discover
    resource classes that may not have @Path in the available source files

The extracted information is used to generate accurate Mockito/Jersey Test500 classes
that reference the real implementation classes from api-impl.jar.
"""

import re
import os
import zipfile
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class JavaMethod:
    """Represents a method in a Java class."""
    def __init__(self, name: str, params: List[str], return_type: str = "Object"):
        self.name = name
        self.params = params          # list of param types (e.g. ['String', 'boolean'])
        self.return_type = return_type

    def __repr__(self):
        return f"{self.return_type} {self.name}({', '.join(self.params)})"


class JavaClass:
    """Represents a Java class discovered in the source tree."""
    def __init__(self, fqn: str, simple_name: str, package: str, source_file: str):
        self.fqn = fqn                          # e.g. eu.fayder.restcountries.v1.rest.CountryService
        self.simple_name = simple_name          # e.g. CountryService
        self.package = package                  # e.g. eu.fayder.restcountries.v1.rest
        self.source_file = source_file          # absolute path to .java file (may be '' for inferred)
        self.jaxrs_paths: List[str] = []        # @Path values on the class
        self.http_methods: List[Dict] = []      # list of {http_verb, path, method_name, params}
        self.public_methods: List[JavaMethod] = []
        self.is_singleton: bool = False         # has getInstance() pattern
        self.is_resource: bool = False          # has @Path annotation or discovered via Application
        self.is_inferred: bool = False          # True if discovered via Application, not @Path
        self.superclass: Optional[str] = None

    def __repr__(self):
        tag = "inferred" if self.is_inferred else ("resource" if self.is_resource else "singleton")
        return f"JavaClass({self.fqn}, {tag})"


class EndpointMapping:
    """Maps an API endpoint path+method to the real Java resource and service classes."""
    def __init__(self):
        self.path: str = ""
        self.http_verb: str = ""
        self.resource_class: Optional[JavaClass] = None
        self.service_class: Optional[JavaClass] = None
        self.service_method: Optional[JavaMethod] = None
        self.resource_method_name: str = ""

    def __repr__(self):
        rc = self.resource_class.fqn if self.resource_class else "?"
        sc = self.service_class.fqn if self.service_class else "?"
        sm = self.service_method.name if self.service_method else "?"
        return f"EndpointMapping({self.http_verb} {self.path} -> {rc} / {sc}.{sm})"


# ---------------------------------------------------------------------------
# Source code parser
# ---------------------------------------------------------------------------

class JavaSourceAnalyzer:
    """
    Analyzes a Java source tree (directory or zip) to build endpoint→class mappings.

    Discovery strategy (in order of priority):
    1. Classes annotated with @Path in the source tree.
    2. Classes registered in Application subclasses (extends Application /
       ResourceConfig) via new ClassName() or register(ClassName.class).
       These may not have @Path in the available source files (e.g. they are
       only present in the compiled api-impl.jar).
    3. Singleton classes (getInstance() pattern) used as service dependencies.
    """

    # Regex patterns
    _RE_PACKAGE = re.compile(r'^\s*package\s+([\w.]+)\s*;', re.MULTILINE)
    _RE_IMPORT = re.compile(r'^\s*import\s+([\w.]+)\s*;', re.MULTILINE)
    _RE_CLASS = re.compile(
        r'(?:public\s+)?(?:abstract\s+)?class\s+(\w+)'
        r'(?:\s+extends\s+(\w+))?'
        r'(?:\s+implements\s+[\w,\s<>]+)?'
        r'\s*\{',
        re.MULTILINE
    )
    _RE_PATH_ANNOTATION = re.compile(r'@Path\s*\(\s*["\']([^"\']+)["\']\s*\)')
    _RE_HTTP_VERB = re.compile(r'@(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\b')
    _RE_METHOD_SIG = re.compile(
        r'(?:public|protected)\s+'
        r'(?:(?:static|final|synchronized)\s+)*'
        r'([\w<>\[\]]+(?:\s*<[^>]*>)?)\s+'   # return type
        r'(\w+)\s*\('                           # method name
        r'([^)]*)\)',                           # params
        re.MULTILINE
    )
    _RE_GET_INSTANCE = re.compile(r'public\s+static\s+\w+\s+getInstance\s*\(')
    _RE_PARAM_TYPE = re.compile(
        r'(?:@\w+(?:\([^)]*\))?\s+)*'          # optional annotations
        r'([\w<>\[\]]+(?:\s*<[^>]*>)?)\s+'     # type
        r'(\w+)\s*$'                            # name
    )
    # Matches: new SomeClass() or new some.pkg.SomeClass()
    _RE_NEW_INSTANCE = re.compile(r'\bnew\s+([\w.]+)\s*\(')
    # Matches: register(SomeClass.class) or register(new SomeClass())
    _RE_REGISTER = re.compile(r'\bregister\s*\(\s*(?:new\s+)?([\w.]+)(?:\.class)?\s*\)')
    # Matches: extends Application or extends ResourceConfig
    _RE_EXTENDS_APP = re.compile(
        r'\bclass\s+\w+\s+extends\s+(Application|ResourceConfig|javax\.ws\.rs\.core\.Application)',
        re.MULTILINE
    )

    def __init__(self, src_path: Path):
        """
        Args:
            src_path: Path to a directory containing Java source files,
                      or a .zip/.jar archive containing them.
        """
        self.src_path = src_path
        self._classes: List[JavaClass] = []
        self._endpoint_mappings: List[EndpointMapping] = []
        self._tmp_dir: Optional[str] = None
        # Map: simple_name -> fqn (built from imports)
        self._import_map: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self) -> List[JavaClass]:
        """
        Parse the source tree and return all discovered JavaClass objects.

        Phase 1: Parse all .java files for @Path, getInstance(), public methods.
        Phase 2: Scan Application subclasses to discover resource classes that
                 are instantiated but may not have @Path in available source.
        """
        java_files = self._collect_java_files()
        logger.info(f"JavaSourceAnalyzer: found {len(java_files)} .java files in {self.src_path}")

        # Phase 1: parse all files
        for java_file in java_files:
            try:
                cls = self._parse_java_file(java_file)
                if cls:
                    self._classes.append(cls)
            except Exception as e:
                logger.debug(f"Could not parse {java_file}: {e}")

        # Phase 2: discover resource classes via Application subclasses
        self._discover_resources_via_application(java_files)

        logger.info(
            f"JavaSourceAnalyzer: parsed {len(self._classes)} classes "
            f"({sum(1 for c in self._classes if c.is_resource)} resources "
            f"[{sum(1 for c in self._classes if c.is_resource and c.is_inferred)} inferred], "
            f"{sum(1 for c in self._classes if c.is_singleton)} singletons)"
        )
        return self._classes

    def build_endpoint_mappings(self) -> List[EndpointMapping]:
        """
        Build endpoint→class mappings after analyze() has been called.
        """
        if not self._classes:
            self.analyze()

        resource_classes = [c for c in self._classes if c.is_resource]
        singleton_classes = [c for c in self._classes if c.is_singleton]

        for resource in resource_classes:
            for http_info in resource.http_methods:
                mapping = EndpointMapping()
                mapping.path = http_info.get('full_path', http_info.get('path', ''))
                mapping.http_verb = http_info.get('http_verb', 'GET')
                mapping.resource_class = resource
                mapping.resource_method_name = http_info.get('method_name', '')

                # Find the best matching singleton service
                service = self._find_service_for_resource(resource, singleton_classes)
                mapping.service_class = service

                # Find the best matching service method
                if service:
                    mapping.service_method = self._find_service_method(
                        service, http_info.get('method_name', ''), mapping.path
                    )

                self._endpoint_mappings.append(mapping)

        return self._endpoint_mappings

    def get_classes_summary(self) -> Dict[str, Any]:
        """
        Return a structured summary of all discovered classes, suitable for
        injection into an LLM prompt.
        """
        if not self._classes:
            self.analyze()

        summary = {
            'resource_classes': [],
            'service_classes': [],
            'all_classes': []
        }

        for cls in self._classes:
            entry = {
                'fqn': cls.fqn,
                'simple_name': cls.simple_name,
                'package': cls.package,
                'is_resource': cls.is_resource,
                'is_inferred': cls.is_inferred,
                'is_singleton': cls.is_singleton,
                'jaxrs_paths': cls.jaxrs_paths,
                'http_methods': cls.http_methods,
                'public_methods': [
                    {'name': m.name, 'params': m.params, 'return_type': m.return_type}
                    for m in cls.public_methods
                ],
                'superclass': cls.superclass,
            }
            summary['all_classes'].append(entry)
            if cls.is_resource:
                summary['resource_classes'].append(entry)
            if cls.is_singleton:
                summary['service_classes'].append(entry)

        return summary

    def format_for_prompt(self) -> str:
        """
        Format the source analysis as a concise text block for LLM prompts.
        Focuses on information needed to generate correct Test500 classes.
        """
        if not self._classes:
            self.analyze()

        lines = ["=== API IMPLEMENTATION SOURCE ANALYSIS ===\n"]

        # Resource classes (both @Path annotated and inferred from Application)
        resource_classes = [c for c in self._classes if c.is_resource]
        if resource_classes:
            lines.append("RESOURCE CLASSES (JAX-RS resource classes registered in the application):")
            for cls in resource_classes:
                tag = " [inferred from Application registration]" if cls.is_inferred else " [@Path annotated]"
                lines.append(f"\n  Class: {cls.fqn}{tag}")
                if cls.jaxrs_paths:
                    lines.append(f"  @Path: {cls.jaxrs_paths}")
                if cls.superclass:
                    lines.append(f"  Extends: {cls.superclass}")
                if cls.http_methods:
                    lines.append("  HTTP Methods:")
                    for m in cls.http_methods:
                        path_info = m.get('full_path', m.get('path', ''))
                        lines.append(
                            f"    - {m['http_verb']} {path_info} -> method: {m['method_name']}()"
                        )
                elif cls.is_inferred:
                    lines.append("  (HTTP methods not available in source — class is in api-impl.jar)")

        # Service/Singleton classes
        singleton_classes = [c for c in self._classes if c.is_singleton]
        if singleton_classes:
            lines.append("\nSERVICE CLASSES (Singleton pattern with getInstance()):")
            for cls in singleton_classes:
                lines.append(f"\n  Class: {cls.fqn}")
                if cls.public_methods:
                    lines.append("  Public Methods:")
                    for m in cls.public_methods:
                        params_str = ', '.join(m.params) if m.params else ''
                        lines.append(f"    - {m.return_type} {m.name}({params_str})")

        # Endpoint path to resource class mapping hint
        lines.append("\nENDPOINT-TO-CLASS MAPPING HINTS:")
        lines.append("  Use the following resource classes for the corresponding endpoint path prefixes:")
        for cls in resource_classes:
            if cls.jaxrs_paths:
                for p in cls.jaxrs_paths:
                    lines.append(f"  - Endpoints under '{p}' -> {cls.fqn}")
            else:
                # Infer from class name: CountryRestV1 -> /v1, CountryRestV2 -> /v2
                name = cls.simple_name.lower()
                if 'v1' in name:
                    lines.append(f"  - Endpoints under '/v1/' -> {cls.fqn}")
                elif 'v2' in name:
                    lines.append(f"  - Endpoints under '/v2/' -> {cls.fqn}")
                else:
                    lines.append(f"  - {cls.fqn} (path prefix unknown — infer from class name)")

        lines.append("\n=== END OF SOURCE ANALYSIS ===")
        return '\n'.join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _collect_java_files(self) -> List[str]:
        """Collect all .java file paths from the source path."""
        java_files = []

        if self.src_path.is_dir():
            for root, _, files in os.walk(str(self.src_path)):
                for f in files:
                    if f.endswith('.java'):
                        java_files.append(os.path.join(root, f))

        elif self.src_path.suffix in ('.zip', '.jar'):
            # Extract to temp dir
            self._tmp_dir = tempfile.mkdtemp(prefix='api_src_')
            try:
                with zipfile.ZipFile(str(self.src_path), 'r') as zf:
                    zf.extractall(self._tmp_dir)
                for root, _, files in os.walk(self._tmp_dir):
                    for f in files:
                        if f.endswith('.java'):
                            java_files.append(os.path.join(root, f))
            except Exception as e:
                logger.error(f"Failed to extract {self.src_path}: {e}")

        return java_files

    def _parse_java_file(self, file_path: str) -> Optional[JavaClass]:
        """Parse a single .java file and return a JavaClass object."""
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        # Extract package
        pkg_match = self._RE_PACKAGE.search(content)
        if not pkg_match:
            return None
        package = pkg_match.group(1)

        # Build import map for this file (simple_name -> fqn)
        for imp_match in self._RE_IMPORT.finditer(content):
            fqn_import = imp_match.group(1)
            simple = fqn_import.split('.')[-1]
            self._import_map[simple] = fqn_import

        # Extract class name
        cls_match = self._RE_CLASS.search(content)
        if not cls_match:
            return None
        simple_name = cls_match.group(1)
        superclass = cls_match.group(2)

        fqn = f"{package}.{simple_name}"
        cls = JavaClass(fqn=fqn, simple_name=simple_name, package=package, source_file=file_path)
        cls.superclass = superclass

        # Check for @Path annotation on the class
        class_path_annotations = self._RE_PATH_ANNOTATION.findall(content)
        if class_path_annotations:
            cls.jaxrs_paths = class_path_annotations
            cls.is_resource = True

        # Check for singleton pattern
        if self._RE_GET_INSTANCE.search(content):
            cls.is_singleton = True

        # Extract HTTP method annotations with their associated Java methods
        if cls.is_resource:
            cls.http_methods = self._extract_http_methods(content, cls.jaxrs_paths)

        # Extract public methods (for service classes)
        cls.public_methods = self._extract_public_methods(content)

        return cls

    def _discover_resources_via_application(self, java_files: List[str]) -> None:
        """
        Scan Application subclasses to discover resource classes that are
        registered but may not have @Path in the available source files.

        This handles the common pattern where the Application class imports
        and instantiates resource classes that are compiled into api-impl.jar
        but whose source files are not provided by the user.
        """
        existing_fqns = {c.fqn for c in self._classes}
        existing_simple = {c.simple_name: c for c in self._classes}

        for java_file in java_files:
            try:
                with open(java_file, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()

                # Check if this class extends Application or ResourceConfig
                if not self._RE_EXTENDS_APP.search(content):
                    continue

                logger.info(f"Found Application subclass: {java_file}")

                # Build local import map for this file
                local_imports: Dict[str, str] = {}
                for imp_match in self._RE_IMPORT.finditer(content):
                    fqn_import = imp_match.group(1)
                    simple = fqn_import.split('.')[-1]
                    local_imports[simple] = fqn_import

                # Extract package of this Application class
                pkg_match = self._RE_PACKAGE.search(content)
                app_package = pkg_match.group(1) if pkg_match else ''

                # Find all classes instantiated via new ClassName()
                instantiated: List[str] = []
                for m in self._RE_NEW_INSTANCE.finditer(content):
                    cls_ref = m.group(1).strip()
                    # Accept simple class names (uppercase start) OR fully qualified names (contain '.')
                    if cls_ref and (cls_ref[0].isupper() or '.' in cls_ref):
                        instantiated.append(cls_ref)

                # Find all classes registered via register(ClassName.class)
                for m in self._RE_REGISTER.finditer(content):
                    cls_ref = m.group(1).strip()
                    if cls_ref and (cls_ref[0].isupper() or '.' in cls_ref):
                        instantiated.append(cls_ref)

                # For each discovered class reference, resolve to FQN
                for cls_ref in instantiated:
                    # Skip well-known framework classes
                    if cls_ref in ('ResourceConfig', 'Application', 'HashSet', 'ArrayList',
                                   'HashMap', 'String', 'Object', 'StripeRest'):
                        continue

                    # Resolve FQN
                    if '.' in cls_ref:
                        # Already fully qualified (e.g. eu.fayder.restcountries.v2.rest.CountryRestV2)
                        fqn = cls_ref
                        simple_name = cls_ref.split('.')[-1]
                        pkg = '.'.join(cls_ref.split('.')[:-1])
                    elif cls_ref in local_imports:
                        fqn = local_imports[cls_ref]
                        simple_name = cls_ref
                        pkg = '.'.join(fqn.split('.')[:-1])
                    elif cls_ref in self._import_map:
                        fqn = self._import_map[cls_ref]
                        simple_name = cls_ref
                        pkg = '.'.join(fqn.split('.')[:-1])
                    else:
                        # Assume same package as Application class
                        fqn = f"{app_package}.{cls_ref}"
                        simple_name = cls_ref
                        pkg = app_package

                    # Skip if already discovered
                    if fqn in existing_fqns:
                        continue

                    # Skip if simple name already exists (different package)
                    if simple_name in existing_simple:
                        continue

                    # Create an inferred resource class entry
                    inferred = JavaClass(
                        fqn=fqn,
                        simple_name=simple_name,
                        package=pkg,
                        source_file=''  # not available in source
                    )
                    inferred.is_resource = True
                    inferred.is_inferred = True

                    self._classes.append(inferred)
                    existing_fqns.add(fqn)
                    existing_simple[simple_name] = inferred
                    logger.info(f"Discovered inferred resource class: {fqn}")

            except Exception as e:
                logger.debug(f"Could not scan {java_file} for Application: {e}")

    def _extract_http_methods(self, content: str, class_paths: List[str]) -> List[Dict]:
        """
        Extract HTTP method mappings from a resource class body.
        Returns list of dicts with http_verb, path, method_name, params.
        """
        http_methods = []
        class_base_path = class_paths[0] if class_paths else ''

        # Split content into lines for context-aware parsing
        lines = content.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Look for HTTP verb annotations
            verb_match = self._RE_HTTP_VERB.search(line)
            if verb_match:
                http_verb = verb_match.group(1)

                # Look for @Path in the surrounding lines (within 5 lines)
                method_path = ''
                for j in range(max(0, i - 3), min(len(lines), i + 3)):
                    path_m = self._RE_PATH_ANNOTATION.search(lines[j])
                    if path_m:
                        method_path = path_m.group(1)
                        break

                # Find the method signature in the next few lines
                for j in range(i + 1, min(len(lines), i + 8)):
                    sig_match = self._RE_METHOD_SIG.search(lines[j])
                    if sig_match:
                        method_name = sig_match.group(2)
                        params_raw = sig_match.group(3).strip()
                        params = self._parse_param_types(params_raw)

                        # Build the full path
                        full_path = self._join_paths(class_base_path, method_path)

                        http_methods.append({
                            'http_verb': http_verb,
                            'path': method_path,
                            'full_path': full_path,
                            'method_name': method_name,
                            'params': params,
                        })
                        break
            i += 1

        return http_methods

    def _extract_public_methods(self, content: str) -> List[JavaMethod]:
        """Extract all public non-constructor methods from a class."""
        methods = []
        seen = set()

        for match in self._RE_METHOD_SIG.finditer(content):
            return_type = match.group(1)
            method_name = match.group(2)
            params_raw = match.group(3).strip()

            # Skip constructors (return type matches class name pattern)
            if return_type in ('public', 'protected', 'private', 'static', 'void'):
                continue
            if method_name in ('if', 'for', 'while', 'switch', 'catch', 'return'):
                continue

            key = f"{method_name}({params_raw})"
            if key in seen:
                continue
            seen.add(key)

            params = self._parse_param_types(params_raw)
            methods.append(JavaMethod(
                name=method_name,
                params=params,
                return_type=return_type
            ))

        return methods

    def _parse_param_types(self, params_raw: str) -> List[str]:
        """Parse a parameter list string and return a list of parameter types."""
        if not params_raw.strip():
            return []

        param_types = []
        # Split by comma, handling generics
        depth = 0
        current = ''
        for ch in params_raw:
            if ch in '<([':
                depth += 1
                current += ch
            elif ch in '>)]':
                depth -= 1
                current += ch
            elif ch == ',' and depth == 0:
                param_types.append(self._extract_type_from_param(current.strip()))
                current = ''
            else:
                current += ch
        if current.strip():
            param_types.append(self._extract_type_from_param(current.strip()))

        return [t for t in param_types if t]

    def _extract_type_from_param(self, param: str) -> str:
        """Extract the type from a parameter declaration, stripping annotations."""
        # Remove annotations like @PathParam("x"), @QueryParam("y"), @DefaultValue("z")
        param = re.sub(r'@\w+(?:\s*\([^)]*\))?\s*', '', param).strip()
        # Split by whitespace and take the type (second-to-last token)
        parts = param.split()
        if len(parts) >= 2:
            return parts[-2]  # type is before the variable name
        elif len(parts) == 1:
            return parts[0]
        return ''

    def _join_paths(self, base: str, sub: str) -> str:
        """Join two JAX-RS path segments."""
        base = base.rstrip('/')
        sub = sub.lstrip('/')
        if base and sub:
            return f"{base}/{sub}"
        return base or sub

    def _find_service_for_resource(
        self,
        resource: JavaClass,
        singletons: List[JavaClass]
    ) -> Optional[JavaClass]:
        """
        Find the most likely service class for a given resource class.

        Strategy:
        1. Same package as resource.
        2. Package is a prefix/suffix match of resource package.
        3. Version-based match: if resource has 'v1' in package, prefer service with 'v1'.
        4. Fall back to first singleton.
        """
        if not singletons:
            return None

        # Prefer service in the same package
        same_pkg = [s for s in singletons if s.package == resource.package]
        if same_pkg:
            return same_pkg[0]

        # Version-based match: v1 resource -> v1 service, v2 resource -> v2 service
        resource_pkg_lower = resource.package.lower()
        for version_tag in ['v1', 'v2', 'v3']:
            if version_tag in resource_pkg_lower:
                version_match = [
                    s for s in singletons
                    if version_tag in s.package.lower()
                ]
                if version_match:
                    return version_match[0]

        # Prefer service whose package is a prefix of the resource's package
        pkg_prefix = [
            s for s in singletons
            if resource.package.startswith(s.package) or
               s.package.startswith(resource.package.rsplit('.', 1)[0])
        ]
        if pkg_prefix:
            return pkg_prefix[0]

        # Fall back to first singleton
        return singletons[0]

    def _find_service_method(
        self,
        service: JavaClass,
        resource_method_name: str,
        endpoint_path: str
    ) -> Optional[JavaMethod]:
        """
        Find the service method that best matches the resource method.
        """
        if not service.public_methods:
            return None

        # Exact name match
        exact = [m for m in service.public_methods if m.name == resource_method_name]
        if exact:
            return exact[0]

        # Fuzzy: method name contains path segment keywords
        path_segments = [
            s.lower() for s in endpoint_path.split('/')
            if s and not s.startswith('{')
        ]
        for method in service.public_methods:
            name_lower = method.name.lower()
            if any(seg in name_lower for seg in path_segments):
                return method

        # Fall back to first public method (excluding getInstance)
        non_static = [m for m in service.public_methods if m.name != 'getInstance']
        return non_static[0] if non_static else service.public_methods[0]

    def cleanup(self):
        """Remove temporary directory if created."""
        if self._tmp_dir:
            import shutil
            try:
                shutil.rmtree(self._tmp_dir)
            except Exception:
                pass


def analyze_api_source(src_path: Path) -> JavaSourceAnalyzer:
    """
    Convenience function: create and run a JavaSourceAnalyzer on the given path.

    Args:
        src_path: Path to a directory or zip file containing Java source.

    Returns:
        A fully analyzed JavaSourceAnalyzer instance.
    """
    analyzer = JavaSourceAnalyzer(src_path)
    analyzer.analyze()
    return analyzer
