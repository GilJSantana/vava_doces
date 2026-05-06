"""Página de custos de produção — foco em tabelas de auditoria."""

# IDs and names are intentionally separated in UI tables to prevent duplicated/misaligned columns.

from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

from src.infrastructure.drive_manager import get_drive_assets_map, load_parquet_from_drive
from src.presentation.components import render_separator

logger = logging.getLogger(__name__)

_CUSTOS_COLUMNS = [
    "nome_produto",
    "qtd_ingredientes",
    "custo_producao",
]


# ── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=1800)
def load_custos_producao_cached() -> pd.DataFrame:
    """Carrega custos_producao_agregado.parquet da camada Gold (TTL 30 min)."""
    candidates = [
        "custos_producao_agregado.parquet",
        "custos_producao.parquet",
    ]
    assets_map = get_drive_assets_map()
    existing_candidates = [name for name in candidates if name in assets_map]

    if not existing_candidates:
        logger.warning(
            "load_custos_producao_cached: nenhum parquet encontrado no Drive (%s, %s)",
            candidates[0],
            candidates[1],
        )
        empty = pd.DataFrame(columns=_CUSTOS_COLUMNS)
        empty.attrs["custos_status"] = "missing"
        return empty

    df = pd.DataFrame()
    for file_name in candidates:
        if file_name not in assets_map:
            continue
        candidate_df = load_parquet_from_drive(file_name)
        if not candidate_df.empty:
            df = candidate_df
            df.attrs["custos_source_file"] = file_name
            break

    if not df.empty:
        if "nome_produto" in df.columns:
            df["nome_produto"] = df["nome_produto"].astype(str).str.title()
        # Ensure numeric types for column_config NumberColumn
        for col in ("qtd_ingredientes", "custo_producao"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if "qtd_ingredientes" in df.columns:
            df = df[df["qtd_ingredientes"].fillna(0).ge(1)].copy()
        df.attrs["custos_status"] = "ok"
        return df

    logger.info(
        "load_custos_producao_cached: parquet(s) encontrados, mas sem linhas utilizaveis (%s)",
        ", ".join(existing_candidates),
    )
    empty = pd.DataFrame(columns=_CUSTOS_COLUMNS)
    empty.attrs["custos_status"] = "empty"
    empty.attrs["custos_source_file"] = ",".join(existing_candidates)
    return empty


@st.cache_data(ttl=1800)
def load_receitas_detalhadas_cached() -> pd.DataFrame:
    """Carrega receitas_detalhadas.parquet (Gold detalhado) com fallback."""
    df = load_parquet_from_drive("receitas_detalhadas.parquet")
    if not df.empty:
        if "nome_produto" in df.columns:
            df["nome_produto"] = df["nome_produto"].astype(str).str.title()
        if "custo_unitario_final" in df.columns:
            df["custo_unitario_final"] = pd.to_numeric(df["custo_unitario_final"], errors="coerce")
        if "custo_origem_ausente" in df.columns:
            df["custo_origem_ausente"] = df["custo_origem_ausente"].fillna(False).astype(bool)
        return df
    return pd.DataFrame(
        columns=[
            "id_produto",
            "nome_produto",
            "id_ingrediente",
            "nome_ingrediente",
            "quantidade_formatada",
            "custo_unitario_final",
            "custo_origem_ausente",
        ]
    )


# ── Column configs ────────────────────────────────────────────────────────────

def _custos_column_config() -> dict:
    """Column config da tabela agregada.

    ``NumberColumn`` preserva renderização nativa de moeda e alinhamento à direita.
    """
    return {
        "nome_produto": st.column_config.TextColumn("Produto"),
        "qtd_ingredientes": st.column_config.NumberColumn("Quantidade de Ingredientes", format="%d"),
        "custo_producao": st.column_config.NumberColumn(
            "Custo de Produção",
            format="R$ %.2f",
            help="Soma dos custos de ingredientes por produto (ignora nulos)",
            width="medium",
        ),
    }


def _recipe_column_config() -> dict:
    """st.column_config para a tabela de receitas detalhadas."""
    return {
        "id_produto": st.column_config.TextColumn("ID Produto", width="small"),
        "nome_produto": st.column_config.TextColumn("Produto"),
        "id_ingrediente": st.column_config.TextColumn("ID Ingred.", width="small"),
        "nome_ingrediente": st.column_config.TextColumn("Ingrediente"),
        "quantidade_formatada": st.column_config.TextColumn("Quantidade", width="small"),
        "custo_unitario_final": st.column_config.NumberColumn(
            "Custo Ingred. (R$)",
            format="R$ %.2f",
            help="⚠️ sem custo apenas quando o preco de origem estiver ausente",
        ),
    }


# ── Data preparation helpers ──────────────────────────────────────────────────

def _filter_by_name(df: pd.DataFrame, col: str, term: str) -> pd.DataFrame:
    """Filtro parcial case-insensitive numa coluna de texto."""
    term = term.strip().lower()
    if not term or col not in df.columns:
        return df
    return df[df[col].astype(str).str.lower().str.contains(term, na=False)].copy()


# ── Public utility functions (used by tests and external callers) ─────────────

def filter_products_by_name(df: pd.DataFrame, term: str) -> pd.DataFrame:
    """Filtro case-insensitive na coluna 'Produto'. Retorna tudo se term for vazio."""
    return _filter_by_name(df, "Produto", term)


def filter_issues_by_product(
    df: pd.DataFrame,
    product_id: str,
    name_filter: str,
) -> pd.DataFrame:
    """Filtra auditoria por 'ID do Produto' e opcionalmente por nome de produto."""
    out = df.copy()
    if "ID do Produto" in out.columns and product_id:
        out = out[out["ID do Produto"].astype(str) == str(product_id)]
    if name_filter.strip():
        out = _filter_by_name(out, "Produto", name_filter)
    return out


def build_no_cost_products_table(source_df: pd.DataFrame) -> pd.DataFrame:
    """Formata tabela de custos renomeando e formatando a coluna de custo (BRL PT-BR)."""
    out = source_df.copy()
    cost_src = "Custo Total (R$)"
    cost_dst = "Custo de Produção"
    if cost_src in out.columns:
        out[cost_dst] = out[cost_src].apply(_format_brl_ptbr)
        out = out.drop(columns=[cost_src])
    desired_cols = ["ID do Produto", "Produto", "Qtd Ingredientes", cost_dst]
    return out[[c for c in desired_cols if c in out.columns]].copy()


def build_recipe_detail_table(raw: pd.DataFrame) -> pd.DataFrame:
    """Alias público de _prepare_recipe_df para uso externo e testes."""
    return _prepare_recipe_df(raw)


def _format_brl_ptbr(value: float | int | None) -> str:
    """Format number as Brazilian currency string."""
    if value is None or pd.isna(value):
        return "⚠️ sem custo"
    text = f"R$ {float(value):,.2f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def _prepare_recipe_df(raw: pd.DataFrame) -> pd.DataFrame:
    """Padroniza receita detalhada para exibição e auditoria visual."""
    detail = raw.copy()

    rename_map = {
        "ID do Produto": "id_produto",
        "produto_id": "id_produto",
        "Produto": "nome_produto",
        "nome_produto": "nome_produto",
        "ID do Ingrediente": "id_ingrediente",
        "ingrediente_id": "id_ingrediente",
        "Ingrediente": "nome_ingrediente",
        "nome_ingrediente": "nome_ingrediente",
        "Quantidade Receita": "qtd",
        "qtd": "qtd",
        "Unidade de Medida": "unidade",
        "unidade": "unidade",
        "quantidade_formatada": "quantidade_formatada",
        "Custo do Ingrediente (R$)": "custo_unitario_final",
        "custo_unitario": "custo_unitario_final",
        "custo_unitario_final": "custo_unitario_final",
    }
    detail = detail.rename(columns={k: v for k, v in rename_map.items() if k in detail.columns})

    for col in ("id_produto", "nome_produto", "id_ingrediente", "nome_ingrediente", "unidade"):
        if col not in detail.columns:
            detail[col] = ""
        detail[col] = detail[col].fillna("").astype(str).str.strip()

    if "qtd" not in detail.columns:
        detail["qtd"] = 0.0
    detail["qtd"] = pd.Series(pd.to_numeric(detail["qtd"], errors="coerce"), index=detail.index).fillna(0.0)

    if "quantidade_formatada" not in detail.columns:
        qty_txt = detail["qtd"].map(lambda x: f"{x:g}" if pd.notna(x) else "")
        unit_txt = detail["unidade"].fillna("").astype(str).str.strip()
        detail["quantidade_formatada"] = (qty_txt + " " + unit_txt).str.strip()
    detail["quantidade_formatada"] = detail["quantidade_formatada"].fillna("").astype(str).str.strip()

    if "custo_unitario_final" not in detail.columns:
        detail["custo_unitario_final"] = pd.NA
    detail["custo_unitario_final"] = pd.to_numeric(detail["custo_unitario_final"], errors="coerce")
    if "custo_origem_ausente" not in detail.columns:
        detail["custo_origem_ausente"] = detail["custo_unitario_final"].isna()
    detail["custo_origem_ausente"] = detail["custo_origem_ausente"].fillna(False).astype(bool)

    sem_custo_mask = detail["custo_origem_ausente"]
    detail["estado_custo"] = sem_custo_mask.map(lambda m: "⚠️ sem custo" if m else "")

    ordered = [
        "id_produto",
        "nome_produto",
        "id_ingrediente",
        "nome_ingrediente",
        "quantidade_formatada",
        "custo_unitario_final",
        "estado_custo",
    ]
    return detail[ordered].reset_index(drop=True)


# ── Section renderers ─────────────────────────────────────────────────────────

def _render_custos_table(search_term: str) -> None:
    """Renderiza tabela agregada de custos Gold filtrada apenas pela busca do cockpit."""
    with st.container(border=True):
        st.subheader("💸 Tabela de Custos de Produção")
        st.caption("Dashboard consolidado da camada Gold por produto.")

        custos_df = load_custos_producao_cached()

        if custos_df.empty:
            status = str(custos_df.attrs.get("custos_status", "missing"))
            if status == "empty":
                st.info(
                    "ℹ️ Arquivos de custos encontrados no Google Drive, mas sem registros para exibir. "
                    "Verifique se as abas manuais de custos/receitas possuem dados validos."
                )
            else:
                st.warning(
                    "⚠️ Arquivos de custos nao encontrados no Google Drive: "
                    "`custos_producao_agregado.parquet` e `custos_producao.parquet`."
                )
            return

        filtered_df = _filter_by_name(custos_df, "nome_produto", search_term)
        display_cols = [c for c in _CUSTOS_COLUMNS if c in filtered_df.columns]

        st.caption(
            f"Exibindo **{len(filtered_df)}** de **{len(custos_df)}** produto(s)"
            + (f" — busca: `{search_term}`" if search_term else "")
        )

        if filtered_df.empty:
            st.warning("Nenhum produto encontrado no cockpit de custos com o filtro informado.")
            return

        if len(filtered_df) > 1000:
            st.warning("Exibindo apenas os primeiros 1000 itens para performance.")
        preview_df = filtered_df.head(1000).copy()
        if "custo_producao" in preview_df.columns:
            preview_df["custo_producao"] = pd.to_numeric(preview_df["custo_producao"], errors="coerce").round(2)

        if "custo_producao" in preview_df.columns and preview_df["custo_producao"].isna().any():
            styled_df = preview_df[display_cols].rename(
                columns={
                    "nome_produto": "Produto",
                    "qtd_ingredientes": "Quantidade de Ingredientes",
                    "custo_producao": "Custo de Produção",
                }
            ).style.format(
                {
                    "Custo de Produção": lambda v: _format_brl_ptbr(v),
                }
            )
            st.dataframe(styled_df, width="stretch", hide_index=True)
        else:
            st.dataframe(
                preview_df[display_cols],
                width="stretch",
                hide_index=True,
                column_config=_custos_column_config(),
            )


def _render_recipe_table(breakdown_all: pd.DataFrame | None) -> str | None:
    """Renderiza receitas detalhadas com investigacao controlada apenas por selecao."""
    with st.container(border=True):
        st.subheader("🧾 Receitas Detalhadas por Produto")

        if breakdown_all is None or breakdown_all.empty:
            st.info(
                "ℹ️ Nenhum dado de receita disponível. "
                "Verifique a aba **Receita** na planilha."
            )
            return None

        recipe_df = breakdown_all.copy()
        expected_cols = [
            "id_produto",
            "nome_produto",
            "id_ingrediente",
            "nome_ingrediente",
            "quantidade_formatada",
            "custo_unitario_final",
        ]
        for col in expected_cols:
            if col not in recipe_df.columns:
                recipe_df[col] = "" if col != "custo_unitario_final" else 0.0

        for col in ["id_produto", "nome_produto", "id_ingrediente", "nome_ingrediente", "quantidade_formatada"]:
            recipe_df[col] = recipe_df[col].fillna("").astype(str).str.strip()
        recipe_df["custo_unitario_final"] = pd.Series(
            pd.to_numeric(recipe_df["custo_unitario_final"], errors="coerce"),
            index=recipe_df.index,
        ).fillna(0.0)

        produto_options = ["Todos"] + sorted(recipe_df["nome_produto"].dropna().astype(str).unique().tolist())
        selected_produto = st.selectbox(
            "Selecionar produto para investigar",
            options=produto_options,
            index=0,
            key="custos_produto_select",
        )

        filtered = recipe_df.copy()
        if selected_produto != "Todos":
            filtered = filtered[filtered["nome_produto"].astype(str) == selected_produto].copy()

        pending_mask = filtered["custo_unitario_final"].eq(0.0)
        if "custo_origem_ausente" in filtered.columns:
            pending_mask = filtered["custo_origem_ausente"].fillna(False).astype(bool)
        pending_ids = filtered.loc[pending_mask, "id_ingrediente"].astype(str).str.strip()
        pending_ids = pending_ids[pending_ids != ""]
        itens_pendentes = int(pending_ids.nunique())

        metric_col, _ = st.columns([1, 2])
        metric_col.metric("Itens Pendentes de Auditoria", itens_pendentes)

        st.caption(
            f"Exibindo **{len(filtered)}** de **{len(recipe_df)}** linha(s)"
            + (f" — produto: `{selected_produto}`" if selected_produto != "Todos" else "")
        )

        if len(filtered) > 1000:
            st.warning("Exibindo apenas os primeiros 1000 itens para performance.")
        preview_df = filtered.head(1000)

        st.dataframe(
            preview_df,
            width="stretch",
            hide_index=True,
            column_order=[
                "id_produto",
                "nome_produto",
                "id_ingrediente",
                "nome_ingrediente",
                "quantidade_formatada",
                "custo_unitario_final",
            ],
            column_config=_recipe_column_config(),
        )
        return None if selected_produto == "Todos" else selected_produto


def _render_audit_expander(
    issues_df: pd.DataFrame | None,
    produto_selecionado: str | None,
    n_breakdown: int,
    cobertura: str,
) -> None:
    """Expander 'Auditoria de Inconsistências': ingredientes sem custo mapeado."""
    n_issues = len(issues_df) if issues_df is not None and not issues_df.empty else 0

    expander_label = (
        f"🔴 Auditoria de Inconsistências — {n_issues} ingrediente(s) sem custo"
        if n_issues > 0
        else "✅ Auditoria de Inconsistências — todos os custos preenchidos"
    )

    with st.expander(expander_label, expanded=(n_issues > 0)):
        # Summary metrics
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Linhas de receita auditadas", n_breakdown)
        col_b.metric("Ingredientes sem custo", n_issues)
        col_c.metric("Cobertura de custo", cobertura)

        if n_issues == 0:
            st.success("✅ Nenhuma inconsistência encontrada. Todos os custos estão preenchidos.")
            return

        st.warning(
            "⚠️ Os ingredientes abaixo não possuem custo válido. "
            "Preencha a coluna **Custo do Ingrediente** na aba **Receita** "
            "ou o **Custo Unitário** na aba **Matéria Prima**."
        )

        audit_df = _prepare_recipe_df(issues_df.copy())
        filtered_audit = audit_df.copy()
        if produto_selecionado:
            filtered_audit = filtered_audit[
                filtered_audit["nome_produto"].astype(str) == str(produto_selecionado)
            ].copy()

        st.caption(
            f"Exibindo **{len(filtered_audit)}** de **{n_issues}** inconsistência(s)"
            + (f" — produto: `{produto_selecionado}`" if produto_selecionado else "")
        )

        if len(filtered_audit) > 1000:
            st.warning("Exibindo apenas os primeiros 1000 itens para performance.")
        preview_audit_df = filtered_audit.head(1000)

        st.dataframe(
            preview_audit_df,
            width="stretch",
            hide_index=True,
            column_config=_recipe_column_config(),
        )

        st.download_button(
            "📥 Exportar inconsistências (CSV)",
            data=issues_df.to_csv(index=False),
            file_name="inconsistencias_receita.csv",
            mime="text/csv",
            key="download_inconsistencias",
        )


# ── Page entry-point ──────────────────────────────────────────────────────────

def show_production_costs() -> None:
    """Renderiza página de custos de produção com foco em tabelas de auditoria."""
    st.header("💰 Custos de Produção")
    render_separator()

    search_term = st.text_input(
        "🔍 Buscar produto no cockpit de custos",
        placeholder="Buscar produto no cockpit de custos...",
        key="prod_costs_search_top",
    )

    render_separator()

    # ── Section 1: Gold custos_producao audit table ───────────────────────────

    _render_custos_table(search_term)

    render_separator()

    # ── Load recipe data once for sections 2 & 3 ─────────────────────────────
    breakdown_all = load_receitas_detalhadas_cached()
    issues_df = pd.DataFrame()
    if not breakdown_all.empty:
        if "custo_origem_ausente" in breakdown_all.columns:
            issues_df = breakdown_all[breakdown_all["custo_origem_ausente"].fillna(False).astype(bool)].copy()
        elif "custo_unitario_final" in breakdown_all.columns:
            issues_df = breakdown_all[breakdown_all["custo_unitario_final"].isna()].copy()
        else:
            issues_df = pd.DataFrame()

    n_issues = len(issues_df) if issues_df is not None and not issues_df.empty else 0
    n_breakdown = len(breakdown_all) if breakdown_all is not None and not breakdown_all.empty else 0
    cobertura = (
        f"{((n_breakdown - n_issues) / n_breakdown * 100):.0f}%"
        if n_breakdown > 0
        else "—"
    )

    # ── Section 2: Detailed recipe breakdown ─────────────────────────────────
    produto_selecionado = _render_recipe_table(breakdown_all)

    render_separator()

    # ── Section 3: Audit expander ─────────────────────────────────────────────
    _render_audit_expander(issues_df, produto_selecionado, n_breakdown, cobertura)
