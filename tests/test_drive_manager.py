import src.infrastructure.drive_manager as drive_manager


class _FakeRequest:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        return self._payload


class _FakeFiles:
    def __init__(self, payloads):
        self._payloads = payloads
        self.calls = []

    def list(self, **kwargs):
        self.calls.append(kwargs)
        idx = len(self.calls) - 1
        return _FakeRequest(self._payloads[idx])


class _FakeService:
    def __init__(self, payloads):
        self._files = _FakeFiles(payloads)

    def files(self):
        return self._files


def test_get_drive_assets_map_uses_all_drives_flags_and_maps_assets(monkeypatch):
    payloads = [
        {
            "nextPageToken": "next-token",
            "files": [
                {"id": "id-a", "name": "custos_producao.parquet", "modifiedTime": "2026-04-28T00:00:00Z"},
                {"id": "", "name": "invalid-no-id.parquet", "modifiedTime": "2026-04-28T00:00:00Z"},
            ],
        },
        {
            "files": [
                {"id": "id-b", "name": "custos_producao.parquet", "modifiedTime": "2026-04-27T00:00:00Z"},
                {"id": "id-c", "name": "fato_vendas.parquet", "modifiedTime": "2026-04-27T00:00:00Z"},
                {"id": "id-d", "name": "", "modifiedTime": "2026-04-27T00:00:00Z"},
            ]
        },
    ]

    fake_service = _FakeService(payloads)
    monkeypatch.setattr(drive_manager, "_build_drive_service", lambda _scopes: fake_service)

    # Use undecorated function body to keep test deterministic and independent from Streamlit cache state.
    result = drive_manager.get_drive_assets_map.__wrapped__()

    assert result == {
        "custos_producao.parquet": "id-a",
        "fato_vendas.parquet": "id-c",
    }

    assert len(fake_service._files.calls) == 2

    first_call = fake_service._files.calls[0]
    assert first_call["q"] == "name contains '.parquet' and trashed = false"
    assert first_call["corpora"] == "allDrives"
    assert first_call["supportsAllDrives"] is True
    assert first_call["includeItemsFromAllDrives"] is True

    second_call = fake_service._files.calls[1]
    assert second_call["pageToken"] == "next-token"

