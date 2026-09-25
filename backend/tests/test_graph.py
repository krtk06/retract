"""Graph tests on an isolated fixture repo (symbol structure only, no RAG)."""

import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.analysis_engine import graph
from app.db import get_session_factory
from app.models import Analysis, Repository, User
from app.services import indexer
from app.services.ingestion import build_inventory

FIXTURE_FILES = {
    "pkg/__init__.py": "",
    "pkg/auth.py": (
        '"""Authentication helpers for validating user credentials."""\n'
        "\n"
        "def authenticate(user, password):\n"
        '    """Validate a user password against stored credentials."""\n'
        "    return check_password(user, password)\n"
        "\n"
        "def check_password(user, password):\n"
        "    return user.password == password\n"
    ),
    "pkg/client.py": (
        "from pkg.auth import authenticate\n"
        "\n"
        "def login(username, password):\n"
        "    return authenticate(username, password)\n"
    ),
    "pkg/util.py": "def helper():\n    return 1\n",
}


@pytest.fixture(scope="module")
def fixture_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("graphrepo")
    for rel, content in FIXTURE_FILES.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return root


@pytest.fixture(scope="module")
def analyzed(fixture_repo: Path) -> Generator[int, None, None]:
    """Create repo/analysis rows and index symbols. No chunking, no embeddings."""
    session: Session = get_session_factory()()
    try:
        user = session.query(User).first()
        if user is None:
            user = User(github_id=None, login="graphfixture")
            session.add(user)
            session.commit()
        repo = Repository(
            owner="fixture", name="graphrepo", url=f"local://fixture/graph-{uuid.uuid4().hex[:8]}",
            default_branch="main", added_by=user.id,
        )
        session.add(repo)
        session.commit()
        analysis = Analysis(repository_id=repo.id)
        session.add(analysis)
        session.commit()

        files, _total, _trunc = build_inventory(fixture_repo)
        indexer.persist_index(session, analysis.id, fixture_repo, [f.path for f in files])
        yield analysis.id
    finally:
        session.close()


def test_index_built_graph(analyzed: int) -> None:
    session = get_session_factory()()
    try:
        summary = graph.summary(session, analyzed)
        assert summary["symbols"].get("module", 0) >= 4
        assert summary["symbols"].get("function", 0) >= 3
        assert summary["edges"].get("imports", 0) >= 1
    finally:
        session.close()


def test_imports_and_dependents(analyzed: int) -> None:
    session = get_session_factory()()
    try:
        imported = {item["module"] for item in graph.imports(session, analyzed, "pkg.client")}
        assert "pkg.auth" in imported

        dependents = {item["name"] for item in graph.dependents(session, analyzed, "pkg.auth")}
        assert "pkg.client" in dependents
    finally:
        session.close()


def test_callers_finds_enclosing_function(analyzed: int) -> None:
    session = get_session_factory()()
    try:
        callers = graph.callers(session, analyzed, "authenticate")
        names = {c["symbol"]["name"] for c in callers}
        assert "login" in names
    finally:
        session.close()


def test_callees_of_login(analyzed: int) -> None:
    session = get_session_factory()()
    try:
        callees = {c["name"] for c in graph.callees(session, analyzed, "login")}
        assert "authenticate" in callees
    finally:
        session.close()


def test_path_between_modules(analyzed: int) -> None:
    session = get_session_factory()()
    try:
        chain = graph.path(session, analyzed, "pkg.client", "pkg.auth")
        assert [item.name for item in chain] == ["pkg.client", "pkg.auth"]
    finally:
        session.close()


def test_neighborhood(analyzed: int) -> None:
    session = get_session_factory()()
    try:
        result = graph.neighborhood(session, analyzed, "pkg.auth", depth=2)
        assert result.root is not None
        assert result.root.name == "pkg.auth"
        assert len(result.nodes) >= 2
    finally:
        session.close()


def test_graph_api_endpoints(auth_client: TestClient, analyzed: int) -> None:
    summary = auth_client.get(f"/api/analyses/{analyzed}/graph/summary")
    assert summary.status_code == 200
    assert summary.json()["symbols"]

    symbols = auth_client.get(f"/api/analyses/{analyzed}/graph/symbols", params={"q": "auth"})
    assert symbols.status_code == 200
    assert any(s["name"] == "authenticate" for s in symbols.json())

    dependents = auth_client.get(
        f"/api/analyses/{analyzed}/graph/dependents", params={"module": "pkg.auth"}
    )
    assert dependents.status_code == 200

    neighborhood = auth_client.get(
        f"/api/analyses/{analyzed}/graph/neighborhood", params={"symbol": "pkg.auth"}
    )
    assert neighborhood.status_code == 200
    assert neighborhood.json()["root"]["name"] == "pkg.auth"

    missing = auth_client.get("/api/analyses/99999/graph/summary")
    assert missing.status_code == 404
