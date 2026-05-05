"""Google Drive parquet asset discovery and manifest state helpers."""

from __future__ import annotations

import io
import json
import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

import pandas as pd
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

logger = logging.getLogger(__name__)

_DRIVE_RO_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
_DRIVE_RW_SCOPES = ["https://www.googleapis.com/auth/drive"]


def _parse_utc_timestamp(value: str | None):
    if not value:
        return None
    try:
        parsed = pd.to_datetime(value, utc=True, errors="coerce")
    except Exception:
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _normalize_source_manifest(entry: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(entry, Mapping):
        return {}
    return {
        "last_processed_timestamp": str(entry.get("last_processed_timestamp") or "").strip() or None,
        "row_count": int(entry.get("row_count") or 0),
        "checksum": str(entry.get("checksum") or "").strip() or None,
        "source_file_id": str(entry.get("source_file_id") or "").strip() or None,
    }


def _normalize_manifest_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"sources": {}}

    sources = payload.get("sources")
    if isinstance(sources, Mapping):
        normalized_sources = {
            str(name): _normalize_source_manifest(details)
            for name, details in sources.items()
        }
        return {
            "sources": normalized_sources,
            "last_success_at_utc": str(payload.get("last_success_at_utc") or payload.get("updated_at") or "").strip() or None,
        }

    legacy_entry = _normalize_source_manifest(payload)
    if legacy_entry:
        return {
            "sources": {"sales_csv": legacy_entry},
            "last_success_at_utc": str(payload.get("last_success_at_utc") or payload.get("updated_at") or "").strip() or None,
        }
    return {"sources": {}}


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


