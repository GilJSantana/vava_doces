"""Tests for seasonality chart rendering (Sazonalidade Mensal)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.presentation.pages.dashboard import _render_sazonalidade_mensal


class TestRenderSazonalidadeMensal:
    """Test suite for monthly seasonality chart rendering."""

    @patch("src.presentation.pages.dashboard.st")
    @patch("src.presentation.pages.dashboard.load_parquet_from_drive")
    def test_missing_file_shows_info_message(self, mock_load, mock_st):
        """When parquet file is missing, should show info message."""
        mock_load.return_value = None
        mock_st.subheader = MagicMock()
        mock_st.info = MagicMock()

        _render_sazonalidade_mensal()

        mock_st.info.assert_called_once()
        assert "Execute o pipeline" in str(mock_st.info.call_args)

    @patch("src.presentation.pages.dashboard.st")
    @patch("src.presentation.pages.dashboard.load_parquet_from_drive")
    def test_empty_dataframe_shows_info_message(self, mock_load, mock_st):
        """When DataFrame is empty, should show info message."""
        mock_load.return_value = pd.DataFrame()
        mock_st.subheader = MagicMock()
        mock_st.info = MagicMock()

        _render_sazonalidade_mensal()

        mock_st.info.assert_called_once()

    @patch("src.presentation.pages.dashboard.st")
    @patch("src.presentation.pages.dashboard.load_parquet_from_drive")
    def test_missing_mes_ano_column_shows_warning(self, mock_load, mock_st):
        """When mes_ano column is missing, should show warning."""
        df = pd.DataFrame({"total_pedidos": [10, 20]})
        mock_load.return_value = df
        mock_st.subheader = MagicMock()
        mock_st.warning = MagicMock()

        _render_sazonalidade_mensal()

        mock_st.warning.assert_called()
        assert "Coluna de mês/ano" in str(mock_st.warning.call_args)

    @patch("src.presentation.pages.dashboard.st")
    @patch("src.presentation.pages.dashboard.load_parquet_from_drive")
    def test_missing_total_pedidos_column_shows_warning(self, mock_load, mock_st):
        """When total_pedidos column is missing, should show warning."""
        df = pd.DataFrame({
            "mes_ano": pd.date_range("2026-01-01", periods=2, freq="MS"),
            "mes_ano_label": ["2026-01", "2026-02"],
        })
        mock_load.return_value = df
        mock_st.subheader = MagicMock()
        mock_st.warning = MagicMock()

        _render_sazonalidade_mensal()

        mock_st.warning.assert_called()
        assert "total_pedidos" in str(mock_st.warning.call_args)

    @patch("src.presentation.pages.dashboard.st")
    @patch("src.presentation.pages.dashboard.load_parquet_from_drive")
    def test_valid_data_renders_bar_chart(self, mock_load, mock_st):
        """With valid data, should render bar_chart."""
        df = pd.DataFrame({
            "mes_ano": pd.date_range("2026-01-01", periods=3, freq="MS"),
            "mes_ano_label": ["2026-01", "2026-02", "2026-03"],
            "total_pedidos": [50, 75, 60],
            "faturamento_total": [500.0, 750.0, 600.0],
        })
        mock_load.return_value = df
        mock_st.subheader = MagicMock()
        mock_st.bar_chart = MagicMock()
        mock_st.columns = MagicMock(return_value=[MagicMock(), MagicMock(), MagicMock()])
        mock_st.metric = MagicMock()

        _render_sazonalidade_mensal()

        mock_st.bar_chart.assert_called_once()

    @patch("src.presentation.pages.dashboard.st")
    @patch("src.presentation.pages.dashboard.load_parquet_from_drive")
    def test_metrics_calculated_correctly(self, mock_load, mock_st):
        """Metrics (analyzed months, peak month, average) should be calculated."""
        df = pd.DataFrame({
            "mes_ano": pd.date_range("2026-01-01", periods=3, freq="MS"),
            "mes_ano_label": ["2026-01", "2026-02", "2026-03"],
            "total_pedidos": [50, 100, 60],  # Peak in Feb
            "faturamento_total": [500.0, 1000.0, 600.0],
        })
        mock_load.return_value = df
        mock_st.subheader = MagicMock()
        mock_st.bar_chart = MagicMock()

        # Mock columns and column context managers
        col_mocks = [MagicMock() for _ in range(3)]
        mock_st.columns = MagicMock(return_value=col_mocks)
        for col in col_mocks:
            col.__enter__ = MagicMock(return_value=col)
            col.__exit__ = MagicMock(return_value=False)

        _render_sazonalidade_mensal()

        # Verify st.metric was called 3 times (months, peak, average)
        assert mock_st.metric.call_count == 3

        # Check metric calls (order may vary, so check all calls)
        calls = [str(call) for call in mock_st.metric.call_args_list]
        metrics_str = " ".join(calls)

        assert "Meses Analisados" in metrics_str
        assert "3" in metrics_str  # 3 months analyzed
        assert "Mês de Pico" in metrics_str
        assert "2026-02" in metrics_str  # Peak is February
        assert "Média Mensal" in metrics_str
        assert "70" in metrics_str  # Average: (50+100+60)/3 = 70

    @patch("src.presentation.pages.dashboard.st")
    @patch("src.presentation.pages.dashboard.load_parquet_from_drive")
    def test_datetime_conversion_preserves_order(self, mock_load, mock_st):
        """Datetime conversion should preserve chronological order."""
        # Load with mes_ano as string (worst case)
        df = pd.DataFrame({
            "mes_ano": ["2026-04-01", "2026-01-01", "2026-12-01"],
            "mes_ano_label": ["2026-04", "2026-01", "2026-12"],
            "total_pedidos": [50, 100, 75],
        })
        mock_load.return_value = df
        mock_st.subheader = MagicMock()
        mock_st.bar_chart = MagicMock()
        mock_st.columns = MagicMock(return_value=[MagicMock(), MagicMock(), MagicMock()])
        mock_st.metric = MagicMock()

        _render_sazonalidade_mensal()

        # Chart should be called with data sorted chronologically
        mock_st.bar_chart.assert_called_once()

        # Verify the chart_df passed has correct order
        chart_df_arg = mock_st.bar_chart.call_args[0][0]
        # After sorting by mes_ano (datetime), index should be [2026-01, 2026-04, 2026-12]
        labels = chart_df_arg.index.tolist()
        assert labels == ["2026-01", "2026-04", "2026-12"]

    @patch("src.presentation.pages.dashboard.st")
    @patch("src.presentation.pages.dashboard.load_parquet_from_drive")
    def test_renders_with_mes_ano_label_fallback(self, mock_load, mock_st):
        """Should render even if mes_ano_label is missing (use strftime fallback)."""
        df = pd.DataFrame({
            "mes_ano": pd.date_range("2026-01-01", periods=2, freq="MS"),
            "total_pedidos": [50, 75],
        })
        mock_load.return_value = df
        mock_st.subheader = MagicMock()
        mock_st.bar_chart = MagicMock()
        mock_st.columns = MagicMock(return_value=[MagicMock(), MagicMock(), MagicMock()])
        mock_st.metric = MagicMock()

        _render_sazonalidade_mensal()

        # Should render using strftime fallback
        mock_st.bar_chart.assert_called_once()

    @patch("src.presentation.pages.dashboard.st")
    @patch("src.presentation.pages.dashboard.load_parquet_from_drive")
    def test_handles_null_faturamento_column(self, mock_load, mock_st):
        """Should handle missing faturamento_total gracefully."""
        df = pd.DataFrame({
            "mes_ano": pd.date_range("2026-01-01", periods=2, freq="MS"),
            "mes_ano_label": ["2026-01", "2026-02"],
            "total_pedidos": [50, 75],
            # faturamento_total is intentionally missing
        })
        mock_load.return_value = df
        mock_st.subheader = MagicMock()
        mock_st.bar_chart = MagicMock()
        mock_st.columns = MagicMock(return_value=[MagicMock(), MagicMock(), MagicMock()])
        mock_st.metric = MagicMock()

        # Should not raise an error
        _render_sazonalidade_mensal()

        mock_st.bar_chart.assert_called_once()

