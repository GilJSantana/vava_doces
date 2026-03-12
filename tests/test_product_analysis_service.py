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
        }
    )
    service = ProductAnalysisService(data_source)

    service.get_recipe_cost_issues()
    service.get_product_cost_breakdown()
    service.get_product_cost_summary()

    assert data_source.calls == {"Receita": 1, "Matéria Prima": 1}


