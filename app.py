"""
Aplicação Streamlit para análise de produtos e vendas da Vava Doces.

Esta aplicação oferece interface interativa para:
- Visualizar dados do cadastro de produtos (aba Produtos)
- Visualizar dados de vendas diárias
- Calcular custo total por produto
- Análises de margens e rentabilidade
"""

import streamlit as st
import pandas as pd
from decimal import Decimal
import os
from dotenv import load_dotenv

from src.infrastructure.google_sheets_adapter import GoogleSheetsAdapter
from src.domain.cost_analysis_service import CostAnalysisService
from src.domain.product_analysis_service import ProductAnalysisService
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
    page_title="Vava Doces - Análise de Produtos e Vendas",
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


@st.cache_resource
def get_product_service(_adapter):
    """Cria instância do serviço de análise de produtos."""
    if _adapter is None:
        return None
    return ProductAnalysisService(data_source=_adapter)


# =====================================================================
# FUNÇÕES AUXILIARES
# =====================================================================

def format_currency(value):
    """Formata um valor em moeda brasileira."""
    if isinstance(value, Decimal):
        return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def parse_currency(value):
    """Converte string de moeda (ex: 'R$ 12,90') para float."""
    if isinstance(value, (int, float)):
        return float(value)
    if pd.isna(value) or value is None:
        return None
    try:
        # Converter string para número
        # Remove 'R$' e espaços
        clean = str(value).replace("R$", "").strip()
        # Substitui ponto por vazio (não é separador decimal em PT-BR)
        clean = clean.replace(".", "")
        # Substitui vírgula por ponto para conversão
        clean = clean.replace(",", ".")
        return float(clean)
    except (ValueError, AttributeError):
        return None


def load_data(service, sheet_name):
    """Carrega dados de uma planilha específica."""
    try:
        return service.get_products_data() if sheet_name == "Produtos" else service.get_sales_data()
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
    st.title("🍰 Vava Doces - Análise de Produtos e Vendas")
    st.markdown("_Ferramenta de análise de produtos, custos e vendas_")
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
                "💰 Custos de Produção",
                "💹 Impacto no Faturamento",
                "🔍 Análise Detalhada"
            ]
        )

    # Inicializar serviços
    service = get_service(adapter)
    product_service = get_product_service(adapter)
    if service is None or product_service is None:
        st.error("❌ Falha ao inicializar serviços de análise")
        st.stop()

    # Renderizar página selecionada
    if page == "📊 Dashboard":
        show_dashboard(service, product_service)
    elif page == "💰 Custos de Produção":
        show_production_costs(product_service)
    elif page == "💹 Impacto no Faturamento":
        show_revenue_impact(product_service)
    elif page == "🔍 Análise Detalhada":
        show_analise_detalhada(service, product_service)


# =====================================================================
# PÁGINA: DASHBOARD
# =====================================================================

