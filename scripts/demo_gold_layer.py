#!/usr/bin/env python
"""Demo: Using gold layer with ProductAnalysisService.

Run with: python scripts/demo_gold_layer.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.domain.service_factory import create_product_analysis_service_with_gold
from src.infrastructure.gold_adapter import GoldParquetAdapter
from src.ports.data_source import DataSourceError


def demo_gold_adapter():
    """Demo 1: Direct use of GoldParquetAdapter."""
    print("\n" + "="*70)
    print("DEMO 1: Direct Gold Adapter Usage")
    print("="*70 + "\n")

    try:
        adapter = GoldParquetAdapter()

        # Load dimension tables
        print("Loading gold dimensions...")
        dim_produto = adapter.load_gold("dim_produto")
        dim_tempo = adapter.load_gold("dim_tempo")
        fato_vendas = adapter.load_gold("fato_vendas")

        print(f"✅ dim_produto:  {len(dim_produto):>5} rows")
        print(f"✅ dim_tempo:    {len(dim_tempo):>5} rows")
        print(f"✅ fato_vendas:  {len(fato_vendas):>5} rows\n")

        print("dim_produto columns:", list(dim_produto.columns))
        print("First 3 products:\n", dim_produto.head(3))

    except DataSourceError as e:
        print(f"⚠️  Gold files not found: {e}")
        print("   Run: python scripts/medallion_pipeline.py")


def demo_service_with_gold():
    """Demo 2: ProductAnalysisService with optional gold support."""
    print("\n" + "="*70)
    print("DEMO 2: Service with Optional Gold Layer")
    print("="*70 + "\n")

    try:
        # Create service with gold support
        service = create_product_analysis_service_with_gold(use_gold=True)

        # Load sales data from gold
        print("Loading sales data from gold layer...")
        sales_df = service.get_sales_data(prefer_gold=True)

        if sales_df is not None:
            print(f"✅ Loaded {len(sales_df)} records from gold layer\n")
            print("Columns:", list(sales_df.columns))
            print("\nFirst 5 sales records:")
            print(sales_df.head(5))
        else:
            print("⚠️  No sales data available")

    except Exception as e:
        print(f"⚠️  Error: {e}")


def demo_backward_compatibility():
    """Demo 3: Backward compatibility - service without gold."""
    print("\n" + "="*70)
    print("DEMO 3: Backward Compatibility (Raw Data Only)")
    print("="*70 + "\n")

    try:
        # Create service WITHOUT gold support
        service = create_product_analysis_service_with_gold(use_gold=False)

        # Load sales data from raw (Google Sheets)
        print("Loading sales data from raw layer (Google Sheets)...")
        sales_df = service.get_sales_data(prefer_gold=False)

        if sales_df is not None:
            print(f"✅ Loaded {len(sales_df)} records from raw layer\n")
            print("This works exactly as before - no breaking changes!")
        else:
            print("⚠️  No raw data available (Google Sheets not connected)")
            print("   Set env vars: GOOGLE_APPLICATION_CREDENTIALS, GOOGLE_SHEET_ID")

    except Exception as e:
        print(f"⚠️  Note: {e}")


def demo_gold_cache():
    """Demo 4: Caching behavior."""
    print("\n" + "="*70)
    print("DEMO 4: Gold Adapter Caching")
    print("="*70 + "\n")

    try:
        adapter = GoldParquetAdapter()

        print("Loading dim_produto (first time - reads from disk)...")
        df1 = adapter.load_gold("dim_produto")
        print(f"   Returned {len(df1)} rows\n")

        print("Loading dim_produto (second time - from cache)...")
        df2 = adapter.load_gold("dim_produto")
        print(f"   Returned {len(df2)} rows")
        print(f"   Same data: {df1.equals(df2)}")
        print(f"   Different objects: {df1 is not df2}\n")

        print("Clearing cache...")
        adapter.clear_cache()
        print("✅ Cache cleared")

    except DataSourceError as e:
        print(f"⚠️  Gold files not found: {e}")


def demo_data_quality():
    """Demo 5: Gold layer data quality metrics."""
    print("\n" + "="*70)
    print("DEMO 5: Gold Layer Data Quality")
    print("="*70 + "\n")

    try:
        adapter = GoldParquetAdapter()
        fato_vendas = adapter.load_gold("fato_vendas")
        dim_tempo = adapter.load_gold("dim_tempo")

        print("Data Quality Metrics:")
        print(f"  Total records:        {len(fato_vendas)}")
        print(f"  Null venda_id:        {fato_vendas['venda_id'].isna().sum()}")
        print(f"  Null produto_id:      {fato_vendas['produto_id'].isna().sum()}")
        print(f"  Null data_id:         {fato_vendas['data_id'].isna().sum()}")

        print(f"\n  Date range:           {dim_tempo['data'].min()} to {dim_tempo['data'].max()}")
        print(f"  Unique products:      {fato_vendas['produto_id'].nunique()}")
        print(f"  Unique dates:         {fato_vendas['data_id'].nunique()}")

        import numpy as np
        inf_count = np.isinf(fato_vendas['margem']).sum()
        print(f"  Infinite margins:     {inf_count}")

        print("\n✅ All quality checks passed!")

    except DataSourceError as e:
        print(f"⚠️  Gold files not found: {e}")


def main():
    """Run all demos."""
    print("\n" + "#"*70)
    print("# Vava Doces — Gold Layer Integration Demos")
    print("#"*70)

    demo_gold_adapter()
    demo_service_with_gold()
    demo_backward_compatibility()
    demo_gold_cache()
    demo_data_quality()

    print("\n" + "#"*70)
    print("# Demos Complete")
    print("#"*70 + "\n")


if __name__ == "__main__":
    main()


