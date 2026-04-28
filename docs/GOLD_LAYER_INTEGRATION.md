# Gold Layer Integration — Current Architecture ✅

## Overview

The application now treats the Gold layer persisted in Google Drive as the main analytical source for the Streamlit UI.

Google Sheets remains available for operational support and ingestion, but the executive pages prioritize `.parquet` assets loaded directly from Drive into memory.

---

## Current Architecture

```text
Google OAuth2 + Drive authorization
                ↓
        initialize_data_pipeline()
                ↓
   RAW / manual sheets ingestion (when needed)
                ↓
      Medallion pipeline (Bronze/Silver/Gold)
                ↓
   update_parquet_in_drive(<asset>.parquet)
                ↓
Google Drive (persistent Gold lake)
                ↓
   load_parquet_from_drive(<asset>.parquet)
                ↓
    Streamlit pages (Dashboard / Custos / Faturamento)
```

---

## Key Components

### `src/infrastructure/drive_manager.py`

Main responsibilities:
- `get_drive_assets_map()`
  - discovers `.parquet` assets in Drive;
  - uses `corpora="allDrives"` and `supportsAllDrives=True`;
  - keeps the most recent file id per asset name.
- `load_parquet_from_drive(file_name)`
  - downloads bytes via Drive API;
  - loads the DataFrame with `pd.read_parquet(io.BytesIO(...))`;
  - caches the result with `@st.cache_data`.
- `update_parquet_in_drive(file_name, df)`
  - writes parquet in memory;
  - updates the existing Drive file with `MediaIoBaseUpload`.

### `scripts/medallion_pipeline.py`

The pipeline now:
- materializes Gold assets in memory;
- updates them in Google Drive;
- avoids relying on local disk as the source of truth for analytical consumption.

### Streamlit pages

- `dashboard.py` reads profitability-related Gold assets;
- `production_costs.py` reads `custos_producao_agregado.parquet` and `receitas_detalhadas.parquet`;
- `faturamento.py` reads validated sales data from the Gold layer.

---

## What Changed vs. Old Architecture

### Old
- local parquet directories were part of the main read path;
- some flows depended on raw Google Sheets/CSV data at render time;
- fallback logic mixed local disk and operational sources more heavily.

### Current
- Google Drive is the persistent analytical storage;
- Streamlit consumes Gold assets directly from Drive;
- local disk is no longer the primary analytical store;
- `st.secrets["gcp_service_account"]` is the canonical credential source.

---

## Main Gold Assets

Typical assets discovered dynamically in Drive:
- `fato_vendas.parquet`
- `dim_produto.parquet`
- `dim_tempo.parquet`
- `agg_vendas_produto.parquet`
- `gold_rentabilidade.parquet`
- `custos_producao_agregado.parquet`
- `receitas_detalhadas.parquet`

---

## Caching Strategy

- `@st.cache_resource` for Drive asset discovery map
- `@st.cache_data` for parquet loads
- targeted cache clear when the user clicks refresh in the sidebar

This keeps the UI responsive while preserving Drive as the durable backend.

---

## Operational Notes

- The app still supports operational/manual data coming from Google Sheets during ingestion.
- The executive UI should prefer Gold assets whenever available.
- Missing or invalid costs remain auditable instead of being silently converted into valid profitability.

---

## Validation Status

The current project test suite validates:
- Drive asset discovery flags and mapping behavior;
- profitability pipeline integration;
- dashboard profitability safeguards;
- production costs and sales pages consuming Gold data.

---

## Recommendation

For new development, treat this document as the source of truth for Gold-layer consumption:
- **Drive-backed**
- **diskless at read time**
- **`st.secrets`-based credentials**
- **3 executive pages only**
