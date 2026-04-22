import pandas as pd

from scripts.medallion_pipeline import clean_cost_sheet


def test_clean_cost_sheet_normalizes_strings_and_financial_values():
    raw = pd.DataFrame(
        {
            " Item ": [" ING-001 ", "ING-002"],
            " Custo Unitario ": ["R$ 1.234,56", " 10,00 "],
            " Margem ": [" 15% ", ""],
            "Nome": [" Brigadeiro ", " Beijinho"],
        }
    )

    col_map = {
        "item": "item",
        "custo unitario": "custo_unit",
        "margem": "margem",
        "nome": "nome",
    }

    cleaned = clean_cost_sheet(raw, col_map)

    assert "item" in cleaned.columns
    assert "custo_unit" in cleaned.columns
    assert "margem" in cleaned.columns
    assert cleaned.loc[0, "item"] == "ING-001"
    assert cleaned.loc[0, "nome"] == "Brigadeiro"
    assert cleaned.loc[0, "custo_unit"] == 1234.56
    assert cleaned.loc[1, "custo_unit"] == 10.0
    assert cleaned.loc[0, "margem"] == 15.0
    assert cleaned.loc[1, "margem"] == 0.0

