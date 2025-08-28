"""
Maven project parser for the API Test Generator System.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass

from ..utils.logger import LoggerMixin
from ..utils.file_utils import is_xml_file


@dataclass
class MavenDependency:
    """Represents a Maven dependency."""
    group_id: str
    artifact_id: str
    version: Optional[str]
    scope: Optional[str]
    type: Optional[str]


@dataclass
class MavenPlugin:
    """Represents a Maven plugin."""
    group_id: str
    artifact_id: str
    version: Optional[str]
    configuration: Dict[str, Any]
    executions: List[Dict[str, Any]]


@dataclass
class MavenProject:
    """Represents a Maven project."""
    group_id: str
    artifact_id: str
    version: str
    packaging: str
    name: Optional[str]
    description: Optional[str]
    properties: Dict[str, str]
    dependencies: List[MavenDependency]
    plugins: List[MavenPlugin]
    parent: Optional[Dict[str, str]]
    modules: List[str]
    project_dir: Path
    source_directories: List[Path]
    test_directories: List[Path]


class MavenParser(LoggerMixin):
    """
    Maven project parser.
    
    Parses pom.xml files and extracts project structure information.
    """
    
    def __init__(self):
        """Initialize the Maven parser."""
        self.logger.info("Initializing Maven parser")
        self.namespace = {'maven': 'http://maven.apache.org/POM/4.0.0'}
    
    def parse_project(self, project_path: Union[str, Path]) -> Optional[MavenProject]:
        """
        Parse a Maven project.
        
        Args:
            project_path: Path to the Maven project directory
        
        Returns:
            Parsed Maven project or None if parsing fails
        """
        project_path = Path(project_path)
        pom_file = project_path / 'pom.xml'
        
        if not pom_file.exists():
            self.logger.error(f"pom.xml not found in {project_path}")
            return None
        
        self.logger.info(f"Parsing Maven project: {project_path}")
        
        try:
            return self._parse_pom(pom_file, project_path)
        except Exception as e:
            self.logger.error(f"Failed to parse Maven project {project_path}: {e}")
            return None
    
    def _parse_pom(self, pom_file: Path, project_dir: Path) -> MavenProject:
        """
        Parse a pom.xml file.
        
        Args:
            pom_file: Path to pom.xml
            project_dir: Project directory
        
        Returns:
            Parsed Maven project
        """
        tree = ET.parse(pom_file)
        root = tree.getroot()
        
        # Handle namespace
        if root.tag.startswith('{'):
            # Extract namespace from root tag
            namespace_uri = root.tag[1:root.tag.index('}')]
            self.namespace = {'maven': namespace_uri}
        
        # Parse basic project information
        group_id = self._get_text(root, './/maven:groupId')
        artifact_id = self._get_text(root, './/maven:artifactId')
        version = self._get_text(root, './/maven:version')
        packaging = self._get_text(root, './/maven:packaging', default='jar')
        name = self._get_text(root, './/maven:name')
        description = self._get_text(root, './/maven:description')
        
        # Parse parent
        parent = self._parse_parent(root)
        
        # Parse properties
        properties = self._parse_properties(root)
        
        # Parse dependencies
        dependencies = self._parse_dependencies(root)
        
        # Parse plugins
        plugins = self._parse_plugins(root)
        
        # Parse modules
        modules = self._parse_modules(root)
        
        # Determine source and test directories
        source_dirs = self._get_source_directories(project_dir)
        test_dirs = self._get_test_directories(project_dir)
        
        return MavenProject(
            group_id=group_id or "",
            artifact_id=artifact_id or "",
            version=version or "1.0.0",
            packaging=packaging,
            name=name,
            description=description,
            properties=properties,
            dependencies=dependencies,
            plugins=plugins,
            parent=parent,
            modules=modules,
            project_dir=project_dir,
            source_directories=source_dirs,
            test_directories=test_dirs
        )
    
    def _get_text(self, root: ET.Element, xpath: str, default: Optional[str] = None) -> Optional[str]:
        """Get text content from XML element using XPath."""
        element = root.find(xpath, self.namespace)
        return element.text if element is not None else default
    
    def _parse_parent(self, root: ET.Element) -> Optional[Dict[str, str]]:
        """Parse parent project information."""
        parent_elem = root.find('.//maven:parent', self.namespace)
        if parent_elem is None:
            return None
        
        return {
            'group_id': self._get_text(parent_elem, './/maven:groupId', ''),
            'artifact_id': self._get_text(parent_elem, './/maven:artifactId', ''),
            'version': self._get_text(parent_elem, './/maven:version', '')
        }
    
    def _parse_properties(self, root: ET.Element) -> Dict[str, str]:
        """Parse project properties."""
        properties = {}
        props_elem = root.find('.//maven:properties', self.namespace)
        
        if props_elem is not None:
            for prop in props_elem:
                # Remove namespace from tag name
                tag_name = prop.tag
                if '}' in tag_name:
                    tag_name = tag_name.split('}')[1]
                properties[tag_name] = prop.text or ""
        
        return properties
    
    def _parse_dependencies(self, root: ET.Element) -> List[MavenDependency]:
        """Parse project dependencies."""
        dependencies = []
        deps_elem = root.find('.//maven:dependencies', self.namespace)
        
        if deps_elem is not None:
            for dep_elem in deps_elem.findall('.//maven:dependency', self.namespace):
                dependency = MavenDependency(
                    group_id=self._get_text(dep_elem, './/maven:groupId', ''),
                    artifact_id=self._get_text(dep_elem, './/maven:artifactId', ''),
                    version=self._get_text(dep_elem, './/maven:version'),
                    scope=self._get_text(dep_elem, './/maven:scope'),
                    type=self._get_text(dep_elem, './/maven:type')
                )
                dependencies.append(dependency)
        
        return dependencies
    
    def _parse_plugins(self, root: ET.Element) -> List[MavenPlugin]:
        """Parse build plugins."""
        plugins = []
        
        # Check both build/plugins and build/pluginManagement/plugins
        plugin_paths = [
            './/maven:build/maven:plugins',
            './/maven:build/maven:pluginManagement/maven:plugins'
        ]
        
        for plugin_path in plugin_paths:
            plugins_elem = root.find(plugin_path, self.namespace)
            if plugins_elem is not None:
                for plugin_elem in plugins_elem.findall('.//maven:plugin', self.namespace):
                    plugin = self._parse_plugin(plugin_elem)
                    plugins.append(plugin)
        
        return plugins
    
    def _parse_plugin(self, plugin_elem: ET.Element) -> MavenPlugin:
        """Parse a single plugin."""
        group_id = self._get_text(plugin_elem, './/maven:groupId', 'org.apache.maven.plugins')
        artifact_id = self._get_text(plugin_elem, './/maven:artifactId', '')
        version = self._get_text(plugin_elem, './/maven:version')
        
        # Parse configuration
        config_elem = plugin_elem.find('.//maven:configuration', self.namespace)
        configuration = self._parse_configuration(config_elem) if config_elem is not None else {}
        
        # Parse executions
        executions = []
        executions_elem = plugin_elem.find('.//maven:executions', self.namespace)
        if executions_elem is not None:
            for exec_elem in executions_elem.findall('.//maven:execution', self.namespace):
                execution = {
                    'id': self._get_text(exec_elem, './/maven:id', ''),
                    'phase': self._get_text(exec_elem, './/maven:phase'),
                    'goals': [goal.text for goal in exec_elem.findall('.//maven:goal', self.namespace)]
                }
                executions.append(execution)
        
        return MavenPlugin(
            group_id=group_id,
            artifact_id=artifact_id,
            version=version,
            configuration=configuration,
            executions=executions
        )
    
    def _parse_configuration(self, config_elem: ET.Element) -> Dict[str, Any]:
        """Parse plugin configuration."""
        config = {}
        
        for child in config_elem:
            tag_name = child.tag
            if '}' in tag_name:
                tag_name = tag_name.split('}')[1]
            
            if len(child) > 0:
                # Has child elements
                config[tag_name] = self._parse_configuration(child)
            else:
                # Text content
                config[tag_name] = child.text or ""
        
        return config
    
    def _parse_modules(self, root: ET.Element) -> List[str]:
        """Parse project modules."""
        modules = []
        modules_elem = root.find('.//maven:modules', self.namespace)
        
        if modules_elem is not None:
            for module_elem in modules_elem.findall('.//maven:module', self.namespace):
                if module_elem.text:
                    modules.append(module_elem.text)
        
        return modules
    
    def _get_source_directories(self, project_dir: Path) -> List[Path]:
        """Get source directories for the project."""
        source_dirs = []
        
        # Standard Maven source directories
        standard_sources = [
            'src/main/java',
            'src/main/resources'
        ]
        
        for src_dir in standard_sources:
            full_path = project_dir / src_dir
            if full_path.exists():
                source_dirs.append(full_path)
        
        return source_dirs
    
    def _get_test_directories(self, project_dir: Path) -> List[Path]:
        """Get test directories for the project."""
        test_dirs = []
        
        # Standard Maven test directories
        standard_tests = [
            'src/test/java',
            'src/test/resources'
        ]
        
        for test_dir in standard_tests:
            full_path = project_dir / test_dir
            if full_path.exists():
                test_dirs.append(full_path)
        
        return test_dirs
    
    def has_dependency(self, project: MavenProject, group_id: str, artifact_id: str) -> bool:
        """
        Check if project has a specific dependency.
        
        Args:
            project: Maven project
            group_id: Dependency group ID
            artifact_id: Dependency artifact ID
        
        Returns:
            True if dependency exists
        """
        for dep in project.dependencies:
            if dep.group_id == group_id and dep.artifact_id == artifact_id:
                return True
        return False
    
    def get_dependency(self, project: MavenProject, group_id: str, artifact_id: str) -> Optional[MavenDependency]:
        """
        Get a specific dependency.
        
        Args:
            project: Maven project
            group_id: Dependency group ID
            artifact_id: Dependency artifact ID
        
        Returns:
            Dependency or None if not found
        """
        for dep in project.dependencies:
            if dep.group_id == group_id and dep.artifact_id == artifact_id:
                return dep
        return None
    
    def get_plugin(self, project: MavenProject, group_id: str, artifact_id: str) -> Optional[MavenPlugin]:
        """
        Get a specific plugin.
        
        Args:
            project: Maven project
            group_id: Plugin group ID
            artifact_id: Plugin artifact ID
        
        Returns:
            Plugin or None if not found
        """
        for plugin in project.plugins:
            if plugin.group_id == group_id and plugin.artifact_id == artifact_id:
                return plugin
        return None
    
    def is_web_project(self, project: MavenProject) -> bool:
        """Check if this is a web project (WAR packaging)."""
        return project.packaging.lower() == 'war'
    
    def is_spring_project(self, project: MavenProject) -> bool:
        """Check if this is a Spring project."""
        spring_deps = [
            'org.springframework',
            'org.springframework.boot'
        ]
        
        for dep in project.dependencies:
            if any(dep.group_id.startswith(spring_dep) for spring_dep in spring_deps):
                return True
        return False
    
    def is_jaxrs_project(self, project: MavenProject) -> bool:
        """Check if this is a JAX-RS project."""
        jaxrs_deps = [
            ('javax.ws.rs', 'javax.ws.rs-api'),
            ('org.jboss.resteasy', 'resteasy-jaxrs'),
            ('org.glassfish.jersey.core', 'jersey-server')
        ]
        
        for group_id, artifact_id in jaxrs_deps:
            if self.has_dependency(project, group_id, artifact_id):
                return True
        return False

