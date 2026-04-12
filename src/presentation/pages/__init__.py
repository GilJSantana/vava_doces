"""Páginas da aplicação Streamlit."""

from src.presentation.pages.dashboard import show_dashboard
from src.presentation.pages.production_costs import show_production_costs
from src.presentation.pages.faturamento import show_faturamento

# Kept on disk for reference but no longer exposed in navigation.
# from src.presentation.pages.detailed_analysis import show_analise_detalhada
# from src.presentation.pages.revenue_impact import show_revenue_impact

__all__ = [
    "show_dashboard",
    "show_production_costs",
    "show_faturamento",
]

