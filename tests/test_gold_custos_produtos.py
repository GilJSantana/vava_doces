import pandas as pd
import pytest

from scripts.medallion_pipeline import build_gold_custos_produtos


def test_build_gold_custos_produtos_computes_real_margin_and_clean_index():
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

    assert list(gold_agregado.columns) == [
        "id_produto",
        "nome_produto",
        "qtd_ingredientes",
        "custo_producao",
    ]
    assert len(gold_agregado) == 1
    assert gold_agregado.loc[0, "qtd_ingredientes"] == 2
    assert gold_agregado.loc[0, "custo_producao"] == 10.4


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





