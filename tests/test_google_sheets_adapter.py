from unittest.mock import MagicMock
import pandas as pd
from src.infrastructure.google_sheets_adapter import GoogleSheetsAdapter

def test_get_data_returns_dataframe():
    # Arrange
    mock_gspread_client = MagicMock()
    mock_sheet = MagicMock()
    mock_worksheet = MagicMock()
    
    # Mock the return value of get_all_records to be a list of dicts
    expected_data = [{"col1": "val1", "col2": "val2"}]
    mock_worksheet.get_all_records.return_value = expected_data
    
    mock_sheet.worksheet.return_value = mock_worksheet
    mock_gspread_client.open_by_key.return_value = mock_sheet
    
    adapter = GoogleSheetsAdapter(credential_file="dummy.json", sheet_id="dummy_id")
    # Inject the mock client directly to avoid real authentication during test
    adapter.client = mock_gspread_client

    # Act
    df = adapter.get_data("Sheet1")

    # Assert
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert df.iloc[0]["col1"] == "val1"
    mock_gspread_client.open_by_key.assert_called_with("dummy_id")
    mock_sheet.worksheet.assert_called_with("Sheet1")


def test_get_data_reuses_cached_sheet_data():
    mock_gspread_client = MagicMock()
    mock_sheet = MagicMock()
    mock_worksheet = MagicMock()

    expected_data = [{"col1": "val1", "col2": "val2"}]
    mock_worksheet.get_all_records.return_value = expected_data

    mock_sheet.worksheet.return_value = mock_worksheet
    mock_gspread_client.open_by_key.return_value = mock_sheet

    adapter = GoogleSheetsAdapter(credential_file="dummy.json", sheet_id="dummy_id")
    adapter.client = mock_gspread_client

    first_df = adapter.get_data("Sheet1")
    second_df = adapter.get_data("Sheet1")

    assert isinstance(first_df, pd.DataFrame)
    assert isinstance(second_df, pd.DataFrame)
    assert first_df.equals(second_df)
    mock_gspread_client.open_by_key.assert_called_once_with("dummy_id")
    mock_sheet.worksheet.assert_called_once_with("Sheet1")
    mock_worksheet.get_all_records.assert_called_once()


