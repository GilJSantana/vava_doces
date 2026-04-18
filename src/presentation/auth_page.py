"""Componentes de Autenticação para Streamlit.

Fornece:
- Página de login com Google OAuth2
- Página de acesso negado
- Display de status de autenticação
"""

from __future__ import annotations

import logging

import streamlit as st

from src.infrastructure.google_oauth2_adapter import (
    GoogleDrivePermissionChecker,
    GoogleOAuth2Adapter,
    clear_auth_session,
    is_user_authenticated,
    set_user_authenticated,
)

logger = logging.getLogger(__name__)


def render_login_page(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> None:
    """Renderiza a página de login OAuth2.

    Args:
        client_id: ID de Cliente OAuth2 (pré-sanitizado)
        client_secret: Segredo de Cliente OAuth2 (pré-sanitizado)
        redirect_uri: URI de Redirecionamento OAuth2 (pré-sanitizado)
    """
    # Defesa dupla: garantir limpeza de credenciais
    client_id = str(client_id).strip()
    client_secret = str(client_secret).strip()
    redirect_uri = str(redirect_uri).strip()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<div style='text-align: center; padding: 2rem 0;'></div>", unsafe_allow_html=True)

        # Logo/Título
        st.markdown(
            "<h1 style='text-align: center; color: #FF6B9D;'>🍰 Vavá Doces</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align: center; color: #666;'>Sistema de Análise de Vendas e Custos</p>",
            unsafe_allow_html=True,
        )

        st.markdown("<div style='padding: 1rem;'></div>", unsafe_allow_html=True)

        # Seção de login
        st.markdown(
            "<h3 style='text-align: center; color: #333;'>🔐 Acesso Restrito</h3>",
            unsafe_allow_html=True,
        )

        st.info(
            "Para acessar o sistema, você precisa estar autenticado com sua conta Google "
            "e ter permissão nos arquivos de origem do Google Drive."
        )

        # Verificar código de autorização na URL
        query_params = st.query_params
        if "code" in query_params:
            code = query_params["code"]
            oauth2 = GoogleOAuth2Adapter(client_id, client_secret, redirect_uri)

            with st.spinner("🔄 Autenticando com Google..."):
                token_response = oauth2.exchange_code_for_token(code)
                if token_response and "access_token" in token_response:
                    access_token = token_response["access_token"]
                    user_email = oauth2.get_user_email_from_token(access_token)

                    if user_email:
                        set_user_authenticated(user_email, access_token)
                        st.success(f"✅ Autenticado como: {user_email}")
                        st.info("🔍 Verificando permissões do Google Drive...")
                        st.rerun()
                    else:
                        clear_auth_session()
                        st.query_params.clear()
                        st.error("❌ Não foi possível obter seu email. Tente novamente.")
                        logger.warning("OAuth2 token exchange succeeded but email extraction failed")
                else:
                    clear_auth_session()
                    st.query_params.clear()
                    st.error("❌ Falha na autenticação OAuth2. Tente novamente.")
                    logger.warning("OAuth2 token exchange failed")
        else:
            # Botão de login
            oauth2 = GoogleOAuth2Adapter(client_id, client_secret, redirect_uri)
            login_url = oauth2.get_login_url()

            st.markdown("<div style='padding: 1rem;'></div>", unsafe_allow_html=True)

            st.markdown(
                f"""
                <div style='text-align: center; padding: 1rem;'>
                    <a href="{login_url}" target="_self" style='
                        display: inline-block;
                        padding: 0.75rem 2rem;
                        background-color: #4285F4;
                        color: white;
                        text-decoration: none;
                        border-radius: 4px;
                        font-weight: bold;
                        font-size: 1rem;
                    '>
                        🔐 Entrar com Google
                    </a>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_access_denied_page(user_email: str) -> None:
    """Renderiza página de acesso negado.

    Args:
        user_email: Email do usuário
    """
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<div style='text-align: center; padding: 2rem 0;'></div>", unsafe_allow_html=True)

        st.markdown(
            "<h1 style='text-align: center; color: #FF6B9D;'>🍰 Vavá Doces</h1>",
            unsafe_allow_html=True,
        )

        st.markdown("<div style='padding: 1rem;'></div>", unsafe_allow_html=True)

        st.markdown(
            "<h2 style='text-align: center; color: #D32F2F;'>🚫 Acesso Negado</h2>",
            unsafe_allow_html=True,
        )

        st.error(
            f"Acesso negado. Este e-mail não possui permissão no diretório de origem do Google Drive.\n\n"
            f"**Email:** {user_email}\n\n"
            f"**Ação Necessária:**\n"
            f"1. Solicite acesso ao administrador do sistema\n"
            f"2. Aguarde a adição de suas permissões no Google Drive\n"
            f"3. Clique no botão abaixo para tentar novamente"
        )

        st.markdown("<div style='padding: 1rem;'></div>", unsafe_allow_html=True)

        if st.button("🔄 Tentar Novamente", width="stretch"):
            clear_auth_session()
            st.query_params.clear()
            st.rerun()

        st.markdown("<div style='padding: 1rem;'></div>", unsafe_allow_html=True)

        if st.button("🔓 Sair da Conta", width="stretch"):
            clear_auth_session()
            st.query_params.clear()
            st.rerun()


def render_auth_status_badge() -> None:
    """Renderiza badge de status de autenticação na sidebar."""
    if is_user_authenticated():
        user_email = st.session_state.get("user_email")
        st.sidebar.success(f"✅ Autenticado: {user_email}")
    else:
        st.sidebar.warning("⚠️ Não autenticado")


def check_permissions_and_authorize(
    user_email: str,
    credential_file: str,
    file_or_folder_id: str,
    min_role: str = "reader",
) -> bool:
    """Verifica permissões do usuário no Google Drive.

    Args:
        user_email: Email do usuário para verificação
        credential_file: Caminho para arquivo de credenciais de Service Account
        file_or_folder_id: ID do arquivo/pasta no Google Drive
        min_role: Papel mínimo necessário (padrão: reader)

    Returns:
        True se autorizado, False caso contrário
    """
    try:
        if not user_email:
            logger.warning("Verificação de permissão ignorada: user_email vazio")
            return False

        logger.info("Iniciando verificação de permissões para %s no arquivo %s", user_email, file_or_folder_id)

        permission_checker = GoogleDrivePermissionChecker(credential_file)
        is_authorized = permission_checker.check_user_permission_on_file(
            file_id=file_or_folder_id,
            user_email=user_email,
            min_role=min_role,
        )

        if is_authorized:
            logger.info("✅ Usuário %s autorizado para acesso", user_email)
        else:
            logger.warning("❌ Usuário %s NÃO autorizado para acesso", user_email)

        return is_authorized

    except Exception as e:
        logger.error("Erro ao verificar permissões: %s", e)
        return False

