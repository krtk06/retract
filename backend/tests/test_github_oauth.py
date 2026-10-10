"""The GitHub OAuth path, which had no tests at all until a sign-in expired.

A ten-minute state TTL shipped unnoticed for exactly this reason: nothing
exercised the flow, so nothing could report that ten minutes is shorter than a
human authorizing. These tests pin the window, the two ways it can fail, and the
promise that a browser is returned to the app instead of a bare JSON body at an
API URL.
"""

import pytest
from fastapi.testclient import TestClient

from app.routers import auth
from app.routers.auth import _STATE_TTL

FRONTEND = "http://localhost:5177"
BROWSER = {"accept": "text/html,application/xhtml+xml"}
JSON = {"accept": "application/json"}

GITHUB_ID = 1234567
GITHUB_LOGIN = "krtk06"


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload


@pytest.fixture
def oauth(monkeypatch: pytest.MonkeyPatch):
    """A sign-in environment: fakeredis for state, stubbed GitHub, no network."""
    import fakeredis

    from app.config import get_settings

    store = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(auth, "_state_store", lambda: store)
    monkeypatch.setenv("RETRACT_GITHUB_CLIENT_ID", "Iv1.0123456789abcdef")
    monkeypatch.setenv("RETRACT_GITHUB_CLIENT_SECRET", "0123456789abcdef" * 2 + "01234567")
    monkeypatch.setenv(
        "RETRACT_GITHUB_OAUTH_REDIRECT_URI", "http://localhost:8110/api/auth/github/callback"
    )
    monkeypatch.setenv("RETRACT_FRONTEND_URL", FRONTEND)
    # `get_settings` is lru_cached, so the first call in the process freezes the
    # settings and later env changes are invisible to it. Clear it on the way in
    # and on the way out, or these tests would read whatever the previous test left.
    get_settings.cache_clear()
    monkeypatch.setattr(
        auth.httpx,
        "post",
        lambda url, **kwargs: _FakeResponse({"access_token": "gho_testtoken"}),
    )
    monkeypatch.setattr(
        auth.httpx,
        "get",
        lambda url, **kwargs: _FakeResponse({"id": GITHUB_ID, "login": GITHUB_LOGIN}),
    )
    yield store
    get_settings.cache_clear()


def _authorize_url(client: TestClient, headers: dict | None = None) -> str:
    response = client.get("/api/auth/github/login", headers=headers or {}, follow_redirects=False)
    assert response.status_code in (302, 307), response.text
    return response.headers["location"]


def _state_from(url: str) -> str:
    from urllib.parse import parse_qs, urlparse

    return parse_qs(urlparse(url).query)["state"][0]


def _error_code_in(location: str) -> str | None:
    """The auth_error carried by a redirect, or None.

    Asserted on the parsed URL rather than the exact string: what matters is
    where the user lands and what the app is told, not whether the configured
    frontend URL happened to carry a trailing slash.
    """
    from urllib.parse import parse_qs, urlparse

    parts = urlparse(location)
    assert f"{parts.scheme}://{parts.netloc}" == FRONTEND
    return parse_qs(parts.query).get("auth_error", [None])[0]


def test_login_redirects_to_github_with_a_state(client: TestClient, oauth) -> None:
    url = _authorize_url(client)
    assert url.startswith("https://github.com/login/oauth/authorize?")
    assert "scope=read:user" in url
    assert oauth.exists(f"oauth_state:{_state_from(url)}")


def test_callback_signs_the_user_in(client: TestClient, oauth) -> None:
    state = _state_from(_authorize_url(client))
    response = client.get(
        "/api/auth/github/callback",
        params={"code": "abc", "state": state},
        headers=BROWSER,
        follow_redirects=False,
    )
    assert response.status_code in (302, 307)
    assert response.headers["location"].rstrip("/") == FRONTEND
    assert "ai_intel_token" in response.cookies

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["github_id"] == GITHUB_ID
    assert me.json()["login"] == GITHUB_LOGIN


def test_an_expired_state_returns_the_user_to_the_app(client: TestClient, oauth) -> None:
    # Nothing in the store at all: the window lapsed before the user came back.
    response = client.get(
        "/api/auth/github/callback",
        params={"code": "abc", "state": "never-issued"},
        headers=BROWSER,
        follow_redirects=False,
    )
    assert response.status_code in (302, 307)
    assert _error_code_in(response.headers["location"]) == "expired_state"


def test_a_replayed_state_says_used_not_expired(client: TestClient, oauth) -> None:
    """A refresh after signing in must not tell the user to start over."""
    state = _state_from(_authorize_url(client))
    first = client.get(
        "/api/auth/github/callback",
        params={"code": "abc", "state": state},
        headers=BROWSER,
        follow_redirects=False,
    )
    assert first.status_code in (302, 307)
    assert first.headers["location"].rstrip("/") == FRONTEND

    replay = client.get(
        "/api/auth/github/callback",
        params={"code": "abc", "state": state},
        headers=BROWSER,
        follow_redirects=False,
    )
    assert _error_code_in(replay.headers["location"]) == "used_state"


def test_a_json_client_still_gets_a_400(client: TestClient, oauth) -> None:
    """The redirect is for browsers; anything asking for JSON keeps the status."""
    response = client.get(
        "/api/auth/github/callback",
        params={"code": "abc", "state": "never-issued"},
        headers=JSON,
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "expired_state"


def test_unconfigured_oauth_reaches_the_app_instead_of_a_bare_400(
    client: TestClient, oauth, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import get_settings

    monkeypatch.setenv("RETRACT_GITHUB_CLIENT_ID", "")
    get_settings.cache_clear()  # the env changed after the fixture's clear
    response = client.get("/api/auth/github/login", headers=BROWSER, follow_redirects=False)
    assert response.status_code in (302, 307)
    assert _error_code_in(response.headers["location"]) == "not_configured"


def test_the_sign_in_window_is_thirty_minutes() -> None:
    """Pinned so the window cannot silently shrink back to ten minutes."""
    assert _STATE_TTL == 1800
