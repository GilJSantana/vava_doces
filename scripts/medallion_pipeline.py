"""scripts/medallion_pipeline.py
================================
Medallion Architecture — Vava Doces
Implements two stages:

  RAW  →  SILVER  (run_raw_to_silver)
      Ingest every .csv/.xlsx from data/raw/, normalise headers, coerce types,
      cross-file deduplicate and tag with lineage metadata.

  SILVER → GOLD   (run_silver_to_gold)
      Build a star schema:
        dim_produto   → surrogate key + nome_produto
        dim_tempo     → surrogate key + data/dia/mes/ano/trimestre
        fato_vendas   → produto_id FK, data_id FK, metrics, margem

Usage (from project root):
  python scripts/medallion_pipeline.py            # full pipeline
  python scripts/medallion_pipeline.py --silver   # raw → silver only
  python scripts/medallion_pipeline.py --gold     # silver → gold only
  python scripts/medallion_pipeline.py --validate # validate star-schema joins
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

# ── Project root on sys.path so src.* imports work ────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── Re-use battle-tested domain helpers (private but intentional within this
#    monorepo — avoids duplicating normalisation / date-parsing logic) ──────
from src.domain.sales_analysis_service import (   # noqa: E402
    _deduplicate_with_audit,
    _normalise_header,
    _normalise_value,
    _parse_sales_dates_with_source,
    _to_numeric,
)
from src.ports.data_source import DriveDataSource  # noqa: E402

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("medallion")

# ─────────────────────────────────────────────────────────────────────────
# Constants — paths
# ─────────────────────────────────────────────────────────────────────────

_RAW_DIR    = _ROOT / "data" / "raw"
_SILVER_DIR = _ROOT / "data" / "processed" / "silver"
_GOLD_DIR   = _ROOT / "data" / "processed" / "gold"

# ─────────────────────────────────────────────────────────────────────────
# Constants — canonical column mapping
#   normalised header (output of _normalise_header) → silver column name
# ─────────────────────────────────────────────────────────────────────────

_RAW_TO_SILVER: dict[str, str] = {
    "numero_da_venda":                  "num_venda",
    "nota_fiscal_rps":                  "nota_fiscal",
    "data_da_venda":                    "data",
    "cliente":                          "cliente",
    "nome_do_produto_servico":          "produto",
    "unidade_de_medida":                "unidade_medida",
    "quantidade_de_itens":              "quantidade",
    "valor_unitario":                   "valor_unitario",
    "valor_bruto":                      "valor_bruto",
    "desconto_na_venda":                "desconto",
    "valor_liquido_no_financeiro":      "valor_liquido",
    "valor_total":                      "valor_total",
    "peso_bruto":                       "peso_bruto",
    "peso_total":                       "peso_total",
    "cidade_do_cliente":                "cidade_cliente",
    "tipo_de_item_produto_ou_servico":  "tipo_item",
    "tipo_de_negociacao":               "tipo_negociacao",
}

# Columns that must be numeric in silver
_NUMERIC_COLS = [
    "quantidade", "valor_unitario", "valor_bruto",
    "desconto", "valor_liquido", "valor_total",
    "peso_bruto", "peso_total",
]

# Final column order for the silver Parquet file
SILVER_COLUMNS = list(_RAW_TO_SILVER.values()) + [
    "custo",            # unit-cost placeholder (0.0) — enriched later from the
                        # products catalog (Google Sheets).  Set here so gold
                        # can compute margem = (valor_total - custo) / quantidade
                        # with a deterministic schema regardless of enrichment.
    "source_file",
    "ingested_at_utc",
]

def _to_day(series: pd.Series) -> pd.Series:
    """Truncate a datetime Series to day precision (midnight) without .dt accessor.

    Works on both datetime64 Series and object/mixed columns.  Using the
    numpy astype("datetime64[D]") cast avoids the false-positive IDE warning
    that arises from ``.dt.normalize()`` on inferred Series types.
    """
    parsed = pd.to_datetime(series, errors="coerce")
    # Cast to day precision via numpy (strips time component)
    day_np = parsed.values.astype("datetime64[D]").astype("datetime64[ns]")
    return pd.Series(day_np, index=series.index, name=series.name)


# Portuguese month names (no locale dependency)
_MONTH_PT: dict[int, str] = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março",    4: "Abril",
    5: "Maio",    6: "Junho",     7: "Julho",    8: "Agosto",
    9: "Setembro",10: "Outubro",  11: "Novembro", 12: "Dezembro",
}


# ─────────────────────────────────────────────────────────────────────────
# Port implementation: DriveDataSource backed by local data/raw/
# ─────────────────────────────────────────────────────────────────────────

def _mime_for(path: Path) -> str:
    """Return a MIME string for known tabular extensions."""
    return "text/csv" if path.suffix.lower() == ".csv" else (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


class LocalRawSource(DriveDataSource):
    """Port-compliant adapter that reads tabular files from a local directory.

    Implements :class:`src.ports.data_source.DriveDataSource` with the same
    interface as :class:`src.infrastructure.google_drive_adapter.GoogleDriveAdapter`,
    so the ingest stage can switch between local and remote I/O transparently.

    CSV  → ``pd.read_csv(sep=None, engine='python')``  (auto-detects delimiter)
    XLSX → ``pd.read_excel(engine='openpyxl')``
    """

    def __init__(self, raw_dir: Path = _RAW_DIR) -> None:
        self._raw_dir = raw_dir

    # -- DriveDataSource contract -------------------------------------------

    def list_tabular_files(self) -> list[dict]:
        """List .csv / .xlsx files; LibreOffice lock files (.~lock*) are skipped."""
        files = [
            {"id": str(f), "name": f.name, "mimeType": _mime_for(f)}
            for f in sorted(self._raw_dir.iterdir())
            if f.suffix.lower() in {".csv", ".xlsx", ".xls"}
            and not f.name.startswith(".~lock")
        ]
        logger.info(
            "LocalRawSource: found %d tabular file(s) in %s",
            len(files), self._raw_dir,
        )
        return files

    def read_as_dataframe(self, file_meta: dict) -> Optional[pd.DataFrame]:
        """Read one file and return a raw DataFrame (default dtypes)."""
        path  = Path(file_meta["id"])
        mime  = file_meta["mimeType"]
        try:
            if mime == "text/csv":
                df = pd.read_csv(path, sep=None, engine="python")
            else:
                df = pd.read_excel(path, engine="openpyxl")
            logger.info("LocalRawSource: loaded %-35s → %d rows", path.name, len(df))
            return df
        except Exception as exc:          # noqa: BLE001
            logger.warning("LocalRawSource: skipping %s — %s", path.name, exc)
            return None


# ─────────────────────────────────────────────────────────────────────────
# SILVER helpers  (small, pure, independently testable)
# ─────────────────────────────────────────────────────────────────────────

def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename non-private columns to snake_case via _normalise_header.

    Columns that start with ``_`` (internal tracking, e.g. ``_source_file``)
    are kept as-is so downstream functions (dedup, date-parser) can locate them.
    """
    df = df.copy()
    df.columns = [
        col if col.startswith("_") else _normalise_header(col)
        for col in df.columns
    ]
    return df


