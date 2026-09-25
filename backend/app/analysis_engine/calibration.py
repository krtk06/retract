"""Confidence calibration (D5).

Combines three signals into a calibrated confidence:
  - model-declared / logprob confidence (already stored on the finding);
  - self-consistency: agreement across independent verdict samples;
  - cross-tool / cross-agent agreement at the same location;
  - historical acceptance rate for the (agent, category) via Beta-Bernoulli
    shrinkage towards a neutral prior.

Pure LLM-only claims are capped below certainty until a tool corroborates them.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CalibrationStat, Finding, FindingStatus

PRIOR_ACCEPT = 2.0
PRIOR_DISMISS = 2.0
LLM_ONLY_CAP = 0.6
MAX_CONFIDENCE = 0.99


@dataclass
class CalibrationResult:
    raw_confidence: float
    history_rate: float
    effective: float
    corroborated: bool
    samples: int


def historical_acceptance_rate(session: Session, agent: str, category: str) -> tuple[float, int]:
    stat = session.scalar(
        select(CalibrationStat).where(
            CalibrationStat.agent == agent, CalibrationStat.category == category
        )
    )
    if stat is None:
        return (PRIOR_ACCEPT / (PRIOR_ACCEPT + PRIOR_DISMISS), 0)
    accepted = stat.accepted + PRIOR_ACCEPT
    dismissed = stat.dismissed + PRIOR_DISMISS
    return (accepted / (accepted + dismissed), stat.shown)


def _corroboration_count(session: Session, finding: Finding) -> int:
    """Independent findings at the same location (any agent/verifier)."""
    if not finding.file_path:
        return 0
    conditions = [
        Finding.analysis_id == finding.analysis_id,
        Finding.id != finding.id,
        Finding.file_path == finding.file_path,
    ]
    if finding.line_start is not None:
        conditions.append(Finding.line_start == finding.line_start)
    return int(session.scalar(select(func.count(Finding.id)).where(*conditions)) or 0)


def calibrate_finding(
    session: Session, finding: Finding, self_consistency: float | None = None
) -> CalibrationResult:
    raw = finding.confidence if finding.confidence is not None else 0.5
    corroboration = _corroboration_count(session, finding)
    corroborated = corroboration > 0
    history, samples = historical_acceptance_rate(session, finding.agent, finding.category)

    signals = [raw, history]
    if self_consistency is not None:
        signals.append(self_consistency)
    if corroborated:
        signals.append(0.85)

    effective = sum(signals) / len(signals)
    if not corroborated and finding.verifier.startswith("llm:"):
        effective = min(effective, LLM_ONLY_CAP)

    effective = max(0.0, min(MAX_CONFIDENCE, round(effective, 3)))
    return CalibrationResult(
        raw_confidence=round(raw, 3),
        history_rate=round(history, 3),
        effective=effective,
        corroborated=corroborated,
        samples=samples,
    )


def recalibrate_analysis(session: Session, analysis_id: int) -> int:
    """Apply calibration to every hypothesis/verified finding. Returns count updated."""
    findings = session.scalars(
        select(Finding).where(
            Finding.analysis_id == analysis_id,
            Finding.status.in_((FindingStatus.HYPOTHESIS, FindingStatus.VERIFIED)),
        )
    ).all()
    for finding in findings:
        # Prefer a tool/cross-source confidence as the raw signal when verified.
        if finding.status == FindingStatus.VERIFIED:
            result = calibrate_finding(session, finding, self_consistency=0.9)
        else:
            result = calibrate_finding(session, finding)
        finding.confidence = result.effective
        evidence = dict(finding.evidence_json or {})
        evidence["calibration"] = {
            "raw_confidence": result.raw_confidence,
            "history_rate": result.history_rate,
            "effective": result.effective,
            "corroborated": result.corroborated,
            "samples": result.samples,
        }
        finding.evidence_json = evidence
    session.commit()
    return len(findings)


def record_feedback(session: Session, agent: str, category: str, decision: str) -> CalibrationStat:
    """Update the per-(agent, category) counter after a human decision."""
    stat = session.scalar(
        select(CalibrationStat).where(
            CalibrationStat.agent == agent, CalibrationStat.category == category
        )
    )
    if stat is None:
        stat = CalibrationStat(agent=agent, category=category, shown=0, accepted=0, dismissed=0)
        session.add(stat)
    stat.shown += 1
    if decision == "approve":
        stat.accepted += 1
    elif decision == "dismiss":
        stat.dismissed += 1
    session.commit()
    return stat
