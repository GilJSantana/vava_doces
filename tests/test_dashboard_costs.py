"""Regression tests for dashboard profitability logic."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.presentation.pages.dashboard import (
    _invalidate_metrics_without_cost,
    _normalize_margin_percent,
    _fmt_currency,
)


# ── _invalidate_metrics_without_cost ─────────────────────────────────────────

def test_invalidate_sets_margem_nan_when_cost_is_zero() -> None:
    df = pd.DataFrame(
        {
            "custo_producao_unitario": [0.0, 5.0],
            "margem_perc": [100.0, 40.0],
            "markup": [99.0, 1.5],
            "item_auditoria": [False, False],
        }
    )
    result = _invalidate_metrics_without_cost(df)
    assert pd.isna(result.loc[0, "margem_perc"]), "zero cost should produce NaN margem"
    assert result.loc[1, "margem_perc"] == 40.0, "non-zero cost should be unchanged"


def test_invalidate_sets_margem_nan_when_cost_is_nan() -> None:
    df = pd.DataFrame(
        {
            "custo_producao_unitario": [np.nan, 3.0],
            "margem_perc": [90.0, 50.0],
            "markup": [10.0, 2.0],
            "item_auditoria": [False, False],
        }
    )
    result = _invalidate_metrics_without_cost(df)
    assert pd.isna(result.loc[0, "margem_perc"])
    assert result.loc[1, "margem_perc"] == 50.0


def test_invalidate_flags_item_auditoria_for_missing_cost() -> None:
    df = pd.DataFrame(
        {
            "custo_producao_unitario": [np.nan, 8.0],
            "margem_perc": [80.0, 25.0],
            "item_auditoria": [False, False],
        }
    )
    result = _invalidate_metrics_without_cost(df)
    assert bool(result.loc[0, "item_auditoria"]) is True
    assert bool(result.loc[1, "item_auditoria"]) is False


def test_invalidate_returns_unchanged_when_all_costs_present() -> None:
    df = pd.DataFrame(
        {
            "custo_producao_unitario": [1.5, 3.0, 10.0],
            "margem_perc": [30.0, 50.0, 60.0],
            "item_auditoria": [False, False, False],
        }
    )
    result = _invalidate_metrics_without_cost(df)
    assert list(result["margem_perc"]) == [30.0, 50.0, 60.0]


def test_invalidate_returns_empty_df_unchanged() -> None:
    df = pd.DataFrame(columns=["custo_producao_unitario", "margem_perc"])
    result = _invalidate_metrics_without_cost(df)
    assert result.empty


# ── _normalize_margin_percent ─────────────────────────────────────────────────

def test_normalize_converts_decimal_to_percent() -> None:
    s = pd.Series([0.35, 0.5, -0.1])
    result = _normalize_margin_percent(s)
    assert abs(float(result.iloc[0]) - 35.0) < 0.001
    assert abs(float(result.iloc[1]) - 50.0) < 0.001
    assert abs(float(result.iloc[2]) - (-10.0)) < 0.001


def test_normalize_keeps_large_percent_unchanged() -> None:
    s = pd.Series([30.0, 55.5, -5.0])
    result = _normalize_margin_percent(s)
    assert list(result) == [30.0, 55.5, -5.0]


def test_normalize_handles_nan() -> None:
    s = pd.Series([np.nan, 0.4])
    result = _normalize_margin_percent(s)
    assert pd.isna(result.iloc[0])
    assert abs(float(result.iloc[1]) - 40.0) < 0.001


# ── _fmt_currency ─────────────────────────────────────────────────────────────

def test_fmt_currency_formats_brl_ptbr() -> None:
    assert _fmt_currency(1234.56) == "R$ 1.234,56"


def test_fmt_currency_returns_audit_needed_for_nan() -> None:
    assert _fmt_currency(None) == "⚠️ Audit Needed"
    assert _fmt_currency(float("nan")) == "⚠️ Audit Needed"

