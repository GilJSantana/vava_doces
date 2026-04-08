"""scripts/medallion_pipeline.py

Medallion Architecture — Vava Doces.

This module keeps the RAW → SILVER → GOLD flow but intentionally preserves
all faturamento rows end-to-end. Duplicate-like rows are only diagnosed in the
returned audit metadata; they are never removed.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from src.infrastructure.data_quality import DataQualityValidator

# ── Project root on sys.path so src.* imports work ────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.domain.sales_analysis_service import (  # noqa: E402
    _deduplicate_with_audit,
    _normalise_header,
    _normalise_value,
    _parse_sales_dates_with_source,
    _to_numeric,
)
from src.infrastructure.gold_adapter import GoldParquetAdapter  # noqa: E402
from src.ports.data_source import DataSourceError, DriveDataSource  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("medallion")


def log_df_shape(stage: str, df: pd.DataFrame | None, key_cols: list[str] | None = None) -> None:
    """Small reusable diagnostic logger for row/column counts."""
    if df is None:
        logger.info("[diag] %s rows=0 cols=0 (df=None)", stage)
        return
    key_cols = key_cols or []
    missing_keys = [c for c in key_cols if c not in df.columns]
    logger.info(
        "[diag] %s rows=%d cols=%d missing_keys=%s",
        stage,
        len(df),
        len(df.columns),
        missing_keys,
    )


_RAW_DIR = _ROOT / "data" / "raw"
_SILVER_DIR = _ROOT / "data" / "processed" / "silver"
_GOLD_DIR = _ROOT / "data" / "processed" / "gold"

_RAW_TO_SILVER: dict[str, str] = {
    "numero_da_venda": "num_venda",
    "nota_fiscal_rps": "nota_fiscal",
    "data_da_venda": "data",
    "cliente": "cliente",
    "nome_do_produto_servico": "produto",
    "unidade_de_medida": "unidade_medida",
    "quantidade_de_itens": "quantidade",
    "valor_unitario": "valor_unitario",
    "valor_bruto": "valor_bruto",
    "desconto_na_venda": "desconto",
    "valor_liquido_no_financeiro": "valor_liquido",
    "valor_total": "valor_total",
    "peso_bruto": "peso_bruto",
    "peso_total": "peso_total",
    "cidade_do_cliente": "cidade_cliente",
    "tipo_de_item_produto_ou_servico": "tipo_item",
    "tipo_de_negociacao": "tipo_negociacao",
}

_NUMERIC_COLS = [
    "quantidade",
    "valor_unitario",
    "valor_bruto",
    "desconto",
    "valor_liquido",
    "valor_total",
    "peso_bruto",
    "peso_total",
]

SILVER_COLUMNS = list(_RAW_TO_SILVER.values()) + [
    "custo",
    "source_file",
    "ingested_at_utc",
    "arquivo_origem",
    "mes_referencia",
    "data_carga",
]

_MONTH_PT: dict[int, str] = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Marco",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}

_CHANNEL_MAP: dict[str, str] = {
    "IFOOD": "IFOOD",
    "IF": "IFOOD",
    "PIX": "PIX",
    "CREDITO": "CREDITO",
    "CRÉDITO": "CREDITO",
    "DEBITO": "DEBITO",
    "DÉBITO": "DEBITO",
    "DINHEIRO": "DINHEIRO",
    "LOJA": "LOJA FISICA",
    "LOJA FISICA": "LOJA FISICA",
    "BALCAO": "LOJA FISICA",
    "BALCÃO": "LOJA FISICA",
    "A VISTA": "A VISTA",
    "À VISTA": "A VISTA",
}

_UNKNOWN_ID = -1


class LocalRawSource(DriveDataSource):
    """Filesystem-backed source compatible with the pipeline Drive contract."""

    def __init__(self, raw_dir: Path | str = _RAW_DIR):
        self.raw_dir = Path(raw_dir)

    def list_tabular_files(self) -> list[dict]:
        files: list[dict] = []
        if not self.raw_dir.exists():
            return files
        for path in sorted(self.raw_dir.iterdir()):
            if not path.is_file():
                continue
            suffix = path.suffix.lower()
            if suffix not in {".csv", ".xlsx", ".xls"}:
                continue
            mime = "text/csv" if suffix == ".csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            files.append({"id": str(path), "name": path.name, "mimeType": mime})
        return files

    def read_as_dataframe(self, file_meta: dict) -> Optional[pd.DataFrame]:
        path = Path(str(file_meta.get("id") or self.raw_dir / str(file_meta.get("name", ""))))
        if not path.exists():
            return None
        try:
            if path.suffix.lower() == ".csv":
                return pd.read_csv(path, sep=None, engine="python")
            return pd.read_excel(path)
        except Exception:
            try:
                if path.suffix.lower() == ".csv":
                    return pd.read_csv(path, sep=";", encoding="latin-1")
            except Exception:
                return None
            return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Medallion ETL Pipeline")
    parser.add_argument("--silver", action="store_true", help="Run RAW→SILVER only")
    parser.add_argument("--gold", action="store_true", help="Run SILVER→GOLD only")
    parser.add_argument("--validate", action="store_true", help="Validate star schema")
    return parser.parse_args()


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [c if str(c).startswith("_") else _normalise_header(c) for c in out.columns]
    return out


def _map_canonical(df: pd.DataFrame) -> pd.DataFrame:
    available = {k: v for k, v in _RAW_TO_SILVER.items() if k in df.columns}
    keep = list(available.keys())
    for extra in ("_source_file", "source_file"):
        if extra in df.columns:
            keep.append(extra)
    out = df[keep].rename(columns=available).copy()
    return out


def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "data" in out.columns:
        if "_source_file" in out.columns:
            out = _parse_sales_dates_with_source(out.rename(columns={"_source_file": "_source_file"}))
        else:
            out["data"] = pd.to_datetime(out["data"], errors="coerce")
    for col in _NUMERIC_COLS:
        if col in out.columns:
            out[col] = _to_numeric(out[col])
    if "custo" not in out.columns:
        out["custo"] = 0.0
    out["custo"] = pd.to_numeric(out["custo"], errors="coerce").fillna(0.0)
    if "produto" in out.columns:
        out["produto_key"] = out["produto"].astype(str).map(_normalise_value)
    return out


def _to_day(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce")
    day_np = parsed.values.astype("datetime64[D]").astype("datetime64[ns]")
    return pd.Series(day_np, index=series.index, name=series.name)


def _safe_divide(numerator: pd.Series, denominator: pd.Series, fill_value: float = 0.0) -> pd.Series:
    result = numerator / denominator
    return result.replace([np.inf, -np.inf], np.nan).fillna(fill_value)


def _normalize_channel_for_gold(channel: str | None) -> str:
    if not channel:
        return "DESCONHECIDO"
    text = str(channel).strip().upper()
    return _CHANNEL_MAP.get(text, text)


def _extract_month_reference(source_file: pd.Series, dates: pd.Series) -> pd.Series:
    month_pattern = pd.Series(source_file).astype(str).str.extract(
        r"(?:(?P<yyyy>20\d{2})[_-]?(?P<mm>0[1-9]|1[0-2]))|(?:(?P<mm2>0[1-9]|1[0-2])[_-]?(?P<yyyy2>20\d{2}))"
    )
    yyyy = month_pattern["yyyy"].astype("string").fillna(month_pattern["yyyy2"].astype("string"))
    mm = month_pattern["mm"].astype("string").fillna(month_pattern["mm2"].astype("string"))
    by_name = (
        yyyy.fillna("")
        + "-"
        + mm.fillna("")
    ).str.strip("-")
    by_name = by_name.replace({"": pd.NA, "-": pd.NA})
    by_date = pd.to_datetime(dates, errors="coerce").dt.to_period("M").astype("string")
    return by_name.fillna(by_date).fillna("sem_mes")


def transform_to_silver(raw_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    """Normalize RAW sales into SILVER without removing any rows."""
    out = _normalise_columns(raw_df)
    if out.columns.duplicated().any():
        out = out.loc[:, ~out.columns.duplicated(keep="first")].copy()
    out = _map_canonical(out)
    if out.columns.duplicated().any():
        out = out.loc[:, ~out.columns.duplicated(keep="first")].copy()
    out = _coerce_types(out)
    if out.columns.duplicated().any():
        out = out.loc[:, ~out.columns.duplicated(keep="first")].copy()

    if "_source_file" not in out.columns:
        if "source_file" in out.columns:
            out["_source_file"] = out["source_file"]
        else:
            out["_source_file"] = ""

    out, dedup_audit = _deduplicate_with_audit(out)

    source_file = out["_source_file"].fillna("").astype(str)
    out["source_file"] = source_file
    out["arquivo_origem"] = source_file
    load_ts = datetime.now(timezone.utc).isoformat()
    out["ingested_at_utc"] = load_ts
    out["data_carga"] = load_ts
    out["mes_referencia"] = _extract_month_reference(source_file, out.get("data", pd.Series(index=out.index, dtype="object")))

    for col in SILVER_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA

    silver = out[SILVER_COLUMNS].copy().reset_index(drop=True)
    audit = {
        "rows_in": int(len(raw_df)),
        "rows_out": int(len(silver)),
        **dedup_audit,
    }
    return silver, audit


def build_dim_produto(silver_df: pd.DataFrame) -> pd.DataFrame:
    produtos = (
        silver_df.get("produto", pd.Series(dtype=str))
        .dropna()
        .astype(str)
        .str.strip()
    )
    produtos = produtos[produtos != ""].drop_duplicates().sort_values().reset_index(drop=True)
    dim = pd.DataFrame({"nome_produto": produtos})
    if dim.empty:
        return pd.DataFrame(columns=["produto_id", "nome_produto"]).astype({"produto_id": "int64", "nome_produto": "object"})
    dim.insert(0, "produto_id", range(1, len(dim) + 1))
    dim["produto_id"] = dim["produto_id"].astype("int64")
    return dim


def build_dim_tempo(silver_df: pd.DataFrame) -> pd.DataFrame:
    datas = pd.to_datetime(silver_df.get("data", pd.Series(dtype="object")), errors="coerce")
    datas = pd.Series(datas.dropna().drop_duplicates().sort_values().reset_index(drop=True))
    if datas.empty:
        return pd.DataFrame(columns=["data_id", "data", "dia", "mes", "ano", "trimestre", "dia_semana", "nome_mes"])
    dim = pd.DataFrame({"data": datas})
    dim.insert(0, "data_id", range(1, len(dim) + 1))
    dim["data_id"] = dim["data_id"].astype("int64")
    dim["dia"] = dim["data"].dt.day.astype("int64")
    dim["mes"] = dim["data"].dt.month.astype("int64")
    dim["ano"] = dim["data"].dt.year.astype("int64")
    dim["trimestre"] = (((dim["mes"] - 1) // 3) + 1).astype("int64")
    dim["dia_semana"] = dim["data"].dt.day_name()
    dim["nome_mes"] = dim["mes"].map(_MONTH_PT)
    return dim


def build_dim_canal(silver_df: pd.DataFrame) -> pd.DataFrame:
    base = silver_df.get("tipo_negociacao", silver_df.get("canal", pd.Series(dtype=str)))
    canais = base.fillna("").astype(str).map(_normalize_channel_for_gold)
    canais = canais[canais != ""].drop_duplicates().sort_values().reset_index(drop=True)
    if canais.empty:
        return pd.DataFrame(columns=["canal_id", "canal"]).astype({"canal_id": "int64", "canal": "object"})
    dim = pd.DataFrame({"canal": canais})
    dim.insert(0, "canal_id", range(1, len(dim) + 1))
    dim["canal_id"] = dim["canal_id"].astype("int64")
    return dim


def build_fato_vendas(
    silver_df: pd.DataFrame,
    dim_produto: pd.DataFrame,
    dim_tempo: pd.DataFrame,
    dim_canal: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Build item-grain fact table preserving every silver row 1:1."""
    df = silver_df.copy().reset_index(drop=True)
    if "produto" not in df.columns:
        df["produto"] = ""
    if "data" not in df.columns:
        df["data"] = pd.NaT

    df["produto"] = df["produto"].fillna("").astype(str).str.strip()
    df["data"] = _to_day(df["data"])
    source_canal = df.get("tipo_negociacao", df.get("canal", pd.Series(index=df.index, dtype=str)))
    df["canal"] = source_canal.fillna("").astype(str).map(_normalize_channel_for_gold)

    if not dim_produto.empty:
        df = df.merge(dim_produto.rename(columns={"nome_produto": "produto"}), on="produto", how="left")
    else:
        df["produto_id"] = pd.NA

    if not dim_tempo.empty:
        dim_tempo_keys = dim_tempo[["data_id", "data"]].copy()
        dim_tempo_keys["data"] = _to_day(dim_tempo_keys["data"])
        df = df.merge(dim_tempo_keys, on="data", how="left")
    else:
        df["data_id"] = pd.NA

    if dim_canal is not None and not dim_canal.empty:
        df = df.merge(dim_canal, on="canal", how="left")
    else:
        df["canal_id"] = pd.NA

    df["produto_id"] = pd.to_numeric(df.get("produto_id"), errors="coerce").fillna(_UNKNOWN_ID).astype("int64")
    df["data_id"] = pd.to_numeric(df.get("data_id"), errors="coerce").fillna(_UNKNOWN_ID).astype("int64")
    df["canal_id"] = pd.to_numeric(df.get("canal_id"), errors="coerce").fillna(_UNKNOWN_ID).astype("int64")

    for col in ("quantidade", "valor_unitario", "valor_bruto", "desconto", "valor_liquido", "valor_total", "custo"):
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df["faturamento_bruto"] = np.where(df["valor_bruto"].ne(0), df["valor_bruto"], df["valor_total"])
    df["faturamento_liquido"] = np.where(df["valor_liquido"].ne(0), df["valor_liquido"], df["valor_total"])
    df["lucro_total"] = df["faturamento_liquido"] - df["custo"]
    df["margem"] = _safe_divide(df["lucro_total"], df["quantidade"])
    df["margem_percentual"] = _safe_divide(df["lucro_total"], df["faturamento_liquido"]) * 100.0

    for col in ("source_file", "arquivo_origem", "mes_referencia", "ingested_at_utc", "data_carga", "cliente", "num_venda"):
        if col not in df.columns:
            df[col] = "" if col != "num_venda" else pd.NA

    fato_cols = [
        "produto_id",
        "data_id",
        "canal_id",
        "num_venda",
        "cliente",
        "canal",
        "quantidade",
        "valor_unitario",
        "valor_bruto",
        "desconto",
        "valor_liquido",
        "valor_total",
        "faturamento_bruto",
        "faturamento_liquido",
        "custo",
        "lucro_total",
        "margem",
        "margem_percentual",
        "source_file",
        "arquivo_origem",
        "mes_referencia",
        "ingested_at_utc",
        "data_carga",
    ]
    fato = df[fato_cols].copy().reset_index(drop=True)
    fato.insert(0, "venda_id", np.arange(1, len(fato) + 1, dtype="int64"))
    log_df_shape("build_fato_vendas:end", fato, ["venda_id", "num_venda", "source_file", "mes_referencia"])
    return fato


