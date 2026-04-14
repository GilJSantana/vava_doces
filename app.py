"""Aplicação Streamlit da Vavá Doces com três páginas executivas.

O MVP em produção é composto por:
- Dashboard de rentabilidade
- Custos de produção
- Faturamento (auditoria)
"""

import os
from pathlib import Path
from time import perf_counter
from typing import Callable

import streamlit as st
from dotenv import load_dotenv
from scripts.medallion_pipeline import MedallionPipeline

from src.domain.sales_analysis_service import sync_drive_files_to_raw_from_env
from src.infrastructure.google_sheets_adapter import GoogleSheetsAdapter
from src.presentation.components import render_app_header
from src.presentation.controller import run_app_controller
from src.presentation.navigation import (
    PAGE_DASHBOARD,
    PAGE_PRODUCTION_COSTS,
    PAGE_FATURAMENTO,
    render_sidebar as render_navigation_sidebar,
)
from src.presentation.pages import (
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
    PAGE_DASHBOARD: show_dashboard,
    PAGE_PRODUCTION_COSTS: show_production_costs,
    PAGE_FATURAMENTO: show_faturamento,
}


@st.cache_resource
def initialize_data_pipeline() -> dict[str, object]:
    """Executa bootstrap de ingestão RAW->SILVER->GOLD antes da renderização."""
    try:
        t0 = perf_counter()
        # Tentar sincronizar dados do Google Drive
        try:
            t_sync = perf_counter()
            synced_files = sync_drive_files_to_raw_from_env()
            print(f"[perf] bronze_sync_ms={(perf_counter() - t_sync) * 1000:.2f}")
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
        t_pipeline = perf_counter()
        result = MedallionPipeline().run()
        print(f"[perf] medallion_run_ms={(perf_counter() - t_pipeline) * 1000:.2f}")
        print(f"[perf] initialize_data_pipeline_ms={(perf_counter() - t0) * 1000:.2f}")
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


def render_selected_page(
    page: str,
    service: object | None = None,
    product_service: object | None = None,
) -> None:
    """Despacha renderização da página selecionada.

    Compatível com handlers legado (sem args) e novo (service, product_service).
    """
    handler = PAGE_HANDLERS.get(page)
    if handler is None:
        st.error("❌ Página inválida selecionada")
        return
    try:
        handler(service, product_service)
    except TypeError:
        handler()


def main():
    """Executa a aplicação Streamlit."""
    if "pipeline_state" not in st.session_state:
        st.session_state["pipeline_state"] = initialize_data_pipeline()
    run_app_controller(
        render_header_fn=render_app_header,
        render_sidebar_fn=lambda: render_navigation_sidebar(get_adapter),
        render_page_fn=render_selected_page,
    )


if __name__ == "__main__":
    main()

