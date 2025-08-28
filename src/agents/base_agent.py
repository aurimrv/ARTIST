"""
Base agent class for the API Test Generator System.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pathlib import Path

from ..config.models import AgentConfig, SystemConfig
from ..utils.logger import LoggerMixin


class BaseAgent(ABC, LoggerMixin):
    """
    Abstract base class for all agents in the system.
    
    Provides common functionality like logging, configuration management,
    and standardized interfaces for agent operations.
    """
    
    def __init__(self, config: AgentConfig, system_config: SystemConfig):
        """
        Initialize the base agent.
        
        Args:
            config: Agent-specific configuration
            system_config: System-wide configuration
        """
        self.config = config
        self.system_config = system_config
        self.name = config.name
        self._initialized = False
        
        self.logger.info(f"Initializing {self.__class__.__name__} with model {config.model}")
    
    async def initialize(self) -> bool:
        """
        Initialize the agent. Override in subclasses for specific initialization.
        
        Returns:
            True if initialization was successful
        """
        if self._initialized:
            return True
        
        try:
            await self._initialize_impl()
            self._initialized = True
            self.logger.info(f"{self.__class__.__name__} initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize {self.__class__.__name__}: {e}")
            return False
    
    async def _initialize_impl(self):
        """Override in subclasses for specific initialization logic."""
        pass
    
    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process input data and return results.
        
        Args:
            input_data: Input data for processing
        
        Returns:
            Dictionary containing processing results
        """
        pass
    
    def validate_input(self, input_data: Dict[str, Any]) -> list[str]:
        """
        Validate input data and return list of validation errors.
        
        Args:
            input_data: Input data to validate
        
        Returns:
            List of validation error messages
        """
        errors = []
        
        # Basic validation - override in subclasses
        if not isinstance(input_data, dict):
            errors.append("Input data must be a dictionary")
        
        return errors
    
    def get_model_name(self) -> str:
        """Get the LLM model name for this agent."""
        return self.config.model
    
    def get_max_tokens(self) -> int:
        """Get the maximum tokens for this agent."""
        return self.config.max_tokens
    
    def get_temperature(self) -> float:
        """Get the temperature setting for this agent."""
        return self.config.temperature
    
    def get_timeout(self) -> int:
        """Get the timeout setting for this agent."""
        return self.config.timeout
    
    def is_initialized(self) -> bool:
        """Check if the agent is initialized."""
        return self._initialized
    
    def log_progress(self, message: str, step: Optional[int] = None, total_steps: Optional[int] = None):
        """
        Log progress information.
        
        Args:
            message: Progress message
            step: Current step number
            total_steps: Total number of steps
        """
        if step is not None and total_steps is not None:
            progress = f"[{step}/{total_steps}] "
        else:
            progress = ""
        
        self.logger.info(f"{progress}{message}")
    
    def log_error(self, message: str, exception: Optional[Exception] = None):
        """
        Log error information.
        
        Args:
            message: Error message
            exception: Optional exception object
        """
        if exception:
            self.logger.error(f"{message}: {exception}", exc_info=True)
        else:
            self.logger.error(message)
    
    def log_warning(self, message: str):
        """
        Log warning information.
        
        Args:
            message: Warning message
        """
        self.logger.warning(message)
    
    def log_debug(self, message: str):
        """
        Log debug information.
        
        Args:
            message: Debug message
        """
        self.logger.debug(message)
    
    def __str__(self) -> str:
        """String representation of the agent."""
        return f"{self.__class__.__name__}(name={self.name}, model={self.config.model})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the agent."""
        return (
            f"{self.__class__.__name__}("
            f"name={self.name}, "
            f"model={self.config.model}, "
            f"initialized={self._initialized})"
        )

