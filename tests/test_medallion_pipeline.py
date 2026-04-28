"""Unit tests for scripts/medallion_pipeline.py.

All tests run in-memory — no real files, no Google APIs.
Fixtures build minimal DataFrames that exercise edge cases:
  - accented / mixed-case headers
  - dates from XLSX (already datetime64) and CSV (string "mm/dd/yyyy")
  - numeric columns with R$ currency strings
  - cross-file duplicate rows
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# ── Ensure project root on sys.path ───────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.medallion_pipeline import (  # noqa: E402
    LocalRawSource,
    MedallionPipeline,
    _coerce_types,
    _parse_args,
    _map_canonical,
    _normalise_columns,
    build_agg_vendas_canal,
    build_agg_vendas_dia,
    build_agg_vendas_produto,
    build_agg_vendas_tempo,
    build_dim_canal,
    build_dim_produto,
    build_dim_tempo,
    build_fato_vendas,
    enrich_cost_from_catalog,
    run_data_quality_validation,
    validate_gold_quality,
    validate_raw_input_quality,
    validate_silver_quality,
    transform_to_silver,
    validate_star_schema,
    SILVER_COLUMNS,
    _MONTH_PT,
)
from src.domain.sales_analysis_service import _deduplicate_with_audit  # noqa: E402
from src.infrastructure.data_quality import DataQualityValidator  # noqa: E402


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
        """Without reliable transaction key, rows are kept and flagged as suspected."""
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
        assert len(silver) == 2
        assert audit["removed"] == 0
        assert audit["suspected_duplicates"]["count"] == 2

    def test_same_sale_number_across_months_is_not_deduplicated(self):
        """Rows from Feb and Mar with same num_venda/produto must both be kept."""
        feb = pd.DataFrame([{
            "Número da venda": 7000,
            "Nota Fiscal / RPS": "NF-7000",
            "Data da venda": "2/28/2026",
            "Cliente": "Cliente X",
            "Nome do produto/serviço": "Brigadeiro",
            "Unidade de medida": "UN",
            "Quantidade de itens": 1,
            "Valor unitário": "R$ 10,00",
            "Valor Bruto": "R$ 10,00",
            "Desconto na venda": "R$ 0,00",
            "Valor Liquido no Financeiro": "R$ 10,00",
            "Valor Total": "R$ 10,00",
            "Peso Bruto": "0",
            "Peso Total": "0",
            "Cidade do cliente": "SP",
            "Tipo de item (produto ou serviço)": "Produto",
            "Tipo de Negociação": "Pix",
            "_source_file": "sales_2026_02.csv",
        }])
        mar = feb.copy()
        mar["Data da venda"] = "3/01/2026"
        mar["_source_file"] = "sales_2026_03.csv"

        combined = pd.concat([feb, mar], ignore_index=True)
        silver, audit = transform_to_silver(combined)

        months = pd.to_datetime(silver["data"], errors="coerce").dt.to_period("M").astype(str)
        assert len(silver) == 2
        assert set(months.tolist()) == {"2026-02", "2026-03"}
        assert audit["removed"] == 0

    def test_source_file_column_in_silver(self, minimal_raw_df):
        """Tracking column must be promoted to source_file (no leading _) in silver."""
        silver, _ = transform_to_silver(minimal_raw_df)
        assert "source_file" in silver.columns
        assert "arquivo_origem" in silver.columns
        assert "_source_file" not in silver.columns

    def test_ingested_at_utc_present(self, minimal_raw_df):
        silver, _ = transform_to_silver(minimal_raw_df)
        assert "ingested_at_utc" in silver.columns
        assert "data_carga" in silver.columns
        assert "mes_referencia" in silver.columns
        assert silver["ingested_at_utc"].notna().all()


class TestTransactionKeyDedupRules:
    def test_ifood_same_order_line_across_files_is_preserved(self):
        df = pd.DataFrame([
            {
                "_source_file": "ifood_2026_02.csv",
                "plataforma": "ifood",
                "codigo_venda": "IFOOD-1001",
                "identificador_item": "1",
                "num_venda": "A1001",
                "produto_key": "coxinha",
                "data": pd.Timestamp("2026-02-10"),
            },
            {
                "_source_file": "ifood_2026_02_reprocess.csv",
                "plataforma": "ifood",
                "codigo_venda": "IFOOD-1001",
                "identificador_item": "1",
                "num_venda": "A1001",
                "produto_key": "coxinha",
                "data": pd.Timestamp("2026-02-10"),
            },
        ])

        deduped, audit = _deduplicate_with_audit(df)

        assert len(deduped) == 2
        assert audit["removed"] == 0
        assert audit["transaction_key_dedup"]["applied"] is True
        assert audit["transaction_key_dedup"]["key_columns"] == [
            "plataforma", "codigo_venda", "identificador_item"
        ]

    def test_ifood_same_order_line_repeated_in_same_file_is_audited_without_removal(self):
        df = pd.DataFrame([
            {
                "_source_file": "ifood_2026_02.csv",
                "plataforma": "ifood",
                "codigo_venda": "IFOOD-1001",
                "identificador_item": "1",
                "num_venda": "A1001",
                "produto_key": "coxinha",
                "data": pd.Timestamp("2026-02-10"),
            },
            {
                "_source_file": "ifood_2026_02.csv",
                "plataforma": "ifood",
                "codigo_venda": "IFOOD-1001",
                "identificador_item": "1",
                "num_venda": "A1001",
                "produto_key": "coxinha",
                "data": pd.Timestamp("2026-02-10"),
            },
        ])

        deduped, audit = _deduplicate_with_audit(df)
        assert len(deduped) == 2
        assert audit["removed"] == 0
        assert audit["detected_exact_by_source_file"] == {"ifood_2026_02.csv": 1}

    def test_same_order_multiple_items_without_item_id_are_preserved(self):
        """One order can have multiple product lines; do not dedup by order key alone."""
        df = pd.DataFrame([
            {
                "_source_file": "ifood_2026_02.csv",
                "plataforma": "ifood",
                "codigo_venda": "IFOOD-7412",
                "num_venda": "7412",
                "produto_key": "esfiha_frango_reque",
                "valor_total": 18.0,
                "data": pd.Timestamp("2026-02-10"),
            },
            {
                "_source_file": "ifood_2026_02.csv",
                "plataforma": "ifood",
                "codigo_venda": "IFOOD-7412",
                "num_venda": "7412",
                "produto_key": "coxinha_frango",
                "valor_total": 18.0,
                "data": pd.Timestamp("2026-02-10"),
            },
        ])

        deduped, audit = _deduplicate_with_audit(df)

        assert len(deduped) == 2
        assert audit["removed"] == 0
        assert audit["transaction_key_dedup"]["applied"] is False

        df = pd.DataFrame([
            {
                "_source_file": "sales_2026_02.csv",
                "num_venda": "X-1",
                "produto_key": "brigadeiro",
                "valor_total": 10.0,
                "data": pd.Timestamp("2026-02-01"),
            },
            {
                "_source_file": "sales_2026_03.csv",
                "num_venda": "X-1",
                "produto_key": "brigadeiro",
                "valor_total": 10.0,
                "data": pd.Timestamp("2026-03-01"),
            },
        ])

        deduped, audit = _deduplicate_with_audit(df)

        assert len(deduped) == 2
        assert audit["removed"] == 0

    def test_missing_codigo_venda_marks_suspected_without_removal(self):
        df = pd.DataFrame([
            {
                "_source_file": "sales_a.csv",
                "num_venda": "LEG-200",
                "produto_key": "risole",
                "data": pd.Timestamp("2026-02-03"),
            },
            {
                "_source_file": "sales_b.csv",
                "num_venda": "LEG-200",
                "produto_key": "risole",
                "data": pd.Timestamp("2026-02-03"),
            },
        ])

        deduped, audit = _deduplicate_with_audit(df)

        assert len(deduped) == 2
        assert audit["removed"] == 0
        assert audit["transaction_key_dedup"]["applied"] is False
        assert audit["suspected_duplicates"]["count"] == 2


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

    def test_read_csv_semicolon_with_decimal_comma(self, tmp_path):
        csv_path = tmp_path / "sales_jan.csv"
        csv_path.write_text(
            "Número da venda;Data da venda;Nome do produto/serviço;Quantidade de itens;Valor Total\n"
            "1001;02/01/2026;Brigadeiro;2;18,00\n",
            encoding="utf-8",
        )
        src = LocalRawSource(raw_dir=tmp_path)
        meta = {"id": str(csv_path), "name": "sales_jan.csv", "mimeType": "text/csv"}
        df = src.read_as_dataframe(meta)
        assert df is not None
        assert df.shape[1] == 5
        assert "Valor Total" in df.columns

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
class TestMedallionPipelineFacade:
    def test_run_materializes_silver_and_gold_and_returns_counts(self, tmp_path, monkeypatch):
        raw_dir = tmp_path / "raw"
        silver_dir = tmp_path / "silver"
        gold_dir = tmp_path / "gold"
        raw_dir.mkdir()

        monkeypatch.setattr("scripts.medallion_pipeline.update_parquet_in_drive", lambda *_args, **_kwargs: False)

        (raw_dir / "sales_2026_01.csv").write_text(
            "Número da venda;Nota Fiscal / RPS;Data da venda;Cliente;Nome do produto/serviço;"
            "Unidade de medida;Quantidade de itens;Valor unitário;Valor Bruto;Desconto na venda;"
            "Valor Liquido no Financeiro;Valor Total;Peso Bruto;Peso Total;Cidade do cliente;"
            "Tipo de item (produto ou serviço);Tipo de Negociação\n"
            "1001;NF-001;02/01/2026;João;Brigadeiro;UN;2;5,00;10,00;0,00;10,00;10,00;0;0;São Paulo;Produto;IFOOD\n",
            encoding="utf-8",
        )

        result = MedallionPipeline(
            source=LocalRawSource(raw_dir=raw_dir),
            silver_dir=silver_dir,
            gold_dir=gold_dir,
        ).run()

        assert result["bronze_rows"] == 1
        assert result["silver_rows"] == 1
        assert result["quarantine_rows"] == 0
        assert result["gold_rows"] == 1
        assert result["gold_uploaded_files"] == 0

    def test_run_uses_existing_layers_when_raw_is_empty(self, tmp_path, monkeypatch):
        raw_dir = tmp_path / "raw"
        silver_dir = tmp_path / "silver"
        gold_dir = tmp_path / "gold"
        raw_dir.mkdir()
        silver_dir.mkdir()
        gold_dir.mkdir()

        silver_existing = pd.DataFrame(
            {
                "num_venda": [1001],
                "data": [pd.Timestamp("2026-01-02")],
                "produto": ["Brigadeiro"],
                "quantidade": [2.0],
                "valor_total": [10.0],
            }
        )

        gold_existing = pd.DataFrame(
            {
                "venda_id": [1],
                "produto_id": [1],
                "data_id": [1],
                "quantidade": [2.0],
                "faturamento_bruto": [10.0],
                "faturamento_liquido": [10.0],
                "custo": [0.0],
                "lucro_total": [10.0],
                "margem": [5.0],
                "margem_percentual": [100.0],
                "canal": ["IFOOD"],
            }
        )

        def _fake_load_parquet_from_drive(file_name: str) -> pd.DataFrame:
            if file_name == "sales_silver.parquet":
                return silver_existing
            if file_name == "fato_vendas.parquet":
                return gold_existing
            return pd.DataFrame()

        monkeypatch.setattr("scripts.medallion_pipeline.load_parquet_from_drive", _fake_load_parquet_from_drive)

        result = MedallionPipeline(
            source=LocalRawSource(raw_dir=raw_dir),
            silver_dir=silver_dir,
            gold_dir=gold_dir,
        ).run()

        assert result["used_existing_layers"] is True
        assert result["silver_rows"] == 1
        assert result["gold_rows"] == 1



class TestEndToEnd:
    def test_full_pipeline_integrity(self, minimal_raw_df):
        """RAW → silver → dim/fato → validation: must all_ok=True."""
        silver, _ = transform_to_silver(minimal_raw_df)
        dim_p = build_dim_produto(silver)
        dim_t = build_dim_tempo(silver)
        fato  = build_fato_vendas(silver, dim_p, dim_t)
        results = validate_star_schema(fato, dim_p, dim_t)
        assert results["all_ok"] is True

    def test_two_monthly_files_all_transactions_are_preserved(self):
        jan = pd.DataFrame([
            {
                "Número da venda": 101,
                "Nota Fiscal / RPS": "NF-101",
                "Data da venda": "02/01/2026",
                "Cliente": "A",
                "Nome do produto/serviço": "Brigadeiro",
                "Unidade de medida": "UN",
                "Quantidade de itens": 1,
                "Valor unitário": "R$ 10,00",
                "Valor Bruto": "R$ 10,00",
                "Desconto na venda": "R$ 0,00",
                "Valor Liquido no Financeiro": "R$ 10,00",
                "Valor Total": "R$ 10,00",
                "Peso Bruto": "0",
                "Peso Total": "0",
                "Cidade do cliente": "SP",
                "Tipo de item (produto ou serviço)": "Produto",
                "Tipo de Negociação": "Pix",
                "_source_file": "sales_2026_01.csv",
            }
        ])
        feb = pd.DataFrame([
            {
                "Número da venda": 102,
                "Nota Fiscal / RPS": "NF-102",
                "Data da venda": "2/21/2026",
                "Cliente": "B",
                "Nome do produto/serviço": "Risole",
                "Unidade de medida": "UN",
                "Quantidade de itens": 2,
                "Valor unitário": "R$ 8,00",
                "Valor Bruto": "R$ 16,00",
                "Desconto na venda": "R$ 0,00",
                "Valor Liquido no Financeiro": "R$ 16,00",
                "Valor Total": "R$ 16,00",
                "Peso Bruto": "0",
                "Peso Total": "0",
                "Cidade do cliente": "SP",
                "Tipo de item (produto ou serviço)": "Produto",
                "Tipo de Negociação": "Pix",
                "_source_file": "sales_2026_02.csv",
            }
        ])
        combined = pd.concat([jan, feb], ignore_index=True)

        silver, audit = transform_to_silver(combined)
        dim_p = build_dim_produto(silver)
        dim_t = build_dim_tempo(silver)
        fato = build_fato_vendas(silver, dim_p, dim_t)

        assert audit["removed"] == 0
        assert len(silver) == 2
        assert len(fato) == 2
        assert set(fato["mes_referencia"].tolist()) == {"2026-01", "2026-02"}
        parsed_months = set(pd.to_datetime(silver["data"], errors="coerce").dt.to_period("M").astype(str).tolist())
        assert parsed_months == {"2026-01", "2026-02"}


# ─────────────────────────────────────────────────────────────────────────
# Data Quality Validation (gold layer)
# ─────────────────────────────────────────────────────────────────────────

class TestDataQualityValidator:
    def _build_gold_tables(self, silver_df):
        dim_p = build_dim_produto(silver_df)
        dim_t = build_dim_tempo(silver_df)
        fato = build_fato_vendas(silver_df, dim_p, dim_t)
        return dim_p, dim_t, fato

    def test_validate_all_passes_for_clean_gold_tables(self, silver_df):
        dim_p, dim_t, fato = self._build_gold_tables(silver_df)
        validator = DataQualityValidator(verbose=False)
        results = validator.validate_all(dim_p, dim_t, fato)
        assert results == {
            "dim_produto": True,
            "dim_tempo": True,
            "fato_vendas": True,
        }

    def test_validate_fato_vendas_fails_for_orphan_fk(self, silver_df):
        dim_p, dim_t, fato = self._build_gold_tables(silver_df)
        fato_bad = fato.copy()
        fato_bad.loc[0, "produto_id"] = 999999
        validator = DataQualityValidator(verbose=False)
        assert validator.validate_fato_vendas(fato_bad, dim_p, dim_t) is False

    def test_validation_report_contains_overall_status(self):
        report = DataQualityValidator.get_validation_report({
            "dim_produto": True,
            "dim_tempo": True,
            "fato_vendas": False,
        })
        assert "DATA QUALITY VALIDATION REPORT" in report
        assert "Overall:" in report


class TestRunDataQualityValidation:
    def test_run_data_quality_validation_returns_true(self, silver_df, monkeypatch):
        dim_p = build_dim_produto(silver_df)
        dim_t = build_dim_tempo(silver_df)
        fato = build_fato_vendas(silver_df, dim_p, dim_t)

        class StubAdapter:
            def load_gold(self, name):
                if name == "dim_produto":
                    return dim_p
                if name == "dim_tempo":
                    return dim_t
                return fato

        monkeypatch.setattr("scripts.medallion_pipeline.GoldParquetAdapter", StubAdapter)
        assert run_data_quality_validation() is True

    def test_run_data_quality_validation_returns_false_on_load_error(self, monkeypatch):
        class BrokenAdapter:
            def load_gold(self, _name):
                raise RuntimeError("boom")

        monkeypatch.setattr("scripts.medallion_pipeline.GoldParquetAdapter", BrokenAdapter)
        assert run_data_quality_validation() is False


class TestCliArgs:
    def test_parse_args_validate_flag(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["medallion_pipeline.py", "--validate"])
        args = _parse_args()
        assert args.validate is True
        assert args.silver is False
        assert args.gold is False

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
        # Without reliable transaction key, potential duplicates are flagged but kept.
        assert audit["removed"] == 0
        assert audit["suspected_duplicates"]["count"] >= 1
        dim_p = build_dim_produto(silver)
        dim_t = build_dim_tempo(silver)
        fato  = build_fato_vendas(silver, dim_p, dim_t)
        results = validate_star_schema(fato, dim_p, dim_t)
        assert results["all_ok"] is True


class TestGoldAnalyticalAggregates:
    def test_build_dim_canal_normalizes_and_deduplicates(self, silver_df):
        dim_canal = build_dim_canal(silver_df)
        assert "canal_id" in dim_canal.columns
        assert "canal" in dim_canal.columns
        assert dim_canal["canal"].nunique() == len(dim_canal)

    def test_build_gold_aggregates_produce_expected_metrics(self, silver_df):
        dim_p = build_dim_produto(silver_df)
        dim_t = build_dim_tempo(silver_df)
        dim_c = build_dim_canal(silver_df)
        fato = build_fato_vendas(silver_df, dim_p, dim_t, dim_c)

        agg_dia = build_agg_vendas_dia(fato, dim_t)
        agg_canal = build_agg_vendas_canal(fato, dim_c)
        agg_produto = build_agg_vendas_produto(fato, dim_p)
        agg_tempo = build_agg_vendas_tempo(fato, dim_t)

        assert not agg_dia.empty
        assert not agg_canal.empty
        assert not agg_produto.empty
        assert not agg_tempo.empty

        expected_total = float(fato["faturamento_liquido"].sum())
        assert float(agg_dia["faturamento_liquido"].sum()) == pytest.approx(expected_total)
        assert float(agg_canal["faturamento_liquido"].sum()) == pytest.approx(expected_total)
        assert float(agg_produto["faturamento_liquido"].sum()) == pytest.approx(expected_total)
        assert float(agg_tempo["faturamento_liquido"].sum()) == pytest.approx(expected_total)

        assert "margem_percentual" in agg_dia.columns
        assert "margem_percentual" in agg_canal.columns
        assert "margem_percentual" in agg_produto.columns
        assert "margem_percentual" in agg_tempo.columns


class TestMinimumDataQualityChecks:
    def test_validate_raw_input_quality_reports_empty_input_error(self):
        report = validate_raw_input_quality(pd.DataFrame())
        assert report["errors"]
        assert "empty" in report["errors"][0].lower()

    def test_validate_silver_quality_flags_invalid_dates_and_unknown_channel(self, silver_df):
        bad = silver_df.copy()
        bad.loc[0, "data"] = pd.NaT
        bad.loc[0, "tipo_negociacao"] = "canal_xpto"
        report = validate_silver_quality(bad)
        assert report["stats"]["invalid_dates"] >= 1
        assert report["stats"]["unrecognized_channels"] >= 1

    def test_validate_gold_quality_detects_missing_required_columns(self, silver_df):
        dim_p = build_dim_produto(silver_df)
        dim_t = build_dim_tempo(silver_df)
        dim_c = build_dim_canal(silver_df)
        fato = build_fato_vendas(silver_df, dim_p, dim_t, dim_c).drop(columns=["faturamento_liquido"])
        report = validate_gold_quality(dim_p, dim_t, dim_c, fato)
        assert report["errors"]
        assert "missing required columns" in report["errors"][0].lower()

