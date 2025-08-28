# API Test Generator System

**Versão:** 1.0.0

Um sistema multi-agente para gerar testes de integração JUnit 4 + Rest Assured para APIs REST com base em especificações OpenAPI e implementações Java.

---

## ✨ Visão Geral

Este sistema automatiza a criação de testes de integração para APIs REST, economizando tempo e esforço para desenvolvedores. Ele usa uma arquitetura multi-agente para analisar especificações de API, gerar código de teste, compilar, executar e corrigir erros automaticamente.

### 🚀 Funcionalidades Principais

- **Geração Automática de Testes**: Cria testes JUnit 4 com Rest Assured a partir de especificações OpenAPI/Swagger.
- **Arquitetura Multi-Agente**: Orquestração inteligente de tarefas com 5 agentes especializados.
- **Correção Automática**: Corrige erros de compilação e falhas de teste usando LLMs e regras.
- **Interface de Linha de Comando**: CLI completa para fácil integração em pipelines de CI/CD.
- **Altamente Configurável**: Personalize modelos, timeouts e comportamento dos agentes.
- **Compatibilidade com Java 8**: Gera projetos Maven compatíveis com Java 8.

### 🤖 Arquitetura Multi-Agente

O sistema é composto por 5 agentes que trabalham juntos para gerar e validar os testes:

1.  **Coordinator Agent**: Orquestra todo o processo, delegando tarefas para os outros agentes.
2.  **Planner Agent**: Analisa a especificação da API e o código-fonte para criar cenários de teste realistas.
3.  **Generator Agent**: Gera o código de teste JUnit 4 + Rest Assured com base nos cenários do Planner.
4.  **Compiler_Corrector Agent**: Compila o código gerado e corrige quaisquer erros de compilação.
5.  **Test_Corrector Agent**: Executa os testes e corrige quaisquer falhas de execução.

---

## 🛠️ Instalação

### Pré-requisitos

- Python 3.8+
- Java 8+
- Maven 3.6+

### Passos de Instalação

1.  **Clone o repositório:**

    ```bash
    git clone https://github.com/api-test-generator/api-test-generator.git
    cd api-test-generator
    ```

2.  **Instale as dependências Python:**

    ```bash
    pip install -r requirements.txt
    ```

3.  **(Opcional) Instale o sistema como um pacote:**

    ```bash
    pip install .
    ```

---

## 🚀 Como Usar

### Comandos da CLI

O sistema fornece uma interface de linha de comando completa para fácil utilização.

#### `generate`

Gera testes de integração para uma API.

```bash
api-test-generator generate --api-spec <spec.yaml> --api-src <src/main/java> --output <output_dir>
```

**Argumentos:**

-   `--api-spec`: Caminho para o arquivo de especificação da API (OpenAPI/Swagger).
-   `--api-src`: Caminho para o diretório de código-fonte da API (projeto Maven).
-   `--output`: Diretório de saída para os testes gerados.
-   `--base-url`: (Opcional) URL base da API (padrão: `http://localhost:8080`).
-   `--package`: (Opcional) Nome do pacote Java para os testes gerados (padrão: auto-detectado).
-   `--config`: (Opcional) Caminho para um arquivo de configuração `.env` customizado.

#### `validate`

Valida a integração e configuração do sistema.

```bash
api-test-generator validate
```

#### `version`

Mostra as informações de versão.

```bash
api-test-generator version
```

### Exemplo de Uso

Para gerar testes para o exemplo `restcountries` incluído:

```bash
api-test-generator generate \
  --api-spec examples/restcountries.yaml \
  --api-src examples/restcountries/src \
  --output generated-tests
```

---

## ⚙️ Configuração

O sistema pode ser configurado usando um arquivo `.env`. Copie o `.env.example` para `.env` e personalize as configurações:

-   `OPENROUTER_API_KEY`: (Opcional) Sua chave de API do OpenRouter para correção de código com LLM.
-   `MAVEN_TIMEOUT`: Timeout para comandos Maven.
-   `LOG_LEVEL`: Nível de log (DEBUG, INFO, WARNING, ERROR).

### Configuração por Agente

Você pode configurar modelos de LLM, max tokens e temperatura para cada agente no arquivo `.env`:

```env
# Exemplo para o Planner Agent
PLANNER_MODEL=openai/gpt-4o
PLANNER_MAX_TOKENS=8000
PLANNER_TEMPERATURE=0.2
```

---

## 🤝 Contribuição

Contribuições são bem-vindas! Sinta-se à vontade para abrir issues e pull requests.

## 📄 Licença

Este projeto está licenciado sob a Licença MIT. Veja o arquivo `LICENSE` para mais detalhes.


