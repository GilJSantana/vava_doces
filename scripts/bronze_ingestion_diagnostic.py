"""Diagnóstico de ingestão Bronze para arquivos de faturamento CSV.

Objetivo:
- Listar CSVs de faturamento (local ou Google Drive)
- Comparar row count físico x registros na Bronze
- Detectar suspeitas de encoding e delimitador inconsistentes
- Diagnosticar parsing de data DD/MM/YYYY vs MM/DD/YYYY

Uso (local):
    python scripts/bronze_ingestion_diagnostic.py \
      --csv-dir data/raw \
      --bronze-path data/processed/silver/sales_silver.parquet

Uso (Google Drive):
    python scripts/bronze_ingestion_diagnostic.py \
      --drive-folder-id "$DRIVE_FOLDER_ID" \
      --credential-file "$GOOGLE_APPLICATION_CREDENTIALS" \
      --bronze-path data/processed/silver/sales_silver.parquet
"""

from __future__ import annotations

import argparse
import io
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

# Ensure ``src.*`` imports resolve when running as ``python scripts/...``.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.domain.sales_analysis_service import _choose_date_format_for_source
from src.infrastructure.google_drive_adapter import GoogleDriveAdapter

logger = logging.getLogger("bronze_diag")

_EXPECTED_HEADERS = {
    "numero_da_venda",
    "data_da_venda",
    "nome_do_produto_servico",
    "quantidade_de_itens",
    "valor_total",
}

_ENCODING_CANDIDATES = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
_SEPARATOR_CANDIDATES = (";", ",", "\t", "|")
_DATE_CANDIDATES = ("data_da_venda", "data", "dt_venda")


@dataclass
class CsvSource:
    name: str
    bytes_data: bytes


@dataclass
class ParseResult:
    df: pd.DataFrame
    encoding: str
    separator: str
    score: int
    warnings: list[str]


def _normalize_header_token(value: object) -> str:
    text = str(value or "").replace("\ufeff", "").strip().lower()
    return "_".join(part for part in "".join(ch if ch.isalnum() else "_" for ch in text).split("_") if part)


def _estimate_physical_rows(raw: bytes, encoding: str) -> int:
    text = raw.decode(encoding, errors="replace")
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return 0
    return max(len(lines) - 1, 0)


def _score_dataframe(df: pd.DataFrame) -> int:
    norm_cols = {_normalize_header_token(c) for c in df.columns}
    return int(df.shape[1]) + 5 * len(norm_cols & _EXPECTED_HEADERS)


def _best_parse_for_csv(raw: bytes, name: str) -> ParseResult:
    best: Optional[ParseResult] = None
    parse_errors: list[str] = []

    for encoding in _ENCODING_CANDIDATES:
        try:
            decoded = raw.decode(encoding)
        except UnicodeDecodeError as exc:
            parse_errors.append(f"encoding={encoding} decode_error={exc.__class__.__name__}")
            continue

        for sep in _SEPARATOR_CANDIDATES:
            try:
                candidate = pd.read_csv(io.StringIO(decoded), sep=sep, engine="python")
            except Exception as exc:  # noqa: BLE001
                parse_errors.append(f"encoding={encoding} sep={repr(sep)} error={exc.__class__.__name__}")
                continue

            score = _score_dataframe(candidate)
            warnings: list[str] = []
            if candidate.shape[1] <= 1:
                warnings.append("parsed_with_single_column")
            if encoding != "utf-8-sig":
                warnings.append(f"non_default_encoding:{encoding}")

            current = ParseResult(candidate, encoding, sep, score, warnings)
            if best is None or current.score > best.score:
                best = current

    if best is None:
        details = "; ".join(parse_errors[:6])
        raise ValueError(f"Falha ao fazer parse de {name}. Tentativas: {details}")

    return best


def _find_date_column(df: pd.DataFrame) -> Optional[str]:
    by_norm = {_normalize_header_token(col): col for col in df.columns}
    for expected in _DATE_CANDIDATES:
        if expected in by_norm:
            return by_norm[expected]
    return None


