#!/usr/bin/env python3
"""
API Test Generator System - Main CLI Interface

A multi-agent system for generating JUnit 4 + Rest Assured integration tests
for REST APIs based on OpenAPI specifications and Java implementations.
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.config.settings import Settings
from src.config.models import AgentConfig, ProjectContext
from src.agents import CoordinatorAgent
from src.utils import setup_logger, get_logger, IntegrationValidator


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description='API Test Generator System - Generate JUnit 4 + Rest Assured tests from API specifications',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate tests based only on API specification
  python main.py generate --api-spec api.yaml --output tests/

  # Generate tests for API specification + source code analysis
  python main.py generate --api-spec api.yaml --api-src src/main/java --output tests/

  # Generate tests with custom base URL
  python main.py generate --api-spec api.yaml --api-src src/ --output tests/ --base-url http://localhost:8080

  # Validate system integration
  python main.py validate

  # Generate with custom configuration
  python main.py generate --api-spec api.yaml --api-src src/ --output tests/ --config custom.env

  # Generate with specific package name (no source code)
  python main.py generate --api-spec api.yaml --output tests/ --package com.example.tests

  # Generate with Mockito/Jersey Test500 classes (requires api-impl.jar)
  python main.py generate --api-spec api.yaml --output tests/ --api-impl path/to/api-impl.jar
        """
    )
    
    # Global options
    parser.add_argument(
        '--config', '-c',
        type=Path,
        help='Path to configuration file (.env format)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress non-error output'
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Generate command
    generate_parser = subparsers.add_parser(
        'generate',
        help='Generate API integration tests'
    )
    generate_parser.add_argument(
        '--api-spec',
        type=Path,
        required=True,
        help='Path to API specification file (OpenAPI/Swagger YAML or JSON)'
    )
    generate_parser.add_argument(
        '--api-src',
        type=Path,
        required=False,
        help='Path to API source code directory (Java Maven project). Optional - if not provided, tests will be generated based only on the API specification.'
    )
    generate_parser.add_argument(
        '--output', '-o',
        type=Path,
        required=True,
        help='Output directory for generated tests'
    )
    generate_parser.add_argument(
        '--base-url',
        type=str,
        default='http://localhost:8080',
        help='Base URL for the API (default: http://localhost:8080)'
    )
    generate_parser.add_argument(
        '--package',
        type=str,
        help='Java package name for generated tests (default: auto-detected)'
    )
    generate_parser.add_argument(
        '--class-name',
        type=str,
        help='Main test class name (default: ApiIntegrationTest)'
    )
    generate_parser.add_argument(
        '--api-impl',
        type=Path,
        required=False,
        default=None,
        help=(
            'Path to the API implementation JAR file (api-impl.jar or any name). '
            'Required when the OpenAPI specification documents HTTP 500 responses, '
            'because the *Test500.java classes use Mockito + Jersey Test Framework '
            'and need the implementation classes on the test classpath. '
            'The file will be copied to src/test/resources/ inside the generated '
            'Maven project and referenced in pom.xml as a system-scoped dependency. '
            'If omitted, the api-impl dependency block is excluded from pom.xml and '
            'no *Test500.java classes are generated.'
        )
    )
    generate_parser.add_argument(
        '--skip-compilation',
        action='store_true',
        help='Skip compilation and correction phases'
    )
    generate_parser.add_argument(
        '--skip-test-run',
        action='store_true',
        help='Skip test execution and correction phases'
    )
    
    # Validate command
    validate_parser = subparsers.add_parser(
        'validate',
        help='Validate system integration and configuration'
    )
    validate_parser.add_argument(
        '--report',
        type=Path,
        help='Save validation report to file'
    )
    
    # Version command
    version_parser = subparsers.add_parser(
        'version',
        help='Show version information'
    )
    
    return parser


def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Setup logging configuration."""
    if quiet:
        log_level = 'ERROR'
    elif verbose:
        log_level = 'DEBUG'
    else:
        log_level = 'INFO'
    
    setup_logger('api-test-generator', level=log_level)


async def validate_command(args: argparse.Namespace) -> int:
    """Handle the validate command."""
    logger = get_logger(__name__)
    logger.info("Starting system validation")
    
    try:
        # Load configuration
        settings = Settings(args.config)
        system_config = settings.config
        
        # Run validation
        validator = IntegrationValidator(system_config)
        results = await validator.validate_full_integration()
        
        # Generate report
        report = validator.generate_validation_report(results)
        
        # Output report
        if args.report:
            args.report.write_text(report, encoding='utf-8')
            logger.info(f"Validation report saved to: {args.report}")
        else:
            print(report)
        
        # Return appropriate exit code
        return 0 if results['overall_success'] else 1
        
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        return 1


async def generate_command(args: argparse.Namespace) -> int:
    """Handle the generate command."""
    logger = get_logger(__name__)
    logger.info("Starting API test generation")
    
    try:
        # Validate input arguments
        if not args.api_spec.exists():
            logger.error(f"API specification file not found: {args.api_spec}")
            return 1
        
        if args.api_src and not args.api_src.exists():
            logger.error(f"API source directory not found: {args.api_src}")
            return 1
        
        if args.api_impl and not args.api_impl.exists():
            logger.error(f"API implementation JAR not found: {args.api_impl}")
            return 1
        
        if args.api_impl and not args.api_impl.is_file():
            logger.error(f"--api-impl must point to a file, not a directory: {args.api_impl}")
            return 1
        
        # Load configuration
        settings = Settings(args.config)
        system_config = settings.config
        
        # Create project context
        context = create_project_context(args)
        
        # Initialize coordinator agent
        coordinator_config = AgentConfig(
            name='coordinator',
            model=system_config.openrouter.default_model
        )
        coordinator = CoordinatorAgent(coordinator_config, system_config)
        await coordinator.initialize()
        
        # Prepare input data
        input_data = {
            'base_url': context.base_url,
            'api_spec_path': str(context.api_spec_path),
            'api_src_path': str(context.api_src_path) if context.api_src_path is not None else None,
            'output_dir': str(context.output_dir),
            'package_name': context.package_name,
            'main_test_class_name': context.main_test_class_name,
            'skip_compilation': args.skip_compilation,
            'skip_test_run': args.skip_test_run,
            'api_impl_path': str(args.api_impl) if args.api_impl else None
        }
        
        # Run the generation process
        logger.info("Starting multi-agent test generation process")
        result = await coordinator.process(input_data)
        
        # Handle results
        if result['success']:
            logger.info("✅ Test generation completed successfully!")
            print(f"\n🎉 Success! Generated tests in: {context.output_dir}")
            print(f"📁 Maven project: {context.maven_project_dir}")
            
            if 'statistics' in result:
                stats = result['statistics']
                print(f"\n📊 Statistics:")
                print(f"   • Test scenarios: {stats.get('total_scenarios', 0)}")
                print(f"   • Generated files: {stats.get('generated_files', 0)}")
                print(f"   • Compilation fixes: {stats.get('compilation_fixes', 0)}")
                print(f"   • Test fixes: {stats.get('test_fixes', 0)}")
            
            return 0
        else:
            logger.error(f"❌ Test generation failed: {result.get('error', 'Unknown error')}")
            return 1
            
    except KeyboardInterrupt:
        logger.info("Generation interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error during generation: {e}")
        return 1


def create_project_context(args: argparse.Namespace) -> ProjectContext:
    """Create project context from command line arguments."""
    # Auto-detect package name if not provided and api_src is available
    package_name = args.package
    if not package_name and args.api_src:
        package_name = auto_detect_package_name(args.api_src)
    elif not package_name:
        # Default package name when no source code is provided
        package_name = 'com.example.api.tests'
    
    # Set default class name if not provided
    class_name = args.class_name or 'ApiIntegrationTest'
    
    # Ensure output directory exists
    args.output.mkdir(parents=True, exist_ok=True)
    
    return ProjectContext(
        base_url=args.base_url,
        api_spec_path=args.api_spec,
        api_src_path=args.api_src,  # Can be None
        package_name=package_name,
        main_test_class_name=class_name,
        output_dir=args.output,
        maven_project_dir=args.output / 'maven-project'
    )


def auto_detect_package_name(src_path: Path) -> str:
    """Auto-detect Java package name from source directory."""
    # Look for Java files and extract package declarations
    java_files = list(src_path.rglob('*.java'))
    
    for java_file in java_files[:5]:  # Check first 5 files
        try:
            content = java_file.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            for line in lines[:10]:  # Check first 10 lines
                line = line.strip()
                if line.startswith('package ') and line.endswith(';'):
                    package = line[8:-1].strip()
                    # Use parent package for tests
                    return f"{package}.tests"
        except Exception:
            continue
    
    # Fallback to generic package name
    return 'com.example.api.tests'


def version_command(args: argparse.Namespace) -> int:
    """Handle the version command."""
    print("API Test Generator System")
    print("Version: 1.0.0")
    print("Multi-agent system for generating JUnit 4 + Rest Assured tests")
    print("Built with Python 3.11+")
    return 0


async def main() -> int:
    """Main entry point."""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose, args.quiet)
    logger = get_logger(__name__)
    
    # Handle commands
    if args.command == 'generate':
        return await generate_command(args)
    elif args.command == 'validate':
        return await validate_command(args)
    elif args.command == 'version':
        return version_command(args)
    else:
        parser.print_help()
        return 1


def cli_main() -> None:
    """CLI entry point that handles async execution."""
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    cli_main()

