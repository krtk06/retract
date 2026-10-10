"""The GitHub OAuth path, which had no tests at all until a sign-in expired.

A ten-minute state TTL shipped unnoticed for exactly this reason: nothing
exercised the flow, so nothing could report that ten minutes is shorter than a
human authorizing. These tests pin the window, the two ways it can fail, and the
promise that a browser is returned to the app instead of a bare JSON body at an
API URL.
"""

from itertools import count

import pytest
from fastapi.testclient import TestClient

from app.routers import auth
from app.routers.auth import _STATE_TTL

FRONTEND = "http://localhost:5177"
BROWSER = {"accept": "text/html,application/xhtml+xml"}
JSON = {"accept": "application/json"}

GITHUB_ID = 1234567
GITHUB_LOGIN = "krtk06"

# Every test needs its own GitHub identity: the database is session-scoped, so a
# shared id would let an earlier test own the identity and this one would
# (correctly, from the app's point of view) land on that earlier account.
_IDENTITY_SEQ = count(9_000_000)


def _next_github_id() -> int:
    return next(_IDENTITY_SEQ)


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

    # GitHub returns one payload per endpoint, so the stub dispatches on the URL:
    # /user carries the identity, /user/emails the addresses the link is built on.
    # A neutral default no test registers, so an earlier case cannot quietly
    # claim the address a later one wants to register.
    github_id = _next_github_id()
    # Unique per test for the same reason the id is: the address lands on the
    # created user, and users.email is unique across the session-scoped database.
    emails: dict = {"list": [(f"user-{github_id}@example.com", True)], "status": 200}

    class _Response:
        def __init__(self, payload, status_code: int = 200) -> None:
            self._payload = payload
            self.status_code = status_code

        def json(self):
            return self._payload

    def fake_get(url: str, **kwargs):
        if url.endswith("/user/emails"):
            if emails["status"] != 200:
                return _Response([], emails["status"])
            return _Response(
                [
                    {"email": address, "verified": verified, "primary": index == 0}
                    for index, (address, verified) in enumerate(emails["list"])
                ]
            )
        return _Response({"id": github_id, "login": GITHUB_LOGIN})

    monkeypatch.setattr(
        auth.httpx,
        "post",
        lambda url, **kwargs: _Response({"access_token": "gho_testtoken"}),
    )
    monkeypatch.setattr(auth.httpx, "get", fake_get)
    yield {"emails": emails, "store": store, "github_id": github_id}
    get_settings.cache_clear()


def _monkey_emails(oauth, entries: list) -> None:
    """Set what /user/emails reports. Entries are addresses, or (address, verified)."""
    oauth["emails"]["list"] = [(e, True) if isinstance(e, str) else e for e in entries]
    oauth["emails"]["status"] = 200


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
    assert oauth["store"].exists(f"oauth_state:{_state_from(url)}")


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
    assert me.json()["github_id"] == oauth["github_id"]
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


def _register_email_account(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/auth/register", json={"email": email, "password": "long-enough-password"}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _sign_in_again(client: TestClient, headers: dict, params: dict) -> object:
    client.post("/api/auth/logout")
    return client.get(
        "/api/auth/github/callback", params=params, headers=headers, follow_redirects=False
    )


def test_links_a_github_identity_to_the_matching_email_account(client: TestClient, oauth) -> None:
    """One human, one account: GitHub and the password reach the same repos.

    Without this every OAuth sign-in minted a fresh user, so signing in with
    GitHub produced an empty dashboard next to the repositories the same person
    had registered with their email.
    """
    owner = _register_email_account(client, "link-owner@example.com")
    state = _state_from(_authorize_url(client))

    _monkey_emails(oauth, ["link-owner@example.com"])
    client.get(
        "/api/auth/github/callback",
        params={"code": "abc", "state": state},
        headers=BROWSER,
        follow_redirects=False,
    )

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == owner["id"], "GitHub sign-in must land on the same account"
    # The account keeps its own identity: neither the login nor the email moves.
    assert me.json()["login"] == owner["login"]
    assert me.json()["email"] == "link-owner@example.com"


def test_an_unverified_email_does_not_link(client: TestClient, oauth) -> None:
    """Linking on an unverified address would be account takeover."""
    owner = _register_email_account(client, "unverified-owner@example.com")
    state = _state_from(_authorize_url(client))

    _monkey_emails(oauth, [("unverified-owner@example.com", False)])
    client.get(
        "/api/auth/github/callback",
        params={"code": "abc", "state": state},
        headers=BROWSER,
        follow_redirects=False,
    )

    me = client.get("/api/auth/me").json()
    assert me["id"] != owner["id"], "an unverified email must not attach to an account"
    assert me["email"] is None


def test_an_account_with_another_github_id_is_never_claimed(
    client: TestClient, oauth, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy.orm import Session as OrmSession

    from app.db import get_engine
    from app.models import User

    with OrmSession(get_engine()) as db:
        other = User(
            github_id=888,
            login=f"someone-else-{oauth['github_id']}",
            email=f"taken-{oauth['github_id']}@example.com",
            password_hash="x",
        )
        db.add(other)
        db.commit()
        other_id = other.id

    state = _state_from(_authorize_url(client))
    _monkey_emails(oauth, [f"taken-{oauth['github_id']}@example.com"])
    response = client.get(
        "/api/auth/github/callback",
        params={"code": "abc", "state": state},
        headers=BROWSER,
        follow_redirects=False,
    )

    # Not a 500: the address is taken, so the new account is created without it.
    assert response.status_code in (302, 307), response.text
    me = client.get("/api/auth/me").json()
    assert me["id"] != other_id
    assert me["github_id"] == oauth["github_id"]
    assert me["email"] is None


def test_a_password_less_account_is_never_adopted(client: TestClient, oauth) -> None:
    """A dev-bypass leftover must not silently become a real person's account."""
    from sqlalchemy.orm import Session as OrmSession

    from app.db import get_engine
    from app.models import User

    with OrmSession(get_engine()) as db:
        dev = User(
            github_id=None,
            login=f"dev-legacy-{oauth['github_id']}",
            email=f"dev-{oauth['github_id']}@example.com",
        )
        db.add(dev)
        db.commit()
        dev_id = dev.id

    state = _state_from(_authorize_url(client))
    _monkey_emails(oauth, [f"dev-{oauth['github_id']}@example.com"])
    response = client.get(
        "/api/auth/github/callback",
        params={"code": "abc", "state": state},
        headers=BROWSER,
        follow_redirects=False,
    )

    # Again not a 500: refusing to adopt it must not break the sign-in.
    assert response.status_code in (302, 307), response.text
    assert client.get("/api/auth/me").json()["id"] != dev_id


def test_a_forbidden_emails_endpoint_still_completes_the_sign_in(client: TestClient, oauth) -> None:
    """403 is a normal answer from an org that forbids member emails."""
    state = _state_from(_authorize_url(client))
    oauth["emails"]["status"] = 403

    response = client.get(
        "/api/auth/github/callback",
        params={"code": "abc", "state": state},
        headers=BROWSER,
        follow_redirects=False,
    )
    assert response.status_code in (302, 307)
    assert client.get("/api/auth/me").json()["github_id"] == oauth["github_id"]


def test_the_authorize_url_asks_for_the_email_scope(client: TestClient, oauth) -> None:
    """Without user:email the callback cannot see an address to link on."""
    assert "user%3Aemail" in _authorize_url(client) or "user:email" in _authorize_url(client)