def _date_diagnostics(series: pd.Series, source_name: str) -> dict[str, object]:
    text = series.astype(str).str.strip()
    text = text.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "NaT": pd.NA}).dropna()
    if text.empty:
        return {
            "date_rows": 0,
            "valid_ddmmyyyy": 0,
            "valid_mmddyyyy": 0,
            "invalid_dates": 0,
            "ambiguous_dates": 0,
            "recommended_format": "n/a",
        }

    parsed_dd = pd.to_datetime(text, format="%d/%m/%Y", errors="coerce")
    parsed_mm = pd.to_datetime(text, format="%m/%d/%Y", errors="coerce")

    valid_dd = int(parsed_dd.notna().sum())
    valid_mm = int(parsed_mm.notna().sum())
    invalid = int((parsed_dd.isna() & parsed_mm.isna()).sum())
    ambiguous = int((parsed_dd.notna() & parsed_mm.notna()).sum())
    recommended = _choose_date_format_for_source(text, source_name)

    return {
        "date_rows": int(len(text)),
        "valid_ddmmyyyy": valid_dd,
        "valid_mmddyyyy": valid_mm,
        "invalid_dates": invalid,
        "ambiguous_dates": ambiguous,
        "recommended_format": recommended,
    }


def _load_local_csv_sources(csv_dir: Path) -> list[CsvSource]:
    if not csv_dir.exists():
        raise FileNotFoundError(f"Diretório não encontrado: {csv_dir}")
    files = [f for f in sorted(csv_dir.glob("*.csv")) if not f.name.startswith(".~lock")]
    return [CsvSource(name=f.name, bytes_data=f.read_bytes()) for f in files]


def _load_drive_csv_sources(credential_file: str, folder_id: str) -> list[CsvSource]:
    adapter = GoogleDriveAdapter(credential_file=credential_file, folder_id=folder_id)
    files = [m for m in adapter.list_tabular_files() if m.get("mimeType") == "text/csv"]
    sources: list[CsvSource] = []
    for meta in sorted(files, key=lambda x: x.get("name", "")):
        raw = adapter.download_bytes(meta["id"])
        sources.append(CsvSource(name=meta["name"], bytes_data=raw))
    return sources


def _load_bronze_counts(bronze_path: Optional[Path], source_col: str) -> dict[str, int]:
    if bronze_path is None:
        return {}
    if not bronze_path.exists():
        raise FileNotFoundError(f"Arquivo Bronze não encontrado: {bronze_path}")

    suffix = bronze_path.suffix.lower()
    if suffix == ".parquet":
        bronze_df = pd.read_parquet(bronze_path)
    elif suffix == ".csv":
        bronze_df = pd.read_csv(bronze_path)
    elif suffix in {".xlsx", ".xls"}:
        bronze_df = pd.read_excel(bronze_path)
    else:
        raise ValueError(f"Formato Bronze não suportado: {suffix}")

    possible_cols: Iterable[str] = (source_col, "source_file", "_source_file", "arquivo_origem")
    selected = next((c for c in possible_cols if c in bronze_df.columns), None)
    if selected is None:
        raise ValueError(
            f"Coluna de origem não encontrada na Bronze. Tentadas: {list(possible_cols)}"
        )

    return (
        bronze_df[selected]
        .fillna("unknown")
        .astype(str)
        .value_counts()
        .to_dict()
    )


