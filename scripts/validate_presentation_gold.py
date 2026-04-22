#!/usr/bin/env python
"""Quick validation of presentation layer with gold data.

Run: python scripts/validate_presentation_gold.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from src.presentation.pages.sales_shared import (
    load_sales_data_cached,
    compute_high_level_kpis,
    enrich_sales_metrics,
)
from src.infrastructure.gold_adapter import GoldParquetAdapter


def validate_gold_loading():
    """Validate gold layer loads correctly."""
    print("\n" + "="*70)
    print("VALIDATION 1: Gold Layer Loading")
    print("="*70)

    df = load_sales_data_cached()
    assert df is not None, "Failed to load sales data"
    assert len(df) == 3348, f"Expected 3348 rows, got {len(df)}"
    
    print(f"✅ Loaded {len(df)} rows from gold layer")
    print(f"   Columns: {list(df.columns)}")
    return df


def validate_kpi_computation(df):
    """Validate KPI calculation."""
    print("\n" + "="*70)
    print("VALIDATION 2: KPI Computation")
    print("="*70)

    kpis = compute_high_level_kpis(df)
    
    assert "faturamento_total" in kpis, "Missing faturamento_total"
    assert "custo_total" in kpis, "Missing custo_total"
    assert "lucro_total" in kpis, "Missing lucro_total"
    
    print(f"✅ Faturamento Total: R$ {kpis['faturamento_total']:,.2f}")
    print(f"✅ Custo Total: R$ {kpis['custo_total']:,.2f}")
    print(f"✅ Lucro Total: R$ {kpis['lucro_total']:,.2f}")
    
    return kpis


def validate_gold_dimensions():
    """Validate gold dimensions."""
    print("\n" + "="*70)
    print("VALIDATION 3: Gold Dimensions")
    print("="*70)

    adapter = GoldParquetAdapter()
    dim_produto = adapter.load_gold("dim_produto")
    dim_tempo = adapter.load_gold("dim_tempo")
    fato_vendas = adapter.load_gold("fato_vendas")
    
    assert len(dim_produto) == 141, f"Expected 141 products, got {len(dim_produto)}"
    assert len(dim_tempo) == 28, f"Expected 28 dates, got {len(dim_tempo)}"
    assert len(fato_vendas) == 3348, f"Expected 3348 facts, got {len(fato_vendas)}"
    
    print(f"✅ dim_produto: {len(dim_produto)} products")
    print(f"✅ dim_tempo: {len(dim_tempo)} dates (2026-02-01 to 2026-02-28)")
    print(f"✅ fato_vendas: {len(fato_vendas)} sales facts")
    
    return dim_produto, dim_tempo, fato_vendas


def validate_data_integrity(df, fato_vendas):
    """Validate data integrity."""
    print("\n" + "="*70)
    print("VALIDATION 4: Data Integrity")
    print("="*70)

    # Check for nulls
    null_produto_id = fato_vendas["produto_id"].isna().sum()
    null_data = df["data"].isna().sum() if "data" in df.columns else 0
    null_margem = df["margem"].isna().sum() if "margem" in df.columns else 0
    
    assert null_produto_id == 0, f"Found {null_produto_id} null produto_id"
    assert null_data == 0, f"Found {null_data} null data values"
    
    print(f"✅ Null produto_id: {null_produto_id}")
    print(f"✅ Null data: {null_data}")
    print(f"✅ Null margem: {null_margem}")
    
    # Check data types
    assert pd.api.types.is_datetime64_any_dtype(df["data"]), "data column not datetime64"
    assert pd.api.types.is_numeric_dtype(df["margem"]), "margem column not numeric"
    
    print(f"✅ data column type: {df['data'].dtype}")
    print(f"✅ margem column type: {df['margem'].dtype}")


def validate_deduplication():
    """Validate deduplication."""
    print("\n" + "="*70)
    print("VALIDATION 5: Deduplication")
    print("="*70)

    df = load_sales_data_cached()
    
    # Gold layer should have 3,348 rows (3 files × 3,348 unique rows)
    unique_rows = len(df.drop_duplicates())
    
    print(f"✅ Total rows in gold: {len(df)}")
    print(f"✅ Unique rows: {unique_rows}")
    print(f"✅ Deduplication: {len(df) == unique_rows}")
    
    assert len(df) == unique_rows, "Found duplicates in gold layer"


def validate_enrichment():
    """Validate metrics enrichment."""
    print("\n" + "="*70)
    print("VALIDATION 6: Metrics Enrichment")
    print("="*70)

    df = load_sales_data_cached()
    enriched = enrich_sales_metrics(df)
    
    # Check calculated columns exist
    assert "valor_total_calc" in enriched.columns, "Missing valor_total_calc"
    assert "lucro_total_calc" in enriched.columns, "Missing lucro_total_calc"
    
    # Check for reasonable values
    assert enriched["valor_total_calc"].sum() > 0, "No faturamento calculated"
    assert enriched["lucro_total_calc"].sum() > 0, "No lucro calculated"
    
    print(f"✅ valor_total_calc sum: R$ {enriched['valor_total_calc'].sum():,.2f}")
    print(f"✅ lucro_total_calc sum: R$ {enriched['lucro_total_calc'].sum():,.2f}")


def main():
    """Run all validations."""
    print("\n\n")
    print("█" * 70)
    print("█  PRESENTATION LAYER GOLD MIGRATION VALIDATION")
    print("█" * 70)

    try:
        df = validate_gold_loading()
        validate_kpi_computation(df)
        validate_gold_dimensions()
        validate_data_integrity(df, GoldParquetAdapter().load_gold("fato_vendas"))
        validate_deduplication()
        validate_enrichment()

        print("\n" + "="*70)
        print("✅ ALL VALIDATIONS PASSED")
        print("="*70)
        print("\nPresentation layer is ready for Streamlit!")
        print("Run: streamlit run app.py")
        print("\n")

    except AssertionError as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

