<div align="center">
  <img src="assets/logo.png" alt="Vava Doces Logo" width="200" height="200" style="border-radius: 20px;">
</div>

# Vavá Doces Data App

Aplicação de Business Intelligence e Engenharia de Dados para transformar planilhas operacionais em decisões de rentabilidade.

## Visão Executiva

A Vavá Doces tinha um problema clássico de pequenas operações: havia volume de vendas, mas pouca visibilidade sobre **quanto cada produto realmente contribuía para o lucro**.

Este projeto resolve essa lacuna com um app de dados que:
- integra dados de Google Drive e Google Sheets;
- padroniza e valida os dados em pipeline Medallion;
- publica análises executivas em Streamlit para decisão rápida.

## Problema que o App Resolve

O app foi desenhado para responder à pergunta central:

**"Quais produtos geram lucro de verdade, quais sustentam caixa e quais estão destruindo margem?"**

Sem essa visibilidade, ajustes de preço, compra de insumos e priorização comercial tendem a ser feitos por percepção. Com o app, as decisões passam a ser baseadas em fatos auditáveis.

### Funcionalidades principais:

- `main.py` — script principal (em desenvolvimento).
  - `src/ports/data_source.py` — contrato/porta `DataSource` e exceção `DataSourceError`.
  - `src/infrastructure/google_sheets_adapter.py` — adaptador que implementa `DataSource` e acessa Google Sheets (usa `gspread`).
  - `src/domain/cost_analysis_service.py` — serviço de domínio que implementa regras e calcula custo por receita (injeção de `DataSource`).
- `tests/` — suíte de testes (pytest)
  - `tests/test_cost_analysis_service.py` — testes de unidade para `CostAnalysisService` (usa um `FakeDataSource`).
  - `tests/test_google_sheets_adapter.py` — testes do adaptador com mocks do `gspread`.
  - `tests/test_streamlit_app.py` — testes para funções auxiliares da aplicação Streamlit.
- `RECEITAS AWI.xlsx` — planilha de referência/entrada para alinhamento de esquema (não é usada diretamente pelos testes).

### Bronze
- Ingestão dos arquivos brutos (CSV/XLSX) e exportações auxiliares de planilhas.
- Preservação do dado original para rastreabilidade.

### Silver
- Normalização de colunas, datas, valores monetários e chaves de produto.
- Deduplicação técnica controlada (sem colapsar itens legítimos de pedidos).
- Tratamento de inconsistências para reduzir ruído analítico.

### Gold
- Tabelas analíticas para consumo da aplicação:
  - fato e dimensões (`fato_vendas`, `dim_produto`, `dim_tempo`);
  - agregados de vendas;
  - custos de produção (`custos_producao_agregado`, `receitas_detalhadas`);
  - rentabilidade (`gold_rentabilidade`).
- Preservação de linhagem de `NaN` para evitar falsos positivos de margem.

### 1. Instalar dependências

```bash
# Instalar todas as dependências
uv install
# Ou, se preferir, recrie o ambiente/instale localmente:
# python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
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

Para mais detalhes sobre a configuração do Streamlit, consulte [STREAMLIT_SETUP.md](./docs/STREAMLIT_SETUP.md).

---

2) Rodar testes (usa o pytest no ambiente uv):

uv run pytest -q
# Exemplo genérico (adapte conforme seu uso do uv):

3) Rodar um teste específico:
3. Defina a variável de ambiente antes de rodar a aplicação/tests:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/caminho/para/service-account.json"
```


B) Autenticação local (desenvolvimento):

- Alternativa: `gcloud auth application-default login` para usar suas credenciais de usuário localmente (não recomendado para CI).


---

## Contratos, design e boas práticas aplicadas

- `CostAnalysisService` (domain): contém regras de negócio (cálculo de custo) e validação. Recebe um `DataSource` por injeção de dependência.
- Erros: adaptadores normalizam exceções para `DataSourceError` para facilitar tratamento e testes.
- Testes escritos com TDD em mente: primeiro os testes de domínio com mocks/fakes, depois implementação da infraestrutura.

## Guia de Uso de Negócio (Resumo)

### Matriz de Rentabilidade
A matriz cruza:
- eixo X: volume vendido;
- eixo Y: margem percentual.

Quadrantes e plano de ação:
- **Estrelas**: alto volume e alta margem. Proteger disponibilidade e manter destaque comercial.
- **Vacas Leiteiras**: alto volume e baixa margem. Otimizar custos e revisar preço/tamanho.
- **Dilemas**: baixo volume e alta margem. Testar campanhas e canais para ganhar escala.
- **Problemas**: baixo volume e baixa margem. Reprecificar, reformular ou descontinuar.

### Tabela de Decisão e Alertas
- **Vermelho**: margem negativa (produto em perda).
- **Oliva**: custo/margem ausente (`NaN`), item precisa de auditoria antes de decisão.

Leitura recomendada:
1. tratar primeiro linhas vermelhas;
2. resolver pendências oliva (dados faltantes);
3. priorizar ganhos por quadrante.

## Stack Técnica

- **Python**: orquestração e regras de negócio.
- **Streamlit**: interface executiva.
- **Pandas**: transformação e modelagem tabular.
- **Plotly**: visualizações analíticas interativas.

## Regras de Limpeza e Qualidade de Dados

Princípios aplicados para evitar diagnósticos errados:
- conversão robusta de moeda e datas com fallback controlado;
- padronização de chaves textuais para reduzir mismatches;
- tratamento explícito de `None`/`NaN` em custos;
- invalidação de margem/markup quando custo está ausente ou zero;
- diferenciação entre dado ausente e valor real zero.

Essas regras evitam **falsos positivos de lucratividade** e preservam confiabilidade analítica.

## Execução Local

```bash
uv sync
uv run pytest -q
uv run streamlit run app.py
```

## Documentação Complementar

_Boa prática: sempre rode a suíte de testes (`uv run pytest`) antes de abrir um PR._

---

> Observação: a documentação do projeto foi organizada na pasta `docs/`. Consulte `docs/` para guias, sumários e o roadmap do projeto.
