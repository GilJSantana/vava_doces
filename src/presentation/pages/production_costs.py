"""Página de custos de produção."""

import pandas as pd
import streamlit as st

from src.presentation.components import build_product_labels, render_separator, render_wrapped_dataframe
from src.presentation.formatters import format_currency


def build_no_cost_products_table(custo_resumo: pd.DataFrame) -> pd.DataFrame:
    """Prepara tabela de produtos com quantidade de ingredientes e custo de produção."""
    display_sem_custo = custo_resumo[
        ["ID do Produto", "Produto", "Qtd Ingredientes", "Custo Total (R$)"]
    ].copy()
    display_sem_custo = display_sem_custo.rename(
        columns={"Custo Total (R$)": "Custo de Produção"}
    )
    display_sem_custo["Custo de Produção"] = display_sem_custo["Custo de Produção"].apply(
        lambda x: format_currency(x) if pd.notna(x) else "⚠️ sem custo"
    )
    return display_sem_custo


def build_cost_summary_table(custo_resumo: pd.DataFrame) -> pd.DataFrame:
    """Prepara tabela-resumo com custo de produção por produto."""
    display_df = custo_resumo.copy()
    display_df["Produto"] = build_product_labels(display_df, "ID do Produto", "Produto")
    display_df = display_df.drop(columns=["ID do Produto"])
    display_df["Custo Total (R$)"] = display_df["Custo Total (R$)"].apply(
        lambda x: format_currency(x) if pd.notna(x) else "⚠️ sem custo"
    )
    return display_df


def build_cost_summary_column_config() -> dict:
    """Configura colunas da tabela de custo para melhor legibilidade."""
    return {
        "Produto": st.column_config.TextColumn("Produto"),
        "Qtd Ingredientes": st.column_config.TextColumn("Qtd Ingredientes"),
        "Custo Total (R$)": st.column_config.TextColumn("Custo Total (R$)"),
    }


def build_cost_summary_styler(cost_summary_df: pd.DataFrame):
    """Centraliza colunas numéricas e mantém texto à esquerda na tabela de custos."""
    styled_df = cost_summary_df.style

    if "Produto" in cost_summary_df.columns:
        styled_df = styled_df.set_properties(subset=["Produto"], **{"text-align": "left"})
    if "Qtd Ingredientes" in cost_summary_df.columns:
        styled_df = styled_df.set_properties(subset=["Qtd Ingredientes"], **{"text-align": "center"})
    if "Custo Total (R$)" in cost_summary_df.columns:
        styled_df = styled_df.set_properties(subset=["Custo Total (R$)"], **{"text-align": "center"})

    return styled_df


def build_recipe_detail_table(recipe_df: pd.DataFrame) -> pd.DataFrame:
    """Padroniza colunas da tabela de componentes da receita, removendo colunas desnecessárias."""
    detail_df = recipe_df.copy()

    # Remover colunas desnecessárias para o usuário
    cols_to_drop = ["Custo Unitário MP (R$)", "Custo da Receita (R$)", "Origem do Custo"]
    for col in cols_to_drop:
        if col in detail_df.columns:
            detail_df = detail_df.drop(columns=[col])

    # Concatenar Quantidade Receita com Unidade de Medida
    if "Quantidade Receita" in detail_df.columns and "Unidade de Medida" in detail_df.columns:
        # Limpar valores vazios e NA da coluna Unidade de Medida
        detail_df["Unidade de Medida"] = detail_df["Unidade de Medida"].astype(str).str.strip()
        detail_df["Unidade de Medida"] = detail_df["Unidade de Medida"].replace(["", "nan", "None"], pd.NA)
        
        # Concatenar apenas quando houver unidade válida
        def concat_qty_unit(row):
            qty = str(row["Quantidade Receita"]).replace(".0", "") if pd.notna(row["Quantidade Receita"]) else ""
            unit = str(row["Unidade de Medida"]).strip() if pd.notna(row["Unidade de Medida"]) else ""
            
            if qty and unit:
                return f"{qty} {unit}"
            elif qty:
                return qty
            return ""
        
        detail_df["Quantidade"] = detail_df.apply(concat_qty_unit, axis=1)
        detail_df = detail_df.drop(columns=["Quantidade Receita", "Unidade de Medida"])
    elif "Quantidade Receita" in detail_df.columns:
        detail_df = detail_df.rename(columns={"Quantidade Receita": "Quantidade"})

    # Formatar custo do ingrediente
    if "Custo do Ingrediente (R$)" in detail_df.columns:
        detail_df["Custo do Ingrediente (R$)"] = detail_df["Custo do Ingrediente (R$)"].apply(
            lambda x: format_currency(x) if pd.notna(x) else "⚠️ sem custo"
        )

    ordered_columns = [
        "ID do Produto",
        "Produto",
        "ID do Ingrediente",
        "Ingrediente",
        "Quantidade",
        "Custo do Ingrediente (R$)",
    ]
    existing_ordered_columns = [col for col in ordered_columns if col in detail_df.columns]
    remaining_columns = [col for col in detail_df.columns if col not in existing_ordered_columns]
    detail_df = detail_df[existing_ordered_columns + remaining_columns]

    return detail_df


