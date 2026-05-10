import pandas as pd
import pytest

from scripts.medallion_pipeline import build_gold_custos_produtos


def test_build_gold_custos_produtos_computes_yield_adjusted_unit_cost_and_clean_index():
    manual_sheets = {
        "materia_prima": pd.DataFrame(
            [
                {
                    "ingrediente_id": "ING-001",
                    "nome_ingrediente": "Chocolate",
                    "unidade": "g",
                    "custo_unit": "20",
                    "rendimento_embalagem": "1000",
                },
                {
                    "ingrediente_id": "ING-002",
                    "nome_ingrediente": "Leite Condensado",
                    "unidade": "g",
                    "custo_unit": "8",
                    "rendimento_embalagem": "395",
                },
            ]
        ),
        "receitas": pd.DataFrame(
            [
                {"produto_id": "PROD-001", "ingrediente_id": "ING-001", "qtd": "120"},
                {"produto_id": "PROD-001", "ingrediente_id": "ING-002", "qtd": "395"},
            ]
        ),
        "produtos": pd.DataFrame(
            [
                {
                    "produto_id": "PROD-001",
                    "nome": "Brigadeiro",
                    "rendimento": "10",
                    "preco_venda": "20.0",
                },
            ]
        )
    }
    cost_map = {}

    gold_agregado, gold_detalhado = build_gold_custos_produtos(manual_sheets, cost_map)

    assert list(gold_detalhado.columns) == [
        "id_produto",
        "nome_produto",
        "id_ingrediente",
        "nome_ingrediente",
        "quantidade_formatada",
        "custo_unitario_final",
        "custo_origem_ausente",
    ]
    assert gold_detalhado.index.name is None

    assert len(gold_detalhado) == 2
    assert gold_detalhado.loc[0, "id_produto"] == "PROD-001"
    assert gold_detalhado.loc[0, "nome_produto"] == "Brigadeiro"
    assert gold_detalhado.loc[0, "id_ingrediente"] == "ING-001"
    assert gold_detalhado.loc[0, "nome_ingrediente"] == "Chocolate"
    assert gold_detalhado.loc[0, "quantidade_formatada"] == "120 g"
    assert gold_detalhado.loc[0, "custo_unitario_final"] == 2.4
    assert gold_detalhado.loc[1, "custo_unitario_final"] == 8.0
    assert bool(gold_detalhado.loc[0, "custo_origem_ausente"]) is True

    assert list(gold_agregado.columns) == [
        "id_produto",
        "nome_produto",
        "qtd_ingredientes",
        "custo_producao",
    ]
    assert len(gold_agregado) == 1
    assert gold_agregado.loc[0, "qtd_ingredientes"] == 2
    assert gold_agregado.loc[0, "custo_producao"] == pytest.approx(10.4)


def test_build_gold_custos_produtos_preserves_nan_when_all_ingredient_costs_are_missing():
    manual_sheets = {
        "materia_prima": pd.DataFrame(
            [
                {
                    "ingrediente_id": "ING-001",
                    "nome_ingrediente": "Chocolate",
                    "unidade": "g",
                    "custo_unit": None,
                    "rendimento_embalagem": "1000",
                },
            ]
        ),
        "receitas": pd.DataFrame(
            [
                {"produto_id": "PROD-001", "ingrediente_id": "ING-001", "qtd": "120"},
            ]
        ),
        "produtos": pd.DataFrame(
            [
                {"produto_id": "PROD-001", "nome": "Brigadeiro"},
            ]
        ),
    }

    gold_agregado, gold_detalhado = build_gold_custos_produtos(manual_sheets, {})

    assert pd.isna(gold_detalhado.loc[0, "custo_unitario_final"])
    assert gold_detalhado["custo_unitario_final"].dtype.kind == "f"
    assert pd.isna(gold_agregado.loc[0, "custo_producao"])
    assert gold_agregado["custo_producao"].dtype.kind == "f"


def test_build_gold_custos_produtos_scales_grams_against_kg_material_base():
    manual_sheets = {
        "materia_prima": pd.DataFrame(
            [
                {
                    "ingrediente_id": "ING-001",
                    "nome_ingrediente": "Acucar",
                    "unidade": "kg",
                    "custo_unit": "23.90",
                    "rendimento_embalagem": "10",
                },
            ]
        ),
        "receitas": pd.DataFrame(
            [
                {"produto_id": "PROD-001", "ingrediente_id": "ING-001", "qtd": "60", "unidade": "g"},
            ]
        ),
        "produtos": pd.DataFrame(
            [
                {"produto_id": "PROD-001", "nome": "Copo Morango"},
            ]
        ),
    }

    gold_agregado, gold_detalhado = build_gold_custos_produtos(manual_sheets, {})

    assert gold_detalhado.loc[0, "custo_unitario_final"] == pytest.approx(0.1434)
    assert gold_agregado.loc[0, "custo_producao"] == pytest.approx(0.1434)


