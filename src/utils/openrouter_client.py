"""
OpenRouter API client for the API Test Generator System.
"""

import json
import time
from typing import Dict, List, Any, Optional, Union
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
    
    async def generate_test_code(
        self,
        scenarios: str,
        project_context: str,
        model: str,
        **kwargs
    ) -> str:
        """
        Generate JUnit test code based on scenarios.
        
        Args:
            scenarios: Test scenarios JSON
            project_context: Project context information
            model: Model name to use
            **kwargs: Additional parameters
        
        Returns:
            Generated test code
        """
        system_message = """You are an expert Java developer specializing in test automation.
Your task is to generate JUnit 4 test code using Rest Assured for API integration testing.
Follow best practices for test organization, naming, and assertions.
IMPORTANT: Return ONLY the Java code without any explanations, comments, or markdown formatting."""
        
        prompt = f"""Generate JUnit 4 test code using Rest Assured based on the following test scenarios and project context.

Test Scenarios:
{scenarios}

Project Context:
{project_context}

Requirements:
1. Use JUnit 4 annotations (@Test, @Before, @After, etc.)
2. Use Rest Assured for HTTP requests
3. Create separate test methods for each scenario
4. Include proper assertions for status codes and response content
5. Handle both positive and negative test cases
6. Follow Java naming conventions
7. Include necessary imports
8. Make tests independent and repeatable

CRITICAL: Return ONLY the complete Java class code. Do NOT include any explanations, descriptions, or markdown code blocks. Start directly with the package declaration or imports."""
        
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

CRITICAL: Return ONLY the corrected Java code that resolves all compilation errors. Do NOT include any explanations, descriptions, or markdown code blocks. Maintain the original functionality and test logic while fixing syntax and import issues."""
        
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
        system_message = """You are an expert test automation engineer specializing in fixing failing tests.
Your task is to analyze test failures and provide corrected test code that passes reliably.
IMPORTANT: Return ONLY the corrected Java code without any explanations or markdown formatting."""
        
        prompt = f"""Fix the test failures in the following Java test code:

Java Test Code:
```java
{code}
```

Test Failures:
{failures}

CRITICAL: Return ONLY the corrected Java test code that resolves the test failures. Do NOT include any explanations, descriptions, or markdown code blocks. If a test cannot be fixed reliably, add @Ignore annotation with a clear reason."""
        
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

