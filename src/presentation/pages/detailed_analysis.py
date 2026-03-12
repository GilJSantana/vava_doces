"""Página de análise detalhada."""

import streamlit as st

from src.presentation.components import build_product_labels, render_separator
from src.presentation.formatters import format_currency


def show_analise_detalhada(service, product_service):
    """Renderiza análise detalhada de custos e relatórios."""
    st.header("🔍 Análise Detalhada")
    render_separator()

    try:
        tab1, tab2, tab3 = st.tabs(["Custos por Produto", "Margens", "Relatórios"])

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

                st.bar_chart(analise_df.set_index("Produto Label"))

                display_df = analise_df.copy()
                display_df["Custo Total (R$)"] = display_df["Custo Total (R$)"].apply(format_currency)
                display_df = display_df.rename(columns={"Custo Total (R$)": "Custo de Produção (R$)"})
                st.dataframe(display_df, use_container_width=True, hide_index=True)
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

