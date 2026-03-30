"""Página de dashboard central de insights (custos + faturamento)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.infrastructure.gold_adapter import GoldParquetAdapter
from src.presentation.chart_style import (
    apply_bar_colors_by_y,
    apply_clean_xy_axes,
    apply_minimal_figure_style,
    build_color_map,
)
from src.presentation.components import render_separator
from src.presentation.pages.sales_shared import (
    build_category_donut_figure,
    build_top_products_figure,
    compute_high_level_kpis,
    format_brl,
    inject_roboto_font,
    load_sales_data_cached,
)

def _to_numeric_currency_series(series: pd.Series) -> pd.Series:
    """Normalize currency-like strings into float for consistent charting."""
    text = series.astype(str).str.strip()
    text = text.replace({"": None, "nan": None, "None": None})
    text = text.str.replace(r"[^0-9,.-]", "", regex=True)

    has_comma = text.str.contains(",", na=False)
    has_dot = text.str.contains(r"\.", na=False)
    mixed_mask = has_comma & has_dot

    text.loc[mixed_mask] = text.loc[mixed_mask].str.replace(".", "", regex=False)
    text = text.str.replace(",", ".", regex=False)
    values = pd.to_numeric(text, errors="coerce")
    return pd.Series(values, index=series.index)


def _build_cost_production_figure(dim_produto: pd.DataFrame, fato_vendas: pd.DataFrame, color_map: dict[str, str]) -> go.Figure | None:
    """Build horizontal production-cost chart from gold layer dimensions."""
    if dim_produto is None or fato_vendas is None:
        return None

    # Group fato_vendas by produto_id and sum custo
    cost_by_produto = fato_vendas.groupby("produto_id").agg({"custo": "sum"}).reset_index()
    
    # Join with dim_produto to get names
    cost_df = cost_by_produto.merge(dim_produto, on="produto_id", how="left")
    cost_df = cost_df.rename(columns={"nome_produto": "produto"})
    
    if cost_df.empty:
        return None

    cost_df = cost_df.sort_values("custo", ascending=False).head(10)

    fig = go.Figure(
        data=[
            go.Bar(
                x=cost_df["custo"],
                y=cost_df["produto"],
                orientation="h",
                customdata=cost_df[["custo"]].values,
                hovertemplate="<b>%{y}</b><br>Custo: R$ %{customdata[0]:.2f}<extra></extra>",
            )
        ]
    )
    apply_minimal_figure_style(fig, showlegend=False, hovermode="y unified")
    fig.update_layout(margin={"l": 220, "r": 24, "t": 16, "b": 20})
    apply_clean_xy_axes(fig, x_title="Custo de Produção (R$)", x_tickprefix="R$ ", y_title="")
    apply_bar_colors_by_y(fig, color_map)
    return fig


@st.cache_data
def _prepare_costs_dataframe(fato_vendas: pd.DataFrame, dim_produto: pd.DataFrame) -> pd.DataFrame:
    """Prepare cost summary from gold layer fato_vendas."""
    if fato_vendas is None or fato_vendas.empty:
        return pd.DataFrame(columns=["id", "custo_total"])

    # Group by produto_id and sum custo
    cost_by_produto = fato_vendas.groupby("produto_id").agg({"custo": "sum"}).reset_index()
    cost_by_produto = cost_by_produto.merge(dim_produto[["produto_id"]], on="produto_id", how="inner")
    
    df_costs = pd.DataFrame(
        {
            "id": cost_by_produto["produto_id"].astype(str),
            "custo_total": cost_by_produto["custo"],
        }
    )
    return df_costs


@st.cache_data
def _compute_cost_kpis(df_custos: pd.DataFrame) -> dict[str, float]:
    """Compute KPI metrics from normalized cost DataFrame."""
    if df_custos is None or df_custos.empty:
        return {
            "total_produtos": 0.0,
            "custo_total": 0.0,
            "custo_medio": 0.0,
            "custo_minimo": 0.0,
            "custo_maximo": 0.0,
        }

    total_skus = float(df_custos["id"].nunique())
    total_cost = float(df_custos["custo_total"].sum())
    avg_cost = float(df_custos["custo_total"].mean())
    min_cost = float(df_custos["custo_total"].min())
    max_cost = float(df_custos["custo_total"].max())

    return {
        "total_produtos": total_skus,
        "custo_total": total_cost,
        "custo_medio": avg_cost,
        "custo_minimo": min_cost,
        "custo_maximo": max_cost,
    }


def _inject_cost_kpi_card_styles() -> None:
    """Inject premium card styles used by production-cost KPI grid."""
    st.markdown(
        """
        <style>
          .vava-kpi-card {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.10);
            border-radius: 10px;
            padding: 14px 16px;
            min-height: 94px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            gap: 8px;
          }
          .vava-kpi-title {
            font-family: 'Roboto', sans-serif;
            font-size: 0.85rem;
            font-weight: 500;
            color: #d7deea;
            line-height: 1.2;
          }
          .vava-kpi-value {
            font-family: 'Roboto', sans-serif;
            font-size: 1.45rem;
            font-weight: 700;
            color: #ffffff;
            line-height: 1.1;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_cost_kpi_card(column, icon: str, title: str, value: str) -> None:
    """Render one custom KPI card."""
    with column:
        st.markdown(
            (
                "<div class='vava-kpi-card'>"
                f"<div class='vava-kpi-title'>{icon} {title}</div>"
                f"<div class='vava-kpi-value'>{value}</div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )


def _render_cost_kpi_grid(fato_vendas: pd.DataFrame) -> None:
    """Render 5-card KPI grid for production cost metrics from gold layer."""
    if fato_vendas is None or fato_vendas.empty:
        st.warning("⚠️ Não há dados de custo disponíveis.")
        return

    df_custos = _prepare_costs_dataframe(fato_vendas, pd.DataFrame())
    kpis = _compute_cost_kpis(df_custos)

    _inject_cost_kpi_card_styles()

    c1, c2, c3, c4, c5 = st.columns(5)
    _render_cost_kpi_card(c1, "🛍️", "Total de Produtos", f"{int(kpis['total_produtos'])}")
    _render_cost_kpi_card(c2, "💸", "Custo de Produção Total", format_brl(kpis["custo_total"]))
    _render_cost_kpi_card(c3, "📊", "Custo de Produção Médio", format_brl(kpis["custo_medio"]))
    _render_cost_kpi_card(c4, "🔽", "Custo de Produção Mínimo", format_brl(kpis["custo_minimo"]))
    _render_cost_kpi_card(c5, "🔼", "Custo de Produção Máximo", format_brl(kpis["custo_maximo"]))


def _render_high_level_kpis(kpis: dict[str, float]) -> None:
    """Render cards with total revenue, total cost and profit delta."""
    col1, col2, col3 = st.columns(3)

    faturamento_total = kpis["faturamento_total"]
    custo_total = kpis["custo_total"]
    lucro_total = kpis["lucro_total"]

    margem_pct = (lucro_total / faturamento_total * 100.0) if faturamento_total > 0 else 0.0
    delta_vs_custo = (lucro_total / custo_total * 100.0) if custo_total > 0.0 else 0.0

    col1.metric("💰 Faturamento Total", format_brl(faturamento_total))
    col2.metric("💸 Custo Total", format_brl(custo_total))
    col3.metric(
        "📈 Lucro (Delta)",
        format_brl(lucro_total),
        delta=f"{margem_pct:.1f}% margem | {delta_vs_custo:.1f}% vs custo",
    )


def _collect_product_names(df: pd.DataFrame) -> list[str]:
    """Collect product names from sales data."""
    names: list[str] = []
    if df is not None and "produto" in df.columns:
        names.extend(df["produto"].dropna().astype(str).tolist())
    return names



def _render_visual_section(df: pd.DataFrame, dim_produto: pd.DataFrame, fato_vendas: pd.DataFrame) -> None:
    """Render revenue and cost analyses using gold layer dimensions."""
    product_names = _collect_product_names(df)
    color_map = build_color_map(product_names)

    with st.container(border=True):
        st.subheader("Análise de Faturamento")
        col_left, col_right = st.columns([1.45, 1])

        with col_left:
            fig_top = build_top_products_figure(df, top_n=10)
            if fig_top is None:
                st.warning("⚠️ Sem dados para o Top 10 de produtos.")
            else:
                apply_bar_colors_by_y(fig_top, color_map)
                st.plotly_chart(fig_top, width="stretch")

        with col_right:
            fig_cat = build_category_donut_figure(df)
            if fig_cat is None:
                st.warning("⚠️ Sem dados de categoria para o período selecionado.")
            else:
                st.plotly_chart(fig_cat, width="stretch")

    st.markdown("\n")

    with st.container(border=True):
        st.subheader("Análise de Custos de Produção")
        _render_cost_kpi_grid(fato_vendas)
        st.markdown("\n")
        fig_cost = _build_cost_production_figure(dim_produto, fato_vendas, color_map)
        if fig_cost is None:
            st.warning("⚠️ Não há dados de custo disponíveis para exibir o gráfico.")
        else:
            st.plotly_chart(fig_cost, width="stretch")


def show_dashboard(service, product_service):
    """Renderiza página inicial de insights com dados do gold layer."""
    del service, product_service  # Dashboard usa gold layer

    inject_roboto_font()
    st.header("📊 Dashboard")
    st.caption("Página inicial de insights: faturamento, custos e lucratividade.")
    render_separator()

    sales_df = load_sales_data_cached()
    if sales_df is None or sales_df.empty:
        st.warning("⚠️ Não foi possível carregar dados de vendas para o dashboard.")
        return

    # Load additional gold dimensions
    try:
        adapter = GoldParquetAdapter()
        dim_produto = adapter.load_gold("dim_produto")
        fato_vendas = adapter.load_gold("fato_vendas")
    except Exception:
        st.warning("⚠️ Não foi possível carregar dimensões do gold layer.")
        dim_produto = None
        fato_vendas = None

    with st.container(border=True):
        st.subheader("Visão High-Level")
        kpis = compute_high_level_kpis(sales_df)
        _render_high_level_kpis(kpis)

    st.markdown("\n")

    _render_visual_section(sales_df, dim_produto, fato_vendas)
