"""Analysis detail, findings, and SSE progress stream."""

import json
from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.analysis_engine.scoring import compute_score
from app.db import get_db
from app.deps import get_current_user
from app.events import get_bus
from app.models import Analysis, Finding, User
from app.schemas import AnalysisOut, FindingOut, ScoreOut

router = APIRouter(prefix="/analyses", tags=["analyses"])


def _get_analysis(db: Session, analysis_id: int) -> Analysis:
    analysis = db.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    return analysis


@router.get("/{analysis_id}", response_model=AnalysisOut)
def get_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> AnalysisOut:
    analysis = _get_analysis(db, analysis_id)
    out = AnalysisOut.model_validate(analysis)
    out.finding_count = (
        db.scalar(select(func.count(Finding.id)).where(Finding.analysis_id == analysis_id)) or 0
    )
    return out


@router.get("/{analysis_id}/score", response_model=ScoreOut)
def get_score(
    analysis_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ScoreOut:
    analysis = _get_analysis(db, analysis_id)
    if analysis.score_json:
        return ScoreOut.model_validate(analysis.score_json)
    score = compute_score(db, analysis_id)
    analysis.score_json = score
    db.commit()
    return ScoreOut.model_validate(score)


@router.get("/{analysis_id}/findings", response_model=list[FindingOut])
def list_findings(
    analysis_id: int,
    agent: str | None = None,
    severity: str | None = None,
    finding_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[FindingOut]:
    _get_analysis(db, analysis_id)
    stmt = select(Finding).where(Finding.analysis_id == analysis_id)
    if agent:
        stmt = stmt.where(Finding.agent == agent)
    if severity:
        stmt = stmt.where(Finding.severity == severity)
    if finding_status:
        stmt = stmt.where(Finding.status == finding_status)
    stmt = stmt.order_by(Finding.created_at, Finding.id).limit(limit).offset(offset)
    return [FindingOut.model_validate(f) for f in db.scalars(stmt).all()]


@router.get("/{analysis_id}/events")
def stream_events(
    analysis_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> EventSourceResponse:
    """Replay event history, then stream live events until a terminal event."""
    _get_analysis(db, analysis_id)
    bus = get_bus()

    def events() -> Generator[dict, None, None]:
        terminal_seen = False
        for event in bus.history(analysis_id):
            if event.get("type") in ("done", "failed"):
                terminal_seen = True
            yield {"event": event["type"], "data": json.dumps(event)}
        if terminal_seen:
            return
        for event in bus.stream(analysis_id):
            yield {"event": event["type"], "data": json.dumps(event)}

    return EventSourceResponse(events())
