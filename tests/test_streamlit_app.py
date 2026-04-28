from __future__ import annotations

import app


def test_get_adapter_uses_sheet_id_from_streamlit_secrets(monkeypatch) -> None:
	captured: dict[str, object] = {}

	class DummyAdapter:
		def __init__(self, credential_file: str | None, sheet_id: str | None) -> None:
			captured["credential_file"] = credential_file
			captured["sheet_id"] = sheet_id

	monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)
	monkeypatch.setattr(app, "GoogleSheetsAdapter", DummyAdapter)
	monkeypatch.setattr(app.st, "secrets", {"GOOGLE_SHEET_ID": "sheet-secret"}, raising=False)

	adapter = app.get_adapter.__wrapped__()

	assert isinstance(adapter, DummyAdapter)
	assert captured == {"credential_file": None, "sheet_id": "sheet-secret"}


def test_get_adapter_returns_none_and_reports_error_on_failure(monkeypatch) -> None:
	messages: list[str] = []

	def failing_adapter(*args, **kwargs):
		raise RuntimeError("boom")

	monkeypatch.setattr(app, "GoogleSheetsAdapter", failing_adapter)
	monkeypatch.setattr(app.st, "secrets", {"GOOGLE_SHEET_ID": "sheet-secret"}, raising=False)
	monkeypatch.setattr(app.st, "error", lambda message: messages.append(message))

	adapter = app.get_adapter.__wrapped__()

	assert adapter is None
	assert messages == ["❌ Erro ao conectar com Google Sheets: boom"]

