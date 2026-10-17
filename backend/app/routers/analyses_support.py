"""Response shaping and snapshot reads for the analyses router."""

from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analysis_engine import remediation, trust
from app.deps import visible_repository_ids
from app.models import Analysis, AnalysisStatus, Finding, Repository, User
from app.schemas import (
    AnalysisHistoryOut,
    AnalysisSummaryOut,
    RemediationItemOut,
    RemediationPlanOut,
    RemediationTargetOut,
    ScoreOut,
)


def recent_analyses(db: Session, user: User, limit: int) -> list[AnalysisSummaryOut]:
    """Recent analyses across the caller's repositories: the dashboard feed."""
    counts = (
        select(Finding.analysis_id, func.count(Finding.id).label("finding_count"))
        .group_by(Finding.analysis_id)
        .subquery()
    )
    rows = db.execute(
        select(Analysis, Repository, counts.c.finding_count)
        .join(Repository, Repository.id == Analysis.repository_id)
        .outerjoin(counts, counts.c.analysis_id == Analysis.id)
        .where(Repository.id.in_(visible_repository_ids(user)))
        .order_by(Analysis.created_at.desc(), Analysis.id.desc())
        .limit(limit)
    ).all()
    return [
        AnalysisSummaryOut(
            id=analysis.id,
            repository_id=analysis.repository_id,
            repo_owner=repo.owner,
            repo_name=repo.name,
            commit_sha=analysis.commit_sha,
            status=analysis.status.value,
            created_at=analysis.created_at,
            finished_at=analysis.finished_at,
            loc=analysis.loc,
            published=bool(analysis.published),
            finding_count=finding_count or 0,
            overall=(analysis.score_json or {}).get("overall"),
        )
        for analysis, repo, finding_count in rows
    ]


def calibration_of(score: dict) -> tuple:
    """The constants a stored score was produced with.

    A score's meaning depends on these, so two scores are only comparable when they
    match. Absent keys mean an older payload, which is treated as a mismatch rather
    than assumed equal.
    """
    return (
        score.get("half_score_density"),
        score.get("worst_pillar_headroom"),
    )


def score_from_stored(db: Session, analysis: Analysis) -> ScoreOut:
    """Return a stored score enriched with a like-for-like previous comparison."""
    score = dict(analysis.score_json or {})
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
        same_calibration = calibration_of(previous.score_json) == calibration_of(score)
        if same_curve and same_calibration:
            score["previous_overall"] = earlier
            if isinstance(current, int) and isinstance(earlier, int):
                score["delta"] = current - earlier
    return ScoreOut.model_validate(score)


def plan_out(plan: remediation.RemediationPlan) -> RemediationPlanOut:
    return RemediationPlanOut(
        analysis_id=plan.analysis_id,
        loc=plan.loc,
        current_overall=plan.current_overall,
        projected_overall=plan.projected_overall,
        recoverable_points=plan.recoverable_points,
        findings_considered=plan.findings_considered,
        unverified_items=plan.unverified_items,
        truncated_findings=plan.truncated_findings,
        work_items=[
            RemediationItemOut(
                key=item.key,
                pillar=item.pillar,
                action=item.action,
                severity=item.severity,
                effort=item.effort,
                source=item.source,
                steps=item.steps,
                verify=item.verify,
                references=item.references,
                finding_count=item.finding_count,
                pillar_points=item.pillar_points,
                weighted_penalty_removed=item.weighted_penalty_removed,
                payoff=round(item.payoff(), 2),
                findings=[
                    RemediationTargetOut(
                        finding_id=f.id,
                        title=f.title,
                        severity=f.severity.value,
                        status=f.status.value,
                        file_path=f.file_path,
                        line_start=f.line_start,
                    )
                    for f in item.findings
                ],
            )
            for item in plan.work_items
        ],
    )


def require_finished(analysis: Analysis) -> None:
    """Refuse to advise on a run that has not produced findings yet.

    The same contract as /score: findings land progressively, so a plan built
    mid-run would describe a repository the analyzers have not finished reading —
    and unlike the score, it reads as authoritative advice.
    """
    if analysis.status != AnalysisStatus.DONE:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="analysis has not finished; no remediation plan exists yet",
        )


def history_out(db: Session, analysis: Analysis) -> AnalysisHistoryOut:
    out = AnalysisHistoryOut.model_validate(analysis)
    out.finding_count = (
        db.scalar(select(func.count(Finding.id)).where(Finding.analysis_id == analysis.id)) or 0
    )
    score = analysis.score_json or {}
    out.overall = score.get("overall")
    out.published = bool(analysis.published)
    return out


def read_snippet(repo_root: Path, path: str, line_start: int, context: int) -> dict:
    """Return a code snippet around a cited line, refusing path escapes."""
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
