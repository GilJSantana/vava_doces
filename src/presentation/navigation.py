"""Navegação e controles de sidebar da aplicação Streamlit."""

from collections.abc import Callable

import streamlit as st


PAGE_DASHBOARD = "📊 Dashboard"
PAGE_PRODUCTION_COSTS = "💰 Custos de Produção"
PAGE_REVENUE_IMPACT = "💹 Impacto no Faturamento"
PAGE_DETAILED_ANALYSIS = "🔍 Análise Detalhada"

PAGE_OPTIONS = [
    PAGE_DASHBOARD,
    PAGE_PRODUCTION_COSTS,
    PAGE_REVENUE_IMPACT,
    PAGE_DETAILED_ANALYSIS,
]


def render_sidebar(get_adapter_fn: Callable[[], object | None]) -> tuple[object | None, str]:
    """Renderiza sidebar, inicializa conexão e retorna adaptador e página selecionada."""
    with st.sidebar:
        st.markdown(
            "<div style='padding:0.5rem 0; color:#F6F1E6'><h3>⚙️ Configuração</h3></div>",
            unsafe_allow_html=True,
        )

        if st.button("🔄 Atualizar dados", use_container_width=True):
            st.cache_resource.clear()
            st.rerun()

        adapter = get_adapter_fn()
        if adapter:
            st.success("✅ Conectado ao Google Sheets")
        else:
            st.error("❌ Desconectado - Configure as credenciais")
            return None, ""

        page = st.radio("Selecione uma página:", options=PAGE_OPTIONS)

    return adapter, page