def run_diagnostic(
    csv_dir: Optional[Path],
    bronze_path: Optional[Path],
    bronze_source_col: str,
    drive_folder_id: Optional[str],
    credential_file: Optional[str],
) -> pd.DataFrame:
    if drive_folder_id:
        if not credential_file:
            raise ValueError("Informe --credential-file ao usar --drive-folder-id")
        sources = _load_drive_csv_sources(credential_file, drive_folder_id)
        source_type = "drive"
    else:
        if csv_dir is None:
            raise ValueError("Informe --csv-dir ou --drive-folder-id")
        sources = _load_local_csv_sources(csv_dir)
        source_type = "local"

    if not sources:
        return pd.DataFrame()

    bronze_counts = _load_bronze_counts(bronze_path, bronze_source_col)
    records: list[dict[str, object]] = []
    chosen_separators: list[str] = []

    for source in sources:
        parsed = _best_parse_for_csv(source.bytes_data, source.name)
        chosen_separators.append(parsed.separator)
        physical_rows = _estimate_physical_rows(source.bytes_data, parsed.encoding)
        parsed_rows = int(len(parsed.df))
        bronze_rows = int(bronze_counts.get(source.name, 0))

        date_col = _find_date_column(parsed.df)
        date_diag = (
            _date_diagnostics(parsed.df[date_col], source.name)
            if date_col is not None
            else {
                "date_rows": 0,
                "valid_ddmmyyyy": 0,
                "valid_mmddyyyy": 0,
                "invalid_dates": 0,
                "ambiguous_dates": 0,
                "recommended_format": "missing_date_column",
            }
        )

        warnings = list(parsed.warnings)
        if physical_rows != parsed_rows:
            warnings.append(f"physical_vs_parsed_mismatch:{physical_rows}!={parsed_rows}")
        if bronze_rows != parsed_rows:
            warnings.append(f"bronze_vs_parsed_mismatch:{bronze_rows}!={parsed_rows}")
        if bronze_rows != physical_rows:
            warnings.append(f"bronze_vs_physical_mismatch:{bronze_rows}!={physical_rows}")

        record = {
            "source": source_type,
            "file_name": source.name,
            "encoding": parsed.encoding,
            "delimiter": repr(parsed.separator),
            "physical_rows": physical_rows,
            "parsed_rows": parsed_rows,
            "bronze_rows": bronze_rows,
            "rows_lost_vs_physical": physical_rows - bronze_rows,
            "date_column": date_col or "<ausente>",
            **date_diag,
            "warnings": " | ".join(warnings) if warnings else "",
        }
        records.append(record)

    report = pd.DataFrame(records).sort_values("file_name").reset_index(drop=True)

    if len(set(chosen_separators)) > 1:
        logger.warning("Delimitador inconsistente entre arquivos: %s", sorted(set(chosen_separators)))

    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Diagnóstico de ingestão Bronze para CSVs de faturamento")
    parser.add_argument("--csv-dir", type=Path, default=Path("data/raw"), help="Diretório local com CSVs")
    parser.add_argument(
        "--bronze-path",
        type=Path,
        default=Path("data/processed/silver/sales_silver.parquet"),
        help="Tabela Bronze para comparação (parquet/csv/xlsx).",
    )
    parser.add_argument(
        "--bronze-source-col",
        default="source_file",
        help="Coluna da Bronze com nome do arquivo de origem",
    )
    parser.add_argument("--drive-folder-id", default=None, help="Folder ID do Google Drive (opcional)")
    parser.add_argument("--credential-file", default=None, help="JSON da service account para Drive")
    parser.add_argument("--output-csv", type=Path, default=None, help="Opcional: salva o relatório em CSV")
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    args = _build_parser().parse_args()

    try:
        report = run_diagnostic(
            csv_dir=args.csv_dir,
            bronze_path=args.bronze_path,
            bronze_source_col=args.bronze_source_col,
            drive_folder_id=args.drive_folder_id,
            credential_file=args.credential_file,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Falha no diagnóstico: %s", exc)
        return 1

    if report.empty:
        print("Nenhum CSV encontrado para diagnóstico.")
        return 0

    pd.set_option("display.max_colwidth", 120)
    print("\n=== Diagnóstico Bronze (CSV de faturamento) ===")
    print(report.to_string(index=False))

    totals = {
        "total_files": int(len(report)),
        "sum_physical_rows": int(report["physical_rows"].sum()),
        "sum_parsed_rows": int(report["parsed_rows"].sum()),
        "sum_bronze_rows": int(report["bronze_rows"].sum()),
    }
    print("\n=== Totais ===")
    for key, value in totals.items():
        print(f"- {key}: {value}")

    if args.output_csv:
        args.output_csv.parent.mkdir(parents=True, exist_ok=True)
        report.to_csv(args.output_csv, index=False)
        print(f"\nRelatório salvo em: {args.output_csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

