#!/usr/bin/env python3
"""Run only the silver normalization stage, independent from the dashboard.

This script loads current raw files from ``data/raw`` and materializes a
normalized silver dataset ready for aggregations by date, product and channel.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.medallion_pipeline import LocalRawSource, read_raw_sources
from src.domain.sales_silver_normalizer import normalize_sales_to_silver_with_audit


def run_silver_stage(
    raw_dir: Path | None = None,
    output_path: Path | None = None,
) -> tuple[Path, dict[str, object]]:
    """Execute silver normalization and persist output parquet."""
    project_root = Path(__file__).resolve().parent.parent
    effective_raw_dir = raw_dir or (project_root / "data" / "raw")
    effective_output_path = output_path or (
        project_root / "data" / "processed" / "silver" / "sales_silver_normalized.parquet"
    )

    source = LocalRawSource(raw_dir=effective_raw_dir)
    raw_df, manual_sheets, source_audit = read_raw_sources(source)
    has_manual_data = any(isinstance(df, pd.DataFrame) and not df.empty for df in manual_sheets.values())
    if raw_df.empty and not has_manual_data:
        raise RuntimeError(f"No raw data found in: {effective_raw_dir}")

    silver_df, audit = normalize_sales_to_silver_with_audit(raw_df if not raw_df.empty else pd.DataFrame())
    effective_output_path.parent.mkdir(parents=True, exist_ok=True)
    silver_df.to_parquet(effective_output_path, index=False, engine="pyarrow", compression="snappy")

    manual_artifacts: dict[str, str] = {}
    for sheet_name, frame in manual_sheets.items():
        if frame is None or frame.empty:
            continue
        artifact_path = effective_output_path.parent / f"manual_{sheet_name}_silver.parquet"
        payload = frame.copy()
        for col in ("produto_id", "ingrediente_id", "item", "nome", "nome_produto", "nome_ingrediente", "unidade"):
            if col in payload.columns:
                payload[col] = payload[col].astype("string")
        payload.to_parquet(artifact_path, index=False, engine="pyarrow", compression="snappy")
        manual_artifacts[sheet_name] = str(artifact_path)

    rows_in = int(audit.get("rows_in", 0))
    rows_out = int(audit.get("rows_out", 0))
    audit = {
        **audit,
        "rows_removed": max(rows_in - rows_out, 0),
        "source_rows": source_audit,
        "manual_artifacts": manual_artifacts,
    }

    return effective_output_path, audit


if __name__ == "__main__":
    out_path, audit = run_silver_stage()
    print(f"Silver output: {out_path}")
    print(json.dumps(audit, indent=2, ensure_ascii=True))