def validate_star_schema(
    fato: pd.DataFrame,
    dim_produto: pd.DataFrame,
    dim_tempo: pd.DataFrame,
    silver_rows: Optional[int] = None,
) -> dict[str, object]:
    results: dict[str, object] = {}
    valid_pids = set(dim_produto.get("produto_id", pd.Series(dtype="int64")).dropna())
    valid_dids = set(dim_tempo.get("data_id", pd.Series(dtype="int64")).dropna())
    orphan_prod = int((~fato["produto_id"].isin(valid_pids) & (fato["produto_id"] != _UNKNOWN_ID)).sum()) if not fato.empty else 0
    orphan_data = int((~fato["data_id"].isin(valid_dids) & (fato["data_id"] != _UNKNOWN_ID)).sum()) if not fato.empty else 0
    null_pk = int(fato.get("venda_id", pd.Series(dtype="float")).isna().sum()) if not fato.empty else 0
    inf_count = int(np.isinf(pd.to_numeric(fato.get("margem", pd.Series(dtype=float)), errors="coerce").fillna(0)).sum()) if not fato.empty else 0

    results["fk_produto_id_ok"] = orphan_prod == 0
    results["fk_produto_id_orphans"] = orphan_prod
    results["fk_data_id_ok"] = orphan_data == 0
    results["fk_data_id_orphans"] = orphan_data
    results["pk_venda_id_ok"] = null_pk == 0
    results["pk_venda_id_nulls"] = null_pk
    results["margem_no_inf_ok"] = inf_count == 0
    results["margem_inf_count"] = inf_count
    results["fato_rows"] = len(fato)
    results["dim_produto_rows"] = len(dim_produto)
    results["dim_tempo_rows"] = len(dim_tempo)
    if silver_rows is not None:
        row_diff = int(len(fato) - int(silver_rows))
        results["silver_gold_rowcount_ok"] = row_diff == 0
        results["silver_gold_rowcount_diff"] = row_diff
    results["all_ok"] = all(v for v in results.values() if isinstance(v, bool))
    return results


