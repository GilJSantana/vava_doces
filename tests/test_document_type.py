from __future__ import annotations

from collections.abc import Iterator, Mapping

import pytest

import src.infrastructure.google_oauth2_adapter as google_oauth2_adapter


class MappingLikeSecret(Mapping[str, str]):
    def __init__(self, data: dict[str, str]) -> None:
        self._data = data

    def __getitem__(self, key: str) -> str:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)


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


def test_load_service_account_info_casts_mapping_like_secret_to_plain_dict(monkeypatch) -> None:
    mapping_secret = MappingLikeSecret(_service_account_info())
    monkeypatch.setattr(
        google_oauth2_adapter.st,
        "secrets",
        {"gcp_service_account": mapping_secret},
        raising=False,
    )

    loaded = google_oauth2_adapter.GoogleDrivePermissionChecker._load_service_account_info()

    assert loaded == _service_account_info()
    assert type(loaded) is dict


def test_load_service_account_info_rejects_empty_secret(monkeypatch) -> None:
    monkeypatch.setattr(
        google_oauth2_adapter.st,
        "secrets",
        {"gcp_service_account": {}},
        raising=False,
    )

    with pytest.raises(ValueError, match="empty"):
        google_oauth2_adapter.GoogleDrivePermissionChecker._load_service_account_info()

