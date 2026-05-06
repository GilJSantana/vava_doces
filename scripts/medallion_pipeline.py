"""scripts/medallion_pipeline.py

Medallion Architecture — Vava Doces.

This module keeps the RAW → SILVER → GOLD flow while only removing exact
same-file duplicates. Cross-file duplicate-like rows remain available for audit.
"""

# IDs and names are intentionally separated in Gold outputs to avoid duplicated/misaligned columns.

from __future__ import annotations

import argparse
import logging
import os
import sys
import unicodedata
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Optional

import numpy as np
import pandas as pd

# ── Project root on sys.path so src.* imports work ────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.infrastructure.data_quality import DataQualityValidator  # noqa: E402
from src.infrastructure.drive_manager import (  # noqa: E402
    DriveManager,
    load_parquet_from_drive,
    update_parquet_in_drive,
    get_drive_assets_map,
)
from src.infrastructure.google_drive_adapter import GoogleDriveAdapter  # noqa: E402
from src.domain.sales_analysis_service import (  # noqa: E402
    _deduplicate_with_audit,
    _normalise_header,
    _normalise_value,
    _parse_sales_dates_with_source,
    _to_numeric,
)
from src.infrastructure.gold_adapter import GoldParquetAdapter  # noqa: E402
from src.ports.data_source import DriveDataSource  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("medallion")

_DEFAULT_SOURCE_PRODUCTS_SHEET_ID = "1KEzf8FcL21DMk_64t-B9gMQIxjEx3ZPS_XsY-jYNVNk"
_MANIFEST_SOURCE_SALES = "sales_csv"
_MANIFEST_SOURCE_COSTS = "production_costs_sheets"

_DECIMAL_INTERMEDIATE_SCALE = Decimal("0.000001")



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


def _drive_folder_id_from_env() -> str:
    return (os.getenv("DRIVE_FOLDER_ID") or os.getenv("GOOGLE_DRIVE_FOLDER_ID") or "").strip()


def _source_products_sheet_id() -> str:
    return (
        os.getenv("PRODUCTION_COSTS_SHEET_ID")
        or os.getenv("GOOGLE_SHEET_ID")
        or os.getenv("SALES_SHEET_ID")
        or _DEFAULT_SOURCE_PRODUCTS_SHEET_ID
    ).strip()

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

# Manual cost/recipe sheet mappings (Google Sheets tabs)
MANUAL_SHEET_COLUMN_MAPS: dict[str, dict[str, str]] = {
    "materia_prima": {
        "ingrediente_id": "ingrediente_id",
        "id do ingrediente": "ingrediente_id",
        "id ingrediente": "ingrediente_id",
        "id_do_ingrediente": "ingrediente_id",
        "item": "item",
        "nome": "nome_ingrediente",
        "nome ingrediente": "nome_ingrediente",
        "nome_do_ingrediente": "nome_ingrediente",
        "unidade": "unidade",
        "tipo_de_medida_ex_k_g_l": "unidade",
        "custo_unitario": "custo_unit",
        "custo unitario": "custo_unit",
        "custo": "custo_unit",
        "custo_fracionado_g_ml": "custo_unit",
        "preco_por_unidade_caixa_item": "custo_unit",
        "rendimento embalagem": "rendimento_embalagem",
        "rendimento_embalagem": "rendimento_embalagem",
        "conteudo_por_caixa_peso_vol": "rendimento_embalagem",
    },
    "receitas": {
        "produto_id": "produto_id",
        "id_do_produto": "produto_id",
        "id do produto": "produto_id",
        "produto": "nome_produto",
        "nome produto": "nome_produto",
        "nome_do_produto": "nome_produto",
        "ingrediente_id": "ingrediente_id",
        "id_do_ingrediente": "ingrediente_id",
        "id do ingrediente": "ingrediente_id",
        "ingrediente": "nome_ingrediente",
        "nome ingrediente": "nome_ingrediente",
        "nome_do_ingrediente": "nome_ingrediente",
        "qtd": "qtd",
        "quantidade": "qtd",
        "quantidade_por_produto": "qtd",
        "unidade_de_medida": "unidade",
        "custo_do_ingrediente": "custo_do_ingrediente",
        "custo do ingrediente": "custo_do_ingrediente",
        "custo_do_ingrediente_r": "custo_do_ingrediente",
        "custo do ingrediente r": "custo_do_ingrediente",
    },
    "produtos": {
        "": "produto_id",
        "produto_id": "produto_id",
        "id do produto": "produto_id",
        "id produto": "produto_id",
        "id_do_produto": "produto_id",
        "unnamed_0": "produto_id",
        "nome": "nome",
        "nome do produto": "nome",
        "nome_do_produto": "nome",
        "rendimento": "rendimento",
        "preco de venda": "preco_venda",
        "preço de venda": "preco_venda",
        "valor de venda": "preco_venda",
        "preco": "preco_venda",
        "preço": "preco_venda",
        "preco_de_venda_r": "preco_venda",
    },
}


class LocalRawSource(DriveDataSource):
    """Filesystem-backed source compatible with the pipeline Drive contract."""

    def __init__(self, raw_dir: Path | str):
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
            files.append(
                {
                    "id": str(path),
                    "name": path.name,
                    "mimeType": mime,
                    "modifiedTime": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
                }
            )
        return files

    def read_as_dataframe(self, file_meta: dict) -> Optional[pd.DataFrame]:
        path = Path(str(file_meta.get("id") or self.raw_dir / str(file_meta.get("name", ""))))
        if not path.exists():
            return None
        try:
            if path.suffix.lower() == ".csv":
                # Manual exports from Google Sheets have stable comma CSV layout.
                if path.name.lower().startswith("manual_"):
                    return pd.read_csv(path, encoding="utf-8-sig")
                return pd.read_csv(path, sep=None, engine="python")
            return pd.read_excel(path)
        except Exception:
            try:
                if path.suffix.lower() == ".csv":
                    return pd.read_csv(path, sep=";", encoding="latin-1")
            except Exception:
                return None
            return None


def _normalize_sheet_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    text = text.strip().lower().replace("-", "_").replace(" ", "_")
    return text


def _is_manual_sheet_name(normalized_name: str) -> bool:
    return (
        normalized_name.startswith("manual_materia_prima")
        or normalized_name.startswith("manual_receitas")
        or normalized_name.startswith("manual_produtos")
        or ("materia" in normalized_name and "prima" in normalized_name)
        or ("produtos" in normalized_name or normalized_name == "produto")
        or ("receitas" in normalized_name or normalized_name == "receita")
    )


def _stable_dataframe_checksum(df: pd.DataFrame | None) -> str:
    if df is None or df.empty:
        return sha256(b"empty_dataframe").hexdigest()
    stable = df.copy().sort_index(axis=1)
    row_hash = pd.util.hash_pandas_object(stable, index=True)
    return sha256(row_hash.to_numpy().tobytes()).hexdigest()


def _stable_manual_sheets_checksum(manual_sheets: dict[str, pd.DataFrame]) -> str:
    digest = sha256()
    for sheet_name in ("produtos", "receitas", "materia_prima"):
        digest.update(sheet_name.encode("utf-8"))
        digest.update(_stable_dataframe_checksum(manual_sheets.get(sheet_name)).encode("utf-8"))
    return digest.hexdigest()


def _count_unique_catalog_products(produtos_df: pd.DataFrame | None) -> int:
    if produtos_df is None or produtos_df.empty or "produto_id" not in produtos_df.columns:
        return 0
    keys = produtos_df["produto_id"].astype("string").str.strip().str.upper()
    keys = keys.replace({"": pd.NA, "NAN": pd.NA, "NONE": pd.NA, "NAT": pd.NA}).dropna()
    return int(keys.nunique())


def clean_cost_sheet(df: pd.DataFrame, column_map: dict[str, str]) -> pd.DataFrame:
    """
    Função para normalizar dados financeiros e strings de abas manuais.
    """
    out = df.copy()

    # 1. Renomeia colunas para o padrão canônico do projeto
    norm_map = {_normalise_header(k): v for k, v in column_map.items()}
    out.columns = [_normalise_header(c) for c in out.columns]
    out = out.rename(columns=norm_map)

    # Collapse duplicate canonical columns (e.g., multiple headers mapped to same target).
    if out.columns.duplicated().any():
        collapsed = pd.DataFrame(index=out.index)
        for col in pd.Index(out.columns).unique():
            same_col = out.loc[:, out.columns == col]
            if isinstance(same_col, pd.Series) or same_col.shape[1] == 1:
                collapsed[col] = same_col if isinstance(same_col, pd.Series) else same_col.iloc[:, 0]
            else:
                collapsed[col] = same_col.bfill(axis=1).iloc[:, 0]
        out = collapsed

    # 2. Normalização de IDs e Strings (evita falha no merge por espaços extras)
    string_cols = out.select_dtypes(include=["object"]).columns
    for col in string_cols:
        out[col] = out[col].astype(str).str.strip()

    # 3. Conversão Financeira (Trata R$, pontos e vírgulas)
    finance_keywords = ["custo", "preco", "valor", "margem", "rendimento"]
    for col in out.columns:
        if any(key in col.lower() for key in finance_keywords):
            text = out[col].astype(str).str.strip()
            text = text.str.replace("R$", "", regex=False).str.replace("%", "", regex=False)
            text = text.str.replace(" ", "", regex=False)
            has_comma = text.str.contains(",", na=False)
            has_dot = text.str.contains(r"\.", na=False)
            mixed_mask = has_comma & has_dot
            text.loc[mixed_mask] = text.loc[mixed_mask].str.replace(".", "", regex=False)
            # Values like "1.045" in sheets are often thousand-separated (1045),
            # not decimal numbers. Keep decimal values (e.g., 11.16) untouched.
            thousand_mask = (~has_comma) & has_dot & text.str.match(r"^-?\d{1,3}(\.\d{3})+$", na=False)
            text.loc[thousand_mask] = text.loc[thousand_mask].str.replace(".", "", regex=False)
            text = text.str.replace(",", ".", regex=False)
            # Preserve NaN on parsing failures to avoid silently zeroing sheet values.
            out[col] = pd.to_numeric(text, errors="coerce")

    return out


