"""Página de faturamento focada em exploração de dados de vendas.

Agora usa gold layer (fato_vendas + dim_tempo) para dados já validados e tipados.
Sem diagnóstico de parsing - apenas carregamento, filtro e exibição.
"""

from __future__ import annotations

import logging
import math
from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

from src.presentation.pages.sales_shared import (
    format_brl,
    log_df_shape,
    load_sales_data_cached,
    to_excel_bytes,
)

logger = logging.getLogger(__name__)

# --- CONFIGURAÇÃO ---
ITENS_POR_PAGINA_OPCOES = [10, 20, 50, 100]


def _apply_filters(
    df: pd.DataFrame,
    data_inicio: date,
    data_fim: date,
    clientes: list[str],
    meses_referencia: list[str] | None = None,
) -> pd.DataFrame:
    """Aplica filtros de data e cliente.
    
    Args:
        df: DataFrame do gold layer
        data_inicio: Data inicial do período
        data_fim: Data final do período
        clientes: Lista de clientes selecionados (vazio = todos)
        
    Returns:
        DataFrame filtrado
    """
    df_filtered = df.copy()
    log_df_shape("faturamento:filters:start", df_filtered, ["num_venda", "data", "mes_referencia"])
    nat_before = int(pd.to_datetime(df_filtered.get("data", pd.Series(dtype="object")), errors="coerce").isna().sum())
    logger.info("[diag] faturamento:filters:start_nat_data=%d", nat_before)

    # Filtro de Data
    if data_inicio:
        before = len(df_filtered)
        df_filtered = df_filtered[df_filtered["data"].dt.date >= data_inicio]
        logger.info("[diag] faturamento:filter:data_inicio before=%d after=%d", before, len(df_filtered))

    if data_fim:
        before = len(df_filtered)
        df_filtered = df_filtered[df_filtered["data"].dt.date <= data_fim]
        logger.info("[diag] faturamento:filter:data_fim before=%d after=%d", before, len(df_filtered))

    # Filtro de Cliente
    if clientes:
        before = len(df_filtered)
        df_filtered = df_filtered[df_filtered["cliente"].isin(clientes)]
        logger.info("[diag] faturamento:filter:clientes before=%d after=%d", before, len(df_filtered))

    # Filtro de mês de referência (YYYY-MM)
    if meses_referencia:
        before = len(df_filtered)
        df_filtered = df_filtered[df_filtered["mes_referencia"].isin(meses_referencia)]
        logger.info("[diag] faturamento:filter:mes_referencia before=%d after=%d", before, len(df_filtered))

    log_df_shape("faturamento:filters:end", df_filtered, ["num_venda", "data", "mes_referencia"])
    return df_filtered