class DriveManager:
    """State watcher and manifest persistence for Drive-backed ETL sync."""

    def __init__(self, manifest_file_name: str = "manifest.json") -> None:
        self.manifest_file_name = manifest_file_name

    def _find_manifest_file_id(self, service) -> str | None:
        query = f"name = '{self.manifest_file_name}' and trashed = false"
        response = (
            service.files()
            .list(
                q=query,
                spaces="drive",
                corpora="allDrives",
                fields="files(id,name,modifiedTime)",
                orderBy="modifiedTime desc",
                pageSize=1,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        files = response.get("files", [])
        if not files:
            return None
        file_id = str(files[0].get("id", "")).strip()
        return file_id or None

    def _fetch_source_modified_time(self, service, source_file_id: str) -> str | None:
        metadata = (
            service.files()
            .get(
                fileId=source_file_id,
                fields="modifiedTime",
                supportsAllDrives=True,
            )
            .execute()
        )
        modified = str(metadata.get("modifiedTime", "")).strip()
        return modified or None

    @staticmethod
    def _latest_modified_time(files: list[dict] | None) -> str | None:
        candidates: list[str] = []
        for meta in files or []:
            modified = str(meta.get("modifiedTime") or "").strip()
            if modified:
                candidates.append(modified)
        if not candidates:
            return None
        parsed = [ts for ts in (_parse_utc_timestamp(value) for value in candidates) if ts is not None]
        if not parsed:
            return None
        return max(parsed).isoformat().replace("+00:00", "Z")

    def _load_manifest_state(self, service) -> tuple[dict[str, Any] | None, str | None, str | None]:
        try:
            manifest_file_id = self._find_manifest_file_id(service)
        except Exception:
            logger.warning("Manifest lookup failed in Drive; enabling safe mode full load", exc_info=True)
            return None, None, "manifest_lookup_failed"

        if not manifest_file_id:
            logger.warning("manifest.json not found in Drive; enabling safe mode full load")
            return None, None, "manifest_missing"

        try:
            payload = service.files().get_media(fileId=manifest_file_id, supportsAllDrives=True).execute()
            content = payload.decode("utf-8") if isinstance(payload, (bytes, bytearray)) else str(payload)
            data = json.loads(content)
            if not isinstance(data, dict):
                logger.warning("manifest.json has invalid payload type; enabling safe mode full load")
                return None, manifest_file_id, "manifest_invalid_type"
            return _normalize_manifest_payload(data), manifest_file_id, None
        except Exception:
            logger.warning("manifest.json is inaccessible/corrupted; enabling safe mode full load", exc_info=True)
            return None, manifest_file_id, "manifest_corrupted"

    def check_for_updates(
        self,
        sales_files: list[dict] | None = None,
        production_costs_sheet_id: str | None = None,
    ) -> dict[str, Any]:
        status: dict[str, Any] = {
            "should_process": True,
            "safe_mode": False,
            "reason": "full_load",
            "manifest_file_id": None,
            "manifest": None,
            "sources": {},
        }

        service = _build_drive_service(_DRIVE_RO_SCOPES)
        if service is None:
            status.update({"safe_mode": True, "reason": "drive_unavailable"})
            logger.warning("Drive indisponivel para leitura de manifesto; Modo Seguro (Full Load)")
            return status

        manifest, manifest_file_id, manifest_error = self._load_manifest_state(service)
        status["manifest_file_id"] = manifest_file_id
        status["manifest"] = manifest
        if manifest_error is not None:
            status.update({"safe_mode": True, "reason": manifest_error})
            return status

        manifest_sources = manifest.get("sources", {}) if isinstance(manifest, dict) else {}
        current_sales_modified_time = self._latest_modified_time(sales_files)
        sales_manifest = _normalize_source_manifest(manifest_sources.get("sales_csv"))
        sales_changed = False
        if sales_files:
            sales_current_ts = _parse_utc_timestamp(current_sales_modified_time)
            sales_manifest_ts = _parse_utc_timestamp(sales_manifest.get("last_processed_timestamp"))
            sales_changed = sales_manifest_ts is None or sales_current_ts is None or sales_current_ts > sales_manifest_ts
        status["sources"]["sales_csv"] = {
            "current_modified_time": current_sales_modified_time,
            "previous_modified_time": sales_manifest.get("last_processed_timestamp"),
            "previous_row_count": sales_manifest.get("row_count", 0),
            "previous_checksum": sales_manifest.get("checksum"),
            "changed": sales_changed,
        }

        costs_manifest = _normalize_source_manifest(manifest_sources.get("production_costs_sheets"))
        current_costs_modified_time = None
        if production_costs_sheet_id:
            try:
                current_costs_modified_time = self._fetch_source_modified_time(service, production_costs_sheet_id)
            except Exception:
                status.update({"safe_mode": True, "reason": "source_modified_time_unavailable"})
                logger.warning("Nao foi possivel ler modifiedTime da planilha fonte; Modo Seguro (Full Load)", exc_info=True)
                return status
            if not current_costs_modified_time:
                status.update({"safe_mode": True, "reason": "source_modified_time_empty"})
                logger.warning("modifiedTime da planilha fonte veio vazio; Modo Seguro (Full Load)")
                return status

        costs_current_ts = _parse_utc_timestamp(current_costs_modified_time)
        costs_manifest_ts = _parse_utc_timestamp(costs_manifest.get("last_processed_timestamp"))
        costs_changed = bool(production_costs_sheet_id) and (
            costs_manifest_ts is None or costs_current_ts is None or costs_current_ts > costs_manifest_ts
        )
        status["sources"]["production_costs_sheets"] = {
            "current_modified_time": current_costs_modified_time,
            "previous_modified_time": costs_manifest.get("last_processed_timestamp"),
            "previous_row_count": costs_manifest.get("row_count", 0),
            "previous_checksum": costs_manifest.get("checksum"),
            "changed": costs_changed,
            "source_file_id": production_costs_sheet_id,
        }
        logger.info(
            "[AUDIT][GATE_STATE] sales_current=%s sales_manifest=%s costs_current=%s costs_manifest=%s",
            current_sales_modified_time,
            sales_manifest.get("last_processed_timestamp"),
            current_costs_modified_time,
            costs_manifest.get("last_processed_timestamp"),
        )

        if not sales_changed and not costs_changed:
            logger.info("Sync desnecessario: a planilha nao foi modificada desde o ultimo processamento")
            logger.info("[AUDIT][GATE_DECISION] should_process=false reason=unchanged_since_last_processed")
            status.update({"should_process": False, "reason": "unchanged_since_last_processed"})
            return status

        status.update({"should_process": True, "reason": "sources_updated"})
        logger.info(
            "Fonte(s) atualizada(s): sales_csv=%s production_costs_sheets=%s; processamento sera executado",
            sales_changed,
            costs_changed,
        )
        logger.info("[AUDIT][GATE_DECISION] should_process=true reason=sources_updated")
        return status

    @staticmethod
    def compute_manifest_checksum(payload: dict[str, Any]) -> str:
        content = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        return sha256(content.encode("utf-8")).hexdigest()

    def update_manifest_state(
        self,
        source_states: Mapping[str, Mapping[str, Any]],
        manifest_file_id: str | None = None,
    ) -> bool:
        service = _build_drive_service(_DRIVE_RW_SCOPES)
        if service is None:
            logger.warning("Drive indisponivel para atualizar manifesto")
            return False

        if not manifest_file_id:
            try:
                manifest_file_id = self._find_manifest_file_id(service)
            except Exception:
                logger.warning("Falha ao buscar manifest.json para update", exc_info=True)
                manifest_file_id = None

        existing_manifest = {"sources": {}}
        if manifest_file_id:
            try:
                payload = service.files().get_media(fileId=manifest_file_id, supportsAllDrives=True).execute()
                content = payload.decode("utf-8") if isinstance(payload, (bytes, bytearray)) else str(payload)
                existing_manifest = _normalize_manifest_payload(json.loads(content))
            except Exception:
                existing_manifest = {"sources": {}}

        merged_sources = dict(existing_manifest.get("sources", {}))
        for source_name, details in source_states.items():
            if not isinstance(details, Mapping):
                continue
            normalized = _normalize_source_manifest(details)
            if str(source_name) == "production_costs_sheets":
                unique_ids = details.get("unique_product_ids")
                if unique_ids is not None:
                    normalized["row_count"] = int(unique_ids)
            merged_sources[str(source_name)] = normalized

        payload = {
            "last_success_at_utc": datetime.now(timezone.utc).isoformat(),
            "sources": merged_sources,
        }

        blob = io.BytesIO(json.dumps(payload, ensure_ascii=True, indent=2).encode("utf-8"))
        blob.seek(0)
        media = MediaIoBaseUpload(blob, mimetype="application/json", resumable=False)

        try:
            if manifest_file_id:
                service.files().update(
                    fileId=manifest_file_id,
                    media_body=media,
                    supportsAllDrives=True,
                ).execute()
            else:
                metadata = {"name": self.manifest_file_name, "mimeType": "application/json"}
                service.files().create(
                    body=metadata,
                    media_body=media,
                    fields="id",
                    supportsAllDrives=True,
                ).execute()
            return True
        except Exception:
            logger.warning("Falha ao atualizar manifest.json no Drive", exc_info=True)
            return False


@st.cache_resource
def get_drive_assets_map() -> dict[str, str]:
    """Discover parquet assets in the configured Drive scope."""
    service = _build_drive_service(_DRIVE_RO_SCOPES)
    if service is None:
        return {}

    query = "name contains '.parquet' and trashed = false"
    page_token = None
    assets: dict[str, str] = {}

    while True:
        response = (
            service.files()
            .list(
                q=query,
                spaces="drive",
                corpora="allDrives",
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


@st.cache_data(ttl=120)
def load_parquet_from_drive(file_name: str) -> pd.DataFrame:
    """Load one parquet file directly from Drive into memory."""
    file_id = get_drive_assets_map().get(file_name)
    if not file_id:
        return pd.DataFrame()

    service = _build_drive_service(_DRIVE_RO_SCOPES)
    if service is None:
        return pd.DataFrame()

    content = service.files().get_media(fileId=file_id, supportsAllDrives=True).execute()
    dataframe = pd.read_parquet(io.BytesIO(content))
    if file_name == "gold_rentabilidade.parquet":
        if dataframe.empty:
            logger.warning("DEBUG RENTABILIDADE: arquivo %s no Drive retornou dataframe vazio", file_name)
        else:
            logger.info("DEBUG RENTABILIDADE: arquivo %s carregado com %d linha(s)", file_name, len(dataframe))
    return dataframe


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
    # Ensure subsequent reads do not return stale cached frames.
    get_drive_assets_map.clear()
    load_parquet_from_drive.clear()
    return True

