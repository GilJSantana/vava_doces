import pandas as pd
from decimal import Decimal

from src.domain.cost_analysis_service import CostAnalysisService
from src.ports.data_source import DataSource


class FakeDataSource(DataSource):
    def __init__(self, df: pd.DataFrame):
        self._df = df

    def get_data(self, sheet_name: str) -> pd.DataFrame:
        return self._df


def test_calculate_cost_per_recipe_happy_path():
    # Arrange: construct a dataframe with expected columns
    df = pd.DataFrame([
        {"recipe": "Brigadeiro", "ingredient": "Chocolate", "qty": 2, "unit_price": 3.5},
        {"recipe": "Brigadeiro", "ingredient": "Leite Condensado", "qty": 1, "unit_price": 4.0},
        {"recipe": "Beijinho", "ingredient": "Coco", "qty": 1.5, "unit_price": 2.0},
    ])

    service = CostAnalysisService(FakeDataSource(df))

    # Act
    result = service.calculate_cost_per_recipe("Custos")

    # Assert
    assert isinstance(result, dict)
    assert result["Brigadeiro"] == Decimal("2") * Decimal("3.5") + Decimal("1") * Decimal("4.0")
    assert result["Beijinho"] == Decimal("1.5") * Decimal("2.0")


def test_calculate_cost_per_recipe_empty_sheet_returns_empty_dict():
    df = pd.DataFrame([])
    service = CostAnalysisService(FakeDataSource(df))

    result = service.calculate_cost_per_recipe("Custos")
    assert result == {}


def test_calculate_cost_per_recipe_missing_columns_raises_value_error():
    df = pd.DataFrame([{"nome": "Brigadeiro"}])
    service = CostAnalysisService(FakeDataSource(df))

    try:
        service.calculate_cost_per_recipe("Custos")
        assert False, "Expected ValueError due to missing columns"
    except ValueError as e:
        assert "missing required column" in str(e)
