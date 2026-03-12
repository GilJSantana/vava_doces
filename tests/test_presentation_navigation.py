from src.presentation import navigation


class _SidebarCtx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _patch_sidebar_base(monkeypatch):
    monkeypatch.setattr(navigation.st, "sidebar", _SidebarCtx())
    monkeypatch.setattr(navigation.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(navigation.st, "cache_resource", type("_C", (), {"clear": staticmethod(lambda: None)})())
    monkeypatch.setattr(navigation.st, "rerun", lambda: None)


def test_render_sidebar_when_adapter_missing(monkeypatch):
    _patch_sidebar_base(monkeypatch)

    errors = []
    monkeypatch.setattr(navigation.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(navigation.st, "success", lambda *args, **kwargs: None)
    monkeypatch.setattr(navigation.st, "error", lambda msg: errors.append(msg))
    monkeypatch.setattr(navigation.st, "radio", lambda *args, **kwargs: navigation.PAGE_DASHBOARD)

    adapter, page = navigation.render_sidebar(lambda: None)

    assert adapter is None
    assert page == ""
    assert errors == ["❌ Desconectado - Configure as credenciais"]


def test_render_sidebar_when_adapter_connected(monkeypatch):
    _patch_sidebar_base(monkeypatch)

    successes = []
    monkeypatch.setattr(navigation.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(navigation.st, "success", lambda msg: successes.append(msg))
    monkeypatch.setattr(navigation.st, "error", lambda *args, **kwargs: None)
    monkeypatch.setattr(navigation.st, "radio", lambda *args, **kwargs: navigation.PAGE_REVENUE_IMPACT)

    adapter, page = navigation.render_sidebar(lambda: "adapter_obj")

    assert adapter == "adapter_obj"
    assert page == navigation.PAGE_REVENUE_IMPACT
    assert successes == ["✅ Conectado ao Google Sheets"]

