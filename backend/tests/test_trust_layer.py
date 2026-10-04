"""Phase 5 trust-layer tests: verifier, calibration, approvals, honest scoring."""

import uuid
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.analysis_engine import approvals, calibration, verify
from app.analysis_engine.scoring import compute_score
from app.db import get_session_factory
from app.models import (
    Analysis,
    ApprovalDecision,
    CalibrationStat,
    Finding,
    FindingStatus,
    Repository,
    Severity,
    User,
)
from app.services.tools.findings import FindingDraft, persist_findings


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "db.py").write_text(
        "import sqlite3\n\n\n"
        "def find_user(cursor, username):\n"
        "    query = f\"SELECT * FROM users WHERE name = '{username}'\"\n"
        "    cursor.execute(query)\n"
        "    return cursor.fetchone()\n"
    )
    (tmp_path / "pkg" / "safe.py").write_text("def add(a, b):\n    return a + b\n")
    return tmp_path


@pytest.fixture
def analysis_id(tmp_path: Path) -> int:
    session = get_session_factory()()
    try:
        user = session.query(User).first()
        if user is None:
            user = User(github_id=None, login="trustfixture")
            session.add(user)
            session.commit()
        suffix = uuid.uuid4().hex[:8]
        repo = Repository(
            owner="fixture",
            name=f"trust-{suffix}",
            url=f"local://fixture/trust-{suffix}",
            default_branch="main",
            added_by=user.id,
        )
        session.add(repo)
        session.commit()
        analysis = Analysis(repository_id=repo.id, loc=1000)
        session.add(analysis)
        session.commit()
        return analysis.id
    finally:
        session.close()


def _hypothesis(session: Session, analysis_id: int, **kwargs) -> Finding:
    defaults = dict(
        agent="security",
        category="injection",
        severity=Severity.HIGH,
        title="claim",
        description="evidence",
        file_path="pkg/db.py",
        line_start=5,
        verifier="llm:mock",
        confidence=0.7,
        status=FindingStatus.HYPOTHESIS,
    )
    defaults.update(kwargs)
    finding = Finding(analysis_id=analysis_id, **defaults)
    session.add(finding)
    session.commit()
    return finding


def test_verifier_promotes_true_security_claim(analysis_id: int, repo_root: Path) -> None:
    session = get_session_factory()()
    try:
        true_finding = _hypothesis(session, analysis_id, file_path="pkg/db.py", line_start=5)
        summary = verify.verify_analysis(session, analysis_id, repo_root)
        session.refresh(true_finding)
        assert summary.promoted == 1
        assert true_finding.status == FindingStatus.VERIFIED
        assert "verified:source-pattern" in true_finding.verifier
    finally:
        session.close()


def test_verifier_rejects_false_security_claim(analysis_id: int, repo_root: Path) -> None:
    session = get_session_factory()()
    try:
        false_finding = _hypothesis(session, analysis_id, file_path="pkg/safe.py", line_start=1)
        summary = verify.verify_analysis(session, analysis_id, repo_root)
        session.refresh(false_finding)
        assert summary.failed == 1
        assert false_finding.status == FindingStatus.HYPOTHESIS
        assert "verification_error" in (false_finding.evidence_json or {})
    finally:
        session.close()


def test_verifier_rejects_nonexistent_citation(analysis_id: int, repo_root: Path) -> None:
    session = get_session_factory()()
    try:
        finding = _hypothesis(session, analysis_id, file_path="pkg/ghost.py", line_start=1)
        summary = verify.verify_analysis(session, analysis_id, repo_root)
        session.refresh(finding)
        assert summary.failed == 1
        assert finding.status == FindingStatus.HYPOTHESIS
    finally:
        session.close()


def test_llm_only_confidence_is_capped(analysis_id: int) -> None:
    session = get_session_factory()()
    try:
        finding = _hypothesis(session, analysis_id, confidence=0.95)
        result = calibration.calibrate_finding(session, finding)
        assert result.effective <= calibration.LLM_ONLY_CAP
        assert result.corroborated is False
    finally:
        session.close()


