import pandas as pd
from decimal import Decimal, InvalidOperation
from typing import Dict, Iterable, Optional
import re
from src.ports.data_source import DataSource, DataSourceError

class CostAnalysisService:
    def __init__(self, data_source: DataSource):
        self.data_source = data_source

    def get_products_data(self) -> pd.DataFrame:
        """
        Retrieves the product-ingredient join data from the 'Produtos' sheet.
        """
        return self.data_source.get_data("Produtos")

    def get_production_costs(self) -> pd.DataFrame:
        """
        Compatibility alias for production costs. Uses 'Produtos' sheet.
        """
        return self.get_products_data()

    def get_sales_data(self) -> pd.DataFrame:
        """
        Retrieves sales data from the 'Vendas Diarias' sheet.
        """
        return self.data_source.get_data("Vendas Diarias")

    def _find_column(self, columns: Iterable[str], candidates: Iterable[str]) -> Optional[str]:
        lower_map = {c.lower(): c for c in columns}
        for candidate in candidates:
            if candidate.lower() in lower_map:
                return lower_map[candidate.lower()]
        return None

    def _parse_decimal(self, value) -> Optional[Decimal]:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        text = str(value).strip()
        if not text:
            return None
        # Normalize currency/number formats like "R$ 6,79" or "6,79"
        text = re.sub(r"[^0-9,.-]", "", text)
        if text.count(",") > 0 and text.count(".") > 0:
            text = text.replace(".", "")
        text = text.replace(",", ".")
        try:
            return Decimal(text)
        except (InvalidOperation, TypeError):
            return None

    def calculate_cost_per_product(self, sheet_name: str = "Produtos") -> Dict[str, Decimal]:
        """
        Loads rows from the given sheet and calculates total cost per product.

        Expected minimal columns in the sheet (case-insensitive):
        - nome do produto (product name)
        - quantidade por produto (qty per product)
        - custo unitário (unit cost)

        Returns a dict mapping product name -> total cost (Decimal).
        Raises ValueError for missing columns.
        """
        try:
            df = self.data_source.get_data(sheet_name)
        except DataSourceError:
            raise

        if df is None or df.empty:
            return {}

        product_col = self._find_column(df.columns, ["Nome do Produto", "ProductName", "product_name", "Nome Produto"])
        qty_col = self._find_column(df.columns, ["Quantidade por Produto", "QtyPerProduct", "qty", "quantidade", "Quantidade"])
        cost_col = self._find_column(df.columns, ["Custo Unitário", "UnitCost", "unit_price", "Custo Unitario"])

        if not product_col or not qty_col or not cost_col:
            raise ValueError("Sheet is missing required columns for product cost calculation")

        results: Dict[str, Decimal] = {}

        for _, row in df.iterrows():
            product = row[product_col]
            if pd.isna(product) or str(product).strip() == "":
                continue

            qty = self._parse_decimal(row[qty_col])
            unit_cost = self._parse_decimal(row[cost_col])
            if qty is None or unit_cost is None:
                continue

            total = qty * unit_cost
            results[product] = results.get(product, Decimal("0")) + total

        return results

    def calculate_cost_per_recipe(self, sheet_name: str) -> Dict[str, Decimal]:
        """
        Legacy method kept for backward compatibility with older sheets.
        Prefer calculate_cost_per_product with the 'Produtos' sheet.
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

