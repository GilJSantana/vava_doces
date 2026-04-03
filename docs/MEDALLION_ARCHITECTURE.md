# Medallion Architecture — Vava Doces

**Data Pipeline Stages: RAW → SILVER → GOLD + Data Quality Validation**

---

## 📊 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     MEDALLION ARCHITECTURE PIPELINE                         │
└─────────────────────────────────────────────────────────────────────────────┘

                              data/raw/
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                 *.csv                     *.xlsx
                    │                         │
                    └────────────┬────────────┘
                                 ↓
                    ┌──────────────────────┐
                    │   RAW LAYER          │
                    │ (LocalRawSource)     │
                    │                      │
                    │ • List tabular files │
                    │ • Read CSV / XLSX    │
                    │ • Tag with metadata  │
                    └──────────┬───────────┘
                               ↓
              ┌────────────────────────────────────┐
              │     NORMALIZATION & CLEANING       │
              │                                    │
              │ • Normalize headers (snake_case)   │
              │ • Map canonical column names       │
              │ • Coerce types (dates, numerics)   │
              │ • Clean strings (whitespace)       │
              │ • Add lineage metadata             │
              └────────────┬───────────────────────┘
                           ↓
              ┌────────────────────────────────────┐
              │   CROSS-FILE DEDUPLICATION         │
              │                                    │
              │ • Use num_venda + produto_key      │
              │ • Tag duplicates with source file  │
              │ • Keep first occurrence            │
              └────────────┬───────────────────────┘
                           ↓
              ╔════════════════════════════════════╗
              ║   SILVER LAYER (Atomic)            ║
              ║ sales_silver.parquet               ║
              ║                                    ║
              ║ • Cleaned, normalized raw data     ║
              ║ • Single denormalized table        ║
              ║ • Ready for dimensional modeling   ║
              ║ • Cost placeholder: custo = 0.0    ║
              ╚════════╤═══════════════════════════╝
                       │
        ┌──────────────┴──────────────┐
        │                             │
        │ (Optional) Cost Enrichment  │
        │ from Google Sheets          │
        │                             │
        └──────────────┬──────────────┘
                       ↓
        ┌──────────────────────────────┐
        │   DIMENSIONAL MODELING        │
        │                              │
        │ • Extract dim_produto        │
        │   (1-based surrogate keys)    │
        │                              │
        │ • Extract dim_tempo          │
        │   (temporal attributes)      │
        │                              │
        │ • Join fact table            │
        │   (compute margem)           │
        └──────────┬───────────────────┘
                   ↓
        ┌──────────────────────────────┐
        │   REFERENTIAL INTEGRITY      │
        │   VALIDATION                 │
        │                              │
        │ • FK: produto_id → dim_prod  │
        │ • FK: data_id → dim_tempo    │
        │ • PK: venda_id uniqueness    │
        │ • Margem: no inf/NaN values  │
        └──────────┬───────────────────┘
                   ↓
        ╔══════════════════════════════╗
        ║   GOLD LAYER (Star Schema)   ║
        ║                              ║
        ║ dim_produto.parquet          ║
        ║  ├─ produto_id (int64 PK)    ║
        ║  └─ nome_produto (str)       ║
        ║                              ║
        ║ dim_tempo.parquet            ║
        ║  ├─ data_id (int64 PK)       ║
        ║  ├─ data (datetime64)        ║
        ║  ├─ dia, mes, ano (int)      ║
        ║  ├─ trimestre (int)          ║
        ║  ├─ dia_semana (int)         ║
        ║  └─ nome_mes (str, PT)       ║
        ║                              ║
        ║ fato_vendas.parquet          ║
        ║  ├─ venda_id (int64 PK)      ║
        ║  ├─ produto_id (int64 FK)    ║
        ║  ├─ data_id (int64 FK)       ║
        ║  ├─ num_venda (int64)        ║
        ║  ├─ cliente (str)            ║
        ║  ├─ quantidade (float64)     ║
        ║  ├─ valor_unitario (float64) ║
        ║  ├─ valor_total (float64)    ║
        ║  ├─ custo (float64)          ║
        ║  └─ margem (float64)         ║
        ║                              ║
        ║ Business Logic:              ║
        ║  margem = (valor_total -     ║
        ║           custo) / quantidade║
        ╚════════╤═══════════════════╝
                 │
                 ↓
    ╔═════════════════════════════════╗
    ║  DATA QUALITY VALIDATION        ║
    ║  (src/infrastructure/          ║
    ║   data_quality.py)             ║
    ║                                 ║
    ║  Checks per table:              ║
    ║  • Required columns present     ║
    ║  • Data types correct           ║
    ║  • Primary key uniqueness       ║
    ║  • Foreign key integrity        ║
    ║  • Business logic constraints   ║
    ║                                 ║
    ║  Results:                       ║
    ║  ├─ ✅ PASSED (production-ready)║
    ║  └─ ❌ FAILED (investigate)     ║
    ╚═════════════════════════════════╝
```

---

## 🔄 Pipeline Execution Flow

### 1. **RAW STAGE** (`run_raw_to_silver`)

- **Input:** CSV/XLSX files from `data/raw/`
- **Output:** `data/processed/silver/sales_silver.parquet`
- **Processing:**
  ```python
  load_raw()
    ├─ LocalRawSource.list_tabular_files()
    └─ LocalRawSource.read_as_dataframe()

  transform_to_silver()
    ├─ _normalise_columns()        # headers → snake_case
    ├─ _map_canonical()             # select & rename to standard names
    ├─ _coerce_types()              # dates, numerics, strings
    ├─ _deduplicate_with_audit()    # cross-file dedup
    └─ project to SILVER_COLUMNS    # fixed schema
  ```

### 2. **SILVER STAGE**

The **Atomic Layer** — single denormalized table ready for gold layer transformation.

- **Schema**: Fixed columns (32 total)
  - Core: `num_venda`, `cliente`, `produto`, `data`, `quantidade`, `valor_*`, etc.
  - Metadata: `custo` (0.0 placeholder), `source_file`, `ingested_at_utc`

- **Quality Characteristics:**
  - Normalized headers (snake_case)
  - Typed columns (no type mismatches)
  - Dates in datetime64 format
  - Numeric values (integers/floats)
  - Strings with no leading/trailing whitespace

### 3. **GOLD STAGE** (`run_silver_to_gold`)

- **Input:** `sales_silver.parquet`
- **Output:** Three Parquet files:
  - `dim_produto.parquet` — 1-based product dimension
  - `dim_tempo.parquet` — temporal dimension
  - `fato_vendas.parquet` — sales fact table with metrics

- **Processing:**
  ```python
  run_silver_to_gold()
    │
    ├─ [OPTIONAL] load_cost_catalog_from_sheets()
    │    └─ enrich_cost_from_catalog()    # populate custo column
    │
    ├─ build_dim_produto()
    │   ├─ Extract unique product names
    │   ├─ Assign 1-based integer IDs (surrogate key)
    │   └─ Validate: no nulls in produto_id
    │
    ├─ build_dim_tempo()
    │   ├─ Extract unique dates
    │   ├─ Decompose to day/month/year/quarter
    │   ├─ Assign 1-based integer IDs (surrogate key)
    │   └─ Add Portuguese month names
    │
    ├─ build_fato_vendas()
    │   ├─ Join with dim_produto (on produto name)
    │   ├─ Join with dim_tempo (on date)
    │   ├─ Compute margem = (valor_total - custo) / quantidade
    │   ├─ Assign 1-based venda_id (surrogate key)
    │   └─ Drop rows with null FKs
    │
    ├─ validate_star_schema()
    │   ├─ FK: produto_id ∈ dim_produto.produto_id
    │   ├─ FK: data_id ∈ dim_tempo.data_id
    │   ├─ PK: venda_id uniqueness
    │   └─ Margem: no ±inf values
    │
    └─ Persist all tables to disk (Parquet + Snappy compression)
  ```

### 4. **DATA QUALITY LAYER** (`run_data_quality_validation`)

Runs **after** gold layer is complete.

- **Input:** Three gold Parquet files
- **Validation Scope:**

  **Table: dim_produto**
  ```
  ✓ Required columns: [produto_id, nome_produto]
  ✓ Data types: produto_id=int64, nome_produto=object
  ✓ Primary key: produto_id unique across all rows
  ✓ No nulls in key columns
  ✓ Row count and uniqueness
  ```

  **Table: dim_tempo**
  ```
  ✓ Required columns: [data_id, data, dia, mes, ano, trimestre, nome_mes, dia_semana]
  ✓ Data types: correct (int64, datetime64, object)
  ✓ Primary key: data_id unique
  ✓ Value ranges: dia ∈ [1,31], mes ∈ [1,12], trimestre ∈ [1,4]
  ✓ No nulls in key columns
  ```

  **Table: fato_vendas**
  ```
  ✓ Required columns: [venda_id, produto_id, data_id, quantidade, valor_total, custo, margem]
  ✓ Data types: correct types for all columns
  ✓ Primary key: venda_id unique
  ✓ Foreign keys: produto_id ∈ dim_produto, data_id ∈ dim_tempo (0 orphans)
  ✓ Business logic: quantidade > 0, valor_total ≥ 0, custo ≥ 0
  ✓ Business logic: margem ∈ [-100%, +1000%] (reasonable range)
  ✓ Margem statistics: avg, median (no inf/NaN)
  ```

- **Output:**
  ```
  ======================================================================
  DATA QUALITY VALIDATION — GOLD LAYER
  ======================================================================

  🔍 Validating dim_produto...
    ✅ Required columns present
    ✅ Data types correct
    ✅ Primary key valid (produto_id unique: 245 rows)
    ✅ No null values in key columns
    ✅ dim_produto VALID (245 products)

  🔍 Validating dim_tempo...
    ✅ Required columns present
    ✅ Data types correct
    ✅ Primary key valid (data_id unique: 365 rows)
    ✅ No null values in key columns
    ✅ Value ranges valid
    ✅ dim_tempo VALID (365 dates)

  🔍 Validating fato_vendas...
    ✅ Required columns present
    ✅ Data types correct
    ✅ Primary key valid (venda_id unique: 5,234 rows)
    ✅ FK produto_id: 0 orphans
    ✅ FK data_id: 0 orphans
    ✅ No null values in key columns
    ✅ All quantities > 0
    ✅ All valores >= 0
    ✅ All custos >= 0
    ✅ All margins in reasonable range (-100%, +1000%)
    📊 Margin statistics: avg=45.32, median=42.18
    ✅ fato_vendas VALID (5,234 sales facts)

  ======================================================================
  OVERALL STATUS: ✅ PASSED
  ======================================================================
  ```

---

## 📝 Implementation Details

### DataQualityValidator Class

**Location:** `src/infrastructure/data_quality.py`

```python
class DataQualityValidator:
    """Validates gold layer tables for production readiness."""

    SCHEMAS = {
        "dim_produto": {...},
        "dim_tempo": {...},
        "fato_vendas": {...},
    }

    def validate_all(
        dim_produto: DataFrame,
        dim_tempo: DataFrame,
        fato_vendas: DataFrame,
    ) -> Dict[str, bool]:
        """Validate all three tables. Returns results per table."""

    def validate_dim_produto(df: DataFrame) -> bool:
        """Validate product dimension."""

    def validate_dim_tempo(df: DataFrame) -> bool:
        """Validate temporal dimension."""

    def validate_fato_vendas(
        df: DataFrame,
        dim_produto: DataFrame,
        dim_tempo: DataFrame,
    ) -> bool:
        """Validate fact table with FK references."""
