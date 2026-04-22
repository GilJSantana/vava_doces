from src.presentation import controller


def test_run_app_controller_happy_path():
    calls = []

    def render_header_fn():
        calls.append("header")

    def render_sidebar_fn():
        calls.append("sidebar")
        return "adapter", "📊 Dashboard"

    def render_page_fn(page):
        calls.append(("page", page))

    controller.run_app_controller(
        render_header_fn=render_header_fn,
        render_sidebar_fn=render_sidebar_fn,
        render_page_fn=render_page_fn,
    )

    assert calls == [
        "header",
        "sidebar",
        ("page", "📊 Dashboard"),
    ]


def test_run_app_controller_still_renders_page_when_adapter_missing():
    called = {"page": False}

    def render_header_fn():
        return None

    def render_sidebar_fn():
        return None, "💰 Custos de Produção"

    def render_page_fn(page):
        called["page"] = page == "💰 Custos de Produção"

    controller.run_app_controller(
        render_header_fn=render_header_fn,
        render_sidebar_fn=render_sidebar_fn,
        render_page_fn=render_page_fn,
    )

    assert called["page"] is True


def test_perf_logging_flag_is_enabled_from_environment(monkeypatch):
    monkeypatch.setenv("VAVA_PERF_LOG", "true")

    assert controller._is_perf_logging_enabled() is True