def test_build_gold_custos_produtos_keeps_fractional_cent_value_from_decimal_calculation():
    manual_sheets = {
        "materia_prima": pd.DataFrame(
            [
                {
                    "ingrediente_id": "ING-001",
                    "nome_ingrediente": "Limao",
                    "unidade": "kg",
                    "custo_unit": "4",
                    "rendimento_embalagem": "1",
                },
            ]
        ),
        "receitas": pd.DataFrame(
            [
                {"produto_id": "PROD-001", "ingrediente_id": "ING-001", "qtd": "1", "unidade": "g"},
            ]
        ),
        "produtos": pd.DataFrame(
            [
                {"produto_id": "PROD-001", "nome": "Torta Limao"},
            ]
        ),
    }

    gold_agregado, gold_detalhado = build_gold_custos_produtos(manual_sheets, {})

    assert gold_detalhado.loc[0, "custo_unitario_final"] == pytest.approx(0.004)
    assert gold_agregado.loc[0, "custo_producao"] == pytest.approx(0.004)
    assert bool(gold_detalhado.loc[0, "custo_origem_ausente"]) is True


def test_build_gold_custos_produtos_links_receitas_by_product_name_when_id_missing():
    manual_sheets = {
        "materia_prima": pd.DataFrame(
            [
                {
                    "ingrediente_id": "ING-001",
                    "nome_ingrediente": "Chocolate",
                    "unidade": "g",
                    "custo_unit": "20",
                    "rendimento_embalagem": "1000",
                },
            ]
        ),
        "receitas": pd.DataFrame(
            [
                {"produto_id": "", "nome_produto": "Brigadeiro", "ingrediente_id": "ING-001", "qtd": "100", "unidade": "g"},
            ]
        ),
        "produtos": pd.DataFrame(
            [
                {"produto_id": "PROD-001", "nome": "Brigadeiro"},
            ]
        ),
    }

    gold_agregado, gold_detalhado = build_gold_custos_produtos(manual_sheets, {})

    assert len(gold_detalhado) == 1
    assert gold_detalhado.loc[0, "id_produto"] == "PROD-001"
    assert gold_agregado.loc[0, "id_produto"] == "PROD-001"
    assert gold_agregado.loc[0, "qtd_ingredientes"] == 1


def test_build_gold_custos_produtos_filters_out_catalog_products_without_receita():
    manual_sheets = {
        "materia_prima": pd.DataFrame(
            [
                {
                    "ingrediente_id": "ING-001",
                    "nome_ingrediente": "Chocolate",
                    "unidade": "g",
                    "custo_unit": "20",
                    "rendimento_embalagem": "1000",
                },
            ]
        ),
        "receitas": pd.DataFrame(
            [
                {"produto_id": "PROD-001", "ingrediente_id": "ING-001", "qtd": "100", "unidade": "g"},
            ]
        ),
        "produtos": pd.DataFrame(
            [
                {"produto_id": "PROD-001", "nome": "Brigadeiro", "rendimento": "10"},
                {"produto_id": "PROD-002", "nome": "Beijinho", "rendimento": "12"},
            ]
        ),
    }

    gold_agregado, gold_detalhado = build_gold_custos_produtos(manual_sheets, {})

    assert len(gold_agregado) == 1
    assert set(gold_agregado["id_produto"].tolist()) == {"PROD-001"}
    assert len(gold_detalhado) == 1


