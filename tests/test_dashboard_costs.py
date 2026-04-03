"""Regression tests for dashboard production-cost KPI preparation."""

from __future__ import annotations

import pandas as pd

from src.presentation.pages.dashboard import _prepare_costs_dataframe


def test_prepare_costs_works_without_dim_produto_dependency() -> None:
    fato_vendas = pd.DataFrame(
        {
            "produto_id": [1, 1, 2],
            "custo": [10.0, 5.0, 7.5],
        }
    )

    # Use undecorated function body to keep unit test deterministic.
    result = _prepare_costs_dataframe.__wrapped__(fato_vendas, pd.DataFrame())

    assert list(result.columns) == ["id", "custo_total"]
    assert result.shape[0] == 2
    assert float(result[result["id"] == "1"]["custo_total"].iloc[0]) == 15.0
    assert float(result[result["id"] == "2"]["custo_total"].iloc[0]) == 7.5


def test_prepare_costs_returns_empty_when_required_columns_missing() -> None:
    fato_vendas = pd.DataFrame({"custo": [10.0]})

    result = _prepare_costs_dataframe.__wrapped__(fato_vendas, None)

    assert list(result.columns) == ["id", "custo_total"]
    assert result.empty


def test_prepare_costs_skips_filter_if_dim_produto_without_produto_id() -> None:
    fato_vendas = pd.DataFrame(
        {
            "produto_id": [1, 2],
            "custo": [3.0, 4.0],
        }
    )
    dim_produto_invalid = pd.DataFrame({"nome_produto": ["A", "B"]})

    result = _prepare_costs_dataframe.__wrapped__(fato_vendas, dim_produto_invalid)

    assert result.shape[0] == 2
    assert set(result["id"].tolist()) == {"1", "2"}

