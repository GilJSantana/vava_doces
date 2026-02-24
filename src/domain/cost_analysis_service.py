import pandas as pd
from decimal import Decimal, InvalidOperation
from typing import Dict
from src.ports.data_source import DataSource, DataSourceError

class CostAnalysisService:
    def __init__(self, data_source: DataSource):
        self.data_source = data_source

    def get_production_costs(self) -> pd.DataFrame:
        """
        Retrieves the production cost data (DataFrame) from the 'Custos' sheet.
        """
        return self.data_source.get_data("Custos")

    def get_sales_data(self) -> pd.DataFrame:
        """
        Retrieves sales/billing data from the 'Faturamento' sheet.
        """
        return self.data_source.get_data("Faturamento")

    def calculate_cost_per_recipe(self, sheet_name: str) -> Dict[str, Decimal]:
        """
        Loads rows from the given sheet and calculates total cost per recipe.

        Expected minimal columns in the sheet (case-insensitive):
        - recipe (nome da receita)
        - ingredient (nome do ingrediente)
        - qty (quantidade usada)
        - unit_price (preço unitário)

        Returns a dict mapping recipe name -> total cost (Decimal).
        Raises ValueError for invalid/missing data.
        """
        try:
            df = self.data_source.get_data(sheet_name)
        except DataSourceError:
            # propagate as-is for caller to handle
            raise

        if df is None or df.empty:
            return {}

        # Normalize column names to lowercase
        df_columns = {c.lower(): c for c in df.columns}
        required = ["recipe", "qty", "unit_price"]
        for col in required:
            if col not in df_columns:
                raise ValueError(f"Sheet '{sheet_name}' is missing required column '{col}'")

        # Use the original column names to access values
        recipe_col = df_columns["recipe"]
        qty_col = df_columns["qty"]
        price_col = df_columns["unit_price"]

        results: Dict[str, Decimal] = {}

        for _, row in df.iterrows():
            recipe = row[recipe_col]
            if pd.isna(recipe):
                continue

            try:
                qty = Decimal(str(row[qty_col]))
                unit_price = Decimal(str(row[price_col]))
            except (InvalidOperation, TypeError) as e:
                raise ValueError(f"Invalid numeric value in row for recipe '{recipe}': {e}")

            total = qty * unit_price
            results[recipe] = results.get(recipe, Decimal("0")) + total

        return results

