"""
Testes de integração entre o adaptador Google Sheets e o serviço de análise.

Estes testes verificam se os componentes funcionam bem juntos.
"""

import pytest
import pandas as pd
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch

from src.infrastructure.google_sheets_adapter import GoogleSheetsAdapter
from src.domain.cost_analysis_service import CostAnalysisService
from src.ports.data_source import DataSourceError


class TestIntegrationAdapterService:
    """Testes de integração entre Adapter e Service."""

    @pytest.fixture
    def mock_adapter(self):
        """Cria um adaptador mockado com dados de teste."""
        adapter = Mock(spec=GoogleSheetsAdapter)

        # Dados de teste para a aba "Custos"
        custos_data = {
            "recipe": ["Bolo de Chocolate", "Bolo de Chocolate", "Bolo de Baunilha"],
            "ingredient": ["Cacau", "Açúcar", "Essência de Baunilha"],
            "qty": [2, 1, 0.5],
            "unit_price": [10.0, 5.0, 15.0]
        }

        # Dados de teste para a aba "Faturamento"
        faturamento_data = {
            "recipe": ["Bolo de Chocolate", "Bolo de Baunilha"],
            "quantity_sold": [10, 5],
            "unit_price": [25.0, 22.0]
        }

        custos_df = pd.DataFrame(custos_data)
        faturamento_df = pd.DataFrame(faturamento_data)

        # Configurar o mock para retornar os dados
        def get_data_side_effect(sheet_name):
            if sheet_name == "Custos":
                return custos_df
            elif sheet_name == "Faturamento":
                return faturamento_df
            else:
                raise DataSourceError(f"Sheet '{sheet_name}' not found")

        adapter.get_data = Mock(side_effect=get_data_side_effect)

        return adapter

    def test_service_with_mock_adapter_calculate_costs(self, mock_adapter):
        """Testa cálculo de custos com adaptador mockado."""
        service = CostAnalysisService(data_source=mock_adapter)

        costs = service.calculate_cost_per_recipe("Custos")

        assert "Bolo de Chocolate" in costs
        assert "Bolo de Baunilha" in costs

        # Bolo de Chocolate: (2 * 10) + (1 * 5) = 25
        assert costs["Bolo de Chocolate"] == Decimal("25")
        # Bolo de Baunilha: 0.5 * 15 = 7.5
        assert costs["Bolo de Baunilha"] == Decimal("7.5")

    def test_service_get_production_costs(self, mock_adapter):
        """Testa recuperação de dados de custos de produção."""
        service = CostAnalysisService(data_source=mock_adapter)

        df = service.get_production_costs()

        assert not df.empty
        assert len(df) == 3
        assert "recipe" in df.columns

    def test_service_get_sales_data(self, mock_adapter):
        """Testa recuperação de dados de faturamento."""
        service = CostAnalysisService(data_source=mock_adapter)

        df = service.get_sales_data()

        assert not df.empty
        assert len(df) == 2
        assert "recipe" in df.columns
        assert "quantity_sold" in df.columns

    def test_service_handles_adapter_error(self):
        """Testa tratamento de erros do adaptador."""
        adapter = Mock(spec=GoogleSheetsAdapter)
        adapter.get_data = Mock(side_effect=DataSourceError("Connection failed"))

        service = CostAnalysisService(data_source=adapter)

        with pytest.raises(DataSourceError):
            service.calculate_cost_per_recipe("Custos")

    def test_service_returns_empty_for_empty_sheet(self):
        """Testa retorno vazio para planilha vazia."""
        adapter = Mock(spec=GoogleSheetsAdapter)
        adapter.get_data = Mock(return_value=pd.DataFrame())

        service = CostAnalysisService(data_source=adapter)

        costs = service.calculate_cost_per_recipe("Custos")

        assert costs == {}


class TestDataValidation:
    """Testes para validação de dados."""

    def test_adapter_raises_on_missing_sheet(self):
        """Testa que o adaptador lança erro para sheet inexistente."""
        adapter = Mock(spec=GoogleSheetsAdapter)
        adapter.get_data = Mock(side_effect=DataSourceError("Sheet not found"))

        service = CostAnalysisService(data_source=adapter)

        with pytest.raises(DataSourceError):
            service.calculate_cost_per_recipe("NonExistentSheet")

    def test_service_validates_required_columns(self):
        """Testa validação de colunas obrigatórias."""
        adapter = Mock(spec=GoogleSheetsAdapter)

        # DataFrame sem a coluna 'unit_price'
        invalid_data = pd.DataFrame({
            "recipe": ["Bolo"],
            "qty": [1]
        })

        adapter.get_data = Mock(return_value=invalid_data)

        service = CostAnalysisService(data_source=adapter)

        with pytest.raises(ValueError, match="missing required column"):
            service.calculate_cost_per_recipe("Custos")


class TestComplexScenarios:
    """Testes para cenários complexos."""

    def test_multiple_recipes_calculation(self):
        """Testa cálculo com múltiplas receitas e ingredientes."""
        adapter = Mock(spec=GoogleSheetsAdapter)

        complex_data = pd.DataFrame({
            "recipe": [
                "Bolo de Chocolate", "Bolo de Chocolate", "Bolo de Chocolate",
                "Brigadeiro", "Brigadeiro",
                "Mousse", "Mousse", "Mousse"
            ],
            "ingredient": [
                "Cacau", "Açúcar", "Farinha",
                "Leite Condensado", "Chocolate em Pó",
                "Chocolate", "Creme de Leite", "Ovo"
            ],
            "qty": [2, 1, 0.5, 1, 0.5, 1, 0.5, 2],
            "unit_price": [10, 5, 8, 15, 12, 20, 10, 2]
        })

        adapter.get_data = Mock(return_value=complex_data)
        service = CostAnalysisService(data_source=adapter)

        costs = service.calculate_cost_per_recipe("Custos")

        # Bolo de Chocolate: (2*10) + (1*5) + (0.5*8) = 29
        assert costs["Bolo de Chocolate"] == Decimal("29")

        # Brigadeiro: (1*15) + (0.5*12) = 21
        assert costs["Brigadeiro"] == Decimal("21")

        # Mousse: (1*20) + (0.5*10) + (2*2) = 20 + 5 + 4 = 29
        assert costs["Mousse"] == Decimal("29")

        # Total de receitas
        assert len(costs) == 3

    def test_case_insensitive_columns(self):
        """Testa se nomes de colunas case-insensitive funcionam."""
        adapter = Mock(spec=GoogleSheetsAdapter)

        data = pd.DataFrame({
            "RECIPE": ["Bolo"],  # Maiúscula
            "QTY": [2],           # Maiúscula
            "UNIT_PRICE": [10]    # Maiúscula
        })

        adapter.get_data = Mock(return_value=data)
        service = CostAnalysisService(data_source=adapter)

        costs = service.calculate_cost_per_recipe("Custos")

        assert costs["Bolo"] == Decimal("20")


