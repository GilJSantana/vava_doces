"""Regression tests for dashboard profitability logic."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.presentation.pages.dashboard import (
    _invalidate_metrics_without_cost,
    _normalize_margin_percent,
    _fmt_currency,
    _normalize_join_key,
    _stabilize_profitability_metrics,
)
import src.presentation.pages.dashboard as dashboard


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


def test_normalize_join_key_aligns_numeric_and_string_variants() -> None:
    s = pd.Series([1.0, " 1 ", "abc ", None])
    result = _normalize_join_key(s)
    assert result.iloc[0] == "1"
    assert result.iloc[1] == "1"
    assert result.iloc[2] == "ABC"
    assert pd.isna(result.iloc[3])


def test_stabilize_profitability_metrics_caps_positive_margin_and_invalidates_bad_costs() -> None:
    df = pd.DataFrame(
        {
            "preco_venda_unitario": [10.0, 12.0, 8.0],
            "custo_producao_unitario": [1.0, 0.0, -2.0],
            "margem_valor": [9.0, 12.0, 10.0],
            "margem_perc": [150.0, 100.0, 125.0],
            "markup": [10.0, np.inf, -4.0],
        }
    )

    result = _stabilize_profitability_metrics(df)

    assert result.loc[0, "margem_perc"] == 100.0
    assert pd.isna(result.loc[1, "margem_perc"])
    assert pd.isna(result.loc[2, "margem_perc"])
    assert pd.isna(result.loc[1, "markup"])
    assert pd.isna(result.loc[2, "markup"])


# ── _fmt_currency ─────────────────────────────────────────────────────────────

def test_fmt_currency_formats_brl_ptbr() -> None:
    assert _fmt_currency(1234.56) == "R$ 1.234,56"


def test_fmt_currency_returns_audit_needed_for_nan() -> None:
    assert _fmt_currency(None) == "⚠️ Audit Needed"
    assert _fmt_currency(float("nan")) == "⚠️ Audit Needed"


def test_build_profitability_base_normalizes_keys_before_merge(monkeypatch) -> None:
    agg_produto = pd.DataFrame(
        {
            "produto_id": [1.0],
            "nome_produto": ["Brigadeiro"],
            "qtd_vendida": [2],
            "faturamento_liquido": [20.0],
        }
    )
    rentabilidade = pd.DataFrame(
        {
            "id_produto": [" 1 "],
            "custo_producao_unitario": [5.0],
            "custo_producao_unitario_audit": [5.0],
            "margem_valor": [5.0],
            "margem_perc": [25.0],
            "markup": [2.0],
        }
    )

    def _fake_load(name: str) -> pd.DataFrame:
        if name == "agg_vendas_produto":
            return agg_produto
        if name == "gold_rentabilidade":
            return rentabilidade
        return pd.DataFrame()

    monkeypatch.setattr(dashboard, "_load_gold_optional", _fake_load)

    result = dashboard._build_profitability_base.__wrapped__()

    assert len(result) == 1
    assert result.loc[0, "id_produto"] == "1"
    assert result.loc[0, "custo_producao_unitario"] == 5.0


def test_build_profitability_base_falls_back_to_product_name_when_rentability_ids_are_blank(monkeypatch) -> None:
    agg_produto = pd.DataFrame(
        {
            "produto_id": [38.0],
            "nome_produto": ["Brigadeiro"],
            "qtd_vendida": [2],
            "faturamento_liquido": [20.0],
        }
    )
    rentabilidade = pd.DataFrame(
        {
            "id_produto": [None],
            "nome_produto": ["brigadeiro "],
            "custo_producao_unitario": [5.0],
            "custo_producao_unitario_audit": [5.0],
            "margem_valor": [5.0],
            "margem_perc": [25.0],
            "markup": [2.0],
        }
    )

    def _fake_load(name: str) -> pd.DataFrame:
        if name == "agg_vendas_produto":
            return agg_produto
        if name == "gold_rentabilidade":
            return rentabilidade
        return pd.DataFrame()

    monkeypatch.setattr(dashboard, "_load_gold_optional", _fake_load)

    result = dashboard._build_profitability_base.__wrapped__()

    assert len(result) == 1
    assert result.loc[0, "id_produto"] == "38"
    assert result.loc[0, "custo_producao_unitario"] == 5.0
    assert result.loc[0, "margem_perc"] == 25.0