def test_build_gold_custos_produtos_deduplicates_case_insensitive_recipe_ids():
    """Test that recipes with case-insensitive IDs and no cost difference are deduplicated
    and qtd is summed (60+40=100) during normalization, reducing to 1 Gold detail line."""
    manual_sheets = {
        "materia_prima": pd.DataFrame(
            [
                {
                    "ingrediente_id": "ING-001",
                    "nome_ingrediente": "Chocolate",
                    "unidade": "g",
                    "custo_unit": "20",
                    "rendimento_embalagem": "1000",
                },
            ]
        ),
        "receitas": pd.DataFrame(
            [
                {"produto_id": "PROD-001", "ingrediente_id": "ING-001", "qtd": "60", "unidade": "g"},
                {"produto_id": "prod-001", "ingrediente_id": "ing-001", "qtd": "40", "unidade": "g"},
            ]
        ),
        "produtos": pd.DataFrame(
            [
                {"produto_id": "PROD-001", "nome": "Brigadeiro", "rendimento": "10"},
            ]
        ),
    }

    gold_agregado, gold_detalhado = build_gold_custos_produtos(manual_sheets, {})

    # After normalization deduplication: 2 input lines → 1 deduplicated line with qtd=100
    assert len(gold_detalhado) == 1
    assert gold_detalhado.loc[0, "id_produto"] == "PROD-001"
    assert gold_detalhado.loc[0, "id_ingrediente"] == "ING-001"
    assert gold_detalhado.loc[0, "quantidade_formatada"] == "100 g"
    assert gold_detalhado.loc[0, "custo_unitario_final"] == pytest.approx(2.0)
    assert gold_agregado.loc[0, "qtd_ingredientes"] == 1
    assert gold_agregado.loc[0, "custo_producao"] == pytest.approx(2.0)


def test_build_gold_custos_produtos_uses_explicit_recipe_cost_strings_and_counts_all_lines_for_prod_007():
    manual_sheets = {
        "materia_prima": pd.DataFrame(
            [
                {
                    "ingrediente_id": "ING-BASE",
                    "nome_ingrediente": "Base",
                    "unidade": "kg",
                    "custo_unit": "R$ 0,00",
                    "rendimento_embalagem": "1",
                },
            ]
        ),
        "receitas": pd.DataFrame(
            [
                {"produto_id": "PROD-007", "ingrediente_id": "ING-001", "qtd": "1", "custo_do_ingrediente": "R$ 1,20"},
                {"produto_id": "PROD-007", "ingrediente_id": "ING-002", "qtd": "1", "custo_do_ingrediente": "R$ 0,95"},
                {"produto_id": "PROD-007", "ingrediente_id": "ING-003", "qtd": "1", "custo_do_ingrediente": "R$ 1,10"},
                {"produto_id": "PROD-007", "ingrediente_id": "ING-004", "qtd": "1", "custo_do_ingrediente": "R$ 0,80"},
                {"produto_id": "PROD-007", "ingrediente_id": "ING-005", "qtd": "1", "custo_do_ingrediente": "R$ 2,30"},
                {"produto_id": "PROD-007", "ingrediente_id": "ING-005", "qtd": "1", "custo_do_ingrediente": "R$ 1,70"},
                {"produto_id": "PROD-007", "ingrediente_id": "ING-006", "qtd": "1", "custo_do_ingrediente": "R$ 1,40"},
                {"produto_id": "PROD-007", "ingrediente_id": "ING-007", "qtd": "1", "custo_do_ingrediente": "R$ 1,05"},
                {"produto_id": "PROD-007", "ingrediente_id": "ING-008", "qtd": "1", "custo_do_ingrediente": "R$ 1,60"},
                {"produto_id": "PROD-007", "ingrediente_id": "ING-009", "qtd": "1", "custo_do_ingrediente": "R$ 1,90"},
            ]
        ),
        "produtos": pd.DataFrame(
            [
                {"produto_id": "PROD-007", "nome": "Torta Supreme Limao", "rendimento": "1"},
            ]
        ),
    }

    gold_agregado, gold_detalhado = build_gold_custos_produtos(manual_sheets, {})

    assert len(gold_detalhado) == 10
    assert len(gold_agregado) == 1
    assert gold_agregado.loc[0, "id_produto"] == "PROD-007"
    assert int(gold_agregado.loc[0, "qtd_ingredientes"]) == 10
    assert gold_agregado.loc[0, "custo_producao"] == pytest.approx(14.0)


