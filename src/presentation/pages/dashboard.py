"""Página de dashboard geral."""

import logging

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.presentation.components import (
    build_product_labels,
    render_metric_card,
    render_separator,
    render_wrapped_dataframe,
)
from src.presentation.formatters import format_currency


logger = logging.getLogger(__name__)


def _to_numeric_currency_series(series: pd.Series) -> pd.Series:
    """Normaliza strings monetárias para float antes de cálculos de métricas."""
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


def build_top_products_by_cost(custo_resumo: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    """Retorna uma visão enxuta do Top N produtos por custo."""
    if custo_resumo is None or custo_resumo.empty:
        return pd.DataFrame()

    top_df = custo_resumo.copy()
    top_df["Custo Numérico"] = _to_numeric_currency_series(top_df["Custo Total (R$)"])
    top_df = top_df[top_df["Custo Numérico"].notna() & (top_df["Custo Numérico"] > 0)]
    if top_df.empty:
        return pd.DataFrame()

    top_df["Produto"] = build_product_labels(top_df, "ID do Produto", "Produto")
    top_df = top_df.sort_values("Custo Numérico", ascending=False).head(top_n)
    top_df["Custo Total (R$)"] = top_df["Custo Numérico"].apply(format_currency)
    return top_df[["Produto", "Custo Total (R$)", "Qtd Ingredientes"]]


def show_dashboard(service, product_service):
    """Renderiza dashboard principal com resumo de custos."""
    st.header("📊 Dashboard")
    render_separator()

    try:
        produtos_df = product_service.get_registered_products()
        custo_resumo = product_service.get_product_cost_summary()

        if custo_resumo is None or custo_resumo.empty:
            st.warning("⚠️ Nenhum dado de produtos disponível")
            return

        if produtos_df is None or produtos_df.empty or "ID do Produto" not in produtos_df.columns:
            total_produtos = 0
            raw_rows = 0
            filtered_rows = 0
        else:
            raw_rows = len(produtos_df)
            filtered_raw_df = produtos_df.copy()
            filtered_raw_df["ID do Produto"] = (
                filtered_raw_df["ID do Produto"].astype(str).str.strip().replace("", pd.NA)
            )
            filtered_raw_df = filtered_raw_df[filtered_raw_df["ID do Produto"].notna()]
            filtered_rows = len(filtered_raw_df)
            total_produtos = filtered_raw_df["ID do Produto"].nunique()

        aggregated_rows = len(custo_resumo)
        logger.info(
            "Dashboard pipeline sizes | Raw=%s | Filtered=%s | Aggregated=%s",
            raw_rows,
            filtered_rows,
            aggregated_rows,
        )

        col1, col2, col3, col4 = st.columns(4)

        numeric_costs = _to_numeric_currency_series(custo_resumo["Custo Total (R$)"])
        valid_costs = numeric_costs[(numeric_costs.notna()) & (numeric_costs > 0)]

        custo_total = numeric_costs.fillna(0.0).sum()
        custo_medio = valid_costs.mean() if not valid_costs.empty else 0
        custo_minimo = valid_costs.min() if not valid_costs.empty else 0

        render_metric_card(
            col1,
            "🛍️ Total de Produtos",
            f"{total_produtos}",
            caption="Total de SKUs cadastrados no Google Sheets",
        )
        render_metric_card(col2, "💸 Custo de Produção Total", format_currency(custo_total))
        render_metric_card(col3, "📊 Custo de Produção Médio", format_currency(custo_medio))
        render_metric_card(col4, "🔽 Custo de Produção Mínimo", format_currency(custo_minimo))

        render_separator()

        chart_col, = st.columns([1])
        with chart_col:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.subheader("💰 Custo de Produção por Produto")
            chart_data = custo_resumo.copy()
            chart_data["Custo Numérico"] = _to_numeric_currency_series(chart_data["Custo Total (R$)"])
            chart_data = chart_data[chart_data["Custo Numérico"].notna() & (chart_data["Custo Numérico"] > 0)]
            chart_data["Produto Label"] = build_product_labels(chart_data, "ID do Produto", "Produto")
            if chart_data.empty:
                st.info("ℹ️ Ainda não há produtos com custo válido para exibir no gráfico.")
            else:
                chart_data["Produto Nome"] = (
                    chart_data["Produto Label"].astype(str).str.split(" - ", n=1).str[-1].str.strip()
                )
                chart_data["len_nome"] = chart_data["Produto Nome"].str.len()
                chart_data = chart_data.sort_values(["len_nome", "Produto Nome"], ascending=[True, True])

                palette = [
                    "#636EFA",
                    "#EF553B",
                    "#00CC96",
                    "#AB63FA",
                    "#FFA15A",
                    "#19D3F3",
                    "#FF6692",
                    "#B6E880",
                    "#FF97FF",
                    "#FECB52",
                ]
                bar_colors = [palette[i % len(palette)] for i in range(len(chart_data))]
                y_labels = chart_data["Produto Nome"].tolist()
                max_name_len = int(chart_data["len_nome"].max()) if not chart_data.empty else 0
                left_margin = min(max(240, max_name_len * 8), 480)

                fig = go.Figure(
                    data=[
                        go.Bar(
                            x=chart_data["Custo Numérico"],
                            y=y_labels,
                            orientation="h",
                            marker={
                                "color": bar_colors,
                                "cornerradius": 18,
                                "line": {"width": 0},
                            },
                            hovertemplate="Produto: %{y}<br>Custo: R$ %{x:.2f}<extra></extra>",
                        )
                    ]
                )
                fig.update_layout(
                    template="plotly_white",
                    paper_bgcolor="#f0f0f0",
                    plot_bgcolor="#f0f0f0",
                    margin={"l": left_margin, "r": 24, "t": 16, "b": 20},
                    showlegend=False,
                    hovermode="x unified",
                )
                fig.update_xaxes(
                    title_text="Custo (R$)",
                    title_font={"color": "#2d2d2d", "size": 12},
                    tickfont={"size": 11, "color": "#2d2d2d"},
                    automargin=True,
                    showgrid=True,
                    gridcolor="#ededed",
                    gridwidth=1,
                    showline=False,
                    zeroline=False,
                )
                fig.update_yaxes(
                    title_text="",
                    title_font={"color": "#2d2d2d", "size": 12},
                    tickfont={"size": 11, "color": "#2d2d2d", "family": "Arial Black, Arial, sans-serif"},
                    ticklabelposition="outside",
                    automargin=True,
                    showgrid=False,
                    showline=False,
                    zeroline=False,
                    categoryorder="array",
                    categoryarray=y_labels,
                    autorange="reversed",
                )
                st.plotly_chart(fig, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        render_separator()
        st.subheader("🏅 Top 5 Produtos por Custo")
        top_5_df = build_top_products_by_cost(custo_resumo, top_n=5)
        if top_5_df.empty:
            st.info("ℹ️ Ainda não há dados de custo para montar o Top 5.")
        else:
            render_wrapped_dataframe(top_5_df)

    except Exception as e:
        st.error(f"❌ Erro ao processar dashboard: {e}")

