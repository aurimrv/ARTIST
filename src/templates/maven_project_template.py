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
    """
    
    def __init__(self):
        """Initialize the Maven project template."""
        self.logger.info("Initializing Maven project template")
        
        # POM template for Java 8 compatibility
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
        
        <!-- Plugin versions -->
        <maven-compiler-plugin.version>3.8.1</maven-compiler-plugin.version>
        <maven-surefire-plugin.version>3.0.0-M7</maven-surefire-plugin.version>
        <maven-failsafe-plugin.version>3.0.0-M7</maven-failsafe-plugin.version>
    </properties>

    <dependencies>
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

        # Test configuration template
        self.test_config_template = Template('''package {{ package_name }};

/**
 * Test configuration constants
 * Generated by API Test Generator System
 */
public class TestConfig {
    
    public static final String BASE_URL = System.getProperty("api.base.url", "{{ base_url }}");
    public static final int DEFAULT_TIMEOUT = {{ default_timeout }};
    public static final String API_VERSION = "{{ api_version }}";
    
    // Test data constants
    public static final String TEST_USER_EMAIL = "test@example.com";
    public static final String TEST_USER_NAME = "Test User";
    public static final int TEST_USER_ID = 1;
    
    // Response validation constants
    public static final String JSON_CONTENT_TYPE = "application/json";
    public static final String XML_CONTENT_TYPE = "application/xml";
    
    private TestConfig() {
        // Utility class
    }
}''')

        # Base test class template
        self.base_test_template = Template('''package {{ package_name }};

import org.junit.BeforeClass;
import org.junit.AfterClass;
import io.restassured.RestAssured;
import io.restassured.config.RestAssuredConfig;
import io.restassured.config.HttpClientConfig;
import io.restassured.specification.RequestSpecification;
import io.restassured.http.ContentType;
import static io.restassured.RestAssured.*;

/**
 * Base test class with common setup and utilities
 * Generated by API Test Generator System
 */
public abstract class BaseApiTest {
    
    @BeforeClass
    public static void globalSetUp() {
        // Configure RestAssured
        RestAssured.baseURI = TestConfig.BASE_URL;
        RestAssured.enableLoggingOfRequestAndResponseIfValidationFails();
        
        // Configure timeouts
        RestAssured.config = RestAssuredConfig.config()
            .httpClient(HttpClientConfig.httpClientConfig()
                .setParam("http.connection.timeout", TestConfig.DEFAULT_TIMEOUT * 1000)
                .setParam("http.socket.timeout", TestConfig.DEFAULT_TIMEOUT * 1000));
    }
    
    @AfterClass
    public static void globalTearDown() {
        RestAssured.reset();
    }
    
    /**
     * Create a default request specification with common headers
     */
    protected RequestSpecification givenDefaultRequest() {
        return given()
            .contentType(ContentType.JSON)
            .accept(ContentType.JSON);
    }
    
    /**
     * Create a request specification for XML content
     */
    protected RequestSpecification givenXmlRequest() {
        return given()
            .contentType(ContentType.XML)
            .accept(ContentType.XML);
    }
    
    /**
     * Create a request specification with authentication
     */
    protected RequestSpecification givenAuthenticatedRequest() {
        return givenDefaultRequest()
            .header("Authorization", "Bearer " + getAuthToken());
    }
    
    /**
     * Get authentication token (override in subclasses if needed)
     */
    protected String getAuthToken() {
        return "test-token";
    }
}''')

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
        
        # Create configuration files
        self._create_config_files(project_dir, context, api_info)
        
        # Create base test class
        self._create_base_test_class(project_dir, context, api_info)
        
        # Create resources
        self._create_resources(project_dir)
        
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
        """Create the POM file."""
        pom_content = self.pom_template.render(
            group_id=context.package_name,
            artifact_id=f"{context.package_name.split('.')[-1]}-api-tests",
            version="1.0.0",
            project_name=f"{api_info.get('title', 'API')} Integration Tests",
            api_title=api_info.get('title', 'API'),
            base_url=context.base_url
        )
        
        write_file(project_dir / 'pom.xml', pom_content)
    
    def _create_config_files(self, project_dir: Path, context: ProjectContext, api_info: Dict[str, Any]):
        """Create configuration files."""
        package_path = context.package_name.replace('.', '/')
        
        # Test configuration class
        config_content = self.test_config_template.render(
            package_name=context.package_name,
            base_url=context.base_url,
            default_timeout=30,
            api_version=api_info.get('version', '1.0.0')
        )
        
        write_file(
            project_dir / f'src/test/java/{package_path}/TestConfig.java',
            config_content
        )
    
    def _create_base_test_class(self, project_dir: Path, context: ProjectContext, api_info: Dict[str, Any]):
        """Create base test class."""
        package_path = context.package_name.replace('.', '/')
        
        base_test_content = self.base_test_template.render(
            package_name=context.package_name
        )
        
        write_file(
            project_dir / f'src/test/java/{package_path}/BaseApiTest.java',
            base_test_content
        )
    
    def _create_resources(self, project_dir: Path):
        """Create resource files."""
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

- `BaseApiTest.java` - Base class with common setup and utilities
- `TestConfig.java` - Configuration constants and properties
- Test classes follow the pattern `*Test.java`

## Configuration

Test configuration can be customized through:
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
        """Validate that the Maven project structure is correct."""
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

