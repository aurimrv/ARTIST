"""
OpenRouter API client for the API Test Generator System.
"""

from typing import Dict, List, Any, Optional
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config.models import OpenRouterConfig
from .logger import LoggerMixin
from .rate_limiter import RateLimiter


class OpenRouterClient(LoggerMixin):
    """
    Client for interacting with the OpenRouter API.
    
    Provides rate limiting, retry logic, and standardized interfaces
    for making LLM requests.
    """
    
    def __init__(self, config: OpenRouterConfig):
        """
        Initialize the OpenRouter client.
        
        Args:
            config: OpenRouter configuration
        """
        self.config = config
        self.base_url = config.api_base.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {config.api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://github.com/api-test-generator',
            'X-Title': 'API Test Generator'
        }
        
        # Initialize rate limiter
        self.rate_limiter = RateLimiter(
            requests_per_minute=config.rate_limit_requests_per_minute,
            tokens_per_minute=config.rate_limit_tokens_per_minute
        )
        
        self.logger.info(f"Initialized OpenRouter client with base URL: {self.base_url}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=1, max=10),
        reraise=True
    )
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens: int = 16000,
        temperature: float = 0.1,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a chat completion using OpenRouter API.
        
        Args:
            messages: List of message dictionaries
            model: Model name to use
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            stream: Whether to stream the response
            **kwargs: Additional parameters
        
        Returns:
            API response dictionary
        
        Raises:
            requests.RequestException: If API request fails
        """
        # Apply rate limiting
        await self.rate_limiter.acquire(estimated_tokens=max_tokens)
        
        payload = {
            'model': model,
            'messages': messages,
            'max_tokens': max_tokens,
            'temperature': temperature,
            'stream': stream,
            **kwargs
        }
        
        print(f"#### Model: {payload['model']}")
        print(f"#### Max_Tokens: {payload['max_tokens']}")
        print(f"#### Temperature: {payload['temperature']}")
        print(f"#### Message: {payload['messages']}")

        self.logger.debug(f"Making chat completion request with model: {model}")
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Update rate limiter with actual usage
            usage = result.get('usage', {})
            if usage:
                await self.rate_limiter.update_usage(
                    tokens_used=usage.get('total_tokens', 0)
                )
            
            self.logger.debug(f"Chat completion successful. Usage: {usage}")
            return result
            
        except requests.RequestException as e:
            self.logger.error(f"OpenRouter API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    self.logger.error(f"Error details: {error_detail}")
                except:
                    self.logger.error(f"Response content: {e.response.text}")
            raise
    
    async def generate_text(
        self,
        prompt: str,
        model: str,
        max_tokens: int = 4000,
        temperature: float = 0.1,
        system_message: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Generate text using a simple prompt.
        
        Args:
            prompt: Input prompt
            model: Model name to use
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            system_message: Optional system message
            **kwargs: Additional parameters
        
        Returns:
            Generated text
        """
        messages = []
        
        if system_message:
            messages.append({
                'role': 'system',
                'content': system_message
            })
        
        messages.append({
            'role': 'user',
            'content': prompt
        })
        
        response = await self.chat_completion(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
        
        if 'choices' in response and response['choices']:
            return response['choices'][0]['message']['content']
        else:
            raise ValueError("No response generated")
    
    async def analyze_code(
        self,
        code: str,
        language: str,
        task: str,
        model: str,
        **kwargs
    ) -> str:
        """
        Analyze code using LLM.
        
        Args:
            code: Source code to analyze
            language: Programming language
            task: Analysis task description
            model: Model name to use
            **kwargs: Additional parameters
        
        Returns:
            Analysis result
        """
        system_message = f"""You are an expert {language} code analyzer. 
Your task is to {task}.
Provide clear, accurate, and actionable analysis."""
        
        prompt = f"""Please analyze the following {language} code:

```{language}
{code}
```

Task: {task}

Provide your analysis in a structured format."""
        
        return await self.generate_text(
            prompt=prompt,
            model=model,
            system_message=system_message,
            **kwargs
        )
    
    async def generate_test_scenarios(
        self,
        api_spec: str,
        implementation_info: str,
        model: str,
        **kwargs
    ) -> str:
        """
        Generate test scenarios based on API specification and implementation.
        
        Args:
            api_spec: API specification content
            implementation_info: Implementation analysis
            model: Model name to use
            **kwargs: Additional parameters
        
        Returns:
            Generated test scenarios
        """
        system_message = """You are an expert test architect specializing in REST API testing.
Your task is to create comprehensive test scenarios for integration testing using JUnit 4 and Rest Assured.
Focus on realistic scenarios that cover both positive and negative test cases."""
        
        prompt = f"""Based on the following API specification and implementation analysis, 
create comprehensive test scenarios for integration testing.

API Specification:
{api_spec}

Implementation Analysis:
{implementation_info}

Please generate test scenarios that include:
1. Positive test cases (happy path)
2. Negative test cases (error conditions)
3. Edge cases and boundary conditions
4. Parameter validation tests
5. Response format validation
6. Assume API database is empty. Create a setup method populating the database using POST method with all parameters used during test.

Format the output as a structured JSON with the following schema:
{{
  "scenarios": [
    {{
      "name": "test_method_name",
      "description": "Test description",
      "endpoint": "/api/path",
      "method": "GET|POST|PUT|DELETE",
      "parameters": {{}},
      "expected_status": 200,
      "expected_response_schema": {{}},
      "is_negative_test": false,
      "test_data": {{}}
    }}
  ]
}}"""
        
        return await self.generate_text(
            prompt=prompt,
            model=model,
            system_message=system_message,
            **kwargs
        )

    
    async def fix_compilation_errors(
        self,
        code: str,
        errors: str,
        model: str,
        **kwargs
    ) -> str:
        """
        Fix compilation errors in Java code.
        
        Args:
            code: Java code with compilation errors
            errors: Compilation error messages
            model: Model name to use
            **kwargs: Additional parameters
        
        Returns:
            Fixed Java code
        """
        system_message = """You are an expert Java developer specializing in fixing compilation errors.
Your task is to analyze compilation errors and provide corrected code that compiles successfully.
IMPORTANT: Return ONLY the corrected Java code without any explanations or markdown formatting."""
        
        prompt = f"""Fix the compilation errors in the following Java code:

Java Code:
```java
{code}
```

Compilation Errors:
{errors}

CRITICAL COMPILATION FIX REQUIREMENTS:
1. Fix ONLY compilation errors (syntax, imports, method signatures, etc.)
2. DO NOT regenerate or modify test scenarios - they are correct as generated
3. DO NOT change test method logic or assertions
4. DO NOT add, remove, or modify @Test methods
5. Focus ONLY on making the existing code compile successfully
6. Preserve all existing test scenarios and their logic
7. Fix only: missing imports, syntax errors, method signatures, variable declarations
8. Maintain the original test structure and functionality

WHAT TO FIX:
- Missing import statements
- Incorrect method signatures
- Variable declaration issues
- Syntax errors (missing semicolons, brackets, etc.)
- Type mismatches
- Access modifier issues

WHAT NOT TO CHANGE:
- Test method names or logic
- Test scenarios or assertions
- @Test method content
- Setup method logic (unless syntax error)
- Test data or expected results

CRITICAL: Return ONLY the corrected Java code that resolves all compilation errors. Do NOT include any explanations, descriptions, or markdown code blocks. Maintain the original functionality and test logic while fixing ONLY syntax and import issues."""
        
        return await self.generate_text(
            prompt=prompt,
            model=model,
            system_message=system_message,
            **kwargs
        )
    
    async def fix_test_failures(
        self,
        code: str,
        failures: str,
        model: str,
        **kwargs
    ) -> str:
        """
        Fix test failures in Java test code.
        
        Args:
            code: Java test code with failures
            failures: Test failure messages
            model: Model name to use
            **kwargs: Additional parameters
        
        Returns:
            Fixed Java test code
        """
        system_message = """You are an expert test automation engineer specializing in fixing failing API 
        tests.\n\nYour core principles:\n- Analyze failure patterns to understand actual API behavior\n- 
        Prefer adapting expectations to reality over ignoring tests\n- Apply consistent fixes across similar 
        test patterns\n- Provide working code that reflects actual API behavior\n\nStatus code flexibility 
        guidelines:\n- Client errors (4xx): 400↔404↔405↔409 are interchangeable for invalid inputs\n- Server 
        errors (5xx): Accept 500/502/503 if consistently returned\n- Success codes: 200↔201↔204 acceptable 
        based on operation type\n\nWhen changing expected status codes, add explanatory comments:\n// API 
        returns {actual} instead of {expected} - {reason}\n\nUse @Ignore only for clearly unimplemented 
        endpoints with specific reasons.\n\nIMPORTANT: Return ONLY the corrected Java code without any 
        explanations or markdown formatting."""
        
        prompt = f"""Fix the test failures in the following Java test code. Analyze the failure patterns 
        and adapt the tests to match the actual API behavior:\n\nJava Test Code:
```java
{code}
```

Test Failures:
{failures}

Apply consistent fixes across similar failures and ensure the corrected tests will pass reliably against the actual API implementation.

CRITICAL: Return ONLY the corrected Java test code that resolves the test failures. Do NOT include any explanations, descriptions, or markdown code blocks. If a test cannot be fixed reliably, add @Ignore annotation with a clear reason."""

        return await self.generate_text(
            prompt=prompt,
            model=model,
            system_message=system_message,
            **kwargs
        )
    

    async def generate_test_code_with_full_context(
        self,
        scenarios_context: str,
        project_context: dict,
        openapi_context: str,
        model: str,
        **kwargs
    ) -> str:
        """
        Generate JUnit test code with full project context and requirements.
        
        Args:
            scenarios_context: Formatted test scenarios
            project_context: Project context dictionary with package, class name, etc.
            openapi_context: OpenAPI specification context
            model: Model name to use
            **kwargs: Additional parameters
        
        Returns:
            Generated test code
        """
        system_message = """You are an expert Java developer specializing in test automation.
Your task is to generate JUnit 4 test code using Rest Assured for API integration testing.
Follow best practices for test organization, naming, and assertions.
IMPORTANT: Return ONLY the Java code without any explanations, comments, or markdown formatting."""
        
        # Format project context
        project_context_str = f"""Project Context:
- Package: {project_context.get('package_name', 'com.example.tests')}
- Test Class Name: {project_context.get('class_name', 'ApiIntegrationTest')}
- Base URL: {project_context.get('base_url', 'http://localhost:8080')}
- Output Directory: {project_context.get('output_dir', 'output')}

CRITICAL REQUIREMENTS:
1. Use JUnit 4 annotations (@Test, @Before, @After, @BeforeClass, @AfterClass)
2. Use Rest Assured framework for HTTP requests (import static io.restassured.RestAssured.*)
3. Java 8 compatibility (no newer Java features like var, lambda expressions in complex scenarios)
4. Create a comprehensive @Before setupTestData() method with fixtures
5. Create a comprehensive @After cleanupTestData() method that reliably removes all data created by setupTestData()
6. Ensure cleanupTestData() uses DELETE requests in the correct dependency order (child entities first, then parents)
7. setupTestData() and cleanupTestData() MUST always be complementary and symmetric: every entity created in setup must be deleted in cleanup, and no entity should be deleted unless it was created in setup.
8. The setup method MUST populate the database using POST requests with all necessary data
9. Ensure POST operations are executed before GET, PUT, or DELETE operations
10. Each test method should be independent and repeatable
11. Use proper assertions for status codes and response content
12. Handle both positive and negative test cases appropriately
13. Include proper error handling and meaningful test names
14. Minimize test failures by ensuring proper data setup and teardown
15. Follow Java naming conventions and best practices
16. ALL @Test methods MUST explicitly declare a timeout of 60000 milliseconds using @Test(timeout = 60000)

SETUP AND CLEANUP METHOD REQUIREMENTS:
- Create a @Before method called setupTestData()
- Create a @After method called cleanupTestData()
- setupTestData() must always create a consistent set of fixture data that is sufficient for all test scenarios.
- This includes creating at least one parent entity and all required child entities so that any test can run independently without missing data.
- setupTestData() must use RestAssured POST endpoints to create fixture data in the correct order (parents before children)
- cleanupTestData() must use RestAssured DELETE endpoints to remove all created data in reverse order (children before parents) without assertions
- cleanupTestData() must always remove exactly the data created in setupTestData(), in reverse dependency order.
- setupTestData() and cleanupTestData() must be resilient to empty or missing response bodies.
- Both setupTestData() and cleanupTestData() must be symmetric: everything created must be deleted, and nothing should be deleted if it was not created in setupTestData().
- They must use request parameters as fallback identifiers when no response body is returned.
- Never fail a test due to attempting to parse an empty response.
- Only @Before method must validate status codes and ensure operations succeeded
- Both methods must handle errors gracefully to avoid test contamination
- Create entities in the correct order (parent entities before child entities)
- Use realistic test data that reflects real-world scenarios

TEST METHOD REQUIREMENTS:
- Each @Test method should test exactly one scenario
- Use descriptive method names that explain what is being tested
- Include both positive and negative test cases
- Use RestAssured's given().when().then() pattern
- Assert on status codes, response body content, and headers when relevant
- Use JsonPath for response validation when testing JSON APIs
- Handle authentication if required by the API

IMPORTS REQUIRED:
- import static io.restassured.RestAssured.*;
- import static org.hamcrest.Matchers.*;
- import static org.junit.Assert.*;
- import org.junit.*;
- import io.restassured.response.Response;
- import io.restassured.path.json.JsonPath;

ERROR HANDLING AND RESPONSE VALIDATION:
- Always check response.getStatusCode() before parsing JSON
- Validate response body is not null or empty before using JsonPath
- NEVER assume that a response body contains JSON
- ALWAYS check responseBody != null AND !responseBody.trim().isEmpty() before calling JsonPath
- If the response body is empty, do NOT attempt to parse it as JSON
- When identifiers are required later (e.g., IDs, names), use known input values from the request if the response does not provide them
- If JSON parsing fails or the field is missing, handle gracefully and skip JsonPath usage
- For POST/PUT endpoints that may return only a status code (201/204) without a body, assert only on the status code and headers
- Use try-catch blocks around JSON parsing operations
- Provide meaningful error messages in assertions
- Use assumeTrue() for test preconditions
- Handle network timeouts and connection issues gracefully
"""        
        prompt = f"""{project_context_str}

{openapi_context}

{scenarios_context}

CRITICAL: Return ONLY the complete Java class code. Do NOT include any explanations, descriptions, or markdown code blocks. Start directly with the package declaration or imports."""
        
        return await self.generate_text(
            prompt=prompt,
            model=model,
            system_message=system_message,
            **kwargs
        )

    async def generate_enhanced_test_scenarios(
        self,
        api_spec: str,
        implementation_info: str,
        existing_scenarios: str,
        model: str,
        **kwargs
    ) -> str:
        """
        Generate enhanced test scenarios with LLM analysis.
        
        Args:
            api_spec: API specification content
            implementation_info: Implementation analysis
            existing_scenarios: Existing scenarios to enhance
            model: Model name to use
            **kwargs: Additional parameters
        
        Returns:
            Enhanced test scenarios
        """
        system_message = """You are an expert test architect specializing in REST API testing.
Your task is to enhance existing test scenarios by adding more comprehensive test cases,
improving test data, and ensuring better coverage of edge cases and error conditions."""
        
        prompt = f"""Enhance the following test scenarios based on the API specification and implementation analysis.

API Specification:
{api_spec}

Implementation Analysis:
{implementation_info}

Existing Scenarios:
{existing_scenarios}

Please enhance the scenarios by:
1. Adding missing edge cases and boundary conditions
2. Improving test data to be more realistic and comprehensive
3. Adding more negative test cases for error conditions
4. Ensuring proper parameter validation tests
5. Adding tests for different content types and response formats
6. Considering authentication and authorization scenarios if applicable

Maintain the same JSON format as the existing scenarios but with enhanced content."""
        
        return await self.generate_text(
            prompt=prompt,
            model=model,
            system_message=system_message,
            **kwargs
        )

    async def get_available_models(self) -> List[Dict[str, Any]]:
        """
        Get list of available models from OpenRouter.
        
        Returns:
            List of available models
        """
        try:
            response = requests.get(
                f"{self.base_url}/models",
                headers=self.headers,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            return result.get('data', [])
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to get available models: {e}")
            return []

