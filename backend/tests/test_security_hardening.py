"""Phase-1 hardening: session revocation, rate limiting, and 4xx-not-500.

Each of these closes a defect the deep test found by reproduction, so the tests
assert the *behaviour that failed*, not the implementation: a replayed cookie after
logout is refused, a caller over the limit is answered 429, and malformed input
that reached the database used to be an unhandled 500.
"""

import base64

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session  # noqa: F401  (typed fixture blocks)

from app import rate_limit
from app.config import get_settings
from app.security import create_access_token, decode_access_token

SESSION_COOKIE = "ai_intel_token"


def _register(client: TestClient, email: str, password: str = "correct-horse-battery"):
    return client.post("/api/auth/register", json={"email": email, "password": password})


# --- Session revocation -------------------------------------------------------


def test_logout_revokes_a_copied_cookie(client: TestClient) -> None:
    """Clearing the cookie ends *this* browser; the token must die on the server.

    A JWT is valid until it expires, so a copy taken before logout — a shared
    machine, a proxy log — otherwise keeps working for the rest of its week. The
    test replays the captured cookie after logout, which the browser's own cookie
    jar would not do.
    """
    assert _register(client, "revoke@example.com").status_code == 201
    stolen = client.cookies.get(SESSION_COOKIE)
    assert stolen

    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200

    client.cookies.set(SESSION_COOKIE, stolen)
    assert client.get("/api/auth/me").status_code == 401


def test_a_token_from_a_stale_generation_is_refused(client: TestClient) -> None:
    """A token minted at version N is dead once the user's version moves past it."""
    assert _register(client, "generation@example.com").status_code == 201
    user_id = client.get("/api/auth/me").json()["id"]

    stale = create_access_token(user_id, token_version=99)
    client.cookies.set(SESSION_COOKIE, stale)
    assert client.get("/api/auth/me").status_code == 401


def test_a_token_without_a_version_still_signs_in(client: TestClient) -> None:
    """Tokens from before the column existed read as version 0, so a deploy does
    not sign everyone out."""
    assert _register(client, "legacy@example.com").status_code == 201
    user_id = client.get("/api/auth/me").json()["id"]

    # Mint exactly what the previous build produced: no `ver` claim.
    import jwt

    settings = get_settings()
    legacy = jwt.encode(
        {"sub": str(user_id), "exp": 4102444800}, settings.jwt_secret, algorithm="HS256"
    )
    client.cookies.set(SESSION_COOKIE, legacy)
    assert client.get("/api/auth/me").status_code == 200


# --- Rate limiting ------------------------------------------------------------


@pytest.fixture
def limited(monkeypatch: pytest.MonkeyPatch):
    """Turn the limiter on with an in-memory store, independent of app settings."""
    store = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(rate_limit, "_redis", lambda: store)
    monkeypatch.setattr(
        rate_limit, "get_settings", lambda: type("S", (), {"rate_limit_enabled": True})()
    )
    return store


class _FakeRequest:
    def __init__(self, host: str = "203.0.113.7") -> None:
        self.client = type("C", (), {"host": host})()


def test_the_limiter_allows_up_to_the_limit_then_refuses(limited) -> None:
    from fastapi import HTTPException

    for _ in range(3):
        rate_limit.enforce(_FakeRequest(), "login", limit=3, window_seconds=60)
    with pytest.raises(HTTPException) as excinfo:
        rate_limit.enforce(_FakeRequest(), "login", limit=3, window_seconds=60)
    assert excinfo.value.status_code == 429
    assert int(excinfo.value.headers["Retry-After"]) >= 1


def test_the_limiter_counts_callers_separately(limited) -> None:
    rate_limit.enforce(_FakeRequest("198.51.100.1"), "login", limit=1, window_seconds=60)
    # A different address must not be punished for the first one's spending.
    rate_limit.enforce(_FakeRequest("198.51.100.2"), "login", limit=1, window_seconds=60)


def test_the_limiter_fails_open_when_redis_is_down(monkeypatch) -> None:
    """A cache outage must not become "nobody can sign in"."""
    import redis

    def boom():
        raise redis.RedisError("down")

    monkeypatch.setattr(rate_limit, "_redis", boom)
    monkeypatch.setattr(
        rate_limit, "get_settings", lambda: type("S", (), {"rate_limit_enabled": True})()
    )
    # No exception: the request is allowed.
    rate_limit.enforce(_FakeRequest(), "login", limit=1, window_seconds=60)


def test_register_is_limited_end_to_end(client: TestClient, limited) -> None:
    """The wiring, not just the function: the 11th registration in the window is 429.

    The endpoint's own limit is 10/hour.
    """
    last = None
    for index in range(11):
        last = _register(client, f"flood-{index}@example.com")
    assert last is not None
    assert last.status_code == 429


# --- Malformed input that used to be an unhandled 500 -------------------------


def test_a_non_ascii_agent_token_is_401_not_500() -> None:
    """`compare_digest` rejects non-ASCII str operands with a TypeError.

    A test client cannot even send such a header (httpx encodes headers as ASCII),
    but a raw socket can — that is how the 500 was reproduced — so the check is
    exercised at the function that receives the already-parsed value.
    """
    from fastapi import HTTPException

    from app.db import get_session_factory
    from app.deps import _agent_user

    class _NoHeaders:
        @staticmethod
        def get(_name):
            return None

    class _Request:
        headers = _NoHeaders()

    session = get_session_factory()()
    try:
        with pytest.raises(HTTPException) as excinfo:
            _agent_user(_Request(), "tëst-nön-ascii-é", session)  # type: ignore[arg-type]
    finally:
        session.close()
    assert excinfo.value.status_code == 401


def test_a_deeply_nested_cookie_header_is_401_not_500(client: TestClient) -> None:
    """A JSON header nested past the recursion limit raises RecursionError out of
    PyJWT's parse, which is not a PyJWTError. It must fail closed."""
    raw = '{"alg":"HS256","typ":"JWT","x":' + "[" * 100000 + "]" * 100000 + "}"
    token = base64.urlsafe_b64encode(raw.encode()).rstrip(b"=").decode() + ".e30.x"

    assert decode_access_token(token) is None
    client.cookies.set(SESSION_COOKIE, token)
    assert client.get("/api/auth/me").status_code == 401


def test_an_unknown_severity_filter_is_422(client: TestClient, auth_client: TestClient) -> None:
    """`?severity=bogus` reached the column and raised a LookupError → 500."""
    repo = auth_client.post("/api/repos", json={"url": "https://github.com/o/r"}).json()
    analysis = auth_client.post(f"/api/repos/{repo['id']}/analyze")
    if analysis.status_code != 201:
        pytest.skip("analysis could not be started in this environment")
    analysis_id = analysis.json()["id"]
    response = auth_client.get(
        f"/api/analyses/{analysis_id}/findings", params={"severity": "bogus"}
    )
    assert response.status_code == 422


def test_a_duplicate_race_is_409_not_500(client: TestClient, monkeypatch) -> None:
    """The uniqueness check and the insert are not atomic, so a collision is a
    `409 Email already registered`, the same answer the pre-check gives."""
    from app.routers import auth as auth_router

    assert _register(client, "first@example.com").status_code == 201
    taken_login = client.get("/api/auth/me").json()["login"]

    # Force the race: the second registration computes a login that already exists,
    # which only fails at the unique index — i.e. inside commit().
    monkeypatch.setattr(auth_router, "_unique_login", lambda db, base: taken_login)
    response = _register(client, "second@example.com")
    assert response.status_code == 409
    assert "already registered" in response.json()["detail"]
