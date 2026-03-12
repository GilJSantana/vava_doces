"""Fábrica de serviços de análise da aplicação."""

from collections.abc import Callable

from src.domain.cost_analysis_service import CostAnalysisService


def build_analysis_services(
    adapter,
    product_service_factory: Callable[[object], object | None],
) -> tuple[object | None, object | None]:
    """Cria serviços de custos e produtos com baixo acoplamento ao app."""
    if adapter is None:
        return None, None

    cost_service = CostAnalysisService(data_source=adapter)
    product_service = product_service_factory(adapter)
    return cost_service, product_service

