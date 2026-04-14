#!/usr/bin/env python3
"""
Diagnosis script to identify row loss during deduplication in Silver layer.

Compares record count across Bronze → Silver for each source file and month.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime, timezone
from time import perf_counter

import pandas as pd

# Project root setup
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.medallion_pipeline import (
    LocalRawSource,
    transform_to_silver,
    _extract_month_reference,
    _RAW_DIR,
)
from src.domain.sales_analysis_service import (
    _deduplicate_with_audit,
    _normalise_header,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("diagnosis")


def diagnose_dedup_loss() -> dict:
    """Analyze row loss at each stage of the pipeline."""
    source = LocalRawSource(_RAW_DIR)
    files = source.list_tabular_files()

    if not files:
        logger.warning("No files found in raw directory: %s", _RAW_DIR)
        return {}

    results = {
        "files_analyzed": 0,
        "total_bronze_rows": 0,
        "total_silver_rows": 0,
        "total_dedup_loss": 0,
        "by_file": {},
        "by_month": {},
    }

    logger.info("="*80)
    logger.info("DEDUPLICATION LOSS ANALYSIS")
    logger.info("="*80)

    for meta in files:
        raw_df = source.read_as_dataframe(meta)
        if raw_df is None or raw_df.empty:
            continue

        file_name = str(meta.get("name", ""))
        if "manual_" in file_name:
            logger.info("⏭️  Skipping manual sheet: %s", file_name)
            continue

        bronze_count = len(raw_df)
        logger.info("\n📄 File: %s", file_name)
        logger.info("   Bronze rows: %d", bronze_count)

        # Add source file marker
        if "_source_file" not in raw_df.columns:
            raw_df["_source_file"] = file_name

        # Transform to Silver (includes dedup)
        silver_df, audit = transform_to_silver(raw_df)
        silver_count = len(silver_df)
        loss = bronze_count - silver_count

        logger.info("   Silver rows: %d", silver_count)
        logger.info("   Rows lost: %d (%.2f%%)", loss, (loss / bronze_count * 100) if bronze_count > 0 else 0)

        # Extract months from the silver data
        if "data" in silver_df.columns and "mes_referencia" in silver_df.columns:
            months = silver_df["mes_referencia"].fillna("unknown").astype(str).unique()
            for month in sorted(months):
                month_data = silver_df[silver_df["mes_referencia"] == month]
                logger.info("      %s: %d rows", month, len(month_data))

        # Dedup audit details
        if audit.get("removed", 0) > 0:
            logger.warning("   ⚠️  Dedup removed: %d rows", audit["removed"])
            logger.info("      Key columns: %s", audit.get("key_columns", []))
            logger.info("      By source file: %s", audit.get("removed_by_source_file", {}))
            logger.info("      By month: %s", audit.get("removed_by_month", {}))

        results["files_analyzed"] += 1
        results["total_bronze_rows"] += bronze_count
        results["total_silver_rows"] += silver_count
        results["total_dedup_loss"] += loss

        results["by_file"][file_name] = {
            "bronze": bronze_count,
            "silver": silver_count,
            "loss": loss,
            "audit": audit,
        }

        # Aggregate by month
        if "mes_referencia" in silver_df.columns:
            for month in months:
                month_bronze = len(raw_df[raw_df.get("data", pd.Series(dtype="object")).astype(str).str.contains(month.replace("-", ""), na=False)])
                month_silver = len(silver_df[silver_df["mes_referencia"] == month])
                month_loss = (results["by_month"].get(month, {}).get("loss", 0)) + (month_bronze - month_silver)

                results["by_month"][month] = {
                    "bronze": results["by_month"].get(month, {}).get("bronze", 0) + month_bronze,
                    "silver": results["by_month"].get(month, {}).get("silver", 0) + month_silver,
                    "loss": month_loss,
                }

    # Summary
    logger.info("\n" + "="*80)
    logger.info("SUMMARY")
    logger.info("="*80)
    logger.info("Files analyzed: %d", results["files_analyzed"])
    logger.info("Total Bronze rows: %d", results["total_bronze_rows"])
    logger.info("Total Silver rows: %d", results["total_silver_rows"])
    logger.info("Total loss: %d rows (%.2f%%)",
                results["total_dedup_loss"],
                (results["total_dedup_loss"] / results["total_bronze_rows"] * 100) if results["total_bronze_rows"] > 0 else 0)

    logger.info("\nLoss by month:")
    for month in sorted(results["by_month"].keys()):
        month_data = results["by_month"][month]
        logger.info("   %s: %d → %d (lost %d)",
                   month,
                   month_data["bronze"],
                   month_data["silver"],
                   month_data["loss"])

    return results


if __name__ == "__main__":
    results = diagnose_dedup_loss()
    print("\n✅ Diagnosis complete")
    print(f"Summary: {results['total_dedup_loss']} total rows lost")

