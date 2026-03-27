"""
Maven project template for generating test projects.
"""

from pathlib import Path
from typing import Dict, Any
from jinja2 import Template

from ..config.models import ProjectContext
from ..utils.logger import LoggerMixin
from ..utils.file_utils import ensure_directory, write_file


class MavenProjectTemplate(LoggerMixin):
    """
    Template generator for Maven test projects.

    Creates complete Maven projects with proper structure and dependencies
    for JUnit 4 and Rest Assured testing.

    Each generated test class is self-contained (standalone): it declares
    its own ``@BeforeClass`` / ``@Before`` / ``@After`` setup and does NOT
    extend any base class.  Therefore the auxiliary files
    ``BaseApiTest.java``, ``TestConfig.java``, and ``ApiIntegrationTest.java``
    are intentionally NOT generated.
    """

    def __init__(self):
        """Initialize the Maven project template."""
        self.logger.info("Initializing Maven project template")

        # POM template for Java 8 compatibility
        # Includes Mockito + Jersey Test Framework for *Test500.java classes
        self.pom_template = Template('''<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>{{ group_id }}</groupId>
    <artifactId>{{ artifact_id }}</artifactId>
    <version>{{ version }}</version>
    <packaging>jar</packaging>

    <name>{{ project_name }}</name>
    <description>Generated API integration tests for {{ api_title }}</description>

    <properties>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
        <maven.compiler.source>1.8</maven.compiler.source>
        <maven.compiler.target>1.8</maven.compiler.target>

        <!-- Dependency versions -->
        <junit.version>4.13.2</junit.version>
        <rest-assured.version>4.5.1</rest-assured.version>
        <hamcrest.version>2.2</hamcrest.version>
        <jackson.version>2.13.4</jackson.version>
        <slf4j.version>1.7.36</slf4j.version>
        <logback.version>1.2.12</logback.version>
        <jersey.version>2.40</jersey.version>
        <mockito.version>5.11.0</mockito.version>

        <!-- Plugin versions -->
        <maven-compiler-plugin.version>3.8.1</maven-compiler-plugin.version>
        <maven-surefire-plugin.version>3.0.0-M7</maven-surefire-plugin.version>
        <maven-failsafe-plugin.version>3.0.0-M7</maven-failsafe-plugin.version>
    </properties>

    <dependencies>
{% if api_impl_jar_name %}
        <!-- SUT JAR ({{ api_impl_jar_name }}) — required for *Test500.java Mockito/Jersey tests -->
        <!-- Copied from api-impl argument to src/test/resources/{{ api_impl_jar_name }} -->
        <dependency>
            <groupId>com.example</groupId>
            <artifactId>api-impl</artifactId>
            <version>1.0.0</version>
            <scope>system</scope>
            <systemPath>${project.basedir}/src/test/resources/{{ api_impl_jar_name }}</systemPath>
        </dependency>
{% endif %}

        <!-- Jersey 2.x Test Framework (javax.ws.rs — for *Test500.java) -->
        <dependency>
            <groupId>org.glassfish.jersey.test-framework</groupId>
            <artifactId>jersey-test-framework-core</artifactId>
            <version>${jersey.version}</version>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.glassfish.jersey.test-framework.providers</groupId>
            <artifactId>jersey-test-framework-provider-grizzly2</artifactId>
            <version>${jersey.version}</version>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.glassfish.jersey.inject</groupId>
            <artifactId>jersey-hk2</artifactId>
            <version>${jersey.version}</version>
            <scope>test</scope>
        </dependency>

        <!-- Mockito (for *Test500.java MockedStatic) -->
        <dependency>
            <groupId>org.mockito</groupId>
            <artifactId>mockito-core</artifactId>
            <version>${mockito.version}</version>
            <scope>test</scope>
        </dependency>

        <!-- JUnit 4 -->
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>${junit.version}</version>
            <scope>test</scope>
        </dependency>

        <!-- Rest Assured -->
        <dependency>
            <groupId>io.rest-assured</groupId>
            <artifactId>rest-assured</artifactId>
            <version>${rest-assured.version}</version>
            <scope>test</scope>
        </dependency>

        <!-- Rest Assured JSON Path -->
        <dependency>
            <groupId>io.rest-assured</groupId>
            <artifactId>json-path</artifactId>
            <version>${rest-assured.version}</version>
            <scope>test</scope>
        </dependency>

        <!-- Rest Assured XML Path -->
        <dependency>
            <groupId>io.rest-assured</groupId>
            <artifactId>xml-path</artifactId>
            <version>${rest-assured.version}</version>
            <scope>test</scope>
        </dependency>

        <!-- Hamcrest Matchers -->
        <dependency>
            <groupId>org.hamcrest</groupId>
            <artifactId>hamcrest</artifactId>
            <version>${hamcrest.version}</version>
            <scope>test</scope>
        </dependency>

        <!-- Jackson for JSON processing -->
        <dependency>
            <groupId>com.fasterxml.jackson.core</groupId>
            <artifactId>jackson-databind</artifactId>
            <version>${jackson.version}</version>
            <scope>test</scope>
        </dependency>

        <!-- SLF4J API -->
        <dependency>
            <groupId>org.slf4j</groupId>
            <artifactId>slf4j-api</artifactId>
            <version>${slf4j.version}</version>
            <scope>test</scope>
        </dependency>

        <!-- Logback Classic -->
        <dependency>
            <groupId>ch.qos.logback</groupId>
            <artifactId>logback-classic</artifactId>
            <version>${logback.version}</version>
            <scope>test</scope>
        </dependency>

        <!-- Log4j 1.x (may be required by SUT classes loaded from api-impl.jar) -->
        <dependency>
            <groupId>log4j</groupId>
            <artifactId>log4j</artifactId>
            <version>1.2.17</version>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <!-- Compiler Plugin -->
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <version>${maven-compiler-plugin.version}</version>
                <configuration>
                    <source>1.8</source>
                    <target>1.8</target>
                    <encoding>UTF-8</encoding>
                </configuration>
            </plugin>

            <!-- Surefire Plugin for Unit Tests -->
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>
                <version>${maven-surefire-plugin.version}</version>
                <configuration>
                    <includes>
                        <include>**/*Test.java</include>
                        <include>**/*Tests.java</include>
                    </includes>
                    <excludes>
                        <exclude>**/*IT.java</exclude>
                        <exclude>**/*ITCase.java</exclude>
                    </excludes>
                    <systemPropertyVariables>
                        <api.base.url>{{ base_url }}</api.base.url>
                    </systemPropertyVariables>
                </configuration>
            </plugin>

            <!-- Failsafe Plugin for Integration Tests -->
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-failsafe-plugin</artifactId>
                <version>${maven-failsafe-plugin.version}</version>
                <configuration>
                    <includes>
                        <include>**/*IT.java</include>
                        <include>**/*ITCase.java</include>
                    </includes>
                    <systemPropertyVariables>
                        <api.base.url>{{ base_url }}</api.base.url>
                    </systemPropertyVariables>
                </configuration>
                <executions>
                    <execution>
                        <goals>
                            <goal>integration-test</goal>
                            <goal>verify</goal>
                        </goals>
                    </execution>
                </executions>
            </plugin>
        </plugins>
    </build>

    <profiles>
        <!-- Profile for running tests against different environments -->
        <profile>
            <id>local</id>
            <activation>
                <activeByDefault>true</activeByDefault>
            </activation>
            <properties>
                <api.base.url>{{ base_url }}</api.base.url>
            </properties>
        </profile>

        <profile>
            <id>dev</id>
            <properties>
                <api.base.url>${env.DEV_API_URL}</api.base.url>
            </properties>
        </profile>

        <profile>
            <id>staging</id>
            <properties>
                <api.base.url>${env.STAGING_API_URL}</api.base.url>
            </properties>
        </profile>
    </profiles>
</project>''')

        # Logback configuration template
        self.logback_config_template = Template('''<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
        <encoder>
            <pattern>%d{HH:mm:ss.SSS} [%thread] %-5level %logger{36} - %msg%n</pattern>
        </encoder>
    </appender>

    <appender name="FILE" class="ch.qos.logback.core.FileAppender">
        <file>target/test-logs/api-tests.log</file>
        <encoder>
            <pattern>%d{yyyy-MM-dd HH:mm:ss.SSS} [%thread] %-5level %logger{36} - %msg%n</pattern>
        </encoder>
    </appender>

    <!-- Rest Assured logging -->
    <logger name="io.restassured" level="INFO"/>

    <!-- Root logger -->
    <root level="INFO">
        <appender-ref ref="STDOUT"/>
        <appender-ref ref="FILE"/>
    </root>
</configuration>''')

    def create_maven_project(
        self,
        context: ProjectContext,
        api_info: Dict[str, Any]
    ) -> Path:
        """
        Create a complete Maven project structure.

        Note: ``BaseApiTest.java``, ``TestConfig.java``, and
        ``ApiIntegrationTest.java`` are intentionally NOT created here.
        Each generated test class is self-contained and standalone.

        Args:
            context: Project context
            api_info: API information

        Returns:
            Path to the created Maven project
        """
        project_dir = context.maven_project_dir
        self.logger.info(f"Creating Maven project: {project_dir}")

        # Ensure project directory exists
        ensure_directory(project_dir)

        # Create directory structure
        self._create_directory_structure(project_dir, context.package_name)

        # Generate and write POM file
        self._create_pom_file(project_dir, context, api_info)

        # Create resources (logback config, test.properties, README)
        self._create_resources(project_dir, context)

        self.logger.info(f"Maven project created successfully: {project_dir}")
        return project_dir

    def _create_directory_structure(self, project_dir: Path, package_name: str):
        """Create Maven directory structure."""
        package_path = package_name.replace('.', '/')

        directories = [
            'src/main/java',
            'src/main/resources',
            f'src/test/java/{package_path}',
            'src/test/resources',
            'target/test-logs'
        ]

        for directory in directories:
            ensure_directory(project_dir / directory)

    def _create_pom_file(self, project_dir: Path, context: ProjectContext, api_info: Dict[str, Any]):
        """Create the POM file.

        When ``context.api_impl_path`` is set the ``api-impl`` system-scoped
        dependency is included in the generated pom.xml, referencing the JAR
        by its **original filename** (e.g. ``my-service-1.0.jar``).  When the
        path is ``None`` (``--api-impl`` was not supplied) the dependency block
        is omitted entirely so that Maven does not fail with a missing-file
        error.
        """
        # Derive the JAR filename to embed in the pom.xml (or None to omit).
        api_impl_jar_name: str | None = None
        if context.api_impl_path:
            api_impl_jar_name = context.api_impl_path.name

        pom_content = self.pom_template.render(
            group_id=context.package_name,
            artifact_id=f"{context.package_name.split('.')[-1]}-api-tests",
            version="1.0.0",
            project_name=f"{api_info.get('title', 'API')} Integration Tests",
            api_title=api_info.get('title', 'API'),
            base_url=context.base_url,
            api_impl_jar_name=api_impl_jar_name
        )

        write_file(project_dir / 'pom.xml', pom_content)

    def _create_resources(self, project_dir: Path, context: ProjectContext):
        """Create resource files (logback config, test.properties, README)."""
        # Logback configuration
        logback_content = self.logback_config_template.render()
        write_file(project_dir / 'src/test/resources/logback-test.xml', logback_content)

        # Test properties file
        properties_content = '''# Test configuration properties
# Override these values as needed

# API Configuration
api.timeout=30000
api.retry.attempts=3

# Test Data
test.user.email=test@example.com
test.user.name=Test User

# Logging
logging.level.io.restassured=INFO
logging.level.root=INFO'''

        write_file(project_dir / 'src/test/resources/test.properties', properties_content)

        # README file
        readme_content = f'''# API Integration Tests

This project contains automatically generated integration tests for the API.

Each test class is **standalone and self-contained**: it manages its own
setup and teardown without relying on shared base classes.

## Running Tests

### Prerequisites
- Java 8 or higher
- Maven 3.6 or higher

### Run all tests
```bash
mvn test
```

### Run integration tests only
```bash
mvn failsafe:integration-test
```

### Run tests against different environments
```bash
# Local environment (default)
mvn test -Plocal

# Development environment
mvn test -Pdev -DDEV_API_URL=http://dev-api.example.com

# Staging environment
mvn test -Pstaging -DSTAGING_API_URL=http://staging-api.example.com
```

## Test Structure

Each `*Test.java` class is self-contained:
- Declares its own `@BeforeClass` / `@Before` / `@After` methods.
- Does **not** extend any shared base class.
- Can be compiled and executed independently.

## Configuration

Test configuration can be customised through:
- System properties (`-Dapi.base.url=...`)
- Environment variables
- `test.properties` file

## Generated by API Test Generator System
'''

        write_file(project_dir / 'README.md', readme_content)

    def get_test_class_path(self, project_dir: Path, package_name: str, class_name: str) -> Path:
        """Get the path for a test class file."""
        package_path = package_name.replace('.', '/')
        return project_dir / f'src/test/java/{package_path}/{class_name}.java'

    def add_test_class(self, project_dir: Path, package_name: str, class_name: str, content: str):
        """Add a test class to the Maven project."""
        test_class_path = self.get_test_class_path(project_dir, package_name, class_name)
        write_file(test_class_path, content)
        self.logger.info(f"Added test class: {test_class_path}")

    def validate_project_structure(self, project_dir: Path) -> bool:
        """
        Validate that the Maven project structure is correct.

        Only checks for files that are always generated.
        The auxiliary files ``BaseApiTest.java``, ``TestConfig.java``, and
        ``ApiIntegrationTest.java`` are intentionally excluded from this check.
        """
        required_files = [
            'pom.xml',
            'src/test/resources/logback-test.xml',
            'src/test/resources/test.properties',
            'README.md'
        ]

        for file_path in required_files:
            if not (project_dir / file_path).exists():
                self.logger.error(f"Missing required file: {file_path}")
                return False

        return True