```

### Integration in Pipeline

**File:** `scripts/medallion_pipeline.py`

```python
def run_pipeline(enrich_cost: bool = False) -> None:
    """Full pipeline: RAW → SILVER → GOLD → DATA QUALITY VALIDATION."""

    # Stage 1: RAW → SILVER
    silver_df = run_raw_to_silver()

    # Stage 2: SILVER → GOLD
    run_silver_to_gold(silver_df=silver_df, enrich_cost=enrich_cost)

    # Stage 3: DATA QUALITY VALIDATION (new)
    run_data_quality_validation()


def run_data_quality_validation() -> bool:
    """Load gold tables and validate quality."""

    adapter = GoldParquetAdapter()
    dim_produto = adapter.load_gold("dim_produto")
    dim_tempo = adapter.load_gold("dim_tempo")
    fato_vendas = adapter.load_gold("fato_vendas")

    validator = DataQualityValidator(verbose=True)
    results = validator.validate_all(dim_produto, dim_tempo, fato_vendas)

    # Returns: Dict[str, bool] with per-table results
    # Logs: Detailed validation report to console + logger
```

---

## 🚀 Usage

### Run Full Pipeline (with validation)

```bash
# From project root
python scripts/medallion_pipeline.py
```

**Output:**
- `data/processed/silver/sales_silver.parquet`
- `data/processed/gold/dim_produto.parquet`
- `data/processed/gold/dim_tempo.parquet`
- `data/processed/gold/fato_vendas.parquet`
- Validation report (console + logs)

### Run Stages Separately

```bash
# RAW → SILVER only
python scripts/medallion_pipeline.py --silver

