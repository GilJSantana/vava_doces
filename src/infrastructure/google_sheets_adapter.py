import os
from typing import Optional

import gspread
import pandas as pd
from src.ports.data_source import DataSource, DataSourceError


DEFAULT_CONTROLE_VENDAS_SHEET_ID = "1KEzf8FcL21DMk_64t-B9gMQIxjEx3ZPS_XsY-jYNVNk"
MANUAL_TABS = {"Matéria Prima", "Receitas", "Produtos"}

class GoogleSheetsAdapter(DataSource):
    def __init__(self, credential_file: Optional[str] = None, sheet_id: Optional[str] = None):
        self.credential_file = credential_file or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self.sheet_id = sheet_id or os.getenv("GOOGLE_SHEET_ID") or DEFAULT_CONTROLE_VENDAS_SHEET_ID
        self._client = None
        self._spreadsheet = None
        self._sheet_cache: dict[str, pd.DataFrame] = {}

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

    def _get_spreadsheet(self):
        """Abre a planilha uma única vez por instância do adaptador."""
        if self._spreadsheet is None:
            client = self.client
            self._spreadsheet = client.open_by_key(self.sheet_id) if self.sheet_id else client.open("")
        return self._spreadsheet

    def get_data(self, sheet_name: str) -> pd.DataFrame:
        return self.get_sheet_as_df(sheet_name)

    def get_sheet_as_df(self, sheet_name: str) -> pd.DataFrame:
        """
        Connects to Google Sheets and retrieves data from a specific worksheet.
        Returns a pandas DataFrame built from worksheet records.
        """
        try:
            if sheet_name in MANUAL_TABS:
                # Explicit branch documents support for manual Medallion tabs.
                pass

            cached_df = self._sheet_cache.get(sheet_name)
            if cached_df is not None:
                return cached_df.copy()

            worksheet = self._get_spreadsheet().worksheet(sheet_name)
            data = worksheet.get_all_records()
            dataframe = pd.DataFrame(data)

            # Early pruning: keep only meaningful rows based on the first two columns.
            if not dataframe.empty and len(dataframe.columns) >= 2:
                dataframe = dataframe.dropna(
                    subset=[dataframe.columns[0], dataframe.columns[1]],
                    how="all",
                )

                valid_mask = dataframe[dataframe.columns[0]].notna().to_numpy()
                if valid_mask.any():
                    last_pos = int(valid_mask.nonzero()[0][-1])
                    dataframe = dataframe.iloc[: last_pos + 1]

            self._sheet_cache[sheet_name] = dataframe
            return dataframe.copy()
        except Exception as e:
            # Normalize errors to DataSourceError for callers/tests
            raise DataSourceError(f"Failed to fetch data from Google Sheets: {e}")
