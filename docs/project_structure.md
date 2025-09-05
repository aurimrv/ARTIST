# Sistema Multi-Agente para Geração de Testes de API

## Documentação Técnica Completa

**Versão:** 1.0.0  
**Data:** 29 de Agosto de 2025  
**Autor:** Sistema de Geração Automática de Testes de API  

---

## Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura do Sistema](#arquitetura-do-sistema)
3. [Agentes e Responsabilidades](#agentes-e-responsabilidades)
4. [Fluxo de Execução](#fluxo-de-execução)
5. [Estruturas de Dados](#estruturas-de-dados)
6. [Uso de LLM](#uso-de-llm)
7. [Parsers e Utilitários](#parsers-e-utilitários)
8. [Templates e Geração de Código](#templates-e-geração-de-código)
9. [Configuração e Deployment](#configuração-e-deployment)
10. [Exemplos de Uso](#exemplos-de-uso)

---

## Visão Geral

O Sistema Multi-Agente para Geração de Testes de API é uma solução automatizada que analisa especificações OpenAPI e código fonte Java para gerar testes de integração completos e funcionais. O sistema utiliza uma arquitetura baseada em agentes especializados que trabalham em conjunto para produzir código Java válido usando JUnit 4 e Rest Assured.

### Características Principais

- **Arquitetura Multi-Agente**: 5 agentes especializados trabalhando em pipeline
- **Análise Dupla**: Especificação OpenAPI + código fonte Java
- **Geração Inteligente**: Templates robustos + enhancement via LLM
- **Correção Automática**: Detecção e correção de erros de compilação e teste
- **Deduplicação**: Remoção automática de cenários duplicados
- **Exportação JSON**: Cenários conformes a schemas definidos

---

## Arquitetura do Sistema

### Diagrama de Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                    COORDINATOR AGENT                           │
│                  (Orquestração Central)                        │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PIPELINE DE AGENTES                        │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   PLANNER   │  │ GENERATOR   │  │ COMPILER    │             │
│  │   AGENT     │─▶│   AGENT     │─▶│ CORRECTOR   │             │
│  │             │  │             │  │   AGENT     │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                           │                     │
│                                           ▼                     │
│                    ┌─────────────┐  ┌─────────────┐             │
│                    │    TEST     │  │ INTEGRATION │             │
│                    │ CORRECTOR   │─▶│ VALIDATOR   │             │
│                    │   AGENT     │  │             │             │
│                    └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                  COMPONENTES DE APOIO                          │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   OPENAPI   │  │    JAVA     │  │   MAVEN     │             │
│  │   PARSER    │  │   PARSER    │  │   PARSER    │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   JUNIT     │  │   MAVEN     │  │ OPENROUTER  │             │
│  │  TEMPLATE   │  │  TEMPLATE   │  │   CLIENT    │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

### Camadas da Arquitetura

1. **Camada de Orquestração**: CoordinatorAgent
2. **Camada de Processamento**: Agentes especializados (Planner, Generator, Correctors)
3. **Camada de Análise**: Parsers (OpenAPI, Java, Maven)
4. **Camada de Geração**: Templates (JUnit, Maven, Rest Assured)
5. **Camada de Integração**: OpenRouter Client, Rate Limiter, Validators

---

## Agentes e Responsabilidades

### 1. CoordinatorAgent

**Responsabilidade**: Orquestração central do pipeline de geração de testes

**Funcionalidades**:
- Inicialização e coordenação de todos os agentes
- Controle do fluxo de execução em 5 fases
- Gerenciamento de tentativas e recuperação de erros
- Validação final do processo

**Estruturas de Entrada**:
```python
ProjectContext:
  - api_spec_path: str
  - api_src_path: Optional[str]
  - output_path: str
  - base_url: str
  - package_name: str
  - main_test_class_name: str
```

**Estruturas de Saída**:
```python
GenerationResult:
  - success: bool
  - output_path: str
  - maven_project_path: str
  - test_files: List[str]
  - scenarios_count: int
  - errors: List[str]
```

**Uso de LLM**: ❌ Não utiliza LLM diretamente

### 2. PlannerAgent

**Responsabilidade**: Análise de API e criação de cenários de teste

**Funcionalidades**:
- Parsing de especificações OpenAPI/Swagger
- Análise de código fonte Java (opcional)
- Extração de endpoints REST
- Geração de cenários de teste realistas
- Deduplicação de cenários
- Exportação para JSON

**Estruturas de Entrada**:
```python
# Especificação OpenAPI
OpenAPISpec:
  - version: str
  - info: Dict[str, Any]
  - servers: List[Server]
  - paths: Dict[str, PathItem]
  - components: Dict[str, Any]

# Código fonte Java (opcional)
JavaProject:
  - classes: List[JavaClass]
  - endpoints: List[RestEndpoint]
  - maven_info: MavenProject
```

**Estruturas de Saída**:
```python
TestScenario:
  - name: str
  - description: str
  - method: str  # GET, POST, PUT, DELETE
  - endpoint: str
  - expected_status: int
  - test_data: Optional[Dict[str, Any]]
  - path_parameters: Dict[str, Any]
  - query_parameters: Dict[str, Any]
  - headers: Dict[str, str]
  - expected_response_schema: Optional[Dict[str, Any]]
  - is_negative_test: bool
  - from_source_code: bool
```

**Uso de LLM**: ✅ Utiliza LLM para enriquecimento de cenários

**Interações LLM**:
- Análise de endpoints para geração de cenários realistas
- Criação de dados de teste apropriados
- Geração de descrições de cenários

### 3. GeneratorAgent

**Responsabilidade**: Geração de código Java de teste

**Funcionalidades**:
- Criação de estrutura Maven
- Geração de classes de teste JUnit 4
- Integração com Rest Assured
- Enhancement opcional via LLM
- Validação de código gerado

**Estruturas de Entrada**:
```python
# Lista de cenários de teste
scenarios: List[TestScenario]

# Contexto do projeto
ProjectContext:
  - package_name: str
  - main_test_class_name: str
  - base_url: str
  - output_path: str
```

**Estruturas de Saída**:
```python
# Arquivos Java gerados
TestClass:
  - file_path: str
  - class_name: str
  - package_name: str
  - test_methods: List[str]
  - helper_methods: List[str]
  - imports: List[str]

# Projeto Maven
MavenProject:
  - pom_xml: str
  - src_structure: Dict[str, str]
  - test_classes: List[TestClass]
```

**Uso de LLM**: ✅ Utiliza LLM para enhancement de código

**Interações LLM**:
- Melhoria de código de teste gerado por template
- Otimização de assertions
- Adição de validações específicas

### 4. CompilerCorrectorAgent

**Responsabilidade**: Detecção e correção de erros de compilação

**Funcionalidades**:
- Execução de compilação Maven
- Parsing de erros de compilação
- Correção automática de erros comuns
- Validação de correções aplicadas

**Estruturas de Entrada**:
```python
# Projeto Maven para compilação
MavenProject:
  - project_path: str
  - pom_xml_path: str
  - source_files: List[str]
```

**Estruturas de Saída**:
```python
CompilationResult:
  - success: bool
  - errors: List[CompilationError]
  - corrections_applied: List[str]
  - compilation_time: float

CompilationError:
  - file_path: str
  - line_number: int
  - column_number: int
  - error_type: str  # syntax, duplicate_method, missing_import, etc.
  - message: str
  - suggested_fix: Optional[str]
```

**Uso de LLM**: ✅ Utiliza LLM para correção de erros complexos

**Interações LLM**:
- Análise de erros de compilação não triviais
- Geração de correções para problemas específicos
- Refatoração de código problemático

### 5. TestCorrectorAgent

**Responsabilidade**: Execução de testes e correção de falhas

**Funcionalidades**:
- Execução de testes Maven
- Parsing de resultados de teste
- Correção de falhas de teste
- Aplicação de @Ignore para testes persistentemente falhos

**Estruturas de Entrada**:
```python
# Projeto Maven compilado
CompiledMavenProject:
  - project_path: str
  - test_classes: List[str]
  - compilation_success: bool
```

**Estruturas de Saída**:
```python
TestResult:
  - success: bool
  - total_tests: int
  - passed_tests: int
  - failed_tests: int
  - errors: int
  - failures: List[TestFailure]
  - corrections_applied: List[str]

TestFailure:
  - test_class: str
  - test_method: str
  - failure_type: str  # assertion, timeout, connection, etc.
  - message: str
  - stack_trace: str
  - suggested_fix: Optional[str]
```

**Uso de LLM**: ✅ Utiliza LLM para correção de falhas de teste

**Interações LLM**:
- Análise de falhas de teste complexas
- Geração de correções para assertions
- Otimização de timeouts e configurações

---

## Fluxo de Execução

### Pipeline de 5 Fases

```
Fase 1: ANÁLISE E PLANEJAMENTO
├── PlannerAgent.analyze_api_specification()
├── PlannerAgent.analyze_source_code() [opcional]
├── PlannerAgent.generate_test_scenarios()
├── PlannerAgent.validate_and_deduplicate_scenarios()
└── PlannerAgent.export_scenarios_to_json()

Fase 2: GERAÇÃO DE CÓDIGO
├── GeneratorAgent.create_maven_project()
├── GeneratorAgent.generate_test_classes()
├── GeneratorAgent.enhance_with_llm() [opcional]
└── GeneratorAgent.validate_generated_code()

Fase 3: CORREÇÃO DE COMPILAÇÃO
├── CompilerCorrectorAgent.compile_project()
├── CompilerCorrectorAgent.parse_compilation_errors()
├── CompilerCorrectorAgent.fix_compilation_errors()
└── CompilerCorrectorAgent.verify_compilation()

Fase 4: CORREÇÃO DE TESTES
├── TestCorrectorAgent.run_tests()
├── TestCorrectorAgent.parse_test_failures()
├── TestCorrectorAgent.fix_test_failures()
└── TestCorrectorAgent.verify_test_results()

Fase 5: VALIDAÇÃO FINAL
├── IntegrationValidator.validate_project_structure()
├── IntegrationValidator.validate_test_coverage()
└── CoordinatorAgent.generate_final_report()
```

### Sequência Detalhada de Chamadas

1. **Inicialização**
   ```python
   coordinator = CoordinatorAgent(config, system_config)
   await coordinator.initialize()
   ```

2. **Fase 1: Análise**
   ```python
   # PlannerAgent
   api_spec = await planner.parse_api_specification(spec_path)
   source_analysis = await planner.analyze_source_code(src_path)  # opcional
   scenarios = await planner.generate_scenarios(api_spec, source_analysis)
   validated_scenarios = await planner.validate_scenarios(scenarios)
   await planner.export_scenarios(validated_scenarios)
   ```

3. **Fase 2: Geração**
   ```python
   # GeneratorAgent
   maven_project = await generator.create_maven_project(context)
   test_classes = await generator.generate_test_classes(scenarios, context)
   enhanced_classes = await generator.enhance_with_llm(test_classes)  # opcional
   await generator.validate_code(enhanced_classes)
   ```

4. **Fase 3: Compilação**
   ```python
   # CompilerCorrectorAgent
   compilation_result = await compiler.compile_project(maven_project)
   if not compilation_result.success:
       errors = await compiler.parse_errors(compilation_result)
       await compiler.fix_errors(errors)
       compilation_result = await compiler.verify_compilation()
   ```

5. **Fase 4: Testes**
   ```python
   # TestCorrectorAgent
   test_result = await test_corrector.run_tests(maven_project)
   if test_result.failures:
       failures = await test_corrector.parse_failures(test_result)
       await test_corrector.fix_failures(failures)
       test_result = await test_corrector.verify_tests()
   ```

6. **Fase 5: Validação**
   ```python
   # IntegrationValidator
   validation_result = await validator.validate_project(maven_project)
   final_report = await coordinator.generate_report(validation_result)
   ```

---

## Estruturas de Dados

### Modelos de Configuração

```python
@dataclass
class AgentConfig:
    name: str
    model: str
    max_tokens: int = 4000
    temperature: float = 0.1
    timeout: int = 60

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
class SystemConfig:
    openrouter: OpenRouterConfig
    maven: MavenConfig
    test_generation: TestGenerationConfig
```

### Modelos de Dados Java

```python
@dataclass
class JavaClass:
    name: str
    package: str
    file_path: str
    annotations: List[str]
    methods: List[JavaMethod]
    fields: List[JavaField]
    imports: List[str]
    extends: Optional[str]
    implements: List[str]

@dataclass
class JavaMethod:
    name: str
    return_type: str
    parameters: List[JavaParameter]
    annotations: List[str]
    visibility: str
    is_static: bool
    is_abstract: bool
    body: Optional[str]
    line_number: int

@dataclass
class RestEndpoint:
    path: str
    method: str  # GET, POST, PUT, DELETE, PATCH
    java_method: str
    java_class: str
    parameters: List[Dict[str, Any]]
    return_type: str
    annotations: List[str]
    status_codes: List[int]
    parameter_validations: Dict[str, Any]
    description: str
```

### Modelos de Teste

```python
@dataclass
class TestScenario:
    name: str
    description: str
    method: str
    endpoint: str
    expected_status: int
    test_data: Optional[Dict[str, Any]]
    path_parameters: Dict[str, Any]
    query_parameters: Dict[str, Any]
    headers: Dict[str, str]
    expected_response_schema: Optional[Dict[str, Any]]
    is_negative_test: bool
    from_source_code: bool
    tags: List[str]
    priority: int
    timeout: Optional[int]

@dataclass
class TestClass:
    class_name: str
    package_name: str
    file_path: str
    scenarios: List[TestScenario]
    imports: List[str]
    setup_methods: List[str]
    teardown_methods: List[str]
    helper_methods: List[str]
```

### Modelos de Resultado

```python
@dataclass
class GenerationResult:
    success: bool
    output_path: str
    maven_project_path: str
    test_files: List[str]
    scenarios_count: int
    compilation_success: bool
    test_execution_success: bool
    errors: List[str]
    warnings: List[str]
    execution_time: float
    
@dataclass
class CompilationError:
    file_path: str
    line_number: int
    column_number: int
    error_type: str
    message: str
    suggested_fix: Optional[str]
    severity: str  # ERROR, WARNING, INFO

@dataclass
class TestFailure:
    test_class: str
    test_method: str
    failure_type: str
    message: str
    stack_trace: str
    suggested_fix: Optional[str]
    is_intermittent: bool
```

---

## Uso de LLM

### Integração com OpenRouter

O sistema utiliza o OpenRouter como gateway para múltiplos modelos LLM:

```python
class OpenRouterClient:
    def __init__(self, config: OpenRouterConfig):
        self.api_key = config.api_key
        self.api_base = config.api_base
        self.default_model = config.default_model
        self.rate_limiter = RateLimiter(config)
    
    async def generate_test_scenarios(self, api_spec: str, context: str) -> List[TestScenario]
    async def generate_test_code(self, scenarios: List[TestScenario], context: str) -> str
    async def fix_compilation_error(self, error: CompilationError, code: str) -> str
    async def fix_test_failure(self, failure: TestFailure, code: str) -> str
```

### Modelos Suportados

- **GPT-4o-mini**: Modelo padrão para tarefas gerais
- **GPT-4**: Para tarefas complexas de análise
- **Claude-3**: Alternativa para geração de código
- **Llama-3**: Opção open-source

### Rate Limiting

```python
class RateLimiter:
    def __init__(self, config: OpenRouterConfig):
        self.requests_per_minute = config.rate_limit_requests_per_minute
        self.tokens_per_minute = config.rate_limit_tokens_per_minute
        self.retry_attempts = config.retry_attempts
        self.retry_delay = config.retry_delay
        self.backoff_factor = config.backoff_factor
```

### Prompts Especializados

#### PlannerAgent - Geração de Cenários
```python
SCENARIO_GENERATION_PROMPT = """
Analise a seguinte especificação de API e gere cenários de teste realistas:

API Specification:
{api_spec}

Source Code Analysis:
{source_analysis}

Gere cenários que incluam:
1. Testes de sucesso com dados válidos
2. Testes de erro com dados inválidos
3. Testes de edge cases
4. Testes de validação de parâmetros

Formato de saída: JSON com estrutura TestScenario
"""
```

#### GeneratorAgent - Enhancement de Código
```python
CODE_ENHANCEMENT_PROMPT = """
Melhore o seguinte código de teste Java:

Template Code:
{template_code}

Project Context:
{project_context}

Melhorias desejadas:
1. Assertions mais específicas
2. Validações de response body
3. Tratamento de edge cases
4. Comentários explicativos

Retorne APENAS o código Java melhorado, sem comentários adicionais.
"""
```

#### CompilerCorrectorAgent - Correção de Erros
```python
COMPILATION_FIX_PROMPT = """
Corrija o seguinte erro de compilação Java:

Error:
{error_message}

Code Context:
{code_context}

File: {file_path}
Line: {line_number}

Forneça a correção mínima necessária para resolver o erro.
Retorne APENAS o código corrigido.
"""
```

#### TestCorrectorAgent - Correção de Falhas
```python
TEST_FIX_PROMPT = """
Corrija a seguinte falha de teste:

Test Failure:
{failure_message}

Test Method:
{test_method}

Stack Trace:
{stack_trace}

Analise a falha e forneça uma correção que:
1. Resolva o problema raiz
2. Mantenha a intenção do teste
3. Use assertions apropriadas

Retorne APENAS o método de teste corrigido.
"""
```

---

## Parsers e Utilitários

### OpenAPIParser

**Responsabilidade**: Análise de especificações OpenAPI/Swagger

```python
class OpenAPIParser:
    def parse_specification(self, spec_path: str) -> OpenAPISpec
    def extract_endpoints(self, spec: OpenAPISpec) -> List[Endpoint]
    def extract_schemas(self, spec: OpenAPISpec) -> Dict[str, Schema]
    def generate_test_data(self, schema: Schema) -> Dict[str, Any]
```

**Funcionalidades**:
- Suporte para OpenAPI 3.0+ e Swagger 2.0
- Extração de endpoints, schemas e parâmetros
- Geração de dados de teste baseados em schemas
- Validação de especificações

### JavaParser

**Responsabilidade**: Análise de código fonte Java

```python
class JavaParser:
    def parse_project(self, project_path: str) -> JavaProject
    def parse_file(self, file_path: str) -> JavaClass
    def extract_rest_endpoints(self, classes: List[JavaClass]) -> List[RestEndpoint]
    def extract_annotations(self, content: str) -> List[str]
```

**Funcionalidades**:
- Parsing de classes, métodos e anotações Java
- Extração de endpoints REST (JAX-RS)
- Análise de anotações @Path, @GET, @POST, etc.
- Combinação de paths de classe e método

### MavenParser

**Responsabilidade**: Análise de projetos Maven

```python
class MavenParser:
    def parse_project(self, project_path: str) -> MavenProject
    def extract_dependencies(self, pom_path: str) -> List[Dependency]
    def extract_project_info(self, pom_path: str) -> ProjectInfo
```

**Funcionalidades**:
- Parsing de arquivos pom.xml
- Extração de dependências e configurações
- Análise de estrutura de diretórios Maven

### MavenRunner

**Responsabilidade**: Execução de comandos Maven

```python
class MavenRunner:
    def compile(self, project_path: str) -> CompilationResult
    def test(self, project_path: str) -> TestResult
    def parse_compilation_errors(self, output: str) -> List[CompilationError]
    def parse_test_failures(self, output: str) -> List[TestFailure]
```

**Funcionalidades**:
- Execução de comandos Maven (compile, test)
- Parsing de saída do Maven
- Extração de erros e falhas
- Timeout e controle de processo

---

## Templates e Geração de Código

### JUnitTemplate

**Responsabilidade**: Geração de classes de teste JUnit 4

```python
class JUnitTemplate:
    def generate_test_class(self, context: ProjectContext, scenarios: List[TestScenario]) -> str
    def generate_test_method(self, scenario: TestScenario) -> str
    def generate_helper_methods(self) -> str
    def generate_ignored_test(self, scenario: TestScenario, reason: str) -> str
```

**Templates Jinja2**:
```python
# Template de classe de teste
test_class_template = Template('''
package {{ package_name }};

import org.junit.Before;
import org.junit.Test;
import org.junit.After;
import org.junit.BeforeClass;
import org.junit.AfterClass;
import static org.junit.Assert.*;
import static org.hamcrest.Matchers.*;

import io.restassured.RestAssured;
import io.restassured.response.Response;
import io.restassured.specification.RequestSpecification;
import static io.restassured.RestAssured.*;
import io.restassured.http.ContentType;

public class {{ class_name }} {
    
    private static final String BASE_URL = "{{ base_url }}";
    private static final int DEFAULT_TIMEOUT = {{ default_timeout }};
    
    @BeforeClass
    public static void setUpClass() {
        RestAssured.baseURI = BASE_URL;
        RestAssured.enableLoggingOfRequestAndResponseIfValidationFails();
    }
    
    @AfterClass
    public static void tearDownClass() {
        RestAssured.reset();
    }
    
    @Before
    public void setUp() {
        // Setup before each test
    }
    
    @After
    public void tearDown() {
        // Cleanup after each test
    }
    
{% for test_method in test_methods %}
    {{ test_method }}
    
{% endfor %}
    
    // Helper methods
    
    private RequestSpecification givenDefaultRequest() {
        return given()
            .contentType(ContentType.JSON)
            .accept(ContentType.JSON);
    }
    
    private void validateResponseTime(Response response) {
        response.then().time(lessThan((long) DEFAULT_TIMEOUT * 1000));
    }
    
    private void validateJsonResponse(Response response) {
        response.then().contentType(ContentType.JSON);
    }
}
''')
```

### MavenProjectTemplate

**Responsabilidade**: Geração de estrutura Maven

```python
class MavenProjectTemplate:
    def create_project(self, project_path: str, context: ProjectContext) -> MavenProject
    def generate_pom_xml(self, context: ProjectContext) -> str
    def create_directory_structure(self, project_path: str) -> None
    def add_test_class(self, project_path: str, test_class: str) -> None
```

**Template pom.xml**:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    
    <groupId>{{ group_id }}</groupId>
    <artifactId>{{ artifact_id }}</artifactId>
    <version>{{ version }}</version>
    <packaging>jar</packaging>
    
    <name>{{ project_name }}</name>
    <description>{{ project_description }}</description>
    
    <properties>
        <maven.compiler.source>11</maven.compiler.source>
        <maven.compiler.target>11</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
        <junit.version>4.13.2</junit.version>
        <rest-assured.version>5.3.0</rest-assured.version>
        <hamcrest.version>2.2</hamcrest.version>
    </properties>
    
    <dependencies>
        <!-- JUnit 4 -->
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>${junit.version}</version>
            <scope>test</scope>
        </dependency>
        
        <!-- Rest Assured -->
        <dependency>
            <groupId>io.rest-assured</groupId>
            <artifactId>rest-assured</artifactId>
            <version>${rest-assured.version}</version>
            <scope>test</scope>
        </dependency>
        
        <!-- Hamcrest -->
        <dependency>
            <groupId>org.hamcrest</groupId>
            <artifactId>hamcrest</artifactId>
            <version>${hamcrest.version}</version>
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
                    <source>11</source>
                    <target>11</target>
                </configuration>
            </plugin>
            
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>
                <version>3.0.0-M7</version>
                <configuration>
                    <includes>
                        <include>**/*Test.java</include>
                        <include>**/*Tests.java</include>
                    </includes>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
```

### RestAssuredTemplate

**Responsabilidade**: Geração de código Rest Assured

```python
class RestAssuredTemplate:
    def generate_request(self, scenario: TestScenario) -> str
    def generate_assertions(self, scenario: TestScenario) -> str
    def generate_path_parameters(self, parameters: Dict[str, Any]) -> str
    def generate_query_parameters(self, parameters: Dict[str, Any]) -> str
```

**Padrões de Código**:
```java
// Request básico
Response response = givenDefaultRequest()
    .pathParam("id", "123")
    .queryParam("format", "json")
.when()
    .get("/api/users/{id}")
.then()
    .statusCode(200)
    .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
    .contentType(ContentType.JSON)
    .body("id", equalTo("123"))
    .body("name", notNullValue())
    .extract().response();

// Validações adicionais
validateResponseTime(response);
validateJsonResponse(response);
```

---

## Configuração e Deployment

### Arquivo de Configuração (.env)

```bash
# OpenRouter Configuration
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_API_BASE=https://openrouter.ai/api/v1
OPENROUTER_DEFAULT_MODEL=openai/gpt-4o-mini

# Rate Limiting
OPENROUTER_RATE_LIMIT_REQUESTS_PER_MINUTE=60
OPENROUTER_RATE_LIMIT_TOKENS_PER_MINUTE=100000
OPENROUTER_RETRY_ATTEMPTS=3
OPENROUTER_RETRY_DELAY=1.0
OPENROUTER_BACKOFF_FACTOR=2.0

# Maven Configuration
MAVEN_TIMEOUT=300
MAVEN_MEMORY=2g
JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
MAVEN_HOME=/usr/share/maven

# Test Generation
DEFAULT_TIMEOUT=30
GENERATE_NEGATIVE_TESTS=true
INCLUDE_PERFORMANCE_TESTS=false
MAX_GENERATION_ATTEMPTS=3
MAX_COMPILE_CORRECTION_ATTEMPTS=5
MAX_TEST_CORRECTION_ATTEMPTS=3
```

### Instalação e Setup

```bash
# 1. Instalar dependências Python
pip install -r requirements.txt

# 2. Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas configurações

# 3. Verificar instalação do Maven
mvn --version

# 4. Verificar instalação do Java
java --version

# 5. Executar testes do sistema
python -m pytest tests/
```

### Uso via CLI

```bash
# Comando básico
python main.py generate \
    --api-spec path/to/openapi.yaml \
    --output output/directory \
    --base-url http://localhost:8080/api

# Com código fonte Java
python main.py generate \
    --api-spec path/to/openapi.yaml \
    --api-src path/to/java/source \
    --output output/directory \
    --base-url http://localhost:8080/api

# Opções avançadas
python main.py generate \
    --api-spec path/to/openapi.yaml \
    --api-src path/to/java/source \
    --output output/directory \
    --base-url http://localhost:8080/api \
    --package-name com.example.tests \
    --class-name ApiIntegrationTest \
    --skip-compilation \
    --skip-test-run \
    --verbose
```

---

## Exemplos de Uso

### Exemplo 1: API REST Countries

```bash
# Geração de testes para API REST Countries
python main.py generate \
    --api-spec examples/restcountries.yaml \
    --api-src examples/restcountries \
    --output output/restcountries-tests \
    --base-url http://localhost:8090/restcountries-2.0.5/rest
```

**Resultado**:
- 40 cenários de teste únicos
- Cobertura completa de endpoints v1 e v2
- Testes de sucesso e erro
- Validações de response time e formato

### Exemplo 2: API Simples (apenas OpenAPI)

```bash
# Geração apenas com especificação OpenAPI
python main.py generate \
    --api-spec api/petstore.yaml \
    --output output/petstore-tests \
    --base-url https://petstore.swagger.io/v2
```

**Resultado**:
- Cenários baseados na especificação
- Dados de teste gerados automaticamente
- Validações de schema

### Exemplo 3: Projeto Existente

```bash
# Análise de projeto Java existente
python main.py generate \
    --api-src src/main/java/com/example/api \
    --output output/existing-project-tests \
    --base-url http://localhost:8080/api \
    --package-name com.example.tests
```

**Resultado**:
- Extração de endpoints do código fonte
- Análise de anotações JAX-RS
- Geração de testes específicos para implementação

### Estrutura de Saída

```
output/
├── generated-tests/
│   └── maven-project/
│       ├── pom.xml
│       ├── src/
│       │   └── test/
│       │       └── java/
│       │           └── com/
│       │               └── example/
│       │                   └── tests/
│       │                       └── ApiIntegrationTest.java
│       └── scenarios/
│           ├── api-test-scenarios.json
│           └── test-set-scenario.json
└── logs/
    └── generation.log
```

### Arquivo de Teste Gerado

```java
package com.example.tests;

import org.junit.Before;
import org.junit.Test;
import org.junit.After;
import org.junit.BeforeClass;
import org.junit.AfterClass;
import static org.junit.Assert.*;
import static org.hamcrest.Matchers.*;

import io.restassured.RestAssured;
import io.restassured.response.Response;
import io.restassured.specification.RequestSpecification;
import static io.restassured.RestAssured.*;
import io.restassured.http.ContentType;

/**
 * Integration tests for REST Countries API
 * Generated by API Test Generator System
 * 
 * Base URL: http://localhost:8090/restcountries-2.0.5/rest
 * API Version: 2.0.5
 */
public class ApiIntegrationTest {
    
    private static final String BASE_URL = "http://localhost:8090/restcountries-2.0.5/rest";
    private static final int DEFAULT_TIMEOUT = 30;
    
    @BeforeClass
    public static void setUpClass() {
        RestAssured.baseURI = BASE_URL;
        RestAssured.enableLoggingOfRequestAndResponseIfValidationFails();
    }
    
    @AfterClass
    public static void tearDownClass() {
        RestAssured.reset();
    }
    
    @Before
    public void setUp() {
        // Setup before each test
    }
    
    @After
    public void tearDown() {
        // Cleanup after each test
    }

    /**
     * Test successful retrieval of all countries
     */
    @Test
    public void testGetAllCountriesSuccess() {
        Response response = givenDefaultRequest()
        .when()
            .get("/v2/all")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .body("", not(empty()))
            .body("size()", greaterThan(0))
            .extract().response();
        
        validateResponseTime(response);
        validateJsonResponse(response);
    }

    /**
     * Test retrieval of country by name
     */
    @Test
    public void testGetCountryByNameSuccess() {
        Response response = givenDefaultRequest()
            .pathParam("name", "portugal")
        .when()
            .get("/v2/name/{name}")
        .then()
            .statusCode(200)
            .time(lessThan((long) DEFAULT_TIMEOUT * 1000))
            .contentType(ContentType.JSON)
            .body("", not(empty()))
            .body("size()", greaterThan(0))
            .extract().response();
        
        validateResponseTime(response);
        validateJsonResponse(response);
    }
    
    // ... mais 38 métodos de teste ...
    
    // Helper methods
    
    private RequestSpecification givenDefaultRequest() {
        return given()
            .contentType(ContentType.JSON)
            .accept(ContentType.JSON);
    }
    
    private void validateResponseTime(Response response) {
        response.then().time(lessThan((long) DEFAULT_TIMEOUT * 1000));
    }
    
    private void validateJsonResponse(Response response) {
        response.then().contentType(ContentType.JSON);
    }
}
```

---

## Conclusão

O Sistema Multi-Agente para Geração de Testes de API representa uma solução robusta e automatizada para criação de testes de integração. Através da coordenação de agentes especializados, o sistema é capaz de:

1. **Analisar** especificações OpenAPI e código fonte Java
2. **Gerar** cenários de teste realistas e abrangentes
3. **Produzir** código Java válido e compilável
4. **Corrigir** automaticamente erros de compilação e teste
5. **Validar** a qualidade e cobertura dos testes gerados

A arquitetura modular permite extensibilidade e manutenibilidade, enquanto a integração com LLM proporciona inteligência na geração e correção de código. O sistema é adequado tanto para projetos novos quanto para análise de APIs existentes, fornecendo uma base sólida para testes automatizados.

### Benefícios Principais

- **Automação Completa**: Reduz significativamente o tempo de criação de testes
- **Qualidade Garantida**: Código sempre compilável e estruturalmente válido
- **Cobertura Abrangente**: Testes de sucesso, erro e edge cases
- **Flexibilidade**: Suporte a diferentes tipos de API e estruturas de projeto
- **Inteligência**: Enhancement via LLM para otimização de testes

### Próximos Passos

- Suporte a mais frameworks de teste (TestNG, JUnit 5)
- Integração com ferramentas de CI/CD
- Geração de relatórios de cobertura
- Suporte a APIs GraphQL
- Interface web para configuração e monitoramento

---

**Documentação gerada automaticamente pelo Sistema Multi-Agente para Geração de Testes de API**  
**Versão 1.0.0 - Agosto 2025**

