"""Analysis detail, findings, agent intake, and SSE progress stream."""

import json
import logging
from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.analysis_engine import trust
from app.analysis_engine.scoring import compute_score
from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user
from app.events import get_bus
from app.models import Analysis, AnalysisStatus, Finding, User
from app.schemas import (
    AgentFindingsIn,
    AgentFindingsOut,
    AnalysisHistoryOut,
    AnalysisOut,
    CompareOut,
    FindingOut,
    ScoreOut,
    TrustSummaryOut,
)

router = APIRouter(prefix="/analyses", tags=["analyses"])
logger = logging.getLogger(__name__)


def _get_analysis(db: Session, analysis_id: int) -> Analysis:
    analysis = db.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    return analysis


# Declared before /{analysis_id} so the literal path is not shadowed by the int param.
@router.get("/compare", response_model=CompareOut)
def compare_analyses(
    left: int = Query(ge=1),
    right: int = Query(ge=1),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> CompareOut:
    """Side-by-side comparison of two analyses (score + per-pillar deltas)."""
    left_row = _get_analysis(db, left)
    right_row = _get_analysis(db, right)
    if left_row.repository_id != right_row.repository_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="analyses belong to different repositories",
        )
    return CompareOut.model_validate(trust.build_comparison(left_row, right_row, db))


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
    from app.analysis_engine import approvals

    out.pending_approvals = len(approvals.pending_findings(db, analysis_id))
    return out


def _calibration_of(score: dict) -> tuple:
    """The constants a stored score was produced with.

    A score's meaning depends on these, so two scores are only comparable when they
    match. Absent keys mean an older payload, which is treated as a mismatch rather
    than assumed equal.
    """
    return (
        score.get("half_score_density"),
        score.get("worst_pillar_headroom"),
    )


@router.get("/{analysis_id}/score", response_model=ScoreOut)
def get_score(
    analysis_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ScoreOut:
    analysis = _get_analysis(db, analysis_id)
    # Never score an analysis that is still running. Findings land progressively, so
    # a score computed mid-run counts only what exists at that moment — for a run
    # whose analyzers had not yet reported, that is zero findings, every pillar at
    # 100, and an overall of a confident-looking 100. Worse, the value was persisted,
    # so it outlived the run: the client cached it and, because the score query is
    # never invalidated when the analysis completes, kept displaying 100 next to a
    # finished analysis that actually scored 88. finalize_analysis writes the real
    # score in the same commit that flips the status to done, so an unfinished
    # analysis simply has no score yet.
    if analysis.status != AnalysisStatus.DONE and not analysis.score_json:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="analysis has not finished; no score exists yet",
        )
    if analysis.score_json:
        score = dict(analysis.score_json)
        score.setdefault("previous_overall", None)
        score.setdefault("delta", None)
        previous = trust.previous_analysis(db, analysis)
        if previous is not None and previous.score_json:
            current = score.get("overall")
            earlier = previous.score_json.get("overall")
            # Only compare like with like. Two things decide whether two scores are
            # comparable: the formula version, and the calibration constants it was
            # produced with. A version match alone is not enough — retuning
            # HALF_SCORE_DENSITY changes every score without changing the shape, and
            # subtracting across that change would report a phantom improvement.
            same_curve = previous.score_json.get("version") == score.get("version")
            same_calibration = _calibration_of(previous.score_json) == _calibration_of(score)
            if same_curve and same_calibration:
                score["previous_overall"] = earlier
                if isinstance(current, int) and isinstance(earlier, int):
                    score["delta"] = current - earlier
        return ScoreOut.model_validate(score)
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


