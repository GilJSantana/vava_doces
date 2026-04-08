# 🔍 Guia Rápido: Corrigir Perda de Registros Jan/Fev

## Problema Identificado

| Arquivo | Registros Esperados | Registros Streamlit | Perda |
|---------|-------------------|-------------------|-------|
| Janeiro | 2742 | 0 | 100% |
| Fevereiro | 3348 | 3337 | 11 (0.3%) |

**Causa raiz**: Registros com data_id/produto_id NULL eram descartados silenciosamente durante transformação Silver → Gold.

---

## ✅ O que foi Corrigido

### 1. **medallion_pipeline.py** (linhas 912–960)
**Antes**: Linhas com `NULL produto_id` ou `NULL data_id` eram REMOVIDAS via `_validate_no_nulls()`
**Depois**: Linhas são PRESERVADAS e SINALIZADAS com flags `_orphan_produto` e `_orphan_data`

**Benefício**: +100% de registros retornam ao pipeline

### 2. **sales_silver_normalizer.py** (_deduplicate_rows)
**Antes**: Chave dedup incluía "produto", colapsando itens da mesma nota
**Depois**: Chave usa apenas `num_venda + data + arquivo_origem`

**Benefício**: Preserva múltiplos itens da mesma venda (NFC-e itemizada)

### 3. **bronze_ingestion_diagnostic.py** (novo)
Script para auditar CSV → Bronze sem mexer no pipeline

---

## 🚀 Como Validar

### 1. **Rodar pipeline com logs detalhados**
```bash
cd /home/gilunix/Documents/Projects/Vava_doces
python scripts/medallion_pipeline.py 2>&1 | tee pipeline_run.log
```

Procure por:
```
[diag] build_fato_vendas:orphan_fks DETECTED
[diag] build_fato_vendas:orphan_retention
[silver:dedup] Removed N duplicates
```

### 2. **Verificar counts no Streamlit**
Após executar o pipeline, recarregue o Streamlit:
```bash
streamlit run app.py
```

Compare:
- **Janeiro**: Deve voltar de 0 para ~2700 registros
- **Fevereiro**: Deve subir de 3337 para ~3348 registros

### 3. **Executar diagnóstico Bronze** (se counts não combinarem)
```bash
python scripts/bronze_ingestion_diagnostic.py \
  --csv-dir data/raw \
  --bronze-path data/processed/silver/sales_silver.parquet \
  --output-csv diagnostic_report.csv

cat diagnostic_report.csv
```

Procure por:
- `rows_lost_vs_physical` > 0 → há parsing fail
- `recommended_format` → qual formato de data foi detectado
- `warnings` → encoding ou delimitador suspeito

---

## 📋 Checklist de Validação

- [ ] Pipeline executa sem erro (exit code 0)
- [ ] Logs mostram `[diag] build_fato_vendas:orphan_retention` com counts
- [ ] Streamlit exibe ~2700 registros em Janeiro (era 0)
- [ ] Streamlit exibe ~3348 registros em Fevereiro (era 3337)
- [ ] Coluna "Total Filtrado" em Faturamento mostra valores realistas
- [ ] Dashboard carrega sem timeout

---

## 🔧 Se Ainda Houver Perda

1. **Abrir pipeline_run.log** e procurar por:
   ```
   [diag] build_fato_vendas:orphan_fks DETECTED
   [diag] build_fato_vendas:orphan_produtos_by_source_month
   ```

   Isso dirá QUAL arquivo/mês tem problema.

2. **Rodar bronze_ingestion_diagnostic.py** com foco no arquivo problemático:
   ```bash
   python scripts/bronze_ingestion_diagnostic.py \
     --csv-dir data/raw \
     --output-csv diagnostic_report.csv
   ```

   Se `rows_lost_vs_physical` > 0, significa parsing falhou no read_csv.

3. **Verificar encoding/delimitador** (se output diagnosticsshow warnings):
   ```bash
   file data/raw/sales_data_01_2026.csv  # Ver encoding
   head -1 data/raw/sales_data_01_2026.csv | od -c  # Ver delimitador
   ```

---

## 📚 Arquivos Alterados

| Arquivo | Mudança | Linhas |
|---------|---------|--------|
| `scripts/medallion_pipeline.py` | Preserve orphans com flags | +50 |
| `src/domain/sales_silver_normalizer.py` | Fix dedup key (remove "produto") | +30 |
| `scripts/bronze_ingestion_diagnostic.py` | Novo script de diagnóstico | +500 |
| `docs/FIX_PERDA_REGISTROS_RESUMO.md` | Documentação técnica | - |
| `tests/test_fato_orphan_preservation.py` | Testes de integridade | +100 |

---

## 💡 Próximos Passos (Opcional)

Após validar que registros retornaram:

1. **Criar alertas para órfãos**:
   ```sql
   SELECT COUNT(*) FROM fato_vendas
   WHERE _orphan_produto=True OR _orphan_data=True
   ```
   Se > 5% do total, investigar encoding/parsing.

2. **Automatizar diagnóstico**:
   ```bash
   # Rodar diagnóstico após cada ingestão
   python scripts/medallion_pipeline.py && \
   python scripts/bronze_ingestion_diagnostic.py --output-csv latest_diagnostic.csv
   ```

3. **Desabilitar flags** quando confiança > 99%:
   - Remover colunas `_orphan_produto` e `_orphan_data` de fato_vendas
   - Alterar lógica de drop_duplicates se não houver mais colisões

---

## 📞 Dúvidas?

Consulte:
- `docs/DIAGNOSTICO_PERDA_REGISTROS.md` — análise técnica detalhada
- `docs/FIX_PERDA_REGISTROS_RESUMO.md` — resumo das mudanças
- Logs do pipeline com `2>&1 | grep "\[diag\]"` para diagnóstico real-time

