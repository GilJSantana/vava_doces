<div align="center">
  <img src="assets/logo.png" alt="Vava Doces Logo" width="200" height="200" style="border-radius: 20px;">
</div>

# Vava Doces - Análise de Custos, Margens e Rentabilidade

## Sobre o Projeto

Este repositório apresenta um pipeline de dados aplicado a um pequeno negócio real: a loja Vava Doces. O projeto integra planilhas operacionais (produtos, receitas, materia-prima e vendas), processa os dados com regras de negocio e disponibiliza analises em um cockpit Streamlit.

O objetivo e transformar dados dispersos em informacao acionavel para gestao: custo por produto, margem, rentabilidade e impacto no faturamento.

---

## Problema de Negocio e Contexto

A Vava Doces enfrentava um cenario comum em pequenos negocios:

- Nao havia cadastro estruturado e confiavel de produtos.
- A compra de materia-prima era operacional, sem visao consolidada de custo por item vendido.
- O sistema contabil registrava vendas com inconsistencias de padronizacao.
- Embora o dono percebesse o negocio "sem dividas", o caixa chegava pressionado no fim do ano, reduzindo capacidade de investimento.

Esse contexto gera uma dor central: vender nao significa necessariamente lucrar. Sem modelo de custo e margem por produto, decisoes de preco e mix de vendas ficam no escuro.

---

## Principais Perguntas que o Projeto Responde

1. Quais produtos realmente geram lucro e quais apenas aumentam volume?
2. Quanto custa produzir (ou adquirir) cada produto, considerando sua composicao?
3. Qual e a margem de contribuicao por produto e por categoria?
4. Quais produtos tem maior impacto no faturamento total?
5. Onde existem distorcoes entre preco praticado e custo real?
6. Quais ajustes de preco podem melhorar caixa sem comprometer competitividade?
7. Como priorizar compras de materia-prima e producao com base em rentabilidade?

---

## Como Funciona (Arquitetura)

A arquitetura segue separacao clara entre regra de negocio e infraestrutura:

- `Ports` (`src/ports/data_source.py`): define o contrato `DataSource` para leitura de dados.
- `Adapters` (`src/infrastructure/google_sheets_adapter.py`): implementa acesso a Google Sheets via `gspread`.
- `Domain Services`:
  - `src/domain/cost_analysis_service.py`: calcula custo por produto e validacoes de schema.
  - `src/domain/product_analysis_service.py`: consolida metricas de produtos, margem e impacto de faturamento.
- `App` (`app.py`): interface Streamlit para visualizacao e apoio a decisao.

Esse desenho facilita testes, manutencao e troca de fonte de dados sem quebrar regras de negocio.

---

## Resultados Esperados para o Dono do Negocio

- Visibilidade clara de custo, margem e rentabilidade por produto.
- Base objetiva para ajustar precificacao e mix de vendas.
- Reducao de decisoes por intuicao e maior confianca na gestao do caixa.
- Identificacao de produtos que drenam margem ou imobilizam capital.
- Prioridade de investimento em produtos mais rentaveis.

---

## Estrutura Relevante do Projeto

- `app.py` - aplicacao Streamlit (cockpit de analise).
- `src/ports/data_source.py` - contrato de acesso a dados (`DataSource`) e erro de integracao.
- `src/infrastructure/google_sheets_adapter.py` - adaptador de leitura da planilha Google Sheets.
- `src/domain/cost_analysis_service.py` - regras de custo por produto.
- `src/domain/product_analysis_service.py` - regras para analise de produtos, margem e faturamento.
- `tests/` - suite com testes de dominio, infraestrutura e aplicacao:
  - `tests/test_cost_analysis_service.py`
  - `tests/test_google_sheets_adapter.py`
  - `tests/test_streamlit_app.py`
  - `tests/test_integration.py`
- `scripts/run_app.sh` - script auxiliar para iniciar o Streamlit.

---

## Como Rodar Localmente (com `uv`)

Os comandos abaixo assumem uso de `uv` no Linux (bash).

### 1) Instalar dependencias

```bash
uv sync
```

Se preferir executar sem sincronizar lock completo:

```bash
uv pip install -e .
```

### 2) Configurar credenciais do Google Sheets

Crie um arquivo `.env` na raiz com:

```bash
GOOGLE_APPLICATION_CREDENTIALS="/caminho/absoluto/para/service-account.json"
GOOGLE_SHEET_ID="SEU_SHEET_ID"
```

### 3) Rodar testes

```bash
uv run pytest -q
```

### 4) Executar o Streamlit

```bash
uv run streamlit run app.py
```

Ou via script auxiliar:

```bash
bash scripts/run_app.sh
```

Aplicacao disponivel em `http://localhost:8501`.

---

## Boas Praticas Aplicadas

- Arquitetura em camadas com `ports/adapters` (baixo acoplamento).
- Inversao de dependencia: dominio depende de contratos, nao de bibliotecas externas.
- Principios SOLID (com foco em SRP, DIP e OCP).
- TDD e testes unitarios para regras de negocio criticas.
- Tratamento de erros de integracao com excecoes especificas.
- Organizacao voltada para evolucao incremental e onboarding tecnico.

---

## Proximos Passos e Melhorias

- Evoluir validacao de schema das abas com relatorio de inconsistencias.
- Adicionar monitoramento de qualidade dos dados (campos obrigatorios, duplicidades, nulos).
- Criar indicadores de tendencia (margem ao longo do tempo, sazonalidade e ruptura).
- Publicar documentacao tecnica no MkDocs + GitHub Pages.
- Configurar CI/CD com execucao de testes e checks de qualidade a cada PR.

---

## Contato

Projeto desenvolvido por **Gsantana**.

- Email: `gilmar.jesus@gmail.com`
- Sugestoes e melhorias: abra uma issue ou pull request neste repositorio.

---

> Este projeto representa uma transicao pratica para a area de dados: conecta modelagem de negocio, engenharia de software e analise para gerar impacto real em pequenas empresas.
