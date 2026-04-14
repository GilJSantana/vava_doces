#!/usr/bin/env python3
"""
Test to validate that multi-product sales are preserved during deduplication.

Scenario:
- Same order (num_venda) with different products
- Should NOT be removed as duplicates
- Each item should be preserved as a separate row (item-grain fact table)
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.domain.sales_analysis_service import _deduplicate_with_audit


def test_preserve_multiproduct_same_order():
    """Verify that rows with same num_venda but different products are preserved."""
    # Create sample data: one order with two different items
    data = {
        "data": ["2024-01-15", "2024-01-15"],
        "num_venda": [1001, 1001],  # Same order
        "cliente": ["Cliente A", "Cliente A"],
        "produto": ["Caseirinho", "Brigadeiro"],  # Different products
        "quantidade": [2, 3],  # Different quantities
        "valor_unitario": [10.0, 8.0],  # Different prices
        "valor_total": [20.0, 24.0],
        "_source_file": ["sales_01_2024.csv", "sales_01_2024.csv"],
    }
    df = pd.DataFrame(data)

    deduped, audit = _deduplicate_with_audit(df)

    # Both rows should be preserved
    assert len(deduped) == 2, f"Expected 2 rows, got {len(deduped)}"
    assert audit["removed"] == 0, f"Expected 0 removed, got {audit['removed']}"
    assert deduped.iloc[0]["produto"] == "Caseirinho"
    assert deduped.iloc[1]["produto"] == "Brigadeiro"


def test_audit_exact_duplicates_same_order_without_removal():
    """Verify that truly identical rows are audited but preserved in Silver."""
    # Create sample data: one order with one product, duplicated row
    data = {
        "data": ["2024-01-15", "2024-01-15"],
        "num_venda": [1001, 1001],  # Same order
        "cliente": ["Cliente A", "Cliente A"],
        "produto": ["Caseirinho", "Caseirinho"],  # Same product
        "quantidade": [2, 2],  # Same quantity
        "valor_unitario": [10.0, 10.0],  # Same price
        "valor_total": [20.0, 20.0],
        "_source_file": ["sales_01_2024.csv", "sales_01_2024.csv"],
    }
    df = pd.DataFrame(data)

    deduped, audit = _deduplicate_with_audit(df)

    # Both rows are preserved because Silver must match Bronze exactly.
    assert len(deduped) == 2, f"Expected 2 rows, got {len(deduped)}"
    assert audit["removed"] == 0, f"Expected 0 removed, got {audit['removed']}"
    assert audit["detected_exact_by_source_file"] == {"sales_01_2024.csv": 1}


def test_preserve_same_product_different_dates():
    """Verify that same product sold on different dates is NOT deduplicated."""
    data = {
        "data": ["2024-01-15", "2024-01-16"],  # Different dates
        "num_venda": [1001, 1002],  # Different orders
        "cliente": ["Cliente A", "Cliente A"],
        "produto": ["Caseirinho", "Caseirinho"],  # Same product
        "quantidade": [2, 2],  # Same quantity
        "valor_unitario": [10.0, 10.0],  # Same price
        "valor_total": [20.0, 20.0],
        "_source_file": ["sales_01_2024.csv", "sales_01_2024.csv"],
    }
    df = pd.DataFrame(data)

    deduped, audit = _deduplicate_with_audit(df)

    # Both rows should be preserved (different dates = different transactions)
    assert len(deduped) == 2, f"Expected 2 rows, got {len(deduped)}"
    assert audit["removed"] == 0, f"Expected 0 removed, got {audit['removed']}"


def test_preserve_same_product_different_quantities():
    """Verify that same product with different quantities is NOT deduplicated."""
    data = {
        "data": ["2024-01-15", "2024-01-15"],
        "num_venda": [1001, 1002],  # Different orders
        "cliente": ["Cliente A", "Cliente A"],
        "produto": ["Caseirinho", "Caseirinho"],  # Same product
        "quantidade": [2, 3],  # Different quantities
        "valor_unitario": [10.0, 10.0],
        "valor_total": [20.0, 30.0],
        "_source_file": ["sales_01_2024.csv", "sales_01_2024.csv"],
    }
    df = pd.DataFrame(data)

    deduped, audit = _deduplicate_with_audit(df)

    # Both rows should be preserved (different quantities = different line items)
    assert len(deduped) == 2, f"Expected 2 rows, got {len(deduped)}"
    assert audit["removed"] == 0, f"Expected 0 removed, got {audit['removed']}"


if __name__ == "__main__":
    print("Testing multi-product order preservation...")

    test_preserve_multiproduct_same_order()
    print("✅ test_preserve_multiproduct_same_order PASSED")

    test_audit_exact_duplicates_same_order_without_removal()
    print("✅ test_audit_exact_duplicates_same_order_without_removal PASSED")

    test_preserve_same_product_different_dates()
    print("✅ test_preserve_same_product_different_dates PASSED")

    test_preserve_same_product_different_quantities()
    print("✅ test_preserve_same_product_different_quantities PASSED")

    print("\n✅ All tests passed!")


