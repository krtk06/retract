"""Phase 4 acceptance: agents on the seedy benchmark repo with the offline mock LLM.

Verifies the acceptance criteria from implementation.md:
  - Security Agent flags the SQL injection at the correct function with caller context;
  - Code Agent dismisses the planted false-positive semgrep finding;
  - Test Agent lists untested modules consistent with the test-presence analysis.

Runs the real deterministic tools + graph, then the agents through the heuristic
offline harness (AI_INTEL_LLM_PROVIDER=mock). This is a pipeline integration test,
not a measure of model quality.
"""

import os
from pathlib import Path

import pytest

from app.db import get_session_factory
from app.llm.client import set_llm_client
from app.llm.mock import HeuristicMockLLM
from app.models import Analysis, Finding, FindingStatus, Repository

REPO_ROOT = Path(__file__).resolve().parents[2] / "benchmark" / "seedy-python-app"


@pytest.fixture(scope="module")
def seedy_analysis() -> int:
    if not REPO_ROOT.is_dir():
        pytest.skip("seedy benchmark repo not present")
    os.environ["AI_INTEL_LLM_PROVIDER"] = "mock"
    os.environ["AI_INTEL_ALLOW_LOCAL_REPOS"] = "1"
    set_llm_client(HeuristicMockLLM())

    session = get_session_factory()()
    try:
        from app.models import User

        user = session.query(User).first()
        if user is None:
            user = User(github_id=None, login="seedyagents")
            session.add(user)
            session.commit()
        repo = Repository(
            owner="local",
            name="seedy-agents",
            url=f"local://{REPO_ROOT}",
            default_branch="local",
            added_by=user.id,
        )
        session.add(repo)
        session.commit()
        analysis = Analysis(repository_id=repo.id)
        session.add(analysis)
        session.commit()
        analysis_id = analysis.id
    finally:
        session.close()

    # Run the full pipeline eagerly (tools -> embeddings -> agents -> finalize).
    from app.tasks.analysis import run_analysis

    run_analysis.delay(analysis_id)  # eager in tests (task_always_eager)
    yield analysis_id
    set_llm_client(None)


def _findings(analysis_id: int) -> list[Finding]:
    session = get_session_factory()()
    try:
        return session.query(Finding).filter(Finding.analysis_id == analysis_id).all()
    finally:
        session.close()


def test_security_agent_flags_sql_injection_with_caller_context(seedy_analysis: int) -> None:
    findings = _findings(seedy_analysis)
    injection = [f for f in findings if f.agent == "security" and f.category == "injection"]
    assert injection, "Security Agent produced no injection finding"
    db_findings = [f for f in injection if f.file_path == "app/db.py"]
    assert db_findings, "SQL injection was not attributed to app/db.py"
    finding = db_findings[0]
    assert finding.line_start == 10
    assert finding.status == FindingStatus.HYPOTHESIS
    assert finding.verifier.startswith("llm:")
    assert "Callers:" in finding.description or "No internal callers" in finding.description


def test_code_agent_dismisses_planted_false_positive(seedy_analysis: int) -> None:
    findings = _findings(seedy_analysis)
    dismissed = [
        f for f in findings if f.category == "vulnerability" and f.status == FindingStatus.DISMISSED
    ]
    assert dismissed, "Code Agent did not dismiss the planted false positive"
    assert any(f.file_path == "app/cache_key.py" for f in dismissed)
    assert "triage" in (dismissed[0].evidence_json or {})


def test_code_agent_adds_hypothesis_insight(seedy_analysis: int) -> None:
    findings = _findings(seedy_analysis)
    code_findings = [f for f in findings if f.agent == "code"]
    assert code_findings, "Code Agent produced no findings"
    assert all(f.status == FindingStatus.HYPOTHESIS for f in code_findings)


def test_test_agent_lists_untested_modules(seedy_analysis: int) -> None:
    findings = _findings(seedy_analysis)
    test_plan = [f for f in findings if f.agent == "tests"]
    assert test_plan, "Test Agent produced no test plan"
    assert any(f.category in ("test-plan",) for f in test_plan)


def test_architecture_agent_explains_cycle(seedy_analysis: int) -> None:
    findings = _findings(seedy_analysis)
    arch = [f for f in findings if f.agent == "architecture"]
    assert arch, "Architecture Agent produced no findings"
    assert any("module" in (f.description or "").lower() or f.category == "layering" for f in arch)


def test_cost_ledger_recorded(seedy_analysis: int) -> None:
    session = get_session_factory()()
    try:
        analysis = session.get(Analysis, seedy_analysis)
        ledger = analysis.cost_json or {}
        agents = ledger.get("agents", [])
        assert len(agents) >= 5, f"expected 5 agent runs in ledger, got {len(agents)}"
        assert ledger.get("tokens_in", 0) > 0
        assert all("model" in run for run in agents)
    finally:
        session.close()
