"""Página de faturamento focada em auditoria e exploração de dados brutos.

FASES 1-6 de Correção: Diagnóstico robusto de parsing de datas e filtros.

Pipeline:
    Load → Diagnose → Normalize (com parser robusto) → Filter → Paginate → Render
"""

from __future__ import annotations

import logging
import math
from datetime import date

import pandas as pd
import streamlit as st

from src.presentation.pages.sales_shared import (
    format_brl,
    load_sales_data_cached,
    to_excel_bytes,
)

logger = logging.getLogger(__name__)

# --- CONFIGURAÇÃO ---
ITENS_POR_PAGINA_OPCOES = [10, 20, 50, 100]


# ============================================================================
# FASE 1: DIAGNÓSTICO E ANÁLISE DE PARSING
# ============================================================================


def _diagnose_date_parsing(df_raw: pd.DataFrame) -> dict:
    """FASE 1: Diagnóstico completo do parsing de datas.
    
    Compara 3 formatos diferentes para identificar qual é mais válido.
    
    Returns:
        dict com informações de parsing para cada formato
    """
    if "data" not in df_raw.columns:
        return {"error": "Coluna 'data' não encontrada"}
    
    # Amostra bruta para inspeção
    amostra_bruta = df_raw["data"].head(20).tolist()
    
    # Test 1: Formato US (mm/dd/yyyy) - comum em arquivos Excel
    test_us = pd.to_datetime(df_raw["data"], format="%m/%d/%Y", errors="coerce")
    count_us = test_us.notna().sum()
    
    # Test 2: Formato BR (dd/mm/yyyy) - padrão brasileiro
    test_br = pd.to_datetime(df_raw["data"], format="%d/%m/%Y", errors="coerce")
    count_br = test_br.notna().sum()
    
    # Test 3: Parsing automático - infer_datetime_format
    test_auto = pd.to_datetime(df_raw["data"], errors="coerce")
    count_auto = test_auto.notna().sum()
    
    # Identifica melhor formato
    melhor = max(
        ("US", count_us),
        ("BR", count_br),
        ("AUTO", count_auto),
        key=lambda x: x[1],
    )[0]
    
    return {
        "amostra_bruta": amostra_bruta,
        "total_registros": len(df_raw),
        "formato_us_valido": count_us,
        "formato_br_valido": count_br,
        "formato_auto_valido": count_auto,
        "melhor_formato": melhor,
    }


# ============================================================================
# FASE 2: PARSER ROBUSTO E NORMALIZAÇÃO
# ============================================================================


def _parse_date_safe(date_series: pd.Series) -> pd.Series:
    """FASE 2.1: Parser robusto para múltiplos formatos de data.
    
    Estratégia:
    1. Tenta formato US (mm/dd/yyyy) primeiro (mais comum em CSVs)
    2. Fallback para parsing automático em casos não parseados
    3. Nunca deixa NaT silencioso - registra em log
    
    Args:
        date_series: Series com strings de data
        
    Returns:
        Series com Timestamps parseados
    """
    # Tentativa 1: Formato US (mm/dd/yyyy)
    parsed = pd.to_datetime(date_series, format="%m/%d/%Y", errors="coerce")
    
    # Fallback: casos não parseados
    mask = parsed.isna()
    if mask.any():
        parsed_fallback = pd.to_datetime(
            date_series[mask], 
            errors="coerce",
            dayfirst=False  # Não assume brasileiro por enquanto
        )
        parsed.loc[mask] = parsed_fallback
    
    return parsed


def _normalize_data(df: pd.DataFrame) -> pd.DataFrame:
    """FASE 2.2: Normalização com parser robusto (sem silenciar NaT).
    
    Processa:
    - Textos (cliente, produto, categoria)
    - Datas com parser robusto
    - Numéricos com fallback a 0.0
    - Validação de integridade
    
    Args:
        df: DataFrame bruto
        
    Returns:
        DataFrame normalizado
    """
    df = df.copy()

    # ===== TEXTOS =====
    if "cliente" in df.columns:
        df["cliente"] = df["cliente"].fillna("").astype(str).str.strip().str.upper()
    else:
        df["cliente"] = "N/A"

    if "produto" in df.columns:
        df["produto"] = df["produto"].fillna("").astype(str).str.strip()
    else:
        df["produto"] = "N/A"

    if "categoria" not in df.columns:
        df["categoria"] = "N/A"

    # ===== DATAS (com parser robusto FASE 2.1) =====
    if "data" in df.columns:
        df["data"] = _parse_date_safe(df["data"].astype(str))
        
        # FASE 4.1: Log de erros (hardening)
        invalid_count = df["data"].isna().sum()
        if invalid_count > 0:
            logger.warning(
                f"_normalize_data: {invalid_count} datas inválidas detectadas "
                f"({100 * invalid_count / len(df):.1f}% da base)"
            )
    else:
        df["data"] = pd.NaT

    # ===== NUMÉRICOS =====
    cols_numericas = ["qtd", "valor_venda", "valor_total", "lucro_est", "custo_unit"]
    for col in cols_numericas:
        if col not in df.columns:
            df[col] = 0.0
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Garante valor_total válido (FASE 2.2: Task 2.3)
    mask_recalc = df["valor_total"] <= 0
    if mask_recalc.any():
        df.loc[mask_recalc, "valor_total"] = (
            df.loc[mask_recalc, "valor_venda"] * df.loc[mask_recalc, "qtd"]
        )

    # FASE 4.2: Assert de integridade
    valid_date_ratio = df["data"].notna().mean()
    if valid_date_ratio < 0.99:
        logger.warning(
            f"_normalize_data: Integridade comprometida. "
            f"Apenas {valid_date_ratio:.2%} de datas válidas"
        )

    return df


