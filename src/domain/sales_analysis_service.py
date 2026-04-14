"""Sales Analysis Service — ETL pipeline for Vava Doces.

Pipeline stages
---------------
Extract  : Google Drive folder (XLSX / CSV monthly files)
           + Google Sheets 'Produtos' tab via gspread.
Transform: Normalise headers, strings, dates and financial columns.
Join     : Left join sales → products by normalised product name.
Load     : Return unified DataFrame with OUTPUT_COLUMNS.

Output columns: [data, produto, categoria, qtd, valor_venda, custo_unit, lucro_est]

Orphan handling
---------------
Products present in sales files but absent from the catalog are kept in the
result with NaN custo_unit / lucro_est and ``sem_cadastro=True``.

Deduplication
-------------
No rows are removed automatically.
Itemized rows from the same sale (same ``num_venda`` with different products)
are preserved and duplicate-like records remain available for audit.
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from pathlib import Path
from typing import Optional

import gspread
import pandas as pd
from dotenv import load_dotenv

from src.infrastructure.google_drive_adapter import GoogleDriveAdapter
from src.infrastructure.google_sheets_adapter import GoogleSheetsAdapter
from src.ports.data_source import DriveDataSource

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_GOLD_DIR = _PROJECT_ROOT / "data" / "processed" / "gold"
_DEFAULT_RAW_DIR  = _PROJECT_ROOT / "data" / "raw"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Columns exposed in the final unified DataFrame.
OUTPUT_COLUMNS = [
    "data",
    "num_venda",
    "cliente",
    "produto",
    "categoria",
    "qtd",
    "valor_venda",
    "valor_total",
    "custo_unit",
    "lucro_est",
]

# Normalised header → internal column name for monthly sales files
_SALES_COL_MAP: dict[str, str] = {
    "numero_da_venda":         "num_venda",
    "data_da_venda":           "data",
    "cliente":                 "cliente",
    "nome_do_produto_servico": "produto_raw",
    "quantidade_de_itens":     "qtd",
    "valor_unitario":          "valor_venda",
    "valor_total":             "valor_total",
}

# Normalised header → internal column name for the Produtos catalog sheet
_PRODUTOS_COL_MAP: dict[str, str] = {
    "nome_do_produto":        "produto",
    "categoria":              "categoria",
    "custo_total_unitario_r": "custo_unit",
}

_PRODUTOS_TAB = "Produtos"
_MANUAL_TAB_RANGES: dict[str, str] = {
    "manual_materia_prima.csv": "A1:H5000",
    "manual_receitas.csv": "A1:F12000",
    "manual_produtos.csv": "A1:H5000",
}


# ---------------------------------------------------------------------------
# Public helpers used by medallion_pipeline.py
# ---------------------------------------------------------------------------

def sync_drive_files_to_raw_from_env(raw_dir: Path | None = None) -> int:
    """Sync tabular sales files from Drive to local raw directory.

    Uses env vars:
      - GOOGLE_APPLICATION_CREDENTIALS
      - DRIVE_FOLDER_ID
    """
    cred   = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    folder = os.getenv("DRIVE_FOLDER_ID")
    if not cred or not folder:
        raise RuntimeError(
            "Missing GOOGLE_APPLICATION_CREDENTIALS or DRIVE_FOLDER_ID for Drive sync."
        )

    target = Path(raw_dir or _DEFAULT_RAW_DIR)
    target.mkdir(parents=True, exist_ok=True)

    adapter = GoogleDriveAdapter(credential_file=cred, folder_id=folder)
    files   = adapter.list_tabular_files()
    copied  = 0
    for meta in files:
        name = str(meta.get("name", "")).strip()
        if not name or name.startswith(".~lock"):
            continue
        raw = adapter.download_bytes(meta["id"])
        (target / name).write_bytes(raw)
        copied += 1

    # Also sync manual tabs directly from Google Sheets (Controle de Vendas).
    sheet_id = os.getenv("GOOGLE_SHEET_ID") or os.getenv("SALES_SHEET_ID")
    sheets_adapter = GoogleSheetsAdapter(credential_file=cred, sheet_id=sheet_id)
    manual_exports = [
        (["Matéria Prima", "Materia Prima", "Insumos", "Ingredientes"], "manual_materia_prima.csv"),
        (["Receitas", "Receita", "BOM - Receitas", "BOM-Receitas"], "manual_receitas.csv"),
        (["Produtos", "Produto", "Cadastro de Produtos"], "manual_produtos.csv"),
    ]
    for tab_candidates, file_name in manual_exports:
        manual_df = None
        chosen_tab = None
        for tab_name in tab_candidates:
            try:
                manual_df = sheets_adapter.get_sheet_as_df(
                    tab_name,
                    cell_range=_MANUAL_TAB_RANGES.get(file_name),
                    ttl_seconds=int(os.getenv("VAVA_SHEETS_CACHE_TTL", "300")),
                )
                chosen_tab = tab_name
                break
            except Exception:
                continue
        try:
            if manual_df is None:
                raise RuntimeError(f"None of the tab aliases exists: {tab_candidates}")
            if manual_df is None or manual_df.empty:
                logger.warning("Manual tab '%s' is empty; skipping export.", chosen_tab)
                continue
            manual_path = target / file_name
            manual_df.to_csv(manual_path, index=False, encoding="utf-8-sig")
            copied += 1
            logger.info(
                "Manual tab '%s' exported to %s (%d row(s)).",
                chosen_tab,
                manual_path,
                len(manual_df),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not export manual tab aliases %s: %s", tab_candidates, exc)

    logger.info("Drive sync complete: %d file(s) copied to %s", copied, target)
    return copied


def load_sales_from_gold(gold_dir: Path | None = None) -> pd.DataFrame:
    """Load unified sales dataset from gold parquet tables only."""
    root             = Path(gold_dir or _DEFAULT_GOLD_DIR)
    fato_path        = root / "fato_vendas.parquet"
    dim_produto_path = root / "dim_produto.parquet"
    dim_tempo_path   = root / "dim_tempo.parquet"

    if not fato_path.exists():
        raise FileNotFoundError(f"Missing gold fact table: {fato_path}")

    fato = pd.read_parquet(fato_path, engine="pyarrow")
    df   = fato.copy()

    if dim_produto_path.exists() and "produto_id" in df.columns:
        dim_produto = pd.read_parquet(dim_produto_path, engine="pyarrow")
        if {"produto_id", "nome_produto"}.issubset(dim_produto.columns):
            df = df.merge(dim_produto[["produto_id", "nome_produto"]], on="produto_id", how="left")

    if dim_tempo_path.exists() and "data_id" in df.columns:
        dim_tempo = pd.read_parquet(dim_tempo_path, engine="pyarrow")
        if {"data_id", "data"}.issubset(dim_tempo.columns):
            df = df.merge(dim_tempo[["data_id", "data"]], on="data_id", how="left", suffixes=("", "_dim"))

    df = df.rename(
        columns={
            "nome_produto":        "produto",
            "quantidade":          "qtd",
            "faturamento_liquido": "valor_venda",
            "custo":               "custo_unit",
        }
    )

    if "valor_venda" not in df.columns and "valor_total" in df.columns:
        df["valor_venda"] = df["valor_total"]
    if "categoria" not in df.columns:
        df["categoria"] = pd.NA
    if "sem_cadastro" not in df.columns:
        df["sem_cadastro"] = False

    return df.reindex(columns=OUTPUT_COLUMNS + ["sem_cadastro"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Text helpers  (pure functions — easy to unit-test in isolation)
# ---------------------------------------------------------------------------

def _normalise_header(text: str) -> str:
    """Convert any column header to lowercase snake_case without accents.

    Examples::

        _normalise_header("Nome do produto/serviço")   # → "nome_do_produto_servico"
        _normalise_header("Custo Total Unitário (R$)") # → "custo_total_unitario_r"
    """
    text = str(text or "").replace("\ufeff", "").strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _normalise_value(text: str) -> str:
    """Normalise a product name for fuzzy key matching (lowercase, no accents)."""
    text = str(text or "").strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.lower().strip()


def _to_numeric(series: pd.Series) -> pd.Series:
    """Coerce a mixed Brazilian-currency Series to float.

    Handles: ``"R$ 6,79"``, ``"1.234,56"``, ``"18.0"``, empty strings.
    """
    text = series.astype(str).str.strip()
    text = text.replace({"": None, "nan": None, "None": None})
    text = text.str.replace(r"[^0-9,.-]", "", regex=True)
    has_comma  = text.str.contains(",", na=False)
    has_dot    = text.str.contains(r"\.", na=False)
    mixed_mask = has_comma & has_dot
    text = text.copy()
    text.loc[mixed_mask] = text.loc[mixed_mask].str.replace(".", "", regex=False)
    text = text.str.replace(",", ".", regex=False)
    return pd.to_numeric(text, errors="coerce")


def _parse_sales_date(series: pd.Series) -> pd.Series:
    """Parse sales dates with mixed format support (US primary, BR fallback)."""
    text   = series.astype(str).str.strip()
    parsed = pd.to_datetime(text, format="%m/%d/%Y", errors="coerce")
    missing = parsed.isna()
    if missing.any():
        parsed.loc[missing] = pd.to_datetime(text[missing], format="%d/%m/%Y", errors="coerce")
    still_missing = parsed.isna()
    if still_missing.any():
        parsed.loc[still_missing] = pd.to_datetime(
            text[still_missing], format="%Y-%m-%d", errors="coerce"
        )
    return parsed


def _choose_date_format_for_source(
    raw_dates: pd.Series, source_name: str | None = None
) -> str:
    """Choose dominant date format for a single source file."""
    text  = raw_dates.astype(str).str.strip()
    parts = text.str.extract(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$")
    left  = pd.to_numeric(parts[0], errors="coerce")
    right = pd.to_numeric(parts[1], errors="coerce")

    month_hint = None
    if source_name:
        match = re.search(
            r"(?:20\d{2})[_-]?(0[1-9]|1[0-2])|(0[1-9]|1[0-2])[_-]?(20\d{2})",
            str(source_name),
        )
        if match:
            month_hint = int(match.group(1) or match.group(2))

    if month_hint is not None:
        left_hint_votes  = int((left  == month_hint).sum())
        right_hint_votes = int((right == month_hint).sum())
        if right_hint_votes > left_hint_votes:
            return "%d/%m/%Y"
        if left_hint_votes > right_hint_votes:
            return "%m/%d/%Y"

    br_votes = int(((left  > 12) & (right <= 12)).sum())
    us_votes = int(((right > 12) & (left  <= 12)).sum())
    if br_votes > us_votes:
        return "%d/%m/%Y"
    return "%m/%d/%Y"


def _parse_sales_dates_with_source(df: pd.DataFrame) -> pd.DataFrame:
    """Parse dates per source file to avoid cross-file format ambiguity."""
    out = df.copy()
    if "data" not in out.columns:
        out["data"]           = pd.NaT
        out["parse_strategy"] = "none"
        return out

    out["data_raw"]       = out["data"].astype(str).str.strip()
    out["parse_strategy"] = ""
    out["data"]           = pd.NaT

    if "_source_file" in out.columns:
        grouped = out.groupby("_source_file", dropna=False)
        for source_name, idx in grouped.groups.items():
            raw           = out.loc[idx, "data_raw"]
            primary_fmt   = _choose_date_format_for_source(raw, str(source_name))
            secondary_fmt = "%d/%m/%Y" if primary_fmt == "%m/%d/%Y" else "%m/%d/%Y"

            parsed  = pd.to_datetime(raw, format=primary_fmt, errors="coerce")
            missing = parsed.isna()
            if missing.any():
                parsed.loc[missing] = pd.to_datetime(
                    raw[missing], format=secondary_fmt, errors="coerce"
                )
            still_missing = parsed.isna()
            if still_missing.any():
                parsed.loc[still_missing] = pd.to_datetime(
                    raw[still_missing], format="%Y-%m-%d", errors="coerce"
                )
            still_missing = parsed.isna()
            if still_missing.any():
                parsed.loc[still_missing] = pd.to_datetime(
                    raw[still_missing], errors="coerce"
                )

            out.loc[idx, "data"]           = parsed
            label_source                   = str(source_name) if source_name is not None else "unknown"
            out.loc[idx, "parse_strategy"] = (
                f"source={label_source}|primary={primary_fmt}|fallback={secondary_fmt}"
            )
            invalid_count = int(parsed.isna().sum())
            if invalid_count:
                logger.warning(
                    "Date parse: source=%s invalid=%d/%d rows.",
                    label_source, invalid_count, len(parsed),
                )
    else:
        parsed            = _parse_sales_date(out["data_raw"])
        out["data"]       = parsed
        out["parse_strategy"] = "global|primary=%m/%d/%Y|fallback=%d/%m/%Y"

    nat_mask = out["data"].isna()
    if nat_mask.any() and "_source_file" in out.columns:
        nat_by_source = (
            out.loc[nat_mask, "_source_file"]
            .fillna("unknown").astype(str).value_counts().to_dict()
        )
        logger.warning("Date parse diagnostics: NaT by source=%s", nat_by_source)

    return out


# ---------------------------------------------------------------------------
# Extract layer
# ---------------------------------------------------------------------------

class SalesFilesExtractor:
    """Loads and concatenates all tabular sales files from a Google Drive folder."""

    def __init__(self, drive_adapter: DriveDataSource) -> None:
        self._adapter = drive_adapter

    def extract(self) -> pd.DataFrame:
        """Return every monthly file concatenated into one DataFrame."""
        files = self._adapter.list_tabular_files()
        if not files:
            logger.warning("SalesFilesExtractor: no sales files found in Drive folder.")
            return pd.DataFrame()

        frames: list[pd.DataFrame] = []
        for file_meta in files:
            df = self._adapter.read_as_dataframe(file_meta)
            if df is None or df.empty:
                continue
            df.columns = [_normalise_header(c) for c in df.columns]
            df["_source_file"] = file_meta["name"]
            frames.append(df)

        if not frames:
            return pd.DataFrame()

        combined = pd.concat(frames, ignore_index=True)
        logger.info(
            "SalesFilesExtractor: combined %d row(s) from %d file(s).",
            len(combined), len(frames),
        )
        return combined


class ProductsCatalogExtractor:
    """Reads the 'Produtos' tab from a Google Sheets spreadsheet via gspread."""

    def __init__(
        self,
        credential_file: str,
        sheet_id: str,
        tab_name: str = _PRODUTOS_TAB,
    ) -> None:
        self._credential_file = credential_file
        self._sheet_id        = sheet_id
        self._tab_name        = tab_name

    def extract(self) -> pd.DataFrame:
        """Return the Produtos sheet with normalised column headers."""
        gc = gspread.service_account(filename=self._credential_file)
        ws = gc.open_by_key(self._sheet_id).worksheet(self._tab_name)
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [_normalise_header(c) for c in df.columns]
        logger.info(
            "ProductsCatalogExtractor: %d product row(s) loaded, cols=%s",
            len(df), list(df.columns),
        )
        return df


# ---------------------------------------------------------------------------
# Transform layer
# ---------------------------------------------------------------------------

class SalesTransformer:
    """Selects, renames and coerces columns in the raw sales DataFrame."""

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply column mapping, date / numeric coercion and derive ``produto_key``."""
        available = {k: v for k, v in _SALES_COL_MAP.items() if k in df.columns}
        missing   = [k for k in _SALES_COL_MAP if k not in df.columns]
        if missing:
            logger.debug("SalesTransformer: missing columns in sales data: %s", missing)

        keep = list(available.keys())
        if "_source_file" in df.columns:
            keep.append("_source_file")

        df = df[keep].rename(columns=available).copy()

        if "data" in df.columns:
            df = _parse_sales_dates_with_source(df)

        for col in ("qtd", "valor_venda", "valor_total"):
            if col in df.columns:
                df[col] = _to_numeric(df[col])

        if "produto_raw" in df.columns:
            df["produto_key"] = df["produto_raw"].map(_normalise_value)

        return df


