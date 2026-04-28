from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import src.infrastructure.google_oauth2_adapter as google_oauth2_adapter


def test_get_login_url_prefers_secret_redirect_and_percent_encodes_scope(monkeypatch) -> None:
	monkeypatch.setattr(
		google_oauth2_adapter.st,
		"secrets",
		{"OAUTH2_REDIRECT_URI": " https://app.example.com/callback \n"},
		raising=False,
	)

	adapter = google_oauth2_adapter.GoogleOAuth2Adapter(
		client_id=" client-id ",
		client_secret=" secret ",
		redirect_uri="http://localhost:8501",
	)

	url = adapter.get_login_url()
	parsed = urlparse(url)
	query = parse_qs(parsed.query)
	scope_fragment = parsed.query.split("scope=", 1)[1].split("&", 1)[0]

	assert parsed.scheme == "https"
	assert parsed.netloc == "accounts.google.com"
	assert query["client_id"] == ["client-id"]
	assert query["redirect_uri"] == ["https://app.example.com/callback"]
	assert query["scope"] == [" ".join(google_oauth2_adapter.OAUTH2_SCOPES)]
	assert "%20" in scope_fragment
	assert "+" not in scope_fragment


def test_get_canonical_redirect_uri_falls_back_to_constructor_value(monkeypatch) -> None:
	monkeypatch.setattr(google_oauth2_adapter.st, "secrets", {}, raising=False)

	adapter = google_oauth2_adapter.GoogleOAuth2Adapter(
		client_id="client-id",
		client_secret="secret",
		redirect_uri=" http://localhost:8501/callback \n",
	)

	assert adapter._get_canonical_redirect_uri() == "http://localhost:8501/callback"

