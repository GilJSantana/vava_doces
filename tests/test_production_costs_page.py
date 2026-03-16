import pandas as pd

from src.presentation.pages.production_costs import (
    build_cost_summary_table,
    build_no_cost_products_table,
    build_recipe_detail_table,
    build_recipe_selector_options,
    extract_product_id,
    filter_issues_by_product,
    filter_products_by_name,
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
            "ID do Produto": ["PROD-001"],
            "Produto": ["Brigadeiro"],
            "Qtd Ingredientes": [3],
            "Custo Total (R$)": [12.5],
        }
    )

    result = build_cost_summary_table(source_df)

    assert "ID do Produto" not in result.columns
    assert result.iloc[0]["Produto"] == "PROD-001 - Brigadeiro"
    assert result.iloc[0]["Custo Total (R$)"] == "R$ 12,50"


def test_build_recipe_detail_table_normalizes_recipe_columns():
    source_df = pd.DataFrame(
        {
            "ID do Produto": ["PROD-001"],
            "Produto": ["Brigadeiro"],
            "Quantidade Receita": [2.0],
            "Unidade de Medida": ["kg"],
            "Custo Unitário MP (R$)": [4.0],
            "Custo do Ingrediente (R$)": [8.0],
            "Custo da Receita (R$)": [8.0],
            "Origem do Custo": ["Calculado MP"],
        }
    )

    result = build_recipe_detail_table(source_df)

    assert "Custo Unitário MP (R$)" not in result.columns
    assert "Custo da Receita (R$)" not in result.columns
    assert "Origem do Custo" not in result.columns
    assert "Quantidade Receita" not in result.columns
    assert "Unidade de Medida" not in result.columns
    assert "Quantidade" in result.columns
    assert result.iloc[0]["Quantidade"] == "2 kg"
    assert result.iloc[0]["Custo do Ingrediente (R$)"] == "R$ 8,00"
    expected_order = [
        "ID do Produto",
        "Produto",
        "ID do Ingrediente",
        "Ingrediente",
        "Quantidade",
        "Custo do Ingrediente (R$)",
    ]
    expected_present = [col for col in expected_order if col in result.columns]
    assert result.columns.tolist()[: len(expected_present)] == expected_present


def test_build_recipe_detail_table_without_unit_of_measure():
    source_df = pd.DataFrame(
        {
            "ID do Produto": ["PROD-001"],
            "Produto": ["Brigadeiro"],
            "Quantidade Receita": [2.0],
            "Custo Unitário MP (R$)": [4.0],
            "Custo do Ingrediente (R$)": [8.0],
        }
    )

    result = build_recipe_detail_table(source_df)

    assert "Quantidade" in result.columns
    assert result.iloc[0]["Quantidade"] == 2.0


def test_build_recipe_detail_table_with_empty_unit_of_measure():
    source_df = pd.DataFrame(
        {
            "ID do Produto": ["PROD-001"],
            "Produto": ["Brigadeiro"],
            "Quantidade Receita": [2.0],
            "Unidade de Medida": [""],
            "Custo do Ingrediente (R$)": [8.0],
        }
    )

    result = build_recipe_detail_table(source_df)

    assert "Quantidade" in result.columns
    assert result.iloc[0]["Quantidade"] == "2"


def test_build_recipe_selector_options_returns_unique_sorted_labels():
    source_df = pd.DataFrame(
        {
            "ID do Produto": ["PROD-002", "PROD-001", "PROD-001"],
            "Produto": ["Beijinho", "Brigadeiro", "Brigadeiro"],
        }
    )

    result = build_recipe_selector_options(source_df)

    assert result == ["PROD-002 - Beijinho", "PROD-001 - Brigadeiro"]


def test_extract_product_id_returns_none_when_label_is_missing():
    assert extract_product_id(None) is None


def test_extract_product_id_returns_prefix_before_separator():
    assert extract_product_id("PROD-001 - Brigadeiro") == "PROD-001"


def test_filter_products_by_name_returns_all_when_search_is_blank():
    source_df = pd.DataFrame(
        {
            "Produto": ["Brigadeiro", "Beijinho"],
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


