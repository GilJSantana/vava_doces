# 🔍 Guia Completo: Cache + Data Profiling para Diagnóstico de Divergências

## Problema Tratado

Streamlit pode estar **cachendo dados antigos** ou **não detectando mudanças** no Gold layer, causando:
- Janeiro: Esperado 2742, exibido 0
- Fevereiro: Esperado 3348, exibido 3337

**Soluções implementadas**:

1. ✅ **Cache Control**: Botão "Limpar Cache" para invalidar @st.cache_data e @st.cache_resource
2. ✅ **Data Profiling**: Tabela que compara contagens por mês em cada camada (Bronze/Silver, Gold Fato, Dim Tempo)
3. ✅ **Diagnóstico Automático**: Widget que detecta divergências e exibe alertas

---

## 📊 Como Usar

### 1. **Abrir Streamlit com Diagnóstico Ativo**

```bash
cd /home/gilunix/Documents/Projects/Vava_doces
streamlit run app.py
```

### 2. **No Dashboard, Vá à Sidebar (esquerda)**

Você verá:
```
🔧 Diagnóstico
┌─────────────────────────┐
│ 🔄 Limpar Cache         │  ← Botão para forçar reload
│ ☐ 📊 Perfil de Dados    │  ← Checkbox para ver tabela
└─────────────────────────┘
```

### 3. **Marque o Checkbox "📊 Perfil de Dados"**

Aparecerá uma tabela:

| Mês      | Bronze (Silver) | Gold Fato | Dim Tempo | Δ (Bronze → Fato) | Status |
|----------|-----------------|-----------|-----------|-------------------|--------|
| 2026-01  | 2742            | 2742      | 31        | 0                 | ✅     |
| 2026-02  | 3348            | 3348      | 28        | 0                 | ✅     |

**Interpretação**:
- **Bronze (Silver)**: Registros na camada Silver (depois da normalização)
- **Gold Fato**: Registros em fato_vendas (após joins com dimensões)
- **Dim Tempo**: Cardinality de datas único em dim_tempo (ex: 31 dias para jan)
- **Δ**: Diferença (Bronze - Gold Fato) — **zero é bom!**
- **Status**: ✅ = OK, ⚠️ = Divergência detectada

---

## 🔧 Se Houver Divergência

### Cenário 1: Delta > 0 (Bronze tem mais registros que Gold)

**Causa**: Registros foram perdidos entre Silver → Gold

**Ação**:
1. Clique em "🔄 Limpar Cache" para invalidar cache
2. Verifique logs do pipeline:
   ```bash
   python scripts/medallion_pipeline.py 2>&1 | grep "\[diag\]"
   ```
   Procure por:
   - `[diag] build_fato_vendas:orphan_fks DETECTED`
   - `[diag] build_fato_vendas:orphan_retention`
   - Quantos `produto_id_null`, `data_id_null`

3. Se houver órfãos, significa parsing falhou. Rode diagnóstico Bronze:
   ```bash
   python scripts/bronze_ingestion_diagnostic.py \
     --csv-dir data/raw \
     --output-csv diagnostic.csv
   cat diagnostic.csv
   ```

### Cenário 2: Dim Tempo < Bronze (poucas datas em dim_tempo)

**Causa**: Parsing de datas falhou — dim_tempo não tem todas as datas

**Ação**:
1. Verifique logs de parsing:
   ```bash
   python scripts/medallion_pipeline.py 2>&1 | grep -i "date"
   ```
2. Rode diagnóstico Bronze com foco em "recommended_format":
   ```bash
   python scripts/bronze_ingestion_diagnostic.py --csv-dir data/raw
   ```
   Se "valid_ddmmyyyy" << "rows", há problema de formato.

### Cenário 3: Tudo OK no Profiler, mas Streamlit exibe < Bronze

**Causa**: Cache do Streamlit não foi invalidado

**Ação**:
1. Clique em "🔄 Limpar Cache" ← **Isso força recarregamento**
2. Atualizar a página (F5) para resetar Streamlit
3. Navegar de volta para o Dashboard

---

## 📈 Fluxo de Diagnóstico Recomendado

```
1. Abrir Streamlit
   ↓
2. Marcar "📊 Perfil de Dados" na sidebar
   ↓
3. Examinar Δ (Delta):
   ├─ Se Δ = 0 → Contagens OK, continue
   │
   ├─ Se Δ > 0 → Registros perdidos em Silver → Gold
   │  └─ Clicar "🔄 Limpar Cache"
   │  └─ Rodar: python scripts/medallion_pipeline.py 2>&1 | grep "[diag]"
   │  └─ Diagnosticar orphan_fks
   │
   └─ Se Dim Tempo << Bronze → Parsing de datas falhou
      └─ Rodar: python scripts/bronze_ingestion_diagnostic.py
      └─ Verificar recommended_format por arquivo
```