def _prune_manual_sheet(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if out.empty or len(out.columns) < 2:
        return out
    first = out.columns[0]
    second = out.columns[1]
    out[first] = out[first].astype("string").str.strip().replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    out[second] = out[second].astype("string").str.strip().replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    out = out.dropna(subset=[out.columns[0], out.columns[1]], how="all")
    valid_mask = out[out.columns[0]].notna().to_numpy()
    if valid_mask.any():
        last_pos = int(np.flatnonzero(valid_mask)[-1])
        out = out.iloc[: last_pos + 1]
    return out.reset_index(drop=True)


def _first_non_empty(series: pd.Series):
    cleaned = (
        pd.Series(series, index=series.index)
        .astype("string")
        .str.strip()
        .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "NAN": pd.NA, "NONE": pd.NA, "NAT": pd.NA})
        .dropna()
    )
    if cleaned.empty:
        return pd.NA
    return cleaned.iloc[0]


def _first_numeric(series: pd.Series) -> float:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return float("nan")
    return float(numeric.iloc[0])


def _parse_brl_numeric(series: pd.Series) -> pd.Series:
    """Parse numeric values accepting BRL text like 'R$ 1.234,56'."""
    text = pd.Series(series, index=series.index).astype("string").str.strip()
    text = text.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "NAN": pd.NA, "NONE": pd.NA, "NAT": pd.NA})
    text = text.str.replace("R$", "", regex=False).str.replace("%", "", regex=False)
    # Keep numeric payload even when sources include unit suffixes (e.g., "1335K").
    text = text.str.replace(r"[^0-9,.-]", "", regex=True)
    text = text.str.replace(" ", "", regex=False)
    has_comma = text.str.contains(",", na=False)
    has_dot = text.str.contains(r"\.", na=False)
    mixed_mask = has_comma & has_dot
    text.loc[mixed_mask] = text.loc[mixed_mask].str.replace(".", "", regex=False)
    thousand_mask = (~has_comma) & has_dot & text.str.match(r"^-?\d{1,3}(\.\d{3})+$", na=False)
    text.loc[thousand_mask] = text.loc[thousand_mask].str.replace(".", "", regex=False)
    text = text.str.replace(",", ".", regex=False)
    return pd.to_numeric(text, errors="coerce")


def _to_decimal(value: object) -> Decimal | None:
    if pd.isna(value):
        return None
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001
        return None


def _series_to_decimal(series: pd.Series) -> pd.Series:
    return pd.Series(series, index=series.index).map(_to_decimal)


def _decimal_mul(a: Decimal | None, b: Decimal | None) -> Decimal | None:
    if a is None or b is None:
        return None
    return a * b


def _decimal_div(a: Decimal | None, b: Decimal | None) -> Decimal | None:
    if a is None or b is None or b == 0:
        return None
    return a / b


def _normalize_unit_token(series: pd.Series) -> pd.Series:
    """Normalize free-text unit values to canonical tokens used in cost conversion."""
    out = pd.Series(series, index=series.index).astype("string").str.strip().str.upper()
    out = out.replace({"": pd.NA, "NAN": pd.NA, "NONE": pd.NA, "NAT": pd.NA})
    # Extract alphabetic token when value comes mixed with quantity, e.g. "1335K".
    out = out.str.extract(r"([A-Z]+)", expand=False)
    unit_map = {
        "K": "KG",
        "KG": "KG",
        "QUILO": "KG",
        "QUILOS": "KG",
        "G": "G",
        "GR": "G",
        "GRAMA": "G",
        "GRAMAS": "G",
        "L": "L",
        "LT": "L",
        "LITRO": "L",
        "LITROS": "L",
        "ML": "ML",
        "MILILITRO": "ML",
        "MILILITROS": "ML",
        "UN": "UN",
        "UND": "UN",
        "UNIDADE": "UN",
    }
    out = out.map(lambda v: unit_map.get(str(v), str(v)) if pd.notna(v) else pd.NA)
    return pd.Series(out, index=series.index, dtype="string")


def normalize_manual_sheets_with_audit(
    manual_sheets: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], dict[str, dict[str, object]]]:
    normalized: dict[str, pd.DataFrame] = {}
    audit: dict[str, dict[str, object]] = {}

    raw_products = _prune_manual_sheet(manual_sheets.get("produtos", pd.DataFrame()).copy())
    products_rows_in = int(len(raw_products))
    if not raw_products.empty:
        if "produto_id" not in raw_products.columns:
            raw_products["produto_id"] = ""
        if "nome" not in raw_products.columns:
            raw_products["nome"] = raw_products["produto_id"]
        if "rendimento" not in raw_products.columns:
            raw_products["rendimento"] = np.nan
        if "preco_venda" not in raw_products.columns:
            raw_products["preco_venda"] = np.nan

        products = raw_products.copy()
        products["produto_id"] = products["produto_id"].astype("string").str.strip().str.upper()
        products["nome"] = products["nome"].astype("string").str.strip()
        products["rendimento"] = pd.to_numeric(products["rendimento"], errors="coerce")
        products["preco_venda"] = pd.to_numeric(products["preco_venda"], errors="coerce")
        products = products.dropna(subset=["produto_id"]).copy()
        prod_key = products["produto_id"].astype(str).str.strip().str.lower()
        products = products[~prod_key.isin({"", "nan", "none", "nat"})].copy()
        products = products.drop_duplicates(subset=["produto_id"], keep="first").reset_index(drop=True)
        for col in ("produto_id", "nome"):
            products[col] = products[col].astype("string")
    else:
        products = pd.DataFrame(columns=["produto_id", "nome", "rendimento", "preco_venda"])
    normalized["produtos"] = products
    audit["produtos"] = {
        "rows_in": products_rows_in,
        "rows_out": int(len(products)),
        "rows_removed": max(products_rows_in - int(len(products)), 0),
        "dedup_key": ["produto_id"],
    }

    raw_materia = _prune_manual_sheet(manual_sheets.get("materia_prima", pd.DataFrame()).copy())
    materia_rows_in = int(len(raw_materia))
    if not raw_materia.empty:
        if "ingrediente_id" not in raw_materia.columns:
            raw_materia["ingrediente_id"] = raw_materia.get("item", "")
        if "item" not in raw_materia.columns:
            raw_materia["item"] = raw_materia.get("ingrediente_id", "")
        if "nome_ingrediente" not in raw_materia.columns:
            raw_materia["nome_ingrediente"] = raw_materia.get("item", raw_materia.get("ingrediente_id", ""))
        if "unidade" not in raw_materia.columns:
            raw_materia["unidade"] = ""
        if "custo_unit" not in raw_materia.columns:
            raw_materia["custo_unit"] = np.nan
        if "rendimento_embalagem" not in raw_materia.columns:
            raw_materia["rendimento_embalagem"] = np.nan

        materia = raw_materia.copy()
        materia["ingrediente_id"] = materia["ingrediente_id"].astype("string").str.strip().str.upper()
        materia["item"] = materia["ingrediente_id"]
        materia["nome_ingrediente"] = materia["nome_ingrediente"].astype("string").str.strip()
        materia["unidade"] = _normalize_unit_token(materia["unidade"])
        materia["custo_unit"] = pd.to_numeric(materia["custo_unit"], errors="coerce")
        materia["rendimento_embalagem"] = pd.to_numeric(materia["rendimento_embalagem"], errors="coerce")
        materia = materia.dropna(subset=["ingrediente_id"]).copy()
        ing_key = materia["ingrediente_id"].astype(str).str.strip().str.lower()
        materia = materia[~ing_key.isin({"", "nan", "none", "nat"})].copy()
        materia = (
            materia.groupby("ingrediente_id", as_index=False, dropna=False)
            .agg(
                item=("item", _first_non_empty),
                nome_ingrediente=("nome_ingrediente", _first_non_empty),
                unidade=("unidade", _first_non_empty),
                custo_unit=("custo_unit", _first_numeric),
                rendimento_embalagem=("rendimento_embalagem", _first_numeric),
            )
            .reset_index(drop=True)
        )
        for col in ("ingrediente_id", "item", "nome_ingrediente", "unidade"):
            materia[col] = materia[col].astype("string")
    else:
        materia = pd.DataFrame(columns=["ingrediente_id", "item", "nome_ingrediente", "unidade", "custo_unit", "rendimento_embalagem"])
    normalized["materia_prima"] = materia
    audit["materia_prima"] = {
        "rows_in": materia_rows_in,
        "rows_out": int(len(materia)),
        "rows_removed": max(materia_rows_in - int(len(materia)), 0),
        "dedup_key": ["ingrediente_id"],
    }

    raw_receitas = _prune_manual_sheet(manual_sheets.get("receitas", pd.DataFrame()).copy())
    receitas_rows_in = int(len(raw_receitas))
    if not raw_receitas.empty:
        def _is_missing_key(series: pd.Series) -> pd.Series:
            keys = series.astype("string").str.strip().str.upper()
            return keys.isna() | keys.isin({"", "NAN", "NONE", "NAT"})

        def _name_to_surrogate(series: pd.Series, prefix: str) -> pd.Series:
            token = series.astype("string").fillna("").astype(str).map(_normalise_header)
            token = token.replace({"": pd.NA, "nan": pd.NA, "none": pd.NA, "nat": pd.NA})
            return pd.Series(np.where(token.notna(), f"{prefix}" + token.astype(str).str.upper(), pd.NA), index=series.index, dtype="string")

        if "produto_id" not in raw_receitas.columns:
            raw_receitas["produto_id"] = ""
        if "nome_produto" not in raw_receitas.columns:
            raw_receitas["nome_produto"] = raw_receitas.get("produto", "")
        if "ingrediente_id" not in raw_receitas.columns:
            raw_receitas["ingrediente_id"] = ""
        if "nome_ingrediente" not in raw_receitas.columns:
            raw_receitas["nome_ingrediente"] = ""
        if "qtd" not in raw_receitas.columns:
            raw_receitas["qtd"] = np.nan
        if "unidade" not in raw_receitas.columns:
            raw_receitas["unidade"] = ""
        if "custo_do_ingrediente" not in raw_receitas.columns:
            if "custo_unitario_final" in raw_receitas.columns:
                raw_receitas["custo_do_ingrediente"] = raw_receitas["custo_unitario_final"]
            elif "custo_unitario" in raw_receitas.columns:
                raw_receitas["custo_do_ingrediente"] = raw_receitas["custo_unitario"]
            else:
                raw_receitas["custo_do_ingrediente"] = np.nan

        receitas = raw_receitas.copy()
        receitas["produto_id"] = receitas["produto_id"].astype("string").str.strip().str.upper()
        receitas["nome_produto"] = receitas["nome_produto"].astype("string").str.strip()
        receitas["ingrediente_id"] = receitas["ingrediente_id"].astype("string").str.strip().str.upper()
        receitas["nome_ingrediente"] = receitas["nome_ingrediente"].astype("string").str.strip()
        receitas["unidade"] = _normalize_unit_token(receitas["unidade"])
        receitas["qtd"] = _parse_brl_numeric(receitas["qtd"])
        receitas["custo_do_ingrediente"] = _parse_brl_numeric(receitas["custo_do_ingrediente"])

        if not products.empty:
            product_name_to_id = {
                str(name_key): str(pid)
                for name_key, pid in zip(products["nome"].astype(str).map(_normalise_value), products["produto_id"], strict=False)
                if str(name_key).strip() not in {"", "nan", "none"}
            }
            missing_id_mask = receitas["produto_id"].fillna("").astype(str).str.strip().str.upper().isin({"", "NAN", "NONE", "NAT"})
            if missing_id_mask.any():
                receitas.loc[missing_id_mask, "produto_id"] = receitas.loc[missing_id_mask, "nome_produto"].astype(str).map(_normalise_value).map(product_name_to_id)
                receitas["produto_id"] = receitas["produto_id"].astype("string").str.strip().str.upper()

        missing_prod_mask = _is_missing_key(receitas["produto_id"])
        if missing_prod_mask.any():
            receitas.loc[missing_prod_mask, "produto_id"] = _name_to_surrogate(
                receitas.loc[missing_prod_mask, "nome_produto"],
                "PROD-NOME-",
            )
            receitas["produto_id"] = receitas["produto_id"].astype("string").str.strip().str.upper()

        missing_ing_mask = _is_missing_key(receitas["ingrediente_id"])
        if missing_ing_mask.any():
            receitas.loc[missing_ing_mask, "ingrediente_id"] = _name_to_surrogate(
                receitas.loc[missing_ing_mask, "nome_ingrediente"],
                "ING-NOME-",
            )
            receitas["ingrediente_id"] = receitas["ingrediente_id"].astype("string").str.strip().str.upper()

        receitas = receitas.dropna(subset=["produto_id", "ingrediente_id"], how="any").copy()
        rec_prod_key = receitas["produto_id"].astype(str).str.strip().str.lower()
        receitas = receitas[~rec_prod_key.isin({"", "nan", "none", "nat"})].copy()
        rec_ing_key = receitas["ingrediente_id"].astype(str).str.strip().str.lower()
        receitas = receitas[~rec_ing_key.isin({"", "nan", "none", "nat"})].copy()

        for col in ("produto_id", "nome_produto", "ingrediente_id", "nome_ingrediente", "unidade"):
            receitas[col] = receitas[col].astype("string")
    else:
        receitas = pd.DataFrame(columns=["produto_id", "nome_produto", "ingrediente_id", "nome_ingrediente", "qtd", "unidade", "custo_do_ingrediente"])
    normalized["receitas"] = receitas
    audit["receitas"] = {
        "rows_in": receitas_rows_in,
        "rows_out": int(len(receitas)),
        "rows_removed": max(receitas_rows_in - int(len(receitas)), 0),
        "dedup_key": [],
    }

    return normalized, audit