# ============================================================================
# FASE 3, 6: FILTROS E PAGINAÇÃO
# ============================================================================


def _apply_filters(
    df: pd.DataFrame, data_inicio: date, data_fim: date, clientes: list[str]
) -> pd.DataFrame:
    """FASE 3, 6: Aplica filtros de data e cliente sobre DataFrame normalizado.
    
    Importante: Sempre trabalha sobre cópia para não mutar original.
    Nunca filtra antes de validar datas.
    
    Args:
        df: DataFrame normalizado
        data_inicio: Data inicial do período (ou None)
        data_fim: Data final do período (ou None)
        clientes: Lista de clientes selecionados (ou vazio para todos)
        
    Returns:
        DataFrame filtrado (cópia)
    """
    df_filtered = df.copy()

    # Filtro de Data
    if data_inicio:
        df_filtered = df_filtered[df_filtered["data"].dt.date >= data_inicio]

    if data_fim:
        df_filtered = df_filtered[df_filtered["data"].dt.date <= data_fim]

    # Filtro de Cliente
    if clientes:
        df_filtered = df_filtered[df_filtered["cliente"].isin(clientes)]

    return df_filtered


def _paginate_dataframe(df: pd.DataFrame, page: int, page_size: int) -> pd.DataFrame:
    """Retorna apenas o slice de dados para a página atual.
    
    Args:
        df: DataFrame completo (já filtrado)
        page: Número da página (1-indexed)
        page_size: Itens por página
        
    Returns:
        Slice do DataFrame para exibição
    """
    start = (page - 1) * page_size
    end = start + page_size
    return df.iloc[start:end]


# ============================================================================
# UI PRINCIPAL
# ============================================================================


