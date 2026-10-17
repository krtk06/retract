"""Analysis detail, findings, agent intake, and SSE progress stream."""

import json
import logging
from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.analysis_engine import remediation, trust
from app.analysis_engine.scoring import compute_score
from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user, get_owned_analysis_or_404
from app.events import get_bus
from app.models import (
    Analysis,
    AnalysisStatus,
    Finding,
    FindingStatus,
    Severity,
    User,
)
from app.routers.analyses_support import (
    history_out,
    plan_out,
    read_snippet,
    recent_analyses,
    require_finished,
    score_from_stored,
)
from app.schemas import (
    AgentFindingsIn,
    AgentFindingsOut,
    AnalysisHistoryOut,
    AnalysisOut,
    AnalysisSummaryOut,
    CompareOut,
    FindingOut,
    RemediationPlanOut,
    RemediationSubmitIn,
    RemediationSubmitOut,
    ScoreOut,
    TrustSummaryOut,
)

router = APIRouter(prefix="/analyses", tags=["analyses"])
logger = logging.getLogger(__name__)


def _get_analysis(db: Session, analysis_id: int, user: User) -> Analysis:
    """Owned-analysis lookup: 404 for both missing and non-owned rows."""
    return get_owned_analysis_or_404(db, analysis_id, user)


# Declared before /{analysis_id} so the literal path is not shadowed by the int param.
@router.get("", response_model=list[AnalysisSummaryOut])
def list_analyses(
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AnalysisSummaryOut]:
    """Recent analyses across the caller's repositories: the dashboard feed."""
    return recent_analyses(db, user, limit)


