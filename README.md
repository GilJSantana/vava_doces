<div align="center">
  <img src="assets/logo.png" alt="Vava Doces Logo" width="200" height="200" style="border-radius: 20px;">
</div>

# Vava Doces - Análise de Custos e Faturamento

## 📋 Sobre o Projeto

Este projeto fornece ferramentas para análise de custos de produção e faturamento para a loja Vava Doces. A ideia é conectar os dados (planilhas Google / Excel) a serviços de domínio que calculam custo por receita, margens e outras métricas de negócio.

O repositório foi organizado com boas práticas (injeção de dependência, separação entre *ports* e *adapters*, e testes orientados por TDD) para facilitar manutenção e evolução.

---

## 🧭 Visão rápida

- Linguagem: Python
- Gerenciador de ambiente/execução aqui usado: `uv` (conforme seu fluxo)
- Testes: `pytest`
- Principais bibliotecas: `pandas`, `gspread` (para Google Sheets; adaptador), `decimal` (para precisão financeira)

---

## 🎨 Interface Streamlit

A aplicação Streamlit oferece uma interface interativa para visualizar e analisar os dados:

### Funcionalidades principais:

- **📊 Dashboard**: Visão geral dos custos com gráficos e métricas principais
- **💰 Custos**: Visualização detalhada dos dados de custos com filtros
- **📈 Faturamento**: Análise de vendas e faturamento
- **🔍 Análise Detalhada**: Relatórios avançados e análises de margens

### Como executar:

```bash
./run_app.sh
# ou
uv run streamlit run app.py
```

Acesse em seu navegador: `http://localhost:8501`

Para documentação completa, veja [STREAMLIT_SETUP.md](./STREAMLIT_SETUP.md)

---

## 🗂 Estrutura do projeto

- `app.py` — aplicação Streamlit para visualização de dados.
- `run_app.sh` — script para executar a aplicação.
- `.env.example` — arquivo de exemplo para configuração de credenciais.
- `.streamlit/config.toml` — configuração da aplicação Streamlit.
- `STREAMLIT_SETUP.md` — documentação completa sobre execução do Streamlit.
- `src/` — código fonte
  - `src/ports/data_source.py` — contrato/porta `DataSource` e exceção `DataSourceError`.
  - `src/infrastructure/google_sheets_adapter.py` — adaptador que implementa `DataSource` e acessa Google Sheets (usa `gspread`).
  - `src/domain/cost_analysis_service.py` — serviço de domínio que implementa regras e calcula custo por receita (injeção de `DataSource`).
- `tests/` — suíte de testes (pytest)
  - `tests/test_cost_analysis_service.py` — testes de unidade para `CostAnalysisService` (usa um `FakeDataSource`).
  - `tests/test_google_sheets_adapter.py` — testes do adaptador com mocks do `gspread`.
  - `tests/test_streamlit_app.py` — testes para funções auxiliares da aplicação Streamlit.
- `RECEITAS AWI.xlsx` — planilha de referência/entrada para alinhamento de esquema (não é usada diretamente pelos testes).

---

## Como rodar localmente (com `uv`)

Observação: neste repositório você informou que está usando o gerenciador `uv`. Os comandos abaixo assumem que as dependências foram instaladas no ambiente gerenciado por `uv`.

### 1. Instalar dependências

```bash
# Instalar todas as dependências
uv install
```

### 2. Configurar credenciais do Google Sheets

```bash
# Copiar arquivo de exemplo
cp .env.example .env

# Editar com seus dados
nano .env
```

Configure:
- `GOOGLE_APPLICATION_CREDENTIALS`: Caminho para o JSON da Service Account
- `GOOGLE_SHEET_ID`: ID da sua planilha

### 3. Rodar testes

```bash
# Rodar todos os testes
uv run pytest -q

# Rodar teste específico
uv run pytest -q tests/test_cost_analysis_service.py::test_calculate_cost_per_recipe_happy_path

# Rodar com cobertura
uv run pytest --cov=src tests/
```

### 4. Executar a aplicação Streamlit

```bash
# Usando o script (recomendado)
./run_app.sh

# Ou diretamente
uv run streamlit run app.py

# Abrir no navegador
# http://localhost:8501
```