# SILVER → GOLD only (silver must exist)
python scripts/medallion_pipeline.py --gold

# With cost enrichment from Google Sheets
python scripts/medallion_pipeline.py --gold --enrich-cost

# Validate star schema joins
python scripts/medallion_pipeline.py --validate
```

---

## 📋 Validation Checklist

| Check | dim_produto | dim_tempo | fato_vendas |
|-------|-------------|----------|-------------|
| Required columns present | ✅ | ✅ | ✅ |
| Data types correct | ✅ | ✅ | ✅ |
| Primary key unique | ✅ | ✅ | ✅ |
| No nulls in keys | ✅ | ✅ | ✅ |
| FK referential integrity | — | — | ✅ |
| Value ranges reasonable | — | ✅ | ✅ |
| Business logic (margem) | — | — | ✅ |
| Statistics sanity check | — | — | ✅ |

---

## 🔍 Example: End-to-End Join

After validation passes, data is production-ready for BI queries:

```sql
-- Equivalent to pandas inner join
SELECT
  fv.venda_id,
  fv.num_venda,
  dp.nome_produto,
  dt.data,
  dt.nome_mes,
  fv.quantidade,
  fv.valor_unitario,
  fv.valor_total,
  fv.custo,
  fv.margem
FROM fato_vendas fv
LEFT JOIN dim_produto dp ON fv.produto_id = dp.produto_id
LEFT JOIN dim_tempo dt ON fv.data_id = dt.data_id
ORDER BY fv.venda_id
LIMIT 10;
```

---

## ⚠️ Known Constraints & Considerations

1. **Cost Enrichment (Optional)**
   - Requires `GOOGLE_APPLICATION_CREDENTIALS` and `GOOGLE_SHEET_ID` env vars
   - Defaults to `custo = 0.0` if connection fails (safe default)
   - Margem calculations use current custo values (may be 0.0 if not enriched)

2. **Surrogate Keys**
   - 1-based integers (produto_id, data_id, venda_id)
   - Assigned at dimension/fact build time (deterministic)
   - Do NOT rely on order — use explicit joins

3. **Margem Formula**
   - Contribution margin per unit: `(valor_total - custo) / quantidade`
   - Handles edge cases: zero quantity → margem = 0
   - Can be negative if cost > revenue (valid business scenario)

4. **Date Precision**
   - Truncated to day precision (midnight)
   - No time component in dim_tempo.data

5. **Cross-File Deduplication**
   - Uses `num_venda + produto_key` for dedup (silver layer)
   - Keeps first occurrence
   - Preserves source file metadata for audit trail

---

## 📚 Related Documentation

- [Quick Start: Faturamento Page](QUICK_START_FATURAMENTO.md)
- [Gold Layer Integration Guide](GOLD_LAYER_INTEGRATION.md)
- [Parsing Dates: Developer Guide](GUIA_TESTE_STREAMLIT.md)
- [Refactoring Summary](REFACTORING_SUMMARY.md)

---

## ✅ Testing

All validation logic uses `pandas` + simple `assert` statements:

```python
# Example validation assertion
assert df["produto_id"].nunique() == len(df), \
    f"Duplicate produto_id found"

assert (df["quantidade"] > 0).all(), \
    f"Found {(df['quantidade'] <= 0).sum()} rows with quantidade <= 0"
```

No external validation framework required — pure pandas + logging.

---

**Last Updated:** 2026-03-30
**Version:** 1.0
**Status:** ✅ Production-Ready

