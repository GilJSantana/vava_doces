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
    @patch("src.presentation.pages.dashboard._render_plot")
    @patch("src.presentation.pages.dashboard.load_parquet_from_drive")
    def test_valid_data_renders_plotly_chart(self, mock_load, mock_plot, mock_st):
        """With valid data, should render hybrid Plotly chart (bars + lines)."""
        df = pd.DataFrame({
            "mes_ano": pd.date_range("2026-01-01", periods=3, freq="MS"),
            "mes_ano_label": ["2026-01", "2026-02", "2026-03"],
            "total_pedidos": [50, 75, 60],
            "faturamento_total": [500.0, 750.0, 600.0],
        })
        mock_load.return_value = df
        mock_st.subheader = MagicMock()
        mock_st.columns = MagicMock(return_value=[MagicMock(), MagicMock(), MagicMock(), MagicMock()])
        mock_st.metric = MagicMock()
        mock_st.markdown = MagicMock()
        mock_st.info = MagicMock()

        _render_sazonalidade_mensal()

        # Should render Plotly chart (via _render_plot)
        mock_plot.assert_called()
        fig = mock_plot.call_args[0][0]
        assert len(fig.data) >= 3
        assert fig.data[0].type == "bar"
        assert fig.data[1].type == "scatter"

    @patch("src.presentation.pages.dashboard.st")
    @patch("src.presentation.pages.dashboard._render_plot")
    @patch("src.presentation.pages.dashboard.load_parquet_from_drive")
    def test_metrics_calculated_correctly(self, mock_load, mock_plot, mock_st):
        """Metrics (Month-on-Month, Year-over-Year, etc.) should be calculated."""
        df = pd.DataFrame({
            "mes_ano": pd.date_range("2026-01-01", periods=3, freq="MS"),
            "mes_ano_label": ["2026-01", "2026-02", "2026-03"],
            "total_pedidos": [50, 100, 60],  # Peak in Feb
            "faturamento_total": [500.0, 1000.0, 600.0],
        })
        mock_load.return_value = df
        mock_st.subheader = MagicMock()
        mock_st.markdown = MagicMock()
        mock_st.info = MagicMock()

        # Mock columns and column context managers (4 columns now, not 3)
        col_mocks = [MagicMock() for _ in range(4)]
        mock_st.columns = MagicMock(return_value=col_mocks)
        for col in col_mocks:
            col.__enter__ = MagicMock(return_value=col)
            col.__exit__ = MagicMock(return_value=False)

        _render_sazonalidade_mensal()

        # Verify st.metric was called with appropriate metrics including MoM and YoY
        assert mock_st.metric.call_count >= 4  # At least 4 metric calls (months, peak, MoM, YoY, average)

        # Check metric calls
        calls = [str(call) for call in mock_st.metric.call_args_list]
        metrics_str = " ".join(calls)

        assert "Meses Analisados" in metrics_str
        assert "3" in metrics_str  # 3 months analyzed
        assert "Mês de Pico" in metrics_str
        assert "2026-02" in metrics_str  # Peak is February

    @patch("src.presentation.pages.dashboard.st")
    @patch("src.presentation.pages.dashboard._render_plot")
    @patch("src.presentation.pages.dashboard.load_parquet_from_drive")
    def test_datetime_conversion_preserves_order(self, mock_load, mock_plot, mock_st):
        """Datetime conversion should preserve chronological order."""
        # Load with mes_ano as string (worst case)
        df = pd.DataFrame({
            "mes_ano": ["2026-04-01", "2026-01-01", "2026-12-01"],
            "mes_ano_label": ["2026-04", "2026-01", "2026-12"],
            "total_pedidos": [50, 100, 75],
        })
        mock_load.return_value = df
        mock_st.subheader = MagicMock()
        mock_st.markdown = MagicMock()
        mock_st.info = MagicMock()
        mock_st.columns = MagicMock(return_value=[MagicMock(), MagicMock(), MagicMock(), MagicMock()])
        mock_st.metric = MagicMock()

        _render_sazonalidade_mensal()

        # Should render Plotly chart (via _render_plot)
        mock_plot.assert_called()

    @patch("src.presentation.pages.dashboard.st")
    @patch("src.presentation.pages.dashboard._render_plot")
    @patch("src.presentation.pages.dashboard.load_parquet_from_drive")
    def test_renders_with_mes_ano_label_fallback(self, mock_load, mock_plot, mock_st):
        """Should render even if mes_ano_label is missing (use strftime fallback)."""
        df = pd.DataFrame({
            "mes_ano": pd.date_range("2026-01-01", periods=2, freq="MS"),
            "total_pedidos": [50, 75],
        })
        mock_load.return_value = df
        mock_st.subheader = MagicMock()
        mock_st.markdown = MagicMock()
        mock_st.info = MagicMock()
        mock_st.columns = MagicMock(return_value=[MagicMock(), MagicMock(), MagicMock(), MagicMock()])
        mock_st.metric = MagicMock()

        _render_sazonalidade_mensal()

        # Should render using strftime fallback
        mock_plot.assert_called()

    @patch("src.presentation.pages.dashboard.st")
    @patch("src.presentation.pages.dashboard._render_plot")
    @patch("src.presentation.pages.dashboard.load_parquet_from_drive")
    def test_handles_null_faturamento_column(self, mock_load, mock_plot, mock_st):
        """Should handle missing faturamento_total gracefully."""
        df = pd.DataFrame({
            "mes_ano": pd.date_range("2026-01-01", periods=2, freq="MS"),
            "mes_ano_label": ["2026-01", "2026-02"],
            "total_pedidos": [50, 75],
            # faturamento_total is intentionally missing
        })
        mock_load.return_value = df
        mock_st.subheader = MagicMock()
        mock_st.markdown = MagicMock()
        mock_st.info = MagicMock()
        mock_st.columns = MagicMock(return_value=[MagicMock(), MagicMock(), MagicMock(), MagicMock()])
        mock_st.metric = MagicMock()

        # Should not raise an error
        _render_sazonalidade_mensal()

        mock_plot.assert_called()

    @patch("src.presentation.pages.dashboard.st")
    @patch("src.presentation.pages.dashboard._render_plot")
    @patch("src.presentation.pages.dashboard.load_parquet_from_drive")
    def test_single_year_data_defers_yoy_and_boxplot(self, mock_load, mock_plot, mock_st):
        """With only one year, render only base chart and show guidance caption."""
        df = pd.DataFrame(
            {
                "mes_ano": pd.date_range("2026-01-01", periods=6, freq="MS"),
                "mes_ano_label": [f"2026-{m:02d}" for m in range(1, 7)],
                "total_pedidos": [50, 75, 60, 80, 90, 70],
            }
        )
        mock_load.return_value = df
        mock_st.subheader = MagicMock()
        mock_st.columns = MagicMock(return_value=[MagicMock(), MagicMock(), MagicMock(), MagicMock()])
        mock_st.metric = MagicMock()
        mock_st.caption = MagicMock()

        _render_sazonalidade_mensal()

        assert mock_plot.call_count == 1
        mock_st.caption.assert_called_once()

    @patch("src.presentation.pages.dashboard.st")
    @patch("src.presentation.pages.dashboard._render_plot")
    @patch("src.presentation.pages.dashboard.load_parquet_from_drive")
    def test_peak_is_highlighted_and_annotated(self, mock_load, mock_plot, mock_st):
        """Peak month should receive a dedicated color and a chart annotation."""
        df = pd.DataFrame(
            {
                "mes_ano": pd.date_range("2026-01-01", periods=4, freq="MS"),
                "mes_ano_label": ["2026-01", "2026-02", "2026-03", "2026-04"],
                "total_pedidos": [30, 55, 120, 80],
            }
        )
        mock_load.return_value = df
        mock_st.subheader = MagicMock()
        mock_st.columns = MagicMock(return_value=[MagicMock(), MagicMock(), MagicMock(), MagicMock()])
        mock_st.metric = MagicMock()
        mock_st.caption = MagicMock()

        _render_sazonalidade_mensal()

        fig = mock_plot.call_args[0][0]
        bar_trace = fig.data[0]
        colors = list(bar_trace.marker.color)
        assert colors.count("#f97316") == 1
        assert len(fig.layout.annotations) >= 1
        assert "Pico:" in fig.layout.annotations[0].text








