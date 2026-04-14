import app


def test_render_selected_page_calls_handler(monkeypatch):
    called = {"ok": False}

    def fake_handler(service, product_service):
        called["ok"] = (service, product_service) == ("s1", "s2")

    monkeypatch.setattr(app, "PAGE_HANDLERS", {"p": fake_handler})

    app.render_selected_page("p", "s1", "s2")

    assert called["ok"] is True


def test_render_selected_page_invalid_page_shows_error(monkeypatch):
    messages = []

    monkeypatch.setattr(app, "PAGE_HANDLERS", {})
    monkeypatch.setattr(app.st, "error", lambda msg: messages.append(msg))

    app.render_selected_page("invalida", "s1", "s2")

    assert messages == ["❌ Página inválida selecionada"]

