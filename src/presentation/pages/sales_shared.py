"""Shared sales helpers for Dashboard insights and Faturamento audit views."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build

from src.infrastructure.gold_adapter import GoldParquetAdapter
from src.ports.data_source import DataSourceError

logger = logging.getLogger(__name__)

_DRIVE_RO_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
_REQUIRED_GOLD_LAYERS = ("fato_vendas", "dim_produto", "dim_tempo")


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


def _gold_local_path(layer: str) -> Path:
    project_root = Path(__file__).resolve().parents[3]
    return project_root / "data" / "processed" / "gold" / f"{layer}.parquet"


def _build_drive_ro_service():
    try:
        account_info = st.secrets.get("gcp_service_account")
    except Exception:
        return None
    if not isinstance(account_info, Mapping):
        return None
    credentials = service_account.Credentials.from_service_account_info(
        dict(account_info),
        scopes=_DRIVE_RO_SCOPES,
    )
    return build("drive", "v3", credentials=credentials)


def _download_gold_layer_from_drive(layer: str) -> bool:
    try:
        folder_id = str(st.secrets.get("GOOGLE_DRIVE_FOLDER_ID", "")).strip()
    except Exception:
        return False
    if not folder_id:
        return False

    service = _build_drive_ro_service()
    if service is None:
        return False

    file_name = f"{layer}.parquet"
    safe_name = file_name.replace("'", "\\'")
    query = f"'{folder_id}' in parents and trashed=false and name='{safe_name}'"
    found = service.files().list(
        q=query,
        pageSize=1,
        fields="files(id,name,modifiedTime)",
        orderBy="modifiedTime desc",
    ).execute().get("files", [])
    if not found:
        return False

    target = _gold_local_path(layer)
    target.parent.mkdir(parents=True, exist_ok=True)
    blob = service.files().get_media(fileId=found[0]["id"]).execute()
    target.write_bytes(blob)
    logger.info(
        "Downloaded latest %s from Drive to %s (modified=%s)",
        file_name,
        target,
        found[0].get("modifiedTime"),
    )
    return True


@st.cache_data(ttl=300)
def load_sales_data_cached() -> Optional[pd.DataFrame]:
    """Load sales data from gold layer (fato_vendas + dim_produto + dim_tempo).

    Returns None when no data is available.
    """
    try:
        for layer in _REQUIRED_GOLD_LAYERS:
            local_path = _gold_local_path(layer)
            if not local_path.exists():
                _download_gold_layer_from_drive(layer)

        # Read only columns used by dashboard/faturamento to reduce parquet I/O.
        adapter = GoldParquetAdapter()
        fato_cols = [
            "venda_id",
            "data_id",
            "produto_id",
            "num_venda",
            "cliente",
            "canal",
            "quantidade",
            "valor_unitario",
            "valor_total",
            "custo",
            "margem",
            "source_file",
            "arquivo_origem",
            "mes_referencia",
            "ingested_at_utc",
            "data_carga",
            "faturamento_liquido",
        ]
        fato_vendas = adapter.load_gold("fato_vendas", columns=fato_cols)
        log_df_shape("load_sales_data_cached:fato_vendas_raw", fato_vendas, ["venda_id", "data_id", "produto_id"])
        dim_produto = adapter.load_gold("dim_produto", columns=["produto_id", "nome_produto"])
        dim_tempo = adapter.load_gold("dim_tempo", columns=["data_id", "data"])

        # Join to get product names and dates
        df = fato_vendas.merge(dim_produto, on="produto_id", how="left")
        df = df.merge(dim_tempo, on="data_id", how="left")

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

