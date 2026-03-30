"""Unit tests for src/presentation/pages/faturamento.py."""

from __future__ import annotations

from datetime import date

import pandas as pd

from src.presentation.pages.faturamento import _apply_filters, _normalize_data



def test_normalize_data_keeps_datetime_without_reparsing_shift():
    source = pd.DataFrame(
        [
            {
                "data": pd.Timestamp("2026-01-02"),
                "cliente": "ifood",
                "produto": "Brigadeiro",
                "qtd": 1,
                "valor_venda": 10.0,
                "valor_total": 10.0,
                "custo_unit": 4.0,
            }
        ]
    )

    normalized = _normalize_data(source)

    assert normalized["data"].iloc[0] == pd.Timestamp("2026-01-02")
    assert normalized["cliente"].iloc[0] == "IFOOD"


def test_apply_filters_returns_january_day_range_full_when_data_is_datetime():
    source = pd.DataFrame(
        [
            {"data": pd.Timestamp("2026-01-01"), "cliente": "IFOOD", "produto": "A"},
            {"data": pd.Timestamp("2026-01-12"), "cliente": "IFOOD", "produto": "B"},
            {"data": pd.Timestamp("2026-01-13"), "cliente": "IFOOD", "produto": "C"},
            {"data": pd.Timestamp("2026-01-31"), "cliente": "IFOOD", "produto": "D"},
            {"data": pd.Timestamp("2026-02-01"), "cliente": "IFOOD", "produto": "E"},
        ]
    )

    filtered = _apply_filters(source, date(2026, 1, 1), date(2026, 1, 31), [])

    assert len(filtered) == 4
    assert filtered["data"].min() == pd.Timestamp("2026-01-01")
    assert filtered["data"].max() == pd.Timestamp("2026-01-31")


def test_apply_filters_supports_cliente_multiselect():
    source = pd.DataFrame(
        [
            {"data": pd.Timestamp("2026-01-10"), "cliente": "IFOOD", "produto": "A"},
            {"data": pd.Timestamp("2026-01-10"), "cliente": "LOJA", "produto": "B"},
        ]
    )

    filtered = _apply_filters(source, date(2026, 1, 1), date(2026, 1, 31), ["IFOOD"])

    assert len(filtered) == 1
    assert filtered["cliente"].iloc[0] == "IFOOD"