def validate_raw_input_quality(df: pd.DataFrame) -> dict:
    errors: list[str] = []
    if df.empty:
        errors.append("Empty raw input")
    return {
        "errors": errors,
        "stats": {
            "rows": int(len(df)),
            "columns": int(len(df.columns)),
        },
    }


def validate_silver_quality(df: pd.DataFrame) -> dict:
    data_series = pd.to_datetime(df.get("data", pd.Series(dtype="object")), errors="coerce")
    channels = df.get("tipo_negociacao", df.get("canal", pd.Series(dtype="object"))).fillna("").astype(str)
    normalized_channels = channels.map(_normalize_channel_for_gold)
    unrecognized = int(((channels.str.strip() != "") & ~normalized_channels.isin(set(_CHANNEL_MAP.values()) | set(_CHANNEL_MAP.keys()) | {"DESCONHECIDO"})).sum())
    return {
        "errors": [],
        "stats": {
            "rows": int(len(df)),
            "invalid_dates": int(data_series.isna().sum()),
            "unrecognized_channels": unrecognized,
        },
    }


def validate_gold_quality(
    dim_produto: pd.DataFrame,
    dim_tempo: pd.DataFrame,
    dim_canal: pd.DataFrame,
    fato: pd.DataFrame,
) -> dict:
    required = {
        "dim_produto": {"produto_id", "nome_produto"},
        "dim_tempo": {"data_id", "data", "dia", "mes", "ano", "trimestre", "dia_semana", "nome_mes"},
        "dim_canal": {"canal_id", "canal"},
        "fato": {"venda_id", "produto_id", "data_id", "quantidade", "valor_unitario", "valor_total", "custo", "margem", "faturamento_liquido"},
    }
    errors: list[str] = []
    if not required["dim_produto"].issubset(dim_produto.columns):
        errors.append("Missing required columns in dim_produto")
    if not required["dim_tempo"].issubset(dim_tempo.columns):
        errors.append("Missing required columns in dim_tempo")
    if not required["dim_canal"].issubset(dim_canal.columns):
        errors.append("Missing required columns in dim_canal")
    if not required["fato"].issubset(fato.columns):
        errors.append("Missing required columns in fato")
    return {
        "errors": errors,
        "star_schema": validate_star_schema(fato, dim_produto, dim_tempo, len(fato) if not fato.empty else 0),
    }


