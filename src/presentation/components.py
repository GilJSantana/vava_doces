"""Componentes e utilitários de renderização Streamlit."""

import pandas as pd
import streamlit as st
from pandas.io.formats.style import Styler


def render_separator() -> None:
    """Renderiza separador visual padrão."""
    st.markdown("---")


def render_wrapped_dataframe(
    df: pd.DataFrame | Styler,
    column_config: dict | None = None,
) -> None:
    """Renderiza dataframe em wrapper visual padronizado."""
    st.markdown('<div class="dataframe-wrapper">', unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True, hide_index=True, column_config=column_config)
    st.markdown('</div>', unsafe_allow_html=True)


def build_product_label(row: pd.Series, id_col: str, name_col: str) -> str:
    """Monta label padrão para exibição de produto."""
    return f"{row[id_col]} - {row[name_col]}"


def build_product_labels(df: pd.DataFrame, id_col: str, name_col: str) -> pd.Series:
    """Monta labels de produto de forma vetorizada para melhor performance."""
    return (
        df[id_col].fillna("").astype(str).str.strip()
        + " - "
        + df[name_col].fillna("").astype(str).str.strip()
    )


def render_metric_card(col, title: str, value: str, caption: str | None = None) -> None:
    """Renderiza card de métrica com estilo padrão."""
    with col:
        st.markdown(
            f"<div class='metric-card'><div class='card-title'>{title}</div><div class='card-value'>{value}</div></div>",
            unsafe_allow_html=True,
        )
        if caption:
            st.caption(caption)


def render_app_header(
    title: str = "🍰 Vava Doces - Análise de Produtos e Vendas",
    subtitle: str = "_Ferramenta de análise de produtos, custos e vendas_",
    logo_path: str = "assets/logo.png",
) -> None:
    """Renderiza cabeçalho principal com logotipo, título e subtítulo."""
    st.markdown('<div class="header">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        try:
            st.markdown('<div class="vava-logo-wrapper">', unsafe_allow_html=True)
            st.image(logo_path, width=150)
            st.markdown('</div>', unsafe_allow_html=True)
        except Exception:
            st.markdown('<div class="vava-logo-wrapper">', unsafe_allow_html=True)
            st.markdown(
                '<div style="width:150px;height:150px;border-radius:999px;background:#C9A23A;display:inline-block"></div>',
                unsafe_allow_html=True,
            )
            st.markdown('</div>', unsafe_allow_html=True)

    st.title(title)
    st.markdown(subtitle)
    st.markdown('</div>', unsafe_allow_html=True)

