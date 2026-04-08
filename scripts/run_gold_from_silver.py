#!/usr/bin/env python3
"""Run only the GOLD stage from an existing SILVER dataset.

Generates star-schema tables and analytical aggregates in ``data/processed/gold``.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.medallion_pipeline import run_silver_to_gold


def run_gold_stage(
    silver_dir: Path | None = None,
    gold_dir: Path | None = None,
    enrich_cost: bool = False,
) -> tuple[Path, dict[str, int]]:
    """Execute silver->gold transformation and persist parquet outputs."""
    project_root = Path(__file__).resolve().parent.parent
    effective_silver_dir = silver_dir or (project_root / "data" / "processed" / "silver")
    effective_gold_dir = gold_dir or (project_root / "data" / "processed" / "gold")

    tables = run_silver_to_gold(
        silver_df=None,
        silver_dir=effective_silver_dir,
        gold_dir=effective_gold_dir,
        enrich_cost=enrich_cost,
    )
    row_counts = {name: int(len(df)) for name, df in tables.items()}
    return effective_gold_dir, row_counts


if __name__ == "__main__":
    out_dir, counts = run_gold_stage()
    print(f"Gold output dir: {out_dir}")
    print(json.dumps(counts, indent=2, ensure_ascii=True))

