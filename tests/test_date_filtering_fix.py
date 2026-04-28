"""Regression test for date filtering on the current in-memory sales flow."""

from __future__ import annotations

import pandas as pd

from src.domain.sales_analysis_service import SalesTransformer


def test_date_filtering_partitions_transformed_sales_by_month() -> None:
    raw_sales = pd.DataFrame(
        [
            {
                "numero_da_venda": "1001",
                "data_da_venda": "13/01/2026",
                "nome_do_produto_servico": "Brigadeiro",
                "quantidade_de_itens": "1",
                "valor_total": "10,00",
                "_source_file": "jan_2026.csv",
            },
            {
                "numero_da_venda": "1002",
                "data_da_venda": "02/02/2026",
                "nome_do_produto_servico": "Brigadeiro",
                "quantidade_de_itens": "2",
                "valor_total": "20,00",
                "_source_file": "fev_2026.csv",
            },
            {
                "numero_da_venda": "1003",
                "data_da_venda": "28/02/2026",
                "nome_do_produto_servico": "Risole",
                "quantidade_de_itens": "3",
                "valor_total": "30,00",
                "_source_file": "fev_2026.csv",
            },
        ]
    )

    df = SalesTransformer().transform(raw_sales)

    dates = pd.to_datetime(df["data"], errors="coerce")
    jan_df = df[(dates >= "2026-01-01") & (dates <= "2026-01-31")]
    fev_df = df[(dates >= "2026-02-01") & (dates <= "2026-02-28")]
    mar_plus = df[(dates >= "2026-03-01") & (dates <= "2026-12-31")]

    assert len(df) == 3
    assert len(jan_df) == 1
    assert len(fev_df) == 2
    assert len(mar_plus) == 0
    assert len(jan_df) + len(fev_df) == len(df)
    assert set(dates.dt.year.dropna().unique()) == {2026}

