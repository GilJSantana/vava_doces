"""Navegação e controles de sidebar da aplicação Streamlit."""

from collections.abc import Callable

import streamlit as st


PAGE_DASHBOARD = "📊 Dashboard"
PAGE_PRODUCTION_COSTS = "💰 Custos de Produção"
PAGE_REVENUE_IMPACT = "💹 Impacto no Faturamento"
PAGE_DETAILED_ANALYSIS = "🔍 Análise Detalhada"
PAGE_FATURAMENTO = "💹 Faturamento (Auditoria)"

PAGE_OPTIONS = [
    PAGE_DASHBOARD,
    PAGE_PRODUCTION_COSTS,
    PAGE_REVENUE_IMPACT,
    PAGE_FATURAMENTO,
    PAGE_DETAILED_ANALYSIS,
]


def _format_medallion_info(medallion_state: dict[str, object] | None) -> str:
    if not medallion_state:
        return "Medallion: sem métricas disponíveis"

    bronze_rows = int(medallion_state.get("bronze_rows", 0) or 0)
    silver_rows = int(medallion_state.get("silver_rows", 0) or 0)
    quarantine_rows = int(medallion_state.get("quarantine_rows", 0) or 0)
    return (
        "Medallion Pipeline\n"
        f"Bronze (Total): {bronze_rows:,}\n"
        f"Silver (Deduped): {silver_rows:,}\n"
        f"Quarantine (NaT): {quarantine_rows:,}"
    )


def render_sidebar(
    get_adapter_fn: Callable[[], object | None],
    medallion_state: dict[str, object] | None = None,
) -> tuple[object | None, str]:
    """Renderiza sidebar, inicializa conexão e retorna adaptador e página selecionada."""
    with st.sidebar:
        st.markdown(
            "<div style='padding:0.5rem 0; color:#F6F1E6'><h3>⚙️ Configuração</h3></div>",
            unsafe_allow_html=True,
        )

        if st.button("🔄 Atualizar dados", width="stretch"):
            # Clear both resource and data caches so updated parquet/raw data is visible.
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()

        st.info(_format_medallion_info(medallion_state))

        adapter = get_adapter_fn()
        if adapter:
            st.success("✅ Conectado ao Google Sheets")
        else:
            st.error("❌ Desconectado - Configure as credenciais")
            return None, ""

        page = st.radio("Selecione uma página:", options=PAGE_OPTIONS)

    return adapter, page

