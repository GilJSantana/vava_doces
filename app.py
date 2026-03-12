"""
Aplicação Streamlit para análise de produtos e vendas da Vava Doces.

Esta aplicação oferece interface interativa para:
- Visualizar dados do cadastro de produtos (aba Produtos)
- Visualizar dados de vendas diárias
- Calcular custo total por produto
- Análises de margens e rentabilidade
"""

import os
from typing import Callable

import streamlit as st
from dotenv import load_dotenv

from src.domain.product_analysis_service import ProductAnalysisService
from src.application import build_analysis_services
from src.infrastructure.google_sheets_adapter import GoogleSheetsAdapter
from src.presentation.components import render_app_header
from src.presentation.controller import run_app_controller
from src.presentation.navigation import (
    PAGE_DASHBOARD,
    PAGE_DETAILED_ANALYSIS,
    PAGE_PRODUCTION_COSTS,
    PAGE_REVENUE_IMPACT,
    render_sidebar as render_navigation_sidebar,
)
from src.presentation.pages import (
    show_analise_detalhada,
    show_dashboard,
    show_production_costs,
    show_revenue_impact,
)
from src.presentation.theme import apply_global_styles

# Carregar variáveis de ambiente
load_dotenv()

# Configuração da página
_favicon_path = "assets/favicon.png" if os.path.exists("assets/favicon.png") else None
_favicon_bytes = None
if _favicon_path:
    try:
        with open(_favicon_path, "rb") as _f:
            _favicon_bytes = _f.read()
    except Exception:
        _favicon_bytes = None

st.set_page_config(
    page_title="Vava Doces - Análise de Produtos e Vendas",
    page_icon=_favicon_bytes or "🍰",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_styles()

PAGE_HANDLERS: dict[str, Callable] = {
    PAGE_DASHBOARD: lambda _service, _product_service: show_dashboard(_service, _product_service),
    PAGE_PRODUCTION_COSTS: lambda _service, _product_service: show_production_costs(_product_service),
    PAGE_REVENUE_IMPACT: lambda _service, _product_service: show_revenue_impact(_product_service),
    PAGE_DETAILED_ANALYSIS: lambda _service, _product_service: show_analise_detalhada(_service, _product_service),
}


@st.cache_resource
def get_adapter():
    """Cria instância do adaptador Google Sheets com cache."""
    try:
        credential_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        sheet_id = os.getenv("GOOGLE_SHEET_ID")

        adapter = GoogleSheetsAdapter(
            credential_file=credential_file,
            sheet_id=sheet_id,
        )
        return adapter
    except Exception as e:
        st.error(f"❌ Erro ao conectar com Google Sheets: {e}")
        return None


@st.cache_resource
def get_product_service(_adapter):
    """Cria instância do serviço de análise de produtos."""
    if _adapter is None:
        return None
    return ProductAnalysisService(data_source=_adapter)


def get_services(adapter: GoogleSheetsAdapter):
    """Inicializa serviços de domínio."""
    return build_analysis_services(
        adapter=adapter,
        product_service_factory=get_product_service,
    )


def render_selected_page(page: str, service, product_service):
    """Despacha renderização da página selecionada."""
    handler = PAGE_HANDLERS.get(page)
    if handler is None:
        st.error("❌ Página inválida selecionada")
        return
    handler(service, product_service)


def main():
    """Executa a aplicação Streamlit."""
    run_app_controller(
        render_header_fn=render_app_header,
        render_sidebar_fn=lambda: render_navigation_sidebar(get_adapter),
        init_services_fn=get_services,
        render_page_fn=render_selected_page,
    )


if __name__ == "__main__":
    main()

