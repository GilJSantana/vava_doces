from abc import ABC, abstractmethod
from typing import Optional, Literal
import pandas as pd


class DataSource(ABC):
    @abstractmethod
    def get_data(self, sheet_name: str) -> pd.DataFrame:
        """Retrieves data from a specific sheet and returns it as a DataFrame."""
        pass


class DriveDataSource(ABC):
    """Port for Drive adapters — lists and reads tabular files from a folder."""

    @abstractmethod
    def list_tabular_files(self) -> list[dict]:
        """Return a list of file metadata dicts (id, name, mimeType)."""
        pass

    @abstractmethod
    def read_as_dataframe(self, file_meta: dict) -> Optional[pd.DataFrame]:
        """Download ``file_meta`` and return it as a DataFrame, or None on failure."""
        pass


class GoldDataSource(ABC):
    """Port for Gold layer (star schema) adapters — reads Parquet dimension/fact tables.

    The gold layer is organized as:
      - dim_produto.parquet      (product dimension)
      - dim_tempo.parquet        (temporal dimension)
      - dim_canal.parquet        (sales channel dimension)
      - fato_vendas.parquet      (sales fact table)
      - agg_vendas_dia.parquet   (daily aggregate)
      - agg_vendas_canal.parquet (channel aggregate)
      - agg_vendas_produto.parquet (product aggregate)
      - agg_vendas_tempo.parquet (monthly aggregate)
    """

    @abstractmethod
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
    ) -> pd.DataFrame:
        """Load a gold layer Parquet table by name.

        Args:
            layer: Name of the gold layer to load.

        Returns:
            DataFrame containing the requested gold layer.

        Raises:
            DataSourceError: If the file is missing or cannot be read.
        """
        pass


class DataSourceError(RuntimeError):
    """Raised when a data source operation fails (e.g. network, auth, API errors).

    Having a specific error class makes it easier for callers to handle
    data-source-related failures and for tests to assert error cases.
    """
    pass
