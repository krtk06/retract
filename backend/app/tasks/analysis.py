"""Analysis pipeline task (Phase 1: ingestion only)."""

import logging
from datetime import UTC, datetime

from app.config import get_settings
from app.db import get_session_factory
from app.events import EventBus, get_bus
from app.models import Analysis, AnalysisStatus, Finding, FindingStatus, Severity
from app.services import ingestion
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _finish(
    analysis: Analysis,
    status: AnalysisStatus,
    bus: EventBus,
    error: str | None = None,
) -> None:
    analysis.status = status
    analysis.finished_at = datetime.now(UTC)
    analysis.error = error


@celery_app.task(name="app.tasks.analysis.run_analysis")
def run_analysis(analysis_id: int) -> dict:
    settings = get_settings()
    bus = get_bus()
    session = get_session_factory()()

    try:
        analysis = session.get(Analysis, analysis_id)
        if analysis is None:
            logger.error("analysis %s not found", analysis_id)
            return {"ok": False, "error": "analysis not found"}
        repo = analysis.repository

        analysis.status = AnalysisStatus.RUNNING
        analysis.started_at = datetime.now(UTC)
        session.commit()
        bus.publish(analysis_id, "status", {"status": AnalysisStatus.RUNNING.value})

        dest = settings.data_dir / "repos" / str(repo.id) / str(analysis_id)
        bus.publish(analysis_id, "step", {"step": "clone", "message": f"Cloning {repo.url}"})
        result = ingestion.ingest(repo.url, dest)

        analysis.commit_sha = result.commit_sha
        if repo.default_branch != result.branch:
            repo.default_branch = result.branch

        bus.publish(
            analysis_id,
            "step",
            {"step": "inventory", "message": f"Indexing {result.total_files} files"},
        )
        evidence = {
            "commit_sha": result.commit_sha,
            "branch": result.branch,
            "total_files": result.total_files,
            "truncated": result.truncated,
            "languages": result.languages,
            "files": [{"path": f.path, "size": f.size, "ext": f.ext} for f in result.files],
        }
        top_languages = ", ".join(list(result.languages)[:5]) or "none detected"
        finding = Finding(
            analysis_id=analysis.id,
            agent="ingestion",
            category="inventory",
            severity=Severity.INFO,
            title="Repository ingestion complete",
            description=(
                f"Indexed {result.total_files} files at {result.commit_sha[:8]} "
                f"({result.branch}). Top languages: {top_languages}."
            ),
            evidence_json=evidence,
            verifier="tool:ingestion",
            confidence=1.0,
            status=FindingStatus.VERIFIED,
        )
        session.add(finding)

        _finish(analysis, AnalysisStatus.DONE, bus)
        session.commit()
        bus.publish(
            analysis_id,
            "done",
            {"status": AnalysisStatus.DONE.value, "commit_sha": result.commit_sha},
        )
        return {"ok": True, "commit_sha": result.commit_sha}
    except Exception as exc:  # noqa: BLE001 — record and report, don't crash the worker
        logger.exception("analysis %s failed", analysis_id)
        try:
            analysis = session.get(Analysis, analysis_id)
            if analysis is not None:
                _finish(analysis, AnalysisStatus.FAILED, bus, error=str(exc)[:2000])
                session.commit()
            bus.publish(analysis_id, "failed", {"error": str(exc)[:2000]})
        except Exception:  # noqa: BLE001
            logger.exception("failed to record analysis failure")
        return {"ok": False, "error": str(exc)}
    finally:
        session.close()
