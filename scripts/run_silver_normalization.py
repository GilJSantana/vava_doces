#!/usr/bin/env python3
"""Run only the silver normalization stage, independent from the dashboard.

This script loads current raw files from ``data/raw`` and materializes a
normalized silver dataset ready for aggregations by date, product and channel.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.medallion_pipeline import LocalRawSource, load_raw
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
    raw_df = load_raw(source)
    if raw_df.empty:
        raise RuntimeError(f"No raw data found in: {effective_raw_dir}")

    silver_df, audit = normalize_sales_to_silver_with_audit(raw_df)
    effective_output_path.parent.mkdir(parents=True, exist_ok=True)
    silver_df.to_parquet(effective_output_path, index=False, engine="pyarrow", compression="snappy")

    return effective_output_path, audit


if __name__ == "__main__":
    out_path, audit = run_silver_stage()
    print(f"Silver output: {out_path}")
    print(json.dumps(audit, indent=2, ensure_ascii=True))

