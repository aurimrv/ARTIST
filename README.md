# ARTIST (Automated REST Testing Intelligent Specification-based Tool)

**ARTIST** is an LLM-based (Large Language Model) multi-agent tool that automatically
**generates, compiles, and iteratively corrects** Java integration tests
(JUnit + RestAssured) from OpenAPI (Swagger) specifications.

The system uses a multi-agent architecture to plan test scenarios from the
specification contract, synthesize the Java source code, build the Maven project,
and iteratively repair failures in compilation and execution. Tests whose documented
behavior that the API does not honor is not silently dropped: they are annotated with
`@Ignore` plus a structured rationale, preserving full traceability to the OpenAPI
contract.

---

## Main Features

- **Specification-driven generation**: reads YAML/JSON documents (Swagger 2.0 or
  OpenAPI 3.0) and extracts endpoints, parameters, schemas, response codes, and
  parameter examples (`x-parameter-examples`).
- **Multi-agent architecture** coordinated by a `CoordinatorAgent`:
  - `PlannerAgent`: analyses the specification (and optional source code) and
    generates positive and negative test scenarios, deduplicating them and saving
    auditable snapshots.
  - `GeneratorAgent`: turns scenarios into Java code (JUnit + RestAssured),
    anchored on reusable templates.
  - `CompilerCorrectorAgent`: builds the Maven project and iteratively repairs
    compilation/import errors via the LLM.
  - `TestCorrectorAgent`: runs the tests and iteratively repairs runtime failures,
    falling back to `@Ignore` for irreconcilable specification/implementation
    divergences.
- **Split-by-endpoint workflow (default)**: each endpoint group is generated,
  compiled, and executed as an isolated unit, so a single failing group never
  aborts the whole run (the offending file is renamed to `.java.err`).
- **Dedicated HTTP 500 testing (Jersey + Mockito)**: when an implementation JAR is
  provided via `--api-impl`, ARTIST synthesizes `*Test500.java` classes using the
  Jersey Test Framework with Mockito (Substitute Resource Pattern) to deterministically
  trigger documented HTTP 500 responses.
- **State isolation**: each generated test class resets `RestAssured.baseURI` and
  calls `RestAssured.reset()` in `@BeforeClass`/`@AfterClass`, avoiding cross-class
  side effects when several test classes share a JVM.
- **Heterogeneous per-agent LLM configuration**: model, temperature, seed, and
  token limits are configurable independently for each agent through `.env`.
- **Determinism and reproducibility**: global and per-agent seed support for
  consistent LLM outputs; every LLM call is logged with prompts, responses, token
  counts, and cost.

---

## Prerequisites

- Python 3.8+
- Java JDK 8 or higher (configured in `JAVA_HOME`)
- Apache Maven 3.6+ (configured in `MAVEN_HOME` or on the `PATH`)
- An OpenRouter API key (for LLM model access)

---

## Installation

1. Clone the repository.
2. Install the Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy the example configuration file and fill in your API key:
   ```bash
   cp .env.example .env
   ```

---

## Basic Usage

The main command is `generate`, which requires at least the API specification and
the output directory:

```bash
python main.py generate --api-spec swagger.yaml --output ./reports/
```

ARTIST supports two operating modes:

- **Specification-only** (`ARTIST-spec`): only the OpenAPI document is required.
  ```bash
  python main.py generate \
    --api-spec swagger.yaml \
    --output ./reports/ \
    --seed 42
  ```
- **Specification + implementation** (`ARTIST-spec-impl`): the optional `--api-src`
  and `--api-impl` flags add implementation-level context (and enable HTTP 500
  tests).
  ```bash
  python main.py generate \
    --api-spec swagger.yaml \
    --api-src  path/to/api/src \
    --api-impl path/to/api-impl.jar \
    --output ./reports/ \
    --seed 42
  ```

### Output Structure

For each run, the system creates a timestamped directory inside the specified
output directory:

