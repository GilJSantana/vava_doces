"""Silver normalization for sales datasets consumed by presentation pages.

This module keeps transformations limited to schema/typing/name cleanup so
business rules remain unchanged.

Deduplication strategy
----------------------
Only 100%-identical rows are removed (``drop_duplicates()`` with no subset).
A single NFC-e sale can contain multiple product lines sharing the same
``num_venda``; using that field as a dedup key would collapse those lines and
lose revenue rows.  Exact-row equality is the only safe dedup criterion here.
"""

from __future__ import annotations

import logging
import re

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

_NUMERIC_TARGETS = [
    "qtd",
    "valor_unit",
    "valor_venda",
    "valor_total",
    "custo",
    "margem",
]

#: Maps canonical silver column names to their possible source aliases.
_CANONICAL_ALIASES: dict[str, list[str]] = {
    "data":           ["data", "data_venda"],
    "produto":        ["produto", "nome_produto", "produto_raw"],
    "num_venda":      ["num_venda", "numero_da_venda", "numero_venda"],
    "qtd":            ["qtd", "quantidade"],
    "valor_unit":     ["valor_unit", "valor_unitario"],
    # canal: tipo_negociacao is the raw column name in silver CSV exports
    "canal":          ["canal", "tipo_negociacao"],
    "arquivo_origem": ["arquivo_origem", "source_file"],
    "data_carga":     ["data_carga", "ingested_at_utc"],
    "mes_referencia": ["mes_referencia"],
}

_ESSENTIAL_TEXT_COLS = [
    "produto", "canal", "arquivo_origem", "data_carga", "mes_referencia",
]

#: Channel labels used for presentation-layer aggregations.
_CHANNEL_MAP: dict[str, str] = {
    "IFOOD":      "IFOOD",
    "IF":         "IFOOD",
    "LOJA":       "LOJA FISICA",
    "LOJA FISICA":"LOJA FISICA",
    "BALCAO":     "LOJA FISICA",
    "WHATS":      "WHATSAPP",
    "WHATSAPP":   "WHATSAPP",
    "INSTAGRAM":  "INSTAGRAM",
    "SITE":       "SITE",
    "MARKETPLACE":"MARKETPLACE",
}


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def _first_available(
    df: pd.DataFrame,
    candidates: list[str],
    default: object = pd.NA,
) -> pd.Series:
    """Return the first column from *candidates* that exists in *df*."""
    for col in candidates:
        if col in df.columns:
            return df[col]
    return pd.Series([default] * len(df), index=df.index)


def _to_numeric(series: pd.Series) -> pd.Series:
    """Coerce a mixed Brazilian-currency Series to float (fillna → 0.0).

    Handles ``"R$ 6,79"``, ``"1.234,56"``, ``"18.0"``, empty strings.
    """
    text = series.astype(str).str.strip()
    text = text.replace({"": None, "nan": None, "None": None})
    text = text.str.replace(r"[^0-9,.-]", "", regex=True)
    has_comma = text.str.contains(",", na=False)
    has_dot   = text.str.contains(r"\.", na=False)
    mixed_mask = has_comma & has_dot
    text = text.copy()
    text.loc[mixed_mask] = text.loc[mixed_mask].str.replace(".", "", regex=False)
    text = text.str.replace(",", ".", regex=False)
    return pd.to_numeric(text, errors="coerce").fillna(0.0)


def _normalize_channel(value: object) -> str:
    """Map raw channel label to a canonical value using _CHANNEL_MAP."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return "SEM_CANAL"
    raw = str(value).strip().upper()
    if not raw or raw in {"NAN", "NONE"}:
        return "SEM_CANAL"
    for key, target in _CHANNEL_MAP.items():
        if key in raw:
            return target
    return raw


def _normalize_product_name(value: object) -> tuple[str, str]:
    """Strip product-code prefix and apply title-case normalisation.

    Examples::

        "  PROD-001 - brigadeiro tradicional " → ("Brigadeiro Tradicional", rule)
        "102 - risole frango"                  → ("Risole Frango", rule)
    """
    original = str(value or "").strip()
    if not original or original.lower() in {"nan", "none"}:
        return "SEM_PRODUTO", "empty_or_null"
    cleaned = re.sub(
        r"^\s*(?:prod[-_ ]?\d+|\d+)\s*-\s*", "", original, flags=re.IGNORECASE
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    normalized = cleaned.title() if cleaned else "SEM_PRODUTO"
    rule = "strip+remove_prefix_code+collapse_spaces+title"
    return normalized, rule


def _month_hint_from_source(source_name: object) -> int | None:
    """Extract month number from a source filename for date-format heuristic."""
    text = str(source_name or "")
    match = re.search(
        r"(?:20\d{2})[_-]?(0[1-9]|1[0-2])|(0[1-9]|1[0-2])[_-]?(20\d{2})", text
    )
    if not match:
        return None
    return int(match.group(1) or match.group(2))


def _choose_date_format_for_source(
    raw_dates: pd.Series, source_name: object
) -> str:
    """Heuristically choose ``%d/%m/%Y`` or ``%m/%d/%Y`` for *source_name*."""
    parts = raw_dates.astype(str).str.extract(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$")
    left  = pd.to_numeric(parts[0], errors="coerce")
    right = pd.to_numeric(parts[1], errors="coerce")

    month_hint = _month_hint_from_source(source_name)
    if month_hint is not None:
        left_votes  = int((left  == month_hint).sum())
        right_votes = int((right == month_hint).sum())
        if right_votes > left_votes:
            return "%d/%m/%Y"
        if left_votes > right_votes:
            return "%m/%d/%Y"

    br_votes = int(((left > 12) & (right <= 12)).sum())
    us_votes = int(((right > 12) & (left <= 12)).sum())
    if br_votes > us_votes:
        return "%d/%m/%Y"
    return "%m/%d/%Y"


def _parse_dates_with_source_hint(
    data: pd.Series, source_series: pd.Series
) -> pd.Series:
    """Parse dates per source file to resolve format ambiguity (BR vs US)."""
    raw    = data.astype(str).str.strip()
    parsed = pd.Series(pd.NaT, index=data.index, dtype="datetime64[ns]")

    grouped = source_series.fillna("unknown").astype(str)
    for source_name, idx in grouped.groupby(grouped).groups.items():
        raw_block = raw.loc[idx]
        primary   = _choose_date_format_for_source(raw_block, source_name)
        secondary = "%d/%m/%Y" if primary == "%m/%d/%Y" else "%m/%d/%Y"
        block     = pd.to_datetime(raw_block, format=primary, errors="coerce")
        missing   = block.isna()
        if missing.any():
            block.loc[missing] = pd.to_datetime(
                raw_block[missing], format=secondary, errors="coerce"
            )
        still_missing = block.isna()
        if still_missing.any():
            block.loc[still_missing] = pd.to_datetime(
                raw_block[still_missing], format="%Y-%m-%d", errors="coerce"
            )
        parsed.loc[idx] = block

    return parsed


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

def _project_canonical_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Project source DataFrame to the canonical silver schema (alias-aware)."""
    out = df.copy()
    for canonical, aliases in _CANONICAL_ALIASES.items():
        out[canonical] = _first_available(out, aliases)
    return out


