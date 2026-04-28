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

- `app.py` — entrada principal da aplicação Streamlit com gates de autenticação/autorização.
- `scripts/medallion_pipeline.py` — pipeline RAW → SILVER → GOLD.
- `src/infrastructure/drive_manager.py` — descoberta e I/O em memória dos arquivos `.parquet` no Google Drive.
- `src/presentation/pages/` — três páginas executivas do app:
  - `dashboard.py` — rentabilidade e matriz executiva;
  - `production_costs.py` — auditoria de custos e receitas;
  - `faturamento.py` — exploração auditável das vendas da Gold layer.
- `tests/` — suíte oficial de regressão e integração via `pytest`.
- `scripts/diagnostics/` — diagnósticos manuais opcionais para troubleshooting local.

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
# Instalar/sincronizar dependências do pyproject.toml
uv sync
```

### 2. Configurar credenciais da aplicação

```bash
# Criar arquivo local de secrets a partir do template
cp .streamlit/secrets.toml.example .streamlit/secrets.toml

# Editar com seus dados
nano .streamlit/secrets.toml
```

Configure:
- `OAUTH2_CLIENT_ID`, `OAUTH2_CLIENT_SECRET`, `OAUTH2_REDIRECT_URI`
- `GOOGLE_DRIVE_FOLDER_ID`
- `GOOGLE_SHEET_ID`
- `[gcp_service_account]` com as credenciais completas da Service Account

> O fluxo principal usa `st.secrets`. O `.env` ficou apenas como apoio opcional a diagnósticos legados.

### 3. Rodar testes

```bash
# Rodar todos os testes
uv run pytest -q

# Rodar teste específico
uv run pytest -q tests/test_google_sheets_adapter.py

# Rodar com cobertura
uv run pytest --cov=src tests/
```

### 4. Executar a aplicação Streamlit

```bash
# Usando o script (recomendado)
./run_app.sh

# Ou diretamente
uv run streamlit run app.py

# Ou com porta específica
uv run streamlit run app.py --server.port 8501
```

Para mais detalhes sobre configuração e operação, consulte a [home da documentação](./docs/index.md) e o [Quick Start Streamlit](./docs/QUICK_START_STREAMLIT.md).

---

## Contratos, design e boas práticas aplicadas

- a Gold layer é o contrato analítico principal consumido pela interface;
- adaptadores de infraestrutura normalizam erros e encapsulam acesso a Drive/Sheets;
- `drive_manager.py` centraliza descoberta e I/O dos ativos `.parquet`;
- a suíte em `tests/` cobre pipeline, páginas, rentabilidade e adaptadores Google.

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

## Páginas Executivas

- `📊 Dashboard`
- `💰 Custos de Produção`
- `💹 Faturamento (Auditoria)`

## Documentação Complementar

_Boa prática: sempre rode a suíte de testes (`uv run pytest`) antes de abrir um PR._

---

> Observação: a documentação do projeto foi organizada na pasta `docs/`. Consulte `docs/` para guias, sumários e o roadmap do projeto.
