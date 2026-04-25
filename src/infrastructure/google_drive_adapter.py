"""Google Drive adapter: lists and downloads files from a shared folder.

Uses google-api-python-client with a Service Account credential.
Responsible only for I/O; no business logic here.
"""

from __future__ import annotations

import io
import logging
import re
import unicodedata
from typing import Optional

import pandas as pd
import streamlit as st
from googleapiclient.discovery import build
from google.oauth2 import service_account

from src.ports.data_source import DriveDataSource

logger = logging.getLogger(__name__)


def _normalize_header_token(value: object) -> str:
    """Normalize header token for lightweight CSV-structure scoring."""
    text = str(value or "").replace("\ufeff", "").strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")

# MIME types we know how to read as tabular data
_TABULAR_MIMES: set[str] = {
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

_DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]


def build_drive_credentials(credential_file: str | None = None) -> service_account.Credentials:
    """Create Service Account credentials from Streamlit secrets.

    The `credential_file` parameter is kept only for backward compatibility.
    """
    account_info = st.secrets.get("gcp_service_account")
    if not isinstance(account_info, dict):
        raise ValueError("Missing required secret: gcp_service_account")

    base_credentials = service_account.Credentials.from_service_account_info(dict(account_info))
    return base_credentials.with_scopes(_DRIVE_SCOPES)


class GoogleDriveAdapter(DriveDataSource):
    """Lists and downloads tabular files from a Google Drive folder.

    Args:
        credential_file: Path to the Service Account JSON key file.
        folder_id: Google Drive folder ID to inspect.
    """

    def __init__(self, credential_file: str, folder_id: str) -> None:
        self._credential_file = credential_file
        self._folder_id = folder_id
        self._service = build(
            "drive",
            "v3",
            credentials=build_drive_credentials(credential_file),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_tabular_files(self) -> list[dict]:
        """Return metadata dicts for every XLSX/CSV in the folder."""
        results = self._service.files().list(
            q=f"'{self._folder_id}' in parents and trashed=false",
            pageSize=200,
            fields="files(id,name,mimeType)",
        ).execute()

        files = [
            f for f in results.get("files", [])
            if f.get("mimeType") in _TABULAR_MIMES
        ]
        for file in files:
            logger.info("Arquivo %s localizado no Drive.", file["name"])
        logger.info("list_tabular_files: found %d file(s) in folder %s", len(files), self._folder_id)
        return files

    def download_bytes(self, file_id: str) -> bytes:
        """Download raw bytes for a Drive file."""
        return self._service.files().get_media(fileId=file_id).execute()

    def read_as_dataframe(self, file_meta: dict) -> Optional[pd.DataFrame]:
        """Download a Drive file and parse it into a DataFrame.

        Returns ``None`` and logs a warning on any read error.
        """
        name = file_meta["name"]
        mime = file_meta["mimeType"]
        try:
            raw = self.download_bytes(file_meta["id"])
            if mime == "text/csv":
                expected_cols = {
                    "numero_da_venda",
                    "data_da_venda",
                    "nome_do_produto_servico",
                    "quantidade_de_itens",
                    "valor_total",
                }
                best_df: Optional[pd.DataFrame] = None
                best_sep = None
                best_score = -1
                last_exc: Optional[Exception] = None
                for sep in (";", ",", "\t", "|"):
                    try:
                        candidate = pd.read_csv(io.BytesIO(raw), sep=sep, engine="python")
                        norm_cols = {
                            _normalize_header_token(c)
                            for c in candidate.columns
                        }
                        score = int(candidate.shape[1]) + 5 * len(norm_cols & expected_cols)
                        if score > best_score:
                            best_df = candidate
                            best_sep = sep
                            best_score = score
                    except Exception as exc:  # noqa: BLE001
                        last_exc = exc
                if best_df is None:
                    raise last_exc if last_exc is not None else ValueError("Unable to parse CSV")
                df = best_df
                logger.info("GoogleDriveAdapter: parsed %s using sep=%r (%d cols)", name, best_sep, df.shape[1])
                logger.info("Arquivo %s carregado com sucesso.", name)
            else:
                df = pd.read_excel(io.BytesIO(raw), engine="openpyxl")
            logger.info("GoogleDriveAdapter: loaded %s  →  %d rows", name, len(df))
            return df
        except Exception as exc:  # noqa: BLE001
            logger.warning("GoogleDriveAdapter: skipping %s — %s", name, exc)
            logger.error("ERRO: Falha ao carregar %s.", name)
            return None



