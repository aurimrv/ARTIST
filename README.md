# API Test Generator System

O **API Test Generator System** é uma ferramenta baseada em agentes LLM (Large Language Models) projetada para gerar, compilar e corrigir automaticamente testes de integração em Java (JUnit 4 + RestAssured) a partir de especificações OpenAPI (Swagger).

O sistema utiliza uma arquitetura multi-agente para planejar cenários de teste, gerar o código-fonte, compilar o projeto Maven e corrigir iterativamente falhas de compilação e execução.

## Funcionalidades Principais

- **Geração Baseada em OpenAPI**: Lê arquivos YAML/JSON e extrai endpoints, parâmetros, schemas e exemplos (`x-parameter-examples`).
- **Arquitetura Multi-Agente**:
  - `PlannerAgent`: Analisa a especificação e gera cenários de teste positivos e negativos.
  - `GeneratorAgent`: Converte os cenários em código Java (JUnit 4 + RestAssured).
  - `CompilerCorrectorAgent`: Tenta compilar o projeto Maven e corrige erros de sintaxe/importação.
  - `TestCorrectorAgent`: Executa os testes e corrige falhas de asserção iterativamente.
- **Testes de Erro 500 (Jersey + Mockito)**: Suporte avançado para simulação de erros internos do servidor usando o padrão de Recurso Substituto (Substitute Resource Pattern).
- **Isolamento de Estado**: Garantia de que cada teste redefine a `baseURI` e limpa o estado do RestAssured (`RestAssured.reset()`) para evitar efeitos colaterais.
- **Determinismo e Reprodutibilidade**: Suporte a configuração de *seed* global e por agente para saídas de LLM consistentes.

## Pré-requisitos

- Python 3.9+
- Java JDK 8 ou superior (configurado no `JAVA_HOME`)
- Apache Maven 3.6+ (configurado no `MAVEN_HOME` ou no `PATH`)
- Chave de API do OpenRouter (para acesso aos modelos LLM)

## Instalação

1. Clone o repositório.
2. Instale as dependências Python:
   ```bash
   pip install -r requirements.txt
   ```
3. Copie o arquivo de configuração de exemplo e preencha sua chave de API:
   ```bash
   cp .env.example .env
   ```

## Uso Básico

O comando principal é o `generate`, que requer pelo menos a especificação da API e o diretório de saída:

```bash
python main.py generate --api-spec swagger.yaml --output ./reports/
```

### Estrutura de Saída

Para cada execução, o sistema cria um diretório com timestamp dentro do diretório de saída especificado:

```text
reports/
└── generated-tests_YYYY-MM-DD_HH-MM-SS/
    ├── maven-project/               # Projeto Java gerado completo (pom.xml, src/)
    └── llm_interactions/            # Logs e snapshots de debug dos agentes LLM
        ├── ..._scenarios_1_raw.json
        ├── ..._scenarios_2_deduplicated.json
        └── ..._scenarios_3_llm_enhanced.json
```

## Parâmetros de Linha de Comando (CLI)

| Parâmetro | Descrição | Obrigatório | Padrão |
|---|---|---|---|
| `--api-spec` | Caminho para o arquivo OpenAPI (YAML/JSON). | Sim | - |
| `--output`, `-o` | Diretório base para a saída gerada. | Sim | - |
| `--api-src` | Caminho para o código-fonte da API (para análise extra). | Não | - |
| `--base-url` | URL base para os testes RestAssured. | Não | `http://localhost:8080` |
| `--package` | Nome do pacote Java para os testes gerados. | Não | Auto-detectado |
| `--class-name` | Nome da classe de teste principal. | Não | `ApiIntegrationTest` |
| `--api-impl` | Caminho para o JAR de implementação da API. Necessário para gerar testes de erro 500 (Mockito/Jersey). | Não | - |
| `--seed` | Seed global para tornar as saídas do LLM determinísticas. | Não | - |
| `--skip-compilation` | Pula as fases de compilação e correção de erros. | Não | `False` |
| `--skip-test-run` | Pula as fases de execução de testes e correção de falhas. | Não | `False` |

## Configuração de Determinismo (Seed)

Para garantir que a geração de testes seja reprodutível entre diferentes execuções, você pode configurar o parâmetro `seed`. A precedência de configuração é a seguinte (do mais forte para o mais fraco):

1. **Seed Específico por Agente (`.env`)**: Variáveis como `PLANNER_SEED=42`, `GENERATOR_SEED=99` no arquivo `.env` têm a precedência máxima.
2. **Seed Global via CLI (`--seed`)**: O parâmetro `--seed 42` na linha de comando sobrescreve o seed global do `.env`, mas respeita os seeds específicos de agentes.
3. **Seed Global (`.env`)**: A variável `SEED=42` no arquivo `.env` atua como fallback para todos os agentes que não possuem um seed específico.

**Exemplo de uso via CLI:**
```bash
python main.py generate --api-spec api.yaml --output tests/ --seed 42
```

## Variáveis de Ambiente (`.env`)

O arquivo `.env` permite configurar o comportamento detalhado do sistema:

- **Autenticação**: `OPENROUTER_API_KEY`, `OPENROUTER_API_BASE`
- **Modelos LLM**: `OPENROUTER_DEFAULT_MODEL`, `PLANNER_MODEL`, `GENERATOR_MODEL`, etc.
- **Limites e Retentativas**: `RATE_LIMIT_REQUESTS_PER_MINUTE`, `RETRY_ATTEMPTS`, `MAX_GENERATION_ATTEMPTS`
- **Determinismo**: `SEED`, `PLANNER_SEED`, `TEMPERATURE`, etc.
- **Ambiente Java**: `JAVA_HOME`, `MAVEN_HOME`

Consulte o arquivo `.env.example` para ver todas as opções disponíveis e seus valores padrão.
