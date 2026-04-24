"""Componentes de Autenticação para Streamlit.

Fornece:
- Página de login com Google OAuth2
- Página de acesso negado
- Display de status de autenticação
"""

from __future__ import annotations

import base64
from html import escape
import logging
from pathlib import Path

import streamlit as st

from src.infrastructure.google_oauth2_adapter import (
    GoogleDrivePermissionChecker,
    GoogleOAuth2Adapter,
    clear_auth_session,
    is_user_authenticated,
    set_user_authenticated,
)

logger = logging.getLogger(__name__)

AUTH_PAGE_CSS = """
<style>
section[data-testid="stAppViewContainer"] {
    background: linear-gradient(180deg, #0d3b2f 0%, #0a2f25 100%);
}

.auth-wrapper {
    max-width: 620px;
    margin: 7vh auto 1.5rem auto;
    text-align: center;
}

.brand-title {
    margin: 0.65rem 0 0 0;
    color: #ffffff;
    font-size: 1.7rem;
    font-weight: 700;
    letter-spacing: 0.01em;
}

.brand-subtitle {
    margin: 0.35rem 0 1.1rem 0;
    color: #d6e4de;
    font-size: 0.95rem;
    text-align: center;
    padding: 1rem;
}

.auth-note {
    margin: 0 auto;
    max-width: 540px;
    color: #e9f3ef;
    font-size: 0.93rem;
    line-height: 1.4;
    margin-bottom: 1rem;
    text-align: center;
}

.auth-logo {
    width: 250px;
    height: 250px;
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid rgba(255, 255, 255, 0.35);
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.24);
}

.auth-emoji-logo {
    font-size: 2.8rem;
}

.auth-divider {
    width: 100%;
    max-width: 560px;
    margin: 0.8rem auto 0.6rem auto;
    border-top: 1px solid rgba(214, 228, 222, 0.28);
}

.auth-footer {
    margin-top: 0.2rem;
    padding-top: 0.7rem;
    text-align: center;
    color: #d6e4de;
    font-size: 0.82rem;
}

.auth-footer a {
    color: #f0f7f4;
    text-decoration: none;
}

.auth-footer a:hover {
    text-decoration: underline;
}

.denied-title {
    margin: 0.4rem 0 0.6rem 0;
    color: #ffd2ce;
    font-size: 1.18rem;
}

.denied-note {
    margin: 0 auto 0.9rem auto;
    max-width: 540px;
    padding: 0.2rem 0.1rem;
    color: #ffe4e1;
    font-size: 0.9rem;
    line-height: 1.4;
}
</style>
"""


def _render_auth_brand() -> None:
    """Renderiza logo da marca; usa imagem local quando disponível."""
    logo_path = Path(__file__).resolve().parents[2] / "assets" / "logo.png"
    if logo_path.exists():
        logo_bytes = logo_path.read_bytes()
        logo_b64 = base64.b64encode(logo_bytes).decode("ascii")
        st.markdown(
            (
                "<div style='text-align:center;'>"
                f"<img src='data:image/png;base64,{logo_b64}' alt='Vavá Doces logo' class='auth-logo'>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
    else:
        st.markdown("<div class='auth-emoji-logo'>🍰</div>", unsafe_allow_html=True)


def _render_auth_footer() -> None:
    st.markdown(
        """
        <div class="auth-divider"></div>
        <div class="auth-footer">
            Vavá Doces - Controle de Vendas © 2026
            &nbsp;|&nbsp;
            Suporte Técnico:
            <a href="mailto:gilmar.jesus@gmail.com" target="_self">gilmar.jesus@gmail.com</a>
        </div>
        """,
        unsafe_allow_html=True,
    )


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

    st.markdown(AUTH_PAGE_CSS, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.7, 1])
    with col2:
        st.markdown("<div class='auth-wrapper'>", unsafe_allow_html=True)

        _render_auth_brand()
        st.markdown("<p class='brand-title'></p>", unsafe_allow_html=True)
        st.markdown("<p class='brand-subtitle'>Sistema de análise de vendas e custos</p>", unsafe_allow_html=True)
        st.markdown(
            """
            <div class="auth-note">
                Para acessar o sistema, autentique-se com sua conta Google e aguarde
                a validação automática das permissões no Google Drive.
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Verificar código de autorização na URL
        query_params = st.query_params
        if "code" in query_params:
            code = query_params["code"]
            oauth2 = GoogleOAuth2Adapter(client_id, client_secret, redirect_uri)

            with st.spinner("Autenticando com Google..."):
                token_response = oauth2.exchange_code_for_token(code)
                if token_response and "access_token" in token_response:
                    access_token = token_response["access_token"]
                    user_email = oauth2.get_user_email_from_token(access_token)

                    if user_email:
                        set_user_authenticated(user_email, access_token)
                        st.success(f"Autenticado como: {user_email}")
                        st.info("Verificando permissões do Google Drive...")
                        st.rerun()
                    else:
                        clear_auth_session()
                        st.query_params.clear()
                        st.error("Não foi possível obter seu e-mail. Tente novamente.")
                        logger.warning("OAuth2 token exchange succeeded but email extraction failed")
                else:
                    clear_auth_session()
                    st.query_params.clear()
                    st.error("Falha na autenticação OAuth2. Tente novamente.")
                    logger.warning("OAuth2 token exchange failed")
        else:
            # Use componente nativo para navegação OAuth2 em ambiente sandboxed.
            # Não aplicar html.escape() na URL para preservar query string intacta.
            oauth2 = GoogleOAuth2Adapter(client_id, client_secret, redirect_uri)
            login_url = oauth2.get_login_url()
            col_btn_left, col_btn_center, col_btn_right = st.columns([1, 1.6, 1])
            with col_btn_center:
                st.link_button(
                    "Entrar com Google",
                    login_url,
                    type="primary",
                    use_container_width=True,
                )

        _render_auth_footer()
        st.markdown("</div>", unsafe_allow_html=True)


def render_access_denied_page(user_email: str) -> None:
    """Renderiza página de acesso negado.

    Args:
        user_email: Email do usuário
    """
    st.markdown(AUTH_PAGE_CSS, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.7, 1])
    with col2:
        st.markdown("<div class='auth-wrapper'>", unsafe_allow_html=True)

        _render_auth_brand()
        st.markdown("<p class='brand-title'>Vavá Doces</p>", unsafe_allow_html=True)
        st.markdown("<p class='brand-subtitle'>Sistema de análise de vendas e custos</p>", unsafe_allow_html=True)
        st.markdown("<h3 class='denied-title'>Acesso Negado</h3>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="denied-note">
                Este e-mail não possui permissão no diretório de origem do Google Drive.<br><br>
                <strong>E-mail:</strong> {escape(user_email)}<br><br>
                <strong>Ação necessária:</strong><br>
                1. Solicite acesso ao administrador do sistema<br>
                2. Aguarde a atualização das permissões no Google Drive<br>
                3. Clique em <em>Tentar novamente</em>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("Tentar novamente", width="stretch"):
            clear_auth_session()
            st.query_params.clear()
            st.rerun()

        if st.button("Sair da conta", width="stretch"):
            clear_auth_session()
            st.query_params.clear()
            st.rerun()

        _render_auth_footer()
        st.markdown("</div>", unsafe_allow_html=True)


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



