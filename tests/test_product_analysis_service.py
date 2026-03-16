import pandas as pd

from src.domain.product_analysis_service import ProductAnalysisService
from src.ports.data_source import DataSource, DataSourceError


class DictDataSource(DataSource):
    def __init__(self, sheets: dict[str, pd.DataFrame]):
        self._sheets = sheets

    def get_data(self, sheet_name: str) -> pd.DataFrame:
        if sheet_name not in self._sheets:
            raise DataSourceError(f"Sheet not found: {sheet_name}")
        return self._sheets[sheet_name]


class CountingDataSource(DictDataSource):
    def __init__(self, sheets: dict[str, pd.DataFrame]):
        super().__init__(sheets)
        self.calls: dict[str, int] = {}

    def get_data(self, sheet_name: str) -> pd.DataFrame:
        self.calls[sheet_name] = self.calls.get(sheet_name, 0) + 1
        return super().get_data(sheet_name)


def test_product_cost_summary_groups_by_product_id():
    receita_df = pd.DataFrame(
        [
            {
                "ID do Produto": "PROD-001",
                "Nome do Produto": "Brigadeiro",
                "ID do Ingrediente": "ING-001",
                "Quantidade": 2,
            },
            {
                "ID do Produto": "PROD-001",
                "Nome do Produto": "Brigadeiro",
                "ID do Ingrediente": "ING-002",
                "Quantidade": 1,
            },
            {
                "ID do Produto": "PROD-002",
                "Nome do Produto": "Beijinho",
                "ID do Ingrediente": "ING-002",
                "Quantidade": 3,
            },
        ]
    )

    materia_df = pd.DataFrame(
        [
            {"ID do Ingrediente": "ING-001", "Ingrediente": "Chocolate", "Custo Unitário": "R$ 5,00"},
            {"ID do Ingrediente": "ING-002", "Ingrediente": "Leite Condensado", "Custo Unitário": "2,00"},
        ]
    )

    produtos_df = pd.DataFrame(
        [
            {"ID do Produto": "PROD-001", "Nome do Produto": "Brigadeiro", "Preço de Venda": "R$ 12,90"},
            {"ID do Produto": "PROD-002", "Nome do Produto": "Beijinho", "Preço de Venda": "R$ 10,00"},
        ]
    )

    service = ProductAnalysisService(
        DictDataSource(
            {
                "Receita": receita_df,
                "Matéria Prima": materia_df,
                "Produtos": produtos_df,
            }
        )
    )

    summary = service.get_product_cost_summary()

    assert not summary.empty
    row_prod_001 = summary[summary["ID do Produto"] == "PROD-001"].iloc[0]
    row_prod_002 = summary[summary["ID do Produto"] == "PROD-002"].iloc[0]

    assert row_prod_001["Custo Total (R$)"] == 12.0
    assert row_prod_001["Qtd Ingredientes"] == 2
    assert row_prod_002["Custo Total (R$)"] == 6.0


def test_products_with_sales_impact_filters_invalid_products_and_computes_margin():
    receita_df = pd.DataFrame(
        [
            {
                "ID do Produto": "PROD-001",
                "ID do Ingrediente": "ING-001",
                "Quantidade": 2,
            }
        ]
    )

    materia_df = pd.DataFrame(
        [{"ID do Ingrediente": "ING-001", "Ingrediente": "Chocolate", "Custo Unitário": "R$ 5,00"}]
    )

    produtos_df = pd.DataFrame(
        [
            {"ID do Produto": "PROD-001", "Nome do Produto": "Brigadeiro", "Preço de Venda": "R$ 20,00"},
            {"ID do Produto": "", "Nome do Produto": "Linha em branco", "Preço de Venda": "R$ 10,00"},
        ]
    )

    service = ProductAnalysisService(
        DictDataSource(
            {
                "Receita": receita_df,
                "Matéria Prima": materia_df,
                "Produtos": produtos_df,
            }
        )
    )

    impact = service.get_products_with_sales_impact()

    assert len(impact) == 1
    assert impact.iloc[0]["ID do Produto"] == "PROD-001"
    assert impact.iloc[0]["Custo Total (R$)"] == 10.0
    assert round(float(impact.iloc[0]["Margem (%)"]), 2) == 50.0


