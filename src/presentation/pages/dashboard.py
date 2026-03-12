"""Página de dashboard geral."""

import streamlit as st

from src.presentation.components import (
    build_product_labels,
    render_metric_card,
    render_separator,
    render_wrapped_dataframe,
)
from src.presentation.formatters import format_currency


def show_dashboard(service, product_service):
    """Renderiza dashboard principal com resumo de custos."""
    st.header("📊 Dashboard")
    render_separator()

    try:
        custo_resumo = product_service.get_product_cost_summary()

        if custo_resumo is None or custo_resumo.empty:
            st.warning("⚠️ Nenhum dado de produtos disponível")
            return

        col1, col2, col3, col4 = st.columns(4)

        total_produtos = len(custo_resumo)
        custo_total = custo_resumo["Custo Total (R$)"].sum()
        custo_medio = custo_resumo["Custo Total (R$)"].mean()
        custo_minimo = custo_resumo["Custo Total (R$)"].min()

        render_metric_card(col1, "🛍️ Total de Produtos", f"{total_produtos}")
        render_metric_card(col2, "💸 Custo de Produção Total", format_currency(custo_total))
        render_metric_card(col3, "📊 Custo de Produção Médio", format_currency(custo_medio))
        render_metric_card(col4, "🔽 Custo de Produção Mínimo", format_currency(custo_minimo))

        render_separator()

        st.subheader("💰 Custo de Produção por Produto")
        chart_data = custo_resumo.copy()
        chart_data["Produto Label"] = build_product_labels(chart_data, "ID do Produto", "Produto")
        st.bar_chart(chart_data.set_index("Produto Label")["Custo Total (R$)"])

        st.subheader("📋 Detalhamento do Custo de Produção")
        display_df = custo_resumo.copy()
        display_df["Produto"] = build_product_labels(display_df, "ID do Produto", "Produto")
        display_df = display_df.drop(columns=["ID do Produto"])
        display_df["Custo Total (R$)"] = display_df["Custo Total (R$)"].apply(format_currency)
        display_df = display_df.rename(columns={"Custo Total (R$)": "Custo de Produção (R$)"})
        render_wrapped_dataframe(display_df)

    except Exception as e:
        st.error(f"❌ Erro ao processar dashboard: {e}")

