"""Factory functions for creating services with optional gold layer support."""

from pathlib import Path
from typing import Optional
import os

from src.infrastructure.google_sheets_adapter import GoogleSheetsAdapter
from src.infrastructure.gold_adapter import GoldParquetAdapter
from src.domain.product_analysis_service import ProductAnalysisService
from src.ports.data_source import GoldDataSource


def create_product_analysis_service_with_gold(
    use_gold: bool = True,
    gold_dir: Optional[Path] = None,
    creds_path: Optional[str] = None,
    sheet_id: Optional[str] = None,
) -> ProductAnalysisService:
    """Factory function to create ProductAnalysisService with optional gold support.

    Args:
        use_gold: If True, attach GoldParquetAdapter for star schema access.
        gold_dir: Path to gold directory. Defaults to data/processed/gold/
        creds_path: Path to Google service account credentials JSON.
                   Defaults to GOOGLE_APPLICATION_CREDENTIALS env var.
        sheet_id: Google Sheets ID. Defaults to GOOGLE_SHEET_ID env var.

    Returns:
        ProductAnalysisService instance with optional gold_source.

    Example:
        # Use gold layer if available, fallback to raw
        service = create_product_analysis_service_with_gold(use_gold=True)
        sales = service.get_sales_data(prefer_gold=True)

        # Use only raw data (backward compatible)
        service = create_product_analysis_service_with_gold(use_gold=False)
        sales = service.get_sales_data(prefer_gold=False)
    """
    # Create raw data source (Google Sheets)
    creds = creds_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    sheet = sheet_id or os.getenv("GOOGLE_SHEET_ID")
    raw_source = GoogleSheetsAdapter(credential_file=creds, sheet_id=sheet)

    # Optionally attach gold source (Parquet star schema)
    gold_source: Optional[GoldDataSource] = None
    if use_gold:
        gold_source = GoldParquetAdapter(gold_dir=gold_dir)

    return ProductAnalysisService(data_source=raw_source, gold_source=gold_source)