def show_faturamento() -> None:
    """Renderiza página de auditoria com diagnóstico robusto de parsing.
    
    FASES 1-6:
    - FASE 1: Diagnóstico de parsing
    - FASE 2: Normalização com parser robusto
    - FASE 3: Aplicação de filtros
    - FASE 4: Hardening (logs e validação)
    - FASE 5: Estrutura correta (parse → normalize → filter → paginate)
    - FASE 6: Integração completa com UI
    """
    st.header("💹 Faturamento (Auditoria)")
    st.caption("Exploração detalhada com diagnóstico robusto de parsing de datas (Fases 1-6).")

    # === FASE 1: Carregamento e Diagnóstico ===
    df_raw = load_sales_data_cached()

    if df_raw is None or df_raw.empty:
        st.warning("⚠️ Nenhum dado de vendas encontrado.")
        return

    # Executar diagnóstico (FASE 1)
    diagnostic_info = _diagnose_date_parsing(df_raw)

    # === FASE 2: Normalização com parser robusto ===
    df_base = _normalize_data(df_raw)

    # === FASE 3, 6: Controles de Filtros ===
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
                "Clientes", options=lista_clientes, placeholder="Todos os clientes"
            )

    # === FASE 3: Aplicação de Filtros ===
    df_filtered = _apply_filters(
        df_base, data_inicio, data_fim, clientes_selecionados
    )

    # === FASE 6: Métricas Agregadas ===
    faturamento_total = df_filtered["valor_total"].sum()
    total_registros = len(df_filtered)

    st.markdown("---")
    st.markdown(
        f"### Total Filtrado: **{format_brl(faturamento_total)}** ({total_registros} registros)"
    )

    # === FASE 6: Paginação ===
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

    # === FASE 6: Slice para exibição ===
    df_page = _paginate_dataframe(df_filtered, page, page_size).copy()

    # === FASE 6: Formatação para Exibição ===
    df_display = df_page.copy()
    if not df_display.empty:
        df_display["Data"] = df_display["data"].dt.strftime("%d/%m/%Y")
        df_display["Valor Total"] = df_display["valor_total"].apply(format_brl)
        df_display["Valor Unit"] = df_display["valor_venda"].apply(format_brl)
        df_display["Qtd"] = df_display["qtd"].apply(
            lambda x: f"{int(x)}" if x.is_integer() else f"{x:.2f}"
        )
    else:
        # Garante colunas mesmo vazio
        df_display["Data"] = []
        df_display["Valor Total"] = []
        df_display["Valor Unit"] = []
        df_display["Qtd"] = []

    # Seleção e renomeação de colunas finais
    colunas_finais = {
        "Data": "Data",
        "cliente": "Cliente",
        "produto": "Produto",
        "categoria": "Categoria",
        "Qtd": "Qtd",
        "Valor Unit": "Valor Unit",
        "Valor Total": "Valor Total",
    }

    # Exibir Tabela
    st.dataframe(
        df_display[list(colunas_finais.keys())].rename(columns=colunas_finais),
        width="stretch",
        hide_index=True,
    )

    # =========================================================================
    # DIAGNÓSTICO COMPLETO E VALIDAÇÃO (FASES 1-4)
    # =========================================================================
    with st.expander("🔍 Diagnóstico Completo de Parsing e Integridade de Dados"):
        
        # === FASE 1: Inspeção de dados brutos ===
        st.subheader("FASE 1: Inspeção de Dados Brutos")
        st.write("**Amostra das primeiras 5 datas (formato raw do CSV):**")
        st.code(str(diagnostic_info.get("amostra_bruta", [])[:5]))

        # === FASE 1.3: Comparação de interpretações ===
        st.subheader("FASE 1.3: Comparação de Interpretações de Formato")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "Formato US\n(mm/dd/yyyy)",
                diagnostic_info.get("formato_us_valido", 0),
            )
        with col2:
            st.metric(
                "Formato BR\n(dd/mm/yyyy)",
                diagnostic_info.get("formato_br_valido", 0),
            )
        with col3:
            st.metric(
                "Formato AUTO",
                diagnostic_info.get("formato_auto_valido", 0),
            )

        best_fmt = diagnostic_info.get("melhor_formato", "UNKNOWN")
        st.success(f"✅ Formato predominante identificado: **{best_fmt}**")

        # === FASE 2-3: Contadores principais de integridade ===
        st.subheader("FASE 2-3: Contadores de Integridade de Dados")
        col_a, col_b, col_c, col_d = st.columns(4)

        with col_a:
            st.metric("Total RAW\n(Carregado)", len(df_raw))
        with col_b:
            st.metric("Total BASE\n(Normalizado)", len(df_base))
        with col_c:
            valid_dates = df_base["data"].notna().sum()
            st.metric("Datas Válidas", valid_dates)
        with col_d:
            invalid_dates = df_base["data"].isna().sum()
            if invalid_dates > 0:
                st.metric("⚠️ Datas Inválidas", invalid_dates)
            else:
                st.metric("✅ Datas Inválidas", invalid_dates)

        # === FASE 3: Distribuição mensal ===
        st.subheader("FASE 3: Distribuição Mensal de Registros")
        if not df_base["data"].isna().all():
            monthly_dist = df_base["data"].dt.to_period("M").value_counts().sort_index()
            st.bar_chart(monthly_dist, use_container_width=True)
            st.write("**Contagem por mês:**")
            st.dataframe(
                monthly_dist.reset_index()
                .rename(columns={"data": "Mês", "count": "Total Registros"}),
                hide_index=True,
            )
        else:
            st.warning("⚠️ Nenhuma data válida para distribuição mensal")

        # === FASE 3.1: Teste isolado (fevereiro 2026) ===
        st.subheader("FASE 3.1: Teste Isolado - Fevereiro 2026")
        st.write("Esperado: ~3348 registros (validação do parsing)")
        try:
            df_fev = df_base[
                (df_base["data"] >= "2026-02-01")
                & (df_base["data"] <= "2026-02-28")
            ]
            st.metric("Registros encontrados em Fevereiro", len(df_fev))
            
            if len(df_fev) < 100:
                st.error(
                    f"❌ FALHA DE PARSING: Apenas {len(df_fev)} registros em fevereiro. "
                    "Se esperava ~3348, há problema crítico no parsing de datas. "
                    "Verifique o formato no CSV."
                )
            elif len(df_fev) < 2000:
                st.warning(
                    f"⚠️ PARCIALMENTE OK: {len(df_fev)} registros encontrados. "
                    "Mais que 100, mas inferior ao esperado de ~3348."
                )
            else:
                st.success(
                    f"✅ PARSING CORRETO: {len(df_fev)} registros em fevereiro "
                    "(próximo do esperado de ~3348)"
                )
        except Exception as e:
            st.error(f"❌ Erro ao filtrar fevereiro: {e}")

        # === FASE 2.3: Exemplo de dados normalizados ===
        st.subheader("FASE 2.3: Amostra de Dados Normalizados (primeiras 10 linhas)")
        if not df_base.empty:
            st.dataframe(
                df_base[["data", "cliente", "produto", "valor_total"]].head(10),
                hide_index=True,
            )

    # === FASE 6: Exportação ===
    col_csv, col_xlsx = st.columns(2)
    if not df_filtered.empty:
        csv_data = df_filtered.to_csv(index=False).encode("utf-8")
        with col_csv:
            st.download_button(
                label="⬇️ Baixar CSV",
                data=csv_data,
                file_name="faturamento_filtrado.csv",
                mime="text/csv",
                use_container_width=True,
            )

        xlsx_data = to_excel_bytes(df_filtered)
        with col_xlsx:
            st.download_button(
                label="⬇️ Baixar Excel",
                data=xlsx_data,
                file_name="faturamento_filtrado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

