"""
Aplicação Streamlit para análise de custos e faturamento da Vava Doces.

Esta aplicação oferece interface interativa para:
- Visualizar dados de custos de produção
- Visualizar dados de faturamento
- Calcular custo por receita
- Análises de margens e rentabilidade
"""

import streamlit as st
import pandas as pd
from decimal import Decimal
import os
from dotenv import load_dotenv
import base64
import mimetypes

from src.infrastructure.google_sheets_adapter import GoogleSheetsAdapter
from src.domain.cost_analysis_service import CostAnalysisService
from src.ports.data_source import DataSourceError

# Carregar variáveis de ambiente
load_dotenv()

# Configuração da página
# Se houver favicon em assets, carregue os bytes para usar como page_icon
_favicon_path = "assets/favicon.png" if os.path.exists("assets/favicon.png") else None
_favicon_bytes = None
if _favicon_path:
    try:
        with open(_favicon_path, 'rb') as _f:
            _favicon_bytes = _f.read()
    except Exception:
        _favicon_bytes = None

st.set_page_config(
    page_title="Vava Doces - Análise de Custos",
    page_icon=_favicon_bytes or "🍰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS customizados para identidade visual (verde + dourado)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&display=swap');
    :root{
        --vava-green-dark: #0F3B2E;
        --vava-green: #145D44;
        --vava-gold: #C9A23A;
        --vava-cream: #F6F1E6;
    }
    html, body, [data-testid='stAppViewContainer'] {
        background: linear-gradient(180deg, var(--vava-green-dark) 0%, #0B2E25 100%);
        color: var(--vava-cream);
        font-family: 'Playfair Display', Georgia, 'Times New Roman', serif;
    }
    .header {
        text-align: center;
        padding: 1.2rem 0 0.25rem 0;
    }
    .vava-logo-wrapper {
        display:flex;align-items:center;justify-content:center;margin-bottom:0.6rem;
    }
    .vava-logo {
        border-radius: 999px;
        border: 4px solid var(--vava-gold);
        box-shadow: 0 6px 18px rgba(0,0,0,0.4);
    }
    /* estilizar imagens geradas por st.image */
    .stImage img { border-radius: 999px !important; border:4px solid var(--vava-gold) !important; box-shadow: 0 6px 18px rgba(0,0,0,0.4) !important; }
    .metric-card {
        background: linear-gradient(180deg, rgba(201,162,58,0.09), rgba(255,255,255,0.02));
        padding: 0.9rem 1rem;
        border-radius: 14px;
        margin: 0.4rem 0;
        border: 1px solid rgba(201,162,58,0.14);
        color: var(--vava-cream);
    }
    .metric-card .card-title { font-size:0.95rem; opacity:0.9; }
    .metric-card .card-value { font-size:1.25rem; font-weight:700; color: var(--vava-cream); }
    .stButton>button {
        background: linear-gradient(90deg, var(--vava-gold), #E6C46B) !important;
        color: #0b2e25 !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
    }
    .stDownloadButton>button { padding: 0.45rem 0.8rem !important; }
    .dataframe-wrapper { border-radius:12px; overflow:hidden; border:1px solid rgba(255,255,255,0.03); }
    .dataframe thead tr th { background: rgba(20,93,68,0.6) !important; }
    .streamlit-expanderHeader { color: var(--vava-cream) !important; }
</style>
""", unsafe_allow_html=True)

# =====================================================================
# INICIALIZAÇÃO E CACHE
# =====================================================================

@st.cache_resource
def get_adapter():
    """Cria instância do adaptador Google Sheets com cache."""
    try:
        credential_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        sheet_id = os.getenv("GOOGLE_SHEET_ID")

        adapter = GoogleSheetsAdapter(
            credential_file=credential_file,
            sheet_id=sheet_id
        )
        return adapter
    except Exception as e:
        st.error(f"❌ Erro ao conectar com Google Sheets: {e}")
        return None


def get_service(adapter):
    """Cria instância do serviço de análise de custos."""
    if adapter is None:
        return None
    return CostAnalysisService(data_source=adapter)


# =====================================================================
# FUNÇÕES AUXILIARES
# =====================================================================

def format_currency(value):
    """Formata um valor em moeda brasileira."""
    if isinstance(value, Decimal):
        return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def load_data(service, sheet_name):
    """Carrega dados de uma planilha específica."""
    try:
        return service.get_production_costs() if sheet_name == "Custos" else service.get_sales_data()
    except DataSourceError as e:
        st.error(f"❌ Erro ao carregar dados de '{sheet_name}': {e}")
        return None
    except Exception as e:
        st.error(f"❌ Erro inesperado: {e}")
        return None


# =====================================================================
# PÁGINA PRINCIPAL
# =====================================================================

def main():
    # Header
    st.markdown('<div class="header">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # logo: preferir assets/logo.jpg se existir, senão usar logo.png
        logo_path = "assets/logo.jpg" if os.path.exists("assets/logo.jpg") else "assets/logo.png"
        # Use st.image para renderizar (mais confiável em Streamlit)
        try:
            st.markdown('<div class="vava-logo-wrapper">', unsafe_allow_html=True)
            st.image(logo_path, width=150)
            st.markdown('</div>', unsafe_allow_html=True)
        except Exception:
            st.markdown('<div class="vava-logo-wrapper">', unsafe_allow_html=True)
            st.markdown('<div style="width:150px;height:150px;border-radius:999px;background:#C9A23A;display:inline-block"></div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
    st.title("🍰 Vava Doces - Análise de Custos e Faturamento")
    st.markdown("_Ferramenta de análise de custos de produção e faturamento_")
    st.markdown('</div>', unsafe_allow_html=True)

    # Sidebar - Configuração
    with st.sidebar:
        st.markdown(f"<div style='padding:0.5rem 0; color:{'#F6F1E6'}'><h3>⚙️ Configuração</h3></div>", unsafe_allow_html=True)

        # Status de conexão
        adapter = get_adapter()
        if adapter:
            st.success("✅ Conectado ao Google Sheets")
        else:
            st.error("❌ Desconectado - Configure as credenciais")
            st.stop()

        # Menu de navegação
        page = st.radio(
            "Selecione uma página:",
            options=["📊 Dashboard", "💰 Custos", "📈 Faturamento", "🔍 Análise Detalhada"]
        )

    # Inicializar serviço
    service = get_service(adapter)
    if service is None:
        st.error("❌ Falha ao inicializar serviço de análise")
        st.stop()

    # Renderizar página selecionada
    if page == "📊 Dashboard":
        show_dashboard(service)
    elif page == "💰 Custos":
        show_custos(service)
    elif page == "📈 Faturamento":
        show_faturamento(service)
    elif page == "🔍 Análise Detalhada":
        show_analise_detalhada(service)


# =====================================================================
# PÁGINA: DASHBOARD
# =====================================================================

def show_dashboard(service):
    st.header("📊 Dashboard")
    st.markdown("---")

    try:
        # Carregar dados
        custos_df = service.get_production_costs()
        faturamento_df = service.get_sales_data()

        if custos_df is None or custos_df.empty:
            st.warning("⚠️ Nenhum dado de custos disponível")
            return

        # Calcular custo total por receita
        custo_por_receita = service.calculate_cost_per_recipe("Custos")

        # Métricas principais
        col1, col2, col3, col4 = st.columns(4)

        # Preparar valores
        total_receitas = len(custo_por_receita)
        custo_total = sum(custo_por_receita.values()) if custo_por_receita else Decimal(0)
        custo_medio = (custo_total / len(custo_por_receita)) if custo_por_receita else Decimal(0)
        custo_minimo = min(custo_por_receita.values()) if custo_por_receita else Decimal(0)

        # Renderizar cards métricos com HTML para controle visual
        def render_metric(col, title, value):
            with col:
                st.markdown(f"<div class='metric-card'><div class='card-title'>{title}</div><div class='card-value'>{value}</div></div>", unsafe_allow_html=True)

        render_metric(col1, '📝 Total de Receitas', f"{total_receitas}")
        render_metric(col2, '💸 Custo Total', format_currency(custo_total))
        render_metric(col3, '📊 Custo Médio', format_currency(custo_medio))
        render_metric(col4, '🔽 Custo Mínimo', format_currency(custo_minimo))

        st.markdown("---")

        # Gráfico de custos por receita
        if custo_por_receita:
            st.subheader("💰 Custo por Receita")

            # Converter para DataFrame para visualização
            custo_df = pd.DataFrame(
                [(k, float(v)) for k, v in custo_por_receita.items()],
                columns=["Receita", "Custo (R$)"]
            ).sort_values("Custo (R$)", ascending=False)

            st.bar_chart(custo_df.set_index("Receita"))

            # Tabela com detalhes
            st.subheader("📋 Detalhamento de Custos")
            display_df = custo_df.copy()
            display_df["Custo (R$)"] = display_df["Custo (R$)"].apply(
                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            st.markdown('<div class="dataframe-wrapper">', unsafe_allow_html=True)
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            st.markdown('</div>', unsafe_allow_html=True)

    except Exception as e:
        st.error(f"❌ Erro ao processar dashboard: {e}")


# =====================================================================
# PÁGINA: CUSTOS
# =====================================================================

def show_custos(service):
    st.header("💰 Dados de Custos")
    st.markdown("---")

    try:
        df = service.get_production_costs()

        if df is None or df.empty:
            st.warning("⚠️ Nenhum dado de custos disponível")
            return

        # Filtros
        col1, col2 = st.columns(2)

        with col1:
            if "recipe" in [c.lower() for c in df.columns]:
                recipes = df[[c for c in df.columns if c.lower() == "recipe"][0]].unique()
                selected_recipe = st.multiselect(
                    "Filtrar por receita:",
                    options=recipes,
                    default=recipes[:5] if len(recipes) > 5 else recipes
                )

        # Exibir dados
        st.subheader("📊 Tabela de Custos")

        if "selected_recipe" in locals() and selected_recipe:
            recipe_col = [c for c in df.columns if c.lower() == "recipe"][0]
            filtered_df = df[df[recipe_col].isin(selected_recipe)]
        else:
            filtered_df = df

        st.dataframe(filtered_df, use_container_width=True)

        # Opções de download
        st.markdown("---")
        st.subheader("📥 Downloads")

        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label="📥 Baixar como CSV",
            data=csv,
            file_name="custos.csv",
            mime="text/csv"
        )

    except Exception as e:
        st.error(f"❌ Erro ao exibir custos: {e}")


# =====================================================================
# PÁGINA: FATURAMENTO
# =====================================================================

def show_faturamento(service):
    st.header("📈 Dados de Faturamento")
    st.markdown("---")

    try:
        df = service.get_sales_data()

        if df is None or df.empty:
            st.warning("⚠️ Nenhum dado de faturamento disponível")
            return

        # Exibir dados
        st.subheader("📊 Tabela de Faturamento")
        st.dataframe(df, use_container_width=True)

        # Estatísticas
        st.markdown("---")
        st.subheader("📊 Estatísticas")

        numeric_cols = df.select_dtypes(include=['number']).columns
        if len(numeric_cols) > 0:
            col1, col2, col3 = st.columns(3)

            with col1:
                for col in numeric_cols:
                    st.metric(f"Total - {col}", f"{df[col].sum():,.2f}")
                    break

            with col2:
                for col in numeric_cols:
                    st.metric(f"Média - {col}", f"{df[col].mean():,.2f}")
                    break

            with col3:
                for col in numeric_cols:
                    st.metric(f"Máximo - {col}", f"{df[col].max():,.2f}")
                    break

        # Opções de download
        st.markdown("---")
        st.subheader("📥 Downloads")

        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Baixar como CSV",
            data=csv,
            file_name="faturamento.csv",
            mime="text/csv"
        )

    except Exception as e:
        st.error(f"❌ Erro ao exibir faturamento: {e}")


# =====================================================================
# PÁGINA: ANÁLISE DETALHADA
# =====================================================================

def show_analise_detalhada(service):
    st.header("🔍 Análise Detalhada")
    st.markdown("---")

    try:
        # Tabs para diferentes análises
        tab1, tab2, tab3 = st.tabs(["Custos por Receita", "Margens", "Relatórios"])

        with tab1:
            st.subheader("Custo Total por Receita")

            custo_por_receita = service.calculate_cost_per_recipe("Custos")

            if custo_por_receita:
                # Criar DataFrame
                analise_df = pd.DataFrame(
                    [(k, float(v)) for k, v in sorted(custo_por_receita.items(), key=lambda x: x[1], reverse=True)],
                    columns=["Receita", "Custo Total (R$)"]
                )

                # Métricas
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Total de Receitas", len(analise_df))

                with col2:
                    total = analise_df["Custo Total (R$)"].sum()
                    st.metric("Custo Total", format_currency(total))

                with col3:
                    media = analise_df["Custo Total (R$)"].mean()
                    st.metric("Custo Médio", format_currency(media))

                # Gráfico
                st.bar_chart(analise_df.set_index("Receita"))

                # Tabela
                display_df = analise_df.copy()
                display_df["Custo Total (R$)"] = display_df["Custo Total (R$)"].apply(
                    lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                )
                st.dataframe(display_df, use_container_width=True, hide_index=True)
            else:
                st.info("ℹ️ Nenhum dado disponível para análise")

        with tab2:
            st.subheader("Análise de Margens")
            st.info("ℹ️ Esta funcionalidade será implementada após integração de dados de faturamento com custos")

        with tab3:
            st.subheader("Relatórios")
            st.info("ℹ️ Relatórios personalizados em desenvolvimento")

    except Exception as e:
        st.error(f"❌ Erro ao processar análise: {e}")


# =====================================================================
# EXECUÇÃO
# =====================================================================

if __name__ == "__main__":
    main()

