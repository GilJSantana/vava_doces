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
        self._cache_vendas = None
        self._receita_loaded = False
        self._materia_prima_loaded = False
        self._produtos_loaded = False
        self._vendas_loaded = False
        self._cache_recipe_cost_base = None
        self._cache_product_cost_breakdown = None
        self._cache_product_cost_summary = None
        self._cache_products_with_sales_impact = None
        self._cache_recipe_cost_issues = None
        self._cache_sales_summary = None
        self._cache_profitability_analysis = None

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

    def _get_vendas_data(self) -> Optional[pd.DataFrame]:
        """Carrega dados de vendas/faturamento com cache por instância do serviço."""
        if not self._vendas_loaded:
            self._cache_vendas = self._load_first_sheet(
                [
                    "Vendas Diarias",
                    "Vendas Diárias",
                    "Resumo Diário",
                    "Resumo Diario",
                    "Faturamento",
                    "Vendas",
                ]
            )
            self._vendas_loaded = True
        return self._copy_df(self._cache_vendas)

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
        values = pd.to_numeric(text, errors="coerce")
        return pd.Series(values, index=series.index)

    def _to_clean_key_series(self, series: pd.Series) -> pd.Series:
        return series.astype(str).str.strip().str.upper()

    def _to_name_key_series(self, series: pd.Series) -> pd.Series:
        """Normaliza nomes para chaves de junção tolerantes a variações de formatação."""
        return series.fillna("").astype(str).map(self._normalize_text)

    def _find_product_id_column(self, df: pd.DataFrame) -> Optional[str]:
        """Encontra coluna de ID do produto, incluindo casos de cabeçalho vazio."""
        product_id_col = self._find_column(
            df,
            ["ID do Produto", "ID", "ProductID", "product_id", "ProdutoID", "id_produto", "SKU"],
        )
        if product_id_col is not None:
            return product_id_col

        for col in df.columns:
            series = df[col].astype(str).str.strip().str.upper()
            if series.str.match(r"^PROD[-_ ]?\d+", na=False).any():
                return col
        return None

    def _build_products_catalog(self) -> pd.DataFrame:
        """Retorna catálogo canônico de produtos (ID + Nome) da aba Produtos."""
        produtos_df = self._get_produtos_data()
        if produtos_df is None or produtos_df.empty:
            return pd.DataFrame(columns=["ID do Produto", "Produto"])

        produtos = produtos_df.copy()
        product_id_col = self._find_product_id_column(produtos)
        product_name_col = self._find_column(
            produtos,
            ["Nome do Produto", "ProductName", "product_name", "Produto"],
        )

        if product_id_col is None:
            return pd.DataFrame(columns=["ID do Produto", "Produto"])

        produtos["ID do Produto"] = self._to_clean_key_series(produtos[product_id_col])
        produtos["Produto"] = (
            produtos[product_name_col].astype(str).str.strip() if product_name_col else ""
        )

        produtos = produtos[produtos["ID do Produto"].str.strip() != ""].copy()
        produtos = produtos.drop_duplicates(subset=["ID do Produto"], keep="first")
        return produtos[["ID do Produto", "Produto"]].reset_index(drop=True)

    def get_registered_products(self) -> pd.DataFrame:
        """Retorna os produtos cadastrados na aba Produtos preservando linhas válidas da planilha."""
        produtos_df = self._get_produtos_data()
        if produtos_df is None or produtos_df.empty:
            return pd.DataFrame(columns=["ID do Produto", "Produto"])

        produtos = produtos_df.copy()
        product_id_col = self._find_product_id_column(produtos)
        product_name_col = self._find_column(
            produtos,
            ["Nome do Produto", "ProductName", "product_name", "Produto"],
        )

        if product_id_col is None:
            return pd.DataFrame(columns=["ID do Produto", "Produto"])

        produtos["ID do Produto"] = self._to_clean_key_series(produtos[product_id_col])
        produtos["Produto"] = (
            produtos[product_name_col].astype(str).str.strip() if product_name_col else ""
        )
        produtos = produtos[produtos["ID do Produto"].str.strip() != ""].copy()
        return produtos[["ID do Produto", "Produto"]].reset_index(drop=True)

    def _build_sales_summary(self) -> pd.DataFrame:
        """Agrega volume de vendas e faturamento total por produto."""
        if self._cache_sales_summary is not None:
            return self._cache_sales_summary.copy()

        vendas_df = self._get_vendas_data()
        if vendas_df is None or vendas_df.empty:
            self._cache_sales_summary = pd.DataFrame(
                columns=["ID do Produto", "Nome do Produto", "Volume de Vendas", "Faturamento Total"]
            )
            return self._cache_sales_summary.copy()

        vendas = vendas_df.copy()
        product_id_col = self._find_column(
            vendas,
            ["ID do Produto", "ID", "ProductID", "product_id", "ProdutoID", "id_produto", "SKU"],
        )
        product_name_col = self._find_column(
            vendas,
            ["Nome do Produto", "Produto", "ProductName", "product_name"],
        )
        volume_col = self._find_column(
            vendas,
            [
                "Quantidade Vendida",
                "Qtd Vendida",
                "Quantidade",
                "Qtde",
                "Volume de Vendas",
                "Volume",
                "Qtd",
                "quantity",
            ],
        )
        revenue_col = self._find_column(
            vendas,
            [
                "Faturamento Total",
                "Receita Total",
                "Valor Total",
                "Total",
                "Faturamento",
                "Receita",
                "Valor da Venda",
                "Total Venda",
            ],
        )
        price_col = self._find_column(
            vendas,
            [
                "Preço de Venda",
                "Preco de Venda",
                "Preço Unitário",
                "Preco Unitario",
                "Preço",
                "Preco",
                "Valor Unitário",
                "Valor Unitario",
            ],
        )

        if not product_id_col and not product_name_col:
            self._cache_sales_summary = pd.DataFrame(
                columns=["ID do Produto", "Nome do Produto", "Volume de Vendas", "Faturamento Total"]
            )
            return self._cache_sales_summary.copy()

        vendas["ID do Produto"] = (
            self._to_clean_key_series(vendas[product_id_col]) if product_id_col else ""
        )
        vendas["Nome do Produto"] = (
            vendas[product_name_col].astype(str).str.strip() if product_name_col else ""
        )
        vendas = vendas[
            (vendas["ID do Produto"].astype(str).str.strip() != "")
            | (vendas["Nome do Produto"].astype(str).str.strip() != "")
        ].copy()

        vendas["Volume de Vendas"] = (
            self._to_numeric_series(vendas[volume_col]) if volume_col else pd.Series([0] * len(vendas), index=vendas.index)
        )

        if revenue_col:
            vendas["Faturamento Total"] = self._to_numeric_series(vendas[revenue_col])
        elif price_col and volume_col:
            vendas["Faturamento Total"] = self._to_numeric_series(vendas[price_col]) * vendas["Volume de Vendas"]
        else:
            vendas["Faturamento Total"] = pd.Series([0] * len(vendas), index=vendas.index)

        summary = (
            vendas.groupby(["ID do Produto", "Nome do Produto"], dropna=False)
            .agg({"Volume de Vendas": "sum", "Faturamento Total": "sum"})
            .reset_index()
        )
        self._cache_sales_summary = summary
        return self._cache_sales_summary.copy()

    def get_product_profitability_analysis(self) -> pd.DataFrame:
        """Retorna base analítica consolidada para gráficos de faturamento e rentabilidade."""
        if self._cache_profitability_analysis is not None:
            return self._cache_profitability_analysis.copy()

        produtos = self.get_products_with_sales_impact()
        if produtos is None or produtos.empty:
            self._cache_profitability_analysis = pd.DataFrame()
            return self._cache_profitability_analysis.copy()

        analysis = produtos.copy()
        analysis["Nome do Produto"] = analysis["Nome do Produto"].astype(str).str.strip()
        analysis["ID do Produto"] = self._to_clean_key_series(analysis["ID do Produto"])
        analysis["Chave Nome"] = self._to_name_key_series(analysis["Nome do Produto"])

        sales_summary = self._build_sales_summary()
        if not sales_summary.empty:
            sales_by_id = (
                sales_summary[["ID do Produto", "Volume de Vendas", "Faturamento Total"]]
                .groupby("ID do Produto", dropna=False)
                .sum()
                .reset_index()
            )
            analysis = analysis.merge(sales_by_id, on="ID do Produto", how="left")

            sales_by_name = (
                sales_summary.assign(**{"Chave Nome": self._to_name_key_series(sales_summary["Nome do Produto"])})
                [["Chave Nome", "Volume de Vendas", "Faturamento Total"]]
                .groupby("Chave Nome", dropna=False)
                .sum()
                .reset_index()
            )
            analysis = analysis.merge(
                sales_by_name,
                on="Chave Nome",
                how="left",
                suffixes=("", "_nome"),
            )
            analysis["Volume de Vendas"] = analysis["Volume de Vendas"].fillna(analysis["Volume de Vendas_nome"])
            analysis["Faturamento Total"] = analysis["Faturamento Total"].fillna(analysis["Faturamento Total_nome"])
            analysis = analysis.drop(columns=["Volume de Vendas_nome", "Faturamento Total_nome"])
        else:
            analysis["Volume de Vendas"] = 0.0
            analysis["Faturamento Total"] = 0.0

        analysis["Preço"] = pd.to_numeric(analysis["Preço"], errors="coerce")
        analysis["Custo Total (R$)"] = pd.to_numeric(analysis["Custo Total (R$)"], errors="coerce")
        analysis["Volume de Vendas"] = pd.to_numeric(analysis["Volume de Vendas"], errors="coerce").fillna(0.0)
        analysis["Faturamento Total"] = pd.to_numeric(analysis["Faturamento Total"], errors="coerce")

        computed_revenue = analysis["Preço"].fillna(0.0) * analysis["Volume de Vendas"]
        analysis["Faturamento Total"] = analysis["Faturamento Total"].fillna(computed_revenue).fillna(0.0)

        analysis["Custo Real"] = analysis["Custo Total (R$)"].fillna(0.0)
        analysis["Margem de Contribuição (R$)"] = analysis["Preço"].fillna(0.0) - analysis["Custo Real"]
        analysis["Margem de Contribuição (%)"] = 0.0
        valid_price_mask = analysis["Preço"].fillna(0.0) > 0
        analysis.loc[valid_price_mask, "Margem de Contribuição (%)"] = (
            analysis.loc[valid_price_mask, "Margem de Contribuição (R$)"]
            / analysis.loc[valid_price_mask, "Preço"]
        ) * 100

        self._cache_profitability_analysis = analysis.drop(columns=["Chave Nome"])
        return self._cache_profitability_analysis.copy()

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
        receita_unit_measure_col = self._find_column(
            receita,
            [
                "Unidade de Medida",
                "Unidade Medida",
                "Unidade",
                "Unit of Measurement",
                "UnitOfMeasure",
                "unit_measure",
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

        receita.loc[:, "ID do Produto"] = self._to_clean_key_series(receita[receita_product_id_col])
        receita = receita.loc[
            (receita["ID do Produto"].notna()) & (receita["ID do Produto"] != "")
        ].copy()

        receita.loc[:, "Produto"] = (
            receita[receita_product_name_col].astype(str).str.strip()
            if receita_product_name_col
            else ""
        )
        receita.loc[:, "Quantidade Receita"] = (
            self._to_numeric_series(receita[receita_qty_col])
            if receita_qty_col
            else pd.Series([pd.NA] * len(receita), index=receita.index)
        )
        receita.loc[:, "Unidade de Medida"] = (
            receita[receita_unit_measure_col].astype(str).str.strip()
            if receita_unit_measure_col
            else ""
        )
        receita.loc[:, "Custo da Receita (R$)"] = (
            self._to_numeric_series(receita[receita_item_cost_col])
            if receita_item_cost_col
            else pd.Series([pd.NA] * len(receita), index=receita.index)
        )

        if receita_ingredient_id_col:
            receita.loc[:, "ID do Ingrediente"] = self._to_clean_key_series(
                receita[receita_ingredient_id_col]
            )
        else:
            receita.loc[:, "ID do Ingrediente"] = ""

        if receita_ingredient_name_col:
            receita.loc[:, "Ingrediente"] = receita[receita_ingredient_name_col].astype(str).str.strip()
        else:
            receita.loc[:, "Ingrediente"] = ""

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
            "Unidade de Medida",
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
        products_catalog = self._build_products_catalog()

        if base.empty:
            recipe_summary = pd.DataFrame(
                columns=["ID do Produto", "Custo Total (R$)", "Qtd Ingredientes"]
            )
        else:
            recipe_summary = (
                base.groupby(["ID do Produto"], dropna=False)
                .agg(
                    {
                        "Custo do Ingrediente (R$)": lambda s: s.sum(min_count=1),
                        "Ingrediente": lambda s: s.astype(str)
                        .str.strip()
                        .replace("", pd.NA)
                        .dropna()
                        .nunique(),
                    }
                )
                .reset_index()
            )
            recipe_summary.columns = ["ID do Produto", "Custo Total (R$)", "Qtd Ingredientes"]

        if not products_catalog.empty:
            summary = products_catalog.merge(recipe_summary, on="ID do Produto", how="left")
        elif not recipe_summary.empty:
            fallback_products = (
                base[["ID do Produto", "Produto"]].drop_duplicates(subset=["ID do Produto"]).copy()
            )
            summary = fallback_products.merge(recipe_summary, on="ID do Produto", how="left")
        else:
            self._cache_product_cost_summary = pd.DataFrame()
            return self._cache_product_cost_summary.copy()

        summary["Qtd Ingredientes"] = pd.to_numeric(summary["Qtd Ingredientes"], errors="coerce").fillna(0).astype(int)

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
            produtos["Preço"] = pd.Series([float("nan")] * len(produtos), index=produtos.index, dtype="float64")

        if margin_col:
            produtos["Margem (%)"] = self._to_numeric_series(produtos[margin_col])
        else:
            produtos["Margem (%)"] = pd.Series([float("nan")] * len(produtos), index=produtos.index, dtype="float64")
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
            produtos["Custo Total (R$)"] = pd.Series([float("nan")] * len(produtos), index=produtos.index, dtype="float64")

        produtos["Custo Total (R$)"] = pd.to_numeric(produtos["Custo Total (R$)"], errors="coerce")

        # Calcular margem caso não exista, usando preço e custo
        needs_margin = produtos["Margem (%)"].isna() & produtos["Preço"].notna() & produtos["Custo Total (R$)"].notna()
        valid_price = produtos["Preço"] > 0
        compute_mask = needs_margin & valid_price
        calculated_margin = (
            (produtos["Preço"] - produtos["Custo Total (R$)"])
            / produtos["Preço"]
        ) * 100
        produtos["Margem (%)"] = produtos["Margem (%)"].where(~compute_mask, calculated_margin)

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