def build_recipe_selector_options(products_df: pd.DataFrame) -> list[str]:
    """Monta opções únicas do seletor de produtos da seção de receita."""
    if products_df is None or products_df.empty:
        return []

    selector_df = (
        products_df[["ID do Produto", "Produto"]]
        .dropna(subset=["ID do Produto", "Produto"])
        .drop_duplicates()
        .sort_values(["Produto", "ID do Produto"])
    )
    return build_product_labels(selector_df, "ID do Produto", "Produto").tolist()


def extract_product_id(product_label: str | None) -> str | None:
    """Extrai o ID do produto a partir do label padrão 'ID - Produto'."""
    if not product_label:
        return None
    return product_label.split(" - ", 1)[0]


def filter_products_by_name(products_df: pd.DataFrame, search_term: str) -> pd.DataFrame:
    """Filtra produtos por nome usando busca parcial, sem diferenciar maiúsculas/minúsculas."""
    normalized_search = search_term.strip().lower()
    if not normalized_search:
        return products_df

    return products_df[
        products_df["Produto"].astype(str).str.strip().str.lower().str.contains(normalized_search, na=False)
    ].copy()


def filter_issues_by_product(issues_df: pd.DataFrame, selected_product_id: str, search_term: str) -> pd.DataFrame:
    """Filtra inconsistências por ID do produto e por nome (refino opcional)."""
    filtered_df = issues_df

    if selected_product_id:
        filtered_df = filtered_df[filtered_df["ID do Produto"].astype(str).str.strip() == selected_product_id]

    normalized_search = search_term.strip().lower()
    if normalized_search:
        filtered_df = filtered_df[
            filtered_df["Produto"].astype(str).str.strip().str.lower().str.contains(normalized_search, na=False)
        ]

    return filtered_df.copy()


