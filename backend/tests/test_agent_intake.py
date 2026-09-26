"""Agent intake contract: eve records D2 verdict findings, and the eve token exchange."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import get_session_factory
from app.models import Analysis, Finding, Repository, User
from app.security import decode_eve_token

settings = get_settings()


@pytest.fixture
def analysis_id() -> int:
    session = get_session_factory()()
    try:
        user = session.query(User).first()
        if user is None:
            user = User(github_id=None, login="agentintake")
            session.add(user)
            session.commit()
        suffix = uuid.uuid4().hex[:8]
        repo = Repository(
            owner="fixture",
            name=f"intake-{suffix}",
            url=f"local://fixture/intake-{suffix}",
            default_branch="main",
            added_by=user.id,
        )
        session.add(repo)
        session.commit()
        analysis = Analysis(repository_id=repo.id, loc=500)
        session.add(analysis)
        session.commit()
        return analysis.id
    finally:
        session.close()


def _valid_finding() -> dict:
    return {
        "claim": "Hardcoded secret committed in the cache module.",
        "evidence": "app/cache_key.py:11 assigns a literal SHA1 salt.",
        "file_path": "app/cache_key.py",
        "line_start": 11,
        "line_end": 11,
        "severity": "high",
        "confidence": 0.7,
        "category": "secret",
    }


def test_record_findings_persists_hypothesis(auth_client: TestClient, analysis_id: int) -> None:
    response = auth_client.post(
        f"/api/analyses/{analysis_id}/findings",
        json={"agent": "eve:security", "findings": [_valid_finding()], "summary": "one issue"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["inserted"] == 1
    assert body["dropped"] == 0
    assert body["analysis_id"] == analysis_id

    session = get_session_factory()()
    try:
        finding = session.query(Finding).filter(Finding.analysis_id == analysis_id).one()
        assert finding.agent == "eve:security"
        assert finding.title == "Hardcoded secret committed in the cache module."
        assert finding.file_path == "app/cache_key.py"
        assert finding.verifier == "llm:eve"
        assert finding.evidence_json["claim"]
        assert finding.evidence_json["source"] == "eve"
    finally:
        session.close()


def test_record_findings_drops_uncited_claims(auth_client: TestClient, analysis_id: int) -> None:
    uncited = _valid_finding()
    uncited["file_path"] = None
    uncited["line_start"] = None
    response = auth_client.post(
        f"/api/analyses/{analysis_id}/findings",
        json={"agent": "eve:code", "findings": [uncited]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["inserted"] == 0
    assert response.json()["dropped"] == 1


def test_record_findings_dedupes(auth_client: TestClient, analysis_id: int) -> None:
    payload = {"agent": "eve:code", "findings": [_valid_finding()]}
    first = auth_client.post(f"/api/analyses/{analysis_id}/findings", json=payload)
    second = auth_client.post(f"/api/analyses/{analysis_id}/findings", json=payload)
    assert first.json()["inserted"] == 1
    assert second.json()["inserted"] == 0
    assert second.json()["dropped"] == 1


def test_record_findings_rescores_and_gates_publication(
    auth_client: TestClient, analysis_id: int
) -> None:
    response = auth_client.post(
        f"/api/analyses/{analysis_id}/findings",
        json={"agent": "eve:security", "findings": [_valid_finding()]},
    )
    body = response.json()
    assert "overall" in body
    session = get_session_factory()()
    try:
        analysis = session.get(Analysis, analysis_id)
        assert analysis is not None
        assert analysis.score_json is not None
        assert analysis.score_json["version"] == 4
    finally:
        session.close()


def test_record_findings_rejects_bad_severity(auth_client: TestClient, analysis_id: int) -> None:
    bad = _valid_finding()
    bad["severity"] = "catastrophic"
    response = auth_client.post(
        f"/api/analyses/{analysis_id}/findings",
        json={"agent": "eve:code", "findings": [bad]},
    )
    assert response.status_code == 422


def test_record_findings_requires_auth(client: TestClient, analysis_id: int) -> None:
    response = client.post(
        f"/api/analyses/{analysis_id}/findings",
        json={"agent": "eve:code", "findings": [_valid_finding()]},
    )
    assert response.status_code == 401


def test_eve_token_is_scoped_and_ephemeral(auth_client: TestClient) -> None:
    response = auth_client.post("/api/auth/eve-token")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["expires_in"] <= 600
    claims = decode_eve_token(body["token"])
    assert claims is not None
    assert claims["iss"] == "ai-intel"
    assert claims["aud"] == "eve-agent"
    assert claims["sub"].isdigit()


def test_eve_token_requires_auth(client: TestClient) -> None:
    assert client.post("/api/auth/eve-token").status_code == 401


def test_agent_service_token_authenticates_tools(auth_client: TestClient) -> None:
    response = auth_client.get(
        "/api/repos",
        headers={"X-Agent-Token": settings.agent_token, "X-Agent-User": "tester"},
    )
    assert response.status_code == 200


def test_agent_service_token_fails_closed_on_bad_secret(auth_client: TestClient) -> None:
    response = auth_client.get("/api/repos", headers={"X-Agent-Token": "wrong"})
    assert response.status_code == 401


def test_agent_service_token_requires_configuration(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "agent_token", "")
    response = auth_client.get("/api/repos", headers={"X-Agent-Token": "anything"})
    assert response.status_code == 401


def test_agent_service_token_resolves_unknown_user_as_service(
    auth_client: TestClient,
) -> None:
    response = auth_client.get(
        "/api/repos",
        headers={"X-Agent-Token": settings.agent_token, "X-Agent-User": "ghost"},
    )
    assert response.status_code == 200


def test_agent_service_token_accepts_numeric_principal(auth_client: TestClient) -> None:
    user_id = auth_client.get("/api/auth/me").json()["id"]
    response = auth_client.get(
        "/api/repos",
        headers={"X-Agent-Token": settings.agent_token, "X-Agent-User": str(user_id)},
    )
    assert response.status_code == 200
