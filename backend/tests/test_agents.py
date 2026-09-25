"""Agent framework tests: schema validation, repair, drop, and triage (mocked LLM)."""

from pathlib import Path

import pytest

from app.agents.base import AgentContext, BaseAgent, apply_triage
from app.agents.code_agent import CodeAgent
from app.db import get_session_factory
from app.llm.client import LLMResponse, set_llm_client
from app.llm.mock import ScriptedMockLLM
from app.models import (
    Analysis,
    Finding,
    FindingStatus,
    Repository,
    Severity,
    User,
)
from app.services.tools.findings import FindingDraft, persist_findings


class _StubAgent(BaseAgent):
    name = "code"

    def build_context(self, ctx: AgentContext) -> dict:
        return {"static_findings": []}


@pytest.fixture
def analysis_id() -> int:
    import uuid

    session = get_session_factory()()
    try:
        user = session.query(User).first()
        if user is None:
            user = User(github_id=None, login="agentfixture")
            session.add(user)
            session.commit()
        suffix = uuid.uuid4().hex[:8]
        repo = Repository(
            owner="fixture",
            name=f"agents-{suffix}",
            url=f"local://fixture/agents-{suffix}",
            default_branch="main",
            added_by=user.id,
        )
        session.add(repo)
        session.commit()
        analysis = Analysis(repository_id=repo.id)
        session.add(analysis)
        session.commit()
        return analysis.id
    finally:
        session.close()


def test_valid_output_becomes_hypothesis(analysis_id: int, tmp_path: Path) -> None:
    payload = (
        '{"findings": [{"claim": "Unchecked return value", '
        '"evidence": "See src/a.py:10", "file_path": "src/a.py", '
        '"line_start": 10, "severity": "medium", "confidence": 0.8, '
        '"category": "code-review"}], "summary": "ok"}'
    )
    session = get_session_factory()()
    try:
        agent = _StubAgent(ScriptedMockLLM([payload]))
        result = agent.run(AgentContext(analysis_id, tmp_path, session))
        assert result.error is None
        assert len(result.findings) == 1
        draft = result.findings[0]
        assert draft.status == FindingStatus.HYPOTHESIS
        assert draft.verifier == "llm:mock-scripted"
        assert draft.file_path == "src/a.py"
        assert draft.line_start == 10
    finally:
        session.close()


def test_malformed_then_repair_succeeds(analysis_id: int, tmp_path: Path) -> None:
    good = '{"findings": [], "summary": "repaired"}'
    session = get_session_factory()()
    try:
        agent = _StubAgent(ScriptedMockLLM(["not json at all", good]))
        result = agent.run(AgentContext(analysis_id, tmp_path, session))
        assert result.error is None
        assert result.repaired == 1
        assert result.summary == "repaired"
    finally:
        session.close()


def test_unparseable_after_repair_drops_run(analysis_id: int, tmp_path: Path) -> None:
    session = get_session_factory()()
    try:
        agent = _StubAgent(ScriptedMockLLM(["nope", "still nope"]))
        result = agent.run(AgentContext(analysis_id, tmp_path, session))
        assert result.error is not None
        assert result.findings == []
    finally:
        session.close()


def test_schema_violation_is_repaired(analysis_id: int, tmp_path: Path) -> None:
    # Missing required `evidence` -> validation error -> repair.
    invalid = '{"findings": [{"claim": "x"}]}'
    valid = '{"findings": [], "summary": "fixed"}'
    session = get_session_factory()()
    try:
        agent = _StubAgent(ScriptedMockLLM([invalid, valid]))
        result = agent.run(AgentContext(analysis_id, tmp_path, session))
        assert result.repaired == 1
        assert result.error is None
    finally:
        session.close()


def test_llm_failure_returns_error(analysis_id: int, tmp_path: Path) -> None:
    from app.llm.client import LLMError

    class _FailingLLM:
        name = "failing"
        model = "none"

        def complete(
            self,
            system: str,
            user: str,
            json_schema: dict | None = None,
            schema_name: str = "response",
        ) -> LLMResponse:
            raise LLMError("boom")

    session = get_session_factory()()
    try:
        agent = _StubAgent(_FailingLLM())
        result = agent.run(AgentContext(analysis_id, tmp_path, session))
        assert result.error == "boom"
        assert result.findings == []
    finally:
        session.close()


def test_apply_triage_dismisses_target(analysis_id: int) -> None:
    session = get_session_factory()()
    try:
        persist_findings(
            session,
            analysis_id,
            [
                FindingDraft(
                    agent="static-analysis",
                    category="vulnerability",
                    severity=Severity.MEDIUM,
                    title="Insecure hash algorithm",
                    description="md5 used",
                    file_path="app/cache_key.py",
                    line_start=9,
                    verifier="tool:semgrep",
                )
            ],
        )
        finding = session.query(Finding).filter(Finding.analysis_id == analysis_id).first()
        applied = apply_triage(
            session,
            analysis_id,
            [
                {
                    "finding_id": finding.id,
                    "verdict": "false-positive",
                    "confidence": 0.9,
                    "reasoning": "cache key only",
                }
            ],
        )
        assert applied == 1
        session.refresh(finding)
        assert finding.status == FindingStatus.DISMISSED
        assert finding.evidence_json["triage"]["verdict"] == "false-positive"
    finally:
        session.close()


def test_set_llm_client_fixture_isolation() -> None:
    set_llm_client(None)
    # CodeAgent without a client would need configuration; injection avoids that.
    client = ScriptedMockLLM(['{"findings": []}'])
    agent = CodeAgent(client)
    assert agent.llm is client
    set_llm_client(None)
