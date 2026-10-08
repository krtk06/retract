"""Email/password accounts, user scoping, and the dashboard endpoint."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session  # noqa: F401  (typed fixture blocks)

from app.db import get_session_factory
from app.models import Analysis, Repository, User, UserRepository


def _register(client: TestClient, email: str, password: str = "correct-horse-battery"):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def _make_repo_and_analysis(session_factory, login: str) -> tuple[int, int]:
    """Backdoor rows for a user that the API can create via dev login."""
    session = session_factory()
    try:
        user = session.query(User).filter(User.login == login).one()
        suffix = uuid.uuid4().hex[:8]
        repo = Repository(
            owner="fixture",
            name=f"iso-{suffix}",
            url=f"https://github.com/fixture/iso-{suffix}",
            default_branch="main",
            added_by=user.id,
        )
        session.add(repo)
        session.commit()
        session.add(UserRepository(repo_id=repo.id, user_id=user.id))
        analysis = Analysis(repository_id=repo.id, loc=100)
        session.add(analysis)
        session.commit()
        return repo.id, analysis.id
    finally:
        session.close()


def test_register_signs_in_and_me_reports_email(client: TestClient) -> None:
    response = _register(client, "  Ada@Example.COM ")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == "ada@example.com"
    assert body["github_id"] is None

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "ada@example.com"


def test_register_rejects_duplicate_email(client: TestClient) -> None:
    assert _register(client, "miss@example.com").status_code == 201
    assert _register(client, "miss@example.com").status_code == 409


def test_register_rejects_weak_password(client: TestClient) -> None:
    assert _register(client, "short@example.com", "short").status_code == 422


def test_login_success_and_generic_failure(client: TestClient) -> None:
    assert _register(client, "lucia@example.com").status_code == 201
    client.post("/api/auth/logout")

    ok = client.post(
        "/api/auth/login", json={"email": "lucia@example.com", "password": "correct-horse-battery"}
    )
    assert ok.status_code == 200
    assert ok.json()["email"] == "lucia@example.com"

    client.post("/api/auth/logout")
    # Wrong password and unknown email share one message: no user enumeration.
    wrong_password = client.post(
        "/api/auth/login", json={"email": "lucia@example.com", "password": "nope-nope-nope"}
    )
    unknown = client.post(
        "/api/auth/login", json={"email": "ghost@example.com", "password": "nope-nope-nope"}
    )
    assert wrong_password.status_code == unknown.status_code == 401
    assert wrong_password.json()["detail"] == unknown.json()["detail"]


def test_login_rejects_github_only_account(client: TestClient) -> None:
    # A dev-login user has no password hash; their email column is empty too.
    auth = client.get("/api/auth/dev/login", params={"login": "oauth"})
    assert auth.status_code == 200
    client.post("/api/auth/logout")
    response = client.post(
        "/api/auth/login", json={"email": "oauth@example.com", "password": "whatever-long"}
    )
    assert response.status_code == 401


def test_cross_user_isolation(client: TestClient) -> None:
    owner = _register(client, "owner@example.com").json()
    repo_id, analysis_id = _make_repo_and_analysis(get_session_factory(), owner["login"])

    client.post("/api/auth/logout")
    _register(client, "ciso@example.com")

    # Every read either 404s (no existence leak) or comes back empty.
    assert client.get(f"/api/analyses/{analysis_id}").status_code == 404
    assert client.get(f"/api/analyses/{analysis_id}/findings").status_code == 404
    assert client.get(f"/api/analyses/{analysis_id}/score").status_code == 404
    assert client.get(f"/api/analyses/{analysis_id}/history").status_code == 404
    assert client.post(f"/api/repos/{repo_id}/analyze").status_code == 404
    assert client.get("/api/repos").json() == []
    assert client.get("/api/analyses").json() == []


def test_shared_repo_url_grants_second_owner_access(client: TestClient) -> None:
    owner = _register(client, "sharer@example.com").json()
    repo_id, analysis_id = _make_repo_and_analysis(get_session_factory(), owner["login"])
    repo = next(rep for rep in client.get("/api/repos").json() if rep["id"] == repo_id)

    client.post("/api/auth/logout")
    _register(client, "peer@example.com")
    # The peer registers the same URL and becomes a co-owner of the shared row.
    again = client.post("/api/repos", json={"url": repo["url"]})
    assert again.status_code == 201
    assert again.json()["id"] == repo_id
    assert client.get(f"/api/analyses/{analysis_id}").status_code == 200
    assert any(rep["id"] == repo_id for rep in client.get("/api/repos").json())


def test_dashboard_lists_analyses_newest_first(client: TestClient) -> None:
    user = _register(client, "dash@example.com").json()
    repo_id, first_id = _make_repo_and_analysis(get_session_factory(), user["login"])

    second = Analysis(repository_id=repo_id, loc=200)
    session = get_session_factory()()
    try:
        session.add(second)
        session.commit()
        second_id = second.id
    finally:
        session.close()

    response = client.get("/api/analyses")
    assert response.status_code == 200
    body = response.json()
    assert [row["id"] for row in body] == [second_id, first_id]
    assert body[0]["repo_name"].startswith("iso-")
    assert body[0]["repo_owner"] == "fixture"
    assert body[0]["status"] == "pending"
    assert body[0]["overall"] is None


def test_requesting_other_users_repo_is_404(client: TestClient) -> None:
    me_response = _register(client, "isolated@example.com")
    assert me_response.status_code == 201
    # A repo id the user does not own looks exactly like one that is absent.
    assert client.post("/api/repos/999999/analyze").status_code == 404
