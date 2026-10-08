"""Analysis orchestrator: ingestion → symbol index → parallel tools → verify/score.

The LLM agent layer is provided by the eve agent (``agent/`` in this repo), not by
Celery: agents call the deterministic tools and graph through the API, and post
findings as hypotheses for the trust layer to verify.
"""

import logging
from datetime import UTC, datetime, timedelta

from celery import chord, group
from sqlalchemy import select

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

# Generous on purpose. The slowest legitimate run observed was sqlalchemy at ~24min on a
# 644k-LOC repository, and a tool that hits its 1260s hard limit still has to unwind, so
# anything under half an hour is a stall rather than a slow repository.
STALLED_AFTER_SECONDS = 3600
REAP_INTERVAL_SECONDS = 300


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
        #
        # on_error is not optional. run_tool catches its own exceptions so a single
        # failing tool cannot break the chord, but a hard `time_limit` is enforced by
        # billiard in the pool *parent*, which SIGKILLs the child. That exception never
        # reaches run_tool's except clause, so the chord dependency simply never
        # returns, `finalize_analysis` is never called, and the analysis is stranded at
        # `running` with no score and no error. The callback is what turns that silence
        # into a recorded failure.
        header = group(run_tool.s(name, analysis_id, str(dest)) for name in TOOL_RUNNERS)
        # The errback must be linked on the chord's *signature* before it is applied.
        # Calling the chord returns an AsyncResult, and AsyncResult has no on_error:
        # attaching it there silently does nothing, which is how this strand bug survived
        # one round of fixes. The body has to be passed to the chord constructor for the
        # same reason — on_error links through self.body.
        signature = chord(header, finalize_analysis.s(analysis_id))
        signature.on_error(on_chord_error.s(analysis_id))
        signature.apply_async()
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


def fail_stalled_analysis(analysis_id: int, message: str) -> dict:
    """Mark an analysis `failed` so it cannot sit at `running` with no explanation.

    Called from two places, both of which exist because the failure is otherwise silent:
    `on_chord_error` when the fan-out as a whole fails, and `_on_tool_failure` when a
    single tool is SIGKILLed by the hard time limit. In both cases the analysis cannot be
    scored honestly, because not every tool reported, so `finalize_analysis` is
    deliberately not called even though most findings may already be persisted.

    An analysis that has already finished is left alone: Celery does not order a chord
    body against its error handler, so a late callback must not overwrite a real score.
    """
    try:
        session = get_session_factory()()
    except Exception:  # noqa: BLE001 — never let the failure reporter itself raise
        logger.exception("could not open a session to record the failure")
        return {"ok": False, "analysis_id": analysis_id}

    try:
        analysis = session.get(Analysis, analysis_id)
        if analysis is None:
            return {"ok": False, "analysis_id": analysis_id, "error": "analysis not found"}
        if analysis.status == AnalysisStatus.DONE:
            return {"ok": True, "analysis_id": analysis_id, "error": "already finished"}
        analysis.status = AnalysisStatus.FAILED
        analysis.finished_at = datetime.now(UTC)
        analysis.error = message[:2000]
        session.commit()
        get_bus().publish(analysis_id, "failed", {"error": analysis.error})
    except Exception:  # noqa: BLE001
        logger.exception("failed to record failure for analysis %s", analysis_id)
    finally:
        session.close()
    return {"ok": True, "analysis_id": analysis_id, "error": message}


@celery_app.task(name="app.tasks.analysis.on_chord_error")
def on_chord_error(exc: BaseException, analysis_id: int) -> dict:
    """Record a failed fan-out so the analysis cannot stay `running` forever."""
    logger.error("analysis %s fan-out failed: %r", analysis_id, exc)
    detail = f"{type(exc).__name__}: {exc}" if exc else "unknown chord failure"
    return fail_stalled_analysis(analysis_id, f"analysis tools did not complete ({detail[:500]})")


@celery_app.task(name="app.tasks.analysis.reap_stalled_analyses")
def reap_stalled_analyses(max_age_seconds: int = STALLED_AFTER_SECONDS) -> dict:
    """Fail analyses that have been `running` far longer than any legitimate run.

    This is the guarantee, and the errbacks are only an optimisation.

    A tool killed by the hard time limit, a worker that OOMs, a host reboot, or a
    `docker compose down` mid-run all strand the analysis row: `run_analysis` set it to
    `running`, and the only thing that would move it on is `finalize_analysis` being
    reached through the chord. Every one of those paths was observed during the
    27-repository sweep, and none of them can be relied on to deliver a callback. A
    stale row is worse than a failed one, because it reports nothing at all.

    Keying on `started_at` rather than on any event means it also catches a run whose
    worker vanished entirely, which no in-process handler can observe.
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=max_age_seconds)
    session = get_session_factory()()
    reaped: list[int] = []
    try:
        stalled = session.scalars(
            select(Analysis).where(
                Analysis.status.in_((AnalysisStatus.RUNNING, AnalysisStatus.PENDING)),
                Analysis.started_at.is_not(None),
                Analysis.started_at < cutoff,
            )
        ).all()
        for analysis in stalled:
            started = analysis.started_at.isoformat() if analysis.started_at else "unknown"
            fail_stalled_analysis(
                analysis.id,
                f"analysis did not finish within {max_age_seconds}s (started {started}); "
                "it is being marked failed rather than left running forever",
            )
            reaped.append(analysis.id)
    finally:
        session.close()
    if reaped:
        logger.warning("reaped %d stalled analyses: %s", len(reaped), reaped)
    return {"ok": True, "reaped": reaped}


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
