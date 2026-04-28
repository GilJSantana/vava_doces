from __future__ import annotations

import pytest

import src.infrastructure.google_sheets_adapter as google_sheets_adapter
from src.infrastructure.google_sheets_adapter import GoogleSheetsAdapter, _fetch_values_cached
from src.ports.data_source import DataSourceError


def _service_account_info() -> dict[str, str]:
    return {
        "type": "service_account",
        "project_id": "demo-project",
        "private_key_id": "key-id",
        "private_key": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----\n",
        "client_email": "svc@example.iam.gserviceaccount.com",
        "client_id": "1234567890",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/svc",
    }


def test_google_sheets_adapter_client_builds_from_streamlit_secrets(monkeypatch) -> None:
    service_account_info = _service_account_info()
    captured: dict[str, object] = {}
    fake_client = object()

    monkeypatch.setattr(
        google_sheets_adapter.st,
        "secrets",
        {"gcp_service_account": service_account_info},
        raising=False,
    )

    def fake_service_account_from_dict(info: dict[str, str]) -> object:
        captured["info"] = info
        return fake_client

    monkeypatch.setattr(
        google_sheets_adapter.gspread,
        "service_account_from_dict",
        fake_service_account_from_dict,
    )

    adapter = GoogleSheetsAdapter(sheet_id="sheet-123")

    assert adapter.client is fake_client
    assert captured["info"] == service_account_info


def test_fetch_values_cached_requires_service_account_secret(monkeypatch) -> None:
    monkeypatch.setattr(google_sheets_adapter.st, "secrets", {}, raising=False)

    with pytest.raises(DataSourceError, match="gcp_service_account"):
        _fetch_values_cached.__wrapped__(None, "sheet-123", "Sheet1", None)

