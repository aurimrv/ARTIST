"""
Data models for configuration and system state.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

def create_timestamp() -> str:
    """
    Cria um timestamp formatado.

    Returns:
        str: Timestamp atual formatado
    """
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

@dataclass
class AgentConfig:
    """Configuration for individual agents."""
    name: str
    model: str
    max_tokens: int = 102400
    temperature: float = 0.7
    timeout: int = 60
    seed: Optional[int] = None
    
    
@dataclass
class OpenRouterConfig:
    """Configuration for OpenRouter API."""
    api_key: Optional[str]
    api_base: str
    default_model: str
    rate_limit_requests_per_minute: int
    rate_limit_tokens_per_minute: int
    retry_attempts: int
    retry_delay: float
    backoff_factor: float


@dataclass
class MavenConfig:
    """Configuration for Maven operations."""
    timeout: int
    memory: str
    java_home: Optional[str] = None
    maven_home: Optional[str] = None


@dataclass
class TestGenerationConfig:
    """Configuration for test generation."""
    default_timeout: int
    generate_negative_tests: bool
    include_performance_tests: bool
    max_generation_attempts: int
    max_compile_correction_attempts: int
    max_test_correction_attempts: int


@dataclass
class SystemConfig:
    """Main system configuration."""
    openrouter: OpenRouterConfig
    maven: MavenConfig
    test_generation: TestGenerationConfig
    agents: Dict[str, AgentConfig]
    java_validation_enabled: bool
    log_level: str
    
    
@dataclass
class ProjectContext:
    """Context for a test generation project."""
    base_url: str
    api_spec_path: Path
    api_src_path: Optional[Path]
    output_dir: Path
    package_name: str
    main_test_class_name: str
    
    # Derived paths
    generated_test_dir: Optional[Path] = None
    maven_project_dir: Optional[Path] = None
    
    def __post_init__(self):
        """Initialize derived paths."""
        timestamp = create_timestamp()
        if self.generated_test_dir is None:
            self.generated_test_dir = self.output_dir / f"generated-tests_{timestamp}"
        if self.maven_project_dir is None:
            self.maven_project_dir = self.generated_test_dir / "maven-project"


@dataclass
class TestScenario:
    """Represents a test scenario to be generated."""
    name: str
    description: str
    endpoint: str
    method: str
    parameters: Dict[str, Any]
    expected_status: int
    expected_response_schema: Optional[Dict[str, Any]] = None
    is_negative_test: bool = False
    test_data: Optional[Dict[str, Any]] = None


@dataclass
class GenerationResult:
    """Result of test generation process."""
    success: bool
    message: str
    generated_files: list[Path]
    compilation_errors: list[str]
    test_failures: list[str]
    ignored_tests: list[str]

