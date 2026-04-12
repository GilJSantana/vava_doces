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
from scripts.medallion_pipeline import MedallionPipeline

from src.domain.product_analysis_service import ProductAnalysisService
from src.domain.sales_analysis_service import sync_drive_files_to_raw_from_env
from src.application import build_analysis_services
from src.infrastructure.gold_adapter import GoldParquetAdapter
from src.infrastructure.google_sheets_adapter import GoogleSheetsAdapter
from src.presentation.components import render_app_header
from src.presentation.controller import run_app_controller
from src.presentation.navigation import (
    PAGE_DASHBOARD,
    PAGE_DETAILED_ANALYSIS,
    PAGE_PRODUCTION_COSTS,
    PAGE_FATURAMENTO,
    render_sidebar as render_navigation_sidebar,
)
from src.presentation.pages import (
    show_analise_detalhada,
    show_dashboard,
    show_production_costs,
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
    PAGE_FATURAMENTO: lambda _service, _product_service: show_faturamento(),
    PAGE_DETAILED_ANALYSIS: lambda _service, _product_service: show_analise_detalhada(_service, _product_service),
}


@st.cache_resource
def initialize_data_pipeline() -> dict[str, object]:
    """Executa bootstrap de ingestão RAW->SILVER->GOLD antes da renderização."""
    try:
        # Tentar sincronizar dados do Google Drive
        try:
            synced_files = sync_drive_files_to_raw_from_env()
            if synced_files > 0:
                print(f"✅ Sincronizados {synced_files} arquivo(s) do Google Drive")
        except Exception as sync_err:
            print(f"⚠️  Não foi possível sincronizar do Google Drive: {sync_err}")
            print("  Continuando com dados locais em data/raw/ (se disponível)")

        # Verificar se há dados em data/raw/
        raw_dir = Path(__file__).resolve().parent / "data" / "raw"
        raw_files = list(raw_dir.glob("*.csv")) + list(raw_dir.glob("*.xlsx"))

        if len(raw_files) == 0:
            # Se não há dados locais, usar modo demo
            print("⚠️  Nenhum arquivo encontrado em data/raw/")
            print("   Use: python -m src.domain.sales_analysis_service --download-demo")
            print("   Ou configure GOOGLE_APPLICATION_CREDENTIALS e DRIVE_FOLDER_ID no .env")
            os.environ["VAVA_SALES_SOURCE"] = "demo"
            return {
                "bronze_rows": 0,
                "silver_rows": 0,
                "gold_rows": 0,
                "mode": "demo",
                "message": "Modo demo: configure Google Drive ou adicione arquivos em data/raw/",
            }

        # Executar pipeline com dados locais
        result = MedallionPipeline().run()
        os.environ["VAVA_SALES_SOURCE"] = "gold"
        print(f"✅ Pipeline executado com sucesso: {result}")
        return result

    except Exception as e:
        print(f"❌ Erro ao executar pipeline: {e}")
        # Retornar modo seguro em vez de falhar
        os.environ["VAVA_SALES_SOURCE"] = "demo"
        return {
            "bronze_rows": 0,
            "silver_rows": 0,
            "gold_rows": 0,
            "mode": "demo",
            "error": str(e),
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
    return ProductAnalysisService(
        data_source=_adapter,
        gold_source=GoldParquetAdapter(),
    )


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
    medallion_state = initialize_data_pipeline()
    run_app_controller(
        render_header_fn=render_app_header,
        render_sidebar_fn=lambda: render_navigation_sidebar(get_adapter, medallion_state),
        init_services_fn=init_services,
        render_page_fn=render_selected_page,
    )


if __name__ == "__main__":
    main()

