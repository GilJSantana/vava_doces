from abc import ABC, abstractmethod
from typing import Optional
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


class DataSourceError(RuntimeError):
    """Raised when a data source operation fails (e.g. network, auth, API errors).

    Having a specific error class makes it easier for callers to handle
    data-source-related failures and for tests to assert error cases.
    """
    pass
