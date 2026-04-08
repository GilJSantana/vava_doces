"""Teste de integração: Silver → Gold com preservação de órfãos"""

from pathlib import Path
import pandas as pd
import pytest

from scripts.medallion_pipeline import (
    build_dim_produto,
    build_dim_tempo,
    build_fato_vendas,
)


def test_build_fato_vendas_preserves_orphan_products():
    """Verify that rows with null produto_id (orphans) are kept with flags."""
    
    # Minimal silver data: 3 rows, 1 produto inexistente em dim
    silver = pd.DataFrame({
        "num_venda": [1, 2, 3],
        "produto": ["Brigadeiro", "INEXISTENTE_PRODUTO", "Pavê"],
        "data": pd.to_datetime(["2026-01-15", "2026-01-20", "2026-01-25"]),
        "quantidade": [2, 1, 3],
        "valor_bruto": [50.0, 40.0, 90.0],
        "valor_liquido": [50.0, 40.0, 90.0],
        "valor_unitario": [25.0, 40.0, 30.0],
        "valor_total": [50.0, 40.0, 90.0],
        "desconto": [0.0, 0.0, 0.0],
        "custo": [10.0, 8.0, 20.0],
        "tipo_negociacao": ["LOJA", "LOJA", "IFOOD"],
        "num_venda": [1, 2, 3],
        "cliente": ["CLI_A", "CLI_B", "CLI_C"],
        "source_file": ["jan.csv", "jan.csv", "jan.csv"],
        "arquivo_origem": ["jan.csv", "jan.csv", "jan.csv"],
        "mes_referencia": ["2026-01", "2026-01", "2026-01"],
        "ingested_at_utc": ["2026-01-31T10:00:00Z"] * 3,
        "data_carga": ["2026-01-31T10:00:00Z"] * 3,
    })

    # Dimensions: produtos não inclui INEXISTENTE_PRODUTO
    dim_produto = pd.DataFrame({
        "produto_id": [1, 2],
        "nome_produto": ["Brigadeiro", "Pavê"],
    })

    dim_tempo = pd.DataFrame({
        "data_id": [1, 2, 3],
        "data": pd.to_datetime(["2026-01-15", "2026-01-20", "2026-01-25"]),
        "dia": [15, 20, 25],
        "mes": [1, 1, 1],
        "ano": [2026, 2026, 2026],
        "trimestre": [1, 1, 1],
        "dia_semana": [2, 0, 5],
        "nome_mes": ["Janeiro", "Janeiro", "Janeiro"],
    })

    # Build fato_vendas
    fato = build_fato_vendas(silver, dim_produto, dim_tempo)

    # Assertions
    assert len(fato) == 3, "All 3 rows should be preserved (not dropped for orphan produto)"
    
    orphan_mask = fato["_orphan_produto"]
    assert int(orphan_mask.sum()) == 1, "Exactly 1 row should be marked as orphan produto"
    
    # The orphan should be row with "INEXISTENTE_PRODUTO"
    orphan_row = fato[orphan_mask].iloc[0]
    assert orphan_row["_orphan_data"] == False, "Orphan should have valid data_id"


def test_build_fato_vendas_preserves_orphan_dates():
    """Verify that rows with null data_id (invalid dates) are kept with flags."""
    
    # Minimal silver data: 3 rows, 1 invalid date
    silver = pd.DataFrame({
        "num_venda": [1, 2, 3],
        "produto": ["Brigadeiro", "Brigadeiro", "Brigadeiro"],
        "data": pd.to_datetime(
            ["2026-01-15", pd.NaT, "2026-01-25"],
            errors="coerce",
        ),
        "quantidade": [2, 1, 3],
        "valor_bruto": [50.0, 40.0, 90.0],
        "valor_liquido": [50.0, 40.0, 90.0],
        "valor_unitario": [25.0, 40.0, 30.0],
        "valor_total": [50.0, 40.0, 90.0],
        "desconto": [0.0, 0.0, 0.0],
        "custo": [10.0, 8.0, 20.0],
        "tipo_negociacao": ["LOJA"] * 3,
        "cliente": ["CLI_A", "CLI_B", "CLI_C"],
        "source_file": ["jan.csv"] * 3,
        "arquivo_origem": ["jan.csv"] * 3,
        "mes_referencia": ["2026-01"] * 3,
        "ingested_at_utc": ["2026-01-31T10:00:00Z"] * 3,
        "data_carga": ["2026-01-31T10:00:00Z"] * 3,
    })

    dim_produto = pd.DataFrame({
        "produto_id": [1],
        "nome_produto": ["Brigadeiro"],
    })

    # Only 2 dates in dim_tempo (missing the NaT)
    dim_tempo = pd.DataFrame({
        "data_id": [1, 3],
        "data": pd.to_datetime(["2026-01-15", "2026-01-25"]),
        "dia": [15, 25],
        "mes": [1, 1],
        "ano": [2026, 2026],
        "trimestre": [1, 1],
        "dia_semana": [2, 5],
        "nome_mes": ["Janeiro", "Janeiro"],
    })

    fato = build_fato_vendas(silver, dim_produto, dim_tempo)

    assert len(fato) == 3, "All 3 rows should be preserved (not dropped for NaT date)"
    
    orphan_mask = fato["_orphan_data"]
    assert int(orphan_mask.sum()) == 1, "Exactly 1 row should be marked as orphan data"
    
    orphan_row = fato[orphan_mask].iloc[0]
    assert orphan_row["_orphan_produto"] == False, "Orphan should have valid produto_id"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

