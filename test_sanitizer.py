#!/usr/bin/env python3
"""
Test script for code sanitization functionality.
"""

from src.utils import CodeSanitizer

def test_sanitization():
    """Test the code sanitization with problematic LLM output."""
    
    # Sample problematic LLM output (similar to the uploaded file)
    problematic_output = """Here's a complete, compilable Java test class code that meets your requirements for API integration testing using JUnit 4 and Rest Assured. The class includes both positive and negative test scenarios, proper assertions, and follows best practices for test organization and naming conventions.

```java
package eu.fayder.restcountries.tests;

import org.junit.Before;
import org.junit.Test;
import org.junit.After;
import org.junit.BeforeClass;
import org.junit.AfterClass;
import static org.junit.Assert.*;
import static org.hamcrest.Matchers.*;

import io.restassured.RestAssured;
import io.restassured.response.Response;
import io.restassured.specification.RequestSpecification;
import io.restassured.http.ContentType;

/**
 * Integration tests for the REST Countries API
 */
public class ApiIntegrationTest {

    private static final String BASE_URL = "http://localhost:8090/restcountries-2.0.5";
    private static final int DEFAULT_TIMEOUT = 30;

    @BeforeClass
    public static void setUpClass() {
        RestAssured.baseURI = BASE_URL;
        RestAssured.enableLoggingOfRequestAndResponseIfValidationFails();
    }

    @Test
    public void testGetAllCountries() {
        Response response = RestAssured.given()
            .when()
                .get("/v2/all")
            .then()
                .statusCode(200)
                .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
                .contentType(ContentType.JSON)
                .body("", not(empty()))
                .body("size()", greaterThan(0))
                .extract().response();
    }
}
```

### Explanation:
1. **Test Organization**: The tests are organized into separate methods for positive and negative scenarios.
2. **Assertions**: Each test method includes assertions for status codes, content types, and response bodies.
3. **Helper Methods**: Common functionality is encapsulated in helper methods.

This code is ready to be compiled and run in a Java environment with JUnit 4 and Rest Assured dependencies included."""

    print("🧪 Testing Code Sanitization")
    print("=" * 50)
    
    sanitizer = CodeSanitizer()
    
    print("📝 Original LLM Output:")
    print("-" * 30)
    print(problematic_output[:200] + "..." if len(problematic_output) > 200 else problematic_output)
    print()
    
    print("🧹 Sanitizing...")
    sanitized_code = sanitizer.sanitize_java_code(problematic_output)
    
    print("✅ Sanitized Code:")
    print("-" * 30)
    print(sanitized_code)
    print()
    
    # Verify the sanitization worked
    print("🔍 Verification:")
    print("-" * 30)
    
    # Check that commentary is removed
    has_commentary = any(phrase in sanitized_code.lower() for phrase in [
        "here's a complete", "explanation:", "this code", "the tests are organized"
    ])
    
    # Check that Java code is preserved
    has_java_code = all(element in sanitized_code for element in [
        "package", "import", "public class", "@Test"
    ])
    
    print(f"❌ Contains LLM commentary: {has_commentary}")
    print(f"✅ Contains Java code: {has_java_code}")
    print(f"📏 Original length: {len(problematic_output)} chars")
    print(f"📏 Sanitized length: {len(sanitized_code)} chars")
    print(f"📉 Reduction: {((len(problematic_output) - len(sanitized_code)) / len(problematic_output) * 100):.1f}%")
    
    if not has_commentary and has_java_code:
        print("\n🎉 Sanitization SUCCESSFUL!")
        return True
    else:
        print("\n❌ Sanitization FAILED!")
        return False

if __name__ == "__main__":
    success = test_sanitization()
    exit(0 if success else 1)