@router.post("/{analysis_id}/findings", response_model=AgentFindingsOut)
def record_findings(
    analysis_id: int,
    payload: AgentFindingsIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> AgentFindingsOut:
    """Intake for the eve agent: persist D2 verdict claims, then re-run the trust layer.

    Claims land as ``hypothesis`` and are verified, calibrated, and scored here so
    the same deterministic gates apply whether a claim came from a tool or an agent.
    """
    from app.analysis_engine import agent_findings, approvals, verify
    from app.analysis_engine import calibration as calibration_mod

    analysis = _get_analysis(db, analysis_id)
    result = agent_findings.record_findings(
        db, analysis_id, payload.agent, [f.model_dump() for f in payload.findings]
    )
    dismissed = agent_findings.apply_triage(db, analysis_id, payload.triage)

    promoted = checked = 0
    settings = get_settings()
    repo_root = settings.data_dir / "repos" / str(analysis.repository_id) / str(analysis_id)
    try:
        verification = verify.verify_analysis(db, analysis_id, repo_root)
        promoted, checked = verification.promoted, verification.checked
    except Exception:  # noqa: BLE001 — a checkout-less analysis must still accept claims
        logger.exception("verification failed while recording agent findings")
    try:
        calibration_mod.recalibrate_analysis(db, analysis_id)
    except Exception:  # noqa: BLE001
        logger.exception("calibration failed while recording agent findings")

    score = compute_score(db, analysis_id)
    analysis.score_json = score
    pending = approvals.pending_findings(db, analysis_id)
    analysis.published = not pending
    db.commit()

    return AgentFindingsOut(
        analysis_id=analysis_id,
        agent=payload.agent,
        inserted=result.inserted,
        dropped=result.dropped,
        dismissed=dismissed,
        promoted=promoted,
        checked=checked,
        overall=score["overall"],
        published=bool(analysis.published),
        reasons=result.reasons,
    )


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


@router.get("/{analysis_id}/history", response_model=list[AnalysisHistoryOut])
def analysis_history(
    analysis_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[AnalysisHistoryOut]:
    """All analyses for the same repository, newest first (for delta + compare)."""
    analysis = _get_analysis(db, analysis_id)
    rows = db.scalars(
        select(Analysis)
        .where(Analysis.repository_id == analysis.repository_id)
        .order_by(Analysis.created_at.desc(), Analysis.id.desc())
    ).all()
    return [_history_out(db, row) for row in rows]


@router.get("/{analysis_id}/trust-summary", response_model=TrustSummaryOut)
def trust_summary(
    analysis_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> TrustSummaryOut:
    """Verification coverage and per-agent confidence for the trust panel."""
    from app.analysis_engine import trust

    _get_analysis(db, analysis_id)
    return TrustSummaryOut.model_validate(trust.build_trust_summary(db, analysis_id))


@router.get("/{analysis_id}/snippet")
def code_snippet(
    analysis_id: int,
    path: str = Query(min_length=1),
    line_start: int = Query(ge=1, default=1),
    context: int = Query(ge=0, le=20, default=4),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """Return a code snippet around a cited line from the analyzed snapshot.

    Reads from the immutable analysis snapshot on disk, and refuses any path
    that escapes the repository root.
    """
    from app.config import get_settings

    analysis = _get_analysis(db, analysis_id)
    settings = get_settings()
    repo_root = (
        settings.data_dir / "repos" / str(analysis.repository_id) / str(analysis_id)
    ).resolve()
    target = (repo_root / path).resolve()
    if not str(target).startswith(str(repo_root) + "/"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="path escapes repository root")
    if not target.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="file not found in snapshot")
    try:
        lines = target.read_text(errors="replace").splitlines()
    except OSError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="could not read file") from exc
    start = max(0, line_start - 1 - context)
    end = min(len(lines), line_start + context)
    return {
        "path": path,
        "line_start": line_start,
        "from_line": start + 1,
        "to_line": end,
        "lines": lines[start:end],
    }


def _history_out(db: Session, analysis: Analysis) -> AnalysisHistoryOut:
    out = AnalysisHistoryOut.model_validate(analysis)
    out.finding_count = (
        db.scalar(select(func.count(Finding.id)).where(Finding.analysis_id == analysis.id)) or 0
    )
    score = analysis.score_json or {}
    out.overall = score.get("overall")
    out.published = bool(analysis.published)
    return out
