"""Tests for gold adapter and gold data source integration."""

import pytest
import pandas as pd

from src.infrastructure.gold_adapter import GoldParquetAdapter
from src.ports.data_source import DataSourceError, GoldDataSource


class TestGoldParquetAdapter:
    """Tests for GoldParquetAdapter."""

    @pytest.fixture
    def fake_drive_store(self):
        return {
            "dim_produto.parquet": pd.DataFrame({
                "produto_id": [1, 2, 3],
                "nome_produto": ["Brigadeiro", "Risole", "Bombom"],
            }),
            "dim_tempo.parquet": pd.DataFrame({
                "data_id": [1, 2],
                "data": pd.to_datetime(["2026-02-01", "2026-02-02"]),
                "dia": [1, 2],
                "mes": [2, 2],
                "ano": [2026, 2026],
                "trimestre": [1, 1],
                "nome_mes": ["Fevereiro", "Fevereiro"],
                "dia_semana": ["domingo", "segunda"],
            }),
            "fato_vendas.parquet": pd.DataFrame({
                "venda_id": [1, 2, 3],
                "produto_id": [1, 2, 1],
                "data_id": [1, 1, 2],
                "cliente": ["Joao", "Maria", "Pedro"],
                "quantidade": [2.0, 1.0, 3.0],
                "valor_total": [18.0, 8.0, 15.0],
                "custo": [0.0, 0.0, 0.0],
                "margem": [9.0, 8.0, 5.0],
            }),
            "agg_vendas_dia.parquet": pd.DataFrame({
                "data_id": [1, 2],
                "faturamento_liquido": [26.0, 15.0],
                "custo_total": [0.0, 0.0],
                "lucro_total": [26.0, 15.0],
            }),
        }

    @staticmethod
    def _adapter_from_store(store: dict[str, pd.DataFrame]) -> GoldParquetAdapter:
        return GoldParquetAdapter(
            parquet_loader=lambda file_name: store.get(file_name, pd.DataFrame()).copy(),
            assets_provider=lambda: {name: f"id-{idx}" for idx, name in enumerate(store, start=1)},
        )

    def test_load_gold_dim_produto(self, fake_drive_store):
        adapter = self._adapter_from_store(fake_drive_store)
        df = adapter.load_gold("dim_produto")
        assert len(df) == 3
        assert list(df.columns) == ["produto_id", "nome_produto"]
        assert df.iloc[0]["nome_produto"] == "Brigadeiro"

    def test_load_gold_dim_tempo(self, fake_drive_store):
        adapter = self._adapter_from_store(fake_drive_store)
        df = adapter.load_gold("dim_tempo")
        assert len(df) == 2
        assert "data" in df.columns
        assert pd.api.types.is_datetime64_any_dtype(df["data"])

    def test_load_gold_fato_vendas(self, fake_drive_store):
        adapter = self._adapter_from_store(fake_drive_store)
        df = adapter.load_gold("fato_vendas")
        assert len(df) == 3
        assert "venda_id" in df.columns
        assert "produto_id" in df.columns
        assert "data_id" in df.columns

    def test_load_gold_agg_vendas_dia(self, fake_drive_store):
        adapter = self._adapter_from_store(fake_drive_store)
        df = adapter.load_gold("agg_vendas_dia")
        assert len(df) == 2
        assert "faturamento_liquido" in df.columns

    def test_load_gold_caching(self, fake_drive_store):
        adapter = self._adapter_from_store(fake_drive_store)
        df1 = adapter.load_gold("dim_produto")
        df2 = adapter.load_gold("dim_produto")
        # Both should be equal data-wise, but different object instances
        assert df1.equals(df2)
        assert df1 is not df2  # Different Python objects

    def test_load_gold_missing_file(self):
        adapter = GoldParquetAdapter(
            parquet_loader=lambda _: pd.DataFrame(),
            assets_provider=lambda: {},
        )
        with pytest.raises(DataSourceError) as exc_info:
            adapter.load_gold("dim_produto")
        assert "not found" in str(exc_info.value).lower()

    def test_clear_cache(self, fake_drive_store):
        adapter = self._adapter_from_store(fake_drive_store)
        adapter.load_gold("dim_produto")
        assert "dim_produto" in adapter._cache
        adapter.clear_cache()
        assert len(adapter._cache) == 0

class TestGoldDataSourceInterface:
    """Tests to ensure GoldDataSource port is properly defined."""

    def test_gold_data_source_abstract(self):
        """GoldDataSource should be an abstract base class."""
        from src.ports.data_source import GoldDataSource
        assert hasattr(GoldDataSource, '__abstractmethods__')

    def test_gold_adapter_implements_gold_data_source(self):
        """GoldParquetAdapter should implement GoldDataSource."""
        adapter = GoldParquetAdapter(
            parquet_loader=lambda _: pd.DataFrame(),
            assets_provider=lambda: {},
        )
        assert isinstance(adapter, GoldDataSource)

    def test_gold_data_source_error_inheritance(self):
        """DataSourceError should be catchable."""
        with pytest.raises(DataSourceError):
            adapter = GoldParquetAdapter(
                parquet_loader=lambda _: pd.DataFrame(),
                assets_provider=lambda: {},
            )
            adapter.load_gold("dim_produto")

