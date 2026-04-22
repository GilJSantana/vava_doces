"""Unit tests for src/domain/sales_analysis_service.py.

All tests run entirely in-memory — no network calls, no Drive, no Sheets.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.domain.sales_analysis_service import (
    OUTPUT_COLUMNS,
    ProductsTransformer,
    SalesFilesExtractor,
    SalesProductJoiner,
    SalesTransformer,
    _choose_date_format_for_source,
    _deduplicate,
    _deduplicate_with_audit,
    _finalise,
    _normalise_header,
    _normalise_value,
    _to_numeric,
)
from src.ports.data_source import DriveDataSource


# ---------------------------------------------------------------------------
# Text helper tests
# ---------------------------------------------------------------------------

class TestNormaliseHeader:
    def test_accented_special_chars(self):
        assert _normalise_header("Nome do produto/serviço") == "nome_do_produto_servico"

    def test_currency_brackets(self):
        assert _normalise_header("Custo Total Unitário (R$)") == "custo_total_unitario_r"

    def test_already_clean(self):
        assert _normalise_header("categoria") == "categoria"

    def test_leading_trailing_underscores_stripped(self):
        result = _normalise_header("  /Valor/  ")
        assert not result.startswith("_")
        assert not result.endswith("_")

    def test_empty_string(self):
        assert _normalise_header("") == ""

    def test_bom_prefix_is_removed(self):
        assert _normalise_header("\ufeffNúmero da venda") == "numero_da_venda"


class TestNormaliseValue:
    def test_strips_accents(self):
        assert _normalise_value("Brigadeiro Clássico") == _normalise_value("brigadeiro classico")

    def test_case_insensitive(self):
        assert _normalise_value("PIZZA") == _normalise_value("pizza")

    def test_strips_whitespace(self):
        assert _normalise_value("  Risole  ") == "risole"


class TestToNumeric:
    def test_plain_float(self):
        s = pd.Series(["18.0", "9.5"])
        result = _to_numeric(s)
        assert list(result) == [18.0, 9.5]

    def test_brazilian_format(self):
        s = pd.Series(["R$ 6,79", "R$ 1.234,56"])
        result = _to_numeric(s)
        assert abs(result.iloc[0] - 6.79) < 0.001
        assert abs(result.iloc[1] - 1234.56) < 0.001

    def test_empty_string_becomes_nan(self):
        s = pd.Series(["", "nan"])
        result = _to_numeric(s)
        assert result.isna().all()


# ---------------------------------------------------------------------------
# SalesTransformer tests
# ---------------------------------------------------------------------------

class TestSalesTransformer:
    def _make_raw_sales(self) -> pd.DataFrame:
        return pd.DataFrame([
            {
                "numero_da_venda": "5623",
                "data_da_venda": "2/1/2026",
                "nome_do_produto_servico": "BRIGADEIRO",
                "quantidade_de_itens": 2.0,
                "valor_unitario": "R$ 12,00",
                "valor_total": "R$ 24,00",
                "_source_file": "sales_data_02_2026.csv",
            },
            {
                "numero_da_venda": "5624",
                "data_da_venda": "3/1/2026",
                "nome_do_produto_servico": "RISOLE",
                "quantidade_de_itens": 1.0,
                "valor_unitario": "8.0",
                "valor_total": "8.0",
                "_source_file": "sales_data_02_2026.csv",
            },
        ])

    def test_columns_renamed(self):
        df = SalesTransformer().transform(self._make_raw_sales())
        assert "num_venda" in df.columns
        assert "produto_raw" in df.columns
        assert "qtd" in df.columns
        assert "valor_venda" in df.columns

    def test_date_parsed(self):
        df = SalesTransformer().transform(self._make_raw_sales())
        assert pd.api.types.is_datetime64_any_dtype(df["data"])

    def test_numeric_coercion(self):
        df = SalesTransformer().transform(self._make_raw_sales())
        assert df["valor_venda"].iloc[0] == pytest.approx(12.0)
        assert df["qtd"].iloc[0] == pytest.approx(2.0)

    def test_produto_key_derived(self):
        df = SalesTransformer().transform(self._make_raw_sales())
        assert "produto_key" in df.columns
        assert df["produto_key"].iloc[0] == "brigadeiro"

    def test_tolerates_missing_columns(self):
        """Only columns that exist in the DataFrame are mapped; no KeyError."""
        raw = pd.DataFrame([{"nome_do_produto_servico": "BOLO", "data_da_venda": "1/1/2026"}])
        df = SalesTransformer().transform(raw)
        assert "produto_raw" in df.columns

    def test_source_aware_parsing_prefers_br_when_first_token_over_12(self):
        raw = pd.DataFrame([
            {
                "numero_da_venda": "7001",
                "data_da_venda": "13/01/2026",
                "nome_do_produto_servico": "BRIGADEIRO",
                "_source_file": "janeiro.csv",
            },
            {
                "numero_da_venda": "7002",
                "data_da_venda": "02/01/2026",
                "nome_do_produto_servico": "RISOLE",
                "_source_file": "janeiro.csv",
            },
        ])
        df = SalesTransformer().transform(raw)
        assert pd.Timestamp("2026-01-13") == df.loc[df["num_venda"] == "7001", "data"].iloc[0]
        assert pd.Timestamp("2026-01-02") == df.loc[df["num_venda"] == "7002", "data"].iloc[0]
        assert "parse_strategy" in df.columns


class TestDateFormatChooser:
    def test_choose_br_when_left_token_indicates_day(self):
        s = pd.Series(["13/01/2026", "14/01/2026", "02/01/2026"])
        assert _choose_date_format_for_source(s) == "%d/%m/%Y"

    def test_choose_us_when_right_token_indicates_day(self):
        s = pd.Series(["01/13/2026", "02/14/2026", "02/01/2026"])
        assert _choose_date_format_for_source(s) == "%m/%d/%Y"

    def test_choose_br_from_january_filename_hint_when_dates_are_ambiguous(self):
        s = pd.Series(["02/01/2026", "10/01/2026", "11/01/2026"])
        assert _choose_date_format_for_source(s, "sales_data_01_2026.csv") == "%d/%m/%Y"

    def test_choose_us_from_february_filename_hint_when_dates_are_ambiguous(self):
        s = pd.Series(["2/1/2026", "2/11/2026", "2/21/2026"])
        assert _choose_date_format_for_source(s, "sales_data_02_2026.csv") == "%m/%d/%Y"


# ---------------------------------------------------------------------------
# ProductsTransformer tests
# ---------------------------------------------------------------------------

class TestProductsTransformer:
    def _make_raw_products(self) -> pd.DataFrame:
        return pd.DataFrame([
            {
                "nome_do_produto": "Brigadeiro",
                "categoria": "Doce",
                "custo_total_unitario_r": "R$ 3,50",
            },
            {
                "nome_do_produto": "Risole",
                "categoria": "Salgado",
                "custo_total_unitario_r": "2,00",
            },
        ])

    def test_columns_renamed(self):
        df = ProductsTransformer().transform(self._make_raw_products())
        assert "produto" in df.columns
        assert "custo_unit" in df.columns
        assert "produto_key" in df.columns

    def test_custo_unit_numeric(self):
        df = ProductsTransformer().transform(self._make_raw_products())
        assert df["custo_unit"].iloc[0] == pytest.approx(3.50)
        assert df["custo_unit"].iloc[1] == pytest.approx(2.00)

    def test_produto_key_normalised(self):
        df = ProductsTransformer().transform(self._make_raw_products())
        assert df["produto_key"].iloc[0] == "brigadeiro"

    def test_missing_categoria_filled_with_none(self):
        raw = pd.DataFrame([{"nome_do_produto": "X", "custo_total_unitario_r": "1.0"}])
        df = ProductsTransformer().transform(raw)
        assert "categoria" in df.columns


# ---------------------------------------------------------------------------
# _deduplicate tests
# ---------------------------------------------------------------------------

class TestDeduplicate:
    def test_preserves_same_transaction_across_distinct_files(self):
        df = pd.DataFrame([
            {"num_venda": "001", "produto_key": "brigadeiro", "_source_file": "jan.csv"},
            {"num_venda": "001", "produto_key": "brigadeiro", "_source_file": "jan_backup.csv"},
            {"num_venda": "002", "produto_key": "risole",     "_source_file": "jan.csv"},
        ])
        result = _deduplicate(df)
        assert len(result) == 3

    def test_preserves_technical_duplicates_inside_same_file_for_audit(self):
        df = pd.DataFrame([
            {"num_venda": "001", "produto_key": "brigadeiro", "_source_file": "jan.csv"},
            {"num_venda": "001", "produto_key": "brigadeiro", "_source_file": "jan.csv"},
            {"num_venda": "002", "produto_key": "risole", "_source_file": "jan.csv"},
        ])
        result = _deduplicate(df)
        assert len(result) == 3

    def test_no_duplicates_unchanged(self):
        df = pd.DataFrame([
            {"num_venda": "001", "produto_key": "brigadeiro"},
            {"num_venda": "002", "produto_key": "risole"},
        ])
        result = _deduplicate(df)
        assert len(result) == 2

    def test_deduplicate_with_audit_reports_detected_count_without_row_loss(self):
        df = pd.DataFrame([
            {
                "num_venda": "001",
                "produto_key": "brigadeiro",
                "data": pd.Timestamp("2026-01-10"),
                "_source_file": "jan.csv",
            },
            {
                "num_venda": "001",
                "produto_key": "brigadeiro",
                "data": pd.Timestamp("2026-01-10"),
                "_source_file": "jan.csv",
            },
            {
                "num_venda": "002",
                "produto_key": "risole",
                "data": pd.Timestamp("2026-01-11"),
                "_source_file": "jan.csv",
            },
        ])
        deduped, audit = _deduplicate_with_audit(df)
        assert len(deduped) == 3
        assert audit["before"] == 3
        assert audit["after"] == 3
        assert audit["removed"] == 0
        assert audit["dedup_scope"] == "audit_only_exact_item_grain_same_file"
        assert sum(audit["detected_exact_by_source_file"].values()) == 1


# ---------------------------------------------------------------------------
# SalesProductJoiner tests
# ---------------------------------------------------------------------------

class TestSalesProductJoiner:
    def _sales(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"produto_raw": "BRIGADEIRO", "produto_key": "brigadeiro",
             "qtd": 2.0, "valor_venda": 12.0},
            {"produto_raw": "PRODUTO DESCONHECIDO", "produto_key": "produto desconhecido",
             "qtd": 1.0, "valor_venda": 5.0},
        ])

    def _products(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"produto": "Brigadeiro", "produto_key": "brigadeiro",
             "categoria": "Doce", "custo_unit": 3.5},
        ])

    def test_matched_row_has_custo_unit(self):
        merged = SalesProductJoiner().join(self._sales(), self._products())
        brigadeiro = merged[merged["produto_raw"] == "BRIGADEIRO"].iloc[0]
        assert brigadeiro["custo_unit"] == pytest.approx(3.5)
        assert not brigadeiro["sem_cadastro"]

    def test_orphan_row_flagged(self):
        merged = SalesProductJoiner().join(self._sales(), self._products())
        orphan = merged[merged["produto_raw"] == "PRODUTO DESCONHECIDO"].iloc[0]
        assert pd.isna(orphan["custo_unit"])
        assert orphan["sem_cadastro"]

    def test_all_sales_rows_preserved(self):
        merged = SalesProductJoiner().join(self._sales(), self._products())
        assert len(merged) == 2

    def test_empty_catalog_flags_all_as_orphans(self):
        merged = SalesProductJoiner().join(self._sales(), pd.DataFrame())
        assert merged["sem_cadastro"].all()


# ---------------------------------------------------------------------------
# _finalise tests
# ---------------------------------------------------------------------------

class TestFinalise:
    def test_output_columns_present(self):
        df = pd.DataFrame([{
            "data": pd.Timestamp("2026-02-01"),
            "produto_raw": "BRIGADEIRO",
            "produto": "Brigadeiro",
            "categoria": "Doce",
            "qtd": 2.0,
            "valor_venda": 12.0,
            "custo_unit": 3.5,
            "sem_cadastro": False,
        }])
        result = _finalise(df)
        for col in OUTPUT_COLUMNS + ["sem_cadastro"]:
            assert col in result.columns

    def test_lucro_est_computed(self):
        df = pd.DataFrame([{
            "produto": "Brigadeiro",
            "produto_raw": "BRIGADEIRO",
            "valor_venda": 12.0,
            "custo_unit": 3.5,
            "sem_cadastro": False,
        }])
        result = _finalise(df)
        assert result["lucro_est"].iloc[0] == pytest.approx(8.5)

    def test_orphan_lucro_est_equals_valor_venda(self):
        """Orphan rows have NaN custo_unit → lucro_est = valor_venda - 0."""
        df = pd.DataFrame([{
            "produto_raw": "DESCONHECIDO",
            "valor_venda": 10.0,
            "custo_unit": float("nan"),
            "sem_cadastro": True,
        }])
        result = _finalise(df)
        assert result["lucro_est"].iloc[0] == pytest.approx(10.0)

    def test_produto_falls_back_to_produto_raw(self):
        df = pd.DataFrame([{
            "produto_raw": "PRODUTO CRU",
            "produto": None,
            "valor_venda": 5.0,
            "custo_unit": float("nan"),
            "sem_cadastro": True,
        }])
        result = _finalise(df)
        assert result["produto"].iloc[0] == "PRODUTO CRU"


# ---------------------------------------------------------------------------
# SalesFilesExtractor tests (with in-memory fake adapter)
# ---------------------------------------------------------------------------

class FakeDriveAdapter(DriveDataSource):
    """In-memory adapter for unit-testing SalesFilesExtractor."""

    def __init__(self, files: list[dict], dataframes: dict[str, pd.DataFrame]) -> None:
        self._files = files
        self._dataframes = dataframes

    def list_tabular_files(self) -> list[dict]:
        return self._files

    def read_as_dataframe(self, file_meta: dict) -> pd.DataFrame | None:
        return self._dataframes.get(file_meta["name"])


class TestSalesFilesExtractor:
    def _make_raw_df(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"Número da venda": "001", "Nome do produto/serviço": "Brigadeiro",
             "Data da venda": "2/1/2026"},
        ])

    def test_normalises_headers_on_load(self):
        adapter = FakeDriveAdapter(
            files=[{"id": "f1", "name": "jan.csv", "mimeType": "text/csv"}],
            dataframes={"jan.csv": self._make_raw_df()},
        )
        df = SalesFilesExtractor(adapter).extract()
        assert "numero_da_venda" in df.columns
        assert "nome_do_produto_servico" in df.columns

    def test_source_file_column_added(self):
        adapter = FakeDriveAdapter(
            files=[{"id": "f1", "name": "jan.csv", "mimeType": "text/csv"}],
            dataframes={"jan.csv": self._make_raw_df()},
        )
        df = SalesFilesExtractor(adapter).extract()
        assert "_source_file" in df.columns
        assert df["_source_file"].iloc[0] == "jan.csv"

    def test_multiple_files_concatenated(self):
        raw = self._make_raw_df()
        adapter = FakeDriveAdapter(
            files=[
                {"id": "f1", "name": "jan.csv", "mimeType": "text/csv"},
                {"id": "f2", "name": "fev.csv", "mimeType": "text/csv"},
            ],
            dataframes={"jan.csv": raw.copy(), "fev.csv": raw.copy()},
        )
        df = SalesFilesExtractor(adapter).extract()
        assert len(df) == 2

    def test_empty_adapter_returns_empty_dataframe(self):
        adapter = FakeDriveAdapter(files=[], dataframes={})
        df = SalesFilesExtractor(adapter).extract()
        assert df.empty



