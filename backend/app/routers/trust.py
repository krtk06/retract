"""Approval queue endpoints (Phase 5, D5) and calibration stats."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis_engine import approvals
from app.db import get_db
from app.deps import get_current_user
from app.models import Analysis, Approval, ApprovalDecision, CalibrationStat, User
from app.schemas import ApprovalOut, ApprovalRequest, CalibrationStatOut, FindingOut, QueueOut

router = APIRouter(tags=["trust"])


def _ensure_analysis(db: Session, analysis_id: int) -> Analysis:
    analysis = db.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    return analysis


@router.get("/analyses/{analysis_id}/approvals/queue", response_model=QueueOut)
def get_queue(
    analysis_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> QueueOut:
    analysis = _ensure_analysis(db, analysis_id)
    pending = approvals.pending_findings(db, analysis_id)
    summary = approvals.summarize(db, analysis_id)
    return QueueOut(
        analysis_id=analysis_id,
        published=analysis.published,
        pending_count=summary.pending,
        approved_count=summary.approved,
        dismissed_count=summary.dismissed,
        pending=[FindingOut.model_validate(f) for f in pending],
    )


@router.post("/analyses/{analysis_id}/approvals", response_model=ApprovalOut)
def decide_approval(
    analysis_id: int,
    payload: ApprovalRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApprovalOut:
    _ensure_analysis(db, analysis_id)
    if payload.decision not in ("approve", "dismiss"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="invalid decision")
    try:
        finding = approvals.decide(
            db,
            analysis_id,
            payload.finding_id,
            user.id,
            ApprovalDecision(payload.decision),
            payload.note,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    latest = db.scalar(
        select(Approval)
        .where(Approval.finding_id == finding.id)
        .order_by(Approval.created_at.desc())
        .limit(1)
    )
    return ApprovalOut(
        finding_id=finding.id,
        decision=payload.decision,
        finding_status=finding.status.value,
        confidence=finding.confidence,
        note=latest.note if latest else payload.note,
        pending_count=len(approvals.pending_findings(db, analysis_id)),
        published=bool(_ensure_analysis(db, analysis_id).published),
    )


@router.get("/calibration/stats", response_model=list[CalibrationStatOut])
def calibration_stats(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[CalibrationStatOut]:
    stats = db.scalars(
        select(CalibrationStat).order_by(CalibrationStat.dismissed.desc(), CalibrationStat.agent)
    ).all()
    out = []
    for stat in stats:
        total = stat.accepted + stat.dismissed
        out.append(
            CalibrationStatOut(
                agent=stat.agent,
                category=stat.category,
                shown=stat.shown,
                accepted=stat.accepted,
                dismissed=stat.dismissed,
                acceptance_rate=round(stat.accepted / total, 3) if total else None,
            )
        )
    return out
