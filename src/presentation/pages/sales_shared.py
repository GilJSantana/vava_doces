"""Shared sales helpers for Dashboard insights and Faturamento audit views."""

from __future__ import annotations

import logging
from io import BytesIO
from typing import Optional

import pandas as pd
import streamlit as st

from src.infrastructure.gold_adapter import GoldParquetAdapter
from src.ports.data_source import DataSourceError

logger = logging.getLogger(__name__)

def log_df_shape(stage: str, df: Optional[pd.DataFrame], key_cols: list[str] | None = None) -> None:
    """Small reusable logger for dataframe shape and key-column diagnostics."""
    if df is None:
        logger.info("[diag] %s rows=0 cols=0 (df=None)", stage)
        return
    normalized_key_cols = key_cols or []
    missing_keys = [c for c in normalized_key_cols if c not in df.columns]
    logger.info(
        "[diag] %s rows=%d cols=%d missing_keys=%s",
        stage,
        len(df),
        len(df.columns),
        missing_keys,
    )


def _normalize_sales_for_presentation(df: pd.DataFrame) -> pd.DataFrame:
    """Light normalization for UI compatibility without deduplication.

    Important: keep one row per record from gold; do not apply front-end dedup.
    """
    out = df.copy()
    out["data"] = pd.to_datetime(out.get("data", pd.Series(index=out.index, dtype="object")), errors="coerce")

    for col in ("produto", "cliente", "canal", "arquivo_origem", "data_carga"):
        if col not in out.columns:
            out[col] = ""
        out[col] = out[col].fillna("").astype(str).str.strip()

    for col in ("qtd", "valor_unit", "valor_venda", "valor_total", "custo", "margem"):
        if col not in out.columns:
            out[col] = 0.0
        out[col] = pd.Series(pd.to_numeric(out[col], errors="coerce"), index=out.index).fillna(0.0)

    if "mes_referencia" not in out.columns:
        out["mes_referencia"] = out["data"].dt.to_period("M").astype(str)
    out["mes_referencia"] = (
        out["mes_referencia"]
        .fillna("sem_mes")
        .astype(str)
        .replace({"NaT": "sem_mes", "nat": "sem_mes", "": "sem_mes", "None": "sem_mes"})
    )
    out["_invalid_date"] = out["data"].isna()
    return out


@st.cache_data
def load_sales_data_cached() -> Optional[pd.DataFrame]:
    """Load sales data from gold layer (fato_vendas + dim_produto + dim_tempo).

    Returns None when no data is available.
    """
    try:
        # Try gold layer first (deduplicated, typed, pre-aggregated)
        adapter = GoldParquetAdapter()
        fato_vendas = adapter.load_gold("fato_vendas")
        log_df_shape("load_sales_data_cached:fato_vendas_raw", fato_vendas, ["venda_id", "data_id", "produto_id"])
        dim_produto = adapter.load_gold("dim_produto")
        dim_tempo = adapter.load_gold("dim_tempo")

        # Join to get product names and dates
        df = fato_vendas.merge(dim_produto, on="produto_id", how="left")
        df = df.merge(dim_tempo[["data_id", "data"]], on="data_id", how="left")

        # Rename columns to match expected schema
        df = df.rename(columns={
            "nome_produto": "produto",
            "quantidade": "qtd",
            "valor_unitario": "valor_unit",
        })

        # Audit compatibility for consolidated monthly filtering.
        if "arquivo_origem" not in df.columns and "source_file" in df.columns:
            df["arquivo_origem"] = df["source_file"]
        if "data_carga" not in df.columns and "ingested_at_utc" in df.columns:
            df["data_carga"] = df["ingested_at_utc"]
        if "mes_referencia" not in df.columns:
            data_series = df.get("data", pd.Series(index=df.index, dtype="object"))
            df["mes_referencia"] = pd.to_datetime(data_series, errors="coerce").dt.to_period("M").astype(str)

        # Ensure valor_venda is available for compatibility
        if "valor_venda" not in df.columns and "valor_total" in df.columns:
            df["valor_venda"] = df["valor_total"]

        log_df_shape("load_sales_data_cached:before_ui_normalization", df, ["num_venda", "produto", "data"])
        normalized = _normalize_sales_for_presentation(df)
        log_df_shape("load_sales_data_cached:after_ui_normalization", normalized, ["num_venda", "produto", "data"])
        return normalized

    except (DataSourceError, FileNotFoundError) as exc:
        logger.warning("load_sales_data_cached: gold layer unavailable after medallion bootstrap — %s", exc)
        return None
    except Exception:
        return None


def inject_roboto_font() -> None:
    """Load Roboto in the browser and apply to Plotly charts."""
    st.markdown(
        """
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
        <style>
          .js-plotly-plot, .js-plotly-plot *, .plotly, .plotly * {
            font-family: 'Roboto', sans-serif !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

def format_brl(value: float) -> str:
    """Format float as BRL (pt-BR separators)."""
    text = f"{float(value):,.2f}"
    text = text.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {text}"




def to_excel_bytes(df: pd.DataFrame) -> bytes:
    """Serialize DataFrame to XLSX bytes for download."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="faturamento")
    return buffer.getvalue()



