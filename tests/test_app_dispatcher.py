import app


def test_render_selected_page_calls_handler(monkeypatch):
    called = {"ok": False}

    def fake_handler():
        called["ok"] = True

    monkeypatch.setattr(app, "PAGE_HANDLERS", {"p": fake_handler})

    app.render_selected_page("p")

    assert called["ok"] is True


def test_render_selected_page_invalid_page_shows_error(monkeypatch):
    messages = []

    monkeypatch.setattr(app, "PAGE_HANDLERS", {})
    monkeypatch.setattr(app.st, "error", lambda msg: messages.append(msg))

    app.render_selected_page("invalida")

    assert messages == ["❌ Página inválida selecionada"]

