import pandas as pd

from scripts.medallion_pipeline import (
    build_dim_canal,
    build_dim_produto,
    build_dim_tempo,
    build_fato_vendas,
    transform_to_silver,
    validate_star_schema,
)


def _raw_fixture() -> pd.DataFrame:
    # Simula schema de origem (bronze) com 4 linhas, incluindo data invalida e produto vazio.
    return pd.DataFrame(
        [
            {
                "Numero da Venda": "1001",
                "Data da Venda": "2026-02-01",
                "Nome do Produto/Servico": "Brigadeiro",
                "Tipo de Negociacao": "IFOOD",
                "Quantidade de Itens": "2",
                "Valor Unitario": "5,00",
                "Valor Total": "10,00",
            },
            {
                "Numero da Venda": "1001",
                "Data da Venda": "2026-02-01",
                "Nome do Produto/Servico": "Beijinho",
                "Tipo de Negociacao": "IFOOD",
                "Quantidade de Itens": "1",
                "Valor Unitario": "6,00",
                "Valor Total": "6,00",
            },
            {
                "Numero da Venda": "1002",
                "Data da Venda": "data_invalida",
                "Nome do Produto/Servico": "Cajuzinho",
                "Tipo de Negociacao": "PIX",
                "Quantidade de Itens": "3",
                "Valor Unitario": "4,00",
                "Valor Total": "12,00",
            },
            {
                "Numero da Venda": "1003",
                "Data da Venda": "2026-02-03",
                "Nome do Produto/Servico": None,
                "Tipo de Negociacao": "DINHEIRO",
                "Quantidade de Itens": "1",
                "Valor Unitario": "8,00",
                "Valor Total": "8,00",
            },
        ]
    )


def test_rowcount_bronze_silver_gold_fact_is_1_to_1():
    bronze = _raw_fixture()
    silver, audit = transform_to_silver(bronze)

    # Bronze -> Silver nao deve perder linhas.
    assert len(silver) == len(bronze)
    assert audit["rows_in"] == len(bronze)
    assert audit["rows_out"] == len(bronze)

    dim_produto = build_dim_produto(silver)
    dim_tempo = build_dim_tempo(silver)
    dim_canal = build_dim_canal(silver)
    fato = build_fato_vendas(silver, dim_produto, dim_tempo, dim_canal)

    # Silver -> Gold (fato) deve preservar todas as linhas (grain item de venda).
    assert len(fato) == len(silver)

    # Dimensoes podem ter menos linhas por dropna()/distinct sem impactar fato.
    assert len(dim_produto) <= len(silver)
    assert len(dim_tempo) <= len(silver)
    assert len(dim_canal) <= len(silver)


def test_star_schema_rowcount_validation_matches_silver():
    bronze = _raw_fixture()
    silver, _ = transform_to_silver(bronze)

    dim_produto = build_dim_produto(silver)
    dim_tempo = build_dim_tempo(silver)
    dim_canal = build_dim_canal(silver)
    fato = build_fato_vendas(silver, dim_produto, dim_tempo, dim_canal)

    validation = validate_star_schema(
        fato=fato,
        dim_produto=dim_produto,
        dim_tempo=dim_tempo,
        silver_rows=len(silver),
    )

    assert validation["silver_gold_rowcount_ok"] is True
    assert validation["silver_gold_rowcount_diff"] == 0

