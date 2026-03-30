"""Shared sales helpers for Dashboard insights and Faturamento audit views."""

from __future__ import annotations

from io import BytesIO
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.domain.sales_analysis_service import SalesETLPipeline
from src.presentation.chart_style import (
    apply_clean_xy_axes,
    apply_minimal_figure_style,
    build_color_map,
    colors_for_labels,
)


@st.cache_data
def load_sales_data_cached() -> Optional[pd.DataFrame]:
    """Load sales data once and reuse across pages.

    Returns None when the pipeline cannot provide rows.
    """
    try:
        df = SalesETLPipeline.from_env().run()
        if df is None or df.empty:
            return None
        return df
    except Exception:
        return None


@st.cache_data
def load_sales_data_with_audit_cached() -> tuple[Optional[pd.DataFrame], dict]:
    """Load sales data plus ETL audit details.

    Returns ``(None, {})`` when the pipeline cannot provide rows.
    """
    try:
        df, audit = SalesETLPipeline.from_env().run_with_audit()
        if df is None or df.empty:
            return None, audit or {}
        return df, audit or {}
    except Exception:
        return None, {}


def inject_roboto_font() -> None:
    """Load Roboto in the browser and apply to Plotly charts."""
    st.markdown(
        """
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
        <style>
          .js-plotly-plot, .js-plotly-plot *, .plotly, .plotly * {
            font-family: 'Roboto', sans-serif !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def to_numeric_safe(series: pd.Series) -> pd.Series:
    """Coerce a Series to float with missing values as 0.0."""
    values = pd.to_numeric(series, errors="coerce")
    return pd.Series(values, index=series.index).fillna(0.0)


def format_brl(value: float) -> str:
    """Format float as BRL (pt-BR separators)."""
    text = f"{float(value):,.2f}"
    text = text.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {text}"


def enrich_sales_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Create normalized financial columns used by dashboard and audit views."""
    base = df.copy()
    base["qtd"] = to_numeric_safe(base.get("qtd", pd.Series(dtype=float)))
    base["valor_venda"] = to_numeric_safe(base.get("valor_venda", pd.Series(dtype=float)))
    base["custo_unit"] = to_numeric_safe(base.get("custo_unit", pd.Series(dtype=float)))

    valor_total_src = base.get("valor_total", pd.Series(dtype=float))
    base["valor_total_calc"] = to_numeric_safe(valor_total_src)
    missing_mask = base["valor_total_calc"] <= 0
    base.loc[missing_mask, "valor_total_calc"] = (
        base.loc[missing_mask, "valor_venda"] * base.loc[missing_mask, "qtd"]
    )

    base["custo_total_calc"] = base["custo_unit"] * base["qtd"]
    base["lucro_total_calc"] = base["valor_total_calc"] - base["custo_total_calc"]
    base["data"] = pd.to_datetime(base.get("data", pd.Series(dtype=str)), errors="coerce")
    return base


def compute_high_level_kpis(df: pd.DataFrame) -> dict[str, float]:
    """Compute high-level KPIs for dashboard cards."""
    data = enrich_sales_metrics(df)
    faturamento_total = float(data["valor_total_calc"].sum())
    custo_total = float(data["custo_total_calc"].sum())
    lucro_total = float(data["lucro_total_calc"].sum())
    return {
        "faturamento_total": faturamento_total,
        "custo_total": custo_total,
        "lucro_total": lucro_total,
    }


def build_top_products_figure(df: pd.DataFrame, top_n: int = 10) -> Optional[go.Figure]:
    """Build Top-N product revenue chart with solid distinct colors."""
    data = enrich_sales_metrics(df)
    if data.empty or "produto" not in data.columns:
        return None

    grouped = (
        data.groupby("produto", as_index=False)
        .agg(valor_total_calc=("valor_total_calc", "sum"))
        .sort_values(by="valor_total_calc", ascending=False)
        .head(top_n)
    )
    if grouped.empty:
        return None

    grouped["valor_brl"] = grouped["valor_total_calc"].apply(format_brl)

    fig = go.Figure(
        data=[
            go.Bar(
                x=grouped["valor_total_calc"],
                y=grouped["produto"],
                orientation="h",
                customdata=grouped[["valor_brl"]].values,
                hovertemplate="<b>%{y}</b><br>Faturamento: %{customdata[0]}<extra></extra>",
            )
        ]
    )
    apply_minimal_figure_style(fig, showlegend=False, hovermode="y unified")
    fig.update_layout(margin={"l": 220, "r": 24, "t": 16, "b": 20})
    apply_clean_xy_axes(fig, x_title="Faturamento (R$)", x_tickprefix="R$ ", y_title="")

    color_map = build_color_map(grouped["produto"].astype(str).tolist())
    fig.update_traces(marker_color=colors_for_labels(grouped["produto"], color_map), selector={"type": "bar"})
    return fig


def build_category_donut_figure(df: pd.DataFrame) -> Optional[go.Figure]:
    """Build donut chart for revenue by category with solid distinct colors."""
    data = enrich_sales_metrics(df)
    if data.empty or "categoria" not in data.columns:
        return None

    grouped = (
        data[data["categoria"].notna()]
        .groupby("categoria", as_index=False)
        .agg(valor_total_calc=("valor_total_calc", "sum"))
        .sort_values(by="valor_total_calc", ascending=False)
    )
    if grouped.empty:
        return None

    grouped["valor_brl"] = grouped["valor_total_calc"].apply(format_brl)

    fig = go.Figure(
        data=[
            go.Pie(
                labels=grouped["categoria"],
                values=grouped["valor_total_calc"],
                hole=0.55,
                customdata=grouped[["valor_brl"]].values,
                hovertemplate="<b>%{label}</b><br>Faturamento: %{customdata[0]}<extra></extra>",
                marker={
                    "colors": colors_for_labels(grouped["categoria"].astype(str).tolist()),
                    "line": {"color": "#FFFFFF", "width": 1},
                },
            )
        ]
    )
    apply_minimal_figure_style(fig, showlegend=True, legend_bottom=True, hovermode="closest")
    return fig


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    """Serialize DataFrame to XLSX bytes for download."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="faturamento")
    return buffer.getvalue()