def run_data_quality_validation(raw_df: pd.DataFrame, silver_df: pd.DataFrame, gold_dict: dict) -> dict:
    return {
        "raw": validate_raw_input_quality(raw_df),
        "silver": validate_silver_quality(silver_df),
        "gold": validate_gold_quality(
            gold_dict.get("dim_produto", pd.DataFrame()),
            gold_dict.get("dim_tempo", pd.DataFrame()),
            gold_dict.get("dim_canal", pd.DataFrame()),
            gold_dict.get("fato_vendas", pd.DataFrame()),
        ),
    }


def enrich_cost_from_catalog(silver_df: pd.DataFrame, cost_map: dict[str, float]) -> pd.DataFrame:
    if not cost_map:
        return silver_df.copy()
    out = silver_df.copy()
    keys = out.get("produto", pd.Series(index=out.index, dtype=str)).astype(str).map(_normalise_value)
    mapped = keys.map(cost_map)
    mask = mapped.notna()
    if "custo" not in out.columns:
        out["custo"] = 0.0
    out.loc[mask, "custo"] = mapped.loc[mask].astype(float)
    out["custo"] = pd.to_numeric(out["custo"], errors="coerce").fillna(0.0)
    return out


def build_agg_vendas_dia(fato_vendas: pd.DataFrame, dim_tempo: pd.DataFrame) -> pd.DataFrame:
    if fato_vendas.empty or dim_tempo.empty:
        return pd.DataFrame()
    merged = fato_vendas.merge(dim_tempo[["data_id", "data", "mes", "ano", "nome_mes"]], on="data_id", how="left")
    grouped = merged.groupby(["data_id", "data", "ano", "mes", "nome_mes"], as_index=False).agg(
        qtd_vendida=("quantidade", "sum"),
        faturamento_bruto=("faturamento_bruto", "sum"),
        faturamento_liquido=("faturamento_liquido", "sum"),
        custo_total=("custo", "sum"),
        lucro_total=("lucro_total", "sum"),
        total_vendas=("venda_id", "count"),
    )
    grouped["margem_percentual"] = _safe_divide(grouped["lucro_total"], grouped["faturamento_liquido"]) * 100.0
    return grouped.sort_values("data").reset_index(drop=True)


