"""Phase 6 API tests: analysis history, trust summary, and comparison."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.db import get_session_factory
from app.models import Analysis, FindingStatus, Repository, Severity, User
from app.services.tools.findings import FindingDraft, persist_findings


@pytest.fixture
def repo_with_analyses() -> tuple[int, int, int]:
    session = get_session_factory()()
    try:
        user = session.query(User).first()
        if user is None:
            user = User(github_id=None, login="phase6")
            session.add(user)
            session.commit()
        suffix = uuid.uuid4().hex[:8]
        repo = Repository(
            owner="fixture",
            name=f"p6-{suffix}",
            url=f"local://fixture/p6-{suffix}",
            default_branch="main",
            added_by=user.id,
        )
        session.add(repo)
        session.commit()

        first = Analysis(repository_id=repo.id, loc=1000, published=True)
        second = Analysis(repository_id=repo.id, loc=1200, published=True)
        session.add_all([first, second])
        session.commit()

        first.score_json = {
            "version": 2,
            "overall": 60,
            "loc": 1000,
            "kloc": 1.0,
            "pillars": {
                "security": {
                    "score": 50,
                    "findings": 4,
                    "verified": 2,
                    "hypotheses": 1,
                    "dismissed": 1,
                    "weighted_penalty": 25.0,
                },
                "testing": {
                    "score": 80,
                    "findings": 1,
                    "verified": 1,
                    "hypotheses": 0,
                    "dismissed": 0,
                    "weighted_penalty": 10.0,
                },
            },
        }
        second.score_json = {
            "version": 2,
            "overall": 75,
            "loc": 1200,
            "kloc": 1.2,
            "pillars": {
                "security": {
                    "score": 70,
                    "findings": 2,
                    "verified": 2,
                    "hypotheses": 0,
                    "dismissed": 0,
                    "weighted_penalty": 20.0,
                },
                "testing": {
                    "score": 85,
                    "findings": 1,
                    "verified": 1,
                    "hypotheses": 0,
                    "dismissed": 0,
                    "weighted_penalty": 8.0,
                },
            },
        }
        session.commit()

        persist_findings(
            session,
            second.id,
            [
                FindingDraft(
                    agent="security",
                    category="vulnerability",
                    severity=Severity.HIGH,
                    title="v1",
                    verifier="tool:semgrep",
                    status=FindingStatus.VERIFIED,
                    confidence=0.9,
                ),
                FindingDraft(
                    agent="security",
                    category="vulnerability",
                    severity=Severity.MEDIUM,
                    title="h1",
                    verifier="llm:mock",
                    status=FindingStatus.HYPOTHESIS,
                    confidence=0.4,
                ),
                FindingDraft(
                    agent="code",
                    category="code-smell",
                    severity=Severity.LOW,
                    title="c1",
                    verifier="llm:mock",
                    status=FindingStatus.DISMISSED,
                    confidence=0.2,
                ),
            ],
        )
        return repo.id, first.id, second.id
    finally:
        session.close()


def test_history_lists_analyses_newest_first(auth_client: TestClient, repo_with_analyses) -> None:
    _repo, first_id, second_id = repo_with_analyses
    response = auth_client.get(f"/api/analyses/{first_id}/history")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["id"] == second_id  # newest created last by id/created_at
    assert body[0]["finding_count"] == 3
    assert body[0]["overall"] == 75
    assert body[1]["overall"] == 60


def test_score_endpoint_exposes_delta(auth_client: TestClient, repo_with_analyses) -> None:
    _repo, first_id, second_id = repo_with_analyses
    response = auth_client.get(f"/api/analyses/{second_id}/score")
    assert response.status_code == 200
    body = response.json()
    assert body["delta"] == 15
    assert body["previous_overall"] == 60


def test_score_delta_is_suppressed_across_curve_versions(
    auth_client: TestClient, repo_with_analyses
) -> None:
    """A v2 and a v3 score come from different curves; their difference is not a change."""
    _repo, first_id, second_id = repo_with_analyses
    session = get_session_factory()()
    try:
        earlier = session.get(Analysis, first_id)
        assert earlier is not None and earlier.score_json is not None
        earlier.score_json = {**earlier.score_json, "version": 1}
        session.commit()
    finally:
        session.close()

    body = auth_client.get(f"/api/analyses/{second_id}/score").json()
    assert body["delta"] is None
    assert body["previous_overall"] is None


def test_trust_summary(auth_client: TestClient, repo_with_analyses) -> None:
    _repo, _first_id, second_id = repo_with_analyses
    response = auth_client.get(f"/api/analyses/{second_id}/trust-summary")
    assert response.status_code == 200
    body = response.json()
    assert body["totals"]["findings"] == 3
    assert body["totals"]["verified"] == 1
    assert body["totals"]["hypotheses"] == 1
    assert body["totals"]["dismissed"] == 1
    # 1 verified / (1 verified + 1 hypothesis)
    assert body["verification_coverage"] == 0.5
    agents = {a["agent"]: a for a in body["agents"]}
    assert agents["security"]["findings"] == 2
    assert "acceptance_rates" in body


def test_compare_two_analyses(auth_client: TestClient, repo_with_analyses) -> None:
    _repo, first_id, second_id = repo_with_analyses
    response = auth_client.get(
        "/api/analyses/compare", params={"left": first_id, "right": second_id}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["overall_delta"] == 15
    pillars = {p["pillar"]: p for p in body["pillars"]}
    assert pillars["security"]["delta"] == 20
    assert pillars["security"]["left_findings"] == 4
    assert pillars["security"]["right_findings"] == 2


def test_compare_rejects_different_repositories(
    auth_client: TestClient, repo_with_analyses
) -> None:
    _repo, first_id, _second_id = repo_with_analyses
    session = get_session_factory()()
    try:
        user = session.query(User).first()
        other_repo = Repository(
            owner="fixture",
            name="other",
            url="local://fixture/other-dcba",
            default_branch="main",
            added_by=user.id,
        )
        session.add(other_repo)
        session.commit()
        other_analysis = Analysis(repository_id=other_repo.id)
        session.add(other_analysis)
        session.commit()
        other_id = other_analysis.id
    finally:
        session.close()

    response = auth_client.get(
        "/api/analyses/compare", params={"left": first_id, "right": other_id}
    )
    assert response.status_code == 422


def test_unknown_analysis_404(auth_client: TestClient) -> None:
    assert auth_client.get("/api/analyses/99999/history").status_code == 404
    assert auth_client.get("/api/analyses/99999/trust-summary").status_code == 404