def _map_canonical(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only mapped columns, rename to canonical silver names.

    The internal ``_source_file`` tracking column is always forwarded.
    """
    available = {k: v for k, v in _RAW_TO_SILVER.items() if k in df.columns}
    missing   = [k for k in _RAW_TO_SILVER if k not in df.columns]
    if missing:
        logger.debug("_map_canonical: unmapped columns (skipped): %s", missing)

    keep = list(available.keys())
    if "_source_file" in df.columns:
        keep.append("_source_file")

    return df[keep].rename(columns=available).copy()


def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    """Parse dates, coerce numerics, clean strings and add cost placeholder.

    Date strategy:
      - datetime64 column (pure XLSX read)  → pd.to_datetime coerce.
      - Object column after concat           → may contain pd.Timestamp
        objects (XLSX rows) mixed with date strings (CSV rows).
        Timestamps are pre-normalised to "YYYY-MM-DD" strings first so
        that _parse_sales_dates_with_source's ISO fallback can handle them
        reliably (str(Timestamp) produces "2026-02-01 00:00:00" which the
        %Y-%m-%d format cannot match due to the time component).

    Cost placeholder:
      ``custo`` (total line-item cost) = 0.0.  Must be enriched from the
      products catalog (Google Sheets) before the margem calculation in gold
      is meaningful.
    """
    df = df.copy()

    # ── Dates ──────────────────────────────────────────────────────────────
    if "data" in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df["data"]):
            df["data"] = pd.to_datetime(df["data"], errors="coerce")
        else:
            # Pre-normalise: convert any pd.Timestamp objects in the mixed
            # object column to "YYYY-MM-DD" strings so the domain parser can
            # apply its ISO fallback.  Plain date strings (e.g. "2/1/2026")
            # are left unchanged so per-source format detection still works.
            df["data"] = df["data"].map(
                lambda v: v.strftime("%Y-%m-%d")
                if isinstance(v, pd.Timestamp)
                else (None if (isinstance(v, float) and np.isnan(v)) else v)
            )
            df = _parse_sales_dates_with_source(df)
            df = df.drop(columns=[c for c in ("data_raw", "parse_strategy") if c in df.columns])

    # ── Numerics ───────────────────────────────────────────────────────────
    for col in _NUMERIC_COLS:
        if col in df.columns:
            df[col] = _to_numeric(df[col]).fillna(0.0)

    # ── String columns: normalise whitespace, drop "nan" artefacts ─────────
    _STR_COLS = [
        "cliente", "produto", "unidade_medida", "cidade_cliente",
        "tipo_item", "tipo_negociacao", "nota_fiscal",
    ]
    for col in _STR_COLS:
        if col in df.columns:
            df[col] = (
                df[col]
                .fillna("")
                .astype(str)
                .str.strip()
                .replace({"nan": "", "None": "", "NaT": ""})
            )

    # ── produto_key: fuzzy-normalised name for cross-file dedup ────────────
    if "produto" in df.columns:
        df["produto_key"] = df["produto"].apply(_normalise_value)

    # ── Cost placeholder ───────────────────────────────────────────────────
    df["custo"] = 0.0

    return df


def _validate_no_nulls(
    df: pd.DataFrame,
    table: str,
    key_cols: list[str],
) -> pd.DataFrame:
    """Drop rows with null values in key columns and warn about each drop.

    Returns a clean copy of *df* with no null values in *key_cols*.
    """
    clean = df.copy()
    for col in key_cols:
        if col not in clean.columns:
            continue
        null_mask  = clean[col].isna()
        null_count = int(null_mask.sum())
        if null_count:
            logger.warning(
                "[Integrity] %s.%s: dropping %d row(s) with null key.",
                table, col, null_count,
            )
            clean = clean[~null_mask]
    return clean.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────
# RAW → SILVER  (public API)
# ─────────────────────────────────────────────────────────────────────────

def load_raw(source: LocalRawSource) -> pd.DataFrame:
    """Extract all tabular files from raw layer; tag each row with _source_file.

    Returns a single concatenated DataFrame (may contain cross-file duplicates).
    """
    files = source.list_tabular_files()
    if not files:
        logger.warning("load_raw: no tabular files found in %s", source._raw_dir)
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    for meta in files:
        df = source.read_as_dataframe(meta)
        if df is None or df.empty:
            continue
        df["_source_file"] = meta["name"]
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    logger.info(
        "load_raw: %d total row(s) from %d file(s) — cross-file dedup pending.",
        len(combined), len(frames),
    )
    return combined


def transform_to_silver(
    raw_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """Apply the full raw → silver transformation.

    Pipeline:
        normalise_columns → map_canonical → coerce_types
        → cross-file dedup → add lineage metadata → project to SILVER_COLUMNS

    Returns:
        (silver_df, audit_dict)
    """
    df = _normalise_columns(raw_df)
    df = _map_canonical(df)
    df = _coerce_types(df)

    # Cross-file deduplication (uses num_venda + produto_key when present)
    df, audit = _deduplicate_with_audit(df)

    # Promote internal tracking column and add ingestion timestamp
    df = df.rename(columns={"_source_file": "source_file"})
    df["ingested_at_utc"] = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")

    # Drop helpers that are not part of the silver schema
    df = df.drop(columns=[c for c in ("produto_key",) if c in df.columns])

    # Fill any missing silver columns with pd.NA and reorder
    for col in SILVER_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[SILVER_COLUMNS].reset_index(drop=True)

    return df, audit


def run_raw_to_silver(
    source: Optional[LocalRawSource] = None,
    output_dir: Path = _SILVER_DIR,
) -> pd.DataFrame:
    """Orchestrate RAW → SILVER; persist result as Parquet.

    Returns the silver DataFrame.
    """
    if source is None:
        source = LocalRawSource()

    raw_df = load_raw(source)
    if raw_df.empty:
        logger.error("run_raw_to_silver: no raw data — aborting silver stage.")
        return pd.DataFrame()

    silver_df, audit = transform_to_silver(raw_df)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "sales_silver.parquet"
    silver_df.to_parquet(out_path, index=False, engine="pyarrow", compression="snappy")

    logger.info(
        "run_raw_to_silver: %d rows saved → %s  "
        "[dedup removed %d duplicate(s) across %d file(s)]",
        len(silver_df),
        out_path,
        audit.get("removed", 0),
        len(source.list_tabular_files()),
    )
    return silver_df


# ─────────────────────────────────────────────────────────────────────────
# GOLD helpers  — star schema dimensions and fact table
# ─────────────────────────────────────────────────────────────────────────

def build_dim_produto(silver_df: pd.DataFrame) -> pd.DataFrame:
    """Build dim_produto with 1-based integer surrogate key.

    Schema: produto_id (int64), nome_produto (str)

    Dedup: case-sensitive unique product names (strip only).
    Rows with empty ``produto`` are excluded.
    """
    s = (
        silver_df["produto"]
        .astype(str)
        .str.strip()
        .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "NaT": pd.NA})
        .dropna()
        .drop_duplicates()
        .sort_values()
        .reset_index(drop=True)
    )
    dim = pd.DataFrame({"produto_id": s.index + 1, "nome_produto": s.values})
    dim = _validate_no_nulls(dim, "dim_produto", ["produto_id", "nome_produto"])
    logger.info("build_dim_produto: %d unique product(s)", len(dim))
    return dim


def build_dim_tempo(silver_df: pd.DataFrame) -> pd.DataFrame:
    """Build dim_tempo with 1-based integer surrogate key.

    Schema:
        data_id (int64), data (datetime64), dia (int), mes (int),
        ano (int), trimestre (int), dia_semana (int, 0=Mon), nome_mes (str)

    Rows where ``data`` is NaT are excluded.
    """
    dates = (
        _to_day(silver_df["data"])
        .dropna()
        .drop_duplicates()
        .sort_values()
        .reset_index(drop=True)
    )
    # Use DatetimeIndex for field extraction (avoids IDE false-positives on .dt)
    dti = pd.DatetimeIndex(dates)
    dim = pd.DataFrame({
        "data_id":    dates.index + 1,
        "data":       dates.values,
        "dia":        dti.day,
        "mes":        dti.month,
        "ano":        dti.year,
        "trimestre":  dti.quarter,
        "dia_semana": dti.weekday,        # 0 = Segunda … 6 = Domingo
        "nome_mes":   [_MONTH_PT[m] for m in dti.month],
    })
    dim = _validate_no_nulls(dim, "dim_tempo", ["data_id", "data"])
    logger.info("build_dim_tempo: %d unique date(s)", len(dim))
    return dim


def build_fato_vendas(
    silver_df: pd.DataFrame,
    dim_produto: pd.DataFrame,
    dim_tempo: pd.DataFrame,
) -> pd.DataFrame:
    """Build fato_vendas by joining silver with dim_produto and dim_tempo.

    Schema:
        venda_id (int64) — surrogate PK for each line item
        produto_id (int64 FK → dim_produto)
        data_id    (int64 FK → dim_tempo)
        num_venda  (int64)  — business sale number
        cliente    (str)
        quantidade (float64)
        valor_unitario (float64) — selling price per unit
        valor_total    (float64) — total amount for this line item
        custo          (float64) — total line-item cost
                                   (0.0 placeholder; enrich from catalog)
        margem         (float64) — (valor_total - custo) / quantidade
                                   i.e. contribution margin per unit sold

    NOTE: custo = 0.0 until the enrichment step connects this table to the
    products catalog from Google Sheets. The margem formula is deterministic
    and will produce correct values once custo is populated.
    """
    df = silver_df.copy()

    # ── Prepare join keys ──────────────────────────────────────────────────
    df["produto"] = df["produto"].astype(str).str.strip().replace({"nan": "", "": pd.NA})
    df["data"]    = _to_day(df["data"])

    # ── Join dim_produto  (on nome_produto = produto) ──────────────────────
    df = df.merge(
        dim_produto.rename(columns={"nome_produto": "produto"}),
        on="produto",
        how="left",
    )

    # ── Join dim_tempo  (on data) ──────────────────────────────────────────
    dim_tempo_keys = dim_tempo[["data_id", "data"]].copy()
    dim_tempo_keys["data"] = _to_day(dim_tempo_keys["data"])
    df = df.merge(dim_tempo_keys, on="data", how="left")

    # ── Margem  (vectorised, avoids apply overhead) ────────────────────────
    # Formula: margem = (valor_total - custo) / quantidade
    valid_qty = df["quantidade"].notna() & (df["quantidade"] > 0)
    df["margem"] = 0.0
    df.loc[valid_qty, "margem"] = (
        (df.loc[valid_qty, "valor_total"] - df.loc[valid_qty, "custo"])
        / df.loc[valid_qty, "quantidade"]
    )

    # ── Select fact columns ────────────────────────────────────────────────
    fato = df[[
        "produto_id", "data_id",
        "num_venda", "cliente",
        "quantidade", "valor_unitario", "valor_total",
        "custo", "margem",
    ]].copy()

    # ── Integrity: drop rows with null FKs ────────────────────────────────
    fato = _validate_no_nulls(fato, "fato_vendas", ["produto_id", "data_id"])

    # ── Surrogate PK (after FK cleaning) ──────────────────────────────────
    fato = fato.reset_index(drop=True)
    fato.insert(0, "venda_id", fato.index + 1)

    logger.info("build_fato_vendas: %d row(s)", len(fato))
    return fato


def validate_star_schema(
    fato: pd.DataFrame,
    dim_produto: pd.DataFrame,
    dim_tempo: pd.DataFrame,
) -> dict[str, object]:
    """Validate referential integrity of the star schema.

    Checks:
        1. All fato.produto_id ∈ dim_produto.produto_id
        2. All fato.data_id    ∈ dim_tempo.data_id
        3. fato.venda_id has no nulls (PK integrity)
        4. margem has no ±inf values

    Returns a dict of check results; 'all_ok' is True only if all pass.
    """
    results: dict[str, object] = {}

    # 1. FK: produto_id
    valid_pids    = set(dim_produto["produto_id"].dropna())
    orphan_prod   = int((~fato["produto_id"].isin(valid_pids)).sum())
    results["fk_produto_id_ok"]      = orphan_prod == 0
    results["fk_produto_id_orphans"] = orphan_prod

    # 2. FK: data_id
    valid_dids   = set(dim_tempo["data_id"].dropna())
    orphan_data  = int((~fato["data_id"].isin(valid_dids)).sum())
    results["fk_data_id_ok"]         = orphan_data == 0
    results["fk_data_id_orphans"]    = orphan_data

    # 3. PK: venda_id
    null_pk      = int(fato["venda_id"].isna().sum())
    results["pk_venda_id_ok"]        = null_pk == 0
    results["pk_venda_id_nulls"]     = null_pk

    # 4. Margem: no infinite values
    inf_count    = int(np.isinf(fato["margem"].fillna(0)).sum())
    results["margem_no_inf_ok"]      = inf_count == 0
    results["margem_inf_count"]      = inf_count

    # 5. Row counts
    results["fato_rows"]        = len(fato)
    results["dim_produto_rows"] = len(dim_produto)
    results["dim_tempo_rows"]   = len(dim_tempo)

    all_ok = all(
        v
        for k, v in results.items()
        if isinstance(v, bool)
    )
    results["all_ok"] = all_ok

    status = "✅ PASSED" if all_ok else "❌ FAILED"
    logger.info("validate_star_schema: %s", status)
    for k, v in results.items():
        logger.info("  %-30s: %s", k, v)

    return results


# ─────────────────────────────────────────────────────────────────────────
# Cost enrichment  (SILVER custo ← Products catalog)
# ─────────────────────────────────────────────────────────────────────────

def enrich_cost_from_catalog(
    silver_df: pd.DataFrame,
    cost_map: dict[str, float],
) -> pd.DataFrame:
    """Update the ``custo`` column in silver using a product-name → cost mapping.

    The join uses normalised product names (lowercase, no accents, trimmed)
    to be tolerant of minor formatting differences between the sales files
    and the Google Sheets products catalog.

    Args:
        silver_df: Silver DataFrame with ``produto`` and ``custo`` columns.
        cost_map:  Dict mapping *normalised* product name to total production
                   cost per unit (from the Receita + Matéria Prima sheets).

    Returns:
        Copy of *silver_df* with ``custo`` populated where a catalog match was
        found; unmatched rows keep their existing value (0.0 placeholder).
    """
    if not cost_map:
        logger.info("enrich_cost_from_catalog: cost_map is empty — skipping enrichment.")
        return silver_df.copy()

    df     = silver_df.copy()
    keys   = df["produto"].apply(_normalise_value)
    mapped = keys.map(cost_map)          # NaN where no match

    # Only overwrite rows where a match was found
    matched_mask  = mapped.notna()
    matched_count = int(matched_mask.sum())
    df.loc[matched_mask, "custo"] = mapped[matched_mask].astype(float)

    total    = len(df)
    pct      = 100.0 * matched_count / total if total else 0.0
    logger.info(
        "enrich_cost_from_catalog: enriched %d / %d row(s) (%.1f%%).",
        matched_count, total, pct,
    )
    if matched_count < total:
        unmatched = df.loc[~matched_mask, "produto"].unique()
        logger.warning(
            "enrich_cost_from_catalog: %d unmatched product(s): %s",
            len(unmatched), list(unmatched[:10]),
        )
    return df


def load_cost_catalog_from_sheets() -> dict[str, float]:
    """Load production costs from Google Sheets via ``ProductAnalysisService``.

    Requires environment variables:
        GOOGLE_APPLICATION_CREDENTIALS  — path to the service-account JSON key
        GOOGLE_SHEET_ID                 — the target spreadsheet ID

    Returns a dict mapping *normalised* product name → production cost (float).
    Returns an empty dict (safe default) if the connection fails or the env
    vars are missing.
    """
    import os

    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    sheet_id   = os.getenv("GOOGLE_SHEET_ID")
    if not creds_path or not sheet_id:
        logger.warning(
            "load_cost_catalog: env vars GOOGLE_APPLICATION_CREDENTIALS / "
            "GOOGLE_SHEET_ID not set — cost enrichment skipped."
        )
        return {}

    try:
        from src.infrastructure.google_sheets_adapter import GoogleSheetsAdapter  # noqa: PLC0415
        from src.domain.product_analysis_service import ProductAnalysisService    # noqa: PLC0415

        adapter = GoogleSheetsAdapter(creds_path=creds_path, sheet_id=sheet_id)
        service = ProductAnalysisService(adapter)
        summary = service.get_product_cost_summary()

        if summary.empty:
            logger.warning("load_cost_catalog: empty cost summary returned from Sheets.")
            return {}

        # Detect the product name column (may be "Produto" or "Nome do Produto")
        name_col = next(
            (c for c in ("Produto", "Nome do Produto") if c in summary.columns),
            None,
        )
        cost_col = next(
            (c for c in ("Custo Total (R$)", "Custo Total") if c in summary.columns),
            None,
        )
        if not name_col or not cost_col:
            logger.warning(
                "load_cost_catalog: expected columns not found in summary: %s",
                list(summary.columns),
            )
            return {}

        cost_map: dict[str, float] = {}
        for _, row in summary.iterrows():
            nome  = str(row[name_col]).strip()
            custo = row[cost_col]
            if nome and not pd.isna(custo):
                cost_map[_normalise_value(nome)] = float(custo)

        logger.info(
            "load_cost_catalog: loaded %d product cost(s) from Google Sheets.",
            len(cost_map),
        )
        return cost_map

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "load_cost_catalog: failed to load from Google Sheets — %s. "
            "Continuing with custo=0.0 placeholder.",
            exc,
        )
        return {}


# ─────────────────────────────────────────────────────────────────────────
# SILVER → GOLD  (public API)
# ─────────────────────────────────────────────────────────────────────────

def run_silver_to_gold(
    silver_df: Optional[pd.DataFrame] = None,
    silver_dir: Path = _SILVER_DIR,
    gold_dir: Path = _GOLD_DIR,
    enrich_cost: bool = False,
) -> dict[str, pd.DataFrame]:
    """Orchestrate SILVER → GOLD; persist all star-schema tables as Parquet.

    Args:
        silver_df:    Pre-loaded silver DataFrame.  If *None* the silver Parquet
                      in *silver_dir* is loaded automatically.
        silver_dir:   Directory containing ``sales_silver.parquet``.
        gold_dir:     Output directory for gold Parquet files.
        enrich_cost:  When *True*, attempt to load production costs from Google
                      Sheets (requires env vars) and populate ``fato_vendas.custo``
                      and ``fato_vendas.margem`` with real values.

    Returns:
        Dict with keys ``dim_produto``, ``dim_tempo``, ``fato_vendas``.

    Raises:
        FileNotFoundError: If *silver_df* is None and the silver file is absent.
    """
    # ── Load silver ────────────────────────────────────────────────────────
    if silver_df is None:
        silver_path = silver_dir / "sales_silver.parquet"
        if not silver_path.exists():
            raise FileNotFoundError(
                f"Silver file not found: {silver_path}\n"
                "Run the pipeline with --silver (or no flag) first."
            )
        silver_df = pd.read_parquet(silver_path, engine="pyarrow")
        logger.info(
            "run_silver_to_gold: loaded %d row(s) from silver.", len(silver_df)
        )

    # ── Optional cost enrichment (before gold build so margem is correct) ──
    if enrich_cost:
        logger.info("run_silver_to_gold: loading cost catalog from Google Sheets…")
        cost_map = load_cost_catalog_from_sheets()
        silver_df = enrich_cost_from_catalog(silver_df, cost_map)

    # ── Build dimensions ───────────────────────────────────────────────────
    dim_produto = build_dim_produto(silver_df)
    dim_tempo   = build_dim_tempo(silver_df)

    # ── Build fact table ───────────────────────────────────────────────────
    fato_vendas = build_fato_vendas(silver_df, dim_produto, dim_tempo)

    # ── Validate star schema ───────────────────────────────────────────────
    validation = validate_star_schema(fato_vendas, dim_produto, dim_tempo)
    if not validation["all_ok"]:
        logger.warning(
            "run_silver_to_gold: validation FAILED — gold tables saved anyway "
            "but referential integrity must be investigated."
        )

    # ── Persist gold tables ────────────────────────────────────────────────
    gold_dir.mkdir(parents=True, exist_ok=True)
    tables: dict[str, pd.DataFrame] = {
        "dim_produto": dim_produto,
        "dim_tempo":   dim_tempo,
        "fato_vendas": fato_vendas,
    }
    for name, df in tables.items():
        out_path = gold_dir / f"{name}.parquet"
        df.to_parquet(out_path, index=False, engine="pyarrow", compression="snappy")
        logger.info(
            "run_silver_to_gold: saved %-25s → %s  (%d rows)",
            name, out_path, len(df),
        )

    return tables


# ─────────────────────────────────────────────────────────────────────────
# Full pipeline orchestration
# ─────────────────────────────────────────────────────────────────────────

def run_pipeline(enrich_cost: bool = False) -> None:
    """Execute the full RAW → SILVER → GOLD pipeline."""
    _sep = "=" * 60
    logger.info(_sep)
    logger.info("Medallion Pipeline — Vava Doces — RAW → SILVER → GOLD")
    logger.info(_sep)

    silver_df = run_raw_to_silver()
    if silver_df.empty:
        logger.error("Pipeline aborted: silver stage produced no data.")
        return

    run_silver_to_gold(silver_df=silver_df, enrich_cost=enrich_cost)

    logger.info(_sep)
    logger.info("Pipeline complete.")
    logger.info("  Silver : %s/sales_silver.parquet", _SILVER_DIR)
    logger.info("  Gold   : %s/{dim_produto,dim_tempo,fato_vendas}.parquet", _GOLD_DIR)
    logger.info(_sep)


# ─────────────────────────────────────────────────────────────────────────
# Star-schema join validation demo (run_validate)
# ─────────────────────────────────────────────────────────────────────────

def run_validate() -> bool:
    """Load gold tables from disk and run FK / PK / margem integrity checks.

    Prints a cross-join sample to confirm dim→fato joins work end-to-end.
    Returns True if all checks pass.
    """
    required = {
        "dim_produto": _GOLD_DIR / "dim_produto.parquet",
        "dim_tempo":   _GOLD_DIR / "dim_tempo.parquet",
        "fato_vendas": _GOLD_DIR / "fato_vendas.parquet",
    }
    missing = [k for k, p in required.items() if not p.exists()]
    if missing:
        logger.error(
            "run_validate: missing gold file(s): %s\n"
            "Run 'python scripts/medallion_pipeline.py' first.",
            missing,
        )
        return False

    dim_p = pd.read_parquet(required["dim_produto"], engine="pyarrow")
    dim_t = pd.read_parquet(required["dim_tempo"],   engine="pyarrow")
    fato  = pd.read_parquet(required["fato_vendas"], engine="pyarrow")

    # Integrity checks
    results = validate_star_schema(fato, dim_p, dim_t)

    # Join demo: fato ⋈ dim_produto ⋈ dim_tempo
    enriched = (
        fato
        .merge(dim_p, on="produto_id", how="left")
        .merge(dim_t[["data_id", "data", "mes", "ano", "nome_mes"]], on="data_id", how="left")
    )
    print("\n── Star-schema join sample (5 rows) ──────────────────────────────────────")
    print(
        enriched[["venda_id", "nome_produto", "data", "mes", "ano",
                  "quantidade", "valor_total", "custo", "margem"]]
        .head(5)
        .to_string(index=False)
    )

    # Summary
    print(f"\n  fato_vendas   : {len(fato):>6,} rows")
    print(f"  dim_produto   : {len(dim_p):>6,} unique products")
    print(f"  dim_tempo     : {len(dim_t):>6,} unique dates")
    print(f"  Join coverage : {len(enriched[enriched['nome_produto'].notna()]):>6,} / {len(fato)} rows have produto match")
    print(f"  All checks    : {'✅ PASSED' if results['all_ok'] else '❌ FAILED'}\n")

    return bool(results["all_ok"])


# ─────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Vava Doces Medallion Pipeline: raw → silver → gold",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/medallion_pipeline.py\n"
            "  python scripts/medallion_pipeline.py --silver\n"
            "  python scripts/medallion_pipeline.py --gold\n"
            "  python scripts/medallion_pipeline.py --gold --enrich-cost\n"
            "  python scripts/medallion_pipeline.py --validate\n"
        ),
    )
    group = p.add_mutually_exclusive_group()
    group.add_argument("--silver",   action="store_true", help="Run raw → silver only")
    group.add_argument("--gold",     action="store_true", help="Run silver → gold only (silver must exist)")
    group.add_argument("--validate", action="store_true", help="Validate star-schema joins (gold must exist)")
    p.add_argument(
        "--enrich-cost",
        action="store_true",
        default=False,
        help=(
            "Enrich fato_vendas.custo with production costs from Google Sheets "
            "(requires GOOGLE_APPLICATION_CREDENTIALS + GOOGLE_SHEET_ID env vars)."
        ),
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.silver:
        run_raw_to_silver()
    elif args.gold:
        run_silver_to_gold(enrich_cost=args.enrich_cost)
    elif args.validate:
        ok = run_validate()
        sys.exit(0 if ok else 1)
    else:
        run_pipeline(enrich_cost=args.enrich_cost)

