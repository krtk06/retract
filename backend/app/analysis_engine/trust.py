"""Trust summary + comparison builders for the dashboard (Phase 6)."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Analysis,
    CalibrationStat,
    Finding,
    FindingStatus,
)


def build_trust_summary(session: Session, analysis_id: int) -> dict[str, Any]:
    """Per-agent confidence, status mix, and verification coverage."""
    findings = session.scalars(select(Finding).where(Finding.analysis_id == analysis_id)).all()

    by_agent: dict[str, dict[str, Any]] = {}
    totals = {status: 0 for status in FindingStatus}
    confidences: list[float] = []

    for finding in findings:
        status = finding.status
        totals[status] += 1
        if finding.confidence is not None:
            confidences.append(float(finding.confidence))
        bucket = by_agent.setdefault(
            finding.agent,
            {
                "agent": finding.agent,
                "findings": 0,
                "verified": 0,
                "hypothesis": 0,
                "dismissed": 0,
                "confidence_sum": 0.0,
                "confidence_n": 0,
            },
        )
        bucket["findings"] += 1
        bucket[status.value] += 1
        if finding.confidence is not None:
            bucket["confidence_sum"] += float(finding.confidence)
            bucket["confidence_n"] += 1

    agents = []
    for bucket in by_agent.values():
        agents.append(
            {
                "agent": bucket["agent"],
                "findings": bucket["findings"],
                "verified": bucket["verified"],
                "hypotheses": bucket["hypothesis"],
                "dismissed": bucket["dismissed"],
                "avg_confidence": (
                    round(bucket["confidence_sum"] / bucket["confidence_n"], 3)
                    if bucket["confidence_n"]
                    else None
                ),
            }
        )
    agents.sort(key=lambda a: a["findings"], reverse=True)

    acceptance = _acceptance_rates(session)
    scored = totals[FindingStatus.VERIFIED]
    considered = scored + totals[FindingStatus.HYPOTHESIS]
    coverage = round(scored / considered, 3) if considered else None

    return {
        "analysis_id": analysis_id,
        "totals": {
            "findings": len(findings),
            "verified": totals[FindingStatus.VERIFIED],
            "hypotheses": totals[FindingStatus.HYPOTHESIS],
            "dismissed": totals[FindingStatus.DISMISSED],
        },
        "verification_coverage": coverage,
        "avg_confidence": round(sum(confidences) / len(confidences), 3) if confidences else None,
        "agents": agents,
        "acceptance_rates": acceptance,
    }


def _acceptance_rates(session: Session) -> list[dict[str, Any]]:
    stats = session.scalars(select(CalibrationStat)).all()
    out: list[dict[str, Any]] = []
    for stat in stats:
        total = stat.accepted + stat.dismissed
        out.append(
            {
                "agent": stat.agent,
                "category": stat.category,
                "shown": stat.shown,
                "accepted": stat.accepted,
                "dismissed": stat.dismissed,
                "acceptance_rate": round(stat.accepted / total, 3) if total else None,
            }
        )
    out.sort(key=lambda row: int(row["shown"]), reverse=True)
    return out[:20]


def build_comparison(left: Analysis, right: Analysis, session: Session) -> dict[str, Any]:
    """Compare two analyses of the same repository: score + per-pillar deltas."""
    left_score = left.score_json or {}
    right_score = right.score_json or {}
    left_pillars = left_score.get("pillars", {})
    right_pillars = right_score.get("pillars", {})

    pillars = []
    for pillar in sorted(set(left_pillars) | set(right_pillars)):
        left_pillar = left_pillars.get(pillar, {})
        right_pillar = right_pillars.get(pillar, {})
        left_value = left_pillar.get("score", 0)
        right_value = right_pillar.get("score", 0)
        pillars.append(
            {
                "pillar": pillar,
                "left_score": left_value,
                "right_score": right_value,
                "delta": right_value - left_value,
                "left_findings": left_pillar.get("findings", 0),
                "right_findings": right_pillar.get("findings", 0),
            }
        )

    left_overall = left_score.get("overall")
    right_overall = right_score.get("overall")
    return {
        "left": {
            "id": left.id,
            "commit_sha": left.commit_sha,
            "created_at": left.created_at.isoformat() if left.created_at else None,
            "overall": left_overall,
            "loc": left.loc,
        },
        "right": {
            "id": right.id,
            "commit_sha": right.commit_sha,
            "created_at": right.created_at.isoformat() if right.created_at else None,
            "overall": right_overall,
            "loc": right.loc,
        },
        "overall_delta": (
            right_overall - left_overall
            if left_overall is not None and right_overall is not None
            else None
        ),
        "pillars": pillars,
    }


def previous_analysis(session: Session, analysis: Analysis) -> Analysis | None:
    """The most recent earlier analysis of the same repository with a score."""
    return session.scalar(
        select(Analysis)
        .where(
            Analysis.repository_id == analysis.repository_id,
            Analysis.id != analysis.id,
            Analysis.score_json.is_not(None),
            Analysis.created_at < analysis.created_at,
        )
        .order_by(Analysis.created_at.desc(), Analysis.id.desc())
        .limit(1)
    )