def build_agg_vendas_canal(fato_vendas: pd.DataFrame, dim_canal: pd.DataFrame) -> pd.DataFrame:
    if fato_vendas.empty:
        return pd.DataFrame()
    merged = fato_vendas.merge(dim_canal[["canal_id", "canal"]], on="canal_id", how="left", suffixes=("", "_dim")) if not dim_canal.empty else fato_vendas.copy()
    if "canal_dim" in merged.columns:
        merged["canal"] = merged.get("canal", pd.Series(index=merged.index, dtype=str)).fillna(merged["canal_dim"])
    grouped = merged.groupby(["canal_id", "canal"], as_index=False).agg(
        qtd_vendida=("quantidade", "sum"),
        faturamento_bruto=("faturamento_bruto", "sum"),
        faturamento_liquido=("faturamento_liquido", "sum"),
        custo_total=("custo", "sum"),
        lucro_total=("lucro_total", "sum"),
        total_vendas=("venda_id", "count"),
    )
    grouped["margem_percentual"] = _safe_divide(grouped["lucro_total"], grouped["faturamento_liquido"]) * 100.0
    return grouped.sort_values("faturamento_liquido", ascending=False).reset_index(drop=True)


def build_agg_vendas_produto(fato_vendas: pd.DataFrame, dim_produto: pd.DataFrame) -> pd.DataFrame:
    if fato_vendas.empty:
        return pd.DataFrame()
    merged = fato_vendas.merge(dim_produto[["produto_id", "nome_produto"]], on="produto_id", how="left") if not dim_produto.empty else fato_vendas.copy()
    grouped = merged.groupby(["produto_id", "nome_produto"], as_index=False).agg(
        qtd_vendida=("quantidade", "sum"),
        faturamento_bruto=("faturamento_bruto", "sum"),
        faturamento_liquido=("faturamento_liquido", "sum"),
        custo_total=("custo", "sum"),
        lucro_total=("lucro_total", "sum"),
        total_vendas=("venda_id", "count"),
    )
    grouped["margem_percentual"] = _safe_divide(grouped["lucro_total"], grouped["faturamento_liquido"]) * 100.0
    return grouped.sort_values("faturamento_liquido", ascending=False).reset_index(drop=True)


