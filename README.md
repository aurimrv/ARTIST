# API Test Generator System

An automated, multi-agent system that reads an OpenAPI specification and generates a complete, compilable, and executable Maven test project using JUnit 4 and Rest Assured.

## Overview

The system orchestrates four specialised AI agents:

| Agent | Responsibility |
|---|---|
| **Planner** | Analyses the OpenAPI spec and produces a list of `TestScenario` objects covering happy-path, negative, boundary, and security cases |
| **Generator** | Converts scenarios into standalone, self-contained Java test classes |
| **Compiler Corrector** | Detects and fixes compilation errors iteratively |
| **Test Corrector** | Runs the test suite and fixes failing assertions iteratively |

Each generated `*Test.java` class is **standalone and self-contained**: it manages its own `@BeforeClass` / `@Before` / `@After` lifecycle without extending any shared base class.

---

## Requirements

- Python 3.9+
- Java 8+
- Maven 3.6+
- An [OpenRouter](https://openrouter.ai) API key (or compatible OpenAI-compatible endpoint)

---

## Installation

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set at minimum OPENROUTER_API_KEY
```

---

## Usage

### Basic command

```bash
python main.py generate \
  --api-spec path/to/openapi.yaml \
  --base-url https://api.example.com \
  --output ./output
```

### Full command reference

```
python main.py generate [OPTIONS]
```

| Option | Required | Description |
|---|---|---|
| `--api-spec FILE` | **Yes** | Path to the OpenAPI specification file (JSON or YAML) |
| `--base-url URL` | **Yes** | Base URL of the API under test |
| `--output DIR` | **Yes** | Directory where the generated Maven project will be written |
| `--package NAME` | No | Java package name for generated classes (default: `com.api.tests`) |
| `--class-name NAME` | No | Main test class name (default: `ApiIntegrationTest`) |
| `--api-src DIR` | No | Path to the API source directory (used for additional context) |
| `--api-impl FILE` | No | Path to the API implementation JAR — see section below |
| `--skip-compilation` | No | Skip the compilation and correction phases |
| `--skip-test-run` | No | Skip the test execution and correction phases |
| `--config FILE` | No | Path to a custom `.env` configuration file |

---

## `--api-impl`: API Implementation JAR

### Purpose

When the OpenAPI specification documents **HTTP 500** responses for one or more endpoints, the system can generate an additional set of test classes (`*Test500.java`) that use **Mockito** and the **Jersey Test Framework** to simulate internal server errors and assert that the API returns the correct 500 response body and status code.

These tests require the API implementation classes to be available on the test classpath. The `--api-impl` parameter provides the path to a JAR file containing those classes.

### Behaviour

| `--api-impl` supplied | Effect |
|---|---|
| **Yes** | The JAR is copied to `src/test/resources/<original-filename>` inside the generated Maven project. The `pom.xml` is generated with a `system`-scoped dependency pointing to that file. `*Test500.java` classes are generated for every endpoint that documents a 500 response. |
| **No** | The `api-impl` dependency block is **omitted** from `pom.xml` entirely (no missing-file compilation error). `*Test500.java` generation is skipped. |

### Important notes

- The file can have **any name** (e.g. `my-service-1.2.jar`). The system uses the original filename in both the copy destination and the `pom.xml` `<systemPath>`.
- The file must exist and be a regular file at the time the command is run; the system validates this before starting generation.
- If the spec has no 500 responses, no `*Test500.java` files are generated even when `--api-impl` is supplied.

### Example

```bash
# Generate tests including Mockito/Jersey 500 tests
python main.py generate \
  --api-spec rest-ncs.json \
  --base-url http://localhost:8080 \
  --output ./generated \
  --package com.example.ncs.tests \
  --api-impl /path/to/ncs-service-1.0.jar
```

After generation, the Maven project will contain:

```
maven-project/
├── pom.xml                          # includes api-impl system dependency
├── src/
│   └── test/
│       ├── java/com/example/ncs/tests/
│       │   ├── V1AlphaTest.java      # regular integration tests
│       │   └── V1AlphaTest500.java   # Mockito/Jersey 500 tests
│       └── resources/
│           ├── ncs-service-1.0.jar   # copied from --api-impl
│           ├── logback-test.xml
│           └── test.properties
```

---

## Generated Project Structure

```
output/
└── generated-tests_<timestamp>/
    └── maven-project/
        ├── pom.xml
        ├── README.md
        └── src/
            ├── main/
            │   ├── java/
            │   └── resources/
            └── test/
                ├── java/<package>/
                │   ├── <Endpoint>Test.java
                │   └── <Endpoint>Test500.java   # only if --api-impl is set
                └── resources/
                    ├── logback-test.xml
                    ├── test.properties
                    └── <api-impl-filename>.jar  # only if --api-impl is set
```

---

## Running the Generated Tests

```bash
cd output/generated-tests_<timestamp>/maven-project

# Run all tests
mvn test

# Run a single test class
mvn test -Dtest=V1AlphaTest

# Run against a different base URL
mvn test -Dapi.base.url=http://staging.example.com

# Run integration tests (failsafe)
mvn failsafe:integration-test
```

---

## Configuration (`.env`)

Key settings in `.env` / `.env.example`:

| Variable | Description |
|---|---|
| `OPENROUTER_API_KEY` | **Required.** Your OpenRouter API key |
| `OPENROUTER_DEFAULT_MODEL` | Default LLM model for all agents |
| `PLANNER_MODEL` | Model override for the Planner agent |
| `GENERATOR_MODEL` | Model override for the Generator agent |
| `COMPILER_CORRECTOR_MODEL` | Model override for the Compiler Corrector agent |
| `TEST_CORRECTOR_MODEL` | Model override for the Test Corrector agent |
| `SEED` | Global random seed for reproducible LLM outputs |
| `SPLIT_BY_ENDPOINT` | `true` (default) — generate one class per endpoint group |
| `MAX_GENERATION_ATTEMPTS` | Maximum generation retry attempts per class |
| `MAX_COMPILE_CORRECTION_ATTEMPTS` | Maximum compilation fix iterations |
| `MAX_TEST_CORRECTION_ATTEMPTS` | Maximum test-failure fix iterations |

---

## Retcode Immutability Policy

The system enforces a strict **retcode immutability** rule across all correction cycles:

> The HTTP status code asserted in a test (`statusCode(200)`, `statusCode(404)`, etc.) **must never be changed** during compilation or test-failure correction. The expected status code is derived from the OpenAPI specification and is considered ground truth. Use of `anyOf` matchers to widen status code acceptance is also prohibited.

This policy is enforced at the prompt level in both the Compiler Corrector and Test Corrector agents.

---

## Generated by API Test Generator System