def test_product_cost_summary_preserves_products_without_recipe_via_left_join():
    receita_df = pd.DataFrame(
        [
            {
                "ID do Produto": "PROD-001",
                "Nome do Produto": "Brigadeiro",
                "ID do Ingrediente": "ING-001",
                "Quantidade": 2,
            }
        ]
    )

    materia_df = pd.DataFrame(
        [{"ID do Ingrediente": "ING-001", "Ingrediente": "Chocolate", "Custo Unitário": "R$ 5,00"}]
    )

    produtos_df = pd.DataFrame(
        [
            {"ID do Produto": "PROD-001", "Nome do Produto": "Brigadeiro"},
            {"ID do Produto": "PROD-002", "Nome do Produto": "Beijinho"},
        ]
    )

    service = ProductAnalysisService(
        DictDataSource(
            {
                "Receita": receita_df,
                "Matéria Prima": materia_df,
                "Produtos": produtos_df,
            }
        )
    )

    summary = service.get_product_cost_summary()

    assert summary["ID do Produto"].tolist() == ["PROD-001", "PROD-002"]
    assert summary.iloc[0]["Custo Total (R$)"] == 10.0
    assert summary.iloc[0]["Qtd Ingredientes"] == 1
    assert pd.isna(summary.iloc[1]["Custo Total (R$)"])
    assert summary.iloc[1]["Qtd Ingredientes"] == 0


def test_service_reuses_cached_recipe_structures_between_calls():
    receita_df = pd.DataFrame(
        [
            {
                "ID do Produto": "PROD-001",
                "Nome do Produto": "Brigadeiro",
                "ID do Ingrediente": "ING-001",
                "Quantidade": 2,
            }
        ]
    )

    materia_df = pd.DataFrame(
        [{"ID do Ingrediente": "ING-001", "Ingrediente": "Chocolate", "Custo Unitário": "R$ 5,00"}]
    )

    data_source = CountingDataSource(
        {
            "Receita": receita_df,
            "Matéria Prima": materia_df,
            "Produtos": pd.DataFrame([
                {"ID do Produto": "PROD-001", "Nome do Produto": "Brigadeiro"}
            ]),
        }
    )
    service = ProductAnalysisService(data_source)

    service.get_recipe_cost_issues()
    service.get_product_cost_breakdown()
    service.get_product_cost_summary()

    assert data_source.calls == {"Receita": 1, "Matéria Prima": 1, "Produtos": 1}


def test_profitability_analysis_merges_sales_and_computes_financial_metrics():
    receita_df = pd.DataFrame(
        [
            {
                "ID do Produto": "PROD-001",
                "Nome do Produto": "Brigadeiro",
                "ID do Ingrediente": "ING-001",
                "Quantidade": 2,
            }
        ]
    )

    materia_df = pd.DataFrame(
        [{"ID do Ingrediente": "ING-001", "Ingrediente": "Chocolate", "Custo Unitário": "R$ 5,00"}]
    )

    produtos_df = pd.DataFrame(
        [
            {"ID do Produto": "PROD-001", "Nome do Produto": "Brigadeiro", "Preço de Venda": "R$ 20,00"},
            {"ID do Produto": "PROD-002", "Nome do Produto": "Beijinho", "Preço de Venda": "R$ 10,00"},
        ]
    )

    vendas_df = pd.DataFrame(
        [
            {"ID do Produto": "PROD-001", "Nome do Produto": "Brigadeiro", "Quantidade Vendida": 3, "Faturamento Total": "R$ 60,00"},
            {"ID do Produto": "PROD-002", "Nome do Produto": "Beijinho", "Quantidade Vendida": 2, "Faturamento Total": "R$ 20,00"},
        ]
    )

    service = ProductAnalysisService(
        DictDataSource(
            {
                "Receita": receita_df,
                "Matéria Prima": materia_df,
                "Produtos": produtos_df,
                "Vendas Diarias": vendas_df,
            }
        )
    )

    analysis = service.get_product_profitability_analysis()

    assert len(analysis) == 2
    row_prod_001 = analysis[analysis["ID do Produto"] == "PROD-001"].iloc[0]
    row_prod_002 = analysis[analysis["ID do Produto"] == "PROD-002"].iloc[0]

    assert row_prod_001["Volume de Vendas"] == 3
    assert row_prod_001["Faturamento Total"] == 60.0
    assert row_prod_001["Custo Real"] == 10.0
    assert row_prod_001["Margem de Contribuição (R$)"] == 10.0
    assert round(float(row_prod_001["Margem de Contribuição (%)"]), 2) == 50.0

    assert row_prod_002["Volume de Vendas"] == 2
    assert row_prod_002["Faturamento Total"] == 20.0
    assert row_prod_002["Custo Real"] == 0.0


def test_profitability_analysis_falls_back_to_sales_merge_by_name_when_id_is_missing():
    produtos_df = pd.DataFrame(
        [{"ID do Produto": "PROD-002", "Nome do Produto": "Beijinho", "Preço de Venda": "R$ 10,00"}]
    )

    vendas_df = pd.DataFrame(
        [{"Nome do Produto": "Beijinho", "Quantidade Vendida": 4, "Faturamento Total": "R$ 40,00"}]
    )

    service = ProductAnalysisService(
        DictDataSource(
            {
                "Produtos": produtos_df,
                "Vendas Diarias": vendas_df,
            }
        )
    )

    analysis = service.get_product_profitability_analysis()

    assert len(analysis) == 1
    assert analysis.iloc[0]["Volume de Vendas"] == 4
    assert analysis.iloc[0]["Faturamento Total"] == 40.0


