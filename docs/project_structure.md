# ARTIST (Automated REST Testing Intelligent Specification-based Tool)

## Complete Technical Documentation

**Tool:** ARTIST (Automated REST Testing Intelligent Specification-based Tool)
**Type:** LLM-based multi-agent system for REST API integration test generation

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Agents and Responsibilities](#agents-and-responsibilities)
4. [Execution Flow](#execution-flow)
5. [Data Structures](#data-structures)
6. [LLM Usage](#llm-usage)
7. [Parsers and Utilities](#parsers-and-utilities)
8. [Templates and Code Generation](#templates-and-code-generation)
9. [Configuration and Deployment](#configuration-and-deployment)
10. [Usage Examples](#usage-examples)

---

## Overview

ARTIST is an automated tool that analyses OpenAPI specifications (and, optionally,
the Java source code and implementation JAR of the API) to generate complete,
runnable integration tests. It is built around specialized agents that cooperate to
produce valid Java code using JUnit and RestAssured, compiling and iteratively
repairing the generated suite through an LLM accessed via the OpenRouter API.

A defining principle of ARTIST is that the OpenAPI document is the single source of
truth for oracle derivation. When a generated test cannot be reconciled with the
actual API behavior, it is not deleted: it is annotated with `@Ignore` plus a
structured rationale, keeping the test as an auditable record of a
specification/implementation divergence.

### Main Characteristics

- **Multi-agent architecture**: a `CoordinatorAgent` orchestrating four
  task-specific agents working as a pipeline.
- **Dual analysis**: OpenAPI specification + optional Java source code/implementation
  JAR.
- **Template-anchored generation**: robust code templates constrain the LLM output
  to syntactically consistent Java structures.
- **Iterative self-correction**: automatic detection and repair of compilation and
  test failures, bounded by per-phase retry budgets.
- **Split-by-endpoint workflow**: each endpoint group is generated, compiled, and
  executed in isolation, so a single failing group does not abort the whole run.
- **Dedicated HTTP 500 testing**: optional Jersey + Mockito branch for documented
  server-error responses.
- **Deduplication and auditability**: duplicate scenarios are removed and every
  pipeline stage is persisted as an inspectable JSON snapshot.

---

## System Architecture

ARTIST is organized in four layers that operate in sequence: **Inputs**,
**Multi-Agent Pipeline**, **External Services**, and **Outputs**.

```
┌──────────────────────────────────────────────────────────────────┐
│                              INPUTS                                │
│   OpenAPI spec (required) · Java source (opt.) · api-impl.jar (opt)│
│   CLI & Configuration: main.py · Settings · .env → ProjectContext  │
└─────────────────────────────┬──────────────────────────────────────┘
                              │  ProjectContext
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                       MULTI-AGENT PIPELINE                         │
│                                                                    │
│              ┌──────────────────────────────────┐                 │
│              │         CoordinatorAgent          │                 │
│              │  lifecycle · split-by-endpoint ·  │                 │
│              │  5xx filtering · GenerationResult │                 │
│              └──────────────────┬───────────────┘                 │
│                                 ▼                                  │
│   Phase 1 Planning   → PlannerAgent      (+ OpenAPI/Java/Maven parsers)
│   Phase 2 Generation → GeneratorAgent    (+ templates, sanitizers) │
│   Phase 3 Compile fix→ CompilerCorrectorAgent (+ MavenRunner)      │
│   Phase 4 Test fix   → TestCorrectorAgent (+ MavenRunner, versioning)
│   Phase 5 HTTP 500   → GeneratorAgent     (Jersey + Mockito, optional)
│                                                                    │
│   Shared utilities: OpenRouterClient · RateLimiter · CodeSanitizer │
│   HttpContentTypeFixer · IntegrationValidator · TestVersionManager │
└─────────────────────────────┬──────────────────────────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                        EXTERNAL SERVICES                           │
│   OpenRouter API (Claude/GPT/Kimi/Gemini) · Apache Maven + JDK 8+  │
│   Surefire (JUnit) · Jersey Test Framework + Mockito (HTTP 500)    │
└─────────────────────────────┬──────────────────────────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                             OUTPUTS                                │
│   generated-tests_<timestamp>/                                     │
│     ├── maven-project/      (pom.xml, src/test/java/**)            │
│     ├── llm_interactions/   (snapshots + *_cost.json)             │
│     └── GenerationResult    (scenarios, files, @Ignore, costs)     │
└──────────────────────────────────────────────────────────────────┘
```

### Architecture Layers

1. **Inputs**: collects and prepares the user-supplied data (OpenAPI spec, optional
   Java source, optional implementation JAR) and the CLI/configuration
   (`main.py`, `Settings`, `.env`), assembling a typed `ProjectContext` that is
   handed to the `CoordinatorAgent`.
2. **Multi-Agent Pipeline**: the `CoordinatorAgent` plus the four task agents, the
   parsers, the templates, and the cross-cutting utility components.
3. **External Services**: the OpenRouter API (uniform access to multiple LLM
   providers) and an Apache Maven + JDK 8+ installation (Surefire for JUnit;
   Jersey Test Framework + Mockito for HTTP 500 scenarios).
4. **Outputs**: the timestamped `generated-tests_<...>/` directory holding the
   Maven project, the LLM interaction snapshots, and the consolidated
   `GenerationResult`.

---

## Agents and Responsibilities

### 1. CoordinatorAgent

**Responsibility**: Central orchestration of the test-generation pipeline.

**Functionality**:
- Instantiates and coordinates all task agents on demand.
- Propagates the run-specific output directory so every LLM interaction snapshot is
  written next to the generated Maven project.
- Filters out 5xx scenarios from regular generation (they are handled in Phase 5).
- Drives either the split-by-endpoint workflow (default) or the legacy
  generate-all/compile-all/run-all workflow.
- Aggregates per-class outcomes into a single `GenerationResult`.

**Input structure**:
```python
ProjectContext:
  - base_url: str
  - api_src_path: Optional[Path]
  - package_name: str
  - main_test_class_name: str
  - split_by_endpoint: bool = True
  - api_impl_path: Optional[Path] = None      # --api-impl JAR
  - generated_test_dir: Optional[Path] = None
  - maven_project_dir: Optional[Path] = None
```

**Output structure**:
```python
GenerationResult:
  - success: bool
  - message: str
  - generated_files: list[Path]
  - compilation_errors: list[str]
  - test_failures: list[str]
  - ignored_tests: list[str]
```

**LLM usage**: ❌ Does not call the LLM directly.

### 2. PlannerAgent

**Responsibility**: API analysis and test-scenario creation.

**Functionality**:
- Parses OpenAPI/Swagger specifications (Swagger 2.0 and OpenAPI 3.0).
- Optionally analyzes Java source code for implementation context.
- Generates positive and negative `TestScenario` records from the documented
  contract.
- Honors operation-level `x-parameter-examples` when present.
- Deduplicates scenarios.
- Persists three auditable JSON snapshots: `1_raw`, `2_deduplicated`, and
  `3_llm_enhanced`.

**Output structure**:
```python
TestScenario:
  - name: str
  - description: str
  - endpoint: str
  - method: str                 # GET, POST, PUT, DELETE, ...
  - parameters: Dict[str, Any]
  - expected_status: int
  - expected_response_schema: Optional[Dict[str, Any]]
  - is_negative_test: bool
  - test_data: Optional[Dict[str, Any]]
  - setup_dependencies: Optional[List[Dict[str, Any]]]
  - teardown_dependencies: Optional[List[Dict[str, Any]]]
  - content_type: Optional[str]
```

**LLM usage**: ✅ Uses the LLM to enrich scenarios (snapshot `3_llm_enhanced`).

### 3. GeneratorAgent

**Responsibility**: Java test-code generation.

**Functionality**:
- Creates the Maven project structure (via `MavenProjectTemplate`).
- Groups scenarios by endpoint and generates one self-contained JUnit class per
  group, anchored on the templates.
- Fills in test bodies through the LLM and cleans the output (`CodeSanitizer`,
  `HttpContentTypeFixer`).
- Generates the dedicated `*Test500.java` classes (Jersey + Mockito) in Phase 5
  when an implementation JAR is supplied.

**LLM usage**: ✅ Uses the LLM to fill in test bodies and the 500-test logic.

### 4. CompilerCorrectorAgent

**Responsibility**: Detection and correction of compilation errors.

**Functionality**:
- Runs `mvn clean compile` through the `MavenRunner`.
- Parses compiler diagnostics.
- Sends the offending source plus the original scenarios back to the LLM for a
  focused repair, up to `MAX_COMPILE_CORRECTION_ATTEMPTS` rounds.
- Renames irrecoverable files to `.java.err` so the remaining groups proceed.

**LLM usage**: ✅ Uses the LLM to repair compilation errors.

### 5. TestCorrectorAgent

**Responsibility**: Test execution and failure correction.

**Functionality**:
- Runs `mvn test` through the `MavenRunner` and parses the Surefire XML reports.
- For each failure/error, attempts a focused LLM repair, up to
  `MAX_TEST_CORRECTION_ATTEMPTS` rounds.
- Uses the `TestVersionManager` to preserve a per-class version history before each
  correction attempt.
- Annotates persistently failing/irreconcilable tests with `@Ignore` plus a
  structured rationale.

**LLM usage**: ✅ Uses the LLM to repair test failures.

---

## Execution Flow

### Five-Phase Pipeline (split-by-endpoint, default)

```
Phase 1: PLANNING
├── Parse OpenAPI spec (OpenAPIParser)
├── Analyze Java source / impl (JavaParser, MavenParser, JavaSourceAnalyzer) [optional]
├── Generate positive/negative TestScenario records (+ x-parameter-examples)
├── Deduplicate scenarios
└── Persist snapshots: 1_raw → 2_deduplicated → 3_llm_enhanced

(5xx scenarios are filtered out here and deferred to Phase 5)

For each endpoint group (isolated unit):
  Phase 2: GENERATION        (up to MAX_GENERATION_ATTEMPTS)
  ├── Assemble JUnit class from templates
  ├── Fill test bodies via LLM
  └── Sanitize output (CodeSanitizer, HttpContentTypeFixer)

  Phase 3: COMPILATION CORRECTION  (up to MAX_COMPILE_CORRECTION_ATTEMPTS)
  ├── mvn clean compile (MavenRunner)
  ├── Parse compiler diagnostics
  ├── LLM repair (TestVersionManager preserves prior versions)
  └── Rename to .java.err if unrecoverable

  Phase 4: TEST CORRECTION   (up to MAX_TEST_CORRECTION_ATTEMPTS)
  ├── mvn test (MavenRunner) + parse Surefire XML
  ├── Fixable mismatch → LLM repair (+ IntegrationValidator)
  └── Irreconcilable divergence → @Ignore + structured rationale

Phase 5: HTTP 500 TESTING (optional, requires --api-impl)
├── Generate *Test500.java classes (Jersey Test Framework + Mockito)
└── Substitute Resource Pattern to trigger documented 500 responses

Finalization:
└── CoordinatorAgent aggregates per-group outcomes into GenerationResult
```

The legacy (non-split) workflow generates all classes, then compiles all, then runs
all; it is selected when `SPLIT_BY_ENDPOINT=false`.

---

## Data Structures

### Configuration Models

```python
@dataclass
class AgentConfig:
    name: str
    model: str
    max_tokens: int = 102400
    temperature: float = 0.7
    timeout: int = 60
    seed: Optional[int] = None

@dataclass
class OpenRouterConfig:
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
    timeout: int
    memory: str
    java_home: Optional[str] = None
    maven_home: Optional[str] = None

@dataclass
class TestGenerationConfig:
    default_timeout: int
    generate_negative_tests: bool
    include_performance_tests: bool
    max_generation_attempts: int
    max_compile_correction_attempts: int
    max_test_correction_attempts: int

@dataclass
class SystemConfig:
    openrouter: OpenRouterConfig
    maven: MavenConfig
    test_generation: TestGenerationConfig
    agents: Dict[str, AgentConfig]
    java_validation_enabled: bool
    log_level: str
    split_by_endpoint: bool = True
```

### Test and Result Models

```python
@dataclass
class TestScenario:
    name: str
    description: str
    endpoint: str
    method: str
    parameters: Dict[str, Any]
    expected_status: int
    expected_response_schema: Optional[Dict[str, Any]] = None
    is_negative_test: bool = False
    test_data: Optional[Dict[str, Any]] = None
    setup_dependencies: Optional[List[Dict[str, Any]]] = None
    teardown_dependencies: Optional[List[Dict[str, Any]]] = None
    content_type: Optional[str] = None

@dataclass
class GenerationResult:
    success: bool
    message: str
    generated_files: list[Path]
    compilation_errors: list[str]
    test_failures: list[str]
    ignored_tests: list[str]
```

---

## LLM Usage

### OpenRouter Integration

ARTIST uses OpenRouter as a uniform gateway to multiple LLM providers. The
`OpenRouterClient` forwards prompts with per-agent settings, records token usage and
cost, and is throttled by the `RateLimiter`.

```python
class OpenRouterClient:
    def __init__(self, config: OpenRouterConfig): ...
    def set_output_dir(self, output_dir: str) -> None: ...
    async def chat_completion(self, messages, model, max_tokens=102400,
                              temperature=..., seed=None, **kwargs) -> dict: ...
```

Key behaviors:
- **Per-agent configuration**: `model`, `temperature`, `seed`, and `max_tokens` are
  resolved per agent from `.env` (e.g. `PLANNER_MODEL`, `GENERATOR_TEMPERATURE`,
  `PLANNER_SEED`).
- **Cost/usage logging**: each call records `prompt_tokens`, `completion_tokens`,
  `total_tokens`, and cost into `*_cost.json` files inside `llm_interactions/`.
- **Seed injection**: when a seed is available it is injected into the request
  payload for more deterministic outputs (supported by most OpenRouter models via
  the OpenAI-compatible API).

### Providers

Through OpenRouter, ARTIST can use providers such as Anthropic Claude, OpenAI GPT,
Moonshot Kimi, and Google Gemini. The default model is configurable through
`OPENROUTER_DEFAULT_MODEL` and can be overridden per agent.

### Rate Limiting

```python
class RateLimiter:
    # Enforces request- and token-per-minute budgets across the whole pipeline,
    # applying retry/backoff according to OpenRouterConfig.
```

---

## Parsers and Utilities

### OpenAPIParser
Parses OpenAPI/Swagger documents (Swagger 2.0 and OpenAPI 3.0): extracts endpoints,
schemas, parameters, response codes, parameter examples, and the
`x-parameter-examples` extension.

### JavaParser
Parses the optional Java source tree: classes, methods, annotations, and JAX-RS REST
endpoints (`@Path`, `@GET`, `@POST`, etc.), combining class- and method-level paths.

### MavenParser
Parses `pom.xml`: dependencies, plugins, and project metadata relevant to the build.

### JavaSourceAnalyzer (`src_analyzer`)
Discovers resource classes and endpoint mappings from source code, including
resources annotated with `@Path` and resources inferred via the JAX-RS
`Application` registration. Produces `EndpointMapping` records used as
implementation-level context in `ARTIST-spec-impl` mode.

### MavenRunner
Wraps `mvn` invocations (`clean compile`, `test`) with structured result parsing,
producing `MavenResult` and `CompilationError` objects; handles process timeouts.

### OpenRouterClient
The single entry point for all LLM calls (see [LLM Usage](#llm-usage)).

### RateLimiter
Enforces request/token-per-minute budgets and retry/backoff policy.

### CodeSanitizer
Cleans LLM output before it reaches the build (e.g. strips markdown fences and
spurious comments) and ensures the required imports for `*Test500.java` classes.

### HttpContentTypeFixer
Post-processes generated tests to ensure correct `Content-Type` handling.

### IntegrationValidator
Runs structural checks over the generated project / repaired code before it is
returned to the build.

### TestVersionManager (`test_versioning`)
Maintains a per-class version history, creating a versioned backup before each
correction attempt so that no intermediate artifact is lost.

### jar_utils
Inspects the implementation JAR (lists classes/packages, locates classes by simple
name) to support the Jersey + Mockito 500-test generation.

### file_utils / logger
Filesystem helpers (directory creation, copy, read/write, file discovery) and
logging setup (`setup_logger`, `get_logger`, `LoggerMixin`).

---

## Templates and Code Generation

### MavenProjectTemplate
Generates the Maven project structure and the `pom.xml`. The generated project
targets **Java 1.8** and uses, among others:

- JUnit `4.13.2`
- RestAssured `4.5.1`
- Hamcrest `2.2`
- Jackson `2.13.4`
- Jersey Test Framework `2.25.1` (for HTTP 500 tests)
- Mockito `5.11.0` (for HTTP 500 tests)
- `maven-compiler-plugin` `3.8.1`
- `maven-surefire-plugin` `3.0.0-M7` (configured to use the JUnit 4 provider; the
  JUnit 5 transitive dependencies pulled by Jersey are explicitly excluded)

When `--api-impl` is provided, the implementation JAR is referenced as a
system-scoped dependency and copied into `src/test/resources/`.

### JUnitTemplate
Generates JUnit test classes and methods, including the `@BeforeClass`/`@AfterClass`
hooks that set `RestAssured.baseURI` and call `RestAssured.reset()`, helper methods,
and `@Ignore`-annotated tests with a documented reason.

### RestAssuredTemplate
Generates RestAssured request/assertion snippets (`given().when().then()`) for the
GET/POST/PUT/DELETE verbs, response validations, and authentication headers.

---

## Configuration and Deployment

### Configuration File (`.env`)

```bash
# OpenRouter API Configuration
OPENROUTER_API_KEY=<YOUR_OPENROUTER_API_KEY>
OPENROUTER_API_BASE=https://openrouter.ai/api/v1

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_TOKENS_PER_MINUTE=100000
RETRY_ATTEMPTS=3
RETRY_DELAY=2.0
BACKOFF_FACTOR=3.0

# Default model for all agents (can be overridden per agent)
OPENROUTER_DEFAULT_MODEL=openai/gpt-4.1-mini

# Agent-specific models
PLANNER_MODEL=openai/gpt-4.1-mini
GENERATOR_MODEL=openai/gpt-4.1-mini
COMPILER_CORRECTOR_MODEL=openai/gpt-4.1-mini
TEST_CORRECTOR_MODEL=openai/gpt-4.1-mini

# Reproducibility/determinism (global and per-agent)
# SEED=42
# PLANNER_SEED=42
# GENERATOR_SEED=42
# COMPILER_CORRECTOR_SEED=42
# TEST_CORRECTOR_SEED=42

# Temperature (global and per-agent)
TEMPERATURE=0.2
PLANNER_TEMPERATURE=0.2
GENERATOR_TEMPERATURE=0.2
COMPILER_CORRECTOR_TEMPERATURE=0.2
TEST_CORRECTOR_TEMPERATURE=0.2

# System configuration
JAVA_HOME=/local/tools/jdk1.8.0
JAVA_VALIDATION_ENABLED=true
MAX_GENERATION_ATTEMPTS=3
MAX_COMPILE_CORRECTION_ATTEMPTS=3
MAX_TEST_CORRECTION_ATTEMPTS=3

# Logging
LOG_LEVEL=INFO

# Maven configuration
MAVEN_TIMEOUT=300
MAVEN_MEMORY=2g
MAVEN_HOME=/local/tools/apache-maven-3.8.5

# Test generation
DEFAULT_TIMEOUT=30
GENERATE_NEGATIVE_TESTS=true
INCLUDE_PERFORMANCE_TESTS=false

# Split test generation by endpoint group (one Java class per endpoint group)
SPLIT_BY_ENDPOINT=true
```

### Installation and Setup

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Configure environment variables
cp .env.example .env
# Edit .env with your configuration

# 3. Verify Maven and Java
mvn --version
java -version
```

### CLI Usage

```bash
# Basic command (specification only)
python main.py generate \
    --api-spec path/to/openapi.yaml \
    --output output/directory \
    --base-url http://localhost:8080

# With source code and implementation JAR (enables HTTP 500 tests)
python main.py generate \
    --api-spec path/to/openapi.yaml \
    --api-src path/to/java/source \
    --api-impl path/to/api-impl.jar \
    --output output/directory \
    --base-url http://localhost:8080

# Advanced options
python main.py generate \
    --api-spec path/to/openapi.yaml \
    --output output/directory \
    --package com.example.tests \
    --class-name ApiIntegrationTest \
    --seed 42 \
    --skip-compilation \
    --skip-test-run \
    --verbose
```

Additional subcommands:
```bash
python main.py validate --report report.txt   # check integration/configuration
python main.py version                         # show version information
```

---

## Usage Examples

### Example 1: restcountries (specification + implementation)

```bash
python main.py generate \
    --api-spec examples/restcountries_enhanced.json \
    --api-src  projects/restcountries/src \
    --api-impl projects/restcountries/target/restcountries-impl.jar \
    --output   output/restcountries-tests \
    --seed     3495
```

In `ARTIST-spec-impl` mode, the source code and implementation JAR provide
implementation-level context that improves parameter synthesis and enables the
HTTP 500 test classes.

### Example 2: Specification only (`ARTIST-spec`)

```bash
python main.py generate \
    --api-spec api/petstore.yaml \
    --output   output/petstore-tests \
    --base-url https://petstore.swagger.io/v2
```

In `ARTIST-spec` mode, only the OpenAPI document is required, making the tool
applicable to third-party APIs or to early-stage projects whose implementation is
still in flux.

### Output Structure

```
output/
└── generated-tests_YYYY-MM-DD_HH-MM-SS/
    ├── maven-project/
    │   ├── pom.xml
    │   └── src/
    │       └── test/
    │           ├── java/...        # *Test.java (and *Test500.java) classes
    │           └── resources/      # api-impl.jar (when --api-impl is provided)
    └── llm_interactions/
        ├── ..._scenarios_1_raw.json
        ├── ..._scenarios_2_deduplicated.json
        ├── ..._scenarios_3_llm_enhanced.json
        └── ..._cost.json
```

### Sample Generated Test

```java
@Test
public void testGetCountryByNamePortugal_200() {
    RestAssured.baseURI = BASE_URL;
    given()
        .queryParam("fullText", false)
    .when()
        .get("/rest/v2/name/portugal")
    .then()
        .statusCode(200)
        .body("[0].name", equalTo("Portugal"))
        .body("[0].alpha2Code", equalTo("PT"));
}
```

The oracle asserts the exact HTTP status code and response-body structure documented
in the (enriched) specification, making each test a direct executable projection of
the contract.

---

## Conclusion

ARTIST provides an automated, framework-independent pipeline for generating REST API
integration tests from OpenAPI specifications. Through the coordination of
specialized agents, the tool is able to:

1. **Analyze** OpenAPI specifications and (optionally) Java source code.
2. **Generate** specification-adherent test scenarios and JUnit/RestAssured code.
3. **Compile** the project and repair compilation errors iteratively.
4. **Execute** the tests and repair runtime failures, quarantining irreconcilable
   cases with `@Ignore` while preserving traceability.
5. **Report** the outcome through structured snapshots and a consolidated
   `GenerationResult`.

The modular architecture favors extensibility and maintainability, while the
template-anchored, multi-agent design keeps the generated code compilable and
specification-adherent.