def test_cross_source_corroboration_raises_confidence(analysis_id: int) -> None:
    session = get_session_factory()()
    try:
        _hypothesis(
            session,
            analysis_id,
            agent="static-analysis",
            verifier="tool:semgrep",
            status=FindingStatus.VERIFIED,
        )
        finding = _hypothesis(session, analysis_id)
        result = calibration.calibrate_finding(session, finding)
        assert result.corroborated is True
        assert result.effective > calibration.LLM_ONLY_CAP
    finally:
        session.close()


def test_feedback_loop_updates_acceptance_rate(analysis_id: int) -> None:
    session = get_session_factory()()
    try:
        before, _ = calibration.historical_acceptance_rate(session, "security", "injection")
        calibration.record_feedback(session, "security", "injection", "approve")
        calibration.record_feedback(session, "security", "injection", "dismiss")
        calibration.record_feedback(session, "security", "injection", "dismiss")
        stat = (
            session.query(CalibrationStat).filter_by(agent="security", category="injection").one()
        )
        assert stat.shown == 3
        assert stat.accepted == 1
        assert stat.dismissed == 2
        after, samples = calibration.historical_acceptance_rate(session, "security", "injection")
        assert samples == 3
        assert after < before  # more dismissals lower the historical rate
    finally:
        session.close()


def test_approval_publishes_when_gates_cleared(analysis_id: int) -> None:
    session = get_session_factory()()
    try:
        user = session.query(User).first()
        finding = _hypothesis(session, analysis_id, severity=Severity.HIGH)
        analysis = session.get(Analysis, analysis_id)
        assert approvals.pending_findings(session, analysis_id)
        analysis.published = False
        session.commit()

        approvals.decide(
            session, analysis_id, finding.id, user.id, ApprovalDecision.DISMISS, "not exploitable"
        )
        session.refresh(analysis)
        session.refresh(finding)
        assert finding.status == FindingStatus.DISMISSED
        assert analysis.published is True
    finally:
        session.close()


def test_approve_promotes_and_records_feedback(analysis_id: int) -> None:
    session = get_session_factory()()
    try:
        user = session.query(User).first()
        finding = _hypothesis(session, analysis_id, category="weak-crypto")
        approvals.decide(session, analysis_id, finding.id, user.id, ApprovalDecision.APPROVE)
        session.refresh(finding)
        assert finding.status == FindingStatus.VERIFIED
        stat = (
            session.query(CalibrationStat).filter_by(agent="security", category="weak-crypto").one()
        )
        assert stat.accepted == 1
    finally:
        session.close()


def test_honest_score_discounts_hypotheses_and_dismissals(analysis_id: int) -> None:
    session = get_session_factory()()
    try:
        # 1 verified high, 1 hypothesis high, 1 dismissed high, all in security.
        persist_findings(
            session,
            analysis_id,
            [
                FindingDraft(
                    agent="security",
                    category="vulnerability",
                    severity=Severity.HIGH,
                    title="v",
                    verifier="tool:semgrep",
                    status=FindingStatus.VERIFIED,
                    confidence=1.0,
                ),
                FindingDraft(
                    agent="security",
                    category="vulnerability",
                    severity=Severity.HIGH,
                    title="h",
                    verifier="llm:mock",
                    status=FindingStatus.HYPOTHESIS,
                    confidence=0.5,
                ),
                FindingDraft(
                    agent="security",
                    category="vulnerability",
                    severity=Severity.HIGH,
                    title="d",
                    verifier="llm:mock",
                    status=FindingStatus.DISMISSED,
                    confidence=0.2,
                ),
            ],
        )
        score = compute_score(session, analysis_id)
        security = score["pillars"]["security"]
        # 20 (verified) + 10 (hypothesis half) + 0 (dismissed) = 30 weighted over
        # 1.0 KLOC → density 30 → 100 / (1 + 30/100) = 77. The curve itself is
        # covered by tests/test_scoring_curve.py.
        assert security["verified"] == 1
        assert security["hypotheses"] == 1
        assert security["dismissed"] == 1
        # 20 verified + 20 hypothesis at half weight = 30 points over 1 KLOC, which is
        # exactly HALF_SCORE_DENSITY, so the pillar lands on the half-score point.
        assert security["weighted_penalty"] == pytest.approx(30.0)
        assert security["score"] == 50
        assert score["version"] == 5
    finally:
        session.close()