Para mais detalhes sobre a configuração do Streamlit, consulte [STREAMLIT_SETUP.md](./STREAMLIT_SETUP.md).

---

## Configuração de credenciais do Google (Sheets)

Recomendamos usar uma Service Account para ambientes servidor/CI. Dois modos comuns:

A) Usando `GOOGLE_APPLICATION_CREDENTIALS` (Service Account JSON):

1. Crie uma Service Account no Google Cloud Console e faça o download do JSON da chave.
2. Dê acesso de leitura (e se necessário escrita) à planilha compartilhando-a com o e-mail da Service Account.
3. Defina a variável de ambiente antes de rodar a aplicação/tests:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/caminho/para/service-account.json"
```

No `GoogleSheetsAdapter` você pode também passar o caminho do arquivo via construtor (argumento `credential_file`) em vez de depender da variável.

B) Autenticação local (desenvolvimento):

- Alternativa: `gcloud auth application-default login` para usar suas credenciais de usuário localmente (não recomendado para CI).

Segurança:
- Nunca comite o JSON de credenciais no repositório. Use secrets no CI (ex.: GitHub Secrets) e grave o conteúdo em arquivo temporário na etapa do job.

---

## Contratos, design e boas práticas aplicadas

- Interface/porta `DataSource` (em `src/ports/data_source.py`): abstrai a fonte de dados (Google Sheets, CSV, DB). O domínio depende dessa abstração (Dependency Inversion).
- `GoogleSheetsAdapter` (adapter): responsabilidade única — autenticar e converter resposta da API para `pandas.DataFrame`.
- `CostAnalysisService` (domain): contém regras de negócio (cálculo de custo) e validação. Recebe um `DataSource` por injeção de dependência.
- Erros: adaptadores normalizam exceções para `DataSourceError` para facilitar tratamento e testes.
- Testes escritos com TDD em mente: primeiro os testes de domínio com mocks/fakes, depois implementação da infraestrutura.

Principais princípios: SOLID (SRP, DIP, ISP, OCP) e testes unitários para regras de negócio.

---

## Como o `CostAnalysisService` é esperado agir

- Método principal disponível: `calculate_cost_per_recipe(sheet_name: str) -> Dict[str, Decimal]`.
- Entrada esperada: um `DataFrame` com pelo menos as colunas (case-insensitive) `recipe`, `qty`, `unit_price`.
- Comportamento:
  - Se a folha estiver vazia, retorna `{}`.
  - Se faltar coluna obrigatória, lança `ValueError` com mensagem clara.
  - Usa `decimal.Decimal` para somas de valores monetários (evita imprecisão de floats).

---

## Execução de desenvolvimento (fluxo recomendado)

- Use TDD: escreva um teste unitário em `tests/` que descreva o comportamento desejado do domínio.
- Faça o teste falhar (red).
- Implemente a lógica mínima no `CostAnalysisService`/adapter (green).
- Refatore preservando os testes.

---

## Riscos e pontos de atenção

- Credenciais no repositório: não comitar arquivos de chave.
- Formato dos dados: células vazias, separadores decimais (vírgula vs ponto) podem causar `ValueError`. Normalizar no adaptador se precisar.
- Quotas da API Google: para leituras frequentes, implemente cache ou backoff.

---

## Próximos passos e melhorias sugeridas

- Adicionar verificação de schema (validar cabeçalho com regras configuráveis) e um adaptador de validação antes do serviço de domínio.
- Implementar caching para leituras frequentes (ex.: Redis ou cache local com TTL).
- Expor um CLI simples ou uma API HTTP (FastAPI/Flask) para executar análises remotamente.
- Adicionar um pipeline de CI (GitHub Actions) que:
  - Instale dependências (usando `uv` se aplicável),
  - Rode `uv run pytest -q`,
  - Não exponha credenciais (use secrets do repositório).

---

## Contato e contribuições

Contribuições são bem-vindas. Abra issues para descrever bugs ou melhorias e PRs para mudanças implementadas com testes.

---

_Boa prática: sempre rode a suíte de testes (`uv run pytest`) antes de abrir um PR._
