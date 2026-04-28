from __future__ import annotations

import pytest

import src.infrastructure.google_drive_adapter as google_drive_adapter


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


def test_build_drive_credentials_uses_streamlit_secret_and_expected_scopes(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeBaseCredentials:
        def with_scopes(self, scopes: list[str]) -> tuple[str, tuple[str, ...]]:
            captured["scopes"] = list(scopes)
            return ("scoped", tuple(scopes))

    class FakeCredentialsClass:
        @staticmethod
        def from_service_account_info(info: dict[str, str]) -> FakeBaseCredentials:
            captured["info"] = info
            return FakeBaseCredentials()

    monkeypatch.setattr(
        google_drive_adapter.st,
        "secrets",
        {"gcp_service_account": _service_account_info()},
        raising=False,
    )
    monkeypatch.setattr(
        google_drive_adapter.service_account,
        "Credentials",
        FakeCredentialsClass,
    )

    result = google_drive_adapter.build_drive_credentials()

    assert result == ("scoped", tuple(google_drive_adapter._DRIVE_SCOPES))
    assert captured["info"] == _service_account_info()
    assert captured["scopes"] == google_drive_adapter._DRIVE_SCOPES


def test_build_drive_credentials_requires_service_account_secret(monkeypatch) -> None:
    monkeypatch.setattr(google_drive_adapter.st, "secrets", {}, raising=False)

    with pytest.raises(ValueError, match="gcp_service_account"):
        google_drive_adapter.build_drive_credentials()
