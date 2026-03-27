"""
Integration validation utility for the API Test Generator System.
"""

import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional

from ..config.models import SystemConfig
from .openrouter_client import OpenRouterClient
from .maven_runner import MavenRunner
from .logger import LoggerMixin


class IntegrationValidator(LoggerMixin):
    """
    Utility for validating the integration of all system components.
    
    Performs comprehensive checks to ensure all agents, utilities,
    and external dependencies are properly configured and working.
    """
    
    def __init__(self, system_config: SystemConfig):
        """Initialize the integration validator."""
        self.system_config = system_config
        self.validation_results = {}
    
    async def validate_full_integration(self) -> Dict[str, Any]:
        """
        Perform comprehensive integration validation.
        
        Returns:
            Dictionary with validation results
        """
        self.logger.info("Starting comprehensive integration validation")
        
        results = {
            'overall_success': True,
            'validations': {},
            'warnings': [],
            'errors': []
        }
        
        # Validate individual components
        validations = [
            ('openrouter_api', self._validate_openrouter_api),
            ('rate_limiting', self._validate_rate_limiting),
            ('maven_integration', self._validate_maven_integration),
            ('agent_initialization', self._validate_agent_initialization),
            ('agent_communication', self._validate_agent_communication),
            ('file_operations', self._validate_file_operations),
            ('configuration', self._validate_configuration)
        ]
        
        for validation_name, validation_func in validations:
            try:
                self.logger.info(f"Validating {validation_name}")
                validation_result = await validation_func()
                results['validations'][validation_name] = validation_result
                
                if not validation_result['success']:
                    results['overall_success'] = False
                    results['errors'].extend(validation_result.get('errors', []))
                
                results['warnings'].extend(validation_result.get('warnings', []))
                
            except Exception as e:
                self.log_error(f"Validation failed for {validation_name}", e)
                results['validations'][validation_name] = {
                    'success': False,
                    'error': str(e)
                }
                results['overall_success'] = False
                results['errors'].append(f"{validation_name}: {str(e)}")
        
        # Generate summary
        results['summary'] = self._generate_validation_summary(results)
        
        self.logger.info(f"Integration validation complete. Overall success: {results['overall_success']}")
        return results
    
    async def _validate_openrouter_api(self) -> Dict[str, Any]:
        """Validate OpenRouter API integration."""
        result = {'success': True, 'warnings': [], 'errors': []}
        
        if not self.system_config.openrouter.api_key:
            result['warnings'].append("No OpenRouter API key configured - LLM features will be disabled")
            return result
        
        try:
            # Test OpenRouter client initialization
            client = OpenRouterClient(self.system_config.openrouter)
            
            # Test API connectivity (if possible)
            models = await client.get_available_models()
            if models:
                result['available_models'] = len(models)
                self.logger.info(f"OpenRouter API validated - {len(models)} models available")
            else:
                result['warnings'].append("Could not retrieve available models from OpenRouter")
            
            # Test basic text generation
            try:
                #print(f"### _validate_openrouter_api temperature: {temperature}")
                response = await client.generate_text(
                    prompt="Test prompt",
                    model=self.system_config.openrouter.default_model,
                    max_tokens=50,
                    temperature=0.7
                )
                if response:
                    result['test_generation'] = True
                    self.logger.info("OpenRouter text generation test successful")
                else:
                    result['warnings'].append("OpenRouter text generation test returned empty response")
            except Exception as e:
                result['warnings'].append(f"OpenRouter text generation test failed: {str(e)}")
            
        except Exception as e:
            result['success'] = False
            result['errors'].append(f"OpenRouter API validation failed: {str(e)}")
        
        return result
    
    async def _validate_rate_limiting(self) -> Dict[str, Any]:
        """Validate rate limiting functionality."""
        result = {'success': True, 'warnings': [], 'errors': []}
        
        try:
            from .rate_limiter import RateLimiter
            
            # Test rate limiter initialization
            rate_limiter = RateLimiter(
                requests_per_minute=self.system_config.openrouter.rate_limit_requests_per_minute,
                tokens_per_minute=self.system_config.openrouter.rate_limit_tokens_per_minute
            )
            
            # Test rate limiter functionality
            await rate_limiter.acquire(estimated_tokens=100)
            usage = rate_limiter.get_current_usage()
            
            result['rate_limiter_initialized'] = True
            result['current_usage'] = usage
            
            self.logger.info("Rate limiting validation successful")
            
        except Exception as e:
            result['success'] = False
            result['errors'].append(f"Rate limiting validation failed: {str(e)}")
        
        return result
    
    async def _validate_maven_integration(self) -> Dict[str, Any]:
        """Validate Maven integration."""
        result = {'success': True, 'warnings': [], 'errors': []}
        
        try:
            maven_runner = MavenRunner(
                maven_home=self.system_config.maven.maven_home,
                java_home=self.system_config.maven.java_home
            )
            
            # Test Maven availability
            maven_version = maven_runner.get_maven_version()
            if maven_version:
                result['maven_version'] = maven_version
                self.logger.info(f"Maven validation successful - version {maven_version}")
            else:
                result['warnings'].append("Could not determine Maven version")
            
            # Test Java availability (if JAVA_HOME is set)
            if self.system_config.maven.java_home:
                java_home = Path(self.system_config.maven.java_home)
                if java_home.exists():
                    result['java_home_valid'] = True
                else:
                    result['warnings'].append(f"JAVA_HOME path does not exist: {java_home}")
            
        except Exception as e:
            result['success'] = False
            result['errors'].append(f"Maven integration validation failed: {str(e)}")
        
        return result
    
    async def _validate_agent_initialization(self) -> Dict[str, Any]:
        """Validate agent initialization."""
        result = {'success': True, 'warnings': [], 'errors': [], 'agents': {}}
        
        # Test each agent type with dynamic imports
        agent_classes = [
            ('coordinator', 'CoordinatorAgent'),
            ('planner', 'PlannerAgent'),
            ('generator', 'GeneratorAgent'),
            ('compiler_corrector', 'CompilerCorrectorAgent'),
            ('test_corrector', 'TestCorrectorAgent')
        ]
        
        for agent_name, agent_class_name in agent_classes:
            try:
                # Dynamic import to avoid circular imports
                from ..agents import (
                    CoordinatorAgent, PlannerAgent, GeneratorAgent, 
                    CompilerCorrectorAgent, TestCorrectorAgent
                )
                
                # Map class names to actual classes
                class_mapping = {
                    'CoordinatorAgent': CoordinatorAgent,
                    'PlannerAgent': PlannerAgent,
                    'GeneratorAgent': GeneratorAgent,
                    'CompilerCorrectorAgent': CompilerCorrectorAgent,
                    'TestCorrectorAgent': TestCorrectorAgent
                }
                
                agent_class = class_mapping[agent_class_name]
                
                # Create agent config
                agent_config = self.system_config.agents.get(agent_name)
                if not agent_config:
                    # Use default config
                    from ..config.models import AgentConfig
                    agent_config = AgentConfig(
                        name=agent_name,
                        model=self.system_config.openrouter.default_model
                    )
                
                # Initialize agent
                agent = agent_class(agent_config, self.system_config)
                await agent.initialize()
                
                result['agents'][agent_name] = {
                    'initialized': True,
                    'config': {
                        'model': agent_config.model,
                        'max_tokens': agent_config.max_tokens,
                        'temperature': agent_config.temperature
                    }
                }
                
                self.logger.info(f"Agent {agent_name} initialized successfully")
                
            except Exception as e:
                result['success'] = False
                result['errors'].append(f"Agent {agent_name} initialization failed: {str(e)}")
                result['agents'][agent_name] = {
                    'initialized': False,
                    'error': str(e)
                }
        
        return result
    
    async def _validate_agent_communication(self) -> Dict[str, Any]:
        """Validate agent communication patterns."""
        result = {'success': True, 'warnings': [], 'errors': []}
        
        try:
            # Test basic agent workflow (simplified)
            from ..config.models import AgentConfig
            from ..agents import CoordinatorAgent
            
            # Initialize coordinator agent
            coordinator_config = AgentConfig(
                name='coordinator',
                model=self.system_config.openrouter.default_model
            )
            coordinator = CoordinatorAgent(coordinator_config, self.system_config)
            await coordinator.initialize()
            
            # Test basic input validation
            test_input = {
                'api_spec_path': '/nonexistent/path',
                'api_src_path': '/nonexistent/path',
                'output_dir': '/tmp/test_output'
            }
            
            validation_errors = coordinator.validate_input(test_input)
            if validation_errors:
                result['input_validation'] = True
                self.logger.info("Agent input validation working correctly")
            else:
                result['warnings'].append("Agent input validation may not be working properly")
            
        except Exception as e:
            result['success'] = False
            result['errors'].append(f"Agent communication validation failed: {str(e)}")
        
        return result
    
    async def _validate_file_operations(self) -> Dict[str, Any]:
        """Validate file operations."""
        result = {'success': True, 'warnings': [], 'errors': []}
        
        try:
            from .file_utils import ensure_directory, write_file, read_file
            
            # Test directory creation
            test_dir = Path('/tmp/api_test_generator_validation')
            ensure_directory(test_dir)
            
            if test_dir.exists():
                result['directory_creation'] = True
            else:
                result['errors'].append("Directory creation failed")
                result['success'] = False
            
            # Test file operations
            test_file = test_dir / 'test.txt'
            test_content = "Test content for validation"
            
            write_file(test_file, test_content)
            if test_file.exists():
                result['file_writing'] = True
            else:
                result['errors'].append("File writing failed")
                result['success'] = False
            
            read_content = read_file(test_file)
            if read_content == test_content:
                result['file_reading'] = True
            else:
                result['errors'].append("File reading failed")
                result['success'] = False
            
            # Cleanup
            test_file.unlink(missing_ok=True)
            test_dir.rmdir()
            
            self.logger.info("File operations validation successful")
            
        except Exception as e:
            result['success'] = False
            result['errors'].append(f"File operations validation failed: {str(e)}")
        
        return result
    
    async def _validate_configuration(self) -> Dict[str, Any]:
        """Validate system configuration."""
        result = {'success': True, 'warnings': [], 'errors': []}
        
        try:
            # Validate OpenRouter configuration
            if not self.system_config.openrouter.api_key:
                result['warnings'].append("OpenRouter API key not configured")
            
            if self.system_config.openrouter.rate_limit_requests_per_minute <= 0:
                result['errors'].append("Invalid rate limit configuration for requests")
                result['success'] = False
            
            if self.system_config.openrouter.rate_limit_tokens_per_minute <= 0:
                result['errors'].append("Invalid rate limit configuration for tokens")
                result['success'] = False
            
            # Validate Maven configuration
            if self.system_config.maven.timeout <= 0:
                result['errors'].append("Invalid Maven timeout configuration")
                result['success'] = False
            
            # Validate test generation configuration
            if self.system_config.test_generation.max_generation_attempts <= 0:
                result['errors'].append("Invalid max generation attempts configuration")
                result['success'] = False
            
            result['config_summary'] = {
                'openrouter_configured': bool(self.system_config.openrouter.api_key),
                'maven_timeout': self.system_config.maven.timeout,
                'rate_limits': {
                    'requests_per_minute': self.system_config.openrouter.rate_limit_requests_per_minute,
                    'tokens_per_minute': self.system_config.openrouter.rate_limit_tokens_per_minute
                }
            }
            
            self.logger.info("Configuration validation successful")
            
        except Exception as e:
            result['success'] = False
            result['errors'].append(f"Configuration validation failed: {str(e)}")
        
        return result
    
    def _generate_validation_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a summary of validation results."""
        validations = results['validations']
        
        summary = {
            'total_validations': len(validations),
            'successful_validations': sum(1 for v in validations.values() if v.get('success', False)),
            'failed_validations': sum(1 for v in validations.values() if not v.get('success', True)),
            'total_warnings': len(results['warnings']),
            'total_errors': len(results['errors']),
            'components_status': {}
        }
        
        # Component status
        for component, validation in validations.items():
            summary['components_status'][component] = 'OK' if validation.get('success', False) else 'FAILED'
        
        # Overall health score
        if summary['total_validations'] > 0:
            summary['health_score'] = (summary['successful_validations'] / summary['total_validations']) * 100
        else:
            summary['health_score'] = 0
        
        return summary
    
    def generate_validation_report(self, results: Dict[str, Any]) -> str:
        """Generate a human-readable validation report."""
        lines = [
            "API Test Generator System - Integration Validation Report",
            "=" * 60,
            "",
            f"Overall Status: {'✅ PASSED' if results['overall_success'] else '❌ FAILED'}",
            f"Health Score: {results['summary']['health_score']:.1f}%",
            "",
            "Component Status:",
            "-" * 20
        ]
        
        for component, status in results['summary']['components_status'].items():
            status_icon = "✅" if status == "OK" else "❌"
            lines.append(f"{status_icon} {component}: {status}")
        
        if results['warnings']:
            lines.extend([
                "",
                "Warnings:",
                "-" * 10
            ])
            for warning in results['warnings']:
                lines.append(f"⚠️  {warning}")
        
        if results['errors']:
            lines.extend([
                "",
                "Errors:",
                "-" * 8
            ])
            for error in results['errors']:
                lines.append(f"❌ {error}")
        
        lines.extend([
            "",
            f"Validation completed with {results['summary']['successful_validations']}/{results['summary']['total_validations']} components passing"
        ])
        
        return "\n".join(lines)

