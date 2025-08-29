"""
Settings loader and validator for the API Test Generator System.
"""

import os
from pathlib import Path
from typing import Optional, Dict
from dotenv import load_dotenv

from .models import (
    SystemConfig, OpenRouterConfig, MavenConfig, 
    TestGenerationConfig, AgentConfig
)


class Settings:
    """Settings loader and manager."""
    
    def __init__(self, env_file: Optional[Path] = None):
        """Initialize settings from environment file."""
        if env_file and env_file.exists():
            load_dotenv(env_file)
        elif Path('.env').exists():
            load_dotenv('.env')
        
        self._config = self._load_config()
    
    def _load_config(self) -> SystemConfig:
        """Load configuration from environment variables."""
        # OpenRouter configuration
        openrouter = OpenRouterConfig(
            api_key=os.getenv('OPENROUTER_API_KEY'),
            api_base=os.getenv('OPENROUTER_API_BASE', 'https://openrouter.ai/api/v1'),
            default_model=os.getenv('OPENROUTER_DEFAULT_MODEL', 'openai/gpt-4o-mini'),
            rate_limit_requests_per_minute=int(os.getenv('RATE_LIMIT_REQUESTS_PER_MINUTE', '60')),
            rate_limit_tokens_per_minute=int(os.getenv('RATE_LIMIT_TOKENS_PER_MINUTE', '100000')),
            retry_attempts=int(os.getenv('RETRY_ATTEMPTS', '3')),
            retry_delay=float(os.getenv('RETRY_DELAY', '2.0')),
            backoff_factor=float(os.getenv('BACKOFF_FACTOR', '3.0'))
        )
        
        # Maven configuration
        maven = MavenConfig(
            timeout=int(os.getenv('MAVEN_TIMEOUT', '300')),
            memory=os.getenv('MAVEN_MEMORY', '2g'),
            java_home=os.getenv('JAVA_HOME'),
            maven_home=os.getenv('MAVEN_HOME')
        )
        
        # Test generation configuration
        test_generation = TestGenerationConfig(
            default_timeout=int(os.getenv('DEFAULT_TIMEOUT', '30')),
            generate_negative_tests=os.getenv('GENERATE_NEGATIVE_TESTS', 'true').lower() == 'true',
            include_performance_tests=os.getenv('INCLUDE_PERFORMANCE_TESTS', 'false').lower() == 'true',
            max_generation_attempts=int(os.getenv('MAX_GENERATION_ATTEMPTS', '5')),
            max_compile_correction_attempts=int(os.getenv('MAX_COMPILE_CORRECTION_ATTEMPTS', '2')),
            max_test_correction_attempts=int(os.getenv('MAX_TEST_CORRECTION_ATTEMPTS', '3'))
        )
        
        # Agent configurations
        agents = self._load_agent_configs(openrouter.default_model)
        
        return SystemConfig(
            openrouter=openrouter,
            maven=maven,
            test_generation=test_generation,
            agents=agents,
            java_validation_enabled=os.getenv('JAVA_VALIDATION_ENABLED', 'true').lower() == 'true',
            log_level=os.getenv('LOG_LEVEL', 'INFO')
        )
    
    def _load_agent_configs(self, default_model: str) -> Dict[str, AgentConfig]:
        """Load agent-specific configurations."""
        agents = {}
        
        agent_names = ['planner', 'generator', 'compiler_corrector', 'test_corrector']
        
        for agent_name in agent_names:
            model_key = f'{agent_name.upper()}_MODEL'
            model = os.getenv(model_key, default_model)
            
            agents[agent_name] = AgentConfig(
                name=agent_name,
                model=model,
                max_tokens=int(os.getenv(f'{agent_name.upper()}_MAX_TOKENS', '16000')),
                temperature=float(os.getenv(f'{agent_name.upper()}_TEMPERATURE', '0.1')),
                timeout=int(os.getenv(f'{agent_name.upper()}_TIMEOUT', '60'))
            )
        
        return agents
    
    @property
    def config(self) -> SystemConfig:
        """Get the system configuration."""
        return self._config
    
    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []
        
        # Validate OpenRouter configuration
        if not self._config.openrouter.api_key:
            errors.append("OPENROUTER_API_KEY is required")
        
        if not self._config.openrouter.api_base:
            errors.append("OPENROUTER_API_BASE is required")
        
        # Validate rate limits
        if self._config.openrouter.rate_limit_requests_per_minute <= 0:
            errors.append("RATE_LIMIT_REQUESTS_PER_MINUTE must be positive")
        
        if self._config.openrouter.rate_limit_tokens_per_minute <= 0:
            errors.append("RATE_LIMIT_TOKENS_PER_MINUTE must be positive")
        
        # Validate Maven configuration
        if self._config.maven.timeout <= 0:
            errors.append("MAVEN_TIMEOUT must be positive")
        
        # Validate test generation limits
        if self._config.test_generation.max_generation_attempts <= 0:
            errors.append("MAX_GENERATION_ATTEMPTS must be positive")
        
        if self._config.test_generation.max_compile_correction_attempts <= 0:
            errors.append("MAX_COMPILE_CORRECTION_ATTEMPTS must be positive")
        
        if self._config.test_generation.max_test_correction_attempts <= 0:
            errors.append("MAX_TEST_CORRECTION_ATTEMPTS must be positive")
        
        # Validate agent configurations
        for agent_name, agent_config in self._config.agents.items():
            if not agent_config.model:
                errors.append(f"Model for agent '{agent_name}' is required")
            
            if agent_config.max_tokens <= 0:
                errors.append(f"max_tokens for agent '{agent_name}' must be positive")
        
        return errors
    
    def get_agent_config(self, agent_name: str) -> Optional[AgentConfig]:
        """Get configuration for a specific agent."""
        return self._config.agents.get(agent_name)
    
    def update_agent_model(self, agent_name: str, model: str):
        """Update the model for a specific agent."""
        if agent_name in self._config.agents:
            self._config.agents[agent_name].model = model

