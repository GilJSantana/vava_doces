"""Gold Layer Adapter — reads Parquet star schema tables from Google Drive."""

from collections.abc import Callable, Mapping
from typing import Literal
import pandas as pd

from src.infrastructure.drive_manager import get_drive_assets_map, load_parquet_from_drive
from src.ports.data_source import GoldDataSource, DataSourceError


class GoldParquetAdapter(GoldDataSource):
    """Adapter for reading gold layer Parquet files exclusively from Google Drive."""

    def __init__(
        self,
        parquet_loader: Callable[[str], pd.DataFrame] | None = None,
        assets_provider: Callable[[], Mapping[str, str]] | None = None,
    ):
        """Initialize the adapter with an optional parquet loader injection (tests)."""
        self._loader = parquet_loader or load_parquet_from_drive
        self._assets_provider = assets_provider or get_drive_assets_map
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
            layer: Name of the table ('dim_produto', 'dim_tempo', or 'fato_vendas').

        Returns:
            DataFrame containing the requested table.

        Raises:
            DataSourceError: If the file is missing or cannot be read.
        """
        cache_key = f"{layer}|{','.join(sorted(columns))}" if columns else layer
        if cache_key in self._cache:
            return self._cache[cache_key].copy()

        file_name = f"{layer}.parquet"
        if file_name not in self._assets_provider():
            raise DataSourceError(
                "Gold layer file not found in Google Drive asset map: "
                f"{file_name}. Run the pipeline to materialize/update gold tables."
            )

        try:
            full_df = self._loader(file_name)
            if full_df is None or full_df.empty:
                raise DataSourceError(f"Gold layer '{layer}' returned empty content from Drive")
            if columns:
                keep = [c for c in columns if c in full_df.columns]
                df = full_df[keep].copy()
            else:
                df = full_df.copy()
            self._cache[cache_key] = df
            return df.copy()
        except Exception as exc:
            raise DataSourceError(
                f"Failed to read gold layer '{layer}': {exc}"
            )

    def clear_cache(self) -> None:
        """Clear the in-memory cache. Useful for testing or forcing reload."""
        self._cache.clear()

