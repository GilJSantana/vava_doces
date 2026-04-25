import os
import time
from typing import Optional

import gspread
import pandas as pd
import streamlit as st

from src.ports.data_source import DataSource, DataSourceError


DEFAULT_CONTROLE_VENDAS_SHEET_ID = "1KEzf8FcL21DMk_64t-B9gMQIxjEx3ZPS_XsY-jYNVNk"
MANUAL_TABS = {"Matéria Prima", "Receitas", "Produtos"}
_SHEETS_CACHE_TTL_SECONDS = int(os.getenv("VAVA_SHEETS_CACHE_TTL", "300"))


@st.cache_data(ttl=_SHEETS_CACHE_TTL_SECONDS)
def _fetch_values_cached(
    credential_file: str | None,
    sheet_id: str,
    sheet_name: str,
    cell_range: str | None,
) -> list:
    """Fetch worksheet payload through Streamlit data cache.

    The adapter still keeps its own in-memory TTL cache, but this function avoids
    repeated network calls across Streamlit reruns/process-local adapter instances.
    """
    account_info = st.secrets.get("gcp_service_account")
    if not isinstance(account_info, dict):
        raise DataSourceError("Missing required secret: gcp_service_account")

    client = gspread.service_account_from_dict(dict(account_info))
    worksheet = client.open_by_key(sheet_id).worksheet(sheet_name)
    if cell_range:
        return worksheet.get(cell_range)
    return worksheet.get_all_records()


class GoogleSheetsAdapter(DataSource):
    def __init__(self, credential_file: Optional[str] = None, sheet_id: Optional[str] = None):
        self.credential_file = credential_file
        self.sheet_id = sheet_id or os.getenv("GOOGLE_SHEET_ID") or DEFAULT_CONTROLE_VENDAS_SHEET_ID
        self._client = None
        self._spreadsheet = None
        self._sheet_cache: dict[tuple[str, str | None], tuple[float, pd.DataFrame]] = {}

    @property
    def client(self):
        if self._client is None:
            account_info = st.secrets.get("gcp_service_account")
            if not isinstance(account_info, dict):
                raise DataSourceError("Missing required secret: gcp_service_account")
            self._client = gspread.service_account_from_dict(dict(account_info))
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

    def get_sheet_as_df(
        self,
        sheet_name: str,
        *,
        cell_range: str | None = None,
        ttl_seconds: int | None = None,
    ) -> pd.DataFrame:
        """Retrieve worksheet data as DataFrame with TTL cache and optional A1 range.

        Args:
            sheet_name: Worksheet/tab name.
            cell_range: Optional A1 range (e.g. "A1:H5000") to reduce payload.
            ttl_seconds: Optional per-call TTL for adapter in-memory cache.
        """
        try:
            if sheet_name in MANUAL_TABS:
                # Explicit branch documents support for manual Medallion tabs.
                pass

            cache_key = (sheet_name, cell_range)
            ttl = int(ttl_seconds if ttl_seconds is not None else _SHEETS_CACHE_TTL_SECONDS)
            cached_entry = self._sheet_cache.get(cache_key)
            if cached_entry is not None:
                cached_at, cached_df = cached_entry
                if (time.time() - cached_at) <= ttl:
                    return cached_df.copy()

            if self._client is None:
                payload = _fetch_values_cached(self.credential_file, self.sheet_id, sheet_name, cell_range)
                dataframe = self._payload_to_dataframe(payload, cell_range)
            else:
                worksheet = self._get_spreadsheet().worksheet(sheet_name)
                payload = worksheet.get(cell_range) if cell_range else worksheet.get_all_records()
                dataframe = self._payload_to_dataframe(payload, cell_range)

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

            self._sheet_cache[cache_key] = (time.time(), dataframe)
            return dataframe.copy()
        except Exception as e:
            # Normalize errors to DataSourceError for callers/tests
            raise DataSourceError(f"Failed to fetch data from Google Sheets: {e}")

    @staticmethod
    def _payload_to_dataframe(payload: list, from_range: str | None) -> pd.DataFrame:
        if not from_range:
            return pd.DataFrame(payload)
        rows = payload if isinstance(payload, list) else []
        if not rows:
            return pd.DataFrame()
        headers = [str(h).strip() for h in rows[0]]
        return pd.DataFrame(rows[1:], columns=headers)

