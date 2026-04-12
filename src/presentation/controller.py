"""Orquestração principal da aplicação Streamlit."""

from collections.abc import Callable
import logging
import os
from time import perf_counter

logger = logging.getLogger(__name__)


def _is_perf_logging_enabled() -> bool:
    """Indica se o log de performance está habilitado por variável de ambiente."""
    return os.getenv("VAVA_PERF_LOG", "").strip().lower() in {"1", "true", "yes", "on"}


def _log_perf_step(step_name: str, start_time: float) -> None:
    """Registra duração do passo em milissegundos quando o debug de performance está ativo."""
    if _is_perf_logging_enabled():
        elapsed_ms = (perf_counter() - start_time) * 1000
        logger.info("[perf] %s: %.2f ms", step_name, elapsed_ms)


def run_app_controller(
    render_header_fn: Callable[[], None],
    render_sidebar_fn: Callable[[], tuple[object | None, str]],
    render_page_fn: Callable[[str], None],
) -> None:
    """Executa o fluxo principal do app com navegação desacoplada de serviços."""
    render_header_fn()

    start_time = perf_counter()
    _adapter, page = render_sidebar_fn()
    _log_perf_step("render_sidebar", start_time)

    start_time = perf_counter()
    render_page_fn(page)
    _log_perf_step(f"render_page:{page}", start_time)

