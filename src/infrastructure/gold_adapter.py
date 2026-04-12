"""Gold Layer Adapter — reads Parquet star schema tables."""

from pathlib import Path
from typing import Literal, Optional
import pandas as pd

from src.ports.data_source import GoldDataSource, DataSourceError


class GoldParquetAdapter(GoldDataSource):
    """Adapter for reading gold layer Parquet files from disk.

    Expects Parquet files in the following structure:
      gold_dir/
        ├── dim_produto.parquet
        ├── dim_tempo.parquet
        ├── dim_canal.parquet
        ├── fato_vendas.parquet
        ├── agg_vendas_dia.parquet
        ├── agg_vendas_canal.parquet
        ├── agg_vendas_produto.parquet
        └── agg_vendas_tempo.parquet

    Uses pyarrow engine for Parquet I/O.
    """

    def __init__(self, gold_dir: Optional[Path] = None):
        """Initialize the adapter with a gold directory path.

        Args:
            gold_dir: Path to the gold layer directory. Defaults to
                      data/processed/gold/ relative to project root.
        """
        if gold_dir is None:
            # Default: data/processed/gold/ relative to project root
            gold_dir = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "gold"
        self.gold_dir = Path(gold_dir)
        self._cache: dict[str, pd.DataFrame] = {}

    def load_gold(
        self,
        layer: Literal[
            "dim_produto",
            "dim_tempo",
            "dim_canal",
            "fato_vendas",
            "agg_vendas_dia",
            "agg_vendas_canal",
            "agg_vendas_produto",
            "agg_vendas_tempo",
        ],
        columns: list[str] | None = None,
    ) -> pd.DataFrame:
        """Load a gold layer Parquet table.

        Args:
            layer: Name of the table ('dim_produto', 'dim_tempo' or 'fato_vendas').
            columns: Optional column projection to reduce I/O.

        Returns:
            DataFrame containing the requested table.

        Raises:
            DataSourceError: If the file is missing or cannot be read.
        """
        cache_key = layer if not columns else f"{layer}|{','.join(sorted(columns))}"
        if cache_key in self._cache:
            return self._cache[cache_key].copy()

        parquet_path = self.gold_dir / f"{layer}.parquet"

        if not parquet_path.exists():
            raise DataSourceError(
                f"Gold layer file not found: {parquet_path}\n"
                "Run 'python scripts/medallion_pipeline.py' first to generate gold tables."
            )

        try:
            read_kwargs = {"engine": "pyarrow"}
            if columns:
                read_kwargs["columns"] = columns
            try:
                df = pd.read_parquet(parquet_path, **read_kwargs)
            except Exception:
                # Fallback for schema drifts: read full table and keep requested columns present.
                if not columns:
                    raise
                full_df = pd.read_parquet(parquet_path, engine="pyarrow")
                keep = [c for c in columns if c in full_df.columns]
                df = full_df[keep].copy()
            self._cache[cache_key] = df
            return df.copy()
        except Exception as exc:
            raise DataSourceError(
                f"Failed to read gold layer '{layer}': {exc}"
            )

    def clear_cache(self) -> None:
        """Clear the in-memory cache. Useful for testing or forcing reload."""
        self._cache.clear()

