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

from src.infrastructure.google_sheets_adapter import GoogleSheetsAdapter
from src.domain.cost_analysis_service import CostAnalysisService
from src.ports.data_source import DataSourceError

# Carregar variáveis de ambiente
load_dotenv()

# Configuração da página
st.set_page_config(
    page_title="Vava Doces - Análise de Custos",
    page_icon="🍰",
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


def load_data_from_sheet(adapter, sheet_name):
    """Carrega dados de uma planilha específica."""
    try:
        return adapter.get_data(sheet_name)
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
        # logo: usar assets/logo.png
        logo_path = "assets/logo.png"
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
            options=[
                "📊 Dashboard",
                "📦 Cadastro de Produtos",
                "🥘 Matéria Prima",
                "💳 Vendas Diárias",
                "📈 Resumo Diário",
                "📊 Análise por Categoria",
                "🔍 Análise Detalhada"
            ]
        )

    # Inicializar serviço
    service = get_service(adapter)
    if service is None:
        st.error("❌ Falha ao inicializar serviço de análise")
        st.stop()

    # Renderizar página selecionada
    if page == "📊 Dashboard":
        show_dashboard(service, adapter)
    elif page == "📦 Cadastro de Produtos":
        show_produtos(adapter)
    elif page == "🥘 Matéria Prima":
        show_materia_prima(adapter)
    elif page == "💳 Vendas Diárias":
        show_vendas_diarias(adapter)
    elif page == "📈 Resumo Diário":
        show_resumo_diario(adapter)
    elif page == "📊 Análise por Categoria":
        show_analise_categoria(adapter)
    elif page == "🔍 Análise Detalhada":
        show_analise_detalhada(service)


# =====================================================================
# PÁGINA: DASHBOARD
# =====================================================================

def show_dashboard(service, adapter):
    st.header("📊 Dashboard")
    st.markdown("---")

    try:
        # Carregar dados
        produtos_df = load_data_from_sheet(adapter, "Cadastro Produtos")
        vendas_df = load_data_from_sheet(adapter, "Vendas Diárias")
        resumo_df = load_data_from_sheet(adapter, "Resumo Diário")

        if produtos_df is None or produtos_df.empty:
            st.warning("⚠️ Nenhum dado disponível")
            return

        # Métricas principais
        col1, col2, col3, col4 = st.columns(4)

        # Renderizar cards métricos
        def render_metric(col, title, value):
            with col:
                st.markdown(f"<div class='metric-card'><div class='card-title'>{title}</div><div class='card-value'>{value}</div></div>", unsafe_allow_html=True)

        total_produtos = len(produtos_df) if produtos_df is not None else 0
        total_vendas = len(vendas_df) if vendas_df is not None else 0

        # Tentar calcular totais de vendas se existirem colunas numéricas
        total_valor_vendas = "R$ 0,00"
        if vendas_df is not None and not vendas_df.empty:
            numeric_cols = vendas_df.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                total_valor_vendas = format_currency(vendas_df[numeric_cols[0]].sum())

        render_metric(col1, '📦 Total de Produtos', f"{total_produtos}")
        render_metric(col2, '💳 Total de Vendas', f"{total_vendas}")
        render_metric(col3, '💰 Valor Total Vendas', total_valor_vendas)
        render_metric(col4, '📊 Categorias', f"{len(produtos_df['Categoria'].unique()) if 'Categoria' in produtos_df.columns else 0}")

        st.markdown("---")

        # Gráficos
        st.subheader("📈 Produtos por Categoria")

        if "Categoria" in produtos_df.columns:
            categoria_count = produtos_df['Categoria'].value_counts()
            st.bar_chart(categoria_count)

        st.markdown("---")

        # Tabelas com resumo
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📋 Últimos Produtos Cadastrados")
            if produtos_df is not None and not produtos_df.empty:
                display_df = produtos_df.tail(5).copy()
                st.dataframe(display_df, use_container_width=True)
            else:
                st.info("Nenhum dado disponível")

        with col2:
            st.subheader("💳 Últimas Vendas")
            if vendas_df is not None and not vendas_df.empty:
                display_df = vendas_df.tail(5).copy()
                st.dataframe(display_df, use_container_width=True)
            else:
                st.info("Nenhum dado disponível")


    except Exception as e:
        st.error(f"❌ Erro ao processar dashboard: {e}")
# =====================================================================
# PÁGINA: CADASTRO DE PRODUTOS
# =====================================================================

def show_produtos(adapter):
    st.header("📦 Cadastro de Produtos")
    st.markdown("---")

    try:
        df = load_data_from_sheet(adapter, "Cadastro Produtos")

        if df is None or df.empty:
            st.warning("⚠️ Nenhum produto cadastrado")
            return

        # Estatísticas
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("📦 Total de Produtos", len(df))

        with col2:
            if "Categoria" in df.columns:
                st.metric("📊 Categorias", df["Categoria"].nunique())

        with col3:
            if "Preço" in df.columns or "preco" in [c.lower() for c in df.columns]:
                price_col = [c for c in df.columns if c.lower() == "preco" or c.lower() == "preço"][0] if any(c.lower() in ["preco", "preço"] for c in df.columns) else None
                if price_col:
                    st.metric("💰 Preço Médio", format_currency(df[price_col].mean()))

        st.markdown("---")

        # Filtros
        col1, col2 = st.columns(2)

        selected_category = None
        if "Categoria" in df.columns:
            with col1:
                categories = df["Categoria"].unique()
                selected_category = st.multiselect(
                    "Filtrar por categoria:",
                    options=categories,
                    default=categories if len(categories) <= 5 else list(categories[:5])
                )

        # Aplicar filtro
        if selected_category:
            df_filtered = df[df["Categoria"].isin(selected_category)]
        else:
            df_filtered = df

        # Exibir tabela
        st.subheader("📋 Lista de Produtos")
        st.dataframe(df_filtered, use_container_width=True)

        # Download
        st.markdown("---")
        st.subheader("📥 Download")
        csv = df_filtered.to_csv(index=False)
        st.download_button(
            label="📥 Baixar como CSV",
            data=csv,
            file_name="produtos.csv",
            mime="text/csv"
        )

    except Exception as e:
        st.error(f"❌ Erro ao exibir produtos: {e}")


