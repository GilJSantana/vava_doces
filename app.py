"""
Aplicação Streamlit para análise de produtos e vendas da Vava Doces.

Esta aplicação oferece interface interativa para:
- Visualizar dados do cadastro de produtos (aba Produtos)
- Visualizar dados de vendas diárias
- Calcular custo total por produto
- Análises de margens e rentabilidade
"""

import os
from pathlib import Path
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
    PAGE_FATURAMENTO,
    render_sidebar as render_navigation_sidebar,
)
from src.presentation.pages import (
    show_analise_detalhada,
    show_dashboard,
    show_production_costs,
    show_revenue_impact,
    show_faturamento,
)
from src.presentation.theme import apply_global_styles

# Carregar variáveis de ambiente
load_dotenv()

# Configuração da página
_PROJECT_ROOT = Path(__file__).resolve().parent
_favicon_path = _PROJECT_ROOT / "assets" / "favicon.png"
_page_icon = str(_favicon_path) if _favicon_path.exists() else "🍰"

st.set_page_config(
    page_title="Vava Doces - Análise de Produtos e Vendas",
    page_icon=_page_icon,
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_styles()

PAGE_HANDLERS: dict[str, Callable] = {
    PAGE_DASHBOARD: lambda _service, _product_service: show_dashboard(_service, _product_service),
    PAGE_PRODUCTION_COSTS: lambda _service, _product_service: show_production_costs(_product_service),
    PAGE_REVENUE_IMPACT: lambda _service, _product_service: show_revenue_impact(_product_service),
    PAGE_FATURAMENTO: lambda _service, _product_service: show_faturamento(),
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


def get_services(adapter: object) -> tuple[object | None, object | None]:
    """Inicializa serviços de domínio."""
    return build_analysis_services(
        adapter=adapter,
        product_service_factory=get_product_service,
    )


def init_services(adapter: object) -> tuple[object | None, object | None]:
    """Wrapper tipado para o controlador principal."""
    return get_services(adapter)


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
        init_services_fn=init_services,
        render_page_fn=render_selected_page,
    )


if __name__ == "__main__":
    main()