def show_dashboard(service, product_service):
    st.header("📊 Dashboard")
    st.markdown("---")

    try:
        # Obter resumo de custos
        custo_resumo = product_service.get_product_cost_summary()
        produtos_df = product_service.get_products_with_sales_impact()

        if custo_resumo is None or custo_resumo.empty:
            st.warning("⚠️ Nenhum dado de produtos disponível")
            return

        # Métricas principais
        col1, col2, col3, col4 = st.columns(4)

        total_produtos = len(custo_resumo)
        custo_total = custo_resumo["Custo Total (R$)"].sum()
        custo_medio = custo_resumo["Custo Total (R$)"].mean()
        custo_minimo = custo_resumo["Custo Total (R$)"].min()

        def render_metric(col, title, value):
            with col:
                st.markdown(f"<div class='metric-card'><div class='card-title'>{title}</div><div class='card-value'>{value}</div></div>", unsafe_allow_html=True)

        render_metric(col1, '🛍️ Total de Produtos', f"{total_produtos}")
        render_metric(col2, '💸 Custo Total', format_currency(custo_total))
        render_metric(col3, '📊 Custo Médio', format_currency(custo_medio))
        render_metric(col4, '🔽 Custo Mínimo', format_currency(custo_minimo))

        st.markdown("---")

        # Gráfico de custos por produto
        if len(custo_resumo) > 0:
            st.subheader("💰 Custo de Produção por Produto")

            # Preparar dados para gráfico
            chart_data = custo_resumo.copy()
            chart_data.columns = ["Produto", "Custo", "Qtd Ing"]

            # Gráfico de barras horizontais (melhor para muitos produtos)
            st.bar_chart(chart_data.set_index("Produto")["Custo"])

            # Tabela com detalhes
            st.subheader("📋 Detalhamento de Custos")
            display_df = custo_resumo.copy()
            display_df["Custo Total (R$)"] = display_df["Custo Total (R$)"].apply(
                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            st.markdown('<div class="dataframe-wrapper">', unsafe_allow_html=True)
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            st.markdown('</div>', unsafe_allow_html=True)

    except Exception as e:
        st.error(f"❌ Erro ao processar dashboard: {e}")


# =====================================================================
# PÁGINA: CUSTOS DE PRODUÇÃO
# =====================================================================

def show_production_costs(product_service):
    st.header("💰 Custos de Produção")
    st.markdown("---")

    try:
        # Obter resumo de custos
        custo_resumo = product_service.get_product_cost_summary()

        if custo_resumo is None or custo_resumo.empty:
            st.warning("⚠️ Nenhum dado de produtos disponível")
            return

        # Seletor de produto
        col1, col2 = st.columns(2)
        with col1:
            produtos = custo_resumo["Produto"].tolist()
            selected_product = st.selectbox(
                "Selecione um produto para análise detalhada:",
                options=produtos,
                index=0
            )

        # Detalhamento do produto selecionado
        if selected_product:
            st.markdown("---")
            st.subheader(f"📊 Análise Detalhada: {selected_product}")

            # Obter breakdown de ingredientes
            breakdown_df = product_service.get_product_cost_breakdown()
            if not breakdown_df.empty:
                product_col = [c for c in breakdown_df.columns if "produto" in c.lower()][0] if any("produto" in c.lower() for c in breakdown_df.columns) else breakdown_df.columns[0]
                product_breakdown = breakdown_df[breakdown_df[product_col] == selected_product]

                if not product_breakdown.empty:
                    st.markdown("**Ingredientes utilizados:**")
                    st.dataframe(product_breakdown, use_container_width=True, hide_index=True)

        st.markdown("---")

        # Tabela geral de custos
        st.subheader("💸 Resumo de Custos de Todos os Produtos")

        display_df = custo_resumo.copy()
        display_df["Custo Total (R$)"] = display_df["Custo Total (R$)"].apply(
            lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )

        st.markdown('<div class="dataframe-wrapper">', unsafe_allow_html=True)
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Download CSV
        st.markdown("---")
        st.subheader("📥 Download")

        csv = custo_resumo.to_csv(index=False)
        st.download_button(
            label="📥 Baixar Custos como CSV",
            data=csv,
            file_name="custos_producao.csv",
            mime="text/csv"
        )

    except Exception as e:
        st.error(f"❌ Erro ao exibir custos de produção: {e}")


# =====================================================================
# PÁGINA: IMPACTO NO FATURAMENTO
# =====================================================================

def show_revenue_impact(product_service):
    st.header("💹 Impacto no Faturamento")
    st.markdown("---")

    try:
        # Obter dados de produtos
        produtos_df = product_service.get_products_with_sales_impact()

        if produtos_df is None or produtos_df.empty:
            st.warning("⚠️ Nenhum dado de produtos disponível")
            st.info("ℹ️ Certifique-se de que a aba 'Produtos' possui dados de preço de venda e margem")
            return

        # Identificar colunas relevantes
        def find_col(candidates):
            for col in produtos_df.columns:
                if any(c.lower() in col.lower() for c in candidates):
                    return col
            return None

        nome_col = find_col(["nome do produto", "product", "produto"])
        preco_col = find_col(["preço de venda", "preco de venda", "price"])
        margem_col = find_col(["margem"])
        categoria_col = find_col(["categoria", "category"])

        if nome_col is None:
            st.warning("⚠️ Não foi possível encontrar coluna de nome de produto")
            return

        # Calcular impacto
        st.subheader("📊 Análise de Impacto por Produto")

        # Métricas gerais
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total de Produtos", len(produtos_df))

        if preco_col and margem_col:
            with col2:
                # Converter coluna de preço para float primeiro
                preco_numeric = produtos_df[preco_col].apply(parse_currency)
                receita_total = preco_numeric.sum()
                st.metric("Receita Potencial Total", format_currency(receita_total))

            with col3:
                # Converter coluna de margem para float
                margem_numeric = produtos_df[margem_col].apply(parse_currency)
                margem_media = margem_numeric.mean()
                st.metric("Margem Média (%)", f"{margem_media:.1f}%")

            with col4:
                if categoria_col:
                    categorias = produtos_df[categoria_col].nunique()
                    st.metric("Categorias", categorias)

        st.markdown("---")

        # Tabela de impacto
        st.subheader("💰 Ranking de Impacto no Faturamento")

        # Preparar dados para exibição
        display_df = produtos_df.copy()

        # Converter colunas numéricas para formato de moeda
        if preco_col:
            display_df["Preço Formatado"] = display_df[preco_col].apply(
                lambda x: format_currency(parse_currency(x)) if parse_currency(x) is not None else "N/A"
            )

        if margem_col:
            display_df["Margem Formatada"] = display_df[margem_col].apply(
                lambda x: f"{parse_currency(x):.1f}%" if parse_currency(x) is not None else "N/A"
            )

        # Selecionar colunas para exibir
        cols_to_show = [nome_col]
        if categoria_col:
            cols_to_show.append(categoria_col)
        if preco_col:
            cols_to_show.append("Preço Formatado")
        if margem_col:
            cols_to_show.append("Margem Formatada")
        if find_col(["ativo", "active"]):
            cols_to_show.append(find_col(["ativo", "active"]))

        st.markdown('<div class="dataframe-wrapper">', unsafe_allow_html=True)
        st.dataframe(display_df[cols_to_show], use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Gráficos
        st.markdown("---")
        st.subheader("📈 Visualizações")

        col1, col2 = st.columns(2)

        with col1:
            if categoria_col:
                st.write("**Produtos por Categoria**")
                categoria_count = produtos_df[categoria_col].value_counts()
                st.bar_chart(categoria_count)

        with col2:
            if margem_col:
                st.write("**Distribuição de Margens**")
                margem_data = produtos_df[[nome_col, margem_col]].copy()
                margem_data.columns = ["Produto", "Margem"]
                # Converter margem para float
                margem_data["Margem"] = margem_data["Margem"].apply(parse_currency)
                # Remover valores NaN
                margem_data = margem_data.dropna()
                if not margem_data.empty:
                    st.bar_chart(margem_data.set_index("Produto"))

        # Download
        st.markdown("---")
        st.subheader("📥 Download")

        csv = produtos_df.to_csv(index=False)
        st.download_button(
            label="📥 Baixar Dados como CSV",
            data=csv,
            file_name="impacto_faturamento.csv",
            mime="text/csv"
        )

    except Exception as e:
        st.error(f"❌ Erro ao processar análise de faturamento: {e}")


# =====================================================================
# PÁGINA: ANÁLISE DETALHADA
# =====================================================================

def show_analise_detalhada(service, product_service):
    st.header("🔍 Análise Detalhada")
    st.markdown("---")

    try:
        # Tabs para diferentes análises
        tab1, tab2, tab3 = st.tabs(["Custos por Produto", "Margens", "Relatórios"])

        with tab1:
            st.subheader("Custo Total por Produto")

            # Usar ProductAnalysisService que lê da aba Receita
            custo_por_produto = product_service.calculate_total_cost_per_product()

            if custo_por_produto:
                # Criar DataFrame
                analise_df = pd.DataFrame(
                    [(k, float(v)) for k, v in sorted(custo_por_produto.items(), key=lambda x: x[1], reverse=True)],
                    columns=["Produto", "Custo Total (R$)"]
                )

                # Métricas
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Total de Produtos", len(analise_df))

                with col2:
                    total = analise_df["Custo Total (R$)"].sum()
                    st.metric("Custo Total", format_currency(total))

                with col3:
                    media = analise_df["Custo Total (R$)"].mean()
                    st.metric("Custo Médio", format_currency(media))

                # Gráfico
                st.bar_chart(analise_df.set_index("Produto"))

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
            st.info("ℹ️ Esta funcionalidade será implementada após integração de vendas com custos")

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

