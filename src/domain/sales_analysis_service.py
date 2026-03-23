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
If the same sale line appears in multiple monthly files (same ``num_venda``
+ ``produto_key``) the duplicates are silently dropped after concat.
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
from src.ports.data_source import DriveDataSource

logger = logging.getLogger(__name__)

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


# ---------------------------------------------------------------------------
# Text helpers  (pure functions — easy to unit-test in isolation)
# ---------------------------------------------------------------------------

def _normalise_header(text: str) -> str:
    """Convert any column header to lowercase snake_case without accents.

    Examples::

        _normalise_header("Nome do produto/serviço")   # → "nome_do_produto_servico"
        _normalise_header("Custo Total Unitário (R$)") # → "custo_total_unitario_r"
    """
    text = str(text or "").strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _normalise_value(text: str) -> str:
    """Normalise a product name for fuzzy key matching.

    Strips, removes accents and lowercases so that
    "Brigadeiro Clássico" and "brigadeiro classico" share the same key.
    """
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

    has_comma = text.str.contains(",", na=False)
    has_dot = text.str.contains(r"\.", na=False)
    mixed_mask = has_comma & has_dot
    text = text.copy()
    text.loc[mixed_mask] = text.loc[mixed_mask].str.replace(".", "", regex=False)
    text = text.str.replace(",", ".", regex=False)
    return pd.to_numeric(text, errors="coerce")


def _parse_sales_date(series: pd.Series) -> pd.Series:
    """Parse sales dates with mixed format support.

    Handles CSV files with inconsistent date formats:
    - Primary: mm/dd/yyyy (US format)
    - Fallback: dd/mm/yyyy (BR format) for dates that fail US parsing
    
    This supports the real-world scenario where a file contains some
    dates in US format and others in BR format.
    """
    text = series.astype(str).str.strip()
    
    # First pass: try US format (mm/dd/yyyy)
    parsed = pd.to_datetime(text, format="%m/%d/%Y", errors="coerce")
    
    # Fallback 1: try BR format for unparsed entries
    missing = parsed.isna()
    if missing.any():
        br_fallback = pd.to_datetime(text[missing], format="%d/%m/%Y", errors="coerce")
        parsed.loc[missing] = br_fallback
    
    # Fallback 2: try ISO format for remaining unparsed entries
    still_missing = parsed.isna()
    if still_missing.any():
        iso_fallback = pd.to_datetime(text[still_missing], format="%Y-%m-%d", errors="coerce")
        parsed.loc[still_missing] = iso_fallback
    
    return parsed


# ---------------------------------------------------------------------------
# Extract layer
# ---------------------------------------------------------------------------

class SalesFilesExtractor:
    """Loads and concatenates all tabular sales files from a Google Drive folder.

    Delegates all Drive I/O to
    :class:`~src.infrastructure.google_drive_adapter.GoogleDriveAdapter`.
    """

    def __init__(self, drive_adapter: DriveDataSource) -> None:
        self._adapter = drive_adapter

    def extract(self) -> pd.DataFrame:
        """Return every monthly file concatenated into one DataFrame.

        Each row is tagged with ``_source_file`` for lineage tracing.
        Returns an empty DataFrame if no files are found or all fail to parse.
        """
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
        self._sheet_id = sheet_id
        self._tab_name = tab_name

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
        missing = [k for k in _SALES_COL_MAP if k not in df.columns]
        if missing:
            logger.debug("SalesTransformer: missing columns in sales data: %s", missing)

        keep = list(available.keys())
        if "_source_file" in df.columns:
            keep.append("_source_file")

        df = df[keep].rename(columns=available).copy()

        if "data" in df.columns:
            df["data_raw"] = df["data"].astype(str).str.strip()
            df["data"] = _parse_sales_date(df["data"])

        for col in ("qtd", "valor_venda", "valor_total"):
            if col in df.columns:
                df[col] = _to_numeric(df[col])

        if "produto_raw" in df.columns:
            df["produto_key"] = df["produto_raw"].apply(_normalise_value)

        return df


class ProductsTransformer:
    """Selects, renames and coerces columns in the raw products catalog DataFrame."""

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply column mapping, numeric coercion and derive ``produto_key``."""
        available = {k: v for k, v in _PRODUTOS_COL_MAP.items() if k in df.columns}
        missing = [k for k in _PRODUTOS_COL_MAP if k not in df.columns]
        if missing:
            logger.debug("ProductsTransformer: missing columns in products data: %s", missing)

        df = df[list(available.keys())].rename(columns=available).copy()

        if "custo_unit" in df.columns:
            df["custo_unit"] = _to_numeric(df["custo_unit"])

        if "produto" in df.columns:
            df["produto"] = df["produto"].astype(str).str.strip()
            df["produto_key"] = df["produto"].apply(_normalise_value)
        else:
            df["produto_key"] = pd.Series(dtype=str)

        if "categoria" not in df.columns:
            df["categoria"] = None

        return df


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows that are duplicated across source files.

    Dedup key: ``num_venda`` + ``produto_key`` when both are present;
    falls back to full-row dedup otherwise.
    """
    before = len(df)
    subset = [c for c in ("num_venda", "produto_key") if c in df.columns] or None
    df = df.drop_duplicates(subset=subset)
    removed = before - len(df)
    if removed:
        logger.info("_deduplicate: removed %d duplicate row(s).", removed)
    return df


