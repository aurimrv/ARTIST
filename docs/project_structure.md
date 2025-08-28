# Estrutura do Projeto - Sistema Multi-Agente para Geração de Testes de API

## Visão Geral da Estrutura

```
api-test-generator-system/
├── src/                          # Código fonte principal
│   ├── agents/                   # Implementação dos agentes
│   │   ├── __init__.py
│   │   ├── base_agent.py        # Classe base para todos os agentes
│   │   ├── coordinator_agent.py # Agente coordenador
│   │   ├── planner_agent.py     # Agente planejador
│   │   ├── generator_agent.py   # Agente gerador
│   │   ├── compiler_corrector_agent.py # Agente corretor de compilação
│   │   └── test_corrector_agent.py     # Agente corretor de testes
│   ├── utils/                    # Utilitários e helpers
│   │   ├── __init__.py
│   │   ├── openrouter_client.py # Cliente para OpenRouter API
│   │   ├── rate_limiter.py      # Controle de rate limiting
│   │   ├── maven_runner.py      # Executor de comandos Maven
│   │   ├── file_utils.py        # Utilitários para arquivos
│   │   └── logger.py            # Sistema de logging
│   ├── parsers/                  # Parsers para diferentes formatos
│   │   ├── __init__.py
│   │   ├── openapi_parser.py    # Parser para OpenAPI/Swagger
│   │   ├── java_parser.py       # Parser para código Java
│   │   └── maven_parser.py      # Parser para projetos Maven
│   ├── templates/                # Templates para geração de código
│   │   ├── __init__.py
│   │   ├── junit_template.py    # Templates JUnit 4
│   │   ├── rest_assured_template.py # Templates Rest Assured
│   │   └── maven_project_template.py # Template projeto Maven
│   ├── config/                   # Configurações do sistema
│   │   ├── __init__.py
│   │   ├── settings.py          # Carregamento de configurações
│   │   └── models.py            # Modelos de dados
│   └── cli/                      # Interface de linha de comando
│       ├── __init__.py
│       └── main.py              # Ponto de entrada principal
├── tests/                        # Testes unitários
│   ├── __init__.py
│   ├── test_agents/
│   ├── test_utils/
│   ├── test_parsers/
│   └── test_templates/
├── examples/                     # Exemplos e casos de teste
│   ├── restcountries/           # Exemplo REST Countries
│   └── sample_outputs/          # Exemplos de saída
├── docs/                         # Documentação
│   ├── project_structure.md     # Este arquivo
│   ├── api_reference.md         # Referência da API
│   └── user_guide.md            # Guia do usuário
├── main.py                       # Ponto de entrada do sistema
├── requirements.txt              # Dependências Python
├── .env.example                  # Exemplo de configuração
├── .gitignore                    # Arquivos ignorados pelo Git
└── README.md                     # Documentação principal
```

## Descrição dos Componentes

### Agentes (`src/agents/`)
- **base_agent.py**: Classe abstrata base com funcionalidades comuns
- **coordinator_agent.py**: Orquestra todo o processo de geração
- **planner_agent.py**: Analisa API e cria cenários de teste
- **generator_agent.py**: Gera código de teste JUnit/Rest Assured
- **compiler_corrector_agent.py**: Corrige erros de compilação
- **test_corrector_agent.py**: Corrige falhas de execução de testes

### Utilitários (`src/utils/`)
- **openrouter_client.py**: Cliente HTTP para API OpenRouter
- **rate_limiter.py**: Implementa rate limiting e retry logic
- **maven_runner.py**: Executa comandos Maven e analisa resultados
- **file_utils.py**: Operações de arquivo e diretório
- **logger.py**: Sistema de logging configurável

### Parsers (`src/parsers/`)
- **openapi_parser.py**: Extrai informações de especificações OpenAPI/Swagger
- **java_parser.py**: Analisa código Java para extrair estruturas
- **maven_parser.py**: Analisa projetos Maven (pom.xml, estrutura)

### Templates (`src/templates/`)
- **junit_template.py**: Gera código de teste JUnit 4
- **rest_assured_template.py**: Gera código Rest Assured
- **maven_project_template.py**: Cria estrutura de projeto Maven

### Configuração (`src/config/`)
- **settings.py**: Carrega configurações do .env e valida
- **models.py**: Classes de dados para configuração e estado

### CLI (`src/cli/`)
- **main.py**: Interface de linha de comando com argparse

## Fluxo de Dados

1. **Entrada**: CLI recebe parâmetros e carrega configurações
2. **Coordenação**: Coordinator Agent inicia o processo
3. **Planejamento**: Planner Agent analisa API spec e código
4. **Geração**: Generator Agent cria testes baseados nos cenários
5. **Compilação**: Compiler_Corrector Agent corrige erros de compilação
6. **Execução**: Test_Corrector Agent corrige falhas de teste
7. **Saída**: Projeto Maven com testes funcionais

## Dependências Principais

### Python
- `requests`: Comunicação HTTP com OpenRouter
- `pyyaml`: Parsing de arquivos YAML
- `jinja2`: Sistema de templates
- `python-dotenv`: Carregamento de variáveis de ambiente
- `click`: Interface de linha de comando avançada
- `pathlib`: Manipulação de caminhos
- `subprocess`: Execução de comandos externos
- `json`: Parsing JSON
- `re`: Expressões regulares
- `logging`: Sistema de logs

### Java (para testes gerados)
- JUnit 4.12+
- Rest Assured 4.x+
- Maven 3.6+
- Java 8 (JDK 8)

## Padrões de Desenvolvimento

### Agentes
- Herdam de `BaseAgent`
- Implementam interface comum
- Usam dependency injection para configurações
- Logging estruturado
- Tratamento de erros padronizado

### Configuração
- Variáveis de ambiente via .env
- Validação de configurações na inicialização
- Configurações específicas por agente
- Fallbacks para valores padrão

### Templates
- Sistema baseado em Jinja2
- Templates modulares e reutilizáveis
- Parâmetros tipados
- Validação de entrada

### Testes
- Testes unitários para cada componente
- Mocks para APIs externas
- Testes de integração com exemplos reais
- Cobertura de código > 80%