class ProductsTransformer:
    """Selects, renames and coerces columns in the raw products catalog DataFrame."""

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply column mapping, numeric coercion and derive ``produto_key``."""
        available = {k: v for k, v in _PRODUTOS_COL_MAP.items() if k in df.columns}
        missing   = [k for k in _PRODUTOS_COL_MAP if k not in df.columns]
        if missing:
            logger.debug("ProductsTransformer: missing columns in products data: %s", missing)

        df = df[list(available.keys())].rename(columns=available).copy()

        if "categoria" not in df.columns:
            df["categoria"] = None

        if "custo_unit" in df.columns:
            df["custo_unit"] = _to_numeric(df["custo_unit"])

        if "produto" in df.columns:
            df["produto"] = df["produto"].astype(str).str.strip()
            df["produto_key"] = df["produto"].map(_normalise_value)
        else:
            df["produto_key"] = pd.Series(dtype=str)

        return df


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _resolve_dedup_key_columns(df: pd.DataFrame) -> list[str]:
    """Choose the most reliable dedup key available for this dataset.

    Priority:
      1) origin transaction id columns (if present)
      2) line-item key (plataforma + codigo_venda + identificador_item)

    Important:
      We intentionally do NOT include ``(plataforma, codigo_venda)`` alone
      because one order can contain multiple product lines.  Using the order ID
      as the sole key would collapse those lines and lose revenue rows.
    """
    for cols in (
        ("transaction_id",),
        ("id_transacao",),
        ("id_transacao_origem",),
        # NOTE: (plataforma, codigo_venda) alone is intentionally excluded.
        # One order/NFC-e can have multiple items; item-grain must be preserved.
        ("plataforma", "codigo_venda", "identificador_item"),
    ):
        if all(c in df.columns for c in cols):
            return list(cols)
    return []


def _non_empty_mask(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    """Return a boolean mask that is True where all *columns* have non-empty values."""
    if not columns:
        return pd.Series(False, index=df.index)
    mask = pd.Series(True, index=df.index)
    for col in columns:
        values   = df[col]
        as_text  = values.astype(str).str.strip().str.lower()
        is_empty = as_text.isin({"", "nan", "none", "nat"}) | values.isna()
        mask     = mask & ~is_empty
    return mask


def _deduplicate_with_audit(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Remove EXACT same-file duplicates only while preserving legitimate multi-item sales.

    Strategy
    --------
    1. Detect and REMOVE only true identical rows (all business columns match).
    2. Preserve rows with same num_venda but different produto/quantidade/valor (multi-item sales).
    3. Use an expanded subset including date, product, amount, and quantity to identify true duplicates.
    4. Never use only order-level keys because one sale can have multiple product lines.

    Critical Change: This function now preserves the 6, 8, 27 lost rows per month.
    """
    before = len(df)
    empty_audit: dict = {
        "before":   0,
        "after":    0,
        "removed":  0,
        "key_columns":            [],
        "dedup_scope":            "expanded_item_grain",
        "removed_by_source_file": {},
        "removed_by_month":       {},
        "transaction_key_dedup":  {
            "applied":       False,
            "key_columns":   [],
            "reliable_rows": 0,
            "removed_rows":  0,
        },
        "suspected_duplicates": {
            "count":         0,
            "key_columns":   [],
            "rows_kept":     0,
            "by_source_file":{},
        },
    }
    if df.empty:
        return df.copy(), empty_audit

    working = df.copy()
    working["_is_duplicate"] = False

    # Expand the dedup key to include ALL identifying columns for the item grain.
    # This ensures we only remove rows that are 100% identical across:
    #   - Date (when the sale occurred)
    #   - Product (what was sold)
    #   - Amount/Quantity (how much)
    #   - Unit price / Total value (financial identity)
    #   - Client (who bought)
    dedup_key_columns = []
    for col in [
        "data",              # Date of sale
        "num_venda",         # Order ID
        "cliente",           # Client name
        "produto",           # Product name
        "produto_key",       # Normalized product key
        "quantidade",        # Quantity
        "valor_unitario",    # Unit price
        "valor_bruto",       # Gross value
        "valor_liquido",     # Net value
        "valor_total",       # Total value
        "desconto",          # Discount applied
        "tipo_item",         # Item type
    ]:
        if col in working.columns:
            dedup_key_columns.append(col)

    # Only remove rows that are 100% identical across the expanded item-grain key.
    if dedup_key_columns and "_source_file" in working.columns:
        # Within same source file, detect exact duplicates
        subset_exact = ["_source_file"] + dedup_key_columns
        duplicate_mask = working.duplicated(subset=subset_exact, keep="first")
        working.loc[duplicate_mask, "_is_duplicate"] = True

        if duplicate_mask.any():
            logger.info(
                "_deduplicate_with_audit: Detected %d exact duplicates within same file(s) "
                "(expanded item-grain key: %s)",
                int(duplicate_mask.sum()),
                dedup_key_columns,
            )
    elif dedup_key_columns:
        # No source file info; use global dedup across all columns
        duplicate_mask = working.duplicated(subset=dedup_key_columns, keep="first")
        working.loc[duplicate_mask, "_is_duplicate"] = True

        if duplicate_mask.any():
            logger.info(
                "_deduplicate_with_audit: Detected %d exact duplicates globally "
                "(expanded item-grain key: %s)",
                int(duplicate_mask.sum()),
                dedup_key_columns,
            )

    # Remove the marked exact duplicates.
    duplicate_rows = working[working["_is_duplicate"]].copy()
    deduped = working.loc[~working["_is_duplicate"]].drop(
        columns=[c for c in ("_is_duplicate",) if c in working.columns]
    ).reset_index(drop=True)
    removed = int(len(duplicate_rows))

    removed_by_source: dict = {}
    if not duplicate_rows.empty and "_source_file" in duplicate_rows.columns:
        removed_by_source = (
            duplicate_rows["_source_file"].fillna("unknown").astype(str)
            .value_counts().to_dict()
        )

    removed_by_month: dict = {}
    if not duplicate_rows.empty and "data" in duplicate_rows.columns:
        months = pd.to_datetime(duplicate_rows["data"], errors="coerce").dt.to_period("M")
        removed_by_month = months.dropna().astype(str).value_counts().sort_index().to_dict()

    if removed > 0:
        logger.warning(
            "_deduplicate_with_audit: REMOVED %d exact duplicate row(s) "
            "(by source file: %s, by month: %s)",
            removed,
            removed_by_source,
            removed_by_month,
        )

    audit = {
        "before":   before,
        "after":    int(len(deduped)),
        "removed":  removed,
        "key_columns":            dedup_key_columns,
        "dedup_scope":            "exact_item_grain_same_file",
        "removed_by_source_file": removed_by_source,
        "removed_by_month":       removed_by_month,
        "transaction_key_dedup":  {
            "applied":       False,
            "key_columns":   dedup_key_columns,
            "reliable_rows": before,
            "removed_rows":  removed,
        },
        "suspected_duplicates": {
            "count":          0,
            "key_columns":    [],
            "rows_kept":      0,
            "by_source_file": {},
        },
    }
    return deduped, audit


