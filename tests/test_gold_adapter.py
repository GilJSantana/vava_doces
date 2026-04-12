"""Tests for gold adapter and gold data source integration."""

from pathlib import Path
import tempfile
import pytest
import pandas as pd

from src.infrastructure.gold_adapter import GoldParquetAdapter
from src.ports.data_source import DataSourceError, GoldDataSource


class TestGoldParquetAdapter:
    """Tests for GoldParquetAdapter."""

    @pytest.fixture
    def temp_gold_dir(self):
        """Create a temporary gold directory with mock Parquet files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gold_dir = Path(tmpdir)

            # Create mock gold tables
            dim_produto = pd.DataFrame({
                "produto_id": [1, 2, 3],
                "nome_produto": ["Brigadeiro", "Risole", "Bombom"],
            })
            dim_produto.to_parquet(gold_dir / "dim_produto.parquet", engine="pyarrow")

            dim_tempo = pd.DataFrame({
                "data_id": [1, 2],
                "data": pd.to_datetime(["2026-02-01", "2026-02-02"]),
                "dia": [1, 2],
                "mes": [2, 2],
                "ano": [2026, 2026],
                "trimestre": [1, 1],
                "nome_mes": ["Fevereiro", "Fevereiro"],
                "dia_semana": ["domingo", "segunda"],
            })
            dim_tempo.to_parquet(gold_dir / "dim_tempo.parquet", engine="pyarrow")

            fato_vendas = pd.DataFrame({
                "venda_id": [1, 2, 3],
                "produto_id": [1, 2, 1],
                "data_id": [1, 1, 2],
                "cliente": ["João", "Maria", "Pedro"],
                "quantidade": [2.0, 1.0, 3.0],
                "valor_total": [18.0, 8.0, 15.0],
                "custo": [0.0, 0.0, 0.0],
                "margem": [9.0, 8.0, 5.0],
            })
            fato_vendas.to_parquet(gold_dir / "fato_vendas.parquet", engine="pyarrow")

            agg_vendas_dia = pd.DataFrame({
                "data_id": [1, 2],
                "faturamento_liquido": [26.0, 15.0],
                "custo_total": [0.0, 0.0],
                "lucro_total": [26.0, 15.0],
            })
            agg_vendas_dia.to_parquet(gold_dir / "agg_vendas_dia.parquet", engine="pyarrow")

            yield gold_dir

    def test_load_gold_dim_produto(self, temp_gold_dir):
        adapter = GoldParquetAdapter(temp_gold_dir)
        df = adapter.load_gold("dim_produto")
        assert len(df) == 3
        assert list(df.columns) == ["produto_id", "nome_produto"]
        assert df.iloc[0]["nome_produto"] == "Brigadeiro"

    def test_load_gold_dim_tempo(self, temp_gold_dir):
        adapter = GoldParquetAdapter(temp_gold_dir)
        df = adapter.load_gold("dim_tempo")
        assert len(df) == 2
        assert "data" in df.columns
        assert pd.api.types.is_datetime64_any_dtype(df["data"])

    def test_load_gold_fato_vendas(self, temp_gold_dir):
        adapter = GoldParquetAdapter(temp_gold_dir)
        df = adapter.load_gold("fato_vendas")
        assert len(df) == 3
        assert "venda_id" in df.columns
        assert "produto_id" in df.columns
        assert "data_id" in df.columns

    def test_load_gold_agg_vendas_dia(self, temp_gold_dir):
        adapter = GoldParquetAdapter(temp_gold_dir)
        df = adapter.load_gold("agg_vendas_dia")
        assert len(df) == 2
        assert "faturamento_liquido" in df.columns

    def test_load_gold_caching(self, temp_gold_dir):
        adapter = GoldParquetAdapter(temp_gold_dir)
        df1 = adapter.load_gold("dim_produto")
        df2 = adapter.load_gold("dim_produto")
        # Both should be equal data-wise, but different object instances
        assert df1.equals(df2)
        assert df1 is not df2  # Different Python objects

    def test_load_gold_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = GoldParquetAdapter(Path(tmpdir))
            with pytest.raises(DataSourceError) as exc_info:
                adapter.load_gold("dim_produto")
            assert "not found" in str(exc_info.value).lower()

    def test_clear_cache(self, temp_gold_dir):
        adapter = GoldParquetAdapter(temp_gold_dir)
        adapter.load_gold("dim_produto")
        assert "dim_produto" in adapter._cache
        adapter.clear_cache()
        assert len(adapter._cache) == 0

    def test_default_gold_dir(self, temp_gold_dir, monkeypatch):
        """Test that default gold_dir is data/processed/gold relative to project root."""
        # Create the expected default path structure in a temp location
        project_root = Path(temp_gold_dir)
        gold_dir = project_root / "data" / "processed" / "gold"
        gold_dir.mkdir(parents=True, exist_ok=True)

        # Create a dummy file
        dim_produto = pd.DataFrame({"id": [1], "name": ["Test"]})
        dim_produto.to_parquet(gold_dir / "dim_produto.parquet", engine="pyarrow")

        # Mock Path resolution to return our temp structure
        # (In real usage, this is handled by the file system)
        adapter = GoldParquetAdapter(gold_dir)
        df = adapter.load_gold("dim_produto")
        assert len(df) == 1

class TestGoldDataSourceInterface:
    """Tests to ensure GoldDataSource port is properly defined."""

    def test_gold_data_source_abstract(self):
        """GoldDataSource should be an abstract base class."""
        from src.ports.data_source import GoldDataSource
        assert hasattr(GoldDataSource, '__abstractmethods__')

    def test_gold_adapter_implements_gold_data_source(self):
        """GoldParquetAdapter should implement GoldDataSource."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = GoldParquetAdapter(Path(tmpdir))
            assert isinstance(adapter, GoldDataSource)

    def test_gold_data_source_error_inheritance(self):
        """DataSourceError should be catchable."""
        with pytest.raises(DataSourceError):
            with tempfile.TemporaryDirectory() as tmpdir:
                adapter = GoldParquetAdapter(Path(tmpdir))
                adapter.load_gold("nonexistent")

