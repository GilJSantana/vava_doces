from __future__ import annotations

import pandas as pd
import pytest

from scripts.medallion_pipeline import build_gold_rentabilidade
from src.infrastructure.data_quality import DataQualityValidator


def test_build_gold_rentabilidade_uses_sales_key_and_product_name_fallback_for_costs() -> None:
    faturamento_agregado = pd.DataFrame(
        {
            "produto_id": [38],
            "nome_produto": ["Brigadeiro"],
            "qtd_vendida": [2.0],
            "faturamento_liquido": [20.0],
        }
    )
    custo_producao_agregado = pd.DataFrame(
        {
            "id_produto": ["PROD-001"],
            "nome_produto": [" brigadeiro "],
            "custo_producao": [5.0],
        }
    )

    result = build_gold_rentabilidade(faturamento_agregado, custo_producao_agregado)

    assert len(result) == 1
    assert result.loc[0, "id_produto"] == "38"
    assert result.loc[0, "custo_producao_unitario"] == 5.0
    assert result.loc[0, "margem_valor"] == 5.0
    assert result.loc[0, "markup"] == pytest.approx(2.0)


def test_data_quality_validator_checks_percentage_margin_range_not_unit_margin() -> None:
    validator = DataQualityValidator(verbose=False)
    dim_produto = pd.DataFrame({"produto_id": [1], "nome_produto": ["Brigadeiro"]}).astype(
        {"produto_id": "int64", "nome_produto": "object"}
    )
    dim_tempo = pd.DataFrame(
        {
            "data_id": [1],
            "data": [pd.Timestamp("2026-02-01")],
            "dia": [1],
            "mes": [2],
            "ano": [2026],
            "trimestre": [1],
            "nome_mes": ["Fevereiro"],
            "dia_semana": ["Sunday"],
        }
    ).astype(
        {
            "data_id": "int64",
            "dia": "int64",
            "mes": "int64",
            "ano": "int64",
            "trimestre": "int64",
            "nome_mes": "object",
            "dia_semana": "object",
        }
    )
    fato_vendas = pd.DataFrame(
        {
            "venda_id": [1],
            "produto_id": [1],
            "data_id": [1],
            "num_venda": ["NF-1"],
            "cliente": ["Cliente"],
            "quantidade": [1.0],
            "valor_unitario": [200.0],
            "valor_total": [200.0],
            "custo": [50.0],
            "margem": [150.0],
            "margem_percentual": [75.0],
            "faturamento_liquido": [200.0],
        }
    ).astype(
        {
            "venda_id": "int64",
            "produto_id": "int64",
            "data_id": "int64",
            "num_venda": "object",
            "cliente": "object",
            "quantidade": "float64",
            "valor_unitario": "float64",
            "valor_total": "float64",
            "custo": "float64",
            "margem": "float64",
            "margem_percentual": "float64",
            "faturamento_liquido": "float64",
        }
    )

    assert validator.validate_fato_vendas(fato_vendas, dim_produto, dim_tempo) is True