def read_raw_sources(
    source: DriveDataSource,
    files: list[dict] | None = None,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], dict[str, object]]:
    files = files if files is not None else source.list_tabular_files()
    sales_frames: list[pd.DataFrame] = []
    manual_raw: dict[str, pd.DataFrame] = {}

    for meta in files:
        df = source.read_as_dataframe(meta)
        if df is None or df.empty:
            continue
        source_name = str(meta.get("name", ""))
        normalized_name = _normalize_sheet_name(source_name)

        if normalized_name.startswith("manual_materia_prima") or ("materia" in normalized_name and "prima" in normalized_name):
            manual_raw["materia_prima"] = clean_cost_sheet(df, MANUAL_SHEET_COLUMN_MAPS["materia_prima"])
            continue
        if normalized_name.startswith("manual_receitas") or ("receitas" in normalized_name or normalized_name == "receita"):
            manual_raw["receitas"] = clean_cost_sheet(df, MANUAL_SHEET_COLUMN_MAPS["receitas"])
            continue
        if normalized_name.startswith("manual_produtos") or ("produtos" in normalized_name or normalized_name == "produto"):
            manual_raw["produtos"] = clean_cost_sheet(df, MANUAL_SHEET_COLUMN_MAPS["produtos"])
            continue

        frame = df.copy()
        if "_source_file" not in frame.columns:
            frame["_source_file"] = meta.get("name", "")
        sales_frames.append(frame)

    bronze_df = pd.concat(sales_frames, ignore_index=True) if sales_frames else pd.DataFrame()
    manual_sheets, manual_audit = normalize_manual_sheets_with_audit(manual_raw)
    load_audit: dict[str, object] = {
        "sales_rows_in": int(len(bronze_df)),
        "sales_files_detected": int(len(sales_frames)),
        "manual_sheets": manual_audit,
    }
    return bronze_df, manual_sheets, load_audit


def _build_manual_cost_map(manual_sheets: dict[str, pd.DataFrame]) -> dict[str, float]:
    """Build product cost map prioritizing explicit recipe-line costs as truth source."""
    receitas = manual_sheets.get("receitas")
    materia = manual_sheets.get("materia_prima")
    if receitas is None or receitas.empty:
        return {}

    if "produto_id" not in receitas.columns:
        return {}

    rec = receitas.copy()
    rec["produto_id"] = rec["produto_id"].astype("string").str.strip().str.upper()
    valid_pid = ~rec["produto_id"].fillna("").astype(str).str.strip().str.lower().isin({"", "nan", "none", "nat"})
    rec = rec[valid_pid].copy()

    # Source of truth: explicit recipe line-cost values from the sheet.
    if "custo_do_ingrediente" in rec.columns:
        rec["custo_item"] = _parse_brl_numeric(rec["custo_do_ingrediente"])
        if rec["custo_item"].notna().any():
            agg = rec.groupby("produto_id", as_index=False).agg(
                custo_item=("custo_item", lambda s: s.sum(min_count=1))
            )
            return {
                _normalise_value(prod): float(_to_decimal(cost) or Decimal("0"))
                for prod, cost in agg[["produto_id", "custo_item"]].itertuples(index=False, name=None)
                if str(prod).strip() != "" and pd.notna(cost)
            }

    if materia is None or materia.empty:
        return {}
    if not {"ingrediente_id", "qtd"}.issubset(rec.columns):
        return {}
    if not {"item", "custo_unit"}.issubset(materia.columns):
        return {}

    mp = materia.copy()
    if "item" not in mp.columns and "ingrediente_id" in mp.columns:
        mp["item"] = mp["ingrediente_id"]
    rec["ingrediente_id_norm"] = rec["ingrediente_id"].astype(str).str.strip().str.lower()
    mp["item_norm"] = mp["item"].astype(str).str.strip().str.lower()

    merged = rec.merge(mp[["item_norm", "custo_unit"]], left_on="ingrediente_id_norm", right_on="item_norm", how="left")
    merged["qtd"] = pd.to_numeric(merged["qtd"], errors="coerce")
    merged["custo_unit"] = pd.to_numeric(merged["custo_unit"], errors="coerce")
    merged["custo_item_dec"] = _series_to_decimal(merged["qtd"]).combine(
        _series_to_decimal(merged["custo_unit"]),
        _decimal_mul,
    )
    agg = merged.groupby("produto_id", as_index=False).agg(
        custo_item_dec=(
            "custo_item_dec",
            lambda s: sum((v for v in s if v is not None), start=Decimal("0")).quantize(
                _DECIMAL_INTERMEDIATE_SCALE,
                rounding=ROUND_HALF_UP,
            ) if any(v is not None for v in s) else None,
        )
    )
    return {
        _normalise_value(prod): float(cost)
        for prod, cost in agg[["produto_id", "custo_item_dec"]].itertuples(index=False, name=None)
        if str(prod).strip() != "" and cost is not None
    }


