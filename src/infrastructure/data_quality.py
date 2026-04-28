"""Data Quality Validation Module for Gold Layer.

Validates:
- Required columns present
- Data types correct
- Value ranges reasonable
- Business logic constraints
"""

from typing import Dict
import logging

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class DataQualityValidator:
    """Validates gold layer tables for production readiness."""

    # Column schemas for each gold table
    SCHEMAS = {
        "dim_produto": {
            "produto_id": "int64",
            "nome_produto": "object",
        },
        "dim_tempo": {
            "data_id": "int64",
            "data": "datetime64[ns]",
            "dia": "int64",
            "mes": "int64",
            "ano": "int64",
            "trimestre": "int64",
            "nome_mes": "object",
            "dia_semana": "object",
        },
        "fato_vendas": {
            "venda_id": "int64",
            "produto_id": "int64",
            "data_id": "int64",
            "num_venda": "object",
            "cliente": "object",
            "quantidade": "float64",
            "valor_unitario": "float64",
            "valor_total": "float64",
            "custo": "float64",
            "margem": "float64",
        },
    }

    def __init__(self, verbose: bool = True):
        """Initialize validator.
        
        Args:
            verbose: Log detailed results to console
        """
        self.verbose = verbose
        self.results = {}

    def validate_all(
        self,
        dim_produto: pd.DataFrame,
        dim_tempo: pd.DataFrame,
        fato_vendas: pd.DataFrame,
    ) -> Dict[str, bool]:
        """Validate all gold layer tables.
        
        Args:
            dim_produto: Product dimension table
            dim_tempo: Temporal dimension table
            fato_vendas: Sales fact table
            
        Returns:
            Dictionary with validation results per table
        """
        self._log("="*70)
        self._log("DATA QUALITY VALIDATION — GOLD LAYER")
        self._log("="*70)
        self._log("")

        results = {}
        
        # Validate dimensions
        results["dim_produto"] = self.validate_dim_produto(dim_produto)
        results["dim_tempo"] = self.validate_dim_tempo(dim_tempo)
        
        # Validate facts (with FK references to dimensions)
        results["fato_vendas"] = self.validate_fato_vendas(
            fato_vendas, dim_produto, dim_tempo
        )

        # Summary
        self._log("")
        all_pass = all(results.values())
        status = "✅ PASSED" if all_pass else "❌ FAILED"
        self._log(f"OVERALL STATUS: {status}")
        self._log("="*70)

        self.results = results
        return results

    def validate_dim_produto(self, df: pd.DataFrame) -> bool:
        """Validate product dimension."""
        self._log("🔍 Validating dim_produto...")
        all_pass = True

        try:
            # Required columns
            required = ["produto_id", "nome_produto"]
            assert all(col in df.columns for col in required), \
                f"Missing columns: {set(required) - set(df.columns)}"
            self._log("  ✅ Required columns present")

            # Types
            assert df["produto_id"].dtype == "int64", \
                f"produto_id must be int64, got {df['produto_id'].dtype}"
            assert df["nome_produto"].dtype == "object", \
                f"nome_produto must be object, got {df['nome_produto'].dtype}"
            self._log("  ✅ Data types correct")

            # Primary key
            assert df["produto_id"].nunique() == len(df), \
                f"Duplicate produto_id found ({len(df)} rows, {df['produto_id'].nunique()} unique)"
            self._log(f"  ✅ Primary key valid (produto_id unique: {len(df)} rows)")

            # No nulls in key
            assert df["produto_id"].notna().all(), "Null values in produto_id"
            assert df["nome_produto"].notna().all(), "Null values in nome_produto"
            self._log("  ✅ No null values in key columns")

            self._log(f"  ✅ dim_produto VALID ({len(df)} products)")
            return True

        except AssertionError as e:
            self._log(f"  ❌ FAILED: {e}")
            all_pass = False
            return False

    def validate_dim_tempo(self, df: pd.DataFrame) -> bool:
        """Validate temporal dimension."""
        self._log("🔍 Validating dim_tempo...")
        all_pass = True

        try:
            # Required columns
            required = ["data_id", "data", "dia", "mes", "ano", "trimestre", 
                       "nome_mes", "dia_semana"]
            assert all(col in df.columns for col in required), \
                f"Missing columns: {set(required) - set(df.columns)}"
            self._log("  ✅ Required columns present")

            # Types
            assert df["data_id"].dtype == "int64", "data_id must be int64"
            assert pd.api.types.is_datetime64_any_dtype(df["data"]), \
                "data must be datetime64"
            self._log("  ✅ Data types correct")

            # Primary key
            assert df["data_id"].nunique() == len(df), \
                f"Duplicate data_id ({len(df)} rows, {df['data_id'].nunique()} unique)"
            self._log(f"  ✅ Primary key valid (data_id unique: {len(df)} rows)")

            # No nulls in key
            assert df["data_id"].notna().all(), "Null values in data_id"
            assert df["data"].notna().all(), "Null values in data"
            self._log("  ✅ No null values in key columns")

            # Value ranges
            assert (df["dia"] >= 1).all() and (df["dia"] <= 31).all(), \
                "dia must be 1-31"
            assert (df["mes"] >= 1).all() and (df["mes"] <= 12).all(), \
                "mes must be 1-12"
            assert (df["trimestre"] >= 1).all() and (df["trimestre"] <= 4).all(), \
                "trimestre must be 1-4"
            self._log("  ✅ Value ranges valid")

            self._log(f"  ✅ dim_tempo VALID ({len(df)} dates)")
            return True

        except AssertionError as e:
            self._log(f"  ❌ FAILED: {e}")
            return False

    def validate_fato_vendas(
        self,
        df: pd.DataFrame,
        dim_produto: pd.DataFrame,
        dim_tempo: pd.DataFrame,
    ) -> bool:
        """Validate sales fact table with FK integrity."""
        self._log("🔍 Validating fato_vendas...")
        all_pass = True

        try:
            # Required columns
            required = ["venda_id", "produto_id", "data_id", "quantidade", 
                       "valor_unitario", "valor_total", "custo", "margem"]
            assert all(col in df.columns for col in required), \
                f"Missing columns: {set(required) - set(df.columns)}"
            self._log("  ✅ Required columns present")

            # Types
            assert df["venda_id"].dtype == "int64", "venda_id must be int64"
            assert df["produto_id"].dtype == "int64", "produto_id must be int64"
            assert df["data_id"].dtype == "int64", "data_id must be int64"
            assert df["quantidade"].dtype == "float64", "quantidade must be float64"
            assert df["valor_total"].dtype == "float64", "valor_total must be float64"
            assert df["custo"].dtype == "float64", "custo must be float64"
            assert df["margem"].dtype == "float64", "margem must be float64"
            self._log("  ✅ Data types correct")

            # Primary key
            assert df["venda_id"].nunique() == len(df), \
                f"Duplicate venda_id ({len(df)} rows, {df['venda_id'].nunique()} unique)"
            self._log(f"  ✅ Primary key valid (venda_id unique: {len(df)} rows)")

            # Foreign key constraints
            orphan_produtos = (~df["produto_id"].isin(dim_produto["produto_id"])).sum()
            assert orphan_produtos == 0, \
                f"Found {orphan_produtos} orphaned produto_id values"
            self._log("  ✅ FK produto_id: 0 orphans")

            orphan_datas = (~df["data_id"].isin(dim_tempo["data_id"])).sum()
            assert orphan_datas == 0, \
                f"Found {orphan_datas} orphaned data_id values"
            self._log("  ✅ FK data_id: 0 orphans")

            # No nulls in key
            assert df["venda_id"].notna().all(), "Null values in venda_id"
            assert df["produto_id"].notna().all(), "Null values in produto_id"
            assert df["data_id"].notna().all(), "Null values in data_id"
            self._log("  ✅ No null values in key columns")

            # Business logic: quantities > 0
            neg_qty = (df["quantidade"] <= 0).sum()
            assert neg_qty == 0, \
                f"Found {neg_qty} rows with quantidade <= 0"
            self._log("  ✅ All quantities > 0")

            # Business logic: values >= 0
            neg_valor = (df["valor_total"] < 0).sum()
            assert neg_valor == 0, \
                f"Found {neg_valor} rows with valor_total < 0"
            self._log("  ✅ All valores >= 0")

            # Business logic: custo >= 0
            neg_custo = (df["custo"] < 0).sum()
            assert neg_custo == 0, \
                f"Found {neg_custo} rows with custo < 0"
            self._log("  ✅ All custos >= 0")

            # Business logic: margem in reasonable range (-100%, +1000%)
            # Unit margin may legitimately exceed 100 in absolute currency;
            # the bounded metric is margem_percentual (percentage points).
            invalid_margem = (np.isinf(df["margem"]) | np.isnan(df["margem"])).sum()
            assert invalid_margem == 0, \
                f"Found {invalid_margem} rows with inf/NaN margem"
            if "margem_percentual" in df.columns:
                margem_pct = pd.to_numeric(df["margem_percentual"], errors="coerce")
            else:
                faturamento = pd.Series(
                    pd.to_numeric(df.get("valor_total", pd.Series(index=df.index, dtype="float64")), errors="coerce"),
                    index=df.index,
                    dtype="float64",
                )
                lucro_total = faturamento - pd.Series(pd.to_numeric(df["custo"], errors="coerce"), index=df.index, dtype="float64")
                margem_pct = (lucro_total / faturamento.mask(faturamento.eq(0))) * 100.0
            invalid_margem_pct = np.isinf(margem_pct).sum()
            assert invalid_margem_pct == 0, \
                f"Found {invalid_margem_pct} rows with inf margem_percentual"
            margem_pct_valid = margem_pct.dropna()
            assert ((margem_pct_valid >= -100) & (margem_pct_valid <= 1000)).all(), \
                "Margem percentual values outside reasonable range (-100%, +1000%)"
            self._log("  ✅ All margins in reasonable range (-100%, +1000%)")

            # Statistical sanity checks
            avg_margem = df["margem"].mean()
            median_margem = df["margem"].median()
            self._log(f"  📊 Margin statistics: avg={avg_margem:.2f}, median={median_margem:.2f}")

            self._log(f"  ✅ fato_vendas VALID ({len(df)} sales facts)")
            return True

        except AssertionError as e:
            self._log(f"  ❌ FAILED: {e}")
            return False

    def _log(self, message: str) -> None:
        """Log message to both logger and console."""
        if self.verbose:
            print(message)
        logger.info(message)

    @staticmethod
    def get_validation_report(results: Dict[str, bool]) -> str:
        """Generate human-readable validation report."""
        lines = []
        lines.append("")
        lines.append("=" * 70)
        lines.append("DATA QUALITY VALIDATION REPORT")
        lines.append("=" * 70)
        
        for table, passed in results.items():
            status = "✅ PASSED" if passed else "❌ FAILED"
            lines.append(f"  {table:20s}: {status}")
        
        all_pass = all(results.values())
        lines.append("=" * 70)
        lines.append(f"Overall: {'✅ ALL TABLES VALID' if all_pass else '❌ VALIDATION FAILED'}")
        lines.append("=" * 70)
        lines.append("")
        
        return "\n".join(lines)

