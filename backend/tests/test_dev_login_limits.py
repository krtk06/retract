"""Login-path limits, and the dev account's one-repository-per-IP rule."""

import uuid
from collections.abc import Generator

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app import rate_limit
from app.config import get_settings
from app.main import create_app
from app.tasks.analysis import run_analysis


@pytest.fixture
def limiter(monkeypatch: pytest.MonkeyPatch) -> Generator[fakeredis.FakeRedis, None, None]:
    fake = fakeredis.FakeRedis(decode_responses=True)
    settings = get_settings().model_copy(update={"rate_limit_enabled": True})
    monkeypatch.setattr(rate_limit, "_redis", lambda: fake)
    monkeypatch.setattr(rate_limit, "get_settings", lambda: settings)
    # The analysis task would clone the fixture URLs; the limits are what this
    # module tests, so the enqueue is a no-op.
    monkeypatch.setattr(run_analysis, "delay", lambda *_args, **_kwargs: None)
    yield fake


def _client(ip: str) -> TestClient:
    return TestClient(create_app(), client=(ip, 50_000))


def test_dev_login_is_limited_to_five_per_hour_per_ip(limiter) -> None:
    with _client("198.51.100.50") as client:
        for _ in range(5):
            response = client.get("/api/auth/dev/login", params={"login": "limit-dev"})
            assert response.status_code == 200, response.text
        refused = client.get("/api/auth/dev/login", params={"login": "limit-dev"})
        assert refused.status_code == 429
        assert int(refused.headers["Retry-After"]) >= 1

    # A different address is unaffected.
    with _client("198.51.100.51") as other:
        assert other.get("/api/auth/dev/login", params={"login": "limit-dev"}).status_code == 200


def test_eve_token_minting_is_limited_per_user(limiter) -> None:
    with _client("198.51.100.52") as client:
        assert client.get("/api/auth/dev/login", params={"login": "eve-limit"}).status_code == 200
        for _ in range(60):
            assert client.post("/api/auth/eve-token").status_code == 200
        refused = client.post("/api/auth/eve-token")
        assert refused.status_code == 429


def _create_repo(client: TestClient, name: str) -> int:
    suffix = uuid.uuid4().hex[:8]
    response = client.post(
        "/api/repos", json={"url": f"https://github.com/fixture/{name}-{suffix}"}
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def test_a_dev_account_gets_one_repository_per_ip_but_may_rerun_it(limiter) -> None:
    with _client("198.51.100.60") as client:
        assert client.get("/api/auth/dev/login", params={"login": "one-repo"}).status_code == 200
        first = _create_repo(client, "first")
        second = _create_repo(client, "second")

        assert client.post(f"/api/repos/{first}/analyze").status_code == 201
        # The same repository is allowed through the IP claim; the run itself is
        # already active, which is a different (and expected) refusal.
        rerun = client.post(f"/api/repos/{first}/analyze")
        assert rerun.status_code == 409, rerun.text

        other = client.post(f"/api/repos/{second}/analyze")
        assert other.status_code == 429
        assert "one repository per IP" in other.json()["detail"]

    # The same dev account from another address has a fresh repository budget.
    with _client("198.51.100.61") as elsewhere:
        assert elsewhere.get("/api/auth/dev/login", params={"login": "one-repo"}).status_code == 200
        assert elsewhere.post(f"/api/repos/{second}/analyze").status_code == 201


def test_a_real_account_may_analyze_two_repositories(limiter) -> None:
    with _client("198.51.100.62") as client:
        suffix = uuid.uuid4().hex[:8]
        registered = client.post(
            "/api/auth/register",
            json={"email": f"real-{suffix}@example.com", "password": "correct-horse-battery"},
        )
        assert registered.status_code == 201, registered.text
        first = _create_repo(client, "real-first")
        second = _create_repo(client, "real-second")

        assert client.post(f"/api/repos/{first}/analyze").status_code == 201
        assert client.post(f"/api/repos/{second}/analyze").status_code == 201
