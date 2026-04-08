"""Serviço para análise de produtos com integração da receita, matéria-prima e vendas.
Consolida dados das abas Receita, Matéria Prima e Produtos para apresentação no Streamlit.
"""
from __future__ import annotations
from decimal import Decimal
from typing import Any, Dict, Optional, TYPE_CHECKING
import pandas as pd
from src.ports.data_source import DataSource, DataSourceError
if TYPE_CHECKING:
    from src.infrastructure.gold_adapter import GoldParquetAdapter
class ProductAnalysisService:
    """
    Serviço que integra dados de Receita, Matéria Prima e Produtos
    para análise consolidada de custos e impacto no faturamento.
    Suporta dois modos de operação:
    1. Raw (padrão): Lê dados brutos de Receita, Matéria Prima, Produtos e Vendas
    2. Gold (opcional): Lê dados normalizados e deduplicated do Parquet star schema
    """
    def __init__(
        self,
        data_source: DataSource,
        gold_source: Optional[GoldParquetAdapter] = None,
    ):
        self.data_source = data_source
        self.gold_source = gold_source
        self._cache_receita: Optional[pd.DataFrame] = None
        self._cache_materia_prima: Optional[pd.DataFrame] = None
        self._cache_produtos: Optional[pd.DataFrame] = None
        self._cache_vendas: Optional[pd.DataFrame] = None
        self._receita_loaded = False
        self._materia_prima_loaded = False
        self._produtos_loaded = False
        self._vendas_loaded = False
        self._cache_product_cost_summary: Optional[pd.DataFrame] = None
    def _copy_df(self, df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
        """Retorna cópia defensiva do DataFrame cacheado."""
        if df is None:
            return None
        return df.copy()
    def _load_first_sheet(self, sheet_names: list[str]) -> Optional[pd.DataFrame]:
        """Tenta carregar a primeira aba existente da lista."""
        for name in sheet_names:
            try:
                return self.data_source.get_data(name)
            except (DataSourceError, KeyError, ValueError):
                continue
        return None
    def _get_receita_data(self) -> Optional[pd.DataFrame]:
        """Carrega dados da aba Receita com cache por instância do serviço."""
        if not self._receita_loaded:
            self._cache_receita = self._load_first_sheet(["Receita", "Receitas", "BOM - Receitas"])
            self._receita_loaded = True
        return self._copy_df(self._cache_receita)
    def _get_materia_prima_data(self) -> Optional[pd.DataFrame]:
        """Carrega dados da aba Matéria Prima com cache por instância do serviço."""
        if not self._materia_prima_loaded:
            self._cache_materia_prima = self._load_first_sheet(
                ["Matéria Prima", "Materia Prima", "Matria Prima", "Insumos"]
            )
            self._materia_prima_loaded = True
        return self._copy_df(self._cache_materia_prima)
    def _get_produtos_data(self) -> Optional[pd.DataFrame]:
        """Carrega dados da aba Produtos com cache por instância do serviço."""
        if not self._produtos_loaded:
            self._cache_produtos = self._load_first_sheet(["Produtos", "Cadastro de Produtos", "Produto"])
            self._produtos_loaded = True
        return self._copy_df(self._cache_produtos)
    def _get_vendas_data(self) -> Optional[pd.DataFrame]:
        """Carrega dados de vendas/faturamento com cache por instância do serviço."""
        if not self._vendas_loaded:
            self._cache_vendas = self._load_first_sheet(
                [
                    "Vendas Diarias",
                    "Vendas Diárias",
                    "Resumo Diário",
                    "Resumo Diario",
                    "Faturamento",
                    "Vendas",
                ]
            )
            self._vendas_loaded = True
        return self._copy_df(self._cache_vendas)
    def get_product_cost_summary(self) -> pd.DataFrame:
        """Get product cost summary."""
        if self._cache_product_cost_summary is not None:
            return self._cache_product_cost_summary.copy()
        receita = self._get_receita_data()
        materia = self._get_materia_prima_data()
        produtos = self._get_produtos_data()
        if receita is None or materia is None or produtos is None:
            return pd.DataFrame()
        # Basic consolidation: merge by product name
        result = produtos.copy()
        self._cache_product_cost_summary = result
        return result.copy()
    def get_sales_data(self, prefer_gold: bool = False) -> Optional[pd.DataFrame]:
        """Carrega dados de vendas, com opção de preferir gold sobre raw.
        Args:
            prefer_gold: Se True, tenta gold layer primeiro; se False, usa raw.
        Returns:
            DataFrame com dados de vendas, ou None se não encontrar.
        """
        if prefer_gold and self.gold_source is not None:
            try:
                return self.gold_source.load_gold("fato_vendas")
            except Exception:
                pass
        return self._get_vendas_data()
    def get_receita_data(self) -> Optional[pd.DataFrame]:
        """Get recipe/cost data."""
        return self._get_receita_data()
    def get_materia_prima_data(self) -> Optional[pd.DataFrame]:
        """Get raw materials data."""
        return self._get_materia_prima_data()
    def get_produtos_data(self) -> Optional[pd.DataFrame]:
        """Get products data."""
        return self._get_produtos_data()
