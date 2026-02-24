from abc import ABC, abstractmethod
import pandas as pd

class DataSource(ABC):
    @abstractmethod
    def get_data(self, sheet_name: str) -> pd.DataFrame:
        """Retrieves data from a specific sheet and returns it as a DataFrame."""
        pass


class DataSourceError(RuntimeError):
    """Raised when a data source operation fails (e.g. network, auth, API errors).

    Having a specific error class makes it easier for callers to handle
    data-source-related failures and for tests to assert error cases.
    """
    pass