def test_build_gold_custos_produtos_preserves_recipe_cost_when_audit_lookup_fails_and_ids_vary_case():
    manual_sheets = {
        "materia_prima": pd.DataFrame(
            [
                {
                    "ingrediente_id": "ING-001",
                    "nome_ingrediente": "Base",
                    "unidade": "kg",
                    "custo_unit": "R$ 99,99",
                    "rendimento_embalagem": "1",
                },
            ]
        ),
        "receitas": pd.DataFrame(
            [
                {"produto_id": "PROD-002", "ingrediente_id": "ing-067", "qtd": "1", "custo_do_ingrediente": "R$ 2,10"},
                {"produto_id": "PROD-002", "ingrediente_id": "ING-067", "qtd": "1", "custo_do_ingrediente": "R$ 1,25"},
                {"produto_id": "PROD-002", "ingrediente_id": "Ing-068", "qtd": "1", "custo_do_ingrediente": "R$ 2,00"},
                {"produto_id": "PROD-002", "ingrediente_id": "ING-069", "qtd": "1", "custo_do_ingrediente": "R$ 1,00"},
            ]
        ),
        "produtos": pd.DataFrame(
            [
                {"produto_id": "PROD-002", "nome": "Produto 2", "rendimento": "1"},
            ]
        ),
    }

    gold_agregado, gold_detalhado = build_gold_custos_produtos(manual_sheets, {})

    assert len(gold_detalhado) == 4
    assert set(gold_detalhado["id_ingrediente"].tolist()) == {"ING-067", "ING-068", "ING-069"}
    assert gold_agregado.loc[0, "id_produto"] == "PROD-002"
    assert int(gold_agregado.loc[0, "qtd_ingredientes"]) == 4
    assert gold_agregado.loc[0, "custo_producao"] == pytest.approx(6.35)


def test_build_gold_custos_produtos_handles_non_standard_unit_token_without_value_error():
    manual_sheets = {
        "materia_prima": pd.DataFrame(
            [
                {
                    "ingrediente_id": "ING-060",
                    "nome_ingrediente": "Ingrediente 060",
                    "unidade": "kg",
                    "custo_unit": "10",
                    "rendimento_embalagem": "1",
                },
            ]
        ),
        "receitas": pd.DataFrame(
            [
                {
                    "produto_id": "PROD-060",
                    "ingrediente_id": "ING-060",
                    "qtd": "1",
                    "unidade": "1335K",
                    "custo_do_ingrediente": "R$ 1,89",
                },
            ]
        ),
        "produtos": pd.DataFrame(
            [
                {"produto_id": "PROD-060", "nome": "Produto 060", "rendimento": "1"},
            ]
        ),
    }

    gold_agregado, gold_detalhado = build_gold_custos_produtos(manual_sheets, {})

    assert len(gold_detalhado) == 1
    assert gold_detalhado.loc[0, "quantidade_formatada"] == "1 kg"
    assert gold_agregado.loc[0, "id_produto"] == "PROD-060"
    assert gold_agregado.loc[0, "custo_producao"] == pytest.approx(1.89)


def test_build_gold_custos_produtos_preserves_recipe_rows_when_ingredient_id_is_missing_but_name_exists():
    manual_sheets = {
        "materia_prima": pd.DataFrame(
            [
                {
                    "ingrediente_id": "ING-001",
                    "nome_ingrediente": "Leite",
                    "unidade": "kg",
                    "custo_unit": "10",
                    "rendimento_embalagem": "1",
                },
            ]
        ),
        "receitas": pd.DataFrame(
            [
                {"produto_id": "", "nome_produto": "Produto A", "ingrediente_id": "", "nome_ingrediente": "Geleia", "qtd": "1", "custo_do_ingrediente": "R$ 1,20"},
                {"produto_id": "", "nome_produto": "Produto A", "ingrediente_id": "", "nome_ingrediente": "Ganache", "qtd": "1", "custo_do_ingrediente": "R$ 2,30"},
                {"produto_id": "", "nome_produto": "Produto B", "ingrediente_id": "", "nome_ingrediente": "Creme", "qtd": "1", "custo_do_ingrediente": "R$ 0,90"},
            ]
        ),
        "produtos": pd.DataFrame(
            [
                {"produto_id": "PROD-001", "nome": "Produto A", "rendimento": "1"},
                {"produto_id": "PROD-002", "nome": "Produto B", "rendimento": "1"},
            ]
        ),
    }

    gold_agregado, gold_detalhado = build_gold_custos_produtos(manual_sheets, {})

    assert len(gold_detalhado) == 3
    assert gold_detalhado["id_ingrediente"].str.startswith("ING-").all()
    assert set(gold_agregado["id_produto"].tolist()) == {"PROD-001", "PROD-002"}
    assert gold_agregado.loc[gold_agregado["id_produto"] == "PROD-001", "custo_producao"].iloc[0] == pytest.approx(3.5)
    assert gold_agregado.loc[gold_agregado["id_produto"] == "PROD-002", "custo_producao"].iloc[0] == pytest.approx(0.9)





