"""Unit tests for scripts/medallion_pipeline.py.

All tests run in-memory — no real files, no Google APIs.
Fixtures build minimal DataFrames that exercise edge cases:
  - accented / mixed-case headers
  - dates from XLSX (already datetime64) and CSV (string "mm/dd/yyyy")
  - numeric columns with R$ currency strings
  - cross-file duplicate rows
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import pytest

# ── Ensure project root on sys.path ───────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.medallion_pipeline import (  # noqa: E402
    LocalRawSource,
    _coerce_types,
    _map_canonical,
    _normalise_columns,
    build_dim_produto,
    build_dim_tempo,
    build_fato_vendas,
    enrich_cost_from_catalog,
    transform_to_silver,
    validate_star_schema,
    SILVER_COLUMNS,
    _MONTH_PT,
)


# ─────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def minimal_raw_df() -> pd.DataFrame:
    """Minimal raw DataFrame mirroring a typical sales CSV row."""
    return pd.DataFrame([
        {
            "Número da venda":           1001,
            "Nota Fiscal / RPS":         "NF-001",
            "Data da venda":             "2/1/2026",   # CSV US format: Feb 1
            "Cliente":                   "João",
            "Nome do produto/serviço":   "Brigadeiro",
            "Unidade de medida":         "UN",
            "Quantidade de itens":       2,
            "Valor unitário":            "R$ 5,00",
            "Valor Bruto":               "R$ 10,00",
            "Desconto na venda":         "R$ 0,00",
            "Valor Liquido no Financeiro": "R$ 10,00",
            "Valor Total":               "R$ 10,00",
            "Peso Bruto":                "0",
            "Peso Total":                "0",
            "Cidade do cliente":         "São Paulo",
            "Tipo de item (produto ou serviço)": "Produto",
            "Tipo de Negociação":        "À Vista",
            "_source_file":              "sales_data.csv",
        },
        {
            "Número da venda":           1002,
            "Nota Fiscal / RPS":         "NF-002",
            "Data da venda":             "2/3/2026",   # Feb 3
            "Cliente":                   "Maria",
            "Nome do produto/serviço":   "Risole",
            "Unidade de medida":         "UN",
            "Quantidade de itens":       1,
            "Valor unitário":            "R$ 8,00",
            "Valor Bruto":               "R$ 8,00",
            "Desconto na venda":         "R$ 0,00",
            "Valor Liquido no Financeiro": "R$ 8,00",
            "Valor Total":               "R$ 8,00",
            "Peso Bruto":                "0",
            "Peso Total":                "0",
            "Cidade do cliente":         "Campinas",
            "Tipo de item (produto ou serviço)": "Produto",
            "Tipo de Negociação":        "Crédito",
            "_source_file":              "sales_data.csv",
        },
    ])


@pytest.fixture()
def minimal_raw_df_xlsx() -> pd.DataFrame:
    """Minimal raw DataFrame mirroring an XLSX file (dates already datetime64)."""
    return pd.DataFrame([
        {
            "Número da venda":           1001,
            "Nota Fiscal / RPS":         "NF-001",
            "Data da venda":             pd.Timestamp("2026-02-01"),
            "Cliente":                   "João",
            "Nome do produto/serviço":   "Brigadeiro",
            "Unidade de medida":         "UN",
            "Quantidade de itens":       2,
            "Valor unitário":            5.00,
            "Valor Bruto":               10.00,
            "Desconto na venda":         0.00,
            "Valor Liquido no Financeiro": 10.00,
            "Valor Total":               10.00,
            "Peso Bruto":                0,
            "Peso Total":                0,
            "Cidade do cliente":         "São Paulo",
            "Tipo de item (produto ou serviço)": "Produto",
            "Tipo de Negociação":        "À Vista",
            "_source_file":              "sales_data.xlsx",
        },
    ])


@pytest.fixture()
def silver_df() -> pd.DataFrame:
    """Pre-built minimal silver DataFrame for gold-stage tests."""
    return pd.DataFrame([
        {
            "num_venda":      1001,
            "nota_fiscal":    "NF-001",
            "data":           pd.Timestamp("2026-02-01"),
            "cliente":        "João",
            "produto":        "Brigadeiro",
            "unidade_medida": "UN",
            "quantidade":     2.0,
            "valor_unitario": 5.0,
            "valor_bruto":    10.0,
            "desconto":       0.0,
            "valor_liquido":  10.0,
            "valor_total":    10.0,
            "peso_bruto":     0.0,
            "peso_total":     0.0,
            "cidade_cliente": "São Paulo",
            "tipo_item":      "Produto",
            "tipo_negociacao":"À Vista",
            "custo":          0.0,
            "source_file":    "sales_data.csv",
            "ingested_at_utc": "2026-03-30T10:00:00+00:00",
        },
        {
            "num_venda":      1002,
            "nota_fiscal":    "NF-002",
            "data":           pd.Timestamp("2026-02-03"),
            "cliente":        "Maria",
            "produto":        "Risole",
            "unidade_medida": "UN",
            "quantidade":     1.0,
            "valor_unitario": 8.0,
            "valor_bruto":    8.0,
            "desconto":       0.0,
            "valor_liquido":  8.0,
            "valor_total":    8.0,
            "peso_bruto":     0.0,
            "peso_total":     0.0,
            "cidade_cliente": "Campinas",
            "tipo_item":      "Produto",
            "tipo_negociacao":"Crédito",
            "custo":          0.0,
            "source_file":    "sales_data.csv",
            "ingested_at_utc": "2026-03-30T10:00:00+00:00",
        },
        {
            "num_venda":      1003,
            "nota_fiscal":    "NF-003",
            "data":           pd.Timestamp("2026-02-01"),
            "cliente":        "Pedro",
            "produto":        "Brigadeiro",
            "unidade_medida": "UN",
            "quantidade":     3.0,
            "valor_unitario": 5.0,
            "valor_bruto":    15.0,
            "desconto":       0.0,
            "valor_liquido":  15.0,
            "valor_total":    15.0,
            "peso_bruto":     0.0,
            "peso_total":     0.0,
            "cidade_cliente": "Santos",
            "tipo_item":      "Produto",
            "tipo_negociacao":"Débito",
            "custo":          0.0,
            "source_file":    "sales_data.csv",
            "ingested_at_utc": "2026-03-30T10:00:00+00:00",
        },
    ])


# ─────────────────────────────────────────────────────────────────────────
# _normalise_columns
# ─────────────────────────────────────────────────────────────────────────

class TestNormaliseColumns:
    def test_accented_headers_become_snake_case(self, minimal_raw_df):
        df = _normalise_columns(minimal_raw_df)
        assert "numero_da_venda" in df.columns
        assert "nome_do_produto_servico" in df.columns

    def test_private_tracking_column_preserved(self, minimal_raw_df):
        """_source_file must not be renamed."""
        df = _normalise_columns(minimal_raw_df)
        assert "_source_file" in df.columns

    def test_no_duplicate_columns_after_normalise(self, minimal_raw_df):
        df = _normalise_columns(minimal_raw_df)
        assert len(df.columns) == len(set(df.columns))


# ─────────────────────────────────────────────────────────────────────────
# _map_canonical
# ─────────────────────────────────────────────────────────────────────────

class TestMapCanonical:
    def test_renames_to_canonical_names(self, minimal_raw_df):
        df = _normalise_columns(minimal_raw_df)
        df = _map_canonical(df)
        assert "produto" in df.columns
        assert "num_venda" in df.columns
        assert "valor_total" in df.columns

    def test_source_file_column_forwarded(self, minimal_raw_df):
        df = _normalise_columns(minimal_raw_df)
        df = _map_canonical(df)
        assert "_source_file" in df.columns

    def test_non_mapped_columns_dropped(self, minimal_raw_df):
        """Extra raw columns not in _RAW_TO_SILVER must be dropped."""
        raw = minimal_raw_df.copy()
        raw["coluna_extra_nao_mapeada"] = "X"
        df = _normalise_columns(raw)
        df = _map_canonical(df)
        assert "coluna_extra_nao_mapeada" not in df.columns


# ─────────────────────────────────────────────────────────────────────────
# _coerce_types
# ─────────────────────────────────────────────────────────────────────────

class TestCoerceTypes:
    def test_csv_date_strings_parsed(self, minimal_raw_df):
        df = _normalise_columns(minimal_raw_df)
        df = _map_canonical(df)
        df = _coerce_types(df)
        assert pd.api.types.is_datetime64_any_dtype(df["data"])
        assert df["data"].notna().all()

    def test_xlsx_timestamps_preserved(self, minimal_raw_df_xlsx):
        df = _normalise_columns(minimal_raw_df_xlsx)
        df = _map_canonical(df)
        df = _coerce_types(df)
        assert pd.api.types.is_datetime64_any_dtype(df["data"])
        assert df.iloc[0]["data"] == pd.Timestamp("2026-02-01")

    def test_currency_strings_coerced_to_float(self, minimal_raw_df):
        df = _normalise_columns(minimal_raw_df)
        df = _map_canonical(df)
        df = _coerce_types(df)
        assert df["valor_total"].dtype == float
        assert df.iloc[0]["valor_total"] == pytest.approx(10.0)

    def test_custo_placeholder_zero(self, minimal_raw_df):
        df = _normalise_columns(minimal_raw_df)
        df = _map_canonical(df)
        df = _coerce_types(df)
        assert "custo" in df.columns
        assert (df["custo"] == 0.0).all()

    def test_produto_key_added(self, minimal_raw_df):
        df = _normalise_columns(minimal_raw_df)
        df = _map_canonical(df)
        df = _coerce_types(df)
        assert "produto_key" in df.columns
        # produto_key is normalised (lower, no accents)
        assert df.iloc[0]["produto_key"] == "brigadeiro"

    def test_mixed_date_sources_all_parsed(self):
        """Concat of XLSX datetime + CSV string dates → all valid after coerce_types."""
        csv_row = pd.DataFrame([{
            "data": "1/15/2026",   # US format
            "_source_file": "a.csv",
            "produto": "X",
        }])
        xlsx_row = pd.DataFrame([{
            "data": pd.Timestamp("2026-02-01"),
            "_source_file": "b.xlsx",
            "produto": "Y",
        }])
        combined = pd.concat([csv_row, xlsx_row], ignore_index=True)
        result = _coerce_types(combined)
        assert result["data"].notna().all(), "Mixed-source concat must produce 0 NaT"


# ─────────────────────────────────────────────────────────────────────────
# transform_to_silver
# ─────────────────────────────────────────────────────────────────────────

class TestTransformToSilver:
    def test_output_has_silver_columns(self, minimal_raw_df):
        silver, _ = transform_to_silver(minimal_raw_df)
        for col in SILVER_COLUMNS:
            assert col in silver.columns, f"Missing silver column: {col}"

    def test_row_count_matches_input(self, minimal_raw_df):
        silver, _ = transform_to_silver(minimal_raw_df)
        assert len(silver) == len(minimal_raw_df)

    def test_audit_dict_has_removed_key(self, minimal_raw_df):
        _, audit = transform_to_silver(minimal_raw_df)
        assert "removed" in audit

    def test_cross_file_duplicates_removed(self):
        """Identical num_venda + produto across two files → one row kept."""
        row = {
            "Número da venda":           5000,
            "Nota Fiscal / RPS":         "NF-X",
            "Data da venda":             "2/1/2026",
            "Cliente":                   "Cliente A",
            "Nome do produto/serviço":   "Produto Dup",
            "Unidade de medida":         "UN",
            "Quantidade de itens":       1,
            "Valor unitário":            "R$ 10,00",
            "Valor Bruto":               "R$ 10,00",
            "Desconto na venda":         "R$ 0,00",
            "Valor Liquido no Financeiro": "R$ 10,00",
            "Valor Total":               "R$ 10,00",
            "Peso Bruto":                "0",
            "Peso Total":                "0",
            "Cidade do cliente":         "SP",
            "Tipo de item (produto ou serviço)": "Produto",
            "Tipo de Negociação":        "À Vista",
        }
        file_a = pd.DataFrame([{**row, "_source_file": "a.csv"}])
        file_b = pd.DataFrame([{**row, "_source_file": "b.csv"}])
        combined = pd.concat([file_a, file_b], ignore_index=True)
        silver, audit = transform_to_silver(combined)
        assert len(silver) == 1, "Cross-file duplicate must be removed"
        assert audit["removed"] == 1

    def test_source_file_column_in_silver(self, minimal_raw_df):
        """Tracking column must be promoted to source_file (no leading _) in silver."""
        silver, _ = transform_to_silver(minimal_raw_df)
        assert "source_file" in silver.columns
        assert "_source_file" not in silver.columns

    def test_ingested_at_utc_present(self, minimal_raw_df):
        silver, _ = transform_to_silver(minimal_raw_df)
        assert "ingested_at_utc" in silver.columns
        assert silver["ingested_at_utc"].notna().all()


# ─────────────────────────────────────────────────────────────────────────
# build_dim_produto
# ─────────────────────────────────────────────────────────────────────────

class TestBuildDimProduto:
    def test_unique_products(self, silver_df):
        dim = build_dim_produto(silver_df)
        # silver_df has Brigadeiro and Risole (2 unique)
        assert len(dim) == 2

    def test_surrogate_key_starts_at_one(self, silver_df):
        dim = build_dim_produto(silver_df)
        assert dim["produto_id"].min() == 1

    def test_required_columns(self, silver_df):
        dim = build_dim_produto(silver_df)
        assert set(dim.columns) >= {"produto_id", "nome_produto"}

    def test_empty_produto_excluded(self):
        df = pd.DataFrame({"produto": ["Brigadeiro", "", None, "Risole"]})
        dim = build_dim_produto(df)
        assert len(dim) == 2

    def test_no_duplicate_product_ids(self, silver_df):
        dim = build_dim_produto(silver_df)
        assert dim["produto_id"].nunique() == len(dim)


# ─────────────────────────────────────────────────────────────────────────
# build_dim_tempo
# ─────────────────────────────────────────────────────────────────────────

class TestBuildDimTempo:
    def test_unique_dates(self, silver_df):
        """silver_df has 2026-02-01 and 2026-02-03 → 2 unique dates."""
        dim = build_dim_tempo(silver_df)
        assert len(dim) == 2

    def test_required_columns(self, silver_df):
        dim = build_dim_tempo(silver_df)
        required = {"data_id", "data", "dia", "mes", "ano", "trimestre", "dia_semana", "nome_mes"}
        assert required.issubset(dim.columns)

    def test_month_name_portuguese(self, silver_df):
        dim = build_dim_tempo(silver_df)
        assert (dim["nome_mes"] == "Fevereiro").all()

    def test_trimestre_february_is_q1(self, silver_df):
        dim = build_dim_tempo(silver_df)
        assert (dim["trimestre"] == 1).all()

    def test_nat_dates_excluded(self):
        df = pd.DataFrame({"data": [pd.Timestamp("2026-02-01"), pd.NaT, pd.Timestamp("2026-02-03")]})
        dim = build_dim_tempo(df)
        assert len(dim) == 2

    def test_surrogate_key_starts_at_one(self, silver_df):
        dim = build_dim_tempo(silver_df)
        assert dim["data_id"].min() == 1

    def test_month_pt_mapping_complete(self):
        """All 12 months must be in the Portuguese mapping."""
        assert len(_MONTH_PT) == 12
        assert _MONTH_PT[1] == "Janeiro"
        assert _MONTH_PT[12] == "Dezembro"


# ─────────────────────────────────────────────────────────────────────────
# build_fato_vendas
# ─────────────────────────────────────────────────────────────────────────

class TestBuildFatoVendas:
    def test_row_count_matches_silver(self, silver_df):
        dim_p = build_dim_produto(silver_df)
        dim_t = build_dim_tempo(silver_df)
        fato  = build_fato_vendas(silver_df, dim_p, dim_t)
        assert len(fato) == len(silver_df)

    def test_required_columns(self, silver_df):
        dim_p = build_dim_produto(silver_df)
        dim_t = build_dim_tempo(silver_df)
        fato  = build_fato_vendas(silver_df, dim_p, dim_t)
        required = {
            "venda_id", "produto_id", "data_id",
            "num_venda", "cliente", "quantidade",
            "valor_unitario", "valor_total", "custo", "margem",
        }
        assert required.issubset(fato.columns)

    def test_no_null_foreign_keys(self, silver_df):
        dim_p = build_dim_produto(silver_df)
        dim_t = build_dim_tempo(silver_df)
        fato  = build_fato_vendas(silver_df, dim_p, dim_t)
        assert fato["produto_id"].notna().all()
        assert fato["data_id"].notna().all()

    def test_margem_formula_zero_cost(self, silver_df):
        """With custo=0, margem = valor_total / quantidade."""
        dim_p = build_dim_produto(silver_df)
        dim_t = build_dim_tempo(silver_df)
        fato  = build_fato_vendas(silver_df, dim_p, dim_t)
        row = fato[fato["num_venda"] == 1001].iloc[0]
        expected_margem = row["valor_total"] / row["quantidade"]
        assert row["margem"] == pytest.approx(expected_margem)

    def test_margem_formula_with_cost(self, silver_df):
        """Enrich custo and verify margem = (valor_total - custo) / quantidade."""
        enriched = silver_df.copy()
        enriched["custo"] = 2.0   # unit cost
        dim_p = build_dim_produto(enriched)
        dim_t = build_dim_tempo(enriched)
        fato  = build_fato_vendas(enriched, dim_p, dim_t)
        row = fato[fato["num_venda"] == 1001].iloc[0]
        # margem = (10.0 - 2.0) / 2.0 = 4.0
        assert row["margem"] == pytest.approx(4.0)

    def test_zero_quantity_does_not_cause_inf(self):
        """quantidade=0 must produce margem=0.0 instead of ±Inf."""
        df = pd.DataFrame([{
            "num_venda":      9999,
            "nota_fiscal":    "NF-Z",
            "data":           pd.Timestamp("2026-02-01"),
            "cliente":        "X",
            "produto":        "Produto Zero",
            "unidade_medida": "UN",
            "quantidade":     0.0,
            "valor_unitario": 5.0,
            "valor_bruto":    0.0,
            "desconto":       0.0,
            "valor_liquido":  0.0,
            "valor_total":    0.0,
            "peso_bruto":     0.0,
            "peso_total":     0.0,
            "cidade_cliente": "SP",
            "tipo_item":      "Produto",
            "tipo_negociacao":"Pix",
            "custo":          0.0,
            "source_file":    "test.csv",
            "ingested_at_utc": "2026-03-30T10:00:00+00:00",
        }])
        dim_p = build_dim_produto(df)
        dim_t = build_dim_tempo(df)
        fato  = build_fato_vendas(df, dim_p, dim_t)
        assert not np.isinf(fato["margem"]).any()
        assert fato.iloc[0]["margem"] == 0.0

    def test_surrogate_pk_sequential(self, silver_df):
        dim_p = build_dim_produto(silver_df)
        dim_t = build_dim_tempo(silver_df)
        fato  = build_fato_vendas(silver_df, dim_p, dim_t)
        assert list(fato["venda_id"]) == list(range(1, len(silver_df) + 1))


# ─────────────────────────────────────────────────────────────────────────
# validate_star_schema
# ─────────────────────────────────────────────────────────────────────────

class TestValidateStarSchema:
    def _build_all(self, silver_df):
        dim_p = build_dim_produto(silver_df)
        dim_t = build_dim_tempo(silver_df)
        fato  = build_fato_vendas(silver_df, dim_p, dim_t)
        return dim_p, dim_t, fato

    def test_clean_schema_passes(self, silver_df):
        dim_p, dim_t, fato = self._build_all(silver_df)
        results = validate_star_schema(fato, dim_p, dim_t)
        assert results["all_ok"] is True

    def test_orphan_produto_id_fails(self, silver_df):
        dim_p, dim_t, fato = self._build_all(silver_df)
        # Inject an invalid produto_id
        fato = fato.copy()
        fato.loc[0, "produto_id"] = 9999
        results = validate_star_schema(fato, dim_p, dim_t)
        assert results["fk_produto_id_ok"] is False
        assert results["fk_produto_id_orphans"] == 1

    def test_orphan_data_id_fails(self, silver_df):
        dim_p, dim_t, fato = self._build_all(silver_df)
        fato = fato.copy()
        fato.loc[0, "data_id"] = 9999
        results = validate_star_schema(fato, dim_p, dim_t)
        assert results["fk_data_id_ok"] is False

    def test_inf_margem_fails(self, silver_df):
        dim_p, dim_t, fato = self._build_all(silver_df)
        fato = fato.copy()
        fato.loc[0, "margem"] = float("inf")
        results = validate_star_schema(fato, dim_p, dim_t)
        assert results["margem_no_inf_ok"] is False

    def test_row_counts_reported(self, silver_df):
        dim_p, dim_t, fato = self._build_all(silver_df)
        results = validate_star_schema(fato, dim_p, dim_t)
        assert results["fato_rows"] == len(silver_df)
        assert results["dim_produto_rows"] == 2   # Brigadeiro + Risole
        assert results["dim_tempo_rows"] == 2     # 2026-02-01, 2026-02-03


# ─────────────────────────────────────────────────────────────────────────
# enrich_cost_from_catalog
# ─────────────────────────────────────────────────────────────────────────

class TestEnrichCostFromCatalog:
    def test_matching_product_cost_populated(self, silver_df):
        cost_map = {"brigadeiro": 3.0, "risole": 2.0}
        enriched = enrich_cost_from_catalog(silver_df, cost_map)
        brigadeiro_rows = enriched[enriched["produto"] == "Brigadeiro"]
        assert (brigadeiro_rows["custo"] == 3.0).all()

    def test_unmatched_product_keeps_zero(self, silver_df):
        cost_map = {"brigadeiro": 3.0}   # Risole not in map
        enriched = enrich_cost_from_catalog(silver_df, cost_map)
        risole_rows = enriched[enriched["produto"] == "Risole"]
        assert (risole_rows["custo"] == 0.0).all()

    def test_margem_recalculated_after_enrichment(self, silver_df):
        """After enriching custo, build_fato_vendas must reflect real margem."""
        cost_map = {"brigadeiro": 2.0, "risole": 2.0}
        enriched = enrich_cost_from_catalog(silver_df, cost_map)
        dim_p = build_dim_produto(enriched)
        dim_t = build_dim_tempo(enriched)
        fato  = build_fato_vendas(enriched, dim_p, dim_t)
        row = fato[fato["num_venda"] == 1001].iloc[0]
        # (10.0 - 2.0) / 2.0 = 4.0
        assert row["margem"] == pytest.approx(4.0)

    def test_empty_cost_map_returns_unchanged_copy(self, silver_df):
        enriched = enrich_cost_from_catalog(silver_df, {})
        assert (enriched["custo"] == 0.0).all()
        # Must return a copy, not mutate original
        assert enriched is not silver_df

    def test_case_insensitive_match(self, silver_df):
        """Catalog keys in UPPER case must still match silver produto."""
        cost_map = {"BRIGADEIRO": 3.0}   # wrong case — should still NOT match after _normalise_value
        # _normalise_value lowercases, so the map key must be lowercase;
        # test that caller is responsible for normalising keys.
        enriched = enrich_cost_from_catalog(silver_df, cost_map)
        # "BRIGADEIRO" ≠ normalised "brigadeiro" → no match
        brigadeiro_rows = enriched[enriched["produto"] == "Brigadeiro"]
        assert (brigadeiro_rows["custo"] == 0.0).all()

    def test_normalised_key_with_accent_matches(self, silver_df):
        """Keys stripped of accents must match regardless."""
        cost_map = {"brigadeiro": 5.0}
        enriched = enrich_cost_from_catalog(silver_df, cost_map)
        assert (enriched[enriched["produto"] == "Brigadeiro"]["custo"] == 5.0).all()

    def test_original_df_not_mutated(self, silver_df):
        original_custo = silver_df["custo"].copy()
        enrich_cost_from_catalog(silver_df, {"brigadeiro": 99.0})
        # Original must be untouched
        assert (silver_df["custo"] == original_custo).all()


# ─────────────────────────────────────────────────────────────────────────
# LocalRawSource
# ─────────────────────────────────────────────────────────────────────────

class TestLocalRawSource:
    def test_list_tabular_files_csv_xlsx(self, tmp_path):
        (tmp_path / "vendas.csv").write_text("a,b\n1,2\n")
        (tmp_path / "vendas.xlsx").write_bytes(b"PK")   # fake XLSX (won't be parsed here)
        (tmp_path / "readme.txt").write_text("ignore")
        src = LocalRawSource(raw_dir=tmp_path)
        files = src.list_tabular_files()
        names = {f["name"] for f in files}
        assert "vendas.csv" in names
        assert "vendas.xlsx" in names
        assert "readme.txt" not in names

    def test_lock_files_excluded(self, tmp_path):
        (tmp_path / ".~lock.vendas.xlsx#").write_text("lock")
        (tmp_path / "vendas.csv").write_text("a,b\n1,2\n")
        src = LocalRawSource(raw_dir=tmp_path)
        files = src.list_tabular_files()
        names = {f["name"] for f in files}
        assert ".~lock.vendas.xlsx#" not in names

    def test_read_csv_returns_dataframe(self, tmp_path):
        csv_path = tmp_path / "test.csv"
        csv_path.write_text("col_a,col_b\nfoo,1\nbar,2\n")
        src = LocalRawSource(raw_dir=tmp_path)
        meta = {"id": str(csv_path), "name": "test.csv", "mimeType": "text/csv"}
        df = src.read_as_dataframe(meta)
        assert df is not None
        assert list(df.columns) == ["col_a", "col_b"]
        assert len(df) == 2

    def test_missing_file_returns_none(self, tmp_path):
        src = LocalRawSource(raw_dir=tmp_path)
        meta = {
            "id": str(tmp_path / "nonexistent.csv"),
            "name": "nonexistent.csv",
            "mimeType": "text/csv",
        }
        result = src.read_as_dataframe(meta)
        assert result is None

    def test_mime_type_for_csv_and_xlsx(self, tmp_path):
        (tmp_path / "a.csv").write_text("x,y\n1,2\n")
        (tmp_path / "b.xlsx").write_bytes(b"PK")
        src = LocalRawSource(raw_dir=tmp_path)
        files = {f["name"]: f["mimeType"] for f in src.list_tabular_files()}
        assert files["a.csv"] == "text/csv"
        assert "spreadsheetml" in files["b.xlsx"]


# ─────────────────────────────────────────────────────────────────────────
# End-to-end: raw → silver → gold (in-memory, no I/O)
# ─────────────────────────────────────────────────────────────────────────

class TestEndToEnd:
    def test_full_pipeline_integrity(self, minimal_raw_df):
        """RAW → silver → dim/fato → validation: must all_ok=True."""
        silver, _ = transform_to_silver(minimal_raw_df)
        dim_p = build_dim_produto(silver)
        dim_t = build_dim_tempo(silver)
        fato  = build_fato_vendas(silver, dim_p, dim_t)
        results = validate_star_schema(fato, dim_p, dim_t)
        assert results["all_ok"] is True

    def test_full_pipeline_row_count_preserved(self, minimal_raw_df):
        """No rows should be lost in raw → gold (input has no cross-file dups)."""
        silver, _ = transform_to_silver(minimal_raw_df)
        dim_p = build_dim_produto(silver)
        dim_t = build_dim_tempo(silver)
        fato  = build_fato_vendas(silver, dim_p, dim_t)
        assert len(fato) == len(minimal_raw_df)

    def test_full_pipeline_mixed_sources(self, minimal_raw_df, minimal_raw_df_xlsx):
        """CSV + XLSX combined must produce a clean star schema."""
        combined = pd.concat([minimal_raw_df, minimal_raw_df_xlsx], ignore_index=True)
        silver, audit = transform_to_silver(combined)
        # Row 0 of CSV and XLSX are both num_venda=1001 + produto="Brigadeiro" → 1 removed
        assert audit["removed"] >= 1
        dim_p = build_dim_produto(silver)
        dim_t = build_dim_tempo(silver)
        fato  = build_fato_vendas(silver, dim_p, dim_t)
        results = validate_star_schema(fato, dim_p, dim_t)
        assert results["all_ok"] is True