```text
reports/
└── generated-tests_YYYY-MM-DD_HH-MM-SS/
    ├── maven-project/               # Complete generated Java project (pom.xml, src/)
    │   ├── pom.xml
    │   └── src/test/java/...        # Generated *Test.java (and *Test500.java) classes
    └── llm_interactions/            # Debug logs and snapshots from the LLM agents
        ├── ..._scenarios_1_raw.json
        ├── ..._scenarios_2_deduplicated.json
        ├── ..._scenarios_3_llm_enhanced.json
        └── ..._cost.json            # Per-call token usage and cost
```

---

## Command-Line Parameters (CLI)

| Parameter | Description | Required | Default |
|---|---|---|---|
| `--api-spec` | Path to the OpenAPI file (YAML/JSON). | Yes | - |
| `--output`, `-o` | Base directory for the generated output. | Yes | - |
| `--api-src` | Path to the API source code directory (Java Maven project) for complementary static analysis. | No | - |
| `--base-url` | Base URL for the RestAssured tests. | No | `http://localhost:8080` |
| `--package` | Java package name for the generated tests. | No | Auto-detected |
| `--class-name` | Name of the main test class. | No | `ApiIntegrationTest` |
| `--api-impl` | Path to the API implementation JAR. Required to generate HTTP 500 tests (Mockito/Jersey); copied into `src/test/resources/` and referenced in `pom.xml` as a system-scoped dependency. | No | - |
| `--seed` | Global seed to make LLM outputs deterministic (overrides `SEED` in `.env`; per-agent seeds still take precedence). | No | - |
| `--skip-compilation` | Skip the compilation and error-correction phases. | No | `False` |
| `--skip-test-run` | Skip the test-execution and failure-correction phases. | No | `False` |
| `--config`, `-c` | Path to a custom `.env` configuration file. | No | `.env` |
| `--verbose`, `-v` | Enable verbose logging. | No | `False` |
| `--quiet`, `-q` | Suppress non-essential logging. | No | `False` |

Two additional subcommands are available: `validate` (checks system integration
and configuration, optionally saving a report with `--report`) and `version`
(shows version information).

---

## Determinism Configuration (Seed)

To make test generation reproducible across runs, configure the `seed`. The
configuration precedence is as follows (strongest to weakest):

1. **Per-agent seed (`.env`)**: variables such as `PLANNER_SEED=42` or
   `GENERATOR_SEED=99` take the highest precedence.
2. **Global seed via CLI (`--seed`)**: `--seed 42` overrides the global `SEED` in
   `.env`, but respects per-agent seeds.
3. **Global seed (`.env`)**: `SEED=42` acts as a fallback for all agents that do
   not define a specific seed.

**Example:**
```bash
python main.py generate --api-spec api.yaml --output tests/ --seed 42
```

---

## Environment Variables (`.env`)

The `.env` file configures the detailed behavior of the system:

- **Authentication**: `OPENROUTER_API_KEY`, `OPENROUTER_API_BASE`
- **LLM models (per agent)**: `OPENROUTER_DEFAULT_MODEL`, `PLANNER_MODEL`,
  `GENERATOR_MODEL`, `COMPILER_CORRECTOR_MODEL`, `TEST_CORRECTOR_MODEL`
- **Rate limiting / retries**: `RATE_LIMIT_REQUESTS_PER_MINUTE`,
  `RATE_LIMIT_TOKENS_PER_MINUTE`, `RETRY_ATTEMPTS`, `RETRY_DELAY`, `BACKOFF_FACTOR`
- **Correction budgets**: `MAX_GENERATION_ATTEMPTS`,
  `MAX_COMPILE_CORRECTION_ATTEMPTS`, `MAX_TEST_CORRECTION_ATTEMPTS`
- **Determinism**: `SEED`, `PLANNER_SEED`, `TEMPERATURE`, `PLANNER_TEMPERATURE`,
  etc.
- **Workflow**: `SPLIT_BY_ENDPOINT` (one Java class per endpoint group; default
  `true`)
- **Java/Maven environment**: `JAVA_HOME`, `MAVEN_HOME`, `MAVEN_TIMEOUT`,
  `MAVEN_MEMORY`, `JAVA_VALIDATION_ENABLED`
- **Logging**: `LOG_LEVEL`

See `.env.example` for all available options and their default values, and
`docs/project_structure.md` for the full technical documentation.

---

## License

This project is distributed under the terms of the `LICENSE` file included in the
repository.
