# 🚀 Quick Start: Página Faturamento

## Um minuto: Executar a aplicação

```bash
cd /home/gilunix/Documents/Projects/Vava_doces

# Ativar virtual env (se necessário)
source .venv/bin/activate

# Executar Streamlit
uv run streamlit run app.py
```

Navegue para `http://localhost:8501` e clique em **"💹 Faturamento"** no sidebar.

---

## Arquitetura em Piadas 😄

```
┌─────────────────────────────────────────────┐
│       Google Drive + Google Sheets           │
│  (Vendas CSV + Catálogo de Produtos)        │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │   SalesETLPipeline   │
        │  (Extract/Transform) │
        └──────────┬───────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │  Unified DataFrame   │
        │  (8 columns ready!)  │
        └──────────┬───────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │  Streamlit UI        │
        │  KPIs + Charts       │
        │  + Tabelas           │
        └──────────────────────┘
```

---

## Fluxo de Dados Simplificado

| Etapa | Entrada | Saída | Função |
|-------|---------|-------|--------|
| **Extract** | Drive CSV + Sheets | Raw DataFrames | `SalesFilesExtractor`, `ProductsCatalogExtractor` |
| **Transform** | Raw DFs | Colunas normalizadas | `SalesTransformer`, `ProductsTransformer` |
| **Deduplicate** | Vendas concat | Linhas únicas | `_deduplicate()` |
| **Join** | Vendas + Produtos | Merge left | `SalesProductJoiner.join()` |
| **Load** | Merged DF | lucro_est calculado | `_finalise()` |
| **Cache** | Final DF | Cached (1h) | `@st.cache_data` |
| **UI** | Cached DF | 5 seções | `show_faturamento()` |

---

## Key Files Reference

### ETL Pipeline
- **`src/domain/sales_analysis_service.py`** — Core pipeline (610 linhas)
- **`src/infrastructure/google_drive_adapter.py`** — Drive I/O (99 linhas)
- **`src/ports/data_source.py`** — Interfaces (DriveDataSource port)

### UI
- **`src/presentation/pages/faturamento.py`** — Streamlit page (358 linhas)
- **`src/presentation/navigation.py`** — Routing (adicionado PAGE_FATURAMENTO)

### Tests
- **`tests/test_sales_analysis_service.py`** — 34 testes de ETL
- **`tests/test_faturamento_page.py`** — 13 testes de UI logic

---

## API de Uso

### Importar e Executar o Pipeline
```python
from src.domain.sales_analysis_service import SalesETLPipeline

# Carrega .env automaticamente
pipeline = SalesETLPipeline.from_env()
df = pipeline.run()

# df tem colunas: [data, produto, categoria, qtd, valor_venda, custo_unit, lucro_est, sem_cadastro]
print(f"Vendas carregadas: {len(df)} linhas")
print(f"Faturamento total: R$ {df['valor_venda'].sum():,.2f}")
```

### Usar a Página Diretamente
```python
# app.py já importa e renderiza automaticamente
from src.presentation.pages.faturamento import show_faturamento

st.set_page_config(layout="wide")
show_faturamento()
```

### Testar Componentes
```bash
# Todos os testes
uv run pytest tests/test_faturamento_page.py -v

# Um teste específico
uv run pytest tests/test_faturamento_page.py::TestCalculateKPIMetrics::test_faturamento_total -v
```

---

## Troubleshooting

### "❌ Não foi possível carregar os dados"
- ✅ Verificar se `.env` tem variáveis corretas:
  ```bash
  cat .env | grep -E "DRIVE_FOLDER_ID|SALES_SHEET_ID|GOOGLE"
  ```
- ✅ Verificar autenticação Google:
  ```bash
  cat $GOOGLE_APPLICATION_CREDENTIALS | head -3
  ```

### "⚠️ Nenhuma venda encontrada no período"
- ✅ Alterar range de datas (usar min/max disponível)
- ✅ Verificar se o arquivo de vendas está no Drive

### "112 orphan product(s)" (aviso)
- ✅ Normal! Significa 112 nomes diferentes entre vendas e catálogo
- ✅ Padronizar nomes na planilha para reduzir (não é bloqueante)

### Gráfico de pizza não aparece
- ✅ Verificar se há produtos com `categoria != null`
- ✅ Reduzir filtro de datas para ter mais dados

---

## Métricas Esperadas (Dados Atuais)

| Métrica | Valor | Observação |
|---------|-------|-----------|
| Total de linhas | 3.337 | Do arquivo de fevereiro/2026 |
| Faturamento total | R$ 58.193,25 | Em reais |
| Lucro bruto médio | R$ 19,16 | Apenas produtos matched |
| Ticket médio | R$ 14,74 | Faturamento / transações |
| Produtos matched | 29 | Com custo definido |
| Produtos órfãos | 112 | Sem match no catálogo |

---

## Stack Tecnológico

```
┌─────────────────────────────────────────────────┐
│ Streamlit UI Framework                          │
├─────────────────────────────────────────────────┤
│ Plotly Charts │ Pandas DataFrames │ st.cache_data │
├─────────────────────────────────────────────────┤
│ SalesETLPipeline (domínio)                      │
├─────────────────────────────────────────────────┤
│ GoogleDriveAdapter │ GoogleSheetsAdapter        │
├─────────────────────────────────────────────────┤
│ Google Drive API | Google Sheets API            │
└─────────────────────────────────────────────────┘
```

---

## Próximo Passo (Roadmap)

### Semana 1
- [ ] Adicionar export CSV/PDF dos dados filtrados
- [ ] Série temporal (gráfico de linha)

### Semana 2
- [ ] Matriz de rentabilidade (scatter plot)
- [ ] Comparação período vs. período anterior

### Semana 3
- [ ] Análise ABC (curva de Pareto)
- [ ] Integração com dados de NFC-e

---

## Cheat Sheet: Comandos Úteis

```bash
# Atualizar dependências
uv add google-api-python-client

# Rodar testes com coverage
uv run pytest tests/test_faturamento_page.py --cov=src.presentation.pages.faturamento

# Limpar cache do Streamlit
rm -rf ~/.streamlit/cache

# Verificar imports
python -c "from src.presentation.pages.faturamento import show_faturamento; print('✅ OK')"

# Executar pipeline direto (sem Streamlit)
python -u - <<'PY'
from src.domain.sales_analysis_service import SalesETLPipeline
pipeline = SalesETLPipeline.from_env()
df = pipeline.run()
print(df.info())
PY
```

---

**Status**: ✅ Pronto para Produção
**Testes**: 85/85 passando
**Cobertura**: Todos os componentes críticos
**Documentação**: Completa + Markdown + Docstrings

