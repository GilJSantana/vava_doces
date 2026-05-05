from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.run_silver_normalization import run_silver_stage


def test_run_silver_stage_writes_sales_and_manual_silver_artifacts(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "processed" / "silver"
    raw_dir.mkdir(parents=True)

    (raw_dir / "sales_2026_01.csv").write_text(
        "Número da venda;Nota Fiscal / RPS;Data da venda;Cliente;Nome do produto/serviço;"
        "Unidade de medida;Quantidade de itens;Valor unitário;Valor Bruto;Desconto na venda;"
        "Valor Liquido no Financeiro;Valor Total;Peso Bruto;Peso Total;Cidade do cliente;"
        "Tipo de item (produto ou serviço);Tipo de Negociação\n"
        "1001;NF-001;02/01/2026;João;Brigadeiro;UN;2;5,00;10,00;0,00;10,00;10,00;0;0;São Paulo;Produto;IFOOD\n",
        encoding="utf-8",
    )
    (raw_dir / "manual_produtos.csv").write_text(
        "ID do Produto,Nome do Produto,Rendimento\n"
        "PROD-001,Brigadeiro,10\n",
        encoding="utf-8",
    )
    (raw_dir / "manual_receitas.csv").write_text(
        "ID do Produto,Nome do Produto,ID do Ingrediente,Nome do Ingrediente,Quantidade por Produto,Unidade de Medida\n"
        "PROD-001,Brigadeiro,ING-001,Chocolate,60,G\n"
        "prod-001,Brigadeiro,ing-001,Chocolate,40,g\n",
        encoding="utf-8",
    )
    (raw_dir / "manual_materia_prima.csv").write_text(
        "ID do Ingrediente,Nome do Ingrediente,Tipo de Medida (Ex: K, G, L),Custo Fracionado (g/ml),Conteúdo por Caixa (Peso/Vol)\n"
        "ING-001,Chocolate,G,20,1000\n",
        encoding="utf-8",
    )

    output_path, audit = run_silver_stage(
        raw_dir=raw_dir,
        output_path=output_dir / "sales_silver_normalized.parquet",
    )

    assert output_path.exists()
    sales_silver = pd.read_parquet(output_path)
    assert len(sales_silver) == 1
    assert audit["rows_in"] == 1
    assert audit["rows_out"] == 1
    assert audit["rows_removed"] == 0

    manual_artifacts = audit["manual_artifacts"]
    assert set(manual_artifacts) == {"produtos", "receitas", "materia_prima"}

    manual_receitas = pd.read_parquet(manual_artifacts["receitas"])
    assert len(manual_receitas) == 1
    assert manual_receitas.loc[0, "produto_id"] == "PROD-001"
    assert manual_receitas.loc[0, "ingrediente_id"] == "ING-001"
    assert manual_receitas.loc[0, "qtd"] == 100.0

    source_rows = audit["source_rows"]
    assert source_rows["sales_rows_in"] == 1
    assert source_rows["manual_sheets"]["produtos"]["rows_out"] == 1
    assert source_rows["manual_sheets"]["receitas"]["rows_in"] == 2
    assert source_rows["manual_sheets"]["receitas"]["rows_out"] == 1


def test_run_silver_stage_succeeds_with_manual_sheets_only(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "processed" / "silver"
    raw_dir.mkdir(parents=True)

    (raw_dir / "manual_produtos.csv").write_text(
        "ID do Produto,Nome do Produto,Rendimento\n"
        "PROD-001,Brigadeiro,10\n",
        encoding="utf-8",
    )

    output_path, audit = run_silver_stage(
        raw_dir=raw_dir,
        output_path=output_dir / "sales_silver_normalized.parquet",
    )

    assert output_path.exists()
    sales_silver = pd.read_parquet(output_path)
    assert sales_silver.empty
    assert audit["rows_in"] == 0
    assert audit["rows_out"] == 0
    assert audit["manual_artifacts"]["produtos"].endswith("manual_produtos_silver.parquet")

