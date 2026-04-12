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
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
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
        "ingrediente_id": "ingrediente_id",
        "id_do_ingrediente": "ingrediente_id",
        "id do ingrediente": "ingrediente_id",
        "qtd": "qtd",
        "quantidade": "qtd",
        "quantidade_por_produto": "qtd",
        "unidade_de_medida": "unidade",
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
            text = text.str.replace(",", ".", regex=False)
            out[col] = pd.to_numeric(text, errors="coerce").fillna(0.0)

    return out


def _build_manual_cost_map(manual_sheets: dict[str, pd.DataFrame]) -> dict[str, float]:
    """
    Builds product cost map from manual tabs (Receitas + Matéria Prima).
    Key format is normalized product token for use with `_normalise_value`.
    """
    receitas = manual_sheets.get("receitas")
    materia = manual_sheets.get("materia_prima")
    if receitas is None or receitas.empty or materia is None or materia.empty:
        return {}

    if not {"produto_id", "ingrediente_id", "qtd"}.issubset(receitas.columns):
        return {}
    if not {"item", "custo_unit"}.issubset(materia.columns):
        return {}

    rec = receitas.copy()
    mp = materia.copy()
    rec["ingrediente_id_norm"] = rec["ingrediente_id"].astype(str).str.strip().str.lower()
    mp["item_norm"] = mp["item"].astype(str).str.strip().str.lower()

    merged = rec.merge(
        mp[["item_norm", "custo_unit"]],
        left_on="ingrediente_id_norm",
        right_on="item_norm",
        how="left",
    )
    merged["qtd"] = pd.to_numeric(merged["qtd"], errors="coerce").fillna(0.0)
    merged["custo_unit"] = pd.to_numeric(merged["custo_unit"], errors="coerce").fillna(0.0)
    merged["custo_item"] = merged["qtd"] * merged["custo_unit"]

    agg = merged.groupby("produto_id", as_index=False)["custo_item"].sum()
    return {
        _normalise_value(prod): float(cost)
        for prod, cost in agg[["produto_id", "custo_item"]].itertuples(index=False, name=None)
        if str(prod).strip() != ""
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
    ]
    agg_cols = ["id_produto", "nome_produto", "qtd_ingredientes", "custo_producao"]

    def _prune_first_two(df: pd.DataFrame) -> pd.DataFrame:
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

    receitas = _prune_first_two(manual_sheets.get("receitas", pd.DataFrame()).copy())
    materia = _prune_first_two(manual_sheets.get("materia_prima", pd.DataFrame()).copy())
    produtos = _prune_first_two(manual_sheets.get("produtos", pd.DataFrame()).copy())

    if receitas.empty:
        return pd.DataFrame(columns=agg_cols), pd.DataFrame(columns=cols)

    if "produto_id" not in receitas.columns:
        receitas["produto_id"] = ""
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
    rec["id_ingrediente"] = rec["ingrediente_id"].astype("string").str.strip()
    rec = rec.dropna(subset=["id_produto", "id_ingrediente"]).copy()
    rec_prod_key = rec["id_produto"].astype(str).str.strip().str.lower()
    rec = rec[~rec_prod_key.isin({"", "nan", "none", "nat"})].copy()
    rec_ing_key = rec["id_ingrediente"].astype(str).str.strip().str.lower()
    rec = rec[~rec_ing_key.isin({"", "nan", "none", "nat"})].copy()
    rec["qtd_receita"] = pd.to_numeric(rec["qtd"], errors="coerce").fillna(0.0)
    rec["unidade"] = rec["unidade"].fillna("").astype(str).str.strip()
    rec["ingrediente_key"] = rec["id_ingrediente"].astype(str).str.strip().str.lower()

    prod = produtos.copy()
    prod["id_produto"] = prod["produto_id"].astype("string").str.strip().str.upper()
    prod["nome"] = prod["nome"].fillna("").astype(str).str.strip()
    prod = prod.dropna(subset=["id_produto"]).copy()
    prod_key = prod["id_produto"].astype(str).str.strip().str.lower()
    prod = prod[~prod_key.isin({"", "nan", "none", "nat"})].copy()
    prod = prod.drop_duplicates(subset=["id_produto"], keep="first")

    mp = materia.copy()
    mp["id_ingrediente"] = mp["ingrediente_id"].astype("string").str.strip()
    mp = mp.dropna(subset=["id_ingrediente"]).copy()
    mp_key = mp["id_ingrediente"].astype(str).str.strip().str.lower()
    mp = mp[~mp_key.isin({"", "nan", "none", "nat"})].copy()
    mp["ingrediente_key"] = mp["id_ingrediente"].astype(str).str.strip().str.lower()
    mp["nome_ingrediente"] = mp["nome_ingrediente"].fillna("").astype(str).str.strip()
    mp["unidade"] = mp["unidade"].fillna("").astype(str).str.strip()
    mp["custo_un_mat_prima"] = pd.to_numeric(mp["custo_unit"], errors="coerce")
    mp["rendimento_embalagem"] = pd.to_numeric(mp["rendimento_embalagem"], errors="coerce").fillna(0.0)
    mp = mp.drop_duplicates(subset=["id_ingrediente"], keep="first")

    detail = rec.merge(
        prod[["id_produto", "nome"]],
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
    detail["id_ingrediente"] = detail["id_ingrediente_mp"].fillna(detail["id_ingrediente"]).fillna("").astype(str).str.strip()
    detail["nome_ingrediente"] = detail["nome_ingrediente"].astype("string").str.strip()
    detail["nome_ingrediente"] = detail["nome_ingrediente"].replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    detail["nome_ingrediente"] = detail["nome_ingrediente"].fillna(detail["id_ingrediente"]).astype(str).str.strip()
    if "unidade_mp" not in detail.columns:
        detail["unidade_mp"] = detail["unidade"]

    qty_num = pd.to_numeric(detail["qtd_receita"], errors="coerce")
    qty_txt = pd.Series(np.where(qty_num.notna(), qty_num.map(lambda x: f"{x:g}"), ""), index=detail.index).astype(str)
    unit_txt = detail["unidade"].fillna("").astype(str).str.strip()
    unit_txt = unit_txt.mask(unit_txt.eq(""), detail["unidade_mp"].fillna("").astype(str).str.strip())
    detail["quantidade_formatada"] = (qty_txt + " " + unit_txt).str.strip()

    # Keep Gold numeric as float; Streamlit handles visual BRL formatting.
    # Formula: (Custo_Unitario_Materia_Prima / Rendimento_Embalagem) * Quantidade_Receita
    denom = detail["rendimento_embalagem"].fillna(1.0)
    denom = denom.where(denom > 0, 1.0)
    numer = pd.to_numeric(detail["custo_un_mat_prima"], errors="coerce")
    qtd = pd.to_numeric(detail["qtd_receita"], errors="coerce")

    recipe_unit = detail["unidade"].fillna("").astype(str).str.strip().str.lower()
    material_unit = detail["unidade_mp"].fillna("").astype(str).str.strip().str.lower()
    recipe_small_unit = recipe_unit.isin({"g", "gr", "grama", "gramas", "ml", "mililitro", "mililitros"})
    material_large_unit = material_unit.isin({"k", "kg", "quilo", "quilos", "l", "lt", "litro", "litros"})
    qtd_ajustada = pd.Series(
        np.where(recipe_small_unit & material_large_unit, qtd / 1000.0, qtd),
        index=detail.index,
    )

    detail["custo_calculado"] = (numer / denom) * qtd_ajustada
    detail["custo_unitario_final"] = pd.to_numeric(detail["custo_calculado"], errors="coerce").astype("float64")

    df_detalhado = detail[cols].copy().reset_index(drop=True)
    df_detalhado.index.name = None

    df_gold_produtos = (
        df_detalhado.groupby(["id_produto", "nome_produto"], as_index=False)
        .agg(
            qtd_ingredientes=("id_ingrediente", "count"),
            custo_producao=("custo_unitario_final", lambda s: s.sum(min_count=1)),
        )
        .reset_index(drop=True)
    )
    df_gold_produtos["custo_producao"] = pd.to_numeric(df_gold_produtos["custo_producao"], errors="coerce").astype("float64")
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
        fat["id_produto"] = ""
    if "nome_produto" not in fat.columns:
        fat["nome_produto"] = fat["id_produto"]
    if "faturamento_liquido" not in fat.columns:
        fat["faturamento_liquido"] = 0.0
    if "qtd_vendida" not in fat.columns:
        fat["qtd_vendida"] = 0.0

    fat["id_produto"] = fat["id_produto"].astype("string").str.strip().str.upper()
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
    if "custo_producao" not in custos.columns:
        custos["custo_producao"] = np.nan

    custos["id_produto"] = custos["id_produto"].astype("string").str.strip().str.upper()
    custos["custo_producao"] = pd.to_numeric(custos["custo_producao"], errors="coerce")
    custos = custos[["id_produto", "custo_producao"]].drop_duplicates(subset=["id_produto"], keep="first")

    gold = fat.merge(custos, on="id_produto", how="left")
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
        self.gold_custos_produtos: Optional[pd.DataFrame] = None
        self.receitas_detalhadas: Optional[pd.DataFrame] = None
        self.gold_rentabilidade: Optional[pd.DataFrame] = None

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
        stage_ms: dict[str, float] = {}
        files = self.source.list_tabular_files()
        if not files:
            return self._load_existing_counts()

        frames: list[pd.DataFrame] = []
        manual_sheets: dict[str, pd.DataFrame] = {}
        for meta in files:
            df = self.source.read_as_dataframe(meta)
            if df is None or df.empty:
                continue
            source_name = str(meta.get("name", ""))
            normalized_name = _normalize_sheet_name(source_name)

            # Apply manual-sheet cleaning before any merge/calc in Gold.
            if normalized_name.startswith("manual_materia_prima"):
                cleaned = clean_cost_sheet(df, MANUAL_SHEET_COLUMN_MAPS["materia_prima"])
                manual_sheets["materia_prima"] = cleaned
                continue
            if normalized_name.startswith("manual_receitas"):
                cleaned = clean_cost_sheet(df, MANUAL_SHEET_COLUMN_MAPS["receitas"])
                manual_sheets["receitas"] = cleaned
                continue
            if normalized_name.startswith("manual_produtos"):
                cleaned = clean_cost_sheet(df, MANUAL_SHEET_COLUMN_MAPS["produtos"])
                manual_sheets["produtos"] = cleaned
                continue

            if "materia" in normalized_name and "prima" in normalized_name:
                cleaned = clean_cost_sheet(df, MANUAL_SHEET_COLUMN_MAPS["materia_prima"])
                manual_sheets["materia_prima"] = cleaned
                continue
            if "produtos" in normalized_name or normalized_name == "produto":
                cleaned = clean_cost_sheet(df, MANUAL_SHEET_COLUMN_MAPS["produtos"])
                manual_sheets["produtos"] = cleaned
                continue
            if "receitas" in normalized_name or normalized_name == "receita":
                cleaned = clean_cost_sheet(df, MANUAL_SHEET_COLUMN_MAPS["receitas"])
                manual_sheets["receitas"] = cleaned
                continue

            frame = df.copy()
            if "_source_file" not in frame.columns:
                frame["_source_file"] = meta.get("name", "")
            frames.append(frame)

        if not frames:
            return self._load_existing_counts()

        stage_start = perf_counter()
        bronze_df = pd.concat(frames, ignore_index=True)
        bronze_rows = int(len(bronze_df))
        self.silver_df, silver_audit = transform_to_silver(bronze_df)
        missing_silver_cols = [c for c in ("data", "produto", "quantidade", "valor_total", "custo") if c not in self.silver_df.columns]
        if missing_silver_cols:
            raise ValueError(f"Silver schema inválido; colunas ausentes: {missing_silver_cols}")
        stage_ms["silver_transform"] = (perf_counter() - stage_start) * 1000

        # Optional enrichment from manual cost sheets (if available).
        manual_cost_map = _build_manual_cost_map(manual_sheets)
        if manual_cost_map:
            self.silver_df = enrich_cost_from_catalog(self.silver_df, manual_cost_map)
            logger.info("Applied manual cost enrichment from Receitas/Matéria Prima to SILVER (%d keys).", len(manual_cost_map))

        _ensure_dir(self.silver_dir)
        _ensure_dir(self.gold_dir)
        self.silver_df.to_parquet(self.silver_dir / "sales_silver.parquet", engine="pyarrow", index=False)

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
        self.gold_rentabilidade = build_gold_rentabilidade(agg_produto, self.gold_custos_produtos)
        stage_ms["gold_aggregations"] = (perf_counter() - stage_start) * 1000

        stage_start = perf_counter()
        self.dim_produto.to_parquet(self.gold_dir / "dim_produto.parquet", engine="pyarrow", index=False)
        self.dim_tempo.to_parquet(self.gold_dir / "dim_tempo.parquet", engine="pyarrow", index=False)
        self.dim_canal.to_parquet(self.gold_dir / "dim_canal.parquet", engine="pyarrow", index=False)
        self.fato_vendas.to_parquet(self.gold_dir / "fato_vendas.parquet", engine="pyarrow", index=False)
        agg_dia.to_parquet(self.gold_dir / "agg_vendas_dia.parquet", engine="pyarrow", index=False)
        agg_canal.to_parquet(self.gold_dir / "agg_vendas_canal.parquet", engine="pyarrow", index=False)
        agg_produto.to_parquet(self.gold_dir / "agg_vendas_produto.parquet", engine="pyarrow", index=False)
        agg_tempo.to_parquet(self.gold_dir / "agg_vendas_tempo.parquet", engine="pyarrow", index=False)
        os.makedirs(str(self.gold_dir), exist_ok=True)
        processed_agg_path = self.gold_dir / "custos_producao_agregado.parquet"
        self.gold_custos_produtos.to_parquet(processed_agg_path, engine="pyarrow", index=False)
        print(f"Sucesso: Arquivo salvo em {processed_agg_path}")
        processed_detail_path = self.gold_dir / "receitas_detalhadas.parquet"
        (self.receitas_detalhadas if self.receitas_detalhadas is not None else pd.DataFrame()).to_parquet(
            processed_detail_path,
            engine="pyarrow",
            index=False,
        )
        print(f"Sucesso: Arquivo salvo em {processed_detail_path}")
        processed_rent_path = self.gold_dir / "gold_rentabilidade.parquet"
        (self.gold_rentabilidade if self.gold_rentabilidade is not None else pd.DataFrame()).to_parquet(
            processed_rent_path,
            engine="pyarrow",
            index=False,
        )
        print(f"Sucesso: Arquivo salvo em {processed_rent_path}")

        # Legacy alias kept for compatibility with existing loaders.
        legacy_custos_path = self.gold_dir / "custos_producao.parquet"
        self.gold_custos_produtos.to_parquet(legacy_custos_path, engine="pyarrow", index=False)
        print(f"Sucesso: Arquivo salvo em {legacy_custos_path}")

        # Fast-read location requested for Streamlit cockpit
        fast_gold_dir = _ROOT / "data" / "gold"
        os.makedirs(str(fast_gold_dir), exist_ok=True)
        fast_agg_path = fast_gold_dir / "custos_producao_agregado.parquet"
        self.gold_custos_produtos.to_parquet(fast_agg_path, engine="pyarrow", index=False)
        print(f"Sucesso: Arquivo salvo em {fast_agg_path}")
        fast_detail_path = fast_gold_dir / "receitas_detalhadas.parquet"
        (self.receitas_detalhadas if self.receitas_detalhadas is not None else pd.DataFrame()).to_parquet(
            fast_detail_path,
            engine="pyarrow",
            index=False,
        )
        print(f"Sucesso: Arquivo salvo em {fast_detail_path}")

        # Legacy alias kept for compatibility with existing loaders.
        fast_legacy_custos_path = fast_gold_dir / "custos_producao.parquet"
        self.gold_custos_produtos.to_parquet(fast_legacy_custos_path, engine="pyarrow", index=False)
        print(f"Sucesso: Arquivo salvo em {fast_legacy_custos_path}")
        stage_ms["persist_parquet"] = (perf_counter() - stage_start) * 1000

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
            "gold_custos_rows": int(len(self.gold_custos_produtos)) if self.gold_custos_produtos is not None else 0,
            "timings_ms": {k: round(v, 2) for k, v in stage_ms.items()},
        }
        logger.info("MedallionPipeline.run() finished: %s", result)
        return result


if __name__ == "__main__":
    result = MedallionPipeline().run()
    print(result)