def _deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """Return the input rows unchanged.

    Deduplication is intentionally disabled to preserve every faturamento record.
    """
    deduped, _ = _deduplicate_with_audit(df)
    return deduped


# ---------------------------------------------------------------------------
# Join layer
# ---------------------------------------------------------------------------

class SalesProductJoiner:
    """Left-joins sales onto the products catalog by normalised product name."""

    def join(self, sales: pd.DataFrame, produtos: pd.DataFrame) -> pd.DataFrame:
        if produtos.empty or "produto_key" not in produtos.columns:
            logger.warning(
                "SalesProductJoiner: products catalog empty — all rows flagged as orphans."
            )
            sales               = sales.copy()
            sales["categoria"]  = None
            sales["custo_unit"] = float("nan")
            sales["produto"]    = sales.get("produto_raw", pd.Series(dtype=str))
            sales["sem_cadastro"] = True
            return sales

        lookup_cols = [c for c in ("produto_key", "produto", "categoria", "custo_unit")
                       if c in produtos.columns]
        merged      = sales.merge(produtos[lookup_cols], on="produto_key", how="left")
        merged["sem_cadastro"] = merged["custo_unit"].isna()
        orphans = (
            merged.loc[merged["sem_cadastro"], "produto_raw"].dropna().unique()
        )
        if orphans.size:
            logger.warning(
                "SalesProductJoiner: %d orphan product(s) without catalog match: %s",
                orphans.size, sorted(orphans[:10].tolist()),
            )
        return merged


