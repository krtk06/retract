"""Analysis orchestrator: ingestion → symbol index → parallel tools → verify/score.

The LLM agent layer is provided by the eve agent (``agent/`` in this repo), not by
Celery: agents call the deterministic tools and graph through the API, and post
findings as hypotheses for the trust layer to verify.
"""

import logging
from datetime import UTC, datetime

from celery import chord, group

from app.config import get_settings
from app.db import get_session_factory
from app.events import get_bus
from app.models import Analysis, AnalysisStatus, Severity
from app.services import indexer, ingestion
from app.services.tools import TOOL_RUNNERS
from app.services.tools.findings import FindingDraft, persist_findings
from app.tasks.celery_app import celery_app
from app.tasks.tools import run_tool

logger = logging.getLogger(__name__)


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
        analysis.loc = result.total_loc
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
            "total_loc": result.total_loc,
            "truncated": result.truncated,
            "languages": result.languages,
            "files": [
                {"path": f.path, "size": f.size, "ext": f.ext, "lines": f.lines}
                for f in result.files
            ],
        }
        top_languages = ", ".join(list(result.languages)[:5]) or "none detected"
        persist_findings(
            session,
            analysis_id,
            [
                FindingDraft(
                    agent="ingestion",
                    category="inventory",
                    severity=Severity.INFO,
                    title="Repository ingestion complete",
                    description=(
                        f"Indexed {result.total_files} files ({result.total_loc} LOC) at "
                        f"{result.commit_sha[:8]} ({result.branch}). "
                        f"Top languages: {top_languages}."
                    ),
                    evidence_json=evidence,
                    verifier="tool:ingestion",
                )
            ],
        )

        bus.publish(analysis_id, "step", {"step": "index", "message": "Building symbol index"})
        symbol_count = indexer.persist_index(
            session, analysis_id, dest, [f.path for f in result.files]
        )
        bus.publish(
            analysis_id, "step", {"step": "index", "message": f"Indexed {symbol_count} symbols"}
        )

        # Deterministic tools in parallel, then verify + score.
        # The eve agent (agent/ in this repo) runs afterwards against this analysis.
        header = group(run_tool.s(name, analysis_id, str(dest)) for name in TOOL_RUNNERS)
        chord(header)(finalize_analysis.s(analysis_id))
        return {"ok": True, "dispatched": list(TOOL_RUNNERS)}
    except Exception as exc:  # noqa: BLE001 — record and report, don't crash the worker
        logger.exception("analysis %s failed", analysis_id)
        try:
            analysis = session.get(Analysis, analysis_id)
            if analysis is not None:
                analysis.status = AnalysisStatus.FAILED
                analysis.finished_at = datetime.now(UTC)
                analysis.error = str(exc)[:2000]
                session.commit()
            bus.publish(analysis_id, "failed", {"error": str(exc)[:2000]})
        except Exception:  # noqa: BLE001
            logger.exception("failed to record analysis failure")
        return {"ok": False, "error": str(exc)}
    finally:
        session.close()


@celery_app.task(name="app.tasks.analysis.finalize_analysis")
def finalize_analysis(_results: list, analysis_id: int) -> dict:
    """Verify LLM findings, calibrate confidence, then compute the honest score."""
    from app.analysis_engine import approvals, verify
    from app.analysis_engine import calibration as calibration_mod
    from app.analysis_engine.scoring import compute_score

    bus = get_bus()
    session = get_session_factory()()
    try:
        analysis = session.get(Analysis, analysis_id)
        if analysis is None:
            return {"ok": False, "error": "analysis not found"}
        repo = analysis.repository

        # Trust layer: verify hypotheses with deterministic checks (D2),
        # then calibrate confidence (D5).
        settings = get_settings()
        repo_root = settings.data_dir / "repos" / str(repo.id) / str(analysis_id)
        try:
            verification = verify.verify_analysis(session, analysis_id, repo_root)
            bus.publish(
                analysis_id,
                "step",
                {
                    "step": "verify",
                    "message": (
                        f"Verified {verification.promoted}/{verification.checked} "
                        f"hypotheses ({verification.failed} unverified)"
                    ),
                },
            )
        except Exception:  # noqa: BLE001 — verification failure must not block scoring
            logger.exception("verification failed for analysis %s", analysis_id)

        try:
            updated = calibration_mod.recalibrate_analysis(session, analysis_id)
            bus.publish(
                analysis_id,
                "step",
                {"step": "calibrate", "message": f"Calibrated {updated} findings"},
            )
        except Exception:  # noqa: BLE001
            logger.exception("calibration failed for analysis %s", analysis_id)

        score = compute_score(session, analysis_id)
        analysis.score_json = score
        analysis.status = AnalysisStatus.DONE
        analysis.finished_at = datetime.now(UTC)

        # Publish gate: high-severity hypotheses require human approval (D5).
        pending = approvals.pending_findings(session, analysis_id)
        analysis.published = not pending
        session.commit()

        bus.publish(
            analysis_id,
            "done",
            {
                "status": AnalysisStatus.DONE.value,
                "overall": score["overall"],
                "published": analysis.published,
                "pending_approvals": len(pending),
            },
        )
        return {"ok": True, "overall": score["overall"], "pending_approvals": len(pending)}
    except Exception as exc:  # noqa: BLE001
        logger.exception("finalize failed for analysis %s", analysis_id)
        analysis = session.get(Analysis, analysis_id)
        if analysis is not None:
            analysis.status = AnalysisStatus.FAILED
            analysis.error = str(exc)[:2000]
            session.commit()
        bus.publish(analysis_id, "failed", {"error": str(exc)[:2000]})
        return {"ok": False, "error": str(exc)}
    finally:
        session.close()
