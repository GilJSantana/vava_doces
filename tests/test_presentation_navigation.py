    adapter, page = navigation.render_sidebar(lambda: "adapter_obj")
    adapter, page = navigation.render_sidebar(lambda: None)
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
    _patch_sidebar_base(monkeypatch)

    infos = []
    errors = []
    monkeypatch.setattr(navigation.st, "info", lambda msg: infos.append(msg))
    monkeypatch.setattr(navigation.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(navigation.st, "success", lambda *args, **kwargs: None)
    monkeypatch.setattr(navigation.st, "error", lambda msg: errors.append(msg))
    monkeypatch.setattr(navigation.st, "radio", lambda *args, **kwargs: navigation.PAGE_DASHBOARD)
    adapter, page = navigation.render_sidebar(
        lambda: None,
        {"bronze_rows": 10, "silver_rows": 8, "quarantine_rows": 2},
    )
    adapter, page = navigation.render_sidebar(lambda: None)

    assert adapter is None
    assert page == ""
    assert "Bronze (Total): 10" in infos[0]
    assert errors == ["❌ Desconectado - Configure as credenciais"]


def test_render_sidebar_when_adapter_connected(monkeypatch):
    _patch_sidebar_base(monkeypatch)

    infos = []
    successes = []
    monkeypatch.setattr(navigation.st, "info", lambda msg: infos.append(msg))
    monkeypatch.setattr(navigation.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(navigation.st, "success", lambda msg: successes.append(msg))
    monkeypatch.setattr(navigation.st, "error", lambda *args, **kwargs: None)
    monkeypatch.setattr(navigation.st, "radio", lambda *args, **kwargs: navigation.PAGE_REVENUE_IMPACT)
    adapter, page = navigation.render_sidebar(
        lambda: "adapter_obj",
        {"bronze_rows": 100, "silver_rows": 90, "quarantine_rows": 10},
    )
    adapter, page = navigation.render_sidebar(lambda: "adapter_obj")

    assert adapter == "adapter_obj"
    assert page == navigation.PAGE_REVENUE_IMPACT
    assert "Silver (Deduped): 90" in infos[0]
    assert successes == ["✅ Conectado ao Google Sheets"]