# =====================================================================
# PÁGINA: MATÉRIA PRIMA
# =====================================================================

def show_materia_prima(adapter):
    st.header("🥘 Matéria Prima")
    st.markdown("---")

    try:
        df = load_data_from_sheet(adapter, "Matéria Prima")

        if df is None or df.empty:
            st.warning("⚠️ Nenhum dado de matéria prima disponível")
            return

        # Estatísticas
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("🥘 Total de Itens", len(df))

        with col2:
            if "Unidade" in df.columns:
                st.metric("📏 Unidades", df["Unidade"].nunique())

        with col3:
            if "Preço" in df.columns or "preco" in [c.lower() for c in df.columns]:
                price_col = [c for c in df.columns if c.lower() == "preco" or c.lower() == "preço"][0] if any(c.lower() in ["preco", "preço"] for c in df.columns) else None
                if price_col:
                    st.metric("💰 Preço Médio", format_currency(df[price_col].mean()))

        st.markdown("---")

        # Exibir tabela
        st.subheader("📋 Tabela de Matéria Prima")
        st.dataframe(df, use_container_width=True)

        # Download
        st.markdown("---")
        st.subheader("📥 Download")
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Baixar como CSV",
            data=csv,
            file_name="materia_prima.csv",
            mime="text/csv"
        )

    except Exception as e:
        st.error(f"❌ Erro ao exibir matéria prima: {e}")


# =====================================================================
# PÁGINA: VENDAS DIÁRIAS
# =====================================================================

def show_vendas_diarias(adapter):
    st.header("💳 Vendas Diárias")
    st.markdown("---")

    try:
        df = load_data_from_sheet(adapter, "Vendas Diárias")

        if df is None or df.empty:
            st.warning("⚠️ Nenhum dado de vendas disponível")
            return

        # Estatísticas
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("💳 Total de Vendas", len(df))

        with col2:
            # Tentar encontrar coluna de valor
            numeric_cols = df.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                st.metric("💰 Valor Total", format_currency(df[numeric_cols[0]].sum()))

        with col3:
            if len(numeric_cols) > 0:
                st.metric("📊 Valor Médio", format_currency(df[numeric_cols[0]].mean()))

        st.markdown("---")

        # Gráfico de vendas
        if len(numeric_cols) > 0:
            st.subheader("📈 Gráfico de Vendas")
            # Tentar agrupar por data se existir coluna de data
            st.line_chart(df[numeric_cols[0]])

        st.markdown("---")

        # Exibir tabela
        st.subheader("📋 Tabela de Vendas Diárias")
        st.dataframe(df, use_container_width=True)

        # Download
        st.markdown("---")
        st.subheader("📥 Download")
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Baixar como CSV",
            data=csv,
            file_name="vendas_diarias.csv",
            mime="text/csv"
        )

    except Exception as e:
        st.error(f"❌ Erro ao exibir vendas diárias: {e}")


# =====================================================================
# PÁGINA: RESUMO DIÁRIO
# =====================================================================

def show_resumo_diario(adapter):
    st.header("📈 Resumo Diário")
    st.markdown("---")

    try:
        df = load_data_from_sheet(adapter, "Resumo Diário")

        if df is None or df.empty:
            st.warning("⚠️ Nenhum dado de resumo disponível")
            return

        # Exibir tabela
        st.subheader("📊 Resumo Diário")
        st.dataframe(df, use_container_width=True)

        # Download
        st.markdown("---")
        st.subheader("📥 Download")
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Baixar como CSV",
            data=csv,
            file_name="resumo_diario.csv",
            mime="text/csv"
        )

    except Exception as e:
        st.error(f"❌ Erro ao exibir resumo diário: {e}")


# =====================================================================
# PÁGINA: ANÁLISE POR CATEGORIA
# =====================================================================

def show_analise_categoria(adapter):
    st.header("📊 Análise por Categoria")
    st.markdown("---")

    try:
        df = load_data_from_sheet(adapter, "Análise por Categoria")

        if df is None or df.empty:
            st.warning("⚠️ Nenhum dado de análise disponível")
            return

        # Exibir tabela
        st.subheader("📊 Análise por Categoria")
        st.dataframe(df, use_container_width=True)

        # Download
        st.markdown("---")
        st.subheader("📥 Download")
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Baixar como CSV",
            data=csv,
            file_name="analise_categoria.csv",
            mime="text/csv"
        )

    except Exception as e:
        st.error(f"❌ Erro ao exibir análise por categoria: {e}")


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

