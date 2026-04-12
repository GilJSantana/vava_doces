"""Páginas da aplicação Streamlit."""

from src.presentation.pages.dashboard import show_dashboard
from src.presentation.pages.production_costs import show_production_costs
from src.presentation.pages.faturamento import show_faturamento


__all__ = [
    "show_dashboard",
    "show_production_costs",
    "show_faturamento",
]

