"""Email verification: the endpoints, and the link it gates.

The link is not cosmetic. It is what makes GitHub account linking safe: an address
that was never proven can be pre-registered by anyone, so the linking rule now
requires the *local* account to have verified it, not merely GitHub to assert it.
"""

import hashlib
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session  # noqa: F401  (typed fixture blocks)

from app.db import get_session_factory
from app.models import EmailVerificationToken, User
from app.routers import auth as auth_router

# A browser is the only realistic client for a link in an email, and sends this.
BROWSER = {"accept": "text/html,application/xhtml+xml"}


def _register(client: TestClient, email: str, password: str = "correct-horse-battery"):
    return client.post("/api/auth/register", json={"email": email, "password": password})


@pytest.fixture
def sent_links(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Capture verification links instead of sending them."""
    links: list[str] = []

    def capture(to: str, link: str, ttl_hours: int) -> None:
        links.append(link)

    monkeypatch.setattr(auth_router.mailer, "send_verification", capture)
    return links


def _token_from(link: str) -> str:
    return parse_qs(urlsplit(link).query)["token"][0]


def test_register_sends_a_verification_link(client: TestClient, sent_links: list[str]) -> None:
    assert _register(client, "newcomer@example.com").status_code == 201
    assert len(sent_links) == 1
    # The link arrives on the app's own origin, which proxies /api — so one URL works
    # in development and in production alike.
    assert urlsplit(sent_links[0]).path == "/api/auth/verify-email"
    assert client.get("/api/auth/me").json()["email_verified"] is False


def test_the_link_verifies_the_address(client: TestClient, sent_links: list[str]) -> None:
    _register(client, "verifyme@example.com")
    response = client.get(
        "/api/auth/verify-email",
        params={"token": _token_from(sent_links[0])},
        headers=BROWSER,
        follow_redirects=False,
    )
    assert response.status_code in (302, 307)
    assert "email_verified=1" in response.headers["location"]
    assert client.get("/api/auth/me").json()["email_verified"] is True


def test_a_link_works_once(client: TestClient, sent_links: list[str]) -> None:
    _register(client, "once@example.com")
    token = _token_from(sent_links[0])
    first = client.get(
        "/api/auth/verify-email", params={"token": token}, headers=BROWSER, follow_redirects=False
    )
    assert "email_verified=1" in first.headers["location"]
    second = client.get(
        "/api/auth/verify-email", params={"token": token}, headers=BROWSER, follow_redirects=False
    )
    assert "auth_error=verification_failed" in second.headers["location"]


def test_an_expired_link_is_refused(client: TestClient) -> None:
    assert _register(client, "expired@example.com").status_code == 201
    session = get_session_factory()()
    try:
        user = session.query(User).filter(User.email == "expired@example.com").one()
        session.add(
            EmailVerificationToken(
                user_id=user.id,
                token_hash=hashlib.sha256(b"stale-token").hexdigest(),
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.get(
        "/api/auth/verify-email",
        params={"token": "stale-token"},
        headers=BROWSER,
        follow_redirects=False,
    )
    assert "auth_error=verification_failed" in response.headers["location"]


def test_an_unknown_token_is_refused(client: TestClient) -> None:
    response = client.get(
        "/api/auth/verify-email",
        params={"token": "never-issued"},
        headers=BROWSER,
        follow_redirects=False,
    )
    assert "auth_error=verification_failed" in response.headers["location"]


def test_resend_requires_authentication(client: TestClient) -> None:
    assert client.post("/api/auth/resend-verification").status_code == 401


def test_resend_sends_a_fresh_link(client: TestClient, sent_links: list[str]) -> None:
    _register(client, "again@example.com")
    assert len(sent_links) == 1
    assert client.post("/api/auth/resend-verification").status_code == 200
    assert len(sent_links) == 2
    assert sent_links[0] != sent_links[1]


def test_resend_is_a_no_op_once_verified(client: TestClient, sent_links: list[str]) -> None:
    _register(client, "done@example.com")
    client.get(
        "/api/auth/verify-email",
        params={"token": _token_from(sent_links[0])},
        headers=BROWSER,
    )
    response = client.post("/api/auth/resend-verification")
    assert response.status_code == 200
    assert response.json()["already_verified"] is True
    assert len(sent_links) == 1


def test_the_link_follows_the_origin_the_app_was_reached_on(
    client: TestClient, sent_links: list[str]
) -> None:
    """The link must point at the host the app is actually served from.

    A configured constant drifts — a stale one here pointed the link at a port
    nothing was listening on, and the failure is invisible until someone clicks it.
    The request that registers knows the real origin, so the link uses it, exactly
    as the OAuth redirect does.
    """
    client.post(
        "/api/auth/register",
        json={"email": "origin@example.com", "password": "correct-horse-battery"},
        headers={"origin": "http://localhost:5175"},
    )
    assert len(sent_links) == 1
    assert urlsplit(sent_links[0]).netloc == "localhost:5175"