def build_gold_custos_produtos(
    manual_sheets: dict[str, pd.DataFrame],
    cost_map: dict[str, float],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build Gold table for cost cockpit.

    Output columns:
      produto_id, nome, rendimento, preco_venda, custo_total, margem_contribuicao_real
    """
    del cost_map
    cols = [
        "id_produto",
        "nome_produto",
        "id_ingrediente",
        "nome_ingrediente",
        "quantidade_formatada",
        "custo_unitario_final",
        "custo_origem_ausente",
    ]
    agg_cols = ["id_produto", "nome_produto", "qtd_ingredientes", "custo_producao"]

    normalized_manual_sheets, manual_audit = normalize_manual_sheets_with_audit(manual_sheets)
    receitas = normalized_manual_sheets.get("receitas", pd.DataFrame()).copy()
    materia = normalized_manual_sheets.get("materia_prima", pd.DataFrame()).copy()
    produtos = normalized_manual_sheets.get("produtos", pd.DataFrame()).copy()
    logger.info(
        "Silver manual sheets audit: produtos=%d→%d receitas=%d→%d materia_prima=%d→%d",
        int(manual_audit.get("produtos", {}).get("rows_in", 0)),
        int(manual_audit.get("produtos", {}).get("rows_out", 0)),
        int(manual_audit.get("receitas", {}).get("rows_in", 0)),
        int(manual_audit.get("receitas", {}).get("rows_out", 0)),
        int(manual_audit.get("materia_prima", {}).get("rows_in", 0)),
        int(manual_audit.get("materia_prima", {}).get("rows_out", 0)),
    )

    if "produto_id" not in receitas.columns:
        receitas["produto_id"] = ""
    if "nome_produto" not in receitas.columns:
        if "produto" in receitas.columns:
            receitas["nome_produto"] = receitas["produto"]
        else:
            receitas["nome_produto"] = ""
    if "ingrediente_id" not in receitas.columns:
        receitas["ingrediente_id"] = ""
    if "qtd" not in receitas.columns:
        receitas["qtd"] = 0.0
    if "unidade" not in receitas.columns:
        receitas["unidade"] = ""

    if "produto_id" not in produtos.columns:
        produtos["produto_id"] = ""
    if "nome" not in produtos.columns:
        produtos["nome"] = produtos["produto_id"]
    if "rendimento" not in produtos.columns:
        produtos["rendimento"] = 1.0

    if "ingrediente_id" not in materia.columns:
        materia["ingrediente_id"] = materia.get("item", "")
    if "nome_ingrediente" not in materia.columns:
        materia["nome_ingrediente"] = materia.get("item", materia.get("ingrediente_id", ""))
    if "unidade" not in materia.columns:
        materia["unidade"] = ""
    if "custo_unit" not in materia.columns:
        materia["custo_unit"] = 0.0
    if "rendimento_embalagem" not in materia.columns:
        materia["rendimento_embalagem"] = 0.0

    rec = receitas.copy()
    rec["id_produto"] = rec["produto_id"].astype("string").str.strip().str.upper()
    rec["id_ingrediente"] = rec["ingrediente_id"].astype("string").str.strip().str.upper()

    prod = produtos.copy()
    prod["id_produto"] = prod["produto_id"].astype("string").str.strip().str.upper()
    prod["nome"] = prod["nome"].fillna("").astype(str).str.strip()
    prod["rendimento"] = pd.to_numeric(prod["rendimento"], errors="coerce")
    prod = prod.dropna(subset=["id_produto"]).copy()
    prod_key = prod["id_produto"].astype(str).str.strip().str.lower()
    prod = prod[~prod_key.isin({"", "nan", "none", "nat"})].copy()
    prod = prod.drop_duplicates(subset=["id_produto"], keep="first")

    # Costs/recipes domain isolation: resolve missing product IDs using product-name mapping
    # only within manual_sheets tabs; sales dedup/hash logic is not used here.
    rec_name_key = rec.get("nome_produto", pd.Series(index=rec.index, dtype="object")).astype(str).map(_normalise_value)
    prod_name_key = prod.get("nome", pd.Series(index=prod.index, dtype="object")).astype(str).map(_normalise_value)
    name_to_id = {
        str(name_key): str(pid)
        for name_key, pid in zip(prod_name_key, prod["id_produto"], strict=False)
        if str(name_key).strip() not in {"", "nan", "none"}
    }
    missing_id_mask = rec["id_produto"].astype("string").fillna("").str.strip().str.upper().isin({"", "NAN", "NONE", "NAT"})
    if missing_id_mask.any():
        rec.loc[missing_id_mask, "id_produto"] = rec_name_key.loc[missing_id_mask].map(name_to_id).fillna("")
        rec["id_produto"] = rec["id_produto"].astype("string").str.strip().str.upper()

    rec = rec.dropna(subset=["id_produto", "id_ingrediente"]).copy()
    rec_prod_key = rec["id_produto"].astype(str).str.strip().str.lower()
    rec = rec[~rec_prod_key.isin({"", "nan", "none", "nat"})].copy()
    rec_ing_key = rec["id_ingrediente"].astype(str).str.strip().str.lower()
    rec = rec[~rec_ing_key.isin({"", "nan", "none", "nat"})].copy()
    rec["qtd_receita"] = _parse_brl_numeric(rec["qtd"]).fillna(0.0)
    rec["custo_receita_linha"] = _parse_brl_numeric(rec.get("custo_do_ingrediente", pd.Series(index=rec.index, dtype="float64")))
    rec["custo_origem_ausente"] = rec["custo_receita_linha"].isna()
    rec["unidade"] = _normalize_unit_token(rec["unidade"]).fillna("")
    rec["ingrediente_key"] = rec["id_ingrediente"].astype(str).str.strip().str.lower()

    mp = materia.copy()
    mp["id_ingrediente"] = mp["ingrediente_id"].astype("string").str.strip().str.upper()
    mp = mp.dropna(subset=["id_ingrediente"]).copy()
    mp_key = mp["id_ingrediente"].astype(str).str.strip().str.lower()
    mp = mp[~mp_key.isin({"", "nan", "none", "nat"})].copy()
    mp["ingrediente_key"] = mp["id_ingrediente"].astype(str).str.strip().str.lower()
    mp["nome_ingrediente"] = mp["nome_ingrediente"].fillna("").astype(str).str.strip()
    mp["unidade"] = _normalize_unit_token(mp["unidade"]).fillna("")
    mp["custo_un_mat_prima"] = _parse_brl_numeric(mp["custo_unit"])
    mp["rendimento_embalagem"] = _parse_brl_numeric(mp["rendimento_embalagem"]).fillna(0.0)
    mp = mp.drop_duplicates(subset=["id_ingrediente"], keep="first")

    detail = rec.merge(
        prod[["id_produto", "nome", "rendimento"]],
        on="id_produto",
        how="left",
    )
    detail = detail.merge(
        mp[["ingrediente_key", "id_ingrediente", "nome_ingrediente", "unidade", "custo_un_mat_prima", "rendimento_embalagem"]],
        on="ingrediente_key",
        how="left",
        suffixes=("", "_mp"),
    )

    detail["id_produto"] = detail["id_produto"].fillna("").astype(str).str.strip().str.upper()
    detail["nome_produto"] = detail["nome"].astype("string").str.strip()
    detail["nome_produto"] = detail["nome_produto"].replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    detail["nome_produto"] = detail["nome_produto"].fillna(detail["id_produto"]).astype(str).str.strip()
    detail["id_ingrediente"] = detail["id_ingrediente_mp"].fillna(detail["id_ingrediente"]).fillna("").astype(str).str.strip().str.upper()
    detail["nome_ingrediente"] = detail.get("nome_ingrediente_mp", detail["nome_ingrediente"]).fillna(detail["nome_ingrediente"]).astype("string").str.strip()
    detail["nome_ingrediente"] = detail["nome_ingrediente"].replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    detail["nome_ingrediente"] = detail["nome_ingrediente"].fillna(detail["id_ingrediente"]).astype(str).str.strip()
    if "unidade_mp" not in detail.columns:
        detail["unidade_mp"] = detail["unidade"]

    qty_num = pd.to_numeric(detail["qtd_receita"], errors="coerce")
    qty_txt = pd.Series(np.where(qty_num.notna(), qty_num.map(lambda x: f"{x:g}"), ""), index=detail.index).astype(str)
    unit_txt = _normalize_unit_token(detail["unidade"]).fillna("").astype(str).str.lower()
    unit_txt = unit_txt.mask(unit_txt.eq(""), _normalize_unit_token(detail["unidade_mp"]).fillna("").astype(str).str.lower())
    detail["quantidade_formatada"] = (qty_txt + " " + unit_txt).str.strip()

    # Ingredient cost formula with Decimal precision:
    # (custo_unitario_materia_prima / rendimento_embalagem) * qtd_receita_ajustada
    denom = pd.to_numeric(detail["rendimento_embalagem"], errors="coerce")
    denom = denom.where(denom > 0, 1.0)
    numer = pd.to_numeric(detail["custo_un_mat_prima"], errors="coerce")
    qtd = pd.to_numeric(detail["qtd_receita"], errors="coerce")

    recipe_unit = _normalize_unit_token(detail["unidade"]).fillna("").astype(str)
    material_unit = _normalize_unit_token(detail["unidade_mp"]).fillna("").astype(str)
    recipe_small_unit = recipe_unit.isin({"G", "ML"})
    material_large_unit = material_unit.isin({"KG", "L"})
    qtd_ajustada = pd.Series(
        np.where(recipe_small_unit & material_large_unit, qtd / 1000.0, qtd),
        index=detail.index,
    )

    custo_base_dec = _series_to_decimal(numer).combine(_series_to_decimal(denom), _decimal_div)
    detail["custo_calculado_dec"] = custo_base_dec.combine(_series_to_decimal(qtd_ajustada), _decimal_mul)
    detail["custo_calculado_dec"] = detail["custo_calculado_dec"].map(
        lambda d: d.quantize(_DECIMAL_INTERMEDIATE_SCALE, rounding=ROUND_HALF_UP) if d is not None else None
    )
    detail["custo_calculado"] = pd.to_numeric(detail["custo_calculado_dec"], errors="coerce")
    # Source-of-truth precedence: keep recipe sheet cost whenever it is present.
    detail["custo_unitario_final"] = pd.to_numeric(detail["custo_receita_linha"], errors="coerce")
    missing_recipe_cost = detail["custo_unitario_final"].isna()
    if missing_recipe_cost.any():
        detail.loc[missing_recipe_cost, "custo_unitario_final"] = pd.to_numeric(
            detail.loc[missing_recipe_cost, "custo_calculado"], errors="coerce"
        )
    detail["custo_unitario_final"] = detail["custo_unitario_final"].astype("float64")
    if "custo_origem_ausente" not in detail.columns:
        detail["custo_origem_ausente"] = True
    detail["custo_origem_ausente"] = detail["custo_origem_ausente"].fillna(True).astype(bool)

    df_detalhado = detail[cols].copy().reset_index(drop=True) if not detail.empty else pd.DataFrame(columns=cols)
    df_detalhado.index.name = None

    detail_agg = (
        df_detalhado.groupby(["id_produto", "nome_produto"], as_index=False)
        .agg(
            qtd_ingredientes=("id_ingrediente", "count"),
            custo_receita_total=("custo_unitario_final", lambda s: s.sum(min_count=1)),
        )
        .reset_index(drop=True)
        if not df_detalhado.empty
        else pd.DataFrame(columns=["id_produto", "nome_produto", "qtd_ingredientes", "custo_receita_total"])
    )

    catalog_products = prod[["id_produto", "nome", "rendimento"]].copy() if not prod.empty else pd.DataFrame(columns=["id_produto", "nome", "rendimento"])
    catalog_products = catalog_products.rename(columns={"nome": "nome_produto"})
    if not catalog_products.empty:
        catalog_products["nome_produto"] = catalog_products["nome_produto"].fillna(catalog_products["id_produto"]).astype(str).str.strip()
        catalog_products = catalog_products.drop_duplicates(subset=["id_produto"], keep="first")

    if not catalog_products.empty:
        # Costs table is catalog-driven: keep only engineered products from the product sheet.
        df_gold_produtos = catalog_products.merge(detail_agg, on=["id_produto", "nome_produto"], how="left")
    else:
        df_gold_produtos = detail_agg.copy()
    if "qtd_ingredientes" not in df_gold_produtos.columns:
        df_gold_produtos["qtd_ingredientes"] = 0
    if "rendimento" not in df_gold_produtos.columns:
        df_gold_produtos["rendimento"] = np.nan
    df_gold_produtos["qtd_ingredientes"] = pd.to_numeric(df_gold_produtos["qtd_ingredientes"], errors="coerce").fillna(0).astype("int64")
    df_gold_produtos = df_gold_produtos[df_gold_produtos["qtd_ingredientes"] >= 1].copy()
    df_gold_produtos["rendimento"] = pd.to_numeric(df_gold_produtos["rendimento"], errors="coerce")
    # Dashboard total is the direct sum of recipe line costs per product.
    df_gold_produtos["custo_producao"] = pd.to_numeric(df_gold_produtos["custo_receita_total"], errors="coerce").astype("float64")

    df_gold_produtos.index.name = None
    return df_gold_produtos[agg_cols], df_detalhado


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


def _month_label_from_reference(values: pd.Series, fallback_dates: pd.Series | None = None) -> pd.Series:
    """Convert month references like ``2026-01`` to ``Month 01``."""
    series = values.astype("string")
    month_num = series.str.extract(r"(?:^|[-_/])(0[1-9]|1[0-2])(?:$|[-_/])", expand=False)
    if fallback_dates is not None:
        month_num = month_num.fillna(pd.to_datetime(fallback_dates, errors="coerce").dt.strftime("%m"))
    return month_num.map(lambda mm: f"Month {mm}" if pd.notna(mm) and str(mm).strip() != "" else "Month Unknown")


def _prepare_bronze_for_integrity(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Normalize Bronze rows to the canonical sales schema for row-count checks."""
    bronze = _normalise_columns(raw_df)
    if bronze.columns.duplicated().any():
        bronze = bronze.loc[:, ~bronze.columns.duplicated(keep="first")].copy()
    bronze = _map_canonical(bronze)
    if bronze.columns.duplicated().any():
        bronze = bronze.loc[:, ~bronze.columns.duplicated(keep="first")].copy()
    bronze = _coerce_types(bronze)
    if bronze.columns.duplicated().any():
        bronze = bronze.loc[:, ~bronze.columns.duplicated(keep="first")].copy()
    if "_source_file" not in bronze.columns:
        if "source_file" in bronze.columns:
            bronze["_source_file"] = bronze["source_file"]
        else:
            bronze["_source_file"] = ""
    bronze["mes_referencia"] = _extract_month_reference(
        bronze["_source_file"],
        bronze.get("data", pd.Series(index=bronze.index, dtype="object")),
    )
    bronze["month_label"] = _month_label_from_reference(bronze["mes_referencia"], bronze.get("data", pd.Series(index=bronze.index, dtype="object")))
    return bronze


def validate_pipeline_integrity(df_bronze: pd.DataFrame, df_silver: pd.DataFrame) -> dict[str, str]:
    """Return month-by-month Bronze→Silver row preservation status.

    Expected shape:
      {"Month 01": "Fixed", "Month 02": "Error: Lost 3"}
    """
    bronze = _prepare_bronze_for_integrity(df_bronze)
    silver = df_silver.copy()
    if "mes_referencia" not in silver.columns:
        source = silver.get("source_file", silver.get("_source_file", pd.Series(index=silver.index, dtype="object")))
        silver["mes_referencia"] = _extract_month_reference(
            source,
            silver.get("data", pd.Series(index=silver.index, dtype="object")),
        )
    silver["month_label"] = _month_label_from_reference(
        silver["mes_referencia"],
        silver.get("data", pd.Series(index=silver.index, dtype="object")),
    )

    bronze_counts = bronze["month_label"].value_counts().to_dict()
    silver_counts = silver["month_label"].value_counts().to_dict()
    all_months = {f"Month {month:02d}" for month in range(1, 13)} | set(bronze_counts) | set(silver_counts)

    report: dict[str, str] = {}
    for month in sorted(all_months):
        bronze_rows = int(bronze_counts.get(month, 0))
        silver_rows = int(silver_counts.get(month, 0))
        diff = bronze_rows - silver_rows
        report[month] = "Fixed" if diff == 0 else f"Error: Lost {diff}"
    return report


def _enforce_zero_loss_months(integrity_report: dict[str, str], months: tuple[str, ...] = ("Month 01", "Month 02", "Month 03")) -> None:
    failing = {month: integrity_report.get(month, "Error: Lost unknown") for month in months if integrity_report.get(month) != "Fixed"}
    if failing:
        raise ValueError(f"Silver integrity validation failed for required months: {failing}")


def transform_to_silver(raw_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    """Normalize RAW sales into SILVER while preserving item-grain multi-product sales.

    Row Loss Tracking:
    - Logs any deduplication at item-grain (item with all identifying columns identical)
    - Reports lost rows by month for audit trail
    - Preserves all rows with same num_venda but different product (multi-item orders)
    """
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

    # Track row count before dedup for month-based reporting
    rows_before_dedup = len(out)
    out, dedup_audit = _deduplicate_with_audit(out)
    rows_after_dedup = len(out)
    rows_lost_total = rows_before_dedup - rows_after_dedup

    source_file = out["_source_file"].fillna("").astype(str)
    out["source_file"] = source_file
    out["arquivo_origem"] = source_file
    load_ts = datetime.now(timezone.utc).isoformat()
    out["ingested_at_utc"] = load_ts
    out["data_carga"] = load_ts
    out["mes_referencia"] = _extract_month_reference(source_file, out.get("data", pd.Series(index=out.index, dtype="object")))

    # Detailed month-by-month loss reporting
    if rows_lost_total > 0 and "mes_referencia" in out.columns:
        logger.warning("[DEDUP LOSS ANALYSIS BY MONTH]")
        # Get original data for comparison
        out_orig = _normalise_columns(raw_df)
        out_orig.columns = [_normalise_header(c) for c in out_orig.columns]
        available = {k: v for k, v in _RAW_TO_SILVER.items() if k in out_orig.columns}
        out_orig = out_orig[list(available.keys())].rename(columns=available).copy()
        out_orig = _coerce_types(out_orig)
        if "_source_file" not in out_orig.columns:
            out_orig["_source_file"] = ""
        out_orig["mes_referencia"] = _extract_month_reference(
            out_orig["_source_file"],
            out_orig.get("data", pd.Series(index=out_orig.index, dtype="object"))
        )

        for month in sorted(out_orig["mes_referencia"].unique()):
            if month is None or str(month).strip() == "":
                continue
            month_before = len(out_orig[out_orig["mes_referencia"] == month])
            month_after = len(out[out["mes_referencia"] == month])
            month_loss = month_before - month_after
            if month_loss > 0:
                logger.warning("  %s: %d → %d (lost %d rows)", month, month_before, month_after, month_loss)

    for col in SILVER_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA

    silver = out[SILVER_COLUMNS].copy().reset_index(drop=True)
    integrity_report = validate_pipeline_integrity(raw_df, silver)
    audit = {
        "rows_in": int(len(raw_df)),
        "rows_out": int(len(silver)),
        "rows_lost_during_dedup": rows_lost_total,
        "integrity_report": integrity_report,
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
    df["_orphan_produto"] = df["produto_id"].eq(_UNKNOWN_ID)
    df["_orphan_data"] = df["data_id"].eq(_UNKNOWN_ID)

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
        "_orphan_produto",
        "_orphan_data",
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
    """Validate the Star Schema Integrity.

    Key Validation:
    - Foreign key referential integrity (all produto_id and data_id exist in dimensions)
    - Primary key uniqueness (no null venda_id)
    - Total row count consistency between Silver (source) and Gold (fato_vendas)
    - No infinite margin values

    Note: The grain is ITEM (one row = one line item from an order),
    so multiple rows with same num_venda but different products are expected and correct.
    """
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
        # Critical validation: Total rows in SILVER must equal total rows in GOLD (fato_vendas)
        # Each Silver row should map to exactly one fato row (item-grain preservation)
        row_diff = int(len(fato) - int(silver_rows))
        results["silver_gold_rowcount_ok"] = row_diff == 0
        results["silver_gold_rowcount_diff"] = row_diff

        if row_diff != 0:
            logger.warning(
                "[STAR SCHEMA VALIDATION] Row count mismatch: Silver %d → Gold fato_vendas %d (diff: %d)",
                silver_rows,
                len(fato),
                row_diff,
            )

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


def run_data_quality_validation(
    raw_df: pd.DataFrame | None = None,
    silver_df: pd.DataFrame | None = None,
    gold_dict: dict | None = None,
) -> dict | bool:
    """Run quality validation in detailed or compatibility mode.

    - When ``raw_df``, ``silver_df`` and ``gold_dict`` are provided, returns the
      structured validation payload used by pipeline callers.
    - When called with no arguments, loads the Gold layer from disk and returns a
      single boolean for backwards-compatible smoke tests.
    """
    if raw_df is None and silver_df is None and gold_dict is None:
        try:
            adapter = GoldParquetAdapter()
            dim_produto = adapter.load_gold("dim_produto")
            dim_tempo = adapter.load_gold("dim_tempo")
            fato_vendas = adapter.load_gold("fato_vendas")
            results = DataQualityValidator(verbose=False).validate_all(dim_produto, dim_tempo, fato_vendas)
            return bool(all(results.values()))
        except Exception:
            return False

    gold_dict = gold_dict or {}
    return {
        "raw": validate_raw_input_quality(raw_df if raw_df is not None else pd.DataFrame()),
        "silver": validate_silver_quality(silver_df if silver_df is not None else pd.DataFrame()),
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


def build_gold_rentabilidade(
    faturamento_agregado: pd.DataFrame,
    custo_producao_agregado: pd.DataFrame,
) -> pd.DataFrame:
    """Build product-level profitability table for the executive dashboard.

    The Gold layer intentionally preserves NaN cost lineage via
    ``custo_producao_unitario_audit`` so the UI can invalidate margin/markup
    instead of silently showing misleading profitability.
    """
    if faturamento_agregado is None or faturamento_agregado.empty:
        return pd.DataFrame(
            columns=[
                "id_produto",
                "nome_produto",
                "faturamento_item",
                "preco_venda_unitario",
                "custo_producao_unitario",
                "custo_producao_unitario_audit",
                "margem_valor",
                "margem_perc",
                "markup",
            ]
        )

    fat = faturamento_agregado.copy()
    if "id_produto" not in fat.columns:
        fat["id_produto"] = fat["produto_id"] if "produto_id" in fat.columns else ""
    if "nome_produto" not in fat.columns:
        fat["nome_produto"] = fat["id_produto"]
    if "faturamento_liquido" not in fat.columns:
        fat["faturamento_liquido"] = 0.0
    if "qtd_vendida" not in fat.columns:
        fat["qtd_vendida"] = 0.0

    fat["id_produto"] = fat["id_produto"].astype("string").str.strip().str.upper()
    fat["nome_produto"] = fat["nome_produto"].fillna(fat["id_produto"]).astype("string").str.strip()
    fat["produto_nome_key"] = fat["nome_produto"].fillna("").astype(str).map(_normalise_value)
    fat["faturamento_item"] = pd.to_numeric(fat["faturamento_liquido"], errors="coerce").fillna(0.0)
    fat["preco_venda_unitario"] = _safe_divide(
        fat["faturamento_item"],
        pd.to_numeric(fat["qtd_vendida"], errors="coerce"),
    )

    custos = custo_producao_agregado.copy() if custo_producao_agregado is not None else pd.DataFrame()
    if custos.empty:
        custos = pd.DataFrame(columns=["id_produto", "custo_producao"])
    if "id_produto" not in custos.columns:
        custos["id_produto"] = ""
    if "nome_produto" not in custos.columns:
        custos["nome_produto"] = custos["id_produto"]
    if "custo_producao" not in custos.columns:
        custos["custo_producao"] = np.nan

    custos["id_produto"] = custos["id_produto"].astype("string").str.strip().str.upper()
    custos["nome_produto"] = custos["nome_produto"].fillna(custos["id_produto"]).astype("string").str.strip()
    custos["produto_nome_key"] = custos["nome_produto"].fillna("").astype(str).map(_normalise_value)
    custos["custo_producao"] = pd.to_numeric(custos["custo_producao"], errors="coerce")
    custos_by_id = custos[["id_produto", "custo_producao"]].drop_duplicates(subset=["id_produto"], keep="first")

    gold = fat.merge(custos_by_id, on="id_produto", how="left")
    if gold["custo_producao"].isna().any():
        custos_by_name = custos[["produto_nome_key", "custo_producao"]].copy()
        custos_by_name["produto_nome_key"] = custos_by_name["produto_nome_key"].replace({"": pd.NA, "nan": pd.NA, "none": pd.NA})
        custos_by_name = custos_by_name.dropna(subset=["produto_nome_key"]).drop_duplicates(subset=["produto_nome_key"], keep="first")
        if not custos_by_name.empty:
            gold = gold.merge(custos_by_name, on="produto_nome_key", how="left", suffixes=("", "_nome"))
            gold["custo_producao"] = gold["custo_producao"].fillna(gold["custo_producao_nome"])
            gold = gold.drop(columns=["custo_producao_nome"])
    gold["custo_producao_unitario"] = pd.to_numeric(gold["custo_producao"], errors="coerce")
    # Keep original NaN lineage for audit; only fill for arithmetic safety.
    gold["custo_producao_unitario_audit"] = gold["custo_producao_unitario"]
    custo_para_calculo = gold["custo_producao_unitario"].fillna(0.0)

    gold["margem_valor"] = pd.to_numeric(gold["preco_venda_unitario"], errors="coerce") - custo_para_calculo
    gold["margem_perc"] = _safe_divide(gold["margem_valor"], gold["preco_venda_unitario"]) * 100.0
    gold["markup"] = _safe_divide(gold["preco_venda_unitario"], custo_para_calculo)

    keep_cols = [
        "id_produto",
        "nome_produto",
        "faturamento_item",
        "preco_venda_unitario",
        "custo_producao_unitario",
        "custo_producao_unitario_audit",
        "margem_valor",
        "margem_perc",
        "markup",
    ]
    return gold[keep_cols].reset_index(drop=True)


def _build_default_drive_source() -> DriveDataSource | None:
    """Build Drive source from environment; returns None when folder is not configured."""
    folder_id = _drive_folder_id_from_env()
    if not folder_id:
        logger.warning("DRIVE_FOLDER_ID/GOOGLE_DRIVE_FOLDER_ID nao configurado; pipeline operara sem fonte tabular")
        return None
    try:
        return GoogleDriveAdapter(credential_file="", folder_id=folder_id)
    except Exception:
        logger.warning("Falha ao inicializar GoogleDriveAdapter", exc_info=True)
        return None



class MedallionPipeline:
    """Materializes RAW → SILVER → GOLD while preserving all source rows."""

    def __init__(
        self,
        source: Optional[DriveDataSource] = None,
        raw_dir: Path | str | None = None,
        silver_dir: Path | str | None = None,
        gold_dir: Path | str | None = None,
    ):
        del raw_dir, silver_dir, gold_dir  # backward-compatible args (Drive-only pipeline)
        self.source = source or _build_default_drive_source()
        self.silver_df: Optional[pd.DataFrame] = None
        self.fato_vendas: Optional[pd.DataFrame] = None
        self.dim_produto: Optional[pd.DataFrame] = None
        self.dim_tempo: Optional[pd.DataFrame] = None
        self.dim_canal: Optional[pd.DataFrame] = None
        self.gold_custos_produtos: Optional[pd.DataFrame] = None
        self.receitas_detalhadas: Optional[pd.DataFrame] = None
        self.gold_rentabilidade: Optional[pd.DataFrame] = None
        self.drive_manager = DriveManager()

    def _build_manifest_source_states(
        self,
        sync_state: dict[str, object],
        bronze_df: pd.DataFrame | None,
        manual_sheets: dict[str, pd.DataFrame],
    ) -> dict[str, dict[str, object]]:
        manifest_sources: dict[str, dict[str, object]] = {}
        has_manual_data = any(isinstance(df, pd.DataFrame) and not df.empty for df in manual_sheets.values())
        sync_sources = sync_state.get("sources", {}) if isinstance(sync_state, dict) else {}

        sales_source = sync_sources.get(_MANIFEST_SOURCE_SALES, {}) if isinstance(sync_sources, dict) else {}
        sales_modified = sales_source.get("current_modified_time") if isinstance(sales_source, dict) else None
        if sales_modified and bronze_df is not None and not bronze_df.empty:
            manifest_sources[_MANIFEST_SOURCE_SALES] = {
                "last_processed_timestamp": sales_modified,
                "row_count": int(len(bronze_df)),
                "checksum": _stable_dataframe_checksum(bronze_df),
            }

        costs_source = sync_sources.get(_MANIFEST_SOURCE_COSTS, {}) if isinstance(sync_sources, dict) else {}
        costs_modified = costs_source.get("current_modified_time") if isinstance(costs_source, dict) else None
        products_df = manual_sheets.get("produtos", pd.DataFrame())
        unique_products = _count_unique_catalog_products(products_df)
        source_sheet_id = _source_products_sheet_id()
        if costs_modified and has_manual_data:
            manifest_sources[_MANIFEST_SOURCE_COSTS] = {
                "source_file_id": source_sheet_id,
                "last_processed_timestamp": costs_modified,
                "row_count": unique_products,
                "unique_product_ids": unique_products,
                "checksum": _stable_manual_sheets_checksum(manual_sheets),
            }

        return manifest_sources

    def _persist_gold_to_drive(self, parquet_frames: dict[str, pd.DataFrame]) -> int:
        """Update existing parquet assets in Drive and validate read-back row counts."""
        uploaded = 0
        for file_name, frame in parquet_frames.items():
            payload = frame if isinstance(frame, pd.DataFrame) else pd.DataFrame()
            if update_parquet_in_drive(file_name, payload):
                uploaded += 1
                # Refresh caches before read-back validation.
                get_drive_assets_map.clear()
                load_parquet_from_drive.clear()
                readback = load_parquet_from_drive(file_name)
                expected = int(len(payload))
                observed = int(len(readback))
                if observed != expected:
                    logger.critical(
                        "[AUDIT][WRITE_MISMATCH] file=%s expected_rows=%d observed_rows=%d",
                        file_name,
                        expected,
                        observed,
                    )
                    raise RuntimeError(
                        f"Drive write consistency mismatch for {file_name}: expected {expected}, observed {observed}"
                    )
                logger.info("[AUDIT][WRITE_OK] file=%s rows=%d", file_name, expected)
        if uploaded:
            logger.info("Updated %d parquet asset(s) in Drive", uploaded)
        return uploaded

    def _preserve_existing_cost_gold_if_needed(
        self,
        sync_state: dict[str, object],
        source_audit: dict[str, object],
    ) -> None:
        """Avoid wiping cost-gold assets when costs source was updated but manual tabs are empty."""
        costs_state = (sync_state.get("sources", {}) or {}).get(_MANIFEST_SOURCE_COSTS, {})
        costs_changed = bool((costs_state or {}).get("changed")) if isinstance(costs_state, dict) else False
        if not costs_changed:
            return

        manual_sheet_audit = source_audit.get("manual_sheets", {}) if isinstance(source_audit, dict) else {}
        manual_rows_in = sum(
            int((entry or {}).get("rows_in", 0))
            for entry in manual_sheet_audit.values()
            if isinstance(entry, dict)
        )
        if manual_rows_in > 0:
            return

        current_custos = self.gold_custos_produtos if isinstance(self.gold_custos_produtos, pd.DataFrame) else pd.DataFrame()
        current_receitas = self.receitas_detalhadas if isinstance(self.receitas_detalhadas, pd.DataFrame) else pd.DataFrame()
        if not current_custos.empty or not current_receitas.empty:
            return

        fallback_custos = load_parquet_from_drive("custos_producao_agregado.parquet")
        fallback_receitas = load_parquet_from_drive("receitas_detalhadas.parquet")
        if fallback_custos.empty and fallback_receitas.empty:
            logger.error(
                "Fonte de custos sinalizou atualizacao, mas abas manuais vieram vazias e nao ha fallback parquet para preservar"
            )
            return

        self.gold_custos_produtos = fallback_custos.copy()
        self.receitas_detalhadas = fallback_receitas.copy()
        logger.error(
            "Abas manuais de custos vieram vazias durante update; preservando Gold anterior (custos=%d receitas=%d)",
            int(len(self.gold_custos_produtos)),
            int(len(self.receitas_detalhadas)),
        )

    def _load_existing_counts(self) -> dict[str, object]:
        silver_df = load_parquet_from_drive("sales_silver.parquet")
        gold_df = load_parquet_from_drive("fato_vendas.parquet")
        if gold_df.empty:
            return {
                "bronze_rows": 0,
                "silver_rows": 0,
                "quarantine_rows": 0,
                "gold_rows": 0,
                "used_existing_layers": False,
            }
        return {
            "bronze_rows": 0,
            "silver_rows": int(len(silver_df)) if not silver_df.empty else int(len(gold_df)),
            "quarantine_rows": 0,
            "gold_rows": int(len(gold_df)),
            "used_existing_layers": True,
        }

    def _log_audit_summary(self, **summary: object) -> None:
        """Emit a compact end-of-run audit summary for ops troubleshooting."""
        ordered_keys = [
            "mode",
            "should_process",
            "reason",
            "bronze_rows",
            "sales_rows_in",
            "manual_rows_in",
            "manual_rows_out",
            "silver_rows",
            "gold_rows",
            "gold_custos_rows",
            "receitas_rows",
            "gold_uploaded_files",
            "validation_all_ok",
            "dq_passed",
            "used_existing_layers",
            "timings_ms",
        ]
        tokens: list[str] = []
        for key in ordered_keys:
            if key not in summary:
                continue
            value = summary.get(key)
            if isinstance(value, dict):
                value = {k: value[k] for k in sorted(value)}
            tokens.append(f"{key}={value}")
        logger.info("[AUDIT][SUMMARY] %s", " | ".join(tokens))

    def run(self) -> dict[str, object]:
        logger.info("MedallionPipeline.run() starting...")
        stage_ms: dict[str, float] = {}
        source_sheet_id = _source_products_sheet_id()
        if self.source is None:
            logger.warning("Fonte de ingestao indisponivel; retornando contagem existente do Drive")
            result = self._load_existing_counts()
            self._log_audit_summary(mode="source_unavailable", should_process=False, reason="source_unavailable", **result)
            return result
        files = self.source.list_tabular_files()
        sales_files = [meta for meta in files if not _is_manual_sheet_name(_normalize_sheet_name(str(meta.get("name", ""))))]
        logger.info(
            "[AUDIT][GATE_PRECHECK] sales_files=%d latest_sales_modified=%s configured_sheet_id=%s",
            len(sales_files),
            DriveManager._latest_modified_time(sales_files),
            source_sheet_id,
        )
        sync_state = self.drive_manager.check_for_updates(
            sales_files=sales_files,
            production_costs_sheet_id=source_sheet_id,
        )
        sales_state = (sync_state.get("sources", {}) or {}).get(_MANIFEST_SOURCE_SALES, {})
        costs_state = (sync_state.get("sources", {}) or {}).get(_MANIFEST_SOURCE_COSTS, {})
        logger.info(
            "[AUDIT][GATE] sales_current=%s sales_manifest=%s costs_current=%s costs_manifest=%s should_process=%s reason=%s",
            sales_state.get("current_modified_time"),
            sales_state.get("previous_modified_time"),
            costs_state.get("current_modified_time"),
            costs_state.get("previous_modified_time"),
            bool(sync_state.get("should_process", True)),
            sync_state.get("reason"),
        )
        if not bool(sync_state.get("should_process", True)):
            logger.info("[AUDIT][GATE_DECISION] processamento ignorado. motivo=%s", sync_state.get("reason"))
            result = self._load_existing_counts()
            self._log_audit_summary(
                mode="gate_skip",
                should_process=False,
                reason=sync_state.get("reason"),
                **result,
            )
            return result
        if not files:
            result = self._load_existing_counts()
            self._log_audit_summary(mode="no_files", should_process=False, reason="no_tabular_files", **result)
            return result

        bronze_df, manual_sheets, source_audit = read_raw_sources(self.source, files=files)
        logger.info("[AUDIT][BRONZE] Linhas lidas da Planilha: %d", int(len(bronze_df)))
        has_manual_data = any(isinstance(df, pd.DataFrame) and not df.empty for df in manual_sheets.values())
        bronze_rows = int(len(bronze_df))
        products_rows = int(len(manual_sheets.get("produtos", pd.DataFrame())))
        products_unique_rows = _count_unique_catalog_products(manual_sheets.get("produtos", pd.DataFrame()))
        receitas_rows = int(len(manual_sheets.get("receitas", pd.DataFrame())))
        sync_sources = sync_state.get("sources", {}) if isinstance(sync_state, dict) else {}
        sales_previous_rows = int(((sync_sources.get(_MANIFEST_SOURCE_SALES, {}) if isinstance(sync_sources, dict) else {}) or {}).get("previous_row_count", 0))
        costs_previous_rows = int(((sync_sources.get(_MANIFEST_SOURCE_COSTS, {}) if isinstance(sync_sources, dict) else {}) or {}).get("previous_row_count", 0))
        logger.info("Fonte: Planilha de Produtos -> Detectadas %d linhas (Anterior: %d)", products_rows, costs_previous_rows)
        logger.info("Fonte: Planilha de Produtos -> IDs unicos detectados=%d", products_unique_rows)
        logger.info("Fonte: Planilha de Receitas -> Detectadas %d linhas apos normalizacao", receitas_rows)
        logger.info("Fonte: CSV de Vendas -> Detectadas %d linhas (Anterior: %d)", bronze_rows, sales_previous_rows)
        logger.info("Silver source audit: %s", source_audit)

        if bronze_df.empty and not has_manual_data:
            result = self._load_existing_counts()
            self._log_audit_summary(mode="empty_sources", should_process=False, reason="bronze_and_manual_empty", **result)
            return result

        if bronze_df.empty and has_manual_data:
            manual_cost_map = _build_manual_cost_map(manual_sheets)
            self.gold_custos_produtos, self.receitas_detalhadas = build_gold_custos_produtos(manual_sheets, manual_cost_map)
            self._preserve_existing_cost_gold_if_needed(sync_state, source_audit)
            logger.info(
                "Gold custos (manual-only): produtos=%d receitas_detalhadas=%d",
                int(len(self.gold_custos_produtos)) if self.gold_custos_produtos is not None else 0,
                int(len(self.receitas_detalhadas)) if self.receitas_detalhadas is not None else 0,
            )
            agg_produto = load_parquet_from_drive("agg_vendas_produto.parquet")
            self.gold_rentabilidade = build_gold_rentabilidade(agg_produto, self.gold_custos_produtos)

            stage_start = perf_counter()
            uploaded_gold_files = self._persist_gold_to_drive(
                {
                    "custos_producao_agregado.parquet": self.gold_custos_produtos if self.gold_custos_produtos is not None else pd.DataFrame(),
                    "custos_producao.parquet": self.gold_custos_produtos if self.gold_custos_produtos is not None else pd.DataFrame(),
                    "receitas_detalhadas.parquet": self.receitas_detalhadas if self.receitas_detalhadas is not None else pd.DataFrame(),
                    "gold_rentabilidade.parquet": self.gold_rentabilidade if self.gold_rentabilidade is not None else pd.DataFrame(),
                }
            )
            stage_ms["persist_drive"] = (perf_counter() - stage_start) * 1000

            silver_existing = load_parquet_from_drive("sales_silver.parquet")
            dim_produto_existing = load_parquet_from_drive("dim_produto.parquet")
            dim_tempo_existing = load_parquet_from_drive("dim_tempo.parquet")
            fato_existing = load_parquet_from_drive("fato_vendas.parquet")
            validation = validate_star_schema(fato_existing, dim_produto_existing, dim_tempo_existing, len(silver_existing) if not silver_existing.empty else None)

            dq_passed = False
            try:
                dq_results = DataQualityValidator(verbose=False).validate_all(dim_produto_existing, dim_tempo_existing, fato_existing)
                dq_passed = bool(all(dq_results.values()))
            except Exception:
                logger.warning("DataQualityValidator raised a non-fatal validation error.", exc_info=True)

            manifest_sources = self._build_manifest_source_states(sync_state, bronze_df if not bronze_df.empty else None, manual_sheets)
            if validation.get("all_ok") and dq_passed and manifest_sources:
                self.drive_manager.update_manifest_state(
                    source_states=manifest_sources,
                    manifest_file_id=sync_state.get("manifest_file_id"),
                )

            existing_counts = self._load_existing_counts()
            result = {
                "bronze_rows": bronze_rows,
                "silver_rows": int(existing_counts.get("silver_rows", 0)),
                "quarantine_rows": 0,
                "gold_rows": int(existing_counts.get("gold_rows", 0)),
                "used_existing_layers": True,
                "dedup_removed": 0,
                "integrity_report": {},
                "validation": validation,
                "gold_custos_rows": int(len(self.gold_custos_produtos)) if self.gold_custos_produtos is not None else 0,
                "gold_uploaded_files": uploaded_gold_files,
                "dq_passed": dq_passed,
                "timings_ms": {k: round(v, 2) for k, v in stage_ms.items()},
            }
            manual_sheet_audit = source_audit.get("manual_sheets", {}) if isinstance(source_audit, dict) else {}
            manual_rows_in = sum(
                int((entry or {}).get("rows_in", 0))
                for entry in manual_sheet_audit.values()
                if isinstance(entry, dict)
            )
            manual_rows_out = sum(
                int((entry or {}).get("rows_out", 0))
                for entry in manual_sheet_audit.values()
                if isinstance(entry, dict)
            )
            self._log_audit_summary(
                mode="manual_only",
                should_process=True,
                reason=sync_state.get("reason"),
                sales_rows_in=source_audit.get("sales_rows_in", 0),
                manual_rows_in=manual_rows_in,
                manual_rows_out=manual_rows_out,
                receitas_rows=int(len(self.receitas_detalhadas)) if self.receitas_detalhadas is not None else 0,
                validation_all_ok=bool(validation.get("all_ok")),
                **result,
            )
            logger.info("MedallionPipeline.run() finished: %s", result)
            return result

        stage_start = perf_counter()
        self.silver_df, silver_audit = transform_to_silver(bronze_df)
        logger.info("[AUDIT][SILVER] rows_in=%d rows_out=%d", int(len(bronze_df)), int(len(self.silver_df)))
        missing_silver_cols = [c for c in ("data", "produto", "quantidade", "valor_total", "custo") if c not in self.silver_df.columns]
        if missing_silver_cols:
            raise ValueError(f"Silver schema inválido; colunas ausentes: {missing_silver_cols}")
        stage_ms["silver_transform"] = (perf_counter() - stage_start) * 1000
        integrity_report = dict(silver_audit.get("integrity_report", {}))
        logger.info("=" * 80)
        logger.info("[PIPELINE INTEGRITY REPORT: BRONZE → SILVER]")
        logger.info("=" * 80)
        for month in ("Month 01", "Month 02", "Month 03"):
            logger.info("  %s: %s", month, integrity_report.get(month, "Fixed"))
        logger.info("=" * 80)

        # Optional enrichment from manual cost sheets (if available).
        manual_cost_map = _build_manual_cost_map(manual_sheets)
        if manual_cost_map:
            self.silver_df = enrich_cost_from_catalog(self.silver_df, manual_cost_map)
            logger.info("Applied manual cost enrichment from Receitas/Matéria Prima to SILVER (%d keys).", len(manual_cost_map))

        stage_start = perf_counter()
        self.dim_produto = build_dim_produto(self.silver_df)
        self.dim_tempo = build_dim_tempo(self.silver_df)
        self.dim_canal = build_dim_canal(self.silver_df)
        self.fato_vendas = build_fato_vendas(self.silver_df, self.dim_produto, self.dim_tempo, self.dim_canal)
        stage_ms["gold_dimensions_fato"] = (perf_counter() - stage_start) * 1000

        stage_start = perf_counter()
        agg_dia = build_agg_vendas_dia(self.fato_vendas, self.dim_tempo)
        agg_canal = build_agg_vendas_canal(self.fato_vendas, self.dim_canal)
        agg_produto = build_agg_vendas_produto(self.fato_vendas, self.dim_produto)
        agg_tempo = build_agg_vendas_tempo(self.fato_vendas, self.dim_tempo)
        self.gold_custos_produtos, self.receitas_detalhadas = build_gold_custos_produtos(manual_sheets, manual_cost_map)
        self._preserve_existing_cost_gold_if_needed(sync_state, source_audit)
        logger.info(
            "[AUDIT][GOLD] fato=%d agg_dia=%d agg_canal=%d agg_produto=%d agg_tempo=%d custos=%d receitas_detalhadas=%d",
            int(len(self.fato_vendas)),
            int(len(agg_dia)),
            int(len(agg_canal)),
            int(len(agg_produto)),
            int(len(agg_tempo)),
            int(len(self.gold_custos_produtos)) if self.gold_custos_produtos is not None else 0,
            int(len(self.receitas_detalhadas)) if self.receitas_detalhadas is not None else 0,
        )
        logger.info(
            "Gold custos: produtos=%d receitas_detalhadas=%d",
            int(len(self.gold_custos_produtos)) if self.gold_custos_produtos is not None else 0,
            int(len(self.receitas_detalhadas)) if self.receitas_detalhadas is not None else 0,
        )
        self.gold_rentabilidade = build_gold_rentabilidade(agg_produto, self.gold_custos_produtos)
        stage_ms["gold_aggregations"] = (perf_counter() - stage_start) * 1000

        _enforce_zero_loss_months(integrity_report)

        stage_start = perf_counter()
        parquet_payloads: dict[str, pd.DataFrame] = {
            "sales_silver.parquet": self.silver_df,
            "dim_produto.parquet": self.dim_produto,
            "dim_tempo.parquet": self.dim_tempo,
            "dim_canal.parquet": self.dim_canal,
            "fato_vendas.parquet": self.fato_vendas,
            "agg_vendas_dia.parquet": agg_dia,
            "agg_vendas_canal.parquet": agg_canal,
            "agg_vendas_produto.parquet": agg_produto,
            "agg_vendas_tempo.parquet": agg_tempo,
            "custos_producao_agregado.parquet": self.gold_custos_produtos if self.gold_custos_produtos is not None else pd.DataFrame(),
            "custos_producao.parquet": self.gold_custos_produtos if self.gold_custos_produtos is not None else pd.DataFrame(),
            "receitas_detalhadas.parquet": self.receitas_detalhadas if self.receitas_detalhadas is not None else pd.DataFrame(),
            "gold_rentabilidade.parquet": self.gold_rentabilidade if self.gold_rentabilidade is not None else pd.DataFrame(),
        }
        uploaded_gold_files = self._persist_gold_to_drive(parquet_payloads)
        stage_ms["persist_drive"] = (perf_counter() - stage_start) * 1000

        validation = validate_star_schema(self.fato_vendas, self.dim_produto, self.dim_tempo, len(self.silver_df))

        # Log detailed validation results
        logger.info("="*80)
        logger.info("[STAR SCHEMA VALIDATION RESULTS]")
        logger.info("="*80)
        logger.info("Foreign Key Integrity:")
        logger.info("  produto_id: %s (%d orphans)", "✅ OK" if validation["fk_produto_id_ok"] else "❌ FAIL", validation["fk_produto_id_orphans"])
        logger.info("  data_id: %s (%d orphans)", "✅ OK" if validation["fk_data_id_ok"] else "❌ FAIL", validation["fk_data_id_orphans"])
        logger.info("Primary Key Integrity:")
        logger.info("  venda_id: %s (%d nulls)", "✅ OK" if validation["pk_venda_id_ok"] else "❌ FAIL", validation["pk_venda_id_nulls"])
        logger.info("Row Count Consistency:")
        logger.info("  Silver → Gold: %d → %d (diff: %d) %s",
                   len(self.silver_df),
                   len(self.fato_vendas),
                   validation["silver_gold_rowcount_diff"],
                   "✅ OK" if validation["silver_gold_rowcount_ok"] else "❌ MISMATCH")
        logger.info("Other Checks:")
        logger.info("  Infinite margins: %s", "✅ None" if validation["margem_no_inf_ok"] else f"❌ {validation['margem_inf_count']} found")
        logger.info("Overall Status: %s", "✅ PASSED" if validation["all_ok"] else "❌ FAILED")
        logger.info("="*80)

        dq_passed = False
        try:
            dq_results = DataQualityValidator(verbose=False).validate_all(self.dim_produto, self.dim_tempo, self.fato_vendas)
            dq_passed = bool(all(dq_results.values()))
        except Exception:
            logger.warning("DataQualityValidator raised a non-fatal validation error.", exc_info=True)

        manifest_sources = self._build_manifest_source_states(sync_state, bronze_df, manual_sheets)
        if validation.get("all_ok") and dq_passed and manifest_sources:
            self.drive_manager.update_manifest_state(
                source_states=manifest_sources,
                manifest_file_id=sync_state.get("manifest_file_id"),
            )
        else:
            logger.info(
                "Manifesto nao atualizado (validation_all_ok=%s dq_passed=%s manifest_sources=%s)",
                bool(validation.get("all_ok")),
                dq_passed,
                sorted(manifest_sources),
            )

        result = {
            "bronze_rows": bronze_rows,
            "silver_rows": int(len(self.silver_df)),
            "quarantine_rows": 0,
            "gold_rows": int(len(self.fato_vendas)),
            "used_existing_layers": False,
            "dedup_removed": int(silver_audit.get("removed", 0)),
            "integrity_report": integrity_report,
            "validation": validation,
            "gold_custos_rows": int(len(self.gold_custos_produtos)) if self.gold_custos_produtos is not None else 0,
            "gold_uploaded_files": uploaded_gold_files,
            "dq_passed": dq_passed,
            "timings_ms": {k: round(v, 2) for k, v in stage_ms.items()},
        }
        manual_sheet_audit = source_audit.get("manual_sheets", {}) if isinstance(source_audit, dict) else {}
        manual_rows_in = sum(
            int((entry or {}).get("rows_in", 0))
            for entry in manual_sheet_audit.values()
            if isinstance(entry, dict)
        )
        manual_rows_out = sum(
            int((entry or {}).get("rows_out", 0))
            for entry in manual_sheet_audit.values()
            if isinstance(entry, dict)
        )
        self._log_audit_summary(
            mode="full_process",
            should_process=True,
            reason=sync_state.get("reason"),
            sales_rows_in=source_audit.get("sales_rows_in", 0),
            manual_rows_in=manual_rows_in,
            manual_rows_out=manual_rows_out,
            receitas_rows=int(len(self.receitas_detalhadas)) if self.receitas_detalhadas is not None else 0,
            validation_all_ok=bool(validation.get("all_ok")),
            **result,
        )
        logger.info("MedallionPipeline.run() finished: %s", result)
        return result


if __name__ == "__main__":
    result = MedallionPipeline().run()
    print(result)
