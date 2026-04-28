# 🚀 Quick Start: Página Faturamento

## Um minuto: Executar a aplicação

```bash
cd /home/gilunix/Documents/Projects/Vava_doces
uv sync
uv run streamlit run app.py
```

Abra `http://localhost:8501` e clique em **"💹 Faturamento (Auditoria)"** no sidebar.

---

## O que a página faz hoje

A página de faturamento deixou de depender do fluxo antigo baseado em DataFrame unificado de ETL bruto.

Ela agora:
- lê a Gold layer validada;
- aplica filtros por data, cliente e mês de referência;
- exibe KPIs e tabelas de auditoria sobre as vendas processadas.

---

## Fluxo Atual de Dados

```text
Google Drive / Sheets operacionais
            ↓
   Medallion pipeline (quando necessário)
            ↓
       fato_vendas.parquet
            ↓
 load_sales_data_cached()
            ↓
 show_faturamento()
```

### Componentes principais
- `src/presentation/pages/faturamento.py`
- `src/presentation/pages/sales_shared.py`
- `src/infrastructure/drive_manager.py`
- `scripts/medallion_pipeline.py`

---

## Como a página carrega dados

1. `load_sales_data_cached()` recupera a base de vendas validada da Gold layer.
2. `_normalize_data()` padroniza datas, clientes e mês de referência.
3. `_apply_filters()` aplica filtros por:
   - data inicial/final;
   - clientes;
   - mês de referência.
4. a UI mostra métricas, tabela paginada e exportações.

---

## Fonte de verdade da página

A fonte principal da página é a Gold layer persistida em Google Drive, especialmente o ativo de vendas validado.

Isso significa que:
- a página trabalha sobre dados já tipados e auditados;
- o Google Drive é o armazenamento persistente principal;
- o disco local não é a fonte analítica principal do app.

---

## Arquivos relevantes

### UI
- `src/presentation/pages/faturamento.py`
- `src/presentation/navigation.py`

### Dados
- `src/presentation/pages/sales_shared.py`
- `src/infrastructure/drive_manager.py`
- `scripts/medallion_pipeline.py`

### Testes
- `tests/test_faturamento_page.py`
- `tests/test_integration.py`
- `tests/test_profitability_pipeline.py`

---

## Troubleshooting

### "Nenhum dado de vendas encontrado"
- verifique se os secrets foram configurados corretamente em `.streamlit/secrets.toml`;
- confira se a Service Account consegue ler os ativos Gold no Drive;
- confirme que o pipeline conseguiu materializar `fato_vendas.parquet`.

### Filtros por data retornam vazio
- verifique se existem linhas com `data` invalida na base carregada;
- revise o período selecionado e o campo `mes_referencia`.

### A pagina nao abre apos login
- confirme se o usuario possui permissao no `GOOGLE_DRIVE_FOLDER_ID`;
- confira os logs de autorizacao OAuth2/Drive no terminal.

---

## Comandos uteis

```bash
# Executar o app
uv run streamlit run app.py

# Rodar a suíte oficial
uv run pytest -q

# Rodar testes da página de faturamento
uv run pytest -q tests/test_faturamento_page.py

# Limpar cache local do Streamlit
rm -rf ~/.streamlit/cache
```

---

## Observacao importante

Este guia foi atualizado para a arquitetura atual:
- **3 paginas executivas**
- **`st.secrets` como configuracao canonica**
- **Google Drive como persistencia principal da Gold layer**
- **consumo diskless/in-memory dos arquivos parquet**

---

**Status**: ✅ Alinhado ao fluxo atual

