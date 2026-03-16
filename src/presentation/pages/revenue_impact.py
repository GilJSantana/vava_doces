"""Página de impacto no faturamento."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.presentation.components import build_product_labels, render_separator, render_wrapped_dataframe
from src.presentation.formatters import format_currency


CHART_BG = "#f9f9f9"
AXIS_TEXT = "#2d2d2d"
GRID_COLOR = "#e0e0e0"
PARETO_PALETTE = [
    "#636EFA",
    "#EF553B",
    "#00CC96",
    "#AB63FA",
    "#FFA15A",
    "#19D3F3",
    "#FF6692",
    "#B6E880",
]


def clean_product_name(series: pd.Series) -> pd.Series:
    """Remove prefixo de ID do produto para exibição mais limpa."""
    return series.astype(str).str.split(" - ", n=1).str[-1].str.strip()


def build_base_figure() -> go.Figure:
    """Cria figura Plotly padronizada para o tema analítico."""
    fig = go.Figure()
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_BG,
        font={"color": AXIS_TEXT, "size": 12},
        margin={"l": 24, "r": 24, "t": 24, "b": 24},
        showlegend=False,
        hovermode="closest",
    )
    return fig


def build_revenue_pareto_chart(analysis_df: pd.DataFrame) -> go.Figure | None:
    """Gráfico horizontal de faturamento total por produto."""
    chart_df = analysis_df.copy()
    chart_df = chart_df[chart_df["Faturamento Total"] > 0].copy()
    if chart_df.empty:
        return None

    chart_df["Produto Limpo"] = clean_product_name(
        build_product_labels(chart_df, "ID do Produto", "Nome do Produto")
    )
    chart_df["len_nome"] = chart_df["Produto Limpo"].str.len()
    chart_df = chart_df.sort_values(["len_nome", "Produto Limpo"], ascending=[True, True])

    fig = build_base_figure()
    fig.add_trace(
        go.Bar(
            x=chart_df["Faturamento Total"],
            y=chart_df["Produto Limpo"],
            orientation="h",
            marker={"color": "#2563EB", "cornerradius": 18, "line": {"width": 0}},
            customdata=chart_df[["Volume de Vendas", "Margem de Contribuição (R$)", "Custo Real"]].to_numpy(),
            hovertemplate=(
                "Produto: %{y}<br>"
                "Faturamento: R$ %{x:.2f}<br>"
                "Volume: %{customdata[0]:.0f}<br>"
                "Margem R$: R$ %{customdata[1]:.2f}<br>"
                "Custo Real: R$ %{customdata[2]:.2f}<extra></extra>"
            ),
        )
    )
    fig.update_layout(hovermode="y unified")
    max_name_len = int(chart_df["len_nome"].max()) if not chart_df.empty else 0
    left_margin = min(max(240, max_name_len * 8), 480)
    fig.update_layout(margin={"l": left_margin, "r": 24, "t": 16, "b": 20})
    fig.update_xaxes(title_text="Faturamento Total (R$)", showgrid=False, zeroline=False, showline=False)
    fig.update_yaxes(
        title_text="",
        automargin=True,
        tickangle=0,
        ticklabelposition="outside",
        tickfont={"color": AXIS_TEXT, "size": 11, "family": "Arial Black, Arial, sans-serif"},
        showgrid=True,
        gridcolor=GRID_COLOR,
        gridwidth=1,
        categoryorder="array",
        categoryarray=chart_df["Produto Limpo"].tolist(),
        autorange="reversed",
    )
    return fig


def build_profitability_scatter_chart(analysis_df: pd.DataFrame) -> go.Figure | None:
    """Matriz de rentabilidade com quadrantes por volume e margem percentual."""
    chart_df = analysis_df.copy()
    chart_df = chart_df[(chart_df["Volume de Vendas"] > 0) & chart_df["Preço"].notna()].copy()
    if chart_df.empty:
        return None

    chart_df["Produto Limpo"] = clean_product_name(
        build_product_labels(chart_df, "ID do Produto", "Nome do Produto")
    )
    chart_df["Tamanho"] = chart_df["Faturamento Total"].clip(lower=0).fillna(0)
    max_size = chart_df["Tamanho"].max() or 1
    marker_sizes = (chart_df["Tamanho"] / max_size * 28).clip(lower=10)

    avg_volume = float(chart_df["Volume de Vendas"].mean())
    avg_margin = float(chart_df["Margem de Contribuição (%)"].mean())
    max_volume = float(chart_df["Volume de Vendas"].max())
    min_margin = float(chart_df["Margem de Contribuição (%)"].min())
    max_margin = float(chart_df["Margem de Contribuição (%)"].max())

    fig = build_base_figure()
    fig.add_trace(
        go.Scatter(
            x=chart_df["Volume de Vendas"],
            y=chart_df["Margem de Contribuição (%)"],
            mode="markers",
            marker={
                "size": marker_sizes.tolist(),
                "color": "#7C3AED",
                "line": {"width": 1, "color": "rgba(45,45,45,0.18)"},
                "opacity": 0.72,
            },
            customdata=chart_df[
                [
                    "Produto Limpo",
                    "Margem de Contribuição (R$)",
                    "Margem de Contribuição (%)",
                ]
            ].to_numpy(),
            hovertemplate=(
                "Produto: %{customdata[0]}<br>"
                "Margem R$: R$ %{customdata[1]:.2f}<br>"
                "Margem %: %{customdata[2]:.2f}%<br>"
                "Volume: %{x:.0f}<extra></extra>"
            ),
        )
    )
    fig.update_layout(showlegend=False, hovermode="closest")
    fig.update_xaxes(title_text="Volume de Vendas", showgrid=False, zeroline=False, showline=False)
    fig.update_yaxes(
        title_text="Margem de Contribuição (%)",
        showgrid=True,
        gridcolor=GRID_COLOR,
        gridwidth=1,
        zeroline=False,
        showline=False,
    )
    fig.add_vline(x=avg_volume, line_dash="dash", line_color="#7A7A7A", opacity=0.7)
    fig.add_hline(y=avg_margin, line_dash="dash", line_color="#7A7A7A", opacity=0.7)

    annotations = [
        (avg_volume * 0.55 if avg_volume else max_volume * 0.25, max_margin, "Estrelas"),
        (avg_volume * 1.35 if avg_volume else max_volume * 0.75, max_margin, "Vacas Leiteiras"),
        (avg_volume * 0.55 if avg_volume else max_volume * 0.25, min_margin, "Interrogações"),
        (avg_volume * 1.35 if avg_volume else max_volume * 0.75, min_margin, "Abacaxis"),
    ]
    for x_pos, y_pos, label in annotations:
        fig.add_annotation(
            x=x_pos,
            y=y_pos,
            text=label,
            showarrow=False,
            font={"color": AXIS_TEXT, "size": 11},
            bgcolor="rgba(249,249,249,0.75)",
        )
    return fig


def build_price_vs_cost_chart(analysis_df: pd.DataFrame) -> go.Figure | None:
    """Gráfico comparativo horizontal entre preço de venda e custo de produção."""
    chart_df = analysis_df.copy()
    chart_df = chart_df[(chart_df["Preço"].fillna(0) > 0) | (chart_df["Custo Real"].fillna(0) > 0)].copy()
    if chart_df.empty:
        return None

    chart_df["Produto Limpo"] = clean_product_name(
        build_product_labels(chart_df, "ID do Produto", "Nome do Produto")
    )
    chart_df["len_nome"] = chart_df["Produto Limpo"].str.len()
    chart_df = chart_df.sort_values(["len_nome", "Produto Limpo"], ascending=[True, True])

    fig = build_base_figure()
    max_name_len = int(chart_df["len_nome"].max()) if not chart_df.empty else 0
    left_margin = min(max(240, max_name_len * 8), 480)
    fig.add_trace(
        go.Bar(
            x=chart_df["Preço"].fillna(0.0),
            y=chart_df["Produto Limpo"],
            orientation="h",
            name="Preço de Venda",
            marker={"color": "#2E8B57", "cornerradius": 18, "line": {"width": 0}},
            hovertemplate="Produto: %{y}<br>Preço de Venda: R$ %{x:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            x=chart_df["Custo Real"].fillna(0.0),
            y=chart_df["Produto Limpo"],
            orientation="h",
            name="Custo de Produção",
            marker={"color": "#F4A261", "cornerradius": 18, "line": {"width": 0}},
            hovertemplate="Produto: %{y}<br>Custo de Produção: R$ %{x:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        barmode="group",
        showlegend=True,
        legend={"orientation": "h", "y": 1.08, "x": 0, "font": {"color": AXIS_TEXT}},
        margin={"l": left_margin, "r": 24, "t": 16, "b": 20},
    )
    fig.update_xaxes(title_text="Valor (R$)", showgrid=False, zeroline=False, showline=False)
    fig.update_yaxes(
        title_text="",
        automargin=True,
        tickangle=0,
        ticklabelposition="outside",
        tickfont={"color": AXIS_TEXT, "size": 11, "family": "Arial Black, Arial, sans-serif"},
        showgrid=True,
        gridcolor=GRID_COLOR,
        gridwidth=1,
        categoryorder="array",
        categoryarray=chart_df["Produto Limpo"].tolist(),
        autorange="reversed",
    )
    return fig


def show_revenue_impact(product_service):
    """Renderiza análise de impacto no faturamento."""
    st.header("💹 Impacto no Faturamento")
    render_separator()

    try:
        produtos_df = product_service.get_product_profitability_analysis()

        if produtos_df is None or produtos_df.empty:
            st.warning("⚠️ Nenhum dado de produtos disponível")
            st.info("ℹ️ Certifique-se de que as abas 'Produtos' e 'Vendas Diárias' possuem dados válidos")
            return

        produtos_df = produtos_df[
            produtos_df["ID do Produto"].notna()
            & (produtos_df["ID do Produto"].astype(str).str.strip() != "")
            & produtos_df["Nome do Produto"].notna()
            & (produtos_df["Nome do Produto"].astype(str).str.strip() != "")
        ].copy()

        if produtos_df.empty:
            st.warning("⚠️ Nenhum produto válido encontrado")
            return

        st.subheader("📊 Análise de Impacto por Produto")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total de Produtos", produtos_df["ID do Produto"].nunique())

        with col2:
            receita_total = produtos_df["Faturamento Total"].fillna(0).sum() if "Faturamento Total" in produtos_df.columns else 0
            st.metric("Faturamento Total", format_currency(receita_total))

        with col3:
            if (
                "Margem de Contribuição (%)" in produtos_df.columns
                and produtos_df["Margem de Contribuição (%)"].notna().any()
            ):
                margem_media = produtos_df["Margem de Contribuição (%)"].dropna().mean()
                st.metric("Margem Média (%)", f"{margem_media:.1f}%")
            else:
                st.metric("Margem Média (%)", "N/A")

        with col4:
            if "Volume de Vendas" in produtos_df.columns:
                volume_total = produtos_df["Volume de Vendas"].fillna(0).sum()
                st.metric("Volume de Vendas", f"{volume_total:.0f}")
            else:
                st.metric("Volume de Vendas", 0)

        render_separator()
        st.subheader("💰 Ranking de Impacto no Faturamento")

        display_df = produtos_df.copy()
        display_df["Produto"] = build_product_labels(display_df, "ID do Produto", "Nome do Produto")

        for col in ["Preço", "Custo Total (R$)", "Margem Bruta (R$)", "Faturamento Total", "Margem de Contribuição (R$)"]:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(
                    lambda x: format_currency(x) if pd.notna(x) else "N/A"
                )

        if "Custo Total (R$)" in display_df.columns:
            display_df = display_df.rename(columns={"Custo Total (R$)": "Custo de Produção (R$)"})

        if "Margem de Contribuição (%)" in display_df.columns:
            display_df["Margem"] = display_df["Margem de Contribuição (%)"].apply(
                lambda x: f"{x:.1f}%" if pd.notna(x) else "N/A"
            )

        cols_to_show = ["Produto"]
        for col in [
            "Categoria",
            "Preço",
            "Custo de Produção (R$)",
            "Faturamento Total",
            "Margem",
            "Margem de Contribuição (R$)",
            "Ativo",
        ]:
            if col in display_df.columns:
                cols_to_show.append(col)

        render_wrapped_dataframe(display_df[cols_to_show])

        render_separator()
        tab_impacto, tab_rentabilidade, tab_preco_custo = st.tabs(
            ["Impacto Financeiro", "Rentabilidade", "Preço vs Custo"]
        )

        with tab_impacto:
            st.subheader("📈 Quais produtos trazem mais dinheiro para o caixa?")
            pareto_fig = build_revenue_pareto_chart(produtos_df)
            if pareto_fig is None:
                st.info("ℹ️ Ainda não há faturamento consolidado suficiente para montar o gráfico de impacto.")
            else:
                st.plotly_chart(pareto_fig, use_container_width=True)

        with tab_rentabilidade:
            st.subheader("🎯 Matriz de Rentabilidade")
            scatter_fig = build_profitability_scatter_chart(produtos_df)
            if scatter_fig is None:
                st.info("ℹ️ Ainda não há volume de vendas suficiente para montar a matriz de rentabilidade.")
            else:
                st.plotly_chart(scatter_fig, use_container_width=True)

        with tab_preco_custo:
            st.subheader("⚖️ Preço de Venda vs. Custo de Produção")
            price_vs_cost_fig = build_price_vs_cost_chart(produtos_df)
            if price_vs_cost_fig is None:
                st.info("ℹ️ Ainda não há dados suficientes para comparar preço e custo por produto.")
            else:
                st.plotly_chart(price_vs_cost_fig, use_container_width=True)

        render_separator()
        st.subheader("📥 Download")

        csv = produtos_df.to_csv(index=False)
        st.download_button(
            label="📥 Baixar Dados como CSV",
            data=csv,
            file_name="impacto_faturamento.csv",
            mime="text/csv",
        )

    except Exception as e:
        st.error(f"❌ Erro ao processar análise de faturamento: {e}")

