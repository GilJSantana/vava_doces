"""Navegação e controles de sidebar da aplicação Streamlit."""

from collections.abc import Callable

import streamlit as st


PAGE_DASHBOARD = "📊 Dashboard"
PAGE_PRODUCTION_COSTS = "💰 Custos de Produção"
PAGE_REVENUE_IMPACT = "💹 Impacto no Faturamento"   # kept as constant for backward-compat; not in menu
PAGE_DETAILED_ANALYSIS = "🔍 Análise Detalhada"      # kept as constant for backward-compat; not in menu
PAGE_FATURAMENTO = "💹 Faturamento (Auditoria)"

# Core navigation: three executive-facing pages only.
PAGE_OPTIONS = [
    PAGE_DASHBOARD,
    PAGE_PRODUCTION_COSTS,
    PAGE_FATURAMENTO,
]


def render_sidebar(
    get_adapter_fn: Callable[[], object | None],
    medallion_state: dict[str, object] | None = None,  # accepted but no longer displayed
) -> tuple[object | None, str]:
    """Renderiza sidebar, inicializa conexão e retorna adaptador e página selecionada."""
    with st.sidebar:
        st.markdown(
            "<div style='padding:1rem 0 0.25rem; color:#F6F1E6'><h3>🍰 Vavá Doces</h3></div>",
            unsafe_allow_html=True,
        )

        if st.button("🔄 Atualizar dados", use_container_width=True):
            # Clear both resource and data caches so updated parquet/raw data is visible.
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()

        st.markdown("<div style='margin-top:0.5rem'></div>", unsafe_allow_html=True)

        adapter = get_adapter_fn()
        if adapter:
            st.success("✅ Conectado ao Google Sheets")
        else:
            st.warning("⚠️ Google Sheets desconectado")

        st.markdown("<div style='margin-top:0.75rem'></div>", unsafe_allow_html=True)
        page = st.radio("Navegação", options=PAGE_OPTIONS, label_visibility="collapsed")

    return adapter, page

