"""
OpenRouter API client for the API Test Generator System.
"""

import json
import os
from datetime import datetime
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
            'HTTP-Referer': 'https://github.com/aurimrv/api-test-generator-system',
            'X-Title': 'API Test Generator'
        }
        
        # Initialize rate limiter
        self.rate_limiter = RateLimiter(
            requests_per_minute=config.rate_limit_requests_per_minute,
            tokens_per_minute=config.rate_limit_tokens_per_minute
        )
        
        # Output directory for llm_interactions files.
        # Defaults to None (falls back to ./llm_interactions) until set by the coordinator.
        self._output_dir: Optional[str] = None
        
        self.logger.info(f"Initialized OpenRouter client with base URL: {self.base_url}")
    
    def set_output_dir(self, output_dir: str) -> None:
        """Set the output directory for llm_interactions files.
        
        Must be called before any LLM requests are made so that all interaction
        files are written inside the run-specific output directory instead of
        the current working directory.
        
        Args:
            output_dir: Path to the run output directory
                        (e.g. '../rest-ncs-reports/generated-tests_2026-04-01_16-40-00').
                        The 'llm_interactions' subdirectory will be created inside it.
        """
        self._output_dir = output_dir
        llm_dir = os.path.join(output_dir, 'llm_interactions')
        os.makedirs(llm_dir, exist_ok=True)
        self.logger.debug(f"llm_interactions directory set to: {llm_dir}")
    
    def _llm_interactions_dir(self) -> str:
        """Return the path to the llm_interactions directory for this run."""
        if self._output_dir:
            return os.path.join(self._output_dir, 'llm_interactions')
        return './llm_interactions'
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=1, max=10),
        reraise=True
    )
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens: int = 102400,
        temperature: float = 0.7,
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

        # Inject seed for reproducibility if provided via kwargs
        # (seed is passed via **kwargs from generate_text -> generate_test_code_with_full_context)
        if 'seed' in payload and payload['seed'] is None:
            del payload['seed']

        #print("### funcao chat_completion")
        #print(f"#### Model: {payload['model']}")
        #print(f"#### Max_Tokens: {payload['max_tokens']}")
        #print(f"#### Temperature: {payload['temperature']}")
        #if 'seed' in payload:
            #print(f"#### Seed: {payload['seed']}")

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

            # Extrair os dados do response.usage
            usage_data = {
                "completion_tokens": usage.get("completion_tokens"),
                "prompt_tokens": usage.get("prompt_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "cost_total": usage.get("cost"),
                "cost_prompt": usage.get("cost_details", {}).get("upstream_inference_prompt_cost"),
                "cost_completion": usage.get("cost_details", {}).get("upstream_inference_completions_cost"),
            }

            _llm_dir = self._llm_interactions_dir()
            os.makedirs(_llm_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
            filename = os.path.join(_llm_dir, f"{timestamp}_cost.json")
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(usage_data, f, indent=2, ensure_ascii=False)
            
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
        max_tokens: int = 102400,
        temperature: float = 0.7,
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

        # ===========================================================
        # DEBUG: Salva prompts enviados ao LLM em ./llm_interactions
        # Pode ser removido futuramente apagando este bloco inteiro.
        # ===========================================================
        try:
            _llm_dir = self._llm_interactions_dir()
            os.makedirs(_llm_dir, exist_ok=True)
            _ts = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
            _op_label = kwargs.pop("_operation_label", "unknown")
            _prompt_filename = os.path.join(_llm_dir, f"{_ts}_{_op_label}_prompt.json")
            _prompt_data = {
                "operation": _op_label,
                "model": model,
                "system_prompt": system_message,
                "user_prompt": prompt,
            }
            with open(_prompt_filename, "w", encoding="utf-8") as _pf:
                json.dump(_prompt_data, _pf, indent=2, ensure_ascii=False)
        except Exception as _e:
            self.logger.warning(f"Failed to save prompt log: {_e}")
        # ===========================================================

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
        scenarios: str,
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

ABSOLUTE CONSTRAINT — HTTP STATUS CODES ARE IMMUTABLE:
The expected HTTP status codes in every @Test method are derived directly from the OpenAPI
specification and MUST NEVER be changed under any circumstances.
- Do NOT change any integer status code literal (e.g. 200, 201, 400, 404, 500).
- Do NOT replace a specific status code with anyOf(), is(), or any flexible matcher.
- Do NOT change a status code even if it is within the same category (e.g. 400 → 404 is FORBIDDEN).
- Do NOT use anyOf() for status code assertions under any circumstances.
- The only permitted fix for a status code assertion is to correct a SYNTAX error in the
  surrounding Java expression while keeping the integer value identical.

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
- HTTP STATUS CODES: every integer status code literal is derived from the OpenAPI spec
  and is IMMUTABLE. Do NOT change 200, 201, 400, 404, 500, or any other status code value.
  Do NOT introduce anyOf() matchers for status codes. Do NOT swap codes within the same
  category (e.g. 400 → 404 is forbidden). The only allowed fix involving a status code
  line is correcting a pure SYNTAX error while keeping the integer value identical.

SOURCE OF TRUTH (Scenarios):
{scenarios}

CRITICAL: Return ONLY the corrected Java code that resolves all compilation errors. You MUST ensure that the status code in each test method in your response matches the expected_status from the 'SOURCE OF TRUTH' scenarios provided above. This is the most important rule. Do NOT include any explanations, descriptions, or markdown code blocks. Maintain the original functionality and test logic while fixing ONLY syntax and import issues."""
        
        kwargs.setdefault("_operation_label", "fix_compilation")
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
        scenarios: str,
        model: str,
        scenario_count: int = 0,
        **kwargs
    ) -> str:
        """
        Fix test failures in Java test code.
        
        Args:
            code: Java test code with failures
            failures: Test failure messages
            model: Model name to use
            scenario_count: Number of original scenarios (used to enforce minimum @Test count)
            **kwargs: Additional parameters
        
        Returns:
            Fixed Java test code
        """
        # FIX #1: Compute the current @Test count from the code so the LLM knows the baseline
        import re as _re
        current_test_count = len(_re.findall(r'@Test', code))

        # FIX #2: Build a minimum-test guard string when scenario_count is known
        min_tests_clause = ""
        if scenario_count > 0:
            min_tests_clause = (
                f"\n\nMINIMUM TEST COUNT ENFORCEMENT:\n"
                f"The original generation produced {current_test_count} @Test methods.\n"
                f"There were {scenario_count} scenarios, so at least {scenario_count} @Test methods "
                f"are mandatory. You MUST NOT reduce the total number of @Test methods below "
                f"{current_test_count}. If you remove a test that cannot be fixed, replace it with "
                f"an @Ignore-annotated stub that still counts as a test method, using a clear "
                f"reason comment explaining why it is ignored.\n"
            )

        system_message = (
            "You are an expert test automation engineer specializing in fixing failing API tests.\n\n"
            "Your core principles:\n"
            "- Analyze failure patterns to understand actual API behavior\n"
            "- Prefer adapting test LOGIC (request parameters, headers, body) to reality over changing status codes\n"
            "- Apply consistent fixes across similar test patterns\n"
            "- Provide working code that reflects actual API behavior.\n\n"
            "ABSOLUTE CONSTRAINT \u2014 HTTP STATUS CODES ARE IMMUTABLE:\n"
            "The expected HTTP status codes in every @Test method are derived directly from the\n"
            "OpenAPI specification and MUST NEVER be changed under any circumstances.\n"
            "- Do NOT change any integer status code literal (e.g. 200, 201, 400, 404, 500).\n"
            "- Do NOT replace a specific status code with anyOf(), is(), or any flexible matcher.\n"
            "- Do NOT change a status code even within the same category\n"
            "  (e.g. 400 \u2192 404 is FORBIDDEN, 200 \u2192 201 is FORBIDDEN, 500 \u2192 503 is FORBIDDEN).\n"
            "- anyOf() is STRICTLY PROHIBITED for status code assertions. Never use it.\n"
            "- If a test fails because the live server returns a different status code than the spec\n"
            "  documents, the test is CORRECT and the server is wrong. Do NOT adapt the test to\n"
            "  match wrong server behavior. Instead, annotate the test with\n"
            "  @Ignore(\"Server returns X but spec requires Y \u2014 server non-compliant\")\n"
            "  and keep the original status code assertion intact.\n\n"
            "WHAT YOU MAY FIX:\n"
            "- Request construction (wrong URL, missing/incorrect parameters, wrong headers, wrong body)\n"
            "- Authentication setup (missing tokens, wrong credentials)\n"
            "- Test data setup (missing prerequisite data, wrong fixture values)\n"
            "- Response body assertions (field names, data types, JSON path expressions)\n"
            "- Java syntax and import errors\n\n"
            "WHAT YOU MUST NEVER CHANGE:\n"
            "- The integer value of any .statusCode(N) assertion\n"
            "- The use of anyOf() for status codes (prohibited entirely)\n"
            "- The HTTP method (GET, POST, PUT, DELETE) of any request\n\n"
            "Use @Ignore only when a test cannot be fixed without violating the spec constraints,\n"
            "with a specific reason comment.\n\n"
            # FIX #3: Explicit instruction to never drop @Test methods during correction
            "CRITICAL TEST COUNT RULE: You MUST preserve or increase the total number of @Test "
            "methods. NEVER remove a @Test method. If a test cannot be made to pass reliably, "
            "annotate it with @Ignore(\"reason\") but keep the method in the class.\n\n"
            "IMPORTANT: Return ONLY the corrected Java code without any explanations or markdown formatting."
        )
        
        prompt = (
            f"Fix the test failures in the following Java test code. Analyze the failure patterns\n"
            f"and adapt the test LOGIC (request construction, test data, body assertions) to match\n"
            f"the actual API behavior. NEVER change HTTP status code assertions.\n\n"
            f"SOURCE OF TRUTH (Scenarios):\n{scenarios}\n\n"
            f"Java Test Code:\n```java\n{code}\n```\n\n"
            f"Test Failures:\n{failures}\n"
            f"{min_tests_clause}\n"
            "IMMUTABLE STATUS CODES REMINDER: Before returning your fix, verify that every\n"
            ".statusCode(N) assertion in the returned code has the EXACT SAME integer N as in\n"
            "the original code above. If you find yourself wanting to change a status code,\n"
            "use @Ignore instead and keep the original assertion intact.\n\n"
            "Apply consistent fixes across similar failures and ensure the corrected tests will "
            "pass reliably against the actual API implementation.\n\n"
            "CRITICAL: Return ONLY the corrected Java test code that resolves the test failures. You MUST ensure that the status code in each test method in your response matches the expected_status from the 'SOURCE OF TRUTH' scenarios provided above. This is the most important rule. "
            "Do NOT include any explanations, descriptions, or markdown code blocks. "
            "If a test cannot be fixed reliably without changing a status code, add @Ignore "
            "annotation with a clear reason but KEEP THE METHOD and its original assertions in the class."
        )

        kwargs.setdefault("_operation_label", "fix_execution")
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

CRITICAL COVERAGE RULE: You MUST generate AT LEAST as many @Test methods as there are
scenarios provided. Each scenario listed in the user prompt MUST have its own dedicated
@Test method. Do NOT merge multiple scenarios into a single @Test method.
Beyond the mandatory minimum, you are expected to ADD extra @Test methods that explore
boundary values, edge cases, and parameter combinations not explicitly listed.

FULL RETCODE COVERAGE RULE: The OpenAPI specification is the single source of truth for
expected HTTP status codes. You MUST generate @Test methods for EVERY response status code
documented in the spec for each endpoint, including:
- 2xx success codes (200, 201, 204, etc.)
- 4xx client error codes (400, 401, 403, 404, 405, 409, 422, etc.)
Do NOT skip any documented status code EXCEPT 5xx codes. Each documented status code for
each endpoint MUST have at least one dedicated @Test method.

EXCLUSION RULE — 5xx CODES: Do NOT generate @Test methods for any 5xx status code
(500, 502, 503, etc.) in this regular test class. HTTP 500 scenarios require a dedicated
Jersey+Mockito test class (*500Test.java) that can simulate service-layer exceptions.
Skip all 5xx scenarios silently — do NOT add @Ignore for them either.

STATUS CODE IMMUTABILITY RULE: Status codes in @Test assertions are derived from the
OpenAPI specification and are IMMUTABLE. Use ONLY the exact integer value documented
in the spec. anyOf() is STRICTLY PROHIBITED for status code assertions. Never use
anyOf(is(200), is(400)) or any similar construct. Each @Test method asserts exactly
one specific status code that matches the scenario it is testing.

IMPORTANT: Return ONLY the Java code without any explanations, comments, or markdown formatting."""
        
        # Format project context
        project_context_str = f"""Project Context:
- Package: {project_context.get('package_name', 'com.example.tests')}
- Test Class Name: {project_context.get('class_name', 'ApiTest')}
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
17. MANDATORY COVERAGE: Generate ONE @Test method per scenario. NEVER merge two scenarios into one @Test method. Each scenario in the list MUST map to exactly one (or more) @Test method(s).
18. EXPAND COVERAGE: After implementing the mandatory @Test methods, add ADDITIONAL @Test methods for boundary values (e.g., zero, negative, maximum, empty string, null) and parameter combinations not listed in the scenarios.
19. FULL RETCODE COVERAGE: For each endpoint in the spec, you MUST generate @Test methods for ALL documented response status codes EXCEPT 5xx codes. Do NOT skip any 2xx or 4xx code. NEVER generate a @Test method that asserts .statusCode(500) or any other 5xx code in this class — those belong exclusively in the *500Test.java class generated separately.
20. STATUS CODE IMMUTABILITY: Each .statusCode(N) assertion MUST use the exact integer N from the OpenAPI spec. anyOf() is STRICTLY PROHIBITED for status code assertions. Do NOT use anyOf(is(200), is(201)) or any similar construct. Do NOT change a status code even within the same HTTP category (e.g. 400 vs 404, 200 vs 201).

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
        # Extract the mandatory minimum count from scenarios_context header if present
        import re as _re
        _min_match = _re.search(r'AT LEAST (\d+) @Test methods', scenarios_context)
        min_tests_reminder = ""
        if _min_match:
            min_count = _min_match.group(1)
            min_tests_reminder = (
                f"\nFINAL MANDATORY CHECK: Before returning, count the @Test methods in your code. "
                f"There MUST be at least {min_count} @Test methods — one for EACH scenario listed above. "
                f"If any scenario is missing a @Test method, add it now. "
                f"Aim for more than {min_count} by adding boundary-value and edge-case tests."
            )

        prompt = f"""{project_context_str}

{openapi_context}

{scenarios_context}
{min_tests_reminder}

CRITICAL: Return ONLY the complete Java class code. Do NOT include any explanations, descriptions, or markdown code blocks. Start directly with the package declaration or imports."""
        
        kwargs.setdefault("_operation_label", "generate_tests")
        return await self.generate_text(
            prompt=prompt,
            model=model,
            system_message=system_message,
            **kwargs
        )

    async def generate_test_code_focused(
        self,
        scenarios_context: str,
        project_context: dict,
        openapi_context: str,
        model: str,
        **kwargs
    ) -> str:
        """
        Generate JUnit test code for a FOCUSED (split_by_endpoint) group.

        This variant uses a stricter prompt that instructs the LLM to generate
        EXACTLY the listed scenarios without expanding to extra boundary/edge cases.
        This prevents token-limit truncation when groups have many scenarios.
        """
        system_message = """You are an expert Java developer specializing in test automation.
Your task is to generate a JUnit 4 test class using Rest Assured for API integration testing.

STRICT SCOPE RULE: Generate ONLY the @Test methods listed in the scenarios below.
Do NOT add extra boundary-value tests or edge-case tests beyond what is specified.
Keep the class small and complete — truncated output is invalid.

EXCLUSION RULE — 5xx CODES: Do NOT generate @Test methods for any scenario whose
expected_status is a 5xx code (500, 502, 503, etc.). HTTP 500 scenarios require a
dedicated Jersey+Mockito test class (*500Test.java). Skip 5xx scenarios silently —
do NOT add @Ignore for them either.

STATUS CODE IMMUTABILITY RULE: Status codes in @Test assertions are derived from the
OpenAPI specification and are IMMUTABLE.
- Use ONLY the exact integer value documented in the spec for each scenario.
- anyOf() is STRICTLY PROHIBITED for status code assertions. Never use anyOf().
- Do NOT change a status code even within the same HTTP category (400 vs 404, 200 vs 201).
- Each @Test method asserts exactly one specific status code matching its scenario.

CRITICAL: Return ONLY the Java code. No explanations. No markdown. No code fences.
Start directly with the package declaration."""

        project_context_str = f"""Project Context:
- Package: {project_context.get('package_name', 'com.example.tests')}
- Test Class Name: {project_context.get('class_name', 'ApiTest')}
- Base URL: {project_context.get('base_url', 'http://localhost:8080')}

REQUIREMENTS:
1. JUnit 4 annotations (@Test, @Before, @After, @BeforeClass)
2. Rest Assured (import static io.restassured.RestAssured.*)
3. Java 8 compatibility
4. @Before setupTestData() — create all necessary fixture data using POST
5. @After cleanupTestData() — delete all created data in reverse dependency order
6. setupTestData() and cleanupTestData() MUST be symmetric: every entity created must be deleted
7. Each @Test method is independent and uses the pre-created fixture data
8. Each @Test must use @Test(timeout = 60000)
9. Validate response body is not null before JsonPath usage (try-catch around JSON parsing)
10. Generate EXACTLY the scenarios listed — one @Test per scenario, no more
11. STATUS CODE IMMUTABILITY: Each .statusCode(N) assertion uses the EXACT integer N from the
    scenario's expected_status field. anyOf() is FORBIDDEN. Do NOT change any status code value.
12. SKIP 5xx SCENARIOS: If any scenario has expected_status 500 or any other 5xx code, skip it
    entirely. Do NOT generate a @Test for it. Do NOT add @Ignore. Just omit it.

IMPORTS REQUIRED:
- import static io.restassured.RestAssured.*;
- import static org.hamcrest.Matchers.*;
- import static org.junit.Assert.*;
- import org.junit.*;
- import io.restassured.response.Response;
- import io.restassured.path.json.JsonPath;
"""

        prompt = f"""{project_context_str}

{openapi_context}

{scenarios_context}

CRITICAL: Return the COMPLETE Java class. If the class cannot fit in one response, reduce
the number of assertions per test method. Never truncate the class — it must end with the
closing brace `}}` of the public class declaration.
Return ONLY the Java class code starting with the package declaration."""

        kwargs.setdefault("_operation_label", "generate_tests_focused")
        return await self.generate_text(
            prompt=prompt,
            model=model,
            system_message=system_message,
            **kwargs
        )

    async def generate_test500_code(
        self,
        endpoints_500: list,
        project_context: dict,
        openapi_context: str,
        model: str,
        **kwargs
    ) -> str:
        """
        Generate a JUnit 4 test class using Mockito and Jersey Test Framework to
        simulate HTTP 500 Internal Server Error responses for endpoints that document
        a 500 response code in the OpenAPI specification.

        The generated class:
        - Extends JerseyTest
        - Overrides configure() to register the real JAX-RS resource class
        - Uses MockedStatic<ServiceClass> to make the service throw RuntimeException
        - Asserts that the response status is exactly 500
        - Is named with the pattern '*500Test.java' (e.g. V1Alpha500Test) so it matches
          the maven-surefire-plugin include pattern '**/*Test.java'

        Args:
            endpoints_500: List of dicts with keys:
                           'path', 'method', 'resource_class', 'service_class',
                           'service_method', 'path_params', 'query_params'
            project_context: Dict with 'package_name', 'class_name' (already has 500 suffix),
                             'base_url'
            openapi_context: Formatted OpenAPI context string
            model: Model name to use
            **kwargs: Additional parameters

        Returns:
            Generated Java test class content as a string
        """
        system_message = """You are an expert Java developer specializing in test automation with
Jersey Test Framework 2.x (org.glassfish.jersey).
Your task is to generate a JUnit 4 test class that uses JerseyTest with a SUBSTITUTE JAX-RS
resource to reliably simulate HTTP 500 Internal Server Error responses.

=== WHY NOT MockedStatic ===
DO NOT use Mockito.mockStatic() to intercept service.getInstance() calls.
Reason: MockedStatic is thread-local. The Jersey test container (Grizzly) executes HTTP
requests on a DIFFERENT thread from the test thread. The mock is invisible to Jersey threads,
so the real service is always called, returning 200 or 404 instead of 500.
This is a fundamental limitation of Mockito's static mocking mechanism.

=== MANDATORY STRATEGY: SUBSTITUTE RESOURCE ===
Instead of mocking, register a SUBSTITUTE JAX-RS resource class in configure() that:
- Has the SAME @Path annotations as the real resource
- Has the SAME @GET/@POST/@PUT/@DELETE + @Path method signatures
- Directly throws RuntimeException inside a try/catch that returns HTTP 500

This substitute resource runs in the Jersey thread and always returns 500, regardless of
any thread-local mocking. No Mockito, no MockedStatic, no service interaction needed.

=== MANDATORY STRUCTURE ===

  public class MyEndpoint500Test extends JerseyTest {

      // Inner static class: substitute resource that always throws 500
      @Path("/v2/lang")
      public static class LangResource500 {
          @GET
          @Path("{lang}")
          public Response getByLanguage(
                  @PathParam("lang") String lang,
                  @QueryParam("fields") String fields) {
              try {
                  throw new RuntimeException("Simulated service error");
              } catch (Exception e) {
                  return Response.status(500)
                          .entity("{\\"status\\":500,\\"message\\":\\"Internal Server Error\\"}") 
                          .build();
              }
          }
      }

      @Override
      protected ResourceConfig configure() {
          enable(TestProperties.LOG_TRAFFIC);
          enable(TestProperties.DUMP_ENTITY);
          // Register ONLY the substitute resource(s), NOT the real resource class
          return new ResourceConfig(LangResource500.class);
      }

      @Test
      public void testGetByLanguage_500InternalServerError() {
          Response response = target("/v2/lang/en").request().get(Response.class);
          assertEquals(500, response.getStatus());
      }
  }

=== MANDATORY RULES ===
1. The outer class MUST extend org.glassfish.jersey.test.JerseyTest.
2. Each endpoint that must return 500 gets its own inner static class annotated with @Path.
   The inner class name should be descriptive, e.g., AlphaResource500, LangResource500.
3. The inner static class MUST have the EXACT same @Path and HTTP method annotations as
   the real resource. Use the source code analysis to get the exact @Path values.
4. Each method in the inner class MUST:
   a. Have the same parameters (@PathParam, @QueryParam) as the real endpoint.
   b. Contain: try { throw new RuntimeException("Simulated service error"); }
               catch (Exception e) { return Response.status(500).entity(...).build(); }
5. The configure() method MUST register ONLY the inner substitute resource classes.
   DO NOT register the real resource class (e.g., CountryRestV2.class).
6. Each @Test method calls the endpoint via target(path).request().get(Response.class)
   and asserts assertEquals(500, response.getStatus()).
7. DO NOT import or use Mockito, MockedStatic, or any mocking library.
8. Use JUnit 4 annotations: @Test from org.junit.Test.
   NEVER use @org.junit.jupiter.api.Test (that is JUnit 5).
9. Java 8 compatibility — no var keyword.
10. The test class name MUST match the class_name in the project context exactly.

=== MANDATORY IMPORTS ===
  import static org.junit.Assert.*;
  import org.junit.Test;
  import org.glassfish.jersey.server.ResourceConfig;
  import org.glassfish.jersey.test.JerseyTest;
  import org.glassfish.jersey.test.TestProperties;
  import javax.ws.rs.GET;  (or POST/PUT/DELETE as needed)
  import javax.ws.rs.Path;
  import javax.ws.rs.PathParam;  (if path params are used)
  import javax.ws.rs.QueryParam;  (if query params are used)
  import javax.ws.rs.core.Response;
NEVER import from `com.sun.jersey.*` — that is Jersey 1.x.
DO NOT import Mockito, MockedStatic, or any mocking library.

=== USING ONLY REAL PATH ANNOTATIONS ===
You MUST use the EXACT @Path values from the real resource class.
DO NOT invent path values. Use the source code analysis or OpenAPI spec to get exact paths.
Example: if the real resource has @Path("v2") on the class and @Path("lang/{lang}") on the
method, the substitute inner class must have @Path("v2/lang") and the method @Path("{lang}").
OR combine them: @Path("v2/lang/{lang}") on the method with no class-level @Path.

=== STRING ESCAPING IN ANNOTATIONS ===
When writing string literals inside Java annotations (e.g., @Ignore("...")), use a SINGLE
backslash to escape inner double quotes: @Ignore("The \"code\" param was not found").
DO NOT use double backslash (\\" is WRONG — it produces a literal backslash in the string).

=== RETURN FORMAT ===
Return ONLY the complete Java class starting with 'package ...'.
Do NOT include any explanations, markdown, or code fences (no ```).
"""

        import json as _json
        endpoints_str = _json.dumps(endpoints_500, indent=2, ensure_ascii=False)

        # Build JAR inventory section (compact: only Resource/Service/Rest classes)
        jar_inventory = project_context.get('jar_inventory', {})
        jar_inventory_str = ""
        if jar_inventory:
            relevant = {
                k: v for k, v in jar_inventory.items()
                if k.endswith(('Resource', 'Service', 'Rest', 'Application', 'Filter'))
            }
            if relevant:
                jar_inventory_str = "\nCLASSES AVAILABLE IN api-impl.jar:\n"
                for simple_name, full_names in relevant.items():
                    jar_inventory_str += f"  {simple_name}: {', '.join(full_names)}\n"

        # Build source analysis section (real class/method mappings from --api-src)
        src_analysis = project_context.get('src_analysis', '')
        src_analysis_section = ""
        if src_analysis:
            src_analysis_section = f"""

=== AUTHORITATIVE SOURCE CODE ANALYSIS ===
The following information was extracted directly from the API implementation source code.
You MUST use these exact fully-qualified class names for ALL imports and references.
Do NOT invent class names. Do NOT use placeholder names like 'V1AlphacodesResource'.

{src_analysis}
=== END OF SOURCE CODE ANALYSIS ==="""

        # Build the endpoint descriptors section
        # Each descriptor now contains enriched fields from source analysis:
        #   resource_class (FQN), service_class (FQN), service_method, service_method_params
        endpoints_enriched_note = ""
        if src_analysis:
            endpoints_enriched_note = (
                "\nNOTE: The endpoint descriptors below have been enriched with REAL class names "
                "from the source code analysis above. The 'resource_class' and 'service_class' "
                "fields contain fully-qualified names that MUST be used verbatim in imports.\n"
            )

        # Detect classes with conflicting simple names across different packages
        # (e.g., CountryService in both v1 and v2) — these must be referenced by FQN
        conflict_warning = ""
        if src_analysis:
            # Extract all FQNs from the src_analysis string to detect name conflicts
            import re as _re
            fqn_pattern = _re.compile(r'([a-z][\w.]+\.([A-Z][\w]+))')
            fqn_matches = fqn_pattern.findall(src_analysis)
            simple_to_fqns: dict = {}
            for fqn, simple in fqn_matches:
                simple_to_fqns.setdefault(simple, set()).add(fqn)
            conflicts = {s: list(fqns) for s, fqns in simple_to_fqns.items() if len(fqns) > 1}
            if conflicts:
                conflict_lines = []
                for simple, fqns in conflicts.items():
                    conflict_lines.append(
                        f"  '{simple}' exists in multiple packages: {', '.join(sorted(fqns))}"
                    )
                conflict_warning = (
                    "\n=== AMBIGUOUS CLASS NAMES (REQUIRE FQN IN CODE) ===\n"
                    "The following class names exist in MULTIPLE packages.\n"
                    "For these classes:\n"
                    "  - Import ONLY the one most relevant to this test class's API version.\n"
                    "  - Reference any other version using its FULL QUALIFIED NAME inline in code.\n"
                    "  - NEVER write 'import X as Y' — Java has no import aliases.\n"
                    "Ambiguous classes:\n"
                    + "\n".join(conflict_lines)
                    + "\n=== END AMBIGUOUS CLASSES ===\n"
                )

        prompt = f"""Generate a JUnit 4 test class using Jersey 2.x (org.glassfish.jersey) to
simulate HTTP 500 Internal Server Error responses for the following endpoints.

Project Context:
- Package: {project_context.get('package_name', 'com.example.api.tests')}
- Test Class Name: {project_context.get('class_name', 'Api500Test')}
  (this name MUST be used as the public class name — it follows the pattern *500Test so it
   matches the maven-surefire-plugin include pattern '**/*Test.java')

{openapi_context}
{jar_inventory_str}
{src_analysis_section}
Endpoints that document HTTP 500 in the spec:
{endpoints_str}

Generate the class following the MANDATORY STRATEGY from the system message:

1. For each endpoint above, create ONE inner static class (annotated with @Path) that acts
   as a substitute resource. The inner class:
   a. Has the EXACT same @Path values as the real endpoint (use the OpenAPI spec paths above).
   b. Has the EXACT same HTTP method annotation (@GET, @POST, etc.).
   c. Has the same @PathParam and @QueryParam parameters as the real endpoint.
   d. Contains: try {{ throw new RuntimeException("Simulated service error"); }}
                catch (Exception e) {{ return Response.status(500).entity(
                    "{{\\"status\\":500,\\"message\\":\\"Internal Server Error\\"}}").build(); }}

2. The configure() method registers ONLY the inner substitute resource classes:
   return new ResourceConfig(InnerClass1.class, InnerClass2.class, ...);
   DO NOT register any real resource class from the API implementation.

3. For each endpoint, generate one @Test method:
   - Calls the endpoint via target(path).request().get(Response.class) (Jersey 2.x).
   - Asserts assertEquals(500, response.getStatus()).
   - NEVER uses resource().path(...) — that is Jersey 1.x.

4. PATH CONSTRUCTION: Build the target path from the OpenAPI spec path.
   Example: for endpoint path "/v2/lang/{{lang}}", use target("/v2/lang/en").
   For path "/v2/alpha" with query param "codes", use target("/v2/alpha").queryParam("codes", "US;CA").

5. DO NOT use Mockito, MockedStatic, or any mocking library.

CRITICAL STRING ESCAPING:
- Inside @Ignore("...") or any annotation string, escape inner quotes with ONE backslash: \"
- WRONG: @Ignore("The \\"code\\" param")  → produces literal backslashes
- CORRECT: @Ignore("The \"code\" param")  → produces correct Java string

CRITICAL: Return ONLY the complete Java class starting with 'package ...'.
Do NOT include any explanations, markdown, or code fences (no ```)."""


        kwargs.setdefault("_operation_label", "generate_tests_500")
        return await self.generate_text(
            prompt=prompt,
            model=model,
            system_message=system_message,
            **kwargs
        )

    async def generate_enhanced_test_scenarios(
        self,
        prompt: str,
        model: str,
        scenario_count: int = 0,
        **kwargs
    ) -> str:
        """
        Generate enhanced test scenarios with LLM analysis using the
        caller-supplied prompt.

        The prompt is built by ``PlannerAgent._build_enhancement_prompt``
        and already contains the full API context, the existing scenarios,
        and a strict JSON output format instruction.

        Args:
            prompt: Complete prompt string produced by the PlannerAgent.
            model: Model name to use.
            scenario_count: Number of input scenarios; used to enforce minimum
                            output count in the system message.
            **kwargs: Additional parameters forwarded to ``generate_text``.

        Returns:
            Raw LLM response string (JSON expected).
        """
        # FIX #4: Embed the input scenario count in the system prompt so the
        # model cannot silently reduce the scenario set during enhancement.
        min_count_instruction = ""
        if scenario_count > 0:
            min_count_instruction = (
                f"\n\nCRITICAL SCENARIO COUNT RULE: The input contains {scenario_count} scenarios. "
                f"Your enhanced_scenarios array MUST contain AT LEAST {scenario_count} entries. "
                f"You may ADD new scenarios, but you must NEVER drop or merge existing ones. "
                f"Each original scenario must appear (possibly improved) in the output."
            )

        system_message = (
            "You are an expert test architect specializing in REST API testing. "
            "Return ONLY valid JSON as instructed in the user prompt – "
            "no prose, no markdown fences, no extra keys."
            + min_count_instruction
        )

        kwargs.setdefault("_operation_label", "enhance_scenarios")
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
