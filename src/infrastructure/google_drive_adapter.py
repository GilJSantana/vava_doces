"""Google Drive adapter: lists and downloads files from a shared folder.

Uses google-api-python-client with a Service Account credential.
Responsible only for I/O; no business logic here.
"""

from __future__ import annotations

import io
import logging
from typing import Optional

import pandas as pd
from googleapiclient.discovery import build
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

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


def build_drive_credentials(credential_file: str) -> service_account.Credentials:
    """Create Service Account credentials scoped for Drive + Sheets (read-only)."""
    return service_account.Credentials.from_service_account_file(
        credential_file, scopes=_DRIVE_SCOPES
    )


class GoogleDriveAdapter:
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
        logger.info("GoogleDriveAdapter: found %d tabular file(s) in folder %s",
                    len(files), self._folder_id)
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
                df = pd.read_csv(io.BytesIO(raw), sep=None, engine="python")
            else:
                df = pd.read_excel(io.BytesIO(raw), engine="openpyxl")
            logger.info("GoogleDriveAdapter: loaded %s  →  %d rows", name, len(df))
            return df
        except Exception as exc:  # noqa: BLE001
            logger.warning("GoogleDriveAdapter: skipping %s — %s", name, exc)
            return None

