"""
Coordinator Agent for orchestrating the test generation process.
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
import asyncio

from .base_agent import BaseAgent
from ..config.models import (
    AgentConfig, SystemConfig, ProjectContext, 
    GenerationResult, TestScenario
)


class CoordinatorAgent(BaseAgent):
    """
    Coordinator Agent responsible for orchestrating the entire test generation process.
    
    This agent manages the workflow, delegates tasks to other agents, and ensures
    the process follows the correct sequence with proper error handling and retries.
    """
    
    def __init__(self, config: AgentConfig, system_config: SystemConfig):
        """Initialize the Coordinator Agent."""
        super().__init__(config, system_config)
        self._agents = {}
        self._current_project: Optional[ProjectContext] = None
    
    async def _initialize_impl(self):
        """Initialize the coordinator and its sub-agents."""
        self.logger.info("Initializing Coordinator Agent and sub-agents")
        
        # Initialize sub-agents
        self._agents = {}
        
        try:
            # Initialize Planner Agent
            from .planner_agent import PlannerAgent
            from ..config.models import AgentConfig
            
            planner_config = self.system_config.agents.get('planner')
            if not planner_config:
                planner_config = AgentConfig(
                    name='planner',
                    model=self.system_config.openrouter.default_model
                )
            
            planner = PlannerAgent(planner_config, self.system_config)
            await planner.initialize()
            self._agents['planner'] = planner
            self.logger.info("Planner agent initialized successfully")
            
        except Exception as e:
            self.logger.warning(f"Failed to initialize Planner agent: {e}")
            self._agents['planner'] = None
        
        try:
            # Initialize Generator Agent
            from .generator_agent import GeneratorAgent
            
            generator_config = self.system_config.agents.get('generator')
            if not generator_config:
                generator_config = AgentConfig(
                    name='generator',
                    model=self.system_config.openrouter.default_model
                )
            
            generator = GeneratorAgent(generator_config, self.system_config)
            await generator.initialize()
            self._agents['generator'] = generator
            self.logger.info("Generator agent initialized successfully")
            
        except Exception as e:
            self.logger.warning(f"Failed to initialize Generator agent: {e}")
            self._agents['generator'] = None
        
        try:
            # Initialize Compiler Corrector Agent
            from .compiler_corrector_agent import CompilerCorrectorAgent
            
            compiler_config = self.system_config.agents.get('compiler_corrector')
            if not compiler_config:
                compiler_config = AgentConfig(
                    name='compiler_corrector',
                    model=self.system_config.openrouter.default_model
                )
            
            compiler_corrector = CompilerCorrectorAgent(compiler_config, self.system_config)
            await compiler_corrector.initialize()
            self._agents['compiler_corrector'] = compiler_corrector
            self.logger.info("Compiler Corrector agent initialized successfully")
            
        except Exception as e:
            self.logger.warning(f"Failed to initialize Compiler Corrector agent: {e}")
            self._agents['compiler_corrector'] = None
        
        try:
            # Initialize Test Corrector Agent
            from .test_corrector_agent import TestCorrectorAgent
            
            test_config = self.system_config.agents.get('test_corrector')
            if not test_config:
                test_config = AgentConfig(
                    name='test_corrector',
                    model=self.system_config.openrouter.default_model
                )
            
            test_corrector = TestCorrectorAgent(test_config, self.system_config)
            await test_corrector.initialize()
            self._agents['test_corrector'] = test_corrector
            self.logger.info("Test Corrector agent initialized successfully")
            
        except Exception as e:
            self.logger.warning(f"Failed to initialize Test Corrector agent: {e}")
            self._agents['test_corrector'] = None
        
        self.logger.info("Coordinator Agent initialization complete")
    
    def register_agent(self, agent_name: str, agent: BaseAgent):
        """
        Register a sub-agent with the coordinator.
        
        Args:
            agent_name: Name of the agent
            agent: Agent instance
        """
        self._agents[agent_name] = agent
        self.logger.info(f"Registered agent: {agent_name}")
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main processing method that orchestrates the entire test generation workflow.
        
        Args:
            input_data: Dictionary containing project parameters
        
        Returns:
            Dictionary with generation results
        """
        try:
            # Validate input
            validation_errors = self.validate_input(input_data)
            if validation_errors:
                return {
                    'success': False,
                    'error': f"Input validation failed: {', '.join(validation_errors)}",
                    'result': None
                }
            
            # Create project context
            project_context = self._create_project_context(input_data)
            self._current_project = project_context
            
            self.logger.info(f"Starting test generation for project: {project_context.package_name}")
            
            # Execute the workflow
            result = await self._execute_workflow(
                project_context, 
                skip_compilation=input_data.get('skip_compilation', False),
                skip_test_run=input_data.get('skip_test_run', False)
            )
            
            return {
                'success': result.success,
                'message': result.message,
                'result': result
            }
            
        except Exception as e:
            self.log_error("Unexpected error in coordinator process", e)
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}",
                'result': None
            }
    
    def validate_input(self, input_data: Dict[str, Any]) -> List[str]:
        """
        Validate input data for the coordinator.
        
        Args:
            input_data: Input data to validate
        
        Returns:
            List of validation errors
        """
        errors = super().validate_input(input_data)
        
        required_fields = [
            'base_url', 'api_spec_path', 
            'output_dir', 'package_name', 'main_test_class_name'
        ]
        
        for field in required_fields:
            if field not in input_data:
                errors.append(f"Missing required field: {field}")
            elif not input_data[field]:
                errors.append(f"Empty value for required field: {field}")
        
        # Validate paths exist
        if 'api_spec_path' in input_data and input_data['api_spec_path']:
            spec_path = Path(input_data['api_spec_path'])
            if not spec_path.exists():
                errors.append(f"API specification file not found: {spec_path}")
        
        if 'api_src_path' in input_data and input_data['api_src_path']:
            src_path = Path(input_data['api_src_path'])
            if not src_path.exists():
                errors.append(f"API source directory not found: {src_path}")
        
        return errors
    
    def _create_project_context(self, input_data: Dict[str, Any]) -> ProjectContext:
        """
        Create a project context from input data.
        
        Args:
            input_data: Input parameters
        
        Returns:
            ProjectContext instance
        """
        api_impl_raw = input_data.get('api_impl_path')
        return ProjectContext(
            base_url=input_data['base_url'],
            api_spec_path=Path(input_data['api_spec_path']),
            api_src_path=Path(input_data['api_src_path']) if input_data['api_src_path'] else None,
            output_dir=Path(input_data['output_dir']),
            package_name=input_data['package_name'],
            main_test_class_name=input_data['main_test_class_name'],
            split_by_endpoint=self.system_config.split_by_endpoint,
            api_impl_path=Path(api_impl_raw) if api_impl_raw else None
        )
    
    async def _execute_workflow(self, context: ProjectContext, skip_compilation: bool = False, skip_test_run: bool = False) -> GenerationResult:
        """
        Execute the complete test generation workflow.
        
        Args:
            context: Project context
        
        Returns:
            Generation result
        """
        max_attempts = self.system_config.test_generation.max_generation_attempts
        
        for attempt in range(1, max_attempts + 1):
            self.log_progress(f"Generation attempt {attempt}/{max_attempts}")
            
            try:
                result = await self._execute_single_attempt(context, attempt, skip_compilation, skip_test_run)
                
                if result.success:
                    self.logger.info(f"Test generation completed successfully on attempt {attempt}")
                    return result
                else:
                    self.logger.warning(f"Attempt {attempt} failed: {result.message}")
                    
                    if attempt < max_attempts:
                        self.logger.info(f"Retrying... ({attempt + 1}/{max_attempts})")
                    
            except Exception as e:
                self.log_error(f"Attempt {attempt} failed with exception", e)
                
                if attempt == max_attempts:
                    return GenerationResult(
                        success=False,
                        message=f"All {max_attempts} generation attempts failed. Last error: {str(e)}",
                        generated_files=[],
                        compilation_errors=[str(e)],
                        test_failures=[],
                        ignored_tests=[]
                    )
        
        return GenerationResult(
            success=False,
            message=f"All {max_attempts} generation attempts failed",
            generated_files=[],
            compilation_errors=["Maximum attempts exceeded"],
            test_failures=[],
            ignored_tests=[]
        )
    
    async def _execute_single_attempt(self, context: ProjectContext, attempt: int, skip_compilation: bool = False, skip_test_run: bool = False) -> GenerationResult:
        """
        Execute a single generation attempt.
        
        Args:
            context: Project context
            attempt: Attempt number
        
        Returns:
            Generation result for this attempt
        """
        self.logger.info("Starting test generation workflow")
        
        # Step 1: Planning phase
        self.log_progress("Phase 1: Analyzing API and creating test scenarios", 1, 5)
        scenarios = await self._run_planning_phase(context)
        
        if not scenarios:
            return GenerationResult(
                success=False,
                message="Planning phase failed - no test scenarios generated",
                generated_files=[],
                compilation_errors=["Planning phase failed"],
                test_failures=[],
                ignored_tests=[]
            )
        
        if context.split_by_endpoint:
            return await self._execute_split_by_endpoint(context, scenarios, skip_compilation, skip_test_run)
        else:
            return await self._execute_legacy_workflow(context, scenarios, skip_compilation, skip_test_run)

    async def _execute_split_by_endpoint(
        self,
        context: ProjectContext,
        scenarios: List[TestScenario],
        skip_compilation: bool = False,
        skip_test_run: bool = False
    ) -> GenerationResult:
        """
        Execute the split-by-endpoint workflow.
        Each endpoint group is generated, compiled, and tested independently.
        """
        generator = self._agents.get('generator')
        compiler = self._agents.get('compiler_corrector')
        test_corrector = self._agents.get('test_corrector')

        # Create Maven project structure first
        if generator:
            project_dir = await generator._create_maven_project(context)
            if not project_dir:
                return GenerationResult(
                    success=False,
                    message="Failed to create Maven project structure",
                    generated_files=[],
                    compilation_errors=["Maven project creation failed"],
                    test_failures=[],
                    ignored_tests=[]
                )
            # Copy api-impl JAR to src/test/resources if provided
            self._copy_api_impl_jar(context)
        
        # Group scenarios by endpoint
        endpoint_groups = generator._group_scenarios_by_endpoint(scenarios, context)
        group_names = list(endpoint_groups.keys())
        total_groups = len(group_names)

        self.logger.info(
            f"split_by_endpoint=True: distributing {len(scenarios)} scenarios "
            f"across {total_groups} endpoint groups"
        )

        max_gen_attempts = self.system_config.test_generation.max_generation_attempts
        max_compile_attempts = self.system_config.test_generation.max_compile_correction_attempts
        max_test_attempts = self.system_config.test_generation.max_test_correction_attempts

        # Track per-group state
        compiled_groups: List[str] = []   # class names that compiled successfully
        failed_groups: List[str] = []     # class names that failed compilation
        all_generated_files: List[Path] = []
        all_test_failures: List[str] = []
        all_ignored_tests: List[str] = []

        test_src_dir = context.maven_project_dir / "src" / "test" / "java"
        # Derive package subdirectory
        package_subdir = test_src_dir / context.package_name.replace('.', '/')

        # Clean test directory before starting (preserve BaseApiTest and TestConfig)
        self._clean_test_directory(package_subdir)

        for group_idx, class_name in enumerate(group_names, 1):
            group_scenarios = endpoint_groups[class_name]
            self.logger.info(
                f"Processing group {group_idx}/{total_groups}: {class_name} ({len(group_scenarios)} scenarios)"
            )

            # --- Phase 2: Generation (up to max_gen_attempts) ---
            self.logger.info(f"[Phase 2] Generating test class: {class_name}")
            generated_file: Optional[Path] = None

            for gen_attempt in range(1, max_gen_attempts + 1):
                try:
                    test_content = await generator._generate_single_test_class_with_llm(
                        context, class_name, group_scenarios, focused=True
                    )
                    if test_content:
                        # Write file
                        generator.maven_template.add_test_class(
                            context.maven_project_dir,
                            context.package_name,
                            class_name,
                            test_content
                        )
                        generated_file = generator.maven_template.get_test_class_path(
                            context.maven_project_dir, context.package_name, class_name
                        )
                        self.logger.info(f"[Phase 2] {class_name} generated (attempt {gen_attempt}/{max_gen_attempts})")
                        break
                    else:
                        self.logger.warning(
                            f"[Phase 2] {class_name}: generation attempt {gen_attempt}/{max_gen_attempts} produced no valid code"
                        )
                except Exception as e:
                    self.logger.warning(f"[Phase 2] {class_name}: generation attempt {gen_attempt} error: {e}")

            if not generated_file or not generated_file.exists():
                self.logger.error(
                    f"[FATAL] Group {class_name}: generation failed after {max_gen_attempts} attempts — aborting"
                )
                failed_groups.append(class_name)
                return GenerationResult(
                    success=False,
                    message=(
                        f"Generation failure for group '{class_name}' after {max_gen_attempts} attempts. "
                        f"Generation aborted. The LLM could not produce valid Java code for this class."
                    ),
                    generated_files=all_generated_files,
                    compilation_errors=[f"Group {class_name} failed generation — aborting"],
                    test_failures=[],
                    ignored_tests=[]
                )

            all_generated_files.append(generated_file)

            # --- Phase 3: Compilation (up to max_compile_attempts) ---
            compiled_ok = False
            if skip_compilation:
                compiled_ok = True
                self.logger.info(f"[Phase 3] {class_name}: compilation skipped")
            else:
                for compile_attempt in range(1, max_compile_attempts + 1):
                    self.logger.info(f"[Phase 3] Compiling: {class_name} (attempt {compile_attempt}/{max_compile_attempts})")
                    if compiler:
                        compile_result = await compiler.process({
                            'project_dir': str(context.maven_project_dir),
                            'generated_files': [str(generated_file)]
                        })
                        # Strip any @Ignore inserted by compiler corrector
                        self._remove_ignore_from_file(generated_file)
                        if compile_result.get('success') or compile_result.get('compilation_successful'):
                            compiled_ok = True
                            self.logger.info(f"[Phase 3] {class_name} compiled successfully")
                            break
                        else:
                            self.logger.warning(
                                f"[Phase 3] {class_name}: compile attempt {compile_attempt}/{max_compile_attempts} failed"
                            )
                    else:
                        # No compiler agent — assume success
                        compiled_ok = True
                        break

            if not compiled_ok:
                self.logger.error(
                    f"[FATAL] Group {class_name}: compilation failed after {max_compile_attempts} attempts — aborting generation"
                )
                failed_groups.append(class_name)
                # Immediately abort: do not continue to next groups
                return GenerationResult(
                    success=False,
                    message=(
                        f"Compilation failure for group '{class_name}' after {max_compile_attempts} attempts. "
                        f"Generation aborted. Fix the class '{class_name}' before retrying."
                    ),
                    generated_files=all_generated_files,
                    compilation_errors=[f"Group {class_name} failed compilation — aborting"],
                    test_failures=[],
                    ignored_tests=[]
                )

            compiled_groups.append(class_name)

            # --- Phase 4: Test Execution (up to max_test_attempts) ---
            if skip_test_run:
                self.logger.info(f"[Phase 4] {class_name}: test execution skipped")
            elif test_corrector:
                for test_attempt in range(1, max_test_attempts + 1):
                    self.logger.info(f"[Phase 4] Running tests: {class_name} (attempt {test_attempt}/{max_test_attempts})")
                    test_result = await test_corrector.process({
                        'project_dir': str(context.maven_project_dir),
                        'generated_files': [str(generated_file)],
                        'test_class': class_name  # hint for isolated execution
                    })
                    failures = test_result.get('failures', [])
                    ignored = test_result.get('ignored', [])
                    if isinstance(failures, list):
                        failure_count = len(failures)
                    else:
                        failure_count = int(failures) if failures else 0

                    all_ignored_tests.extend(ignored if isinstance(ignored, list) else [])

                    if failure_count == 0 or test_result.get('success'):
                        stats = test_result.get('statistics', {})
                        passed = stats.get('tests_run', '?')
                        failed_count_stat = stats.get('failures', 0) + stats.get('errors', 0)
                        self.logger.info(f"[Phase 4] {class_name}: {passed} passed, {failed_count_stat} failed")
                        break
                    else:
                        if isinstance(failures, list):
                            all_test_failures.extend([str(f) for f in failures])
                        self.logger.warning(
                            f"[Phase 4] {class_name}: {failure_count} failures on attempt {test_attempt}/{max_test_attempts}"
                        )

            self.logger.info(f"Group {class_name}: DONE")

        # Phase 5: Generate *Test500.java files for endpoints with documented HTTP 500
        self.log_progress("Phase 5: Generating Mockito/Jersey Test500 classes", 5, 6)
        if generator:
            try:
                test500_files = await generator.generate_test500_classes(context)
                if test500_files:
                    self.logger.info(
                        f"[Phase 5] Generated {len(test500_files)} Test500 class(es): "
                        + ", ".join(f.name for f in test500_files)
                    )
                    all_generated_files.extend(test500_files)
                else:
                    self.logger.info("[Phase 5] No Test500 classes generated (no 500 endpoints found or generation skipped)")
            except Exception as e:
                self.logger.warning(f"[Phase 5] Test500 generation failed (non-fatal): {e}")

        if failed_groups:
            self.logger.warning(
                f"Groups excluded from Suite runner (compilation failed): {', '.join(failed_groups)}"
            )

        success = len(compiled_groups) > 0
        message = (
            f"split_by_endpoint: {len(compiled_groups)}/{total_groups} groups compiled successfully. "
            f"Suite runner includes: {compiled_groups}."
        )
        if failed_groups:
            message += f" Failed groups (excluded): {failed_groups}."

        return GenerationResult(
            success=success,
            message=message,
            generated_files=all_generated_files,
            compilation_errors=[f"Group {g} failed compilation" for g in failed_groups],
            test_failures=all_test_failures,
            ignored_tests=all_ignored_tests
        )

    async def _execute_legacy_workflow(
        self,
        context: ProjectContext,
        scenarios: List[TestScenario],
        skip_compilation: bool = False,
        skip_test_run: bool = False
    ) -> GenerationResult:
        """
        Execute the legacy (non-split) workflow: generate all → compile all → run all.
        """
        # Copy api-impl JAR to src/test/resources if provided
        self._copy_api_impl_jar(context)

        # Step 2: Generation phase
        self.log_progress("Phase 2: Generating test code", 2, 5)
        generated_files = await self._run_generation_phase(context, scenarios)
        
        if not generated_files:
            return GenerationResult(
                success=False,
                message="Generation phase failed - no test files generated",
                generated_files=[],
                compilation_errors=["Generation phase failed"],
                test_failures=[],
                ignored_tests=[]
            )
        
        # Step 2b: Generate *Test500.java files for endpoints with documented HTTP 500
        generator = self._agents.get('generator')
        if generator:
            try:
                test500_files = await generator.generate_test500_classes(context)
                if test500_files:
                    self.logger.info(
                        f"Generated {len(test500_files)} Test500 class(es): "
                        + ", ".join(f.name for f in test500_files)
                    )
                    generated_files.extend(test500_files)
                else:
                    self.logger.info("No Test500 classes generated (no 500 endpoints found or generation skipped)")
            except Exception as e:
                self.logger.warning(f"Test500 generation failed (non-fatal): {e}")

        # Step 3: Compilation correction phase
        self.log_progress("Phase 3: Checking and fixing compilation errors", 3, 5)
        if skip_compilation:
            self.logger.info("Skipping compilation phase as requested")
            compilation_result = {'success': True, 'message': 'Compilation skipped', 'errors': []}
        else:
            compilation_result = await self._run_compilation_phase(context, generated_files)
        
        if not compilation_result['success']:
            return GenerationResult(
                success=False,
                message=f"Compilation phase failed: {compilation_result['message']}",
                generated_files=generated_files,
                compilation_errors=compilation_result['errors'],
                test_failures=[],
                ignored_tests=[]
            )
        
        # Step 4: Test correction phase
        self.log_progress("Phase 4: Running tests and fixing failures", 4, 5)
        if skip_test_run:
            self.logger.info("Skipping test execution phase as requested")
            test_result = {'success': True, 'message': 'Test execution skipped', 'failures': [], 'ignored': []}
        else:
            test_result = await self._run_test_correction_phase(context, generated_files)
        
        # Step 5: Final validation
        self.log_progress("Phase 5: Final validation", 5, 5)
        final_result = await self._run_final_validation(context, generated_files)
        
        return GenerationResult(
            success=final_result['success'],
            message=final_result['message'],
            generated_files=generated_files,
            compilation_errors=compilation_result.get('errors', []),
            test_failures=test_result.get('failures', []),
            ignored_tests=test_result.get('ignored', [])
        )

    def _clean_test_directory(self, package_dir: Path):
        """
        Remove all .java test files from the package directory.

        No files are preserved: BaseApiTest.java and TestConfig.java are no
        longer generated, so there is nothing to protect.
        """
        if not package_dir.exists():
            return
        for java_file in package_dir.glob('*.java'):
            try:
                java_file.unlink()
                self.logger.debug(f"Cleaned test file: {java_file.name}")
            except Exception as e:
                self.logger.warning(f"Could not remove {java_file}: {e}")

    def _remove_ignore_from_file(self, file_path: Path):
        """
        Remove any @Ignore annotations (and unused import) inserted by compiler corrector.
        """
        if not file_path or not file_path.exists():
            return
        try:
            content = file_path.read_text(encoding='utf-8')
            if '@Ignore' not in content:
                return
            import re
            cleaned = re.sub(r'\s*@Ignore(?:\([^)]*\))?\s*\n', '\n', content)
            # Remove import if no @Ignore remains
            if '@Ignore' not in cleaned:
                cleaned = re.sub(r'\s*import\s+org\.junit\.Ignore\s*;\s*\n', '\n', cleaned)
            if cleaned != content:
                file_path.write_text(cleaned, encoding='utf-8')
                self.logger.warning(f"@Ignore removed from {file_path.name} (compiler corrector inserted it illegally)")
        except Exception as e:
            self.logger.warning(f"Failed to remove @Ignore from {file_path}: {e}")

    def _copy_api_impl_jar(self, context: ProjectContext) -> None:
        """
        Copy the api-impl JAR provided via ``--api-impl`` into
        ``src/test/resources/`` of the generated Maven project.

        The file is copied using its **original filename** so that the
        ``systemPath`` entry in pom.xml can reference it by name.  If
        ``context.api_impl_path`` is ``None`` (parameter not supplied) this
        method is a no-op and logs an informational message.
        """
        if not context.api_impl_path:
            self.logger.info(
                "--api-impl not provided: api-impl JAR will NOT be copied. "
                "*Test500.java classes will be skipped."
            )
            return

        resources_dir = context.maven_project_dir / "src" / "test" / "resources"
        resources_dir.mkdir(parents=True, exist_ok=True)

        dest = resources_dir / context.api_impl_path.name
        try:
            import shutil
            shutil.copy2(str(context.api_impl_path), str(dest))
            self.logger.info(
                f"api-impl JAR copied: {context.api_impl_path} → {dest}"
            )
        except Exception as exc:
            self.logger.error(
                f"Failed to copy api-impl JAR '{context.api_impl_path}' to "
                f"'{dest}': {exc}"
            )

    # _generate_suite_runner has been removed.
    # ApiIntegrationTest.java is no longer generated because each test class
    # is standalone and self-contained — no suite runner is needed.

    
    async def _run_planning_phase(self, context: ProjectContext) -> List[TestScenario]:
        """
        Run the planning phase using the Planner Agent.
        
        Args:
            context: Project context
        
        Returns:
            List of test scenarios
        """
        if not self._agents.get('planner'):
            self.logger.warning("Planner agent not available, using mock scenarios")
            return self._create_mock_scenarios(context)
        
        planner = self._agents['planner']
        
        planning_input = {
            'api_spec_path': str(context.api_spec_path),
            'api_src_path': str(context.api_src_path) if context.api_src_path is not None else None,
            'base_url': context.base_url
        }
        
        result = await planner.process(planning_input)
        
        if result.get('success'):
            return result.get('scenarios', [])
        else:
            self.log_error(f"Planning phase failed: {result.get('error', 'Unknown error')}")
            return []
    
    async def _run_generation_phase(self, context: ProjectContext, scenarios: List[TestScenario]) -> List[Path]:
        """
        Run the generation phase using the Generator Agent.
        
        Args:
            context: Project context
            scenarios: Test scenarios to generate
        
        Returns:
            List of generated file paths
        """
        if not self._agents.get('generator'):
            self.logger.warning("Generator agent not available, creating mock files")
            return self._create_mock_generated_files(context)
        
        generator = self._agents['generator']
        
        generation_input = {
            'context': context,
            'scenarios': scenarios
        }
        
        result = await generator.process(generation_input)
        
        if result.get('success'):
            return result.get('generated_files', [])
        else:
            self.log_error(f"Generation phase failed: {result.get('error', 'Unknown error')}")
            return []
    
    async def _run_compilation_phase(self, context: ProjectContext, files: List[Path]) -> Dict[str, Any]:
        """
        Run the compilation correction phase.
        
        Args:
            context: Project context
            files: Generated files to compile
        
        Returns:
            Compilation result dictionary
        """
        if not self._agents.get('compiler_corrector'):
            self.logger.warning("Compiler corrector agent not available, assuming compilation success")
            return {'success': True, 'message': 'Mock compilation success', 'errors': []}
        
        compiler = self._agents['compiler_corrector']
        
        compilation_input = {
            'project_dir': str(context.maven_project_dir),
            'generated_files': [str(f) for f in files]
        }
        
        result = await compiler.process(compilation_input)
        return result
    
    async def _run_test_correction_phase(self, context: ProjectContext, files: List[Path]) -> Dict[str, Any]:
        """
        Run the test correction phase.
        
        Args:
            context: Project context
            files: Generated files to test
        
        Returns:
            Test result dictionary
        """
        if not self._agents.get('test_corrector'):
            self.logger.warning("Test corrector agent not available, assuming test success")
            return {'success': True, 'message': 'Mock test success', 'failures': [], 'ignored': []}
        
        test_corrector = self._agents['test_corrector']
        
        test_input = {
            'project_dir': str(context.maven_project_dir),
            'generated_files': [str(f) for f in files]
        }
        
        result = await test_corrector.process(test_input)
        return result
    
    async def _run_final_validation(self, context: ProjectContext, files: List[Path]) -> Dict[str, Any]:
        """
        Run final validation of the generated project.
        
        Args:
            context: Project context
            files: Generated files
        
        Returns:
            Validation result dictionary
        """
        # Basic validation - check if files exist and are not empty
        valid_files = []
        
        for file_path in files:
            if file_path.exists() and file_path.stat().st_size > 0:
                valid_files.append(file_path)
            else:
                self.logger.warning(f"Generated file is missing or empty: {file_path}")
        
        if not valid_files:
            return {
                'success': False,
                'message': 'No valid generated files found'
            }
        
        return {
            'success': True,
            'message': f'Successfully generated {len(valid_files)} test files'
        }
    
    def _create_mock_scenarios(self, context: ProjectContext) -> List[TestScenario]:
        """Create mock test scenarios for testing purposes."""
        return [
            TestScenario(
                name="test_get_all_countries",
                description="Test getting all countries",
                endpoint="/v2/all",
                method="GET",
                parameters={},
                expected_status=200,
                is_negative_test=False
            ),
            TestScenario(
                name="test_get_country_by_name",
                description="Test getting country by name",
                endpoint="/v2/name/portugal",
                method="GET",
                parameters={"name": "portugal"},
                expected_status=200,
                is_negative_test=False
            )
        ]
    
    def _create_mock_generated_files(self, context: ProjectContext) -> List[Path]:
        """Create mock generated files for testing purposes."""
        from ..utils.file_utils import ensure_directory, write_file
        
        # Create the test directory structure
        test_dir = context.maven_project_dir / "src" / "test" / "java"
        ensure_directory(test_dir)
        
        # Create a basic test file
        test_file = test_dir / f"{context.main_test_class_name}.java"
        
        # Generate basic test content
        mock_test_content = f"""package {context.package_name};

import org.junit.Test;
import static io.restassured.RestAssured.*;
import static org.hamcrest.Matchers.*;

/**
 * Mock integration test for {context.base_url}
 * Generated by API Test Generator System (Mock Mode)
 */
public class {context.main_test_class_name} {{
    
    private static final String BASE_URL = "{context.base_url}";
    
    @Test
    public void testApiConnection() {{
        given()
            .baseUri(BASE_URL)
        .when()
            .get("/")
        .then()
            .statusCode(anyOf(is(200), is(404), is(405)));
    }}
    
    @Test
    public void testMockEndpoint() {{
        // This is a mock test - replace with actual API endpoints
        given()
            .baseUri(BASE_URL)
        .when()
            .get("/health")
        .then()
            .statusCode(anyOf(is(200), is(404)));
    }}
}}
"""
        
        # Write the mock test file
        write_file(test_file, mock_test_content)
        self.logger.info(f"Created mock test file: {test_file}")
        
        # Also create a basic pom.xml if it doesn't exist
        pom_file = context.maven_project_dir / "pom.xml"
        if not pom_file.exists():
            pom_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    
    <groupId>{context.package_name}</groupId>
    <artifactId>api-integration-tests</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>
    
    <properties>
        <maven.compiler.source>8</maven.compiler.source>
        <maven.compiler.target>8</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    </properties>
    
    <dependencies>
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>4.13.2</version>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>io.rest-assured</groupId>
            <artifactId>rest-assured</artifactId>
            <version>4.5.1</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
    
    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <version>3.8.1</version>
                <configuration>
                    <source>8</source>
                    <target>8</target>
                </configuration>
            </plugin>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>
                <version>3.0.0-M7</version>
            </plugin>
        </plugins>
    </build>
</project>
"""
            write_file(pom_file, pom_content)
            self.logger.info(f"Created mock pom.xml: {pom_file}")
        
        return [test_file]
    
    def get_current_project(self) -> Optional[ProjectContext]:
        """Get the current project context."""
        return self._current_project
    
    def get_registered_agents(self) -> Dict[str, BaseAgent]:
        """Get all registered agents."""
        return {k: v for k, v in self._agents.items() if v is not None}

