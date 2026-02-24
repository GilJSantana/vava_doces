import gspread
import pandas as pd
from typing import Optional
from src.ports.data_source import DataSource, DataSourceError

class GoogleSheetsAdapter(DataSource):
    def __init__(self, credential_file: Optional[str] = None, sheet_id: Optional[str] = None):
        self.credential_file = credential_file
        self.sheet_id = sheet_id
        self._client = None

    @property
    def client(self):
        if self._client is None:
            # If a credential file path is provided, use it; otherwise rely on
            # environment (GOOGLE_APPLICATION_CREDENTIALS) or default service account.
            if self.credential_file:
                self._client = gspread.service_account(filename=self.credential_file)
            else:
                self._client = gspread.service_account()
        return self._client

    @client.setter
    def client(self, value):
        self._client = value

    def get_data(self, sheet_name: str) -> pd.DataFrame:
        """
        Connects to Google Sheets and retrieves data from a specific worksheet.
        Returns a pandas DataFrame built from worksheet records.
        """
        try:
            client = self.client
            sh = client.open_by_key(self.sheet_id) if self.sheet_id else client.open("")
            worksheet = sh.worksheet(sheet_name)
            data = worksheet.get_all_records()
            return pd.DataFrame(data)
        except Exception as e:
            # Normalize errors to DataSourceError for callers/tests
            raise DataSourceError(f"Failed to fetch data from Google Sheets: {e}")
