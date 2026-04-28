from __future__ import annotations

import pandas as pd
import pytest

from scripts.medallion_pipeline import build_gold_custos_produtos, build_gold_rentabilidade


def test_cost_gold_output_feeds_profitability_with_yield_adjusted_unit_cost() -> None:
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
		),
	}

	custos_agregados, _ = build_gold_custos_produtos(manual_sheets, {})
	faturamento_agregado = pd.DataFrame(
		{
			"id_produto": ["PROD-001"],
			"nome_produto": ["Brigadeiro"],
			"qtd_vendida": [1.0],
			"faturamento_liquido": [20.0],
		}
	)

	rentabilidade = build_gold_rentabilidade(faturamento_agregado, custos_agregados)

	assert rentabilidade.loc[0, "custo_producao_unitario"] == pytest.approx(1.04)
	assert rentabilidade.loc[0, "margem_valor"] == pytest.approx(18.96)
	assert rentabilidade.loc[0, "markup"] == pytest.approx(20.0 / 1.04)


def test_profitability_build_preserves_sales_row_even_without_matching_cost() -> None:
	faturamento_agregado = pd.DataFrame(
		{
			"id_produto": ["PROD-999"],
			"nome_produto": ["Produto Sem Receita"],
			"qtd_vendida": [2.0],
			"faturamento_liquido": [20.0],
		}
	)

	rentabilidade = build_gold_rentabilidade(
		faturamento_agregado,
		pd.DataFrame(columns=["id_produto", "nome_produto", "custo_producao"]),
	)

	assert len(rentabilidade) == 1
	assert pd.isna(rentabilidade.loc[0, "custo_producao_unitario"])
	assert pd.isna(rentabilidade.loc[0, "custo_producao_unitario_audit"])
	assert rentabilidade.loc[0, "margem_valor"] == pytest.approx(10.0)