@router.get("/compare", response_model=CompareOut)
def compare_analyses(
    left: int = Query(ge=1),
    right: int = Query(ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CompareOut:
    """Side-by-side comparison of two analyses (score + per-pillar deltas)."""
    left_row = _get_analysis(db, left, user)
    right_row = _get_analysis(db, right, user)
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
    user: User = Depends(get_current_user),
) -> AnalysisOut:
    analysis = _get_analysis(db, analysis_id, user)
    out = AnalysisOut.model_validate(analysis)
    out.finding_count = (
        db.scalar(select(func.count(Finding.id)).where(Finding.analysis_id == analysis_id)) or 0
    )
    from app.analysis_engine import approvals

    out.pending_approvals = len(approvals.pending_findings(db, analysis_id))
    return out


@router.get("/{analysis_id}/score", response_model=ScoreOut)
def get_score(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScoreOut:
    analysis = _get_analysis(db, analysis_id, user)
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
        return score_from_stored(db, analysis)
    score = compute_score(db, analysis_id)
    analysis.score_json = score
    db.commit()
    return ScoreOut.model_validate(score)


@router.get("/{analysis_id}/findings", response_model=list[FindingOut])
def list_findings(
    analysis_id: int,
    agent: str | None = None,
    # Typed as the enums, not `str`: an unknown value like `?severity=bogus` used to
    # reach the column and raise a LookupError deep in the driver — a 500 for what is
    # plainly a bad request. FastAPI now rejects it as a 422 before any query runs.
    severity: Severity | None = None,
    finding_status: FindingStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[FindingOut]:
    _get_analysis(db, analysis_id, user)
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
    user: User = Depends(get_current_user),
) -> AgentFindingsOut:
    """Intake for the eve agent: persist D2 verdict claims, then re-run the trust layer.

    Claims land as ``hypothesis`` and are verified, calibrated, and scored here so
    the same deterministic gates apply whether a claim came from a tool or an agent.
    """
    from app.analysis_engine import agent_findings, approvals, verify
    from app.analysis_engine import calibration as calibration_mod

    analysis = _get_analysis(db, analysis_id, user)
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
    except Exception as exc:  # noqa: BLE001 — a checkout-less analysis must still accept claims
        logger.exception("verification failed while recording agent findings: %s", exc)
    try:
        calibration_mod.recalibrate_analysis(db, analysis_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("calibration failed while recording agent findings: %s", exc)

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


@router.get("/{analysis_id}/remediation", response_model=RemediationPlanOut)
def get_remediation(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RemediationPlanOut:
    """Prioritised fix plan: what to fix, in what order, and what it is worth."""
    analysis = _get_analysis(db, analysis_id, user)
    require_finished(analysis)
    return plan_out(remediation.build_plan(db, analysis_id))


@router.get("/{analysis_id}/remediation.md")
def get_remediation_markdown(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """The plan as a Markdown document, for an issue or a PR description."""
    analysis = _get_analysis(db, analysis_id, user)
    require_finished(analysis)
    repo = analysis.repository
    label = f"{repo.owner}/{repo.name}" if repo else f"analysis-{analysis_id}"
    body = remediation.render_markdown(
        remediation.build_plan(db, analysis_id), label, analysis.commit_sha
    )
    filename = f"{label.replace('/', '-')}-fix-plan.md"
    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{analysis_id}/remediation", response_model=RemediationSubmitOut)
def record_remediation(
    analysis_id: int,
    payload: RemediationSubmitIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RemediationSubmitOut:
    """Intake for LLM-authored fixes.

    Stored in the finding's ``evidence_json`` alongside the verification,
    calibration, and triage records, so a fix lives and dies with its finding:
    dismiss the finding as a false positive and its advice goes with it. The
    submitted action is *not* verified or scored — advice is not a claim about
    the code — but it is attributed to the submitting agent so a reader can
    always tell it apart from catalog advice.
    """
    from app.analysis_engine.remediation import EFFORT_WEIGHT

    _get_analysis(db, analysis_id, user)
    reasons: list[str] = []
    recorded = 0
    for item in payload.remediations:
        finding = db.get(Finding, item.finding_id)
        if finding is None or finding.analysis_id != analysis_id:
            reasons.append(f"finding {item.finding_id} not found in this analysis")
            continue
        if finding.status == FindingStatus.DISMISSED:
            reasons.append(f"finding {item.finding_id} is dismissed; its fix was not stored")
            continue
        effort = item.effort if item.effort in EFFORT_WEIGHT else "medium"
        evidence = dict(finding.evidence_json or {})
        evidence["remediation"] = {
            "action": item.action,
            "steps": [s[:500] for s in item.steps][:10],
            "effort": effort,
            "verify": item.verify[:500],
            "references": [r[:400] for r in item.references][:5],
            "source": payload.agent,
            "reasoning": item.reasoning[:1000],
        }
        finding.evidence_json = evidence
        recorded += 1

    if recorded:
        db.commit()

    return RemediationSubmitOut(
        analysis_id=analysis_id,
        agent=payload.agent,
        recorded=recorded,
        rejected=len(payload.remediations) - recorded,
        reasons=reasons,
    )


@router.get("/{analysis_id}/events")
def stream_events(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EventSourceResponse:
    """Replay event history, then stream live events until a terminal event."""
    _get_analysis(db, analysis_id, user)
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
    user: User = Depends(get_current_user),
) -> list[AnalysisHistoryOut]:
    """All analyses for the same repository, newest first (for delta + compare)."""
    analysis = _get_analysis(db, analysis_id, user)
    rows = db.scalars(
        select(Analysis)
        .where(Analysis.repository_id == analysis.repository_id)
        .order_by(Analysis.created_at.desc(), Analysis.id.desc())
    ).all()
    return [history_out(db, row) for row in rows]


@router.get("/{analysis_id}/trust-summary", response_model=TrustSummaryOut)
def trust_summary(
    analysis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TrustSummaryOut:
    """Verification coverage and per-agent confidence for the trust panel."""
    from app.analysis_engine import trust

    _get_analysis(db, analysis_id, user)
    return TrustSummaryOut.model_validate(trust.build_trust_summary(db, analysis_id))


@router.get("/{analysis_id}/snippet")
def code_snippet(
    analysis_id: int,
    path: str = Query(min_length=1),
    line_start: int = Query(ge=1, default=1),
    context: int = Query(ge=0, le=20, default=4),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Return a code snippet around a cited line from the analyzed snapshot.

    Reads from the immutable analysis snapshot on disk, and refuses any path
    that escapes the repository root.
    """
    from app.config import get_settings

    analysis = _get_analysis(db, analysis_id, user)
    settings = get_settings()
    repo_root = (
        settings.data_dir / "repos" / str(analysis.repository_id) / str(analysis_id)
    ).resolve()
    return read_snippet(repo_root, path, line_start, context)