def build_agg_vendas_tempo(fato_vendas: pd.DataFrame, dim_tempo: pd.DataFrame) -> pd.DataFrame:
    if fato_vendas.empty or dim_tempo.empty:
        return pd.DataFrame()
    merged = fato_vendas.merge(dim_tempo[["data_id", "data", "mes", "ano", "nome_mes", "trimestre"]], on="data_id", how="left")
    grouped = merged.groupby(["ano", "trimestre"], as_index=False).agg(
        qtd_vendida=("quantidade", "sum"),
        faturamento_bruto=("faturamento_bruto", "sum"),
        faturamento_liquido=("faturamento_liquido", "sum"),
        custo_total=("custo", "sum"),
        lucro_total=("lucro_total", "sum"),
        total_vendas=("venda_id", "count"),
    )
    grouped["margem_percentual"] = _safe_divide(grouped["lucro_total"], grouped["faturamento_liquido"]) * 100.0
    return grouped.sort_values(["ano", "trimestre"]).reset_index(drop=True)


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


class MedallionPipeline:
    """Materializes RAW → SILVER → GOLD while preserving all source rows."""

    def __init__(
        self,
        source: Optional[DriveDataSource] = None,
        raw_dir: Path | str = _RAW_DIR,
        silver_dir: Path | str = _SILVER_DIR,
        gold_dir: Path | str = _GOLD_DIR,
    ):
        self.raw_dir = Path(raw_dir)
        self.silver_dir = Path(silver_dir)
        self.gold_dir = Path(gold_dir)
        self.source = source or LocalRawSource(self.raw_dir)
        self.silver_df: Optional[pd.DataFrame] = None
        self.fato_vendas: Optional[pd.DataFrame] = None
        self.dim_produto: Optional[pd.DataFrame] = None
        self.dim_tempo: Optional[pd.DataFrame] = None
        self.dim_canal: Optional[pd.DataFrame] = None

    def _load_existing_counts(self) -> dict[str, object]:
        silver_path = self.silver_dir / "sales_silver.parquet"
        gold_path = self.gold_dir / "fato_vendas.parquet"
        if not silver_path.exists() or not gold_path.exists():
            return {
                "bronze_rows": 0,
                "silver_rows": 0,
                "quarantine_rows": 0,
                "gold_rows": 0,
                "used_existing_layers": False,
            }
        silver_df = pd.read_parquet(silver_path, engine="pyarrow")
        gold_df = pd.read_parquet(gold_path, engine="pyarrow")
        return {
            "bronze_rows": 0,
            "silver_rows": int(len(silver_df)),
            "quarantine_rows": 0,
            "gold_rows": int(len(gold_df)),
            "used_existing_layers": True,
        }

    def run(self) -> dict[str, object]:
        logger.info("MedallionPipeline.run() starting...")
        files = self.source.list_tabular_files()
        if not files:
            return self._load_existing_counts()

        frames: list[pd.DataFrame] = []
        for meta in files:
            df = self.source.read_as_dataframe(meta)
            if df is None or df.empty:
                continue
            frame = df.copy()
            if "_source_file" not in frame.columns:
                frame["_source_file"] = meta.get("name", "")
            frames.append(frame)

        if not frames:
            return self._load_existing_counts()

        bronze_df = pd.concat(frames, ignore_index=True)
        bronze_rows = int(len(bronze_df))
        self.silver_df, silver_audit = transform_to_silver(bronze_df)

        _ensure_dir(self.silver_dir)
        _ensure_dir(self.gold_dir)
        self.silver_df.to_parquet(self.silver_dir / "sales_silver.parquet", engine="pyarrow", index=False)

        self.dim_produto = build_dim_produto(self.silver_df)
        self.dim_tempo = build_dim_tempo(self.silver_df)
        self.dim_canal = build_dim_canal(self.silver_df)
        self.fato_vendas = build_fato_vendas(self.silver_df, self.dim_produto, self.dim_tempo, self.dim_canal)

        agg_dia = build_agg_vendas_dia(self.fato_vendas, self.dim_tempo)
        agg_canal = build_agg_vendas_canal(self.fato_vendas, self.dim_canal)
        agg_produto = build_agg_vendas_produto(self.fato_vendas, self.dim_produto)
        agg_tempo = build_agg_vendas_tempo(self.fato_vendas, self.dim_tempo)

        self.dim_produto.to_parquet(self.gold_dir / "dim_produto.parquet", engine="pyarrow", index=False)
        self.dim_tempo.to_parquet(self.gold_dir / "dim_tempo.parquet", engine="pyarrow", index=False)
        self.dim_canal.to_parquet(self.gold_dir / "dim_canal.parquet", engine="pyarrow", index=False)
        self.fato_vendas.to_parquet(self.gold_dir / "fato_vendas.parquet", engine="pyarrow", index=False)
        agg_dia.to_parquet(self.gold_dir / "agg_vendas_dia.parquet", engine="pyarrow", index=False)
        agg_canal.to_parquet(self.gold_dir / "agg_vendas_canal.parquet", engine="pyarrow", index=False)
        agg_produto.to_parquet(self.gold_dir / "agg_vendas_produto.parquet", engine="pyarrow", index=False)
        agg_tempo.to_parquet(self.gold_dir / "agg_vendas_tempo.parquet", engine="pyarrow", index=False)

        validation = validate_star_schema(self.fato_vendas, self.dim_produto, self.dim_tempo, len(self.silver_df))
        try:
            DataQualityValidator(verbose=False).validate_all(self.dim_produto, self.dim_tempo, self.fato_vendas)
        except Exception:
            logger.warning("DataQualityValidator raised a non-fatal validation error.", exc_info=True)

        result = {
            "bronze_rows": bronze_rows,
            "silver_rows": int(len(self.silver_df)),
            "quarantine_rows": 0,
            "gold_rows": int(len(self.fato_vendas)),
            "used_existing_layers": False,
            "dedup_removed": int(silver_audit.get("removed", 0)),
            "validation": validation,
        }
        logger.info("MedallionPipeline.run() finished: %s", result)
        return result


if __name__ == "__main__":
    result = MedallionPipeline().run()
    print(result)
