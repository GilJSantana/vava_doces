"""Unit tests for src/domain/sales_silver_normalizer.py."""

from __future__ import annotations

import pandas as pd

from src.domain.sales_silver_normalizer import (
    normalize_sales_to_silver,
    normalize_sales_to_silver_with_audit,
)


def test_normalize_sales_to_silver_standardizes_columns_and_types():
    raw = pd.DataFrame(
        [
            {
                "nome_produto": "  PROD-001 - brigadeiro tradicional ",
                "quantidade": "2",
                "valor_unitario": "45,00",
                "valor_total": "90,00",
                "tipo_negociacao": "ifood app",
                "data": "02/01/2026",
                "source_file": "sales_data_01_2026.csv",
            },
            {
                "nome_produto": "102 - risole frango",
                "quantidade": "1",
                "valor_unitario": "45.00",
                "valor_total": "45.00",
                "tipo_negociacao": "Loja",
                "data": "2/21/2026",
                "source_file": "sales_data_02_2026.csv",
            },
        ]
    )

    silver = normalize_sales_to_silver(raw)

    assert silver["produto"].tolist() == ["Brigadeiro Tradicional", "Risole Frango"]
    assert silver["canal"].tolist() == ["IFOOD", "LOJA FISICA"]
    assert silver["valor_total"].tolist() == [90.0, 45.0]
    assert silver["qtd"].tolist() == [2.0, 1.0]
    assert silver["mes_referencia"].tolist() == ["2026-01", "2026-02"]


def test_normalize_sales_to_silver_marks_invalid_dates():
    raw = pd.DataFrame(
        [
            {
                "produto": "Brigadeiro",
                "qtd": 1,
                "valor_total": 10,
                "data": "invalida",
            }
        ]
    )

    silver = normalize_sales_to_silver(raw)

    assert bool(silver["_invalid_date"].iloc[0]) is True
    assert silver["mes_referencia"].iloc[0] == "sem_mes"


def test_normalize_sales_to_silver_deduplicates_with_traceability_audit():
    """Rows are preserved 1:1 and duplicate diagnostics remain audit-only.

    Dedup key is intentionally empty and ``removed`` stays zero because faturamento
    must preserve every source row, even when technically repeated.
    """
    raw = pd.DataFrame(
        [
            {
                "numero_da_venda": "123",
                "nome_produto": "PROD-123 - Brigadeiro",
                "quantidade": "1",
                "valor_total": "10,00",
                "tipo_negociacao": "ifood",
                "data": "02/01/2026",
                "source_file": "sales_data_01_2026.csv",
                "ingested_at_utc": "2026-04-01T10:00:00Z",
            },
            {
                "numero_da_venda": "123",
                "nome_produto": "PROD-123 - Brigadeiro",
                "quantidade": "1",
                "valor_total": "10,00",
                "tipo_negociacao": "ifood",
                "data": "02/01/2026",
                "source_file": "sales_data_01_2026.csv",
                "ingested_at_utc": "2026-04-01T10:00:00Z",
            },
        ]
    )

    silver, audit = normalize_sales_to_silver_with_audit(raw)

    assert silver["canal"].iloc[0] == "IFOOD"
    assert silver["produto"].iloc[0] == "Brigadeiro"
    assert silver["arquivo_origem"].iloc[0] == "sales_data_01_2026.csv"

    assert audit["rows_in"] == 2
    assert audit["rows_out"] == 2
    assert audit["rows_removed"] == 0
    assert audit["rows_by_source"] == {"sales_data_01_2026.csv": 2}
    assert audit["dedup"]["removed"] == 0
    assert audit["dedup"]["dedup_key"] == []
