"""
Serviço para análise de produtos com integração da receita, matéria prima e vendas.
Consolida dados das abas Receita e Matéria Prima para apresentação no Streamlit.
"""

import pandas as pd
from decimal import Decimal
from typing import Dict, Optional, Tuple
from src.ports.data_source import DataSource, DataSourceError


class ProductAnalysisService:
    """
    Serviço que integra dados de Receita, Matéria Prima e Produtos
    para análise consolidada de custos e impacto no faturamento.
    """

    def __init__(self, data_source: DataSource):
        self.data_source = data_source
        self._cache_receita = None
        self._cache_materia_prima = None
        self._cache_produtos = None

    def _get_receita_data(self) -> Optional[pd.DataFrame]:
        """Carrega dados da aba Receita com cache."""
        if self._cache_receita is None:
            try:
                self._cache_receita = self.data_source.get_data("Receita")
            except DataSourceError:
                return None
        return self._cache_receita

    def _get_materia_prima_data(self) -> Optional[pd.DataFrame]:
        """Carrega dados da aba Matéria Prima com cache."""
        if self._cache_materia_prima is None:
            try:
                self._cache_materia_prima = self.data_source.get_data("Matéria Prima")
            except DataSourceError:
                return None
        return self._cache_materia_prima

    def _get_produtos_data(self) -> Optional[pd.DataFrame]:
        """Carrega dados da aba Produtos com cache."""
        if self._cache_produtos is None:
            try:
                self._cache_produtos = self.data_source.get_data("Produtos")
            except DataSourceError:
                return None
        return self._cache_produtos

    def _find_column(self, df: pd.DataFrame, candidates: list) -> Optional[str]:
        """Encontra coluna case-insensitive."""
        if df is None:
            return None
        lower_map = {c.lower(): c for c in df.columns}
        for candidate in candidates:
            if candidate.lower() in lower_map:
                return lower_map[candidate.lower()]
        return None

    def get_product_cost_breakdown(self) -> pd.DataFrame:
        """
        Retorna um DataFrame consolidado com:
        - Nome do Produto
        - Ingredientes e quantidades
        - Custo total de produção
        """
        receita_df = self._get_receita_data()
        if receita_df is None or receita_df.empty:
            return pd.DataFrame()

        # Identificar colunas
        product_col = self._find_column(receita_df, ["Nome do Produto", "product_name"])
        ingredient_col = self._find_column(receita_df, ["Nome do Ingrediente", "ingredient_name"])
        qty_col = self._find_column(receita_df, ["Quantidade por Produto", "qty"])
        cost_col = self._find_column(receita_df, ["Custo Unitário", "unit_cost"])

        if not all([product_col, ingredient_col, qty_col, cost_col]):
            return pd.DataFrame()

        # Criar DataFrame consolidado
        receita_df["Custo do Ingrediente"] = pd.to_numeric(
            receita_df[cost_col].astype(str).str.replace("R$", "").str.replace(",", "."),
            errors="coerce"
        ) * pd.to_numeric(receita_df[qty_col], errors="coerce")

        return receita_df[[product_col, ingredient_col, qty_col, cost_col, "Custo do Ingrediente"]]

    def get_product_cost_summary(self) -> pd.DataFrame:
        """
        Retorna resumo de custos por produto:
        - Nome do Produto
        - Custo Total
        - Quantidade de Ingredientes
        """
        receita_df = self._get_receita_data()
        if receita_df is None or receita_df.empty:
            return pd.DataFrame()

        product_col = self._find_column(receita_df, ["Nome do Produto", "product_name"])
        cost_col = self._find_column(receita_df, ["Custo Unitário", "unit_cost"])
        qty_col = self._find_column(receita_df, ["Quantidade por Produto", "qty"])

        if not all([product_col, cost_col, qty_col]):
            return pd.DataFrame()

        # Converter custos para float
        receita_df["Custo Calc"] = pd.to_numeric(
            receita_df[cost_col].astype(str).str.replace("R$", "").str.replace(",", "."),
            errors="coerce"
        ) * pd.to_numeric(receita_df[qty_col], errors="coerce")

        # Agrupar por produto
        summary = receita_df.groupby(product_col).agg({
            "Custo Calc": "sum",
            cost_col: "count"  # Número de ingredientes
        }).reset_index()

        summary.columns = ["Produto", "Custo Total (R$)", "Qtd Ingredientes"]

        return summary.sort_values("Custo Total (R$)", ascending=False)

    def get_products_with_sales_impact(self) -> pd.DataFrame:
        """
        Retorna produtos com informações comerciais:
        - Nome do Produto
        - Categoria
        - Preço de Venda
        - Custo de Produção (calculado)
        - Margem (%)
        - Margem Bruta (R$)
        """
        produtos_df = self._get_produtos_data()
        if produtos_df is None or produtos_df.empty:
            return pd.DataFrame()

        return produtos_df

    def calculate_total_cost_per_product(self) -> Dict[str, Decimal]:
        """
        Calcula o custo total de produção para cada produto
        baseado na aba Receita (ingredientes + quantidades).
        """
        receita_df = self._get_receita_data()
        if receita_df is None or receita_df.empty:
            return {}

        product_col = self._find_column(receita_df, ["Nome do Produto", "product_name"])
        cost_col = self._find_column(receita_df, ["Custo Unitário", "unit_cost"])
        qty_col = self._find_column(receita_df, ["Quantidade por Produto", "qty"])

        if not all([product_col, cost_col, qty_col]):
            return {}

        results = {}

        for _, row in receita_df.iterrows():
            product = row[product_col]
            if pd.isna(product):
                continue

            # Converter strings para números
            try:
                cost_str = str(row[cost_col]).replace("R$", "").strip()
                qty_str = str(row[qty_col]).strip()

                cost = float(cost_str.replace(",", "."))
                qty = float(qty_str.replace(",", "."))

                total = cost * qty

                if product in results:
                    results[product] += total
                else:
                    results[product] = total
            except (ValueError, TypeError):
                continue

        return {k: Decimal(str(v)) for k, v in results.items()}

    def get_ingredients_list(self) -> pd.DataFrame:
        """Retorna lista de matéria prima disponível."""
        materia_df = self._get_materia_prima_data()
        if materia_df is None or materia_df.empty:
            return pd.DataFrame()

        return materia_df

