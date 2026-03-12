import pytest

from src.presentation import controller


class _StopExecution(Exception):
    """Exceção auxiliar para simular st.stop em testes."""


def test_run_app_controller_happy_path():
    calls = []

    def render_header_fn():
        calls.append("header")

    def render_sidebar_fn():
        calls.append("sidebar")
        return "adapter", "📊 Dashboard"

    def init_services_fn(adapter):
        calls.append(("services", adapter))
        return "service", "product_service"

    def render_page_fn(page, service, product_service):
        calls.append(("page", page, service, product_service))

    controller.run_app_controller(
        render_header_fn=render_header_fn,
        render_sidebar_fn=render_sidebar_fn,
        init_services_fn=init_services_fn,
        render_page_fn=render_page_fn,
    )

    assert calls == [
        "header",
        "sidebar",
        ("services", "adapter"),
        ("page", "📊 Dashboard", "service", "product_service"),
    ]


def test_run_app_controller_stops_when_adapter_missing(monkeypatch):
    def fake_stop():
        raise _StopExecution()

    monkeypatch.setattr(controller.st, "stop", fake_stop)

    called = {"page": False, "services": False}

    def render_header_fn():
        return None

    def render_sidebar_fn():
        return None, ""

    def init_services_fn(adapter):
        called["services"] = True
        return "service", "product_service"

    def render_page_fn(page, service, product_service):
        called["page"] = True

    with pytest.raises(_StopExecution):
        controller.run_app_controller(
            render_header_fn=render_header_fn,
            render_sidebar_fn=render_sidebar_fn,
            init_services_fn=init_services_fn,
            render_page_fn=render_page_fn,
        )

    assert called["services"] is False
    assert called["page"] is False


def test_perf_logging_flag_is_enabled_from_environment(monkeypatch):
    monkeypatch.setenv("VAVA_PERF_LOG", "true")

    assert controller._is_perf_logging_enabled() is True


