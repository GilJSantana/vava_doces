"""Página de análise detalhada."""

import plotly.graph_objects as go
import streamlit as st

from src.presentation.chart_style import apply_clean_xy_axes, apply_minimal_figure_style, build_color_map, colors_for_labels
from src.presentation.components import build_product_labels, render_separator
from src.presentation.formatters import format_currency


def show_analise_detalhada(service, product_service):
    """Renderiza análise detalhada de custos e relatórios."""
    st.header("🔍 Análise Detalhada")
    render_separator()

    try:
        tab1, tab2, tab3 = st.tabs(["Custo de Produção por Produto", "Margens", "Relatórios"])

        with tab1:
            st.subheader("Custo de Produção por Produto")

            custo_resumo = product_service.get_product_cost_summary()
            if custo_resumo is not None and not custo_resumo.empty:
                analise_df = custo_resumo[["ID do Produto", "Produto", "Custo Total (R$)"]].copy()
                analise_df["Produto Label"] = build_product_labels(analise_df, "ID do Produto", "Produto")
                analise_df = analise_df[["Produto Label", "Custo Total (R$)"]].sort_values(
                    "Custo Total (R$)",
                    ascending=False,
                )

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Total de Produtos", len(analise_df))

                with col2:
                    total = analise_df["Custo Total (R$)"].sum()
                    st.metric("Custo de Produção Total", format_currency(total))

                with col3:
                    media = analise_df["Custo Total (R$)"].mean()
                    st.metric("Custo de Produção Médio", format_currency(media))

                plot_df = analise_df.copy()
                color_map = build_color_map(plot_df["Produto Label"].tolist())
                fig = go.Figure(
                    data=[
                        go.Bar(
                            x=plot_df["Custo Total (R$)"],
                            y=plot_df["Produto Label"],
                            orientation="h",
                            marker={"color": colors_for_labels(plot_df["Produto Label"], color_map), "line": {"width": 0}},
                            hovertemplate="Produto: %{y}<br>Custo: R$ %{x:.2f}<extra></extra>",
                        )
                    ]
                )
                apply_minimal_figure_style(fig, showlegend=False, hovermode="y unified")
                apply_clean_xy_axes(fig, x_title="Custo de Produção (R$)", x_tickprefix="R$ ", y_title="")
                fig.update_layout(margin={"l": 240, "r": 24, "t": 16, "b": 20})
                st.plotly_chart(fig, width="stretch")

                display_df = analise_df.copy()
                display_df["Custo Total (R$)"] = display_df["Custo Total (R$)"].apply(format_currency)
                display_df = display_df.rename(columns={"Custo Total (R$)": "Custo de Produção (R$)"})
                st.dataframe(display_df, width="stretch", hide_index=True)
            else:
                st.info("ℹ️ Nenhum dado disponível para análise")

        with tab2:
            st.subheader("Análise de Margens")
            st.info("ℹ️ Esta funcionalidade será implementada após integração de vendas com custos")

        with tab3:
            st.subheader("Relatórios")
            st.info("ℹ️ Relatórios personalizados em desenvolvimento")

    except Exception as e:
        st.error(f"❌ Erro ao processar análise: {e}")

