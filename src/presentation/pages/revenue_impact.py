"""Página de impacto no faturamento."""

import pandas as pd
import streamlit as st

from src.presentation.components import build_product_labels, render_separator, render_wrapped_dataframe
from src.presentation.formatters import format_currency


def show_revenue_impact(product_service):
    """Renderiza análise de impacto no faturamento."""
    st.header("💹 Impacto no Faturamento")
    render_separator()

    try:
        produtos_df = product_service.get_products_with_sales_impact()

        if produtos_df is None or produtos_df.empty:
            st.warning("⚠️ Nenhum dado de produtos disponível")
            st.info("ℹ️ Certifique-se de que a aba 'Produtos' possui dados válidos")
            return

        produtos_df = produtos_df[
            produtos_df["ID do Produto"].notna()
            & (produtos_df["ID do Produto"].astype(str).str.strip() != "")
            & produtos_df["Nome do Produto"].notna()
            & (produtos_df["Nome do Produto"].astype(str).str.strip() != "")
        ].copy()

        if produtos_df.empty:
            st.warning("⚠️ Nenhum produto válido encontrado")
            return

        st.subheader("📊 Análise de Impacto por Produto")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total de Produtos", len(produtos_df))

        with col2:
            receita_total = produtos_df["Preço"].dropna().sum() if "Preço" in produtos_df.columns else 0
            st.metric("Receita Potencial Total", format_currency(receita_total))

        with col3:
            if "Margem (%)" in produtos_df.columns and produtos_df["Margem (%)"].notna().any():
                margem_media = produtos_df["Margem (%)"].dropna().mean()
                st.metric("Margem Média (%)", f"{margem_media:.1f}%")
            else:
                st.metric("Margem Média (%)", "N/A")

        with col4:
            if "Categoria" in produtos_df.columns and produtos_df["Categoria"].notna().any():
                categorias = produtos_df["Categoria"].nunique()
                st.metric("Categorias", categorias)
            else:
                st.metric("Categorias", 0)

        render_separator()
        st.subheader("💰 Ranking de Impacto no Faturamento")

        display_df = produtos_df.copy()
        display_df["Produto"] = build_product_labels(display_df, "ID do Produto", "Nome do Produto")

        for col in ["Preço", "Custo Total (R$)", "Margem Bruta (R$)"]:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(
                    lambda x: format_currency(x) if pd.notna(x) else "N/A"
                )

        if "Margem (%)" in display_df.columns:
            display_df["Margem"] = display_df["Margem (%)"].apply(
                lambda x: f"{x:.1f}%" if pd.notna(x) else "N/A"
            )

        cols_to_show = ["Produto"]
        for col in ["Categoria", "Preço", "Custo Total (R$)", "Margem", "Margem Bruta (R$)", "Ativo"]:
            if col in display_df.columns:
                cols_to_show.append(col)

        render_wrapped_dataframe(display_df[cols_to_show])

        render_separator()
        st.subheader("📈 Visualizações")

        col1, col2 = st.columns(2)

        with col1:
            if "Categoria" in produtos_df.columns and produtos_df["Categoria"].notna().any():
                st.write("**Produtos por Categoria**")
                categoria_count = produtos_df["Categoria"].value_counts()
                st.bar_chart(categoria_count)

        with col2:
            if "Margem (%)" in produtos_df.columns and produtos_df["Margem (%)"].notna().any():
                st.write("**Distribuição de Margens**")
                margem_data = produtos_df[["Nome do Produto", "Margem (%)"]].dropna().copy()
                if not margem_data.empty:
                    margem_data.columns = ["Produto", "Margem"]
                    st.bar_chart(margem_data.set_index("Produto"))

        render_separator()
        st.subheader("📥 Download")

        csv = produtos_df.to_csv(index=False)
        st.download_button(
            label="📥 Baixar Dados como CSV",
            data=csv,
            file_name="impacto_faturamento.csv",
            mime="text/csv",
        )

    except Exception as e:
        st.error(f"❌ Erro ao processar análise de faturamento: {e}")

