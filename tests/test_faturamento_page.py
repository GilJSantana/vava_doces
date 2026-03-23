"""Unit tests for src/presentation/pages/faturamento.py.

Tests focus on data calculation and transformation logic (no Streamlit UI rendering).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from src.presentation.pages.faturamento import (
    calculate_kpi_metrics,
    _filter_by_date_range,
    _to_numeric_safe,
)


class TestToNumericSafe:
    def test_valid_floats(self):
        s = pd.Series([1.5, 2.0, 3.5])
        result = _to_numeric_safe(s)
        assert list(result) == [1.5, 2.0, 3.5]

    def test_nan_becomes_zero(self):
        s = pd.Series([1.0, float("nan"), 3.0])
        result = _to_numeric_safe(s)
        assert result.iloc[1] == 0.0

    def test_string_coercion(self):
        s = pd.Series(["10.5", "20.0", "invalid"])
        result = _to_numeric_safe(s)
        assert result.iloc[0] == pytest.approx(10.5)
        assert result.iloc[1] == pytest.approx(20.0)
        assert result.iloc[2] == 0.0


class TestFilterByDateRange:
    def test_filters_by_date_range(self):
        df = pd.DataFrame([
            {"data": "2026-01-15", "produto": "A", "valor_venda": 100.0},
            {"data": "2026-02-10", "produto": "B", "valor_venda": 200.0},
            {"data": "2026-03-05", "produto": "C", "valor_venda": 300.0},
        ])
        df["data"] = pd.to_datetime(df["data"])

        start = datetime(2026, 2, 1)
        end = datetime(2026, 2, 28)
        result = _filter_by_date_range(df, start, end)

        assert len(result) == 1
        assert result.iloc[0]["produto"] == "B"

    def test_handles_missing_data_column(self):
        df = pd.DataFrame([{"produto": "A", "valor_venda": 100.0}])
        start = datetime(2026, 1, 1)
        end = datetime(2026, 12, 31)
        result = _filter_by_date_range(df, start, end)
        assert len(result) == 1  # No filtering

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        start = datetime(2026, 1, 1)
        end = datetime(2026, 12, 31)
        result = _filter_by_date_range(df, start, end)
        assert result.empty


class TestCalculateKPIMetrics:
    def _make_sales_df(self) -> pd.DataFrame:
        return pd.DataFrame([
            {
                "num_venda": "001",
                "produto": "Brigadeiro",
                "qtd": 2.0,
                "valor_venda": 24.0,  # 2 × R$ 12,00
                "custo_unit": 7.0,
                "lucro_est": 17.0,  # 24 - 7
                "sem_cadastro": False,
            },
            {
                "num_venda": "002",
                "produto": "Risole",
                "qtd": 1.0,
                "valor_venda": 8.0,
                "custo_unit": 2.0,
                "lucro_est": 6.0,
                "sem_cadastro": False,
            },
            {
                "num_venda": "003",
                "produto": "Produto Desconhecido",
                "qtd": 1.0,
                "valor_venda": 10.0,
                "custo_unit": float("nan"),
                "lucro_est": 10.0,
                "sem_cadastro": True,  # Orphan
            },
        ])

    def test_faturamento_total(self):
        df = self._make_sales_df()
        metrics = calculate_kpi_metrics(df)
        assert metrics["faturamento_total"] == pytest.approx(42.0)  # 24 + 8 + 10

    def test_total_itens(self):
        df = self._make_sales_df()
        metrics = calculate_kpi_metrics(df)
        assert metrics["total_itens"] == pytest.approx(4.0)  # 2 + 1 + 1

    def test_lucro_bruto_medio_excludes_orphans(self):
        """Lucro médio should only consider matched products (sem_cadastro=False)."""
        df = self._make_sales_df()
        metrics = calculate_kpi_metrics(df)
        # Only 2 matched rows: lucro_est = 17.0 and 6.0 → avg = 11.5
        assert metrics["lucro_bruto_medio"] == pytest.approx(11.5)

    def test_ticket_medio(self):
        """Ticket médio = faturamento_total / unique transactions."""
        df = self._make_sales_df()
        metrics = calculate_kpi_metrics(df)
        # 3 unique transactions, faturamento_total = 42.0 → 42/3 = 14.0
        assert metrics["ticket_medio"] == pytest.approx(14.0)

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        metrics = calculate_kpi_metrics(df)
        for value in metrics.values():
            assert value == 0.0

    def test_no_sem_cadastro_column(self):
        """Handle DataFrames without sem_cadastro column."""
        df = pd.DataFrame([
            {
                "num_venda": "001",
                "qtd": 2.0,
                "valor_venda": 24.0,
                "lucro_est": 20.0,
            },
            {
                "num_venda": "002",
                "qtd": 1.0,
                "valor_venda": 8.0,
                "lucro_est": 6.0,
            },
        ])
        metrics = calculate_kpi_metrics(df)
        assert metrics["faturamento_total"] == pytest.approx(32.0)
        assert metrics["lucro_bruto_medio"] == pytest.approx(13.0)  # (20 + 6) / 2
        assert metrics["ticket_medio"] == pytest.approx(16.0)  # 32 / 2

    def test_no_num_venda_column(self):
        """Handle DataFrames without num_venda column (ticket_medio = 0)."""
        df = pd.DataFrame([
            {
                "qtd": 2.0,
                "valor_venda": 24.0,
                "lucro_est": 20.0,
                "sem_cadastro": False,
            },
        ])
        metrics = calculate_kpi_metrics(df)
        assert metrics["faturamento_total"] == pytest.approx(24.0)
        assert metrics["ticket_medio"] == 0.0  # Cannot calculate without num_venda

