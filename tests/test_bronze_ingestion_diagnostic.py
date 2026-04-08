from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.bronze_ingestion_diagnostic import run_diagnostic


def _write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    path.write_text(content, encoding=encoding)


def test_run_diagnostic_compares_physical_and_bronze_counts(tmp_path: Path) -> None:
    csv_dir = tmp_path / "raw"
    csv_dir.mkdir()

    jan_csv = (
        "Numero da venda;Data da venda;Nome do produto/serviço;Quantidade de itens;Valor total\n"
        "7412;31/01/2026;ESFIHA FRANGO/REQUE;1;18,00\n"
        "7412;31/01/2026;COXINHA DE FRANGO;1;18,00\n"
    )
    feb_csv = (
        "Numero da venda,Data da venda,Nome do produto/serviço,Quantidade de itens,Valor total\n"
        "7413,02/01/2026,B PT NINHO C NUT 250 ML,1,18.00\n"
        "7413,02/01/2026,B PT PRESTIGIO 250 ML,1,18.00\n"
    )

    _write_text(csv_dir / "sales_data_01_2026.csv", jan_csv)
    _write_text(csv_dir / "sales_data_02_2026.csv", feb_csv)

    bronze = pd.DataFrame(
        {
            "source_file": [
                "sales_data_01_2026.csv",
                "sales_data_01_2026.csv",
                "sales_data_02_2026.csv",
            ]
        }
    )
    bronze_path = tmp_path / "bronze.parquet"
    bronze.to_parquet(bronze_path, index=False)

    report = run_diagnostic(
        csv_dir=csv_dir,
        bronze_path=bronze_path,
        bronze_source_col="source_file",
        drive_folder_id=None,
        credential_file=None,
    )

    assert len(report) == 2

    jan = report.loc[report["file_name"] == "sales_data_01_2026.csv"].iloc[0]
    feb = report.loc[report["file_name"] == "sales_data_02_2026.csv"].iloc[0]

    assert jan["physical_rows"] == 2
    assert jan["parsed_rows"] == 2
    assert jan["bronze_rows"] == 2

    assert feb["physical_rows"] == 2
    assert feb["parsed_rows"] == 2
    assert feb["bronze_rows"] == 1
    assert feb["rows_lost_vs_physical"] == 1


def test_run_diagnostic_reports_date_preference(tmp_path: Path) -> None:
    csv_dir = tmp_path / "raw"
    csv_dir.mkdir()

    csv_content = (
        "Numero da venda;Data da venda;Nome do produto/serviço;Quantidade de itens;Valor total\n"
        "7412;31/01/2026;PROD A;1;18,00\n"
        "7413;30/01/2026;PROD B;1;18,00\n"
    )
    _write_text(csv_dir / "sales_data_01_2026.csv", csv_content)

    bronze_path = tmp_path / "bronze.parquet"
    pd.DataFrame({"source_file": ["sales_data_01_2026.csv", "sales_data_01_2026.csv"]}).to_parquet(
        bronze_path, index=False
    )

    report = run_diagnostic(
        csv_dir=csv_dir,
        bronze_path=bronze_path,
        bronze_source_col="source_file",
        drive_folder_id=None,
        credential_file=None,
    )

    row = report.iloc[0]
    assert row["valid_ddmmyyyy"] == 2
    assert row["valid_mmddyyyy"] == 0
    assert row["recommended_format"] == "%d/%m/%Y"