# ---------------------------------------------------------------------------
# Join layer
# ---------------------------------------------------------------------------

class SalesProductJoiner:
    """Left-joins sales onto the products catalog by normalised product name.

    All sale lines are preserved.  Lines without a catalog match receive
    ``NaN`` cost values and are flagged with ``sem_cadastro=True``.
    """

    def join(self, sales: pd.DataFrame, produtos: pd.DataFrame) -> pd.DataFrame:
        if produtos.empty or "produto_key" not in produtos.columns:
            logger.warning(
                "SalesProductJoiner: products catalog empty — all rows flagged as orphans."
            )
            sales = sales.copy()
            sales["categoria"] = None
            sales["custo_unit"] = float("nan")
            sales["produto"] = sales.get("produto_raw", pd.Series(dtype=str))
            sales["sem_cadastro"] = True
            return sales

        lookup_cols = [c for c in ("produto_key", "produto", "categoria", "custo_unit")
                       if c in produtos.columns]
        merged = sales.merge(produtos[lookup_cols], on="produto_key", how="left")

        merged["sem_cadastro"] = merged["custo_unit"].isna()
        orphans = (
            merged.loc[merged["sem_cadastro"], "produto_raw"]
            .dropna()
            .unique()
        )
        if orphans.size:
            logger.warning(
                "SalesProductJoiner: %d orphan product(s) without catalog match: %s",
                orphans.size,
                sorted(orphans[:10].tolist()),
            )

        return merged


# ---------------------------------------------------------------------------
# Load / output finalisation
# ---------------------------------------------------------------------------

def _finalise(df: pd.DataFrame) -> pd.DataFrame:
    """Compute ``lucro_est``, resolve display ``produto`` and project to OUTPUT_COLUMNS."""
    # Prefer the catalog display name; fall back to raw name from the sales file
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
    """Orchestrates Extract → Transform → Deduplicate → Join → Load.

    Constructor accepts concrete collaborators so unit tests can inject
    in-memory fakes without any network calls.

    Typical usage::

        pipeline = SalesETLPipeline.from_env()
        df = pipeline.run()
        # df.columns → [data, produto, categoria, qtd,
        #                valor_venda, custo_unit, lucro_est, sem_cadastro]
    """

    def __init__(
        self,
        sales_extractor: SalesFilesExtractor,
        products_extractor: ProductsCatalogExtractor,
        sales_transformer: SalesTransformer,
        products_transformer: ProductsTransformer,
        joiner: SalesProductJoiner,
    ) -> None:
        self._sales_extractor = sales_extractor
        self._products_extractor = products_extractor
        self._sales_transformer = sales_transformer
        self._products_transformer = products_transformer
        self._joiner = joiner

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(
        cls,
        credential_file: Optional[str] = None,
        drive_folder_id: Optional[str] = None,
        sales_sheet_id: Optional[str] = None,
        env_file: str | Path = ".env",
    ) -> "SalesETLPipeline":
        """Build a fully-wired pipeline from environment variables.

        Required env vars (unless overridden via arguments):

        * ``GOOGLE_APPLICATION_CREDENTIALS`` — path to Service Account JSON.
        * ``DRIVE_FOLDER_ID``               — Google Drive folder ID.
        * ``SALES_SHEET_ID``                — Controle-de-Vendas-Doceria sheet ID.
        """
        if Path(env_file).exists():
            load_dotenv(env_file)

        cred = credential_file or os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
        folder = drive_folder_id or os.environ["DRIVE_FOLDER_ID"]
        sheet = sales_sheet_id or os.environ["SALES_SHEET_ID"]

        drive_adapter = GoogleDriveAdapter(credential_file=cred, folder_id=folder)

        return cls(
            sales_extractor=SalesFilesExtractor(drive_adapter),
            products_extractor=ProductsCatalogExtractor(
                credential_file=cred,
                sheet_id=sheet,
            ),
            sales_transformer=SalesTransformer(),
            products_transformer=ProductsTransformer(),
            joiner=SalesProductJoiner(),
        )

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self) -> pd.DataFrame:
        """Execute the full ETL pipeline.

        Returns a DataFrame with columns ``OUTPUT_COLUMNS + ['sem_cadastro']``.
        """
        empty = pd.DataFrame(columns=OUTPUT_COLUMNS + ["sem_cadastro"])

        # ── Extract ──────────────────────────────────────────────────
        raw_sales = self._sales_extractor.extract()
        if raw_sales.empty:
            logger.warning("SalesETLPipeline: no sales data — returning empty.")
            return empty

        raw_products = self._products_extractor.extract()

        # ── Transform ────────────────────────────────────────────────
        sales = self._sales_transformer.transform(raw_sales)
        products = self._products_transformer.transform(raw_products)

        # ── Deduplicate ───────────────────────────────────────────────
        sales = _deduplicate(sales)

        # ── Join ──────────────────────────────────────────────────────
        joined = self._joiner.join(sales, products)

        # ── Load ──────────────────────────────────────────────────────
        result = _finalise(joined)
        logger.info("SalesETLPipeline: finished — %d row(s) in output.", len(result))
        return result

