"""Google Drive parquet asset discovery and in-memory I/O helpers."""

from __future__ import annotations

import io
import logging
from collections.abc import Mapping

import pandas as pd
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

logger = logging.getLogger(__name__)

_DRIVE_RO_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
_DRIVE_RW_SCOPES = ["https://www.googleapis.com/auth/drive"]


def _get_drive_folder_id() -> str:
    try:
        return str(st.secrets.get("GOOGLE_DRIVE_FOLDER_ID", "")).strip()
    except Exception:
        return ""


def _load_service_account_info() -> dict | None:
    try:
        account_info = st.secrets.get("gcp_service_account")
    except Exception:
        logger.warning("Could not read gcp_service_account from st.secrets")
        return None

    if not isinstance(account_info, Mapping):
        logger.warning("Missing or invalid gcp_service_account in st.secrets")
        return None

    native = dict(account_info)
    return native if native else None


def _build_drive_service(scopes: list[str]):
    info = _load_service_account_info()
    if info is None:
        return None
    credentials = service_account.Credentials.from_service_account_info(info, scopes=scopes)
    return build("drive", "v3", credentials=credentials)


@st.cache_resource
def get_drive_assets_map() -> dict[str, str]:
    """Discover parquet assets in the configured Drive folder.

    Returns a mapping: {"<file_name>.parquet": "<file_id>"}.
    """
    service = _build_drive_service(_DRIVE_RO_SCOPES)
    if service is None:
        return {}

    # Global discovery in service-account scope (includes nested folders).
    query = "name contains '.parquet' and trashed = false"
    page_token = None
    assets: dict[str, str] = {}

    while True:
        response = (
            service.files()
            .list(
                q=query,
                spaces="drive",
                fields="nextPageToken, files(id,name,modifiedTime)",
                orderBy="modifiedTime desc",
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )

        for item in response.get("files", []):
            name = str(item.get("name", "")).strip()
            file_id = str(item.get("id", "")).strip()
            if not name or not file_id:
                continue
            if name not in assets:
                assets[name] = file_id

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    logger.info("Discovered %d parquet asset(s) in service-account Drive scope", len(assets))
    logger.debug("Mapeamento final de ativos: %s", assets)
    return assets


@st.cache_data(ttl=3600)
def load_parquet_from_drive(file_name: str) -> pd.DataFrame:
    """Load one parquet file directly from Drive into memory."""
    file_id = get_drive_assets_map().get(file_name)
    if not file_id:
        return pd.DataFrame()

    service = _build_drive_service(_DRIVE_RO_SCOPES)
    if service is None:
        return pd.DataFrame()

    content = service.files().get_media(fileId=file_id, supportsAllDrives=True).execute()
    return pd.read_parquet(io.BytesIO(content))


def update_parquet_in_drive(file_name: str, df: pd.DataFrame) -> bool:
    """Update an existing parquet file in Drive using in-memory bytes."""
    file_id = get_drive_assets_map().get(file_name)
    if not file_id:
        logger.warning("Drive parquet asset not found for update: %s", file_name)
        return False

    service = _build_drive_service(_DRIVE_RW_SCOPES)
    if service is None:
        return False

    buffer = io.BytesIO()
    df.to_parquet(buffer, engine="pyarrow", index=False)
    buffer.seek(0)

    media = MediaIoBaseUpload(buffer, mimetype="application/octet-stream", resumable=False)
    service.files().update(
        fileId=file_id,
        media_body=media,
        supportsAllDrives=True,
    ).execute()
    return True