def _normalize_data(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize loaded sales data for stable filtering and display."""
    out = df.copy()
    out["data"] = pd.to_datetime(out.get("data", pd.Series(dtype=object)), errors="coerce")
    if "cliente" not in out.columns:
        out["cliente"] = "N/A"
    out["cliente"] = out["cliente"].fillna("N/A").astype(str).str.strip().str.upper()

    if "mes_referencia" not in out.columns:
        out["mes_referencia"] = out["data"].dt.to_period("M").astype(str)
    out["mes_referencia"] = (
        out["mes_referencia"]
        .fillna("sem_mes")
        .astype(str)
        .replace({"NaT": "sem_mes", "nat": "sem_mes", "": "sem_mes"})
    )
    out["_invalid_date"] = out["data"].isna()
    return out


def _paginate_dataframe(df: pd.DataFrame, page: int, page_size: int) -> pd.DataFrame:
    """Retorna slice de dados para a página atual."""
    start = (page - 1) * page_size
    end = start + page_size
    return df.iloc[start:end]


def show_faturamento() -> None:
    """Renderiza página de faturamento com dados do gold layer."""
    st.header("💹 Faturamento")
    st.caption("Exploração de dados de vendas com filtros por data e cliente.")

    # Carregar dados do gold layer
    sales_df = load_sales_data_cached()
    if sales_df is None or sales_df.empty:
        st.warning("⚠️ Nenhum dado de vendas encontrado.")
        return

    # Preparar base para filtro
    df_base = _normalize_data(sales_df)
    invalid_date_rows = int(df_base.get("_invalid_date", pd.Series(dtype=bool)).sum())
    if invalid_date_rows:
        st.warning(
            f"{invalid_date_rows} registro(s) com data inválida. Revise parsing/arquivo para evitar perdas em filtros por data."
        )

    # === FILTROS ===
    with st.container():
        st.subheader("Filtros")
        c1, c2, c3 = st.columns([1, 1, 2])

        # Determinar range de datas disponível
        if not df_base["data"].isnull().all():
            min_date_avail = df_base["data"].min().date()
            max_date_avail = df_base["data"].max().date()
        else:
            min_date_avail = date.today()
            max_date_avail = date.today()

        with c1:
            data_inicio = st.date_input(
                "Data Inicial",
                value=min_date_avail,
                min_value=min_date_avail,
                max_value=max_date_avail,
                format="DD/MM/YYYY",
            )
        with c2:
            data_fim = st.date_input(
                "Data Final",
                value=max_date_avail,
                min_value=min_date_avail,
                max_value=max_date_avail,
                format="DD/MM/YYYY",
            )

        with c3:
            lista_clientes = sorted(df_base["cliente"].unique().tolist())
            clientes_selecionados = st.multiselect(
                "Plataformas", options=lista_clientes, placeholder="Todas as plataformas"
            )

        meses_disponiveis = sorted(
            [m for m in df_base["mes_referencia"].dropna().astype(str).unique().tolist() if m and m != "sem_mes"]
        )
        meses_selecionados = st.multiselect(
            "Mês de Referência",
            options=meses_disponiveis,
            default=meses_disponiveis,
            placeholder="Todos os meses",
        )

    # Aplicar filtros
    df_filtered = _apply_filters(
        df_base, data_inicio, data_fim, clientes_selecionados, meses_selecionados
    )
    if df_filtered.empty and invalid_date_rows:
        st.info("Filtro retornou vazio e há datas inválidas na base carregada.")

    # Métricas agregadas
    # Prefer faturamento bruto (matches CSV 'Valor Bruto'); fallback keeps compatibility.
    valor_base = "valor_bruto" if "valor_bruto" in df_filtered.columns else "valor_total"
    faturamento_total = df_filtered.get(valor_base, pd.Series(dtype=float)).sum()
    total_registros = len(df_filtered)

    st.markdown("---")
    st.markdown(
        f"### Faturamento: **{format_brl(faturamento_total)}**\n "
        f"#### Número de Vendas: {total_registros}"
    )
    base_label = "Valor Bruto" if valor_base == "valor_bruto" else "Valor Total"
    st.caption(f"Base do cálculo do total: {base_label}")

    # === PAGINAÇÃO ===
    c_page, c_size = st.columns([2, 5])
    with c_size:
        page_size = st.selectbox(
            "Itens por página", ITENS_POR_PAGINA_OPCOES, index=1
        )

    total_pages = math.ceil(total_registros / page_size) if total_registros > 0 else 1

    with c_page:
        page = st.number_input(
            "Página", min_value=1, max_value=total_pages, value=1
        )

    # Slice para exibição
    df_page = _paginate_dataframe(df_filtered, page, page_size).copy()

    # Formatação para exibição
    df_display = df_page.copy()
    if not df_display.empty:
        if "data" in df_display.columns:
            df_display["Data"] = df_display["data"].dt.strftime("%d/%m/%Y")
        if "valor_total" in df_display.columns:
            df_display["Valor Total"] = [format_brl(v) for v in df_display["valor_total"].tolist()]
        valor_unit_col = "valor_unit" if "valor_unit" in df_display.columns else "valor_unitario"
        if valor_unit_col in df_display.columns:
            df_display["Valor Unit"] = [format_brl(v) for v in df_display[valor_unit_col].tolist()]
        qtd_col = "qtd" if "qtd" in df_display.columns else "quantidade"
        if qtd_col in df_display.columns:
            qtd_num = pd.to_numeric(df_display[qtd_col], errors="coerce")
            is_int = qtd_num.notna() & np.isclose(qtd_num, np.floor(qtd_num))
            qtd_fmt = np.where(is_int, qtd_num.fillna(0).astype("int64").astype(str), qtd_num.map(lambda x: f"{x:.2f}" if pd.notna(x) else ""))
            df_display["Qtd"] = pd.Series(qtd_fmt, index=df_display.index)
    else:
        df_display["Data"] = []
        df_display["Valor Total"] = []
        df_display["Valor Unit"] = []
        df_display["Qtd"] = []

    # Seleção e renomeação de colunas finais
    colunas_para_exibir = []
    mapeamento = {}
    
    if "Data" in df_display.columns:
        colunas_para_exibir.append("Data")
        mapeamento["Data"] = "Data"
    if "cliente" in df_display.columns:
        colunas_para_exibir.append("cliente")
        mapeamento["cliente"] = "Cliente"
    if "produto" in df_display.columns:
        colunas_para_exibir.append("produto")
        mapeamento["produto"] = "Produto"
    if "Qtd" in df_display.columns:
        colunas_para_exibir.append("Qtd")
        mapeamento["Qtd"] = "Qtd"
    if "Valor Unit" in df_display.columns:
        colunas_para_exibir.append("Valor Unit")
        mapeamento["Valor Unit"] = "Valor Unit"
    if "Valor Total" in df_display.columns:
        colunas_para_exibir.append("Valor Total")
        mapeamento["Valor Total"] = "Valor Total"

    # Exibir Tabela
    if colunas_para_exibir:
        st.dataframe(
            df_display[colunas_para_exibir].rename(columns=mapeamento),
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("Nenhuma coluna para exibir.")

    # === EXPORTAÇÃO ===
    if not df_filtered.empty:
        col_csv, col_xlsx = st.columns(2)
        csv_data = df_filtered.to_csv(index=False).encode("utf-8")
        with col_csv:
            st.download_button(
                label="⬇️ Baixar CSV",
                data=csv_data,
                file_name="faturamento_filtrado.csv",
                mime="text/csv",
                width="stretch",
            )

        xlsx_data = to_excel_bytes(df_filtered)
        with col_xlsx:
            st.download_button(
                label="⬇️ Baixar Excel",
                data=xlsx_data,
                file_name="faturamento_filtrado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )

