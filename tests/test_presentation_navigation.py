from src.presentation import navigation


class _SidebarCtx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _patch_sidebar_base(monkeypatch):
    monkeypatch.setattr(navigation.st, "cache_data", type("_D", (), {"clear": staticmethod(lambda: None)})())
    monkeypatch.setattr(navigation.st, "sidebar", _SidebarCtx())
    monkeypatch.setattr(navigation.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(navigation.st, "rerun", lambda: None)


def test_render_sidebar_when_adapter_missing(monkeypatch):
    """Sidebar no longer exits early when adapter is missing; it still renders navigation."""
    _patch_sidebar_base(monkeypatch)

    warnings = []
    monkeypatch.setattr(navigation.st, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(navigation.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(navigation.st, "success", lambda *args, **kwargs: None)
    monkeypatch.setattr(navigation.st, "warning", lambda msg: warnings.append(msg))
    monkeypatch.setattr(navigation.st, "error", lambda *args, **kwargs: None)
    monkeypatch.setattr(navigation.st, "radio", lambda *args, **kwargs: navigation.PAGE_DASHBOARD)

    adapter, page = navigation.render_sidebar(
        lambda: None,
        {"bronze_rows": 10, "silver_rows": 8, "quarantine_rows": 2},
    )

    assert adapter is None
    assert page == navigation.PAGE_DASHBOARD
    # Pipeline metrics are no longer shown in the sidebar.
    assert any("desconectado" in str(w).lower() for w in warnings)


def test_render_sidebar_when_adapter_connected(monkeypatch):
    """Sidebar returns the adapter and selected page when connected."""
    _patch_sidebar_base(monkeypatch)

    successes = []
    monkeypatch.setattr(navigation.st, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(navigation.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(navigation.st, "success", lambda msg: successes.append(msg))
    monkeypatch.setattr(navigation.st, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(navigation.st, "error", lambda *args, **kwargs: None)
    monkeypatch.setattr(navigation.st, "radio", lambda *args, **kwargs: navigation.PAGE_PRODUCTION_COSTS)

    adapter, page = navigation.render_sidebar(
        lambda: "adapter_obj",
        {"bronze_rows": 100, "silver_rows": 90, "quarantine_rows": 10},
    )

    assert adapter == "adapter_obj"
    assert page == navigation.PAGE_PRODUCTION_COSTS
    # Pipeline metrics are no longer shown; connection status still visible.
    assert successes == ["✅ Conectado ao Google Sheets"]


def test_page_revenue_impact_not_in_menu():
    """Impacto no Faturamento page is removed from the navigation menu."""
    assert navigation.PAGE_REVENUE_IMPACT not in navigation.PAGE_OPTIONS


def test_page_options_contains_expected_pages():
    """Remaining pages are all present in the navigation menu."""
    expected = {
        navigation.PAGE_DASHBOARD,
        navigation.PAGE_PRODUCTION_COSTS,
        navigation.PAGE_FATURAMENTO,
        navigation.PAGE_DETAILED_ANALYSIS,
    }
    assert expected == set(navigation.PAGE_OPTIONS)


