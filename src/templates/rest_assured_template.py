"""
Rest Assured template utilities.
"""

from typing import Dict, List, Any
from ..utils.logger import LoggerMixin


class RestAssuredTemplate(LoggerMixin):
    """
    Utility class for generating Rest Assured code snippets.
    
    Provides helper methods for generating common Rest Assured patterns
    and request/response handling code.
    """
    
    def __init__(self):
        """Initialize the Rest Assured template."""
        self.logger.info("Initializing Rest Assured template")
    
    def generate_get_request(self, endpoint: str, params: Dict[str, Any] = None) -> str:
        """Generate a GET request snippet."""
        lines = ["given()"]
        
        if params:
            for key, value in params.items():
                if isinstance(value, str):
                    lines.append(f'    .queryParam("{key}", "{value}")')
                else:
                    lines.append(f'    .queryParam("{key}", {value})')
        
        lines.extend([
            ".when()",
            f'    .get("{endpoint}")',
            ".then()",
            "    .statusCode(200)"
        ])
        
        return "\n".join(lines)
    
    def generate_post_request(self, endpoint: str, body: Dict[str, Any] = None) -> str:
        """Generate a POST request snippet."""
        lines = [
            "given()",
            "    .contentType(ContentType.JSON)"
        ]
        
        if body:
            import json
            body_json = json.dumps(body, indent=2)
            escaped_body = body_json.replace('"', '\\"')
            lines.append(f'    .body("{escaped_body}")')
        
        lines.extend([
            ".when()",
            f'    .post("{endpoint}")',
            ".then()",
            "    .statusCode(201)"
        ])
        
        return "\n".join(lines)
    
    def generate_put_request(self, endpoint: str, body: Dict[str, Any] = None) -> str:
        """Generate a PUT request snippet."""
        lines = [
            "given()",
            "    .contentType(ContentType.JSON)"
        ]
        
        if body:
            import json
            body_json = json.dumps(body, indent=2)
            escaped_body = body_json.replace('"', '\\"')
            lines.append(f'    .body("{escaped_body}")')
        
        lines.extend([
            ".when()",
            f'    .put("{endpoint}")',
            ".then()",
            "    .statusCode(200)"
        ])
        
        return "\n".join(lines)
    
    def generate_delete_request(self, endpoint: str) -> str:
        """Generate a DELETE request snippet."""
        return f"""given()
.when()
    .delete("{endpoint}")
.then()
    .statusCode(204)"""
    
    def generate_response_validation(self, validations: List[str]) -> str:
        """Generate response validation code."""
        if not validations:
            return ""
        
        lines = [".then()"]
        for validation in validations:
            lines.append(f"    {validation}")
        
        return "\n".join(lines)
    
    def generate_authentication_header(self, auth_type: str = "bearer", token: str = "token") -> str:
        """Generate authentication header code."""
        if auth_type.lower() == "bearer":
            return f'.header("Authorization", "Bearer {token}")'
        elif auth_type.lower() == "basic":
            return f'.auth().basic("username", "password")'
        else:
            return f'.header("Authorization", "{token}")'
    
    def generate_common_validations(self) -> List[str]:
        """Generate common response validations."""
        return [
            ".statusCode(200)",
            ".contentType(ContentType.JSON)",
            ".time(lessThan(30000L))",
            ".body(\"$\", notNullValue())"
        ]

