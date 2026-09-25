"""Human approval queue and publish gating (D5).

High-severity hypotheses must be explicitly approved or dismissed before an
analysis is considered *published*. Dismissals feed the calibration counters.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis_engine.calibration import record_feedback
from app.models import Analysis, Approval, ApprovalDecision, Finding, FindingStatus, Severity

GATING_SEVERITIES = {Severity.HIGH, Severity.CRITICAL}


@dataclass
class ApprovalSummary:
    pending: int
    approved: int
    dismissed: int
    published: bool


def pending_findings(session: Session, analysis_id: int) -> list[Finding]:
    return list(
        session.scalars(
            select(Finding)
            .where(
                Finding.analysis_id == analysis_id,
                Finding.status == FindingStatus.HYPOTHESIS,
                Finding.severity.in_(list(GATING_SEVERITIES)),
            )
            .order_by(Finding.severity.desc(), Finding.id)
        ).all()
    )


def summarize(session: Session, analysis_id: int) -> ApprovalSummary:
    analysis = session.get(Analysis, analysis_id)
    pending = len(pending_findings(session, analysis_id))
    approvals = session.scalars(
        select(Approval).where(
            Approval.finding_id.in_(select(Finding.id).where(Finding.analysis_id == analysis_id))
        )
    ).all()
    approved = sum(1 for a in approvals if a.decision == ApprovalDecision.APPROVE)
    dismissed = sum(1 for a in approvals if a.decision == ApprovalDecision.DISMISS)
    return ApprovalSummary(
        pending=pending,
        approved=approved,
        dismissed=dismissed,
        published=bool(analysis.published) if analysis else False,
    )


def decide(
    session: Session,
    analysis_id: int,
    finding_id: int,
    user_id: int,
    decision: ApprovalDecision,
    note: str | None = None,
) -> Finding:
    """Record an approve/dismiss decision and apply its effect to the finding."""
    finding = session.get(Finding, finding_id)
    if finding is None or finding.analysis_id != analysis_id:
        raise ValueError("finding not found for analysis")

    session.add(
        Approval(
            finding_id=finding_id,
            user_id=user_id,
            decision=decision,
            note=note,
        )
    )
    if decision == ApprovalDecision.APPROVE:
        finding.status = FindingStatus.VERIFIED
        finding.verifier = f"{finding.verifier}+approved"
        finding.confidence = min(1.0, max(finding.confidence, 0.9))
    else:
        finding.status = FindingStatus.DISMISSED
    session.commit()

    record_feedback(session, finding.agent, finding.category, decision.value)
    _maybe_publish(session, analysis_id)
    return finding


def _maybe_publish(session: Session, analysis_id: int) -> None:
    """Publish once no gating findings remain pending."""
    analysis = session.get(Analysis, analysis_id)
    if analysis is None or analysis.published:
        return
    if not pending_findings(session, analysis_id):
        analysis.published = True
        session.commit()


def has_pending_gates(session: Session, analysis_id: int) -> bool:
    return bool(pending_findings(session, analysis_id))