---

## 💾 Cache & Performance

### Por que cache?
- Streamlit re-executa o script inteiro a cada interação
- `@st.cache_data` armazena resultado de funções caras (I/O, parsing)
- Sem cache: Dashboard leva ~5-10s para carregar

### Quando o cache se torna problema?
- Gold layer foi regenerado (novo pipeline run)
- Dados no disco mudaram, mas cache não sabe
- Diferentes análises precisam de dados diferentes

### Como forçar invalidação?
**Opção A** (Novo): Clique em "🔄 Limpar Cache" no Dashboard
- Limpa `@st.cache_data` + `@st.cache_resource`
- Força recarregamento de todos os dados
- Streamlit faz `st.rerun()` automaticamente

**Opção B** (CLI, se Streamlit não responder):
```bash
# Deletar arquivos de cache do Streamlit
rm -rf ~/.streamlit/cache
streamlit run app.py
```

**Opção C** (Hard reset, última resort):
```bash
# Kill todos os processos Streamlit
pkill -f streamlit
# Limpar cache
rm -rf ~/.streamlit/cache
# Rodar pipeline novamente
python scripts/medallion_pipeline.py
# Iniciar Streamlit fresco
streamlit run app.py
```

---

## 🎯 Critério de Aceite (Problema Resolvido)

✅ Dashboard carrega sem erro
✅ Sidebar exibe "🔄 Limpar Cache" e "📊 Perfil de Dados"
✅ Perfil de Dados mostra tabela com contagens por mês
✅ Para todos os meses: Δ = 0 (Bronze = Gold Fato)
✅ Janeiro exibe ~2700 registros no Streamlit (era 0)
✅ Fevereiro exibe ~3348 registros no Streamlit (era 3337)
✅ Faturamento calcula valores realistas (não zero)

---

## 📝 Logs & Troubleshooting

### Verificar se Gold foi regenerado corretamente:
```bash
ls -lh data/processed/gold/
# Deve mostrar arquivos recentes (timestamp hoje)
# fato_vendas.parquet, dim_produto.parquet, dim_tempo.parquet, etc
```

### Verificar contagens em cada arquivo Gold:
```bash
python -c "
import pandas as pd
fato = pd.read_parquet('data/processed/gold/fato_vendas.parquet')
dim_t = pd.read_parquet('data/processed/gold/dim_tempo.parquet')
print(f'Fato: {len(fato)} rows')
print(f'Dim Tempo: {len(dim_t)} rows (datas únicas)')
"
```

### Ver logs do Pipeline:
```bash
python scripts/medallion_pipeline.py 2>&1 | tee pipeline.log
# Procurar por "[diag]" para diagnósticos
grep "\[diag\]" pipeline.log
```

### Se Streamlit não exibir novos dados após cache clear:
```bash
# Verificar se load_sales_data_cached() está retornando corretamente
python -c "
import sys
sys.path.insert(0, '.')
from src.presentation.pages.sales_shared import load_sales_data_cached
df = load_sales_data_cached()
print(f'Rows: {len(df) if df is not None else 0}')
print(f'Months: {df[\"mes_referencia\"].unique() if df is not None else []}')
"
```

---

## 🚀 Próximos Passos (Opcional)

1. **Monitorar regularmente**:
   ```bash
   # Adicionar ao cron (ex: 22:00 todo dia)
   0 22 * * * cd /path/to/Vava_doces && \
     python scripts/medallion_pipeline.py >> logs/pipeline.log 2>&1 && \
     python scripts/bronze_ingestion_diagnostic.py \
       --output-csv logs/diagnostic_$(date +%Y-%m-%d).csv
   ```

2. **Alertas automáticos** (se Δ > limiar):
   - Integrar com Slack/Email
   - Enviar mensagem se Δ > 5% do total

3. **Versionar diagnósticos**:
   - Salvar histórico de `diagnostic.csv` por data
   - Comparar tendências de divergência

---

## 📞 Quick Reference

| Problema | Solução | Tempo |
|----------|---------|-------|
| Streamlit exibe dados antigos | "🔄 Limpar Cache" | 3s |
| Divergência em Perfil de Dados | `grep "[diag]" pipeline.log` | 30s |
| Parser de datas suspeito | `bronze_ingestion_diagnostic.py` | 10s |
| Tudo OK mas erro persiste | Hard reset: `rm -rf ~/.streamlit/cache` | 60s |

