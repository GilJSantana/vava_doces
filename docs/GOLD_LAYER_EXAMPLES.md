"""
Gold Layer Integration Examples

This document shows how to use the new gold layer (star schema)
with the ProductAnalysisService for improved performance and data quality.
"""

# Example 1: Factory function with gold support (recommended)
# ============================================================

from src.domain.service_factory import create_product_analysis_service_with_gold

# Create service with gold layer enabled
# (falls back to raw if gold files don't exist)
service_with_gold = create_product_analysis_service_with_gold(use_gold=True)

# Load sales data from gold (deduplicated, normalized)
sales_df = service_with_gold.get_sales_data(prefer_gold=True)
print(f"Loaded {len(sales_df)} sales records from gold layer")

# Example 2: Service without gold support (backward compatible)
# =============================================================

from src.infrastructure.google_sheets_adapter import GoogleSheetsAdapter
from src.domain.product_analysis_service import ProductAnalysisService

# Create service with only raw data source
raw_source = GoogleSheetsAdapter()
service_raw_only = ProductAnalysisService(data_source=raw_source)

# Works exactly as before
sales_df_raw = service_raw_only.get_sales_data()

# Example 3: Explicit gold adapter usage
# ========================================

from src.infrastructure.gold_adapter import GoldParquetAdapter
from pathlib import Path

# Create gold adapter
gold_adapter = GoldParquetAdapter(gold_dir=Path("data/processed/gold"))

# Load specific gold tables
dim_produto = gold_adapter.load_gold("dim_produto")      # 141 products
dim_tempo = gold_adapter.load_gold("dim_tempo")          # 28 dates
fato_vendas = gold_adapter.load_gold("fato_vendas")      # 3,348 sales

print(f"Products: {len(dim_produto)}")
print(f"Dates: {len(dim_tempo)}")
print(f"Sales: {len(fato_vendas)}")

# Example 4: Service with explicit gold source
# =============================================

from src.infrastructure import GoogleSheetsAdapter, GoldParquetAdapter

raw_source = GoogleSheetsAdapter()
gold_source = GoldParquetAdapter()

service = ProductAnalysisService(
    data_source=raw_source,
    gold_source=gold_source,
)

# Get sales from gold, fallback to raw if gold unavailable
sales = service.get_sales_data(prefer_gold=True)

# Example 5: Using gold data directly with Streamlit
# ===================================================

import streamlit as st
from src.domain.service_factory import create_product_analysis_service_with_gold

@st.cache_data
def load_sales_from_gold():
    service = create_product_analysis_service_with_gold(use_gold=True)
    return service.get_sales_data(prefer_gold=True)

# In your Streamlit app:
sales_df = load_sales_from_gold()
st.dataframe(sales_df)

# Example 6: Generating gold tables
# =================================

# Run the medallion pipeline to generate gold tables:
# python scripts/medallion_pipeline.py

# With optional cost enrichment:
# python scripts/medallion_pipeline.py --gold --enrich-cost

# Validate gold star schema:
# python scripts/medallion_pipeline.py --validate

# Benefits of Using Gold Layer
# =============================
#
# 1. **Deduplication**: 10,044 raw rows → 3,348 unique (66.6% reduction)
#    - Cross-file duplicates automatically removed
#    - Intra-file duplicates preserved (per business logic)
#
# 2. **Date Normalization**: Automatic format detection per source
#    - CSV: "2/1/2026" (US mm/dd/yyyy) → 2026-02-01
#    - XLSX: "2026-02-01" (ISO) → 2026-02-01
#    - All dates guaranteed datetime64[ns]
#
# 3. **Type Safety**: All columns properly coerced
#    - Dates: datetime64[ns]
#    - Currency: float64 (R$ stripped)
#    - No string dates, no mixed types
#
# 4. **Star Schema**: Optimized for analytics
#    - Dimensions: dim_produto (141), dim_tempo (28)
#    - Facts: fato_vendas (3,348) with FKs
#    - 100% referential integrity
#    - Easy joins for BI tools
#
# 5. **Performance**: Parquet format advantages
#    - Columnar storage (fast filters)
#    - Compression (smaller files)
#    - Lazy loading (read only needed columns)
#
# 6. **Cost Enrichment**: Optional production cost data
#    - Loads from Google Sheets "Receita" tab
#    - Enables real margin calculations
#    - Automatic fallback to 0.0 if unavailable
#
# Migration Path (Backward Compatible)
# ====================================
#
# Current (Raw Data):
#    Streamlit → ProductAnalysisService → Google Sheets → Receita/Matéria Prima/Produtos
#
# With Gold (Recommended):
#    Streamlit → ProductAnalysisService → (Gold layer via Parquet)
#                                      ↓ (fallback)
#                                   Google Sheets
#
# No changes required to existing code! The service handles both transparently.
#
# To migrate:
#   1. Run: python scripts/medallion_pipeline.py
#   2. Change: service.get_sales_data() → service.get_sales_data(prefer_gold=True)
#   3. Optional: Use factory function for new code
"""

Example Usage in Real Streamlit App
====================================

import streamlit as st
from src.domain.service_factory import create_product_analysis_service_with_gold

# Create service once with gold support
@st.cache_resource
def get_service():
    return create_product_analysis_service_with_gold(use_gold=True)

service = get_service()

# Use gold data (deduplicated, normalized)
st.header("📊 Sales Dashboard")

if st.checkbox("Use Gold Layer (Recommended)", value=True):
    sales_df = service.get_sales_data(prefer_gold=True)
    st.info("✅ Using optimized gold layer (star schema)")
else:
    sales_df = service.get_sales_data(prefer_gold=False)
    st.info("⚠️ Using raw data (raw Google Sheets)")

if sales_df is not None:
    st.dataframe(sales_df)
    st.metric("Total Records", len(sales_df))
    st.metric("Date Range", f"{sales_df['data'].min()} to {sales_df['data'].max()}")

"""

