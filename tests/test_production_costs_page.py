import pandas as pd

from src.presentation.pages.production_costs import (
    _read_first_existing_parquet,
    build_no_cost_products_table,
    build_recipe_detail_table,
    filter_products_by_name,
    filter_issues_by_product,
)


def test_build_no_cost_products_table_adds_production_cost_column():
    source_df = pd.DataFrame(
        {
            "ID do Produto": ["PROD-001"],
            "Produto": ["Brigadeiro"],
            "Qtd Ingredientes": [3],
            "Custo Total (R$)": [12.5],
        }
    )

    result = build_no_cost_products_table(source_df)

    assert list(result.columns) == [
        "ID do Produto",
        "Produto",
        "Qtd Ingredientes",
        "Custo de Produção",
    ]
    assert result.iloc[0]["Custo de Produção"] == "R$ 12,50"


def test_build_cost_summary_table_formats_product_label_and_cost():
    source_df = pd.DataFrame(
        {
            "Custo de Produção": ["R$ 10,00", "R$ 12,00"],
        }
    )

    result = filter_products_by_name(source_df, "   ")

    assert len(result) == 2


def test_filter_products_by_name_matches_partial_name_case_insensitive():
    source_df = pd.DataFrame(
        {
            "Produto": ["Copo Morango", "Casadinho", "Mousse Ninho"],
            "Custo de Produção": ["R$ 10,00", "R$ 12,00", "R$ 14,00"],
        }
    )

    result = filter_products_by_name(source_df, "mOrAn")

    assert result["Produto"].tolist() == ["Copo Morango"]


def test_filter_products_by_name_returns_empty_when_no_match_exists():
    source_df = pd.DataFrame(
        {
            "Produto": ["Copo Morango", "Casadinho"],
            "Custo de Produção": ["R$ 10,00", "R$ 12,00"],
        }
    )

    result = filter_products_by_name(source_df, "trufa")

    assert result.empty


def test_filter_issues_by_product_filters_by_selected_id():
    issues_df = pd.DataFrame(
        {
            "ID do Produto": ["PROD-001", "PROD-002"],
            "Produto": ["Brigadeiro", "Beijinho"],
            "Ingrediente": ["Chocolate", "Coco"],
        }
    )

    result = filter_issues_by_product(issues_df, "PROD-001", "")

    assert result["ID do Produto"].tolist() == ["PROD-001"]


def test_filter_issues_by_product_applies_name_refinement():
    issues_df = pd.DataFrame(
        {
            "ID do Produto": ["PROD-001", "PROD-001", "PROD-002"],
            "Produto": ["Copo Morango", "Casadinho", "Mousse Ninho"],
            "Ingrediente": ["Morango", "Chocolate", "Ninho"],
        }
    )

    result = filter_issues_by_product(issues_df, "PROD-001", "moran")

    assert result["Produto"].tolist() == ["Copo Morango"]


def test_read_first_existing_parquet_returns_first_valid_file(tmp_path):
    first = tmp_path / "first.parquet"
    second = tmp_path / "second.parquet"
    pd.DataFrame({"a": [1]}).to_parquet(second, index=False)

    result = _read_first_existing_parquet((first, second))

    assert len(result) == 1
    assert result.loc[0, "a"] == 1


def test_read_first_existing_parquet_returns_empty_when_none_exist(tmp_path):
    missing_a = tmp_path / "a.parquet"
    missing_b = tmp_path / "b.parquet"

    result = _read_first_existing_parquet((missing_a, missing_b))

    assert result.empty


