"""API tests: health, auth, repos, analyses, findings, SSE replay."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.events import get_bus
from app.services.ingestion import FileEntry, IngestionResult


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["db"] == "ok"


def test_me_unauthenticated(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 401


def test_dev_login_and_me(auth_client: TestClient) -> None:
    response = auth_client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["login"] == "tester"


def test_logout(auth_client: TestClient) -> None:
    assert auth_client.post("/api/auth/logout").status_code == 200
    assert auth_client.get("/api/auth/me").status_code == 401


def test_create_repo_validates_url(auth_client: TestClient) -> None:
    response = auth_client.post("/api/repos", json={"url": "https://gitlab.com/a/b"})
    assert response.status_code == 422


def test_create_and_list_repo(auth_client: TestClient) -> None:
    response = auth_client.post("/api/repos", json={"url": "https://github.com/psf/requests"})
    assert response.status_code == 201
    repo = response.json()
    assert repo["owner"] == "psf"
    assert repo["name"] == "requests"

    # Idempotent: same URL returns the same repo row.
    again = auth_client.post("/api/repos", json={"url": "https://github.com/psf/requests.git"})
    assert again.status_code == 201
    assert again.json()["id"] == repo["id"]

    listing = auth_client.get("/api/repos")
    assert listing.status_code == 200
    assert any(r["id"] == repo["id"] for r in listing.json())


def _fake_ingest(url: str, dest: Path) -> IngestionResult:
    dest.mkdir(parents=True, exist_ok=True)
    return IngestionResult(
        dest=dest,
        commit_sha="abc123def456",
        branch="main",
        files=[FileEntry("src/app.py", 42, ".py"), FileEntry("web/index.ts", 24, ".ts")],
        languages={"Python": 1, "TypeScript": 1},
        total_files=2,
        truncated=False,
    )


def test_analysis_flow_end_to_end(auth_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.tasks.analysis.ingestion.ingest", _fake_ingest)

    repo = auth_client.post("/api/repos", json={"url": "https://github.com/psf/requests"}).json()
    response = auth_client.post(f"/api/repos/{repo['id']}/analyze")
    assert response.status_code == 201
    analysis = response.json()

    # Task ran eagerly; the analysis should be done by now.
    detail = auth_client.get(f"/api/analyses/{analysis['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "done"
    assert body["commit_sha"] == "abc123def456"
    assert body["finding_count"] == 1

    findings = auth_client.get(f"/api/analyses/{analysis['id']}/findings")
    assert findings.status_code == 200
    items = findings.json()
    assert len(items) == 1
    finding = items[0]
    assert finding["agent"] == "ingestion"
    assert finding["status"] == "verified"
    assert finding["confidence"] == 1.0
    assert finding["evidence_json"]["languages"] == {"Python": 1, "TypeScript": 1}

    # Conflict while an analysis is "active": simulate a pending one.
    monkeypatch.setattr("app.routers.repos.run_analysis.delay", lambda _id: None)
    second = auth_client.post(f"/api/repos/{repo['id']}/analyze")
    assert second.status_code == 201
    third = auth_client.post(f"/api/repos/{repo['id']}/analyze")
    assert third.status_code == 409


def test_analysis_events_replay(auth_client: TestClient) -> None:
    repo = auth_client.post("/api/repos", json={"url": "https://github.com/psf/requests"}).json()
    # Create an analysis row without running the task.
    from app.db import get_session_factory
    from app.models import Analysis

    session = get_session_factory()()
    analysis = Analysis(repository_id=repo["id"])
    session.add(analysis)
    session.commit()
    analysis_id = analysis.id
    session.close()

    bus = get_bus()
    bus.publish(analysis_id, "status", {"status": "running"})
    bus.publish(analysis_id, "done", {"status": "done"})

    response = auth_client.get(f"/api/analyses/{analysis_id}/events")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [e["type"] for e in events] == ["status", "done"]


def test_analysis_not_found(auth_client: TestClient) -> None:
    assert auth_client.get("/api/analyses/9999").status_code == 404
    assert auth_client.get("/api/analyses/9999/findings").status_code == 404
