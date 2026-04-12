"""Páginas da aplicação Streamlit."""

from src.presentation.pages.dashboard import show_dashboard
from src.presentation.pages.production_costs import show_production_costs
from src.presentation.pages.detailed_analysis import show_analise_detalhada
from src.presentation.pages.faturamento import show_faturamento

# revenue_impact is preserved on disk but removed from main navigation.
from src.presentation.pages.revenue_impact import show_revenue_impact  # noqa: F401

__all__ = [
    "show_dashboard",
    "show_production_costs",
    "show_revenue_impact",
    "show_analise_detalhada",
    "show_faturamento",
]

