from __future__ import annotations

import pandas as pd

from src.infrastructure.google_drive_adapter import (
    GoogleDriveAdapter,
    _manual_sheet_alias,
    _sheet_values_to_dataframe,
)


class _FakeDriveService:
    def __init__(self, list_response: dict, metadata_by_id: dict[str, dict]):
        self._list_response = list_response
        self._metadata_by_id = metadata_by_id

    def files(self):
        return self

    def list(self, **_kwargs):
        return self

    def get(self, fileId: str, **_kwargs):
        self._selected_id = fileId
        return self

    def execute(self):
        if hasattr(self, "_selected_id"):
            return self._metadata_by_id[self._selected_id]
        return self._list_response


class _FakeSheetsService:
    def __init__(self, tabs_by_sheet_id: dict[str, list[str]], values_payload: dict[str, list[list[str]]]):
        self._tabs_by_sheet_id = tabs_by_sheet_id
        self._values_payload = values_payload

    def spreadsheets(self):
        return self

    def get(self, spreadsheetId: str, **_kwargs):
        self._spreadsheet_id = spreadsheetId
        self._mode = "meta"
        return self

    def values(self):
        return self

    def get_value(self, spreadsheetId: str, range: str, **_kwargs):
        self._spreadsheet_id = spreadsheetId
        self._range = range
        self._mode = "values"
        return self

    # google client uses values().get(...), so expose get with routing by kwargs
    def get(self, spreadsheetId: str, **kwargs):  # type: ignore[override]
        if "range" in kwargs:
            self._spreadsheet_id = spreadsheetId
            self._range = kwargs["range"]
            self._mode = "values"
        else:
            self._spreadsheet_id = spreadsheetId
            self._mode = "meta"
        return self

    def execute(self):
        if self._mode == "meta":
            tabs = self._tabs_by_sheet_id.get(self._spreadsheet_id, [])
            return {"sheets": [{"properties": {"title": t}} for t in tabs]}
        key = f"{self._spreadsheet_id}:{self._range}"
        return {"values": self._values_payload.get(key, [])}


def _make_adapter(drive_service, sheets_service, manual_sheet_id: str | None = None) -> GoogleDriveAdapter:
    adapter = object.__new__(GoogleDriveAdapter)
    adapter._credential_file = ""
    adapter._folder_id = "folder-1"
    adapter._service = drive_service
    adapter._sheets_service = sheets_service
    adapter._manual_sheet_id = manual_sheet_id
    return adapter


def test_manual_sheet_alias_supports_accented_titles() -> None:
    assert _manual_sheet_alias("Matéria Prima") == "materia_prima"
    assert _manual_sheet_alias("Receitas") == "receitas"
    assert _manual_sheet_alias("Produtos") == "produtos"


def test_list_tabular_files_includes_manual_sheet_tabs() -> None:
    drive = _FakeDriveService(
        list_response={
            "files": [
                {"id": "1", "name": "sales_data_01_2026.csv", "mimeType": "text/csv", "modifiedTime": "2026-04-01T00:00:00Z"},
                {"id": "2", "name": "sales_data_02_2026.csv", "mimeType": "text/csv", "modifiedTime": "2026-04-02T00:00:00Z"},
                {"id": "3", "name": "sales_data_03_2026.csv", "mimeType": "text/csv", "modifiedTime": "2026-04-03T00:00:00Z"},
            ]
        },
        metadata_by_id={
            "sheet-123": {
                "id": "sheet-123",
                "name": "Controle de Custos",
                "mimeType": "application/vnd.google-apps.spreadsheet",
                "modifiedTime": "2026-05-05T18:40:00Z",
            }
        },
    )
    sheets = _FakeSheetsService(
        tabs_by_sheet_id={"sheet-123": ["Produtos", "Receitas", "Matéria Prima", "Resumo"]},
        values_payload={},
    )
    adapter = _make_adapter(drive, sheets, manual_sheet_id="sheet-123")

    files = adapter.list_tabular_files()
    names = [f["name"] for f in files]

    assert "sales_data_01_2026.csv" in names
    assert "manual_produtos.csv" in names
    assert "manual_receitas.csv" in names
    assert "manual_materia_prima.csv" in names


def test_read_as_dataframe_builds_frame_from_sheet_values() -> None:
    drive = _FakeDriveService(list_response={"files": []}, metadata_by_id={})
    sheets = _FakeSheetsService(
        tabs_by_sheet_id={},
        values_payload={
            "sheet-123:'Receitas'": [
                ["ID do Produto", "ID do Ingrediente", "Quantidade"],
                ["PROD-001", "ING-001", "60"],
                ["PROD-001", "ING-002", "40"],
            ]
        },
    )
    adapter = _make_adapter(drive, sheets, manual_sheet_id="sheet-123")

    df = adapter.read_as_dataframe(
        {
            "id": "sheet-123",
            "name": "manual_receitas.csv",
            "mimeType": "application/vnd.google-apps.spreadsheet",
            "sheetName": "Receitas",
        }
    )

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert list(df.columns) == ["ID do Produto", "ID do Ingrediente", "Quantidade"]


def test_sheet_values_to_dataframe_handles_ragged_rows() -> None:
    df = _sheet_values_to_dataframe(
        [
            ["a", "b", "c"],
            ["1", "2"],
        ]
    )
    assert len(df) == 1
    assert list(df.iloc[0]) == ["1", "2", ""]

