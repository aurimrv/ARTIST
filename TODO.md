# Output generted_test with timestamp

# Parameters

--api-spec (opcional) --api-src (mandatory)
--api-src (opcional) --api-spec (mandatory)

# Specification Coverage (closed-box)

## Criar um relatório que demonstre quais testes foram criados para quais itens da especificação em OpenAPI

# Code Coverage (open-box)

## Configurável desde que exista o código fonte .env

USE_COVERGE_INFORMATION=true

## Melhorar projeto Maven dos testes para incluir o plugin de medir a cobertura de código

## Gerar o relatório de cobertura

## Criar um novo agente que, após executar os testes e medir a cobetura, use os dados do relatório par criar novos testes priorizando cobrir áreas não cobertas pelos testes atuais.

# Mapear Input/Output de cada agente

Cada agente poderia receber de entrada as informações em algum formato e produzir sua saída em algum formato para ser consumido para outro agente.

Isso permitiria realizar o processamento passo a passo. Agente por agente. Ou até mesmo ter agentes diferentes consumindo a saída de um agente inicial.

## Code with exit worflows commented