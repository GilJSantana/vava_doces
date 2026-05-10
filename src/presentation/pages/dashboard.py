"""Dashboard executivo de rentabilidade e concentração de receita."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from pandas.api.types import is_datetime64_any_dtype
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.infrastructure.drive_manager import load_parquet_from_drive
from src.domain.sales_analysis_service import _normalise_value
from src.presentation.components import render_separator
from src.presentation.pages.sales_shared import inject_roboto_font, load_sales_data_cached

logger = logging.getLogger(__name__)

# Vava Doces visual identity (dark-theme friendly).
_QUADRANT_COLORS = {
    "ESTRELAS": "#2ecc71",        # Verde esmeralda (sucesso)
    "VACAS_LEITEIRAS": "#3498db", # Azul/ciano (estabilidade)
    "DILEMAS": "#9b59b6",         # Roxo/lilas (potencial)
    "PROBLEMAS": "#e74c3c",       # Vermelho/rosa forte (alerta)
}
_BRAND_MARGIN_COLORSCALE = [
    (0.0, "#EC4899"),
    (0.5, "#F9A8D4"),
    (1.0, "#14B8A6"),
]
_MAX_SCATTER_POINTS = 800
_MAX_REASONABLE_MARGIN_PERCENT = 100.0
_PRODUCT_KEY_CANDIDATES = ("produto_id", "id_produto", "produto_key")
_BRAND_PRIMARY_BLUE = "#4f83cc"
_BRAND_TREND_BLUE = "#60a5fa"
_BRAND_ACCENT_ORANGE = "#f5a623"
_BRAND_PEAK_ORANGE = "#f97316"


def _safe_num(series: pd.Series | None, fill: float | None = 0.0) -> pd.Series:
    if series is None:
        return pd.Series(dtype="float64")
    out = pd.Series(pd.to_numeric(series, errors="coerce"), index=series.index)
    if fill is not None:
        out = out.fillna(fill)
    return out


def _normalize_join_key(series: pd.Series | None) -> pd.Series:
    """Normalize merge keys across mixed numeric/string sources."""
    if series is None:
        return pd.Series(dtype="string")
    out = pd.Series(series, index=series.index, dtype="string")
    out = out.str.strip().str.upper()
    out = out.str.replace(r"\.0+$", "", regex=True)
    out = out.replace({"": pd.NA, "<NA>": pd.NA, "NAN": pd.NA, "NONE": pd.NA})
    return out


def _sample_keys(series: pd.Series | None, limit: int = 3) -> list[str]:
    if series is None:
        return []
    cleaned = _normalize_join_key(series).dropna().astype(str)
    return cleaned.head(limit).tolist()


def _normalize_name_key(series: pd.Series | None) -> pd.Series:
    if series is None:
        return pd.Series(dtype="string")
    out = pd.Series(series, index=series.index, dtype="string")
    out = out.fillna("").astype(str).map(_normalise_value)
    out = pd.Series(out, index=series.index, dtype="string")
    out = out.replace({"": pd.NA, "nan": pd.NA, "none": pd.NA})
    return out


def _stabilize_profitability_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Avoid impossible profitability values caused by invalid divisors or source noise."""
    if df.empty:
        return df

    out = df.copy()
    preco_unit = _safe_num(out.get("preco_venda_unitario"), fill=None)
    custo_unit = _safe_num(out.get("custo_producao_unitario"), fill=None)
    invalid_mask = preco_unit.isna() | preco_unit.le(0) | custo_unit.isna() | custo_unit.le(0)

    if "margem_valor" in out.columns:
        out.loc[invalid_mask, "margem_valor"] = np.nan
    if "margem_perc" in out.columns:
        out.loc[invalid_mask, "margem_perc"] = np.nan
        unreasonable_positive_mask = out["margem_perc"].gt(_MAX_REASONABLE_MARGIN_PERCENT)
        if unreasonable_positive_mask.any():
            logger.warning(
                "DEBUG RENTABILIDADE: %d margem(ns) acima de %.1f%% foram limitadas",
                int(unreasonable_positive_mask.sum()),
                _MAX_REASONABLE_MARGIN_PERCENT,
            )
            out.loc[unreasonable_positive_mask, "margem_perc"] = _MAX_REASONABLE_MARGIN_PERCENT
    if "markup" in out.columns:
        out.loc[invalid_mask, "markup"] = np.nan
    return out


def _normalize_margin_percent(series: pd.Series | None) -> pd.Series:
    """Normalize mixed margin scales to percentage points.

    If values look like decimals (-1..1), convert to percent by *100.
    Existing percentage values are preserved.
    """
    vals = _safe_num(series, fill=None)
    if vals.empty:
        return vals
    decimal_mask = vals.notna() & vals.abs().le(1.0)
    out = vals.copy()
    out.loc[decimal_mask] = out.loc[decimal_mask] * 100.0
    return out


def _invalidate_metrics_without_cost(df: pd.DataFrame) -> pd.DataFrame:
    """Mark profitability metrics as unknown when source cost is missing (null lineage)."""
    if df.empty or "custo_producao_unitario" not in df.columns:
        return df

    out = df.copy()
    audit_col = out.get("custo_producao_unitario_audit")
    if audit_col is not None:
        missing_cost_mask = _safe_num(audit_col, fill=None).isna()
    else:
        missing_cost_mask = _safe_num(out.get("custo_producao_unitario"), fill=None).isna()

    if "margem_perc" in out.columns:
        out.loc[missing_cost_mask, "margem_perc"] = np.nan
    if "markup" in out.columns:
        out.loc[missing_cost_mask, "markup"] = np.nan
    if "item_auditoria" in out.columns:
        out["item_auditoria"] = out["item_auditoria"].fillna(False) | missing_cost_mask
    else:
        out["item_auditoria"] = missing_cost_mask
    return out


def _fmt_currency(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "⚠️ Audit Needed"
    text = f"{float(value):,.2f}"
    text = text.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {text}"


def _fmt_percent(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "⚠️ Audit Needed"
    return f"{float(value):.2f}".replace(".", ",") + "%"


def _render_plot(fig) -> None:
    # Remove export action from Plotly toolbar to keep dashboard focused on analysis.
    st.plotly_chart(fig, width="stretch", config={"modeBarButtonsToRemove": ["toImage"]})


def _period_title_suffix(selected_months: list[str], available_months: list[str]) -> str:
    if not selected_months:
        return "(sem periodo selecionado)"
    if available_months and len(selected_months) == len(available_months):
        return "(todos os meses)"
    if len(selected_months) == 1:
        return f"({selected_months[0]})"
    return f"({len(selected_months)} meses selecionados)"


def _load_gold_optional(name: str) -> pd.DataFrame:
    return load_parquet_from_drive(f"{name}.parquet")


def _build_sales_agg_from_sales_df(sales_df: pd.DataFrame | None) -> pd.DataFrame:
    """Build product-level sales aggregation from the shared cached sales dataframe."""
    if sales_df is None or sales_df.empty:
        logger.info("DEBUG RENTABILIDADE: sales_df compartilhado vazio/None na agregacao")
        return pd.DataFrame()

    df = sales_df.copy()
    logger.info("DEBUG RENTABILIDADE: sales_df bruto antes da agregacao linhas=%d", len(df))

    if "data" in df.columns:
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
        nat_count = int(df["data"].isna().sum())
        logger.info(
            "DEBUG RENTABILIDADE: dtype data apos cast=%s nat_data=%d",
            df["data"].dtype,
            nat_count,
        )

    qty_col = "qtd" if "qtd" in df.columns else ("quantidade" if "quantidade" in df.columns else None)
    revenue_col = (
        "faturamento_liquido"
        if "faturamento_liquido" in df.columns
        else ("valor_total" if "valor_total" in df.columns else ("valor_venda" if "valor_venda" in df.columns else None))
    )
    if qty_col is None or revenue_col is None:
        logger.warning(
            "DEBUG RENTABILIDADE: sem colunas obrigatorias para agregacao qty=%s revenue=%s",
            qty_col,
            revenue_col,
        )
        return pd.DataFrame()

    key_col = next((c for c in _PRODUCT_KEY_CANDIDATES if c in df.columns), None)
    if key_col is None:
        logger.warning("DEBUG RENTABILIDADE: sales_df sem coluna de chave de produto. candidatos=%s", _PRODUCT_KEY_CANDIDATES)
        return pd.DataFrame()
    logger.info("DEBUG RENTABILIDADE: chave de produto selecionada na origem=%s", key_col)

    df["produto_id"] = _normalize_join_key(df.get(key_col))

    before_drop = len(df)
    df = df.loc[df["produto_id"].notna()].copy()
    logger.info(
        "DEBUG RENTABILIDADE: filtro produto_id.notna() before=%d after=%d",
        before_drop,
        len(df),
    )
    if df.empty:
        return pd.DataFrame()

    if "produto" not in df.columns:
        df["produto"] = df["produto_id"].astype(str)

    agg_produto = (
        df.groupby(["produto_id", "produto"], as_index=False, dropna=False)
        .agg(qtd_vendida=(qty_col, "sum"), faturamento_liquido=(revenue_col, "sum"))
        .rename(columns={"produto_id": "id_produto", "produto": "nome_produto"})
    )
    logger.info("DEBUG RENTABILIDADE: agg_produto derivado do sales_df linhas=%d", len(agg_produto))
    return agg_produto


def _compute_revenue_total_from_sales(
    sales_df: pd.DataFrame | None,
    selected_months: list[str] | None,
) -> float | None:
    """Compute dashboard revenue KPI from transactional sales source-of-truth."""
    if sales_df is None or sales_df.empty:
        return None
    df = sales_df.copy()
    if selected_months is not None:
        if not selected_months:
            return 0.0
        if "mes_referencia" in df.columns:
            df = df[df["mes_referencia"].astype(str).isin(selected_months)].copy()
    if df.empty:
        return 0.0

    revenue_col = (
        "faturamento_liquido"
        if "faturamento_liquido" in df.columns
        else ("valor_total" if "valor_total" in df.columns else ("valor_venda" if "valor_venda" in df.columns else None))
    )
    if revenue_col is None:
        return None
    return float(_safe_num(df.get(revenue_col), fill=0.0).sum())


def _build_sales_agg_from_sales_df(sales_df: pd.DataFrame | None) -> pd.DataFrame:
    """Build product-level sales aggregation from the shared cached sales dataframe."""
    if sales_df is None or sales_df.empty:
        logger.info("DEBUG RENTABILIDADE: sales_df compartilhado vazio/None na agregacao")
        return pd.DataFrame()

    df = sales_df.copy()
    logger.info("DEBUG RENTABILIDADE: sales_df bruto antes da agregacao linhas=%d", len(df))

    if "data" in df.columns:
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
        nat_count = int(df["data"].isna().sum())
        logger.info(
            "DEBUG RENTABILIDADE: dtype data apos cast=%s nat_data=%d",
            df["data"].dtype,
            nat_count,
        )

    qty_col = "qtd" if "qtd" in df.columns else ("quantidade" if "quantidade" in df.columns else None)
    revenue_col = (
        "faturamento_liquido"
        if "faturamento_liquido" in df.columns
        else ("valor_total" if "valor_total" in df.columns else ("valor_venda" if "valor_venda" in df.columns else None))
    )
    if qty_col is None or revenue_col is None:
        logger.warning(
            "DEBUG RENTABILIDADE: sem colunas obrigatorias para agregacao qty=%s revenue=%s",
            qty_col,
            revenue_col,
        )
        return pd.DataFrame()

    key_col = next((c for c in _PRODUCT_KEY_CANDIDATES if c in df.columns), None)
    if key_col is None:
        logger.warning("DEBUG RENTABILIDADE: sales_df sem coluna de chave de produto. candidatos=%s", _PRODUCT_KEY_CANDIDATES)
        return pd.DataFrame()
    logger.info("DEBUG RENTABILIDADE: chave de produto selecionada na origem=%s", key_col)

    df["produto_id"] = _normalize_join_key(df.get(key_col))

    before_drop = len(df)
    df = df.loc[df["produto_id"].notna()].copy()
    logger.info(
        "DEBUG RENTABILIDADE: filtro produto_id.notna() before=%d after=%d",
        before_drop,
        len(df),
    )
    if df.empty:
        return pd.DataFrame()

    if "produto" not in df.columns:
        df["produto"] = df["produto_id"].astype(str)

    agg_produto = (
        df.groupby(["produto_id", "produto"], as_index=False, dropna=False)
        .agg(qtd_vendida=(qty_col, "sum"), faturamento_liquido=(revenue_col, "sum"))
        .rename(columns={"produto_id": "id_produto", "produto": "nome_produto"})
    )
    logger.info("DEBUG RENTABILIDADE: agg_produto derivado do sales_df linhas=%d", len(agg_produto))
    return agg_produto


def _apply_month_filter(
    profitability_df: pd.DataFrame,
    sales_df: pd.DataFrame | None,
    selected_months: list[str],
) -> pd.DataFrame:
    """Filter profitability base by selected months and recompute month-scoped metrics."""
    if profitability_df.empty:
        return profitability_df
    if sales_df is None or sales_df.empty or "mes_referencia" not in sales_df.columns:
        # Fallback: if no month source is available, keep dataset unchanged.
        return profitability_df
    if not selected_months:
        return profitability_df.iloc[0:0].copy()

    month_agg = _build_month_sales_agg(sales_df, tuple(selected_months))
    if month_agg.empty:
        return profitability_df.iloc[0:0].copy()

    profitability_norm = profitability_df.copy()
    profitability_norm["id_produto"] = _normalize_join_key(profitability_norm.get("id_produto"))
    month_agg = month_agg.copy()
    month_agg["id_produto"] = _normalize_join_key(month_agg.get("id_produto"))
    logger.info(
        "DEBUG RENTABILIDADE: linhas pre-merge mensal profitability=%d month_agg=%d",
        len(profitability_norm),
        len(month_agg),
    )
    logger.debug(
        "DEBUG RENTABILIDADE: sample keys profitability mensal=%s month_agg=%s",
        _sample_keys(profitability_norm.get("id_produto")),
        _sample_keys(month_agg.get("id_produto")),
    )

    out = profitability_norm.merge(
        month_agg[["id_produto", "qtd_vendida", "faturamento_item"]],
        on="id_produto",
        how="inner",
        suffixes=("", "_mes"),
    )
    if out.empty:
        return out

    out["qtd_vendida"] = _safe_num(out.get("qtd_vendida_mes"), fill=0.0)
    out["faturamento_item"] = _safe_num(out.get("faturamento_item_mes"), fill=0.0)
    out["preco_venda_unitario"] = (out["faturamento_item"] / out["qtd_vendida"]).replace([np.inf, -np.inf], np.nan)

    cost_calc = _safe_num(out.get("custo_producao_unitario"), fill=0.0)
    out["margem_valor"] = _safe_num(out.get("preco_venda_unitario"), fill=0.0) - cost_calc
    out["margem_perc"] = ((out["margem_valor"] / out["preco_venda_unitario"]) * 100.0).replace([np.inf, -np.inf], np.nan)
    out["markup"] = (out["preco_venda_unitario"] / cost_calc).replace([np.inf, -np.inf], np.nan)

    drop_cols = [c for c in ["qtd_vendida_mes", "faturamento_item_mes"] if c in out.columns]
    out = out.drop(columns=drop_cols)
    out = _stabilize_profitability_metrics(out)
    return _invalidate_metrics_without_cost(out)


@st.cache_data(ttl=300)
def _build_month_sales_agg(sales_df: pd.DataFrame, selected_months: tuple[str, ...]) -> pd.DataFrame:
    if sales_df is None or sales_df.empty or not selected_months:
        return pd.DataFrame()
    logger.info(
        "DEBUG RENTABILIDADE: filtro mensal entrada linhas=%d meses=%s",
        len(sales_df),
        list(selected_months),
    )
    filtered_sales = sales_df[sales_df["mes_referencia"].astype(str).isin(selected_months)].copy()
    logger.info(
        "DEBUG RENTABILIDADE: filtro mensal mes_referencia before=%d after=%d",
        len(sales_df),
        len(filtered_sales),
    )
    if filtered_sales.empty:
        return pd.DataFrame()
    qty_col = "qtd" if "qtd" in filtered_sales.columns else ("quantidade" if "quantidade" in filtered_sales.columns else None)
    revenue_col = (
        "faturamento_liquido"
        if "faturamento_liquido" in filtered_sales.columns
        else ("valor_total" if "valor_total" in filtered_sales.columns else ("valor_venda" if "valor_venda" in filtered_sales.columns else None))
    )
    key_col = next((c for c in _PRODUCT_KEY_CANDIDATES if c in filtered_sales.columns), None)
    if qty_col is None or revenue_col is None or key_col is None:
        return pd.DataFrame()
    filtered_sales["produto_id"] = _normalize_join_key(filtered_sales.get(key_col))
    filtered_sales = filtered_sales.loc[filtered_sales["produto_id"].notna()].copy()
    if filtered_sales.empty:
        return pd.DataFrame()
    month_agg = (
        filtered_sales.groupby(["produto_id", "produto"], as_index=False)
        .agg(qtd_vendida=(qty_col, "sum"), faturamento_item=(revenue_col, "sum"))
        .rename(columns={"produto_id": "id_produto", "produto": "nome_produto"})
    )
    month_agg["id_produto"] = _normalize_join_key(month_agg["id_produto"])
    return month_agg


@st.cache_data(ttl=1800)
def _build_profitability_base(sales_df: pd.DataFrame | None = None) -> pd.DataFrame:
    if sales_df is None:
        logger.info("DEBUG RENTABILIDADE: sales_df nao informado, usando load_sales_data_cached()")
        sales_df = load_sales_data_cached()

    agg_produto = _build_sales_agg_from_sales_df(sales_df)
    rent = _load_gold_optional("gold_rentabilidade")
    custos = _load_gold_optional("custos_producao_agregado")

    logger.info(
        "DEBUG RENTABILIDADE: linhas vendas=%d rentabilidade=%d custos=%d",
        len(agg_produto),
        len(rent),
        len(custos),
    )
    mapping_error = False
    if not agg_produto.empty and "produto_id" in agg_produto.columns:
        logger.debug("DEBUG RENTABILIDADE: vendas dtypes=\n%s", agg_produto.dtypes)
        logger.debug(
            "DEBUG RENTABILIDADE: vendas keys sample=\n%s",
            agg_produto[["produto_id"]].head(),
        )
        logger.info("DEBUG RENTABILIDADE: sample 3 chaves vendas=%s", _sample_keys(agg_produto.get("produto_id")))
    if not custos.empty and "id_produto" in custos.columns:
        logger.debug("DEBUG RENTABILIDADE: custos dtypes=\n%s", custos.dtypes)
        logger.debug(
            "DEBUG RENTABILIDADE: custos keys sample=\n%s",
            custos[["id_produto"]].head(),
        )
        logger.info("DEBUG RENTABILIDADE: sample 3 chaves custos=%s", _sample_keys(custos.get("id_produto")))

    if agg_produto.empty:
        logger.warning("DEBUG RENTABILIDADE: base de vendas vazia, profitability_df retornara vazio")
        return pd.DataFrame(
            columns=[
                "id_produto",
                "nome_produto",
                "qtd_vendida",
                "faturamento_item",
                "preco_venda_unitario",
                "custo_producao_unitario",
                "margem_valor",
                "margem_perc",
                "markup",
                "item_auditoria",
            ]
        )

    base = agg_produto.copy()
    if "id_produto" not in base.columns and "produto_id" in base.columns:
        base = base.rename(columns={"produto_id": "id_produto"})
    if "id_produto" not in base.columns:
        base["id_produto"] = pd.NA
    base = base.rename(columns={"faturamento_liquido": "faturamento_item"})
    base["id_produto"] = _normalize_join_key(base["id_produto"])
    base["produto_nome_key"] = _normalize_name_key(base.get("nome_produto"))
    base["qtd_vendida"] = _safe_num(base.get("qtd_vendida"), fill=0.0)
    base["faturamento_item"] = _safe_num(base.get("faturamento_item"), fill=0.0)
    base["preco_venda_unitario"] = (base["faturamento_item"] / base["qtd_vendida"]).replace([np.inf, -np.inf], np.nan)

    if not rent.empty and "id_produto" in rent.columns:
        rent_df = rent.copy()
        rent_df["id_produto"] = _normalize_join_key(rent_df["id_produto"])
        rent_df["produto_nome_key"] = _normalize_name_key(rent_df.get("nome_produto"))
        logger.debug("DEBUG RENTABILIDADE: rentabilidade dtypes=\n%s", rent_df.dtypes)
        logger.debug(
            "DEBUG RENTABILIDADE: rentabilidade keys sample=\n%s",
            rent_df[["id_produto"]].head(),
        )
        logger.info("DEBUG RENTABILIDADE: sample 3 chaves rentabilidade=%s", _sample_keys(rent_df.get("id_produto")))
        common_keys = set(base["id_produto"].dropna().unique()).intersection(set(rent_df["id_produto"].dropna().unique()))
        logger.info("DEBUG RENTABILIDADE: chaves em comum vendas x rentabilidade=%d", len(common_keys))
        logger.info(
            "DEBUG RENTABILIDADE: sample chaves em comum vendas x rentabilidade=%s",
            list(sorted(common_keys))[:3],
        )
        if not common_keys:
            logger.error("FALHA CRITICA: sem intersecao de chaves entre vendas e rentabilidade")
            mapping_error = True
        merge_cols = [
            "id_produto",
            "custo_producao_unitario",
            "custo_producao_unitario_audit",
            "margem_valor",
            "margem_perc",
            "markup",
        ]
        merge_cols = [c for c in merge_cols if c in rent_df.columns]
        base = base.merge(rent_df[merge_cols], on="id_produto", how="left")
        metric_cols = [c for c in merge_cols if c != "id_produto"]
        missing_cost_mask = base.get("custo_producao_unitario", pd.Series(index=base.index, dtype="float64")).isna()
        if missing_cost_mask.any() and "produto_nome_key" in rent_df.columns:
            name_merge_cols = ["produto_nome_key", *metric_cols]
            rent_by_name = rent_df[name_merge_cols].copy()
            rent_by_name = rent_by_name.dropna(subset=["produto_nome_key"]).drop_duplicates(subset=["produto_nome_key"], keep="first")
            if not rent_by_name.empty:
                base = base.merge(rent_by_name, on="produto_nome_key", how="left", suffixes=("", "_nome"))
                for col in metric_cols:
                    fallback_col = f"{col}_nome"
                    if fallback_col in base.columns:
                        base[col] = base[col].fillna(base[fallback_col])
                        base = base.drop(columns=[fallback_col])
    else:
        if not custos.empty and {"id_produto", "custo_producao"}.issubset(custos.columns):
            tmp = custos[["id_produto", "custo_producao"]].copy()
            tmp["id_produto"] = _normalize_join_key(tmp["id_produto"])
            tmp = tmp.drop_duplicates(subset=["id_produto"], keep="first")
            common_keys = set(base["id_produto"].dropna().unique()).intersection(set(tmp["id_produto"].dropna().unique()))
            logger.info("DEBUG RENTABILIDADE: chaves em comum vendas x custos=%d", len(common_keys))
            logger.info(
                "DEBUG RENTABILIDADE: sample chaves em comum vendas x custos=%s",
                list(sorted(common_keys))[:3],
            )
            if not common_keys:
                logger.error("FALHA CRITICA: sem intersecao de chaves entre vendas e custos")
                mapping_error = True
            base = base.merge(tmp, on="id_produto", how="left")
            base["custo_producao_unitario"] = _safe_num(base.get("custo_producao"), fill=None)
            if base["custo_producao_unitario"].isna().any() and "nome_produto" in custos.columns:
                tmp_by_name = custos[["nome_produto", "custo_producao"]].copy()
                tmp_by_name["produto_nome_key"] = _normalize_name_key(tmp_by_name.get("nome_produto"))
                tmp_by_name = tmp_by_name.dropna(subset=["produto_nome_key"]).drop_duplicates(subset=["produto_nome_key"], keep="first")
                if not tmp_by_name.empty:
                    base = base.merge(tmp_by_name[["produto_nome_key", "custo_producao"]], on="produto_nome_key", how="left", suffixes=("", "_nome"))
                    base["custo_producao_unitario"] = base["custo_producao_unitario"].fillna(_safe_num(base.get("custo_producao_nome"), fill=None))
                    drop_cols = [c for c in ["custo_producao_nome"] if c in base.columns]
                    if drop_cols:
                        base = base.drop(columns=drop_cols)
        else:
            base["custo_producao_unitario"] = np.nan
        base["custo_producao_unitario_audit"] = base["custo_producao_unitario"]
        custo_calc = _safe_num(base["custo_producao_unitario"], fill=0.0)
        base["margem_valor"] = _safe_num(base["preco_venda_unitario"], fill=0.0) - custo_calc
        base["margem_perc"] = ((base["margem_valor"] / base["preco_venda_unitario"]) * 100.0).replace([np.inf, -np.inf], np.nan)
        base["markup"] = (base["preco_venda_unitario"] / custo_calc).replace([np.inf, -np.inf], np.nan)

    base["nome_produto"] = base.get("nome_produto", base["id_produto"]).fillna(base["id_produto"]).astype(str).str.strip()
    base["item_auditoria"] = base.get("custo_producao_unitario_audit", base["custo_producao_unitario"]).isna()

    keep = [
        "id_produto",
        "nome_produto",
        "qtd_vendida",
        "faturamento_item",
        "preco_venda_unitario",
        "custo_producao_unitario",
        "custo_producao_unitario_audit",
        "margem_valor",
        "margem_perc",
        "markup",
        "item_auditoria",
        "_mapping_error",
    ]
    base["_mapping_error"] = mapping_error
    for col in keep:
        if col not in base.columns:
            base[col] = np.nan
    base = _stabilize_profitability_metrics(base)
    base = _invalidate_metrics_without_cost(base)
    logger.info("DEBUG RENTABILIDADE: profitability_df final linhas=%d", len(base))
    return base[keep].reset_index(drop=True)


def _render_kpi_row(df: pd.DataFrame, revenue_override: float | None = None) -> None:
    revenue = revenue_override if revenue_override is not None else float(_safe_num(df.get("faturamento_item"), fill=0.0).sum())
    total_margin = float(_safe_num(df.get("margem_valor"), fill=0.0).sum())
    avg_margin = float(_safe_num(df.get("margem_perc"), fill=None).dropna().mean()) if not df.empty else 0.0
    audit_items = int(df[df.get("item_auditoria", pd.Series(dtype=bool)).fillna(False)]["id_produto"].nunique()) if not df.empty else 0

    st.markdown(
        """
        <style>
        div[data-testid="stMetricValue"] > div {
            white-space: normal;
            overflow-wrap: anywhere;
        }
        div[data-testid="stMetricLabel"] {
            white-space: normal;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    row1_col1, row1_col2 = st.columns(2)
    row2_col1, row2_col2 = st.columns(2)

    row1_col1.metric(
        label="Faturamento Total",
        value=_fmt_currency(revenue),
        help="Soma bruta de todas as vendas no período. Reflete o volume financeiro que entrou no caixa.",
    )
    row1_col2.metric(
        label="Margem Total (R$)",
        value=_fmt_currency(total_margin),
        help="Lucro bruto total estimado. Calculado subtraindo o custo de produção do preço de venda dos itens com receita cadastrada.",
    )
    row2_col1.metric(
        label="Margem Média %",
        value=_fmt_percent(avg_margin if not pd.isna(avg_margin) else 0.0),
        help="Média ponderada da lucratividade. Indica, em média, quanto de cada real vendido sobra após pagar os custos de produção.",
    )
    row2_col2.metric(
        label="Itens para Auditoria",
        value=f"{audit_items}",
        help="Produtos vendidos que não possuem custo calculado (receita faltando). Atenção: se este número for alto, o Lucro Total estará subestimado.",
    )


def _render_scatter(df: pd.DataFrame, selected_months: list[str], available_months: list[str]) -> None:
    st.subheader(
        "Matriz de Rentabilidade",
        help="Visualização estratégica de produtos baseada em Volume vs. Margem."
    )

    if df.empty:
        st.warning("⚠️ Sem dados para matriz de rentabilidade.")
        return

    # 1. Preparação e Limpeza de Dados
    plot_df = df.copy()
    plot_df = plot_df[_safe_num(plot_df["qtd_vendida"], fill=0.0) > 0]

    if plot_df.empty:
        st.warning("⚠️ Não há dados com volume vendido.")
        return

    # Cálculos de Referência
    mediana_volume = float(_safe_num(plot_df["qtd_vendida"], fill=0.0).median())
    margem_alvo = 30.0

    # 2. Engenharia de Visualização
    plot_df["margem_plot"] = plot_df["margem_perc"].fillna(0.0)

    # Lógica de Quadrantes
    x_high = plot_df["qtd_vendida"].ge(mediana_volume)
    y_high = plot_df["margem_plot"].ge(margem_alvo)
    plot_df["quadrante"] = np.select(
        [x_high & y_high, x_high & ~y_high, ~x_high & y_high],
        ["ESTRELAS", "VACAS LEITEIRAS", "DILEMAS"],
        default="PROBLEMAS",
    )

    # 3. Definição de Limites e Padding dinâmico
    x_max = plot_df["qtd_vendida"].max()
    y_min = min(plot_df["margem_plot"].min(), -20)
    y_max = max(plot_df["margem_plot"].max(), 100)  # Teto para evitar outliers esmagarem o gráfico

    fig = go.Figure()

    # 4. Background: Labels de Quadrantes como Marcas d'Água
    # Posicionamento centralizado em cada quadrante para evitar encavalamento
    quadrant_labels = [
        {"x": (mediana_volume + x_max) / 2, "y": (margem_alvo + y_max) / 2, "txt": "ESTRELAS"},
        {"x": (mediana_volume + x_max) / 2, "y": (y_min + margem_alvo) / 2, "txt": "VACAS LEITEIRAS"},
        {"x": mediana_volume / 2, "y": (margem_alvo + y_max) / 2, "txt": "DILEMAS"},
        {"x": mediana_volume / 2, "y": (y_min + margem_alvo) / 2, "txt": "PROBLEMAS"},
    ]

    for q in quadrant_labels:
        fig.add_annotation(
            x=q["x"], y=q["y"], text=f"<b>{q['txt']}</b>",
            showarrow=False, font=dict(size=24, color="rgba(255, 255, 255, 0.1)"),
            xref="x", yref="y"
        )

    # 5. Renderização dos Pontos (Scatter)
    # Separando válidos de auditoria
    mask_audit = plot_df["margem_perc"].isna()

    # Plot de Itens com Margem (Bolhas Coloridas)
    valid_df = plot_df[~mask_audit]
    if not valid_df.empty:
        fig.add_trace(go.Scatter(
            x=valid_df["qtd_vendida"],
            y=valid_df["margem_plot"],
            mode="markers",
            name="Margem Calculada",
            marker=dict(
                size=valid_df["faturamento_item"],
                sizemode='area',
                sizeref=2.0 * max(valid_df["faturamento_item"]) / (45 ** 2),  # Max size 45
                sizemin=5,
                color=valid_df["margem_perc"],
                colorscale=_BRAND_MARGIN_COLORSCALE,
                showscale=True,
                colorbar=dict(title="Margem %", thickness=15, x=1.02),
                line=dict(width=0.5, color="#1e293b")
            ),
            hovertemplate="<b>%{customdata[0]}</b><br>Volume: %{x}<br>Margem: %{y:.1f}%<extra></extra>",
            customdata=valid_df[["nome_produto"]].values
        ))

    # Plot de Itens para Auditoria (Diamantes Cinzas com Jitter para evitar sobreposição total)
    audit_df = plot_df[mask_audit].copy()
    if not audit_df.empty:
        # Adiciona um pequeno ruído no Y (±2%) para dispersar os diamantes na linha 0
        jitter = np.random.uniform(-2, 2, size=len(audit_df))
        fig.add_trace(go.Scatter(
            x=audit_df["qtd_vendida"],
            y=audit_df["margem_plot"] + jitter,
            mode="markers",
            name="Auditoria Necessária",
            marker=dict(symbol="diamond", size=12, color="#64748b", line=dict(width=1, color="white")),
            hovertemplate="<b>%{customdata[0]}</b><br>Volume: %{x}<br>Sem Custo Cadastrado<extra></extra>",
            customdata=audit_df[["nome_produto"]].values
        ))

    # 6. Layout e Eixos
    fig.add_vline(x=mediana_volume, line_dash="dot", line_color="rgba(255,255,255,0.3)")
    fig.add_hline(y=margem_alvo, line_dash="dot", line_color="rgba(46, 204, 113, 0.4)")

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=80, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(title="Vendas", showgrid=False),
        yaxis=dict(title="Margem %", showgrid=True, gridcolor="rgba(255,255,255,0.05)", range=[y_min, y_max])
    )

    _render_plot(fig)

def _render_revenue_pareto(df: pd.DataFrame) -> None:
    st.subheader("Análise de Pareto da Receita")
    if df.empty:
        st.warning("⚠️ Sem dados para composição de receita.")
        return

    pareto_df = (
        df[["nome_produto", "faturamento_item"]]
        .copy()
        .groupby("nome_produto", as_index=False)["faturamento_item"]
        .sum()
    )
    pareto_df = pd.DataFrame(pareto_df).sort_values(by="faturamento_item", ascending=False).reset_index(drop=True)
    if pareto_df.empty:
        st.warning("⚠️ Sem dados para composição de receita.")
        return

    total = float(_safe_num(pareto_df["faturamento_item"], fill=0.0).sum())
    pareto_df["pct_acumulado"] = (_safe_num(pareto_df["faturamento_item"], fill=0.0).cumsum() / total * 100.0) if total > 0 else 0.0

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=pareto_df["nome_produto"],
            y=pareto_df["faturamento_item"],
            name="Receita (R$)",
            marker={"color": _BRAND_PRIMARY_BLUE},
            hovertemplate="<b>%{x}</b><br>Receita: R$ %{y:,.2f}<extra></extra>",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=pareto_df["nome_produto"],
            y=pareto_df["pct_acumulado"],
            name="% Acumulado",
            mode="lines+markers",
            line={"color": _BRAND_ACCENT_ORANGE, "width": 2},
            hovertemplate="<b>%{x}</b><br>% Acumulado: %{y:.1f}%<extra></extra>",
        ),
        secondary_y=True,
    )

    crossing_idx = pareto_df.index[pareto_df["pct_acumulado"] >= 80.0]
    if len(crossing_idx) > 0:
        cutoff = int(crossing_idx[0])
        fig.add_vline(
            x=cutoff,
            line_dash="dash",
            line_color="#d62728",
            annotation_text="Marco 80%",
            annotation_position="top",
        )

    fig.update_layout(
        title="Concentração de Receita por Produto (Pareto)",
        legend_title_text="Métricas",
        margin={"l": 8, "r": 8, "t": 46, "b": 8},
        xaxis_title="Produto",
    )
    fig.update_yaxes(title_text="Receita (R$)", secondary_y=False)
    fig.update_yaxes(title_text="% Acumulado", range=[0, 105], secondary_y=True)
    _render_plot(fig)


def _style_decision_table(row: pd.Series) -> list[str]:
    margem = row.get("Margem (%) Numérica", np.nan)
    custo_unit = row.get("Custo Unit.", np.nan)
    if pd.isna(margem) or pd.isna(custo_unit):
        style = "background-color: #333300; color: #ffffff"
    elif margem < 0:
        style = "background-color: #4d0000; color: #ffffff"
    else:
        style = ""
    return [style for _ in row.index]


def _ptbr_currency_style(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "⚠️ Audit Needed"
    return _fmt_currency(float(value))


def _ptbr_percent_style(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "⚠️ Audit Needed"
    return _fmt_percent(float(value))


def _render_sazonalidade_mensal() -> None:
    """Render monthly seasonality with MoM + moving average and optional multi-year views."""
    st.subheader(
        "📅 Sazonalidade Mensal",
        help="Evolução mensal de vendas com análise de tendências e sazonalidade.",
    )

    df_mensal = load_parquet_from_drive("gold_vendas_mensais.parquet")

    if df_mensal is None or df_mensal.empty:
        st.info("ℹ️ Dados de sazonalidade ainda não disponíveis. Execute o pipeline para gerar `gold_vendas_mensais.parquet`.")
        return

    # Ensure datetime column is properly typed for chronological sorting
    if "mes_ano" in df_mensal.columns:
        df_mensal["mes_ano"] = pd.to_datetime(df_mensal["mes_ano"], errors="coerce")
        df_mensal = df_mensal.sort_values("mes_ano").reset_index(drop=True)

    # Use the readable label for X axis; fall back to mes_ano if label column missing
    if "mes_ano_label" in df_mensal.columns:
        x_labels = df_mensal["mes_ano_label"].astype(str).tolist()
    elif "mes_ano" in df_mensal.columns:
        x_labels = df_mensal["mes_ano"].dt.strftime("%Y-%m").tolist()
    else:
        st.warning("⚠️ Coluna de mês/ano não encontrada no arquivo de sazonalidade.")
        return

    if "total_pedidos" not in df_mensal.columns:
        st.warning("⚠️ Coluna `total_pedidos` não encontrada em `gold_vendas_mensais.parquet`.")
        return

    # Prepare data for visualization
    vendas = pd.to_numeric(df_mensal["total_pedidos"], errors="coerce").fillna(0.0).astype(float).values
    peak_idx = int(np.argmax(vendas)) if len(vendas) else 0
    peak_label = x_labels[peak_idx] if 0 <= peak_idx < len(x_labels) else "—"
    peak_value = float(vendas[peak_idx]) if 0 <= peak_idx < len(vendas) else 0.0

    # Calculate MoM variation for hover + KPI.
    mom_series = pd.Series(vendas).pct_change() * 100.0
    mom_labels = ["—" if pd.isna(v) else f"{float(v):+.1f}%" for v in mom_series.tolist()]

    # Calculate 3-month moving average
    window = 3
    moving_avg = pd.Series(vendas).rolling(window=window, center=False).mean().values

    bar_colors = [_BRAND_PRIMARY_BLUE] * len(vendas)
    if 0 <= peak_idx < len(bar_colors):
        bar_colors[peak_idx] = _BRAND_PEAK_ORANGE

    # Create interactive chart with bars and moving average line using Plotly
    fig = go.Figure()

    # Add bar chart with automatic peak highlight.
    fig.add_trace(go.Bar(
        x=x_labels,
        y=vendas,
        name="Vendas Mensais",
        marker=dict(color=bar_colors),
        customdata=np.array(mom_labels, dtype=object).reshape(-1, 1),
        hovertemplate="<b>%{x}</b><br>Vendas: %{y:.0f}<br>MoM: %{customdata[0]}<extra></extra>"
    ))

    # Overlay line improves trend readability while bars keep absolute magnitude.
    fig.add_trace(go.Scatter(
        x=x_labels,
        y=vendas,
        name="Tendência Mensal",
        mode="lines+markers",
        line=dict(color=_BRAND_TREND_BLUE, width=2),
        marker=dict(size=6),
        customdata=np.array(mom_labels, dtype=object).reshape(-1, 1),
        hovertemplate="<b>%{x}</b><br>Vendas: %{y:.0f}<br>MoM: %{customdata[0]}<extra></extra>"
    ))

    # Add moving average line
    fig.add_trace(go.Scatter(
        x=x_labels,
        y=moving_avg,
        name=f"Média Móvel ({window} meses)",
        mode='lines',
        line=dict(color=_BRAND_ACCENT_ORANGE, width=3, dash="dot"),
        hovertemplate="<b>%{x}</b><br>MA({window}): %{y:.0f}<extra></extra>"
    ))

    if 0 <= peak_idx < len(x_labels):
        fig.add_annotation(
            x=x_labels[peak_idx],
            y=peak_value,
            text=f"Pico: {peak_label}",
            showarrow=True,
            arrowhead=2,
            ax=0,
            ay=-35,
            bgcolor="rgba(249,115,22,0.16)",
            bordercolor=_BRAND_PEAK_ORANGE,
            font=dict(color="#f8fafc", size=11),
        )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        height=400,
        margin=dict(l=20, r=20, t=40, b=20),
        bargap=0.25,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(title="Período", showgrid=False, zeroline=False),
        yaxis=dict(title="Quantidade de Vendas", showgrid=True, gridcolor="rgba(255,255,255,0.03)", zeroline=False)
    )

    _render_plot(fig)


    # MoM: compare peak month to the immediately previous month.
    mom_pct = "—"
    if peak_idx > 0:
        prev_value = float(vendas[peak_idx - 1])
        if prev_value > 0:
            mom_pct = f"{((peak_value - prev_value) / prev_value * 100):+.1f}%"

    monthly_avg = float(np.mean(vendas)) if len(vendas) else 0.0

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Meses Analisados", len(df_mensal))
    with col2:
        st.metric("Mês de Pico", peak_label)
    with col3:
        st.metric("Pico vs. Mês Anterior", mom_pct, help="Month-on-Month (MoM) variation")
    with col4:
        st.metric("Média Mensal de Vendas", f"{monthly_avg:.0f}")

    unique_years = int(df_mensal["mes_ano"].dt.year.nunique()) if "mes_ano" in df_mensal.columns else 0
    if unique_years < 2:
        st.caption(
            "Comparação Ano-a-Ano (YoY) e variabilidade sazonal por mês serão exibidas automaticamente "
            "quando houver pelo menos 2 anos de histórico."
        )
        return

    # Year-over-Year comparison (only when data spans multiple years)
    st.markdown("---")
    st.markdown("#### 📈 Comparação Ano-a-Ano (YoY)")

    if "mes_ano" in df_mensal.columns and len(df_mensal) > 12:
        # Extract year and month for pivot
        df_mensal_copy = df_mensal.copy()
        df_mensal_copy["year"] = df_mensal_copy["mes_ano"].dt.year
        df_mensal_copy["month"] = df_mensal_copy["mes_ano"].dt.month
        df_mensal_copy["month_name"] = df_mensal_copy["mes_ano"].dt.strftime("%b")  # Jan, Feb, etc.
        
        # Create pivot table: months as rows, years as columns
        df_yoy = df_mensal_copy.pivot_table(
            index="month_name",
            columns="year",
            values="total_pedidos",
            aggfunc="sum"
        )
        
        # Reorder to calendar order
        month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        df_yoy = df_yoy.reindex([m for m in month_order if m in df_yoy.index])
        
        if not df_yoy.empty:
            # Create YoY line chart
            fig_yoy = go.Figure()
            
            for year in df_yoy.columns:
                fig_yoy.add_trace(go.Scatter(
                    x=df_yoy.index,
                    y=df_yoy[year],
                    mode='lines+markers',
                    name=str(year),
                    hovertemplate="<b>%{x} (%{fullData.name})</b><br>Vendas: %{y:.0f}<extra></extra>"
                ))
            
            fig_yoy.update_layout(
                title="Comparação de Padrões Mensais por Ano",
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                hovermode="x unified",
                height=400,
                margin=dict(l=20, r=20, t=60, b=20),
                xaxis=dict(title="Mês"),
                yaxis=dict(title="Quantidade de Vendas", showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            _render_plot(fig_yoy)
        else:
            st.info("ℹ️ Dados insuficientes para comparação YoY.")
    # Box Plot for seasonal patterns (if multiple years available)
    st.markdown("---")
    st.markdown("#### 📊 Variabilidade Sazonal por Mês")

    if "mes_ano" in df_mensal.columns and len(df_mensal) > 12:
        df_mensal_copy = df_mensal.copy()
        df_mensal_copy["month_name"] = df_mensal_copy["mes_ano"].dt.strftime("%b")
        
        # Create box plot
        fig_box = go.Figure()
        
        month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        for month in month_order:
            month_data = df_mensal_copy[df_mensal_copy["month_name"] == month]["total_pedidos"]
            if not month_data.empty:
                fig_box.add_trace(go.Box(
                    y=month_data,
                    name=month,
                    boxmean='sd',
                    hovertemplate="<b>%{fullData.name}</b><br>Vendas: %{y:.0f}<extra></extra>"
                ))
        
        fig_box.update_layout(
            title="Distribuição de Vendas por Mês (Todos os Anos)",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=400,
            margin=dict(l=20, r=20, t=60, b=20),
            xaxis=dict(title="Mês"),
            yaxis=dict(title="Quantidade de Vendas", showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
            showlegend=False
        )
        
        _render_plot(fig_box)


def _render_decision_table(df: pd.DataFrame) -> None:
    st.subheader("Tabela de Decisão e Alertas")
    st.markdown(
        """
        **Como interpretar:**

        - **VERMELHO ESCURO:** Produtos com margem negativa (prejuízo unitário). Exigem revisão de preço ou de custo urgente.
        - **OLIVA/AMARELO:** Produtos sem receita cadastrada. Precisam de auditoria para que o lucro real seja calculado.
        """
    )
    st.caption("Itens com 100% de margem e custo 'None' são inconsistências de dados que precisam de preenchimento na planilha de receitas.")
    if df.empty:
        st.warning("⚠️ Sem dados de margem para priorização.")
        return

    decision_df = df.copy()
    decision_df["margem_perc_num"] = _normalize_margin_percent(decision_df["margem_perc"])
    decision_df = decision_df.sort_values("margem_perc_num", ascending=True, na_position="last").head(10)

    table = pd.DataFrame(
        {
            "Produto": decision_df["nome_produto"].fillna(""),
            "Quantidade Vendida": _safe_num(decision_df["qtd_vendida"], fill=0.0),
            "Receita": _safe_num(decision_df["faturamento_item"], fill=None),
            "Custo Unit.": _safe_num(decision_df["custo_producao_unitario"], fill=None),
            "Margem (R$)": _safe_num(decision_df["margem_valor"], fill=None),
            "Margem (%)": _safe_num(decision_df["margem_perc"], fill=None),
            "Margem (%) Numérica": decision_df["margem_perc_num"],
        }
    )

    formatters: dict[str, Any] = {
        "Receita": _ptbr_currency_style,
        "Custo Unit.": _ptbr_currency_style,
        "Margem (R$)": _ptbr_currency_style,
        "Margem (%)": _ptbr_percent_style,
    }
    styled = table.style.apply(_style_decision_table, axis=1).format(formatters)
    try:
        st.dataframe(
            styled.hide(axis="columns", subset=["Margem (%) Numérica"]),
            width="stretch",
            column_config={
                "Quantidade Vendida": st.column_config.NumberColumn("Quantidade Vendida", format="%.0f"),
                # Keep numeric source columns for sorting; style handles final text formatting.
                "Receita": st.column_config.NumberColumn("Receita", format="R$ %.2f"),
                "Custo Unit.": st.column_config.NumberColumn("Custo Unit.", format="R$ %.2f"),
                "Margem (R$)": st.column_config.NumberColumn("Margem (R$)", format="R$ %.2f"),
                "Margem (%)": st.column_config.NumberColumn("Margem (%)", format="%.2f%%"),
            },
        )
    except Exception:
        # Fallback to style-only render when column_config has compatibility issues.
        st.dataframe(styled.hide(axis="columns", subset=["Margem (%) Numérica"]), width="stretch")

def show_dashboard() -> None:
    """Render dashboard with profitability, concentration and pricing priorities."""
    inject_roboto_font()
    st.header("📊 Dashboard")
    st.caption("Cockpit executivo de receita, margem e auditoria de custos.")
    render_separator()


    sales_df = load_sales_data_cached()
    if sales_df is not None and not sales_df.empty:
        sales_df = sales_df.copy()
        sales_df["data"] = pd.to_datetime(sales_df.get("data", pd.Series(index=sales_df.index, dtype="object")), errors="coerce")
        if not is_datetime64_any_dtype(sales_df["data"]):
            logger.error("DEBUG RENTABILIDADE: coluna 'data' nao esta em datetime64[ns] apos cast")
        nat_data = int(sales_df["data"].isna().sum())
        logger.info(
            "DEBUG RENTABILIDADE: sales_df dashboard rows=%d data_dtype=%s nat_data=%d",
            len(sales_df),
            sales_df["data"].dtype,
            nat_data,
        )
        data_ini = sales_df["data"].min()
        data_fim = sales_df["data"].max()
        logger.info("Filtros Dashboard: Inicio=%s, Fim=%s", data_ini, data_fim)
    available_months: list[str] = []
    if sales_df is not None and not sales_df.empty and "mes_referencia" in sales_df.columns:
        available_months = sorted([m for m in sales_df["mes_referencia"].dropna().astype(str).unique().tolist() if m and m != "sem_mes"])

    selected_months = st.sidebar.multiselect(
        "Periodo de Analise (Mes)",
        options=available_months,
        default=available_months,
    )

    margem_range = st.sidebar.slider(
        "Filtrar por Faixa de Margem %",
        min_value=-100,
        max_value=100,
        value=(-100, 100),
        step=1,
    )
    st.sidebar.caption("Itens com 'Audit Needed' (margem nula) sao sempre exibidos.")

    if sales_df is None:
        st.warning("⚠️ Não foi possível validar a carga de vendas do Gold.")

    profitability_df = _build_profitability_base(sales_df)
    if not profitability_df.empty and "_mapping_error" in profitability_df.columns and bool(profitability_df["_mapping_error"].fillna(False).any()):
        st.error("Erro de Mapeamento: Chaves de Produtos não coincidem")
    if profitability_df.empty:
        st.warning("⚠️ Não há dados suficientes para montar o dashboard de rentabilidade.")
        return

    profitability_df = _apply_month_filter(profitability_df, sales_df, selected_months)
    if profitability_df.empty:
        st.warning("⚠️ Sem dados para o periodo selecionado.")
        return

    profitability_df = profitability_df.copy()
    profitability_df["margem_perc"] = _normalize_margin_percent(profitability_df.get("margem_perc"))

    margem_num = profitability_df["margem_perc"]
    low, high = margem_range
    # Slider applies to numeric margins; NaN rows remain visible for audit.
    filtered_df = profitability_df[
        (margem_num.between(low, high, inclusive="both"))
        | (margem_num.isna())
    ].copy()
    if filtered_df.empty:
        st.warning("⚠️ O filtro de margem não retornou produtos. Ajuste a faixa na barra lateral.")
        return

    revenue_kpi = _compute_revenue_total_from_sales(sales_df, selected_months)

    with st.container(border=True):
        _render_kpi_row(filtered_df, revenue_override=revenue_kpi)

    with st.container(border=True):
        _render_scatter(filtered_df, selected_months, available_months)

    with st.container(border=True):
        _render_revenue_pareto(filtered_df)

    with st.container(border=True):
        _render_sazonalidade_mensal()

    with st.container(border=True):
        _render_decision_table(filtered_df)