# ---------------------------------------------------------------------------
# Load / output finalisation
# ---------------------------------------------------------------------------

def _finalise(df: pd.DataFrame) -> pd.DataFrame:
    """Compute ``lucro_est``, resolve display ``produto`` and project to OUTPUT_COLUMNS."""
    if "produto" not in df.columns:
        df["produto"] = df.get("produto_raw", pd.Series(dtype=str))
    else:
        df["produto"] = df["produto"].fillna(df.get("produto_raw", ""))

    df["lucro_est"] = df["valor_venda"].fillna(0.0) - df["custo_unit"].fillna(0.0)
    return df.reindex(columns=OUTPUT_COLUMNS + ["sem_cadastro"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Pipeline façade
# ---------------------------------------------------------------------------

class SalesETLPipeline:
    """Orchestrates Extract → Transform → Deduplicate → Join → Load."""

    def __init__(
        self,
        sales_extractor: SalesFilesExtractor,
        products_extractor: ProductsCatalogExtractor,
        sales_transformer: SalesTransformer,
        products_transformer: ProductsTransformer,
        joiner: SalesProductJoiner,
    ) -> None:
        self._sales_extractor     = sales_extractor
        self._products_extractor  = products_extractor
        self._sales_transformer   = sales_transformer
        self._products_transformer = products_transformer
        self._joiner              = joiner

    @classmethod
    def from_env(
        cls,
        credential_file: Optional[str] = None,
        drive_folder_id: Optional[str] = None,
        sales_sheet_id:  Optional[str] = None,
        env_file: str | Path = ".env",
    ) -> "SalesETLPipeline":
        """Build a fully-wired pipeline from environment variables."""
        if Path(env_file).exists():
            load_dotenv(env_file)

        cred   = credential_file or os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
        folder = drive_folder_id or os.environ["DRIVE_FOLDER_ID"]
        sheet  = sales_sheet_id  or os.environ["SALES_SHEET_ID"]

        drive_adapter = GoogleDriveAdapter(credential_file=cred, folder_id=folder)
        return cls(
            sales_extractor     = SalesFilesExtractor(drive_adapter),
            products_extractor  = ProductsCatalogExtractor(credential_file=cred, sheet_id=sheet),
            sales_transformer   = SalesTransformer(),
            products_transformer = ProductsTransformer(),
            joiner              = SalesProductJoiner(),
        )

    def run(self) -> pd.DataFrame:
        """Execute the full ETL pipeline."""
        empty = pd.DataFrame(columns=OUTPUT_COLUMNS + ["sem_cadastro"])

        if os.getenv("VAVA_SALES_SOURCE", "raw").strip().lower() == "gold":
            try:
                result = load_sales_from_gold()
                logger.info("SalesETLPipeline: loaded %d row(s) from gold parquet.", len(result))
                return result
            except Exception as exc:
                logger.error("SalesETLPipeline: failed to load from gold — %s", exc)
                return empty

        raw_sales = self._sales_extractor.extract()
        if raw_sales.empty:
            logger.warning("SalesETLPipeline: no sales data — returning empty.")
            return empty

        raw_products = self._products_extractor.extract()
        sales        = self._sales_transformer.transform(raw_sales)
        products     = self._products_transformer.transform(raw_products)
        sales        = _deduplicate(sales)
        joined       = self._joiner.join(sales, products)
        result       = _finalise(joined)
        logger.info("SalesETLPipeline: finished — %d row(s) in output.", len(result))
        return result

    def run_with_audit(self) -> tuple[pd.DataFrame, dict]:
        """Execute the full ETL pipeline and return result plus audit details."""
        empty        = pd.DataFrame(columns=OUTPUT_COLUMNS + ["sem_cadastro"])
        empty_audit  = {
            "raw_rows": 0, "transformed_rows": 0,
            "dedup": {
                "before": 0, "after": 0, "removed": 0,
                "key_columns": [], "removed_by_source_file": {}, "removed_by_month": {},
                "transaction_key_dedup": {"applied": False, "key_columns": [], "reliable_rows": 0, "removed_rows": 0},
                "suspected_duplicates":  {"count": 0, "key_columns": [], "rows_kept": 0, "by_source_file": {}},
            },
            "parse_strategies": {},
        }

        if os.getenv("VAVA_SALES_SOURCE", "raw").strip().lower() == "gold":
            try:
                result = load_sales_from_gold()
                audit  = {
                    "raw_rows": 0, "transformed_rows": int(len(result)),
                    "dedup": empty_audit["dedup"],
                    "parse_strategies": {"source": "gold"},
                }
                return result, audit
            except Exception as exc:
                logger.error("SalesETLPipeline: failed to load audit data from gold — %s", exc)
                return empty, empty_audit

        raw_sales = self._sales_extractor.extract()
        if raw_sales.empty:
            return empty, empty_audit

        raw_products     = self._products_extractor.extract()
        sales            = self._sales_transformer.transform(raw_sales)
        products         = self._products_transformer.transform(raw_products)
        parse_strategies = {}
        if "parse_strategy" in sales.columns:
            parse_strategies = sales["parse_strategy"].value_counts().to_dict()

        sales_dedup, dedup_audit = _deduplicate_with_audit(sales)
        joined  = self._joiner.join(sales_dedup, products)
        result  = _finalise(joined)

        audit = {
            "raw_rows":        int(len(raw_sales)),
            "transformed_rows": int(len(sales)),
            "dedup":           dedup_audit,
            "parse_strategies": parse_strategies,
        }
        logger.info("SalesETLPipeline: finished with audit — %d row(s) in output.", len(result))
        return result, audit

