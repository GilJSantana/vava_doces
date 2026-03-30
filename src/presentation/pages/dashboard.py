"""Página de dashboard central de insights (custos + faturamento)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

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
def _build_cost_production_figure(product_service, color_map: dict[str, str]) -> go.Figure | None:
    """Restore and render horizontal production-cost chart."""
    if product_service is None:
        return None

    summary = product_service.get_product_cost_summary()
    if summary is None or summary.empty:
        return None

    cost_df = summary.copy()
    if "Custo Total (R$)" not in cost_df.columns or "Produto" not in cost_df.columns:
        return None

    cost_df["Custo Numérico"] = _to_numeric_currency_series(cost_df["Custo Total (R$)"])
    cost_df = cost_df[cost_df["Custo Numérico"].notna() & (cost_df["Custo Numérico"] > 0)]
    if cost_df.empty:
        return None

    cost_df = cost_df.sort_values("Custo Numérico", ascending=False).head(10)

    fig = go.Figure(
        data=[
            go.Bar(
                x=cost_df["Custo Numérico"],
                y=cost_df["Produto"],
                orientation="h",
                customdata=cost_df[["Custo Numérico"]].values,
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
def _prepare_costs_dataframe(cost_summary: pd.DataFrame) -> pd.DataFrame:
    """Normalize cost summary to canonical schema: id, custo_total."""
    if cost_summary is None or cost_summary.empty:
        return pd.DataFrame(columns=["id", "custo_total"])

    base = cost_summary.copy()
    id_col = "ID do Produto" if "ID do Produto" in base.columns else "id"
    cost_col = "Custo Total (R$)" if "Custo Total (R$)" in base.columns else "custo_total"

    if id_col not in base.columns or cost_col not in base.columns:
        return pd.DataFrame(columns=["id", "custo_total"])

    df_costs = pd.DataFrame(
        {
            "id": base[id_col].astype(str).str.strip(),
            "custo_total": _to_numeric_currency_series(base[cost_col]),
        }
    )
    df_costs = df_costs[df_costs["id"] != ""].copy()
    df_costs["custo_total"] = df_costs["custo_total"].fillna(0.0)
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


def _render_cost_kpi_grid(product_service) -> None:
    """Render 5-card KPI grid for production cost metrics."""
    if product_service is None:
        st.warning("⚠️ Serviço de custos indisponível para cálculo dos KPIs.")
        return

    cost_summary = product_service.get_product_cost_summary()
    df_custos = _prepare_costs_dataframe(cost_summary)
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


def _collect_product_names(df: pd.DataFrame, product_service) -> list[str]:
    """Collect product names present in revenue and cost datasets."""
    names: list[str] = []
    if "produto" in df.columns:
        names.extend(df["produto"].dropna().astype(str).tolist())

    if product_service is not None:
        cost_summary = product_service.get_product_cost_summary()
        if cost_summary is not None and not cost_summary.empty and "Produto" in cost_summary.columns:
            names.extend(cost_summary["Produto"].dropna().astype(str).tolist())
    return names


def _render_visual_section(df: pd.DataFrame, product_service) -> None:
    """Render revenue and cost analyses with a unified vibrant palette."""
    product_names = _collect_product_names(df, product_service)
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
        _render_cost_kpi_grid(product_service)
        st.markdown("\n")
        fig_cost = _build_cost_production_figure(product_service, color_map)
        if fig_cost is None:
            st.warning("⚠️ Não há dados de custo disponíveis para exibir o gráfico.")
        else:
            st.plotly_chart(fig_cost, width="stretch")


def show_dashboard(service, product_service):
    """Renderiza página inicial de insights com visão consolidada."""
    del service  # Dashboard usa pipeline de vendas + serviço de custos.

    inject_roboto_font()
    st.header("📊 Dashboard")
    st.caption("Página inicial de insights: faturamento, custos e lucratividade.")
    render_separator()

    sales_df = load_sales_data_cached()
    if sales_df is None or sales_df.empty:
        st.warning("⚠️ Não foi possível carregar dados de vendas para o dashboard.")
        return

    with st.container(border=True):
        st.subheader("Visão High-Level")
        kpis = compute_high_level_kpis(sales_df)
        _render_high_level_kpis(kpis)

    st.markdown("\n")

    _render_visual_section(sales_df, product_service)
