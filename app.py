"""Aplicação Streamlit da Vavá Doces com três páginas executivas.

O MVP em produção é composto por:
- Dashboard de rentabilidade
- Custos de produção
- Faturamento (auditoria)

Camada de Segurança:
- OAuth2 via Google (autenticação de identidade)
- Google Drive API (verificação de permissões via Service Account)
- Session state com gates de acesso antes de carregar dados
"""

import logging
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from time import perf_counter
from typing import Callable

import streamlit as st
from dotenv import load_dotenv

# Garante resolução de imports absolutos (ex.: src.*) em ambientes como Streamlit Cloud.
_APP_ROOT = os.path.dirname(os.path.abspath(__file__))
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)

from scripts.medallion_pipeline import MedallionPipeline

from src.infrastructure.drive_manager import get_drive_assets_map, load_parquet_from_drive
from src.infrastructure.google_oauth2_adapter import (
    init_session_state_auth,
    is_user_authenticated,
    is_user_authorized,
    set_user_authorized,
)
from src.infrastructure.google_sheets_adapter import GoogleSheetsAdapter
from src.presentation.auth_page import (
    check_permissions_and_authorize,
    render_access_denied_page,
    render_login_page,
)
from src.presentation.components import render_app_header
from src.presentation.controller import run_app_controller
from src.presentation.navigation import (
    PAGE_DASHBOARD,
    PAGE_FATURAMENTO,
    PAGE_PRODUCTION_COSTS,
    render_sidebar as render_navigation_sidebar,
)
from src.presentation.pages import (
    show_dashboard,
    show_faturamento,
    show_production_costs,
)
from src.presentation.theme import apply_global_styles

logger = logging.getLogger(__name__)

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
        drive_folder_id = (st.secrets.get("GOOGLE_DRIVE_FOLDER_ID", "") or "").strip()
        if drive_folder_id:
            os.environ["DRIVE_FOLDER_ID"] = drive_folder_id

        t0 = perf_counter()
        t_pipeline = perf_counter()
        result = MedallionPipeline().run()
        print(f"[perf] medallion_run_ms={(perf_counter() - t_pipeline) * 1000:.2f}")
        print(f"[perf] initialize_data_pipeline_ms={(perf_counter() - t0) * 1000:.2f}")
        # Global cache invalidation after successful pipeline execution.
        get_drive_assets_map.clear()
        load_parquet_from_drive.clear()
        st.cache_data.clear()
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
        sheet_id = os.getenv("GOOGLE_SHEET_ID") or st.secrets.get("GOOGLE_SHEET_ID")

        adapter = GoogleSheetsAdapter(
            credential_file=None,  # Use Streamlit secrets via st.secrets, not env vars
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
    """Executa a aplicação Streamlit com autenticação e autorização obrigatórias."""

    # STEP 1: Inicializar estado de autenticação
    init_session_state_auth()
    logger.info("Iniciando aplicação Vavá Doces com camada de segurança")

    # STEP 2: Verificar autenticação OAuth2
    if not is_user_authenticated():
        try:
            oauth2_client_id = st.secrets.get("OAUTH2_CLIENT_ID", "").strip()
            oauth2_client_secret = st.secrets.get("OAUTH2_CLIENT_SECRET", "").strip()
            oauth2_redirect_uri = st.secrets.get("OAUTH2_REDIRECT_URI", "http://localhost:8501").strip()

            if not oauth2_client_id or not oauth2_client_secret:
                st.error(
                    "❌ **Erro de Configuração - OAuth2**\n\n"
                    "`OAUTH2_CLIENT_ID` e `OAUTH2_CLIENT_SECRET` não foram configurados.\n\n"
                    "Por favor, adicione em `.streamlit/secrets.toml`"
                )
                logger.error("OAuth2 credentials missing in st.secrets")
                return

            if not oauth2_redirect_uri:
                oauth2_redirect_uri = "http://localhost:8501"
                logger.debug("Using default redirect_uri: http://localhost:8501")

            logger.info("OAuth2 credentials loaded from secrets")
            render_login_page(
                client_id=oauth2_client_id,
                client_secret=oauth2_client_secret,
                redirect_uri=oauth2_redirect_uri,
            )
        except Exception as e:
            st.error(f"❌ Erro ao carregar configuração de autenticação: {e}")
            logger.exception("Error loading OAuth2 configuration")
        return

    # STEP 3: Verificar autorização via Drive se autenticado mas não autorizado
    if not is_user_authorized():
        try:
            user_email = st.session_state.get("user_email")
            drive_source_folder_id = st.secrets.get("GOOGLE_DRIVE_FOLDER_ID", "").strip()

            if not user_email:
                st.error("❌ Identidade do usuário não foi validada. Tente fazer login novamente.")
                logger.error("user_email missing after OAuth2 authentication")
                return

            if not drive_source_folder_id:
                st.error(
                    "❌ **Erro de Configuração - Google Drive**\n\n"
                    "`GOOGLE_DRIVE_FOLDER_ID` não foi configurado.\n\n"
                    "Por favor, adicione em `.streamlit/secrets.toml`"
                )
                logger.error("Drive configuration missing in st.secrets")
                return

            gcp_service_account_info = st.secrets.get("gcp_service_account")
            if not isinstance(gcp_service_account_info, Mapping) or not gcp_service_account_info:
                st.error(
                    "❌ **Erro de Configuração - Service Account**\n\n"
                    "`[gcp_service_account]` não foi configurado corretamente em `.streamlit/secrets.toml`."
                )
                logger.error("Missing or invalid gcp_service_account in st.secrets: %s", type(gcp_service_account_info))
                return

            # Verificar permissões com spinner
            with st.spinner("🔍 Verificando permissões no Google Drive..."):
                logger.info("Initiating Drive permission check for %s on folder %s", user_email, drive_source_folder_id)
                is_authorized = check_permissions_and_authorize(
                    user_email=user_email,
                    credential_file=None,  # Use Streamlit secrets exclusively
                    file_or_folder_id=drive_source_folder_id,
                    min_role="reader",
                )

            set_user_authorized(is_authorized)

            if not is_authorized:
                logger.warning("Authorization failed for user %s", user_email)
                render_access_denied_page(user_email)
                return

            st.success("✅ Autorização do Google Drive concedida!")
            logger.info("Drive Authorization Successful")
            st.rerun()

        except FileNotFoundError as e:
            st.error(
                f"❌ Erro ao verificar credenciais: {e}\n\n"
                "As credenciais de Service Account devem estar configuradas em `.streamlit/secrets.toml` sob `[gcp_service_account]`"
            )
            logger.error("Service account credentials not found: %s", e)
            return
        except Exception as e:
            st.error(f"❌ Erro ao verificar permissões do Google Drive: {e}")
            logger.exception("Error checking Drive permissions")
            return

    # STEP 4: Usuário autenticado E autorizado — carregar aplicação principal
    logger.info("User %s fully authenticated and authorized", st.session_state.get("user_email"))

    if "pipeline_state" not in st.session_state:
        st.session_state["pipeline_state"] = initialize_data_pipeline()

    run_app_controller(
        render_header_fn=render_app_header,
        render_sidebar_fn=lambda: render_navigation_sidebar(get_adapter),
        render_page_fn=render_selected_page,
    )


if __name__ == "__main__":
    main()

