## Página Faturamento — Módulo de Análise de Vendas

### Visão Geral

A página `💹 Faturamento` é um módulo Streamlit que apresenta análises consolidadas de vendas, custos e rentabilidade. Integra-se com o pipeline `SalesETLPipeline` para extrair e transformar dados de múltiplos arquivos de vendas mensais do Google Drive e catálogo de produtos do Google Sheets.

### Fluxo de Dados

```
Google Drive (pasta Vava_Doces_Data)
  ├─ sales_data_02_2026.csv
  ├─ ... outros XLSX/CSV mensais
  └─ Controle-de-Vendas-Doceria (Google Sheet)
      └─ aba "Produtos" (catálogo)

          ↓ SalesETLPipeline

[Extract] Lê arquivos + catálogo
  ↓
[Transform] Normaliza headers, datas, valores moeda
  ↓
[Deduplicate] Remove linhas duplicadas cross-files
  ↓
[Join] Left join sales × produtos (por nome normalizado)
  ↓
[Load] Calcula lucro_est = valor_venda − custo_unit
  ↓
DataFrame unificado: [data, produto, categoria, qtd, valor_venda, custo_unit, lucro_est, sem_cadastro]

          ↓ Faturamento Page

[KPI Cards] Exibe 4 métricas principais
[Date Filter] Filtra por período
[Products Chart] Top 10 por faturamento
[Products Table] Detalhe com formatação monetária
[Category Pie] Distribuição por categoria
```

### Componentes Principais

#### 1. **KPI Cards** (Topo)
- 💰 **Faturamento Total**: Soma de `valor_venda` no período
- 📈 **Lucro Bruto Médio**: Média de `lucro_est` (somente produtos com custo definido)
- 📦 **Total de Itens**: Soma de `qtd` vendidas
- 🎫 **Ticket Médio**: `faturamento_total / num_vendas_unicas`

#### 2. **Filtro Temporal**
- `st.date_input` com range selecionável
- Limita os gráficos/tabelas ao período escolhido
- Valores padrão: min/max da dataset

#### 3. **Análise de Produtos**
- **Gráfico Horizontal** (Plotly): Top 10 produtos por faturamento
  - Design: barras arredondadas, fundo limpo, hover interativo
- **Tabela Detalhada**
  - Coluna "Produto" (string)
  - Coluna "Quantidade" (inteiro)
  - Colunas monetárias com `st.column_config.NumberColumn(format="R$ %.2f")`
  - Ordenação descendente por faturamento

#### 4. **Análise de Categoria**
- **Gráfico de Pizza** (Plotly)
  - Distribuição de faturamento por categoria
  - Exclui linhas com `categoria=null`
  - Hover com valores em R$

#### 5. **Avisos de Qualidade**
- `st.warning()` se `sem_cadastro > 0`
  - Indica quantas vendas não têm custo calculado
  - Sugere padronização de nomes na planilha

### Cache e Performance

```python
@st.cache_data(ttl=3600)
def load_sales_data() -> Optional[pd.DataFrame]:
    """TTL = 3600 segundos (1 hora)"""
```

**Benefícios**:
- Evita chamadas repetidas ao Google Drive a cada interação de filtro
- Melhora responsividade da UI
- Cache é limpo manualmente via botão "🔄 Atualizar dados" na sidebar

### Tratamento de Erros

| Erro | Resposta |
|------|----------|
| Env vars faltantes (`GOOGLE_APPLICATION_CREDENTIALS`, etc.) | `st.error()` com mensagem clara |
| Pipeline retorna DataFrame vazio | `st.warning()` sem dados para o período |
| Categoria nula no gráfico de pizza | Linhas excluídas (não quebra o gráfico) |
| Coluna `sem_cadastro` ausente | Usa padrão seguro (0 orphans) |

### Estrutura do Código

```
src/presentation/pages/faturamento.py
├── Load layer
│   └── load_sales_data() [cached]
├── Transform helpers
│   ├── _to_numeric_safe()
│   ├── _filter_by_date_range()
│   └── calculate_kpi_metrics()
├── Chart builders
│   ├── build_top_products_chart()
│   └── build_category_pie_chart()
├── UI components
│   ├── render_kpi_cards()
│   ├── render_date_filter()
│   ├── render_products_analysis()
│   └── render_category_analysis()
└── Main entry point
    └── show_faturamento()
```

### Testes

**Arquivo**: `tests/test_faturamento_page.py`

**Cobertura**:
- `_to_numeric_safe()`: coerção de tipos
- `_filter_by_date_range()`: filtro temporal
- `calculate_kpi_metrics()`: cálculo de KPIs
  - Inclui casos edge: orphans, missing columns, empty DataFrames

**Execução**:
```bash
uv run pytest tests/test_faturamento_page.py -v
```

### Integração com App Multipage

**Arquivo**: `src/presentation/navigation.py`
```python
PAGE_FATURAMENTO = "💹 Faturamento"
PAGE_OPTIONS = [..., PAGE_FATURAMENTO, ...]
```

**Arquivo**: `app.py`
```python
PAGE_HANDLERS = {
    ...,
    PAGE_FATURAMENTO: lambda _service, _product_service: show_faturamento(),
    ...,
}
```

### Próximas Melhorias

1. **Export**: Adicionar botão de download (CSV/PDF) dos dados filtrados
2. **Série Temporal**: Gráfico de linha mostrando faturamento acumulado por data
3. **Análise de Margem**: Scatter plot Volume × Margem (matriz de rentabilidade)
4. **Alertas Automáticos**: Notificar produtos com margem negativa
5. **Comparação Período**: Comparar YoY ou período vs. período anterior

### Dependências

```toml
pandas
plotly>=5.19
streamlit
google-api-python-client
gspread
```

### Exemplo de Uso

```python
from src.presentation.pages.faturamento import show_faturamento
import streamlit as st

st.set_page_config(layout="wide")
show_faturamento()
```

---

**Autor**: GitHub Copilot
**Versão**: 1.0
**Data**: 2026-03-21