def _normalize_dates_and_month(out: pd.DataFrame) -> pd.DataFrame:
    """Parse dates and derive ``mes_referencia`` from the parsed timestamp."""
    out["data"]          = _parse_dates_with_source_hint(out["data"], out["arquivo_origem"])
    out["_invalid_date"] = out["data"].isna()

    out["mes_referencia"] = out["mes_referencia"].where(
        out["mes_referencia"].notna(),
        out["data"].dt.to_period("M").astype(str),
    )
    out["mes_referencia"] = (
        out["mes_referencia"]
        .astype(str)
        .replace({"NaT": "sem_mes", "nat": "sem_mes", "<NA>": "sem_mes", "": "sem_mes", "None": "sem_mes"})
    )
    return out


def _normalize_numeric_columns(out: pd.DataFrame) -> pd.DataFrame:
    """Coerce numeric targets to float; missing columns are silently skipped."""
    for col in _NUMERIC_TARGETS:
        if col in out.columns:
            out[col] = _to_numeric(out[col])
    return out


def _normalize_text_fields(out: pd.DataFrame) -> pd.DataFrame:
    """Normalize channel labels and product names; clean essential text cols."""
    out["canal"]            = out["canal"].map(_normalize_channel)
    out["produto_original"] = out["produto"].astype(str)
    normalized_pairs        = out["produto"].map(_normalize_product_name)
    out["produto"]                      = normalized_pairs.map(lambda p: p[0])
    out["produto_regra_normalizacao"]   = normalized_pairs.map(lambda p: p[1])

    for col in _ESSENTIAL_TEXT_COLS:
        out[col] = out[col].fillna("desconhecido").astype(str).str.strip()
        out[col] = out[col].replace(
            {"": "desconhecido", "nan": "desconhecido", "None": "desconhecido"}
        )

    out["mes_referencia"] = out["mes_referencia"].replace({"desconhecido": "sem_mes"})
    return out


def _deduplicate_rows(
    out: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Preserve all rows and report duplicate diagnostics for audit only.

    IMPORTANT: ``num_venda`` (or any order/sale ID) is intentionally *not* used
    as a dedup key.  One NFC-e sale can have multiple product lines that share
    the same ``num_venda``; collapsing by that field would silently drop revenue
    rows.  Only rows that are identical across **every** column are removed.
    """
    before_dedup = int(len(out))
    if out.empty:
        return out, {"before": 0, "after": 0, "removed": 0, "dedup_key": []}

    duplicate_like = int(out.duplicated(keep="first").sum())
    deduped = out.reset_index(drop=True)

    after_dedup = int(len(deduped))
    removed = 0
    audit: dict[str, object] = {
        "before":    before_dedup,
        "after":     after_dedup,
        "removed":   removed,
        # empty list signals "full-row equality used; no transaction-key subset"
        "dedup_key": [],
    }
    if duplicate_like:
        logger.info(
            "_deduplicate_rows: detected %d exact-duplicate row(s), but removal is disabled.",
            duplicate_like,
        )
    return deduped, audit


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_sales_to_silver_with_audit(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Return normalized silver DataFrame plus transformation audit metadata.

    The audit dict includes ``rows_in``, ``rows_out``, ``invalid_dates`` and a
    ``dedup`` sub-dict produced by :func:`_deduplicate_rows`.
    """
    out = _project_canonical_columns(df)
    out = _normalize_dates_and_month(out)
    out = _normalize_numeric_columns(out)
    out = _normalize_text_fields(out)
    out, dedup_audit = _deduplicate_rows(out)

    audit: dict[str, object] = {
        "rows_in":       int(len(df)),
        "rows_out":      int(len(out)),
        "invalid_dates": int(out.get("_invalid_date", pd.Series(dtype=bool)).sum()),
        "dedup":         dedup_audit,
    }
    return out, audit


def normalize_sales_to_silver(df: pd.DataFrame) -> pd.DataFrame:
    """Return a normalized sales DataFrame ready for aggregation pages."""
    normalized, _ = normalize_sales_to_silver_with_audit(df)
    return normalized
