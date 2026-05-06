"""Google Drive adapter: lists and downloads files from a shared folder.

Uses google-api-python-client with a Service Account credential.
Responsible only for I/O; no business logic here.
"""

from __future__ import annotations

import io
import logging
import os
import re
import unicodedata
from collections.abc import Mapping
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
_SHEET_MIME = "application/vnd.google-apps.spreadsheet"

_MANUAL_TAB_ALIASES = {
    "produtos": "manual_produtos.csv",
    "receitas": "manual_receitas.csv",
    "materia_prima": "manual_materia_prima.csv",
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
    if not isinstance(account_info, Mapping):
        raise ValueError("Missing required secret: gcp_service_account")

    # Streamlit secrets section may be Mapping-like, not a plain dict.
    base_credentials = service_account.Credentials.from_service_account_info(dict(account_info))
    return base_credentials.with_scopes(_DRIVE_SCOPES)


def _normalize_sheet_token(value: object) -> str:
    text = str(value or "").strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _manual_sheet_alias(sheet_title: str) -> str | None:
    token = _normalize_sheet_token(sheet_title)
    if not token:
        return None
    if "materia" in token and "prima" in token:
        return "materia_prima"
    if token.startswith("receita") or "receitas" in token:
        return "receitas"
    if token.startswith("produto") or "produtos" in token:
        return "produtos"
    return None


def _sheet_values_to_dataframe(values: list[list[object]]) -> pd.DataFrame:
    if not values:
        return pd.DataFrame()
    header = [str(col).strip() for col in values[0]]
    data_rows = values[1:] if len(values) > 1 else []
    if not header:
        return pd.DataFrame(data_rows)
    # Keep row width consistent with header width to avoid DataFrame constructor errors.
    normalized_rows = [list(row[: len(header)]) + [""] * max(0, len(header) - len(row)) for row in data_rows]
    return pd.DataFrame(normalized_rows, columns=header)


class GoogleDriveAdapter(DriveDataSource):
    """Lists and downloads tabular files from a Google Drive folder.

    Args:
        credential_file: Path to the Service Account JSON key file.
        folder_id: Google Drive folder ID to inspect.
    """

    def __init__(self, credential_file: str, folder_id: str) -> None:
        self._credential_file = credential_file
        self._folder_id = folder_id
        self._credentials = build_drive_credentials(credential_file)
        self._service = build(
            "drive",
            "v3",
            credentials=self._credentials,
        )
        self._sheets_service = build(
            "sheets",
            "v4",
            credentials=self._credentials,
        )
        self._manual_sheet_id = self._resolve_manual_sheet_id()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_tabular_files(self) -> list[dict]:
        """Return metadata dicts for tabular files and manual-cost sheet tabs."""
        results = self._service.files().list(
            q=f"'{self._folder_id}' in parents and trashed=false",
            pageSize=200,
            fields="files(id,name,mimeType,modifiedTime)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()

        files = [
            f for f in results.get("files", [])
            if f.get("mimeType") in _TABULAR_MIMES
        ]
        files.extend(self._list_manual_sheet_entries())
        for file in files:
            logger.info("Arquivo %s localizado no Drive.", file["name"])
        logger.info("list_tabular_files: found %d file(s) in folder %s", len(files), self._folder_id)
        return files

    def _resolve_manual_sheet_id(self) -> str | None:
        env_candidates = [
            os.getenv("PRODUCTION_COSTS_SHEET_ID"),
            os.getenv("GOOGLE_SHEET_ID"),
            os.getenv("SALES_SHEET_ID"),
        ]
        for value in env_candidates:
            token = str(value or "").strip()
            if token:
                return token
        secret_id = st.secrets.get("GOOGLE_SHEET_ID")
        token = str(secret_id or "").strip()
        return token or None

    def _fetch_sheet_metadata(self, sheet_id: str) -> dict | None:
        try:
            return self._service.files().get(
                fileId=sheet_id,
                fields="id,name,mimeType,modifiedTime",
                supportsAllDrives=True,
            ).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("GoogleDriveAdapter: failed to fetch metadata for sheet %s — %s", sheet_id, exc)
            return None

    def _list_manual_sheet_entries(self) -> list[dict]:
        if not self._manual_sheet_id:
            return []
        metadata = self._fetch_sheet_metadata(self._manual_sheet_id)
        if not metadata or metadata.get("mimeType") != _SHEET_MIME:
            return []
        try:
            spreadsheet = self._sheets_service.spreadsheets().get(
                spreadsheetId=self._manual_sheet_id,
                fields="sheets(properties(title))",
            ).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("GoogleDriveAdapter: failed to list manual sheet tabs — %s", exc)
            return []

        entries: list[dict] = []
        for sheet in spreadsheet.get("sheets", []):
            title = str((sheet.get("properties") or {}).get("title") or "").strip()
            alias = _manual_sheet_alias(title)
            if not alias:
                continue
            entries.append(
                {
                    "id": metadata.get("id"),
                    "name": _MANUAL_TAB_ALIASES[alias],
                    "mimeType": _SHEET_MIME,
                    "modifiedTime": metadata.get("modifiedTime"),
                    "sheetName": title,
                }
            )
        return entries

    def download_bytes(self, file_id: str) -> bytes:
        """Download raw bytes for a Drive file."""
        return self._service.files().get_media(fileId=file_id).execute()

    def read_as_dataframe(self, file_meta: dict) -> Optional[pd.DataFrame]:
        """Download a Drive file and parse it into a DataFrame.

        Returns ``None`` and logs a warning on any read error.
        """
        name = file_meta["name"]
        mime = file_meta["mimeType"]
        sheet_name = str(file_meta.get("sheetName") or "").strip()
        try:
            if mime == _SHEET_MIME and sheet_name:
                payload = self._sheets_service.spreadsheets().values().get(
                    spreadsheetId=file_meta["id"],
                    range=f"'{sheet_name}'",
                ).execute()
                df = _sheet_values_to_dataframe(payload.get("values", []))
                logger.info("GoogleDriveAdapter: loaded sheet tab %s/%s  →  %d rows", name, sheet_name, len(df))
                return df

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



