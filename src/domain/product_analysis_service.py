"""
Serviço para análise de produtos com integração da receita, matéria-prima e vendas.
Consolida dados das abas Receita, Matéria Prima e Produtos para apresentação no Streamlit.
"""

from decimal import Decimal
from typing import Dict, Optional
import unicodedata

import pandas as pd

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
        self._receita_loaded = False
        self._materia_prima_loaded = False
        self._produtos_loaded = False
        self._cache_recipe_cost_base = None
        self._cache_product_cost_breakdown = None
        self._cache_product_cost_summary = None
        self._cache_products_with_sales_impact = None
        self._cache_recipe_cost_issues = None

    def _copy_df(self, df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
        """Retorna cópia defensiva do DataFrame cacheado."""
        if df is None:
            return None
        return df.copy()

    def _load_first_sheet(self, sheet_names: list[str]) -> Optional[pd.DataFrame]:
        """Tenta carregar a primeira aba existente da lista."""
        for name in sheet_names:
            try:
                return self.data_source.get_data(name)
            except DataSourceError:
                continue
        return None

    def _get_receita_data(self) -> Optional[pd.DataFrame]:
        """Carrega dados da aba Receita com cache por instância do serviço."""
        if not self._receita_loaded:
            self._cache_receita = self._load_first_sheet(["Receita", "Receitas", "BOM - Receitas"])
            self._receita_loaded = True
        return self._copy_df(self._cache_receita)

    def _get_materia_prima_data(self) -> Optional[pd.DataFrame]:
        """Carrega dados da aba Matéria Prima com cache por instância do serviço."""
        if not self._materia_prima_loaded:
            self._cache_materia_prima = self._load_first_sheet(
                ["Matéria Prima", "Materia Prima", "Matria Prima", "Insumos"]
            )
            self._materia_prima_loaded = True
        return self._copy_df(self._cache_materia_prima)

    def _get_produtos_data(self) -> Optional[pd.DataFrame]:
        """Carrega dados da aba Produtos com cache por instância do serviço."""
        if not self._produtos_loaded:
            self._cache_produtos = self._load_first_sheet(["Produtos", "Cadastro de Produtos", "Produto"])
            self._produtos_loaded = True
        return self._copy_df(self._cache_produtos)

    def _find_column(self, df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
        """Encontra coluna por comparação normalizada (acentos, espaços e underscores)."""
        if df is None:
            return None
        normalized_map = {self._normalize_text(c): c for c in df.columns}
        for candidate in candidates:
            match = normalized_map.get(self._normalize_text(candidate))
            if match:
                return match
        return None

    def _normalize_text(self, value: str) -> str:
        text = str(value or "").strip().lower().replace("_", " ")
        text = unicodedata.normalize("NFD", text)
        text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
        return "".join(ch for ch in text if ch.isalnum())

    def _to_numeric_series(self, series: pd.Series) -> pd.Series:
        """Converte moeda/texto para número float de forma tolerante."""
        text = series.astype(str).str.strip()
        text = text.replace({"": None, "nan": None, "None": None})
        text = text.str.replace(r"[^0-9,.-]", "", regex=True)
        has_comma = text.str.contains(",", na=False)
        has_dot = text.str.contains(r"\.", na=False)

        mixed_mask = has_comma & has_dot
        text.loc[mixed_mask] = text.loc[mixed_mask].str.replace(".", "", regex=False)
        text = text.str.replace(",", ".", regex=False)
        return pd.to_numeric(text, errors="coerce")

    def _to_clean_key_series(self, series: pd.Series) -> pd.Series:
        return series.astype(str).str.strip().str.upper()

    def _build_recipe_cost_base(self) -> pd.DataFrame:
        """
        Constrói base canônica de custos por item de receita.

        Regras:
        - Chave canônica do produto: ID do Produto
        - Receita: quantidade usada do ingrediente
        - Matéria Prima: custo unitário por unidade comprada
        """
        if self._cache_recipe_cost_base is not None:
            return self._cache_recipe_cost_base.copy()

        receita_df = self._get_receita_data()
        if receita_df is None or receita_df.empty:
            self._cache_recipe_cost_base = pd.DataFrame()
            return self._cache_recipe_cost_base.copy()

        receita = receita_df
        materia_df = self._get_materia_prima_data()
        materia = materia_df if materia_df is not None else pd.DataFrame()

        # Receita
        receita_product_id_col = self._find_column(
            receita,
            ["ID do Produto", "ID", "ProductID", "product_id", "ProdutoID", "id_produto"],
        )
        receita_product_name_col = self._find_column(
            receita,
            ["Nome do Produto", "ProductName", "product_name", "Produto"],
        )
        receita_ingredient_id_col = self._find_column(
            receita,
            [
                "ID do Ingrediente",
                "IngredientID",
                "ingredient_id",
                "ID Matéria Prima",
                "ID Materia Prima",
                "id_materia_prima",
            ],
        )
        receita_ingredient_name_col = self._find_column(
            receita,
            ["Ingrediente", "Nome do Ingrediente", "ingredient_name", "Matéria Prima", "Materia Prima"],
        )
        receita_qty_col = self._find_column(
            receita,
            [
                "Quantidade",
                "Quantidade Receita",
                "Quantidade Usada",
                "Quantidade por Produto",
                "qty",
                "Qtde",
                "Custo Unitário",
                "Custo Unitario",
                "Custo",
            ],
        )
        receita_item_cost_col = self._find_column(
            receita,
            [
                "Custo do Ingrediente",
                "Custo Ingrediente",
                "Custo_Ingrediente",
                "Ingredient Cost",
                "Valor do Ingrediente",
            ],
        )

        # Matéria-prima (opcional quando receita já traz custo do ingrediente)
        materia_ingredient_id_col = self._find_column(
            materia,
            [
                "ID do Ingrediente",
                "IngredientID",
                "ingredient_id",
                "ID Matéria Prima",
                "ID Materia Prima",
                "id_materia_prima",
            ],
        )
        materia_ingredient_name_col = self._find_column(
            materia,
            ["Ingrediente", "Nome do Ingrediente", "ingredient_name", "Matéria Prima", "Materia Prima"],
        )
        materia_unit_cost_col = self._find_column(
            materia,
            [
                "Custo Unitário",
                "Custo Unitario",
                "Custo_Unitrio",
                "Custo Unitrio",
                "Custo por Unidade",
                "UnitCost",
                "Preço Unitário",
                "Preco Unitario",
                "Valor Unitário",
                "Valor Unitario",
            ],
        )

        if not receita_product_id_col:
            self._cache_recipe_cost_base = pd.DataFrame()
            return self._cache_recipe_cost_base.copy()
        if not receita_qty_col and not receita_item_cost_col:
            self._cache_recipe_cost_base = pd.DataFrame()
            return self._cache_recipe_cost_base.copy()
        can_use_materia = not materia.empty and bool(materia_unit_cost_col)
        if not receita_item_cost_col and not can_use_materia:
            self._cache_recipe_cost_base = pd.DataFrame()
            return self._cache_recipe_cost_base.copy()

        receita["ID do Produto"] = self._to_clean_key_series(receita[receita_product_id_col])
        receita = receita[(receita["ID do Produto"].notna()) & (receita["ID do Produto"] != "")]

        receita["Produto"] = (
            receita[receita_product_name_col].astype(str).str.strip()
            if receita_product_name_col
            else ""
        )
        receita["Quantidade Receita"] = (
            self._to_numeric_series(receita[receita_qty_col])
            if receita_qty_col
            else pd.Series([pd.NA] * len(receita), index=receita.index)
        )
        receita["Custo da Receita (R$)"] = (
            self._to_numeric_series(receita[receita_item_cost_col])
            if receita_item_cost_col
            else pd.Series([pd.NA] * len(receita), index=receita.index)
        )

        if receita_ingredient_id_col:
            receita["ID do Ingrediente"] = self._to_clean_key_series(receita[receita_ingredient_id_col])
        else:
            receita["ID do Ingrediente"] = ""

        if receita_ingredient_name_col:
            receita["Ingrediente"] = receita[receita_ingredient_name_col].astype(str).str.strip()
        else:
            receita["Ingrediente"] = ""

        if can_use_materia:
            materia["Custo Unitário MP (R$)"] = self._to_numeric_series(materia[materia_unit_cost_col])
            if materia_ingredient_id_col:
                materia["ID do Ingrediente"] = self._to_clean_key_series(materia[materia_ingredient_id_col])
            else:
                materia["ID do Ingrediente"] = ""

            if materia_ingredient_name_col:
                materia["Ingrediente"] = materia[materia_ingredient_name_col].astype(str).str.strip()
            else:
                materia["Ingrediente"] = ""

            if materia_ingredient_id_col and receita_ingredient_id_col:
                base = receita.merge(
                    materia[["ID do Ingrediente", "Ingrediente", "Custo Unitário MP (R$)"]],
                    on="ID do Ingrediente",
                    how="left",
                    suffixes=("", "_mp"),
                )
                base["Ingrediente"] = base["Ingrediente"].where(
                    base["Ingrediente"].astype(str).str.strip() != "", base.get("Ingrediente_mp", "")
                )
                if "Ingrediente_mp" in base.columns:
                    base = base.drop(columns=["Ingrediente_mp"])
            else:
                base = receita.merge(
                    materia[["Ingrediente", "Custo Unitário MP (R$)"]],
                    on="Ingrediente",
                    how="left",
                )
        else:
            base = receita.copy()
            base["Custo Unitário MP (R$)"] = pd.NA

        computed_cost = base["Quantidade Receita"] * base["Custo Unitário MP (R$)"]
        base["Custo do Ingrediente (R$)"] = base["Custo da Receita (R$)"].where(
            base["Custo da Receita (R$)"].notna(),
            computed_cost,
        )
        base["Origem do Custo"] = pd.NA
        base.loc[base["Custo da Receita (R$)"].notna(), "Origem do Custo"] = "Receita"
        base.loc[
            base["Custo da Receita (R$)"].isna() & computed_cost.notna(),
            "Origem do Custo",
        ] = "Calculado MP"
        base.loc[base["Custo do Ingrediente (R$)"].isna(), "Origem do Custo"] = "Sem Custo"

        cols = [
            "ID do Produto",
            "Produto",
            "ID do Ingrediente",
            "Ingrediente",
            "Quantidade Receita",
            "Custo Unitário MP (R$)",
            "Custo da Receita (R$)",
            "Custo do Ingrediente (R$)",
            "Origem do Custo",
        ]

        for col in cols:
            if col not in base.columns:
                base[col] = None

        self._cache_recipe_cost_base = base[cols]
        return self._cache_recipe_cost_base.copy()

    def get_product_cost_breakdown(self) -> pd.DataFrame:
        """
        Retorna DataFrame consolidado por item de ingrediente na receita.
        """
        if self._cache_product_cost_breakdown is not None:
            return self._cache_product_cost_breakdown.copy()

        base = self._build_recipe_cost_base()
        if base.empty:
            self._cache_product_cost_breakdown = pd.DataFrame()
            return self._cache_product_cost_breakdown.copy()

        self._cache_product_cost_breakdown = base.sort_values(["ID do Produto", "Ingrediente"], na_position="last")
        return self._cache_product_cost_breakdown.copy()

    def get_product_cost_summary(self) -> pd.DataFrame:
        """
        Retorna resumo de custos por produto:
        - ID do Produto
        - Produto
        - Custo Total
        - Quantidade de Ingredientes
        """
        if self._cache_product_cost_summary is not None:
            return self._cache_product_cost_summary.copy()

        base = self._build_recipe_cost_base()
        if base.empty:
            self._cache_product_cost_summary = pd.DataFrame()
            return self._cache_product_cost_summary.copy()

        summary = (
            base.groupby(["ID do Produto", "Produto"], dropna=False)
            .agg(
                {
                    "Custo do Ingrediente (R$)": lambda s: s.sum(min_count=1),
                    "Ingrediente": lambda s: s.astype(str).str.strip().replace("", pd.NA).dropna().nunique(),
                }
            )
            .reset_index()
        )
        summary.columns = ["ID do Produto", "Produto", "Custo Total (R$)", "Qtd Ingredientes"]
        self._cache_product_cost_summary = summary.sort_values(
            "Custo Total (R$)", ascending=False, na_position="last"
        )
        return self._cache_product_cost_summary.copy()

    def get_products_with_sales_impact(self) -> pd.DataFrame:
        """
        Retorna produtos com informações comerciais e custos calculados.
        """
        if self._cache_products_with_sales_impact is not None:
            return self._cache_products_with_sales_impact.copy()

        produtos_df = self._get_produtos_data()
        if produtos_df is None or produtos_df.empty:
            self._cache_products_with_sales_impact = pd.DataFrame()
            return self._cache_products_with_sales_impact.copy()

        produtos = produtos_df
        cost_summary = self.get_product_cost_summary()

        product_id_col = self._find_column(
            produtos,
            ["ID do Produto", "ID", "ProductID", "product_id", "ProdutoID", "id_produto"],
        )
        product_name_col = self._find_column(
            produtos,
            ["Nome do Produto", "ProductName", "product_name", "Produto"],
        )
        price_col = self._find_column(
            produtos,
            [
                "Preço de Venda",
                "Preco de Venda",
                "Preo de Venda",
                "Preo de Venda (R$)",
                "Preço",
                "Preco",
                "price",
                "preco",
            ],
        )
        margin_col = self._find_column(produtos, ["Margem", "Margin", "margem (%)"])
        category_col = self._find_column(produtos, ["Categoria", "category"])
        active_col = self._find_column(produtos, ["Ativo", "active", "status"])

        if not product_id_col or not product_name_col:
            self._cache_products_with_sales_impact = pd.DataFrame()
            return self._cache_products_with_sales_impact.copy()

        produtos["ID do Produto"] = self._to_clean_key_series(produtos[product_id_col])
        produtos["Nome do Produto"] = produtos[product_name_col].astype(str).str.strip()

        # Filtrar apenas produtos reais cadastrados
        produtos = produtos[
            (produtos["ID do Produto"] != "") & (produtos["Nome do Produto"] != "")
        ].copy()

        if price_col:
            produtos["Preço"] = self._to_numeric_series(produtos[price_col])
        else:
            produtos["Preço"] = pd.NA

        if margin_col:
            produtos["Margem (%)"] = self._to_numeric_series(produtos[margin_col])
        else:
            produtos["Margem (%)"] = pd.NA
        produtos["Margem (%)"] = pd.to_numeric(produtos["Margem (%)"], errors="coerce")

        if category_col:
            produtos["Categoria"] = produtos[category_col]
        else:
            produtos["Categoria"] = pd.NA

        if active_col:
            produtos["Ativo"] = produtos[active_col]
        else:
            produtos["Ativo"] = pd.NA

        if not cost_summary.empty:
            produtos = produtos.merge(
                cost_summary[["ID do Produto", "Custo Total (R$)"]],
                on="ID do Produto",
                how="left",
            )
        else:
            produtos["Custo Total (R$)"] = pd.NA

        # Calcular margem caso não exista, usando preço e custo
        needs_margin = produtos["Margem (%)"].isna() & produtos["Preço"].notna() & produtos["Custo Total (R$)"].notna()
        valid_price = produtos["Preço"] > 0
        compute_mask = needs_margin & valid_price
        produtos.loc[compute_mask, "Margem (%)"] = (
            (produtos.loc[compute_mask, "Preço"] - produtos.loc[compute_mask, "Custo Total (R$)"])
            / produtos.loc[compute_mask, "Preço"]
        ) * 100

        produtos["Margem Bruta (R$)"] = produtos["Preço"] - produtos["Custo Total (R$)"]

        output_cols = [
            "ID do Produto",
            "Nome do Produto",
            "Categoria",
            "Preço",
            "Custo Total (R$)",
            "Margem (%)",
            "Margem Bruta (R$)",
            "Ativo",
        ]
        self._cache_products_with_sales_impact = produtos[output_cols]
        return self._cache_products_with_sales_impact.copy()

    def calculate_total_cost_per_product(self) -> Dict[str, Decimal]:
        """
        Calcula custo total de produção por ID do Produto.
        """
        summary = self.get_product_cost_summary()
        if summary.empty:
            return {}

        results: Dict[str, Decimal] = {}
        for _, row in summary.iterrows():
            product_id = str(row["ID do Produto"]).strip()
            cost = row["Custo Total (R$)"]
            if not product_id or pd.isna(cost):
                continue
            results[product_id] = Decimal(str(float(cost)))
        return results

    def get_ingredients_list(self) -> pd.DataFrame:
        """Retorna lista de matéria-prima disponível."""
        materia_df = self._get_materia_prima_data()
        if materia_df is None or materia_df.empty:
            return pd.DataFrame()
        return materia_df

    def get_recipe_cost_issues(self) -> pd.DataFrame:
        """Retorna itens de receita sem custo válido para facilitar correção na planilha."""
        if self._cache_recipe_cost_issues is not None:
            return self._cache_recipe_cost_issues.copy()

        breakdown = self.get_product_cost_breakdown()
        if breakdown.empty:
            self._cache_recipe_cost_issues = pd.DataFrame()
            return self._cache_recipe_cost_issues.copy()

        issues = breakdown[breakdown["Custo do Ingrediente (R$)"].isna()].copy()
        if issues.empty:
            self._cache_recipe_cost_issues = pd.DataFrame()
            return self._cache_recipe_cost_issues.copy()

        issues["Problema"] = "Sem custo válido (verifique fórmula da Receita ou custo da Matéria Prima)"
        cols = [
            "ID do Produto",
            "Produto",
            "ID do Ingrediente",
            "Ingrediente",
            "Quantidade Receita",
            "Custo da Receita (R$)",
            "Custo Unitário MP (R$)",
            "Problema",
        ]
        self._cache_recipe_cost_issues = issues[cols]
        return self._cache_recipe_cost_issues.copy()