def show_production_costs(product_service):
    """Renderiza custos, inconsistências e detalhamento por produto."""
    st.header("💰 Custo de Produção")
    render_separator()

    try:
        issues_df = product_service.get_recipe_cost_issues()
        breakdown_all = product_service.get_product_cost_breakdown()

        n_issues = len(issues_df) if issues_df is not None and not issues_df.empty else 0
        n_total = len(breakdown_all) if breakdown_all is not None and not breakdown_all.empty else 0
        cobertura = f"{((n_total - n_issues) / n_total * 100):.0f}%" if n_total > 0 else "—"

        label_expander = (
            f"🔴 {n_issues} Ingrediente(s) sem custo — clique para ver detalhes"
            if n_issues > 0
            else "✅ Todos os ingredientes com custo válido"
        )

        def render_issues_expander() -> None:
            if n_issues > 0:
                st.warning(
                    "⚠️ Os ingredientes abaixo não possuem custo válido. "
                    "Preencha a coluna **Custo do Ingrediente** na aba **Receita** "
                    "ou o **Custo Unitário** na aba **Matéria Prima**."
                )

            with st.expander(label_expander, expanded=(n_issues > 0)):
                if n_issues > 0:
                    issues_display_df = build_recipe_detail_table(issues_df)

                    product_options_df = (
                        issues_display_df[["ID do Produto", "Produto"]]
                        .drop_duplicates()
                        .sort_values(["Produto", "ID do Produto"])
                    )
                    product_options_df["Label Produto"] = (
                        product_options_df["ID do Produto"].astype(str).str.strip()
                        + " - "
                        + product_options_df["Produto"].astype(str).str.strip()
                    )

                    product_options = ["Todos os produtos"] + product_options_df["Label Produto"].tolist()
                    selected_product_label = st.selectbox(
                        "Filtrar por produto (ID - Produto):",
                        options=product_options,
                        index=0,
                        key="issues_filter_product",
                    )
                    selected_product_id = (
                        selected_product_label.split(" - ", 1)[0]
                        if selected_product_label != "Todos os produtos"
                        else ""
                    )

                    filtered_issues_df = filter_issues_by_product(
                        issues_display_df,
                        selected_product_id,
                        "",
                    )

                    col_a, col_b = st.columns(2)
                    col_a.metric("Ingredientes na receita", len(filtered_issues_df))
                    col_b.metric("Cobertura de custo", cobertura)
                    st.caption(
                        f"Exibindo {len(filtered_issues_df)} de {len(issues_display_df)} inconsistência(s)."
                    )

                    if filtered_issues_df.empty:
                        st.info("ℹ️ Nenhuma inconsistência encontrada com os filtros atuais.")
                    else:
                        render_wrapped_dataframe(filtered_issues_df)

                    csv_issues = issues_df.to_csv(index=False)
                    st.download_button(
                        "📥 Baixar lista de inconsistências",
                        data=csv_issues,
                        file_name="inconsistencias_receita.csv",
                        mime="text/csv",
                    )
                else:
                    col_a, col_b = st.columns(2)
                    col_a.metric("Ingredientes na receita", n_total)
                    col_b.metric("Cobertura de custo", cobertura)
                    st.success("Nenhuma inconsistência encontrada. Todos os custos estão preenchidos.")

        custo_resumo = product_service.get_product_cost_summary()

        sem_dados = custo_resumo is None or custo_resumo.empty
        tem_custos = not sem_dados and custo_resumo["Custo Total (R$)"].notna().any()

        if sem_dados:
            st.warning("⚠️ Nenhum dado de receita disponível. Verifique a aba **Receita** na planilha.")
            render_separator()
            render_issues_expander()
            return

        cost_summary_df = build_cost_summary_table(custo_resumo)
        recipe_selector_options = build_recipe_selector_options(custo_resumo)

        if not tem_custos:
            st.warning(
                "⚠️ Há produtos na receita, mas nenhum custo válido foi calculado ainda. "
                "Corrija as inconsistências acima e clique em **🔄 Atualizar dados**."
            )

        st.subheader("💸 Custo de Produção por Produto")
        if tem_custos:
            render_wrapped_dataframe(
                build_cost_summary_styler(cost_summary_df),
                column_config=build_cost_summary_column_config(),
            )
        else:
            display_sem_custo = build_no_cost_products_table(custo_resumo)
            search_term = st.text_input(
                "Buscar produto pelo nome:",
                placeholder="Digite parte do nome do produto",
            )
            filtered_display_df = filter_products_by_name(display_sem_custo, search_term)
            st.caption(
                f"Exibindo {len(filtered_display_df)} de {len(display_sem_custo)} produto(s)."
            )
            render_wrapped_dataframe(filtered_display_df)

        render_separator()
        st.subheader("🧾 Receita")

        selected_label = None
        if recipe_selector_options:
            selected_label = st.selectbox(
                "Selecione um produto para visualizar os componentes da receita:",
                options=recipe_selector_options,
                index=0,
                key="recipe_product_selector",
            )
            st.caption(f"Produto selecionado: {selected_label}")
        else:
            st.info("ℹ️ Nenhum produto disponível para detalhar a receita.")

        selected_id = extract_product_id(selected_label)

        if selected_id and breakdown_all is not None and not breakdown_all.empty:
            product_breakdown = breakdown_all[breakdown_all["ID do Produto"] == selected_id].copy()

            if not product_breakdown.empty:
                recipe_detail_df = build_recipe_detail_table(product_breakdown)
                render_wrapped_dataframe(recipe_detail_df)
            else:
                st.info("ℹ️ Nenhum componente de receita encontrado para o produto selecionado.")

        render_separator()
        render_issues_expander()

        if not tem_custos:
            return

        render_separator()
        st.subheader("📥 Download")
        csv = custo_resumo.to_csv(index=False)
        st.download_button(
            label="📥 Baixar Custos como CSV",
            data=csv,
            file_name="custos_producao.csv",
            mime="text/csv",
        )

    except Exception as e:
        st.error(f"❌ Erro ao exibir custos de produção: {e}")
        raise


