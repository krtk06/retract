"""Analysis orchestrator: ingestion → indexing → parallel tools → scoring."""

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
from app.tasks.agents import run_agent
from app.tasks.celery_app import celery_app
from app.tasks.embeddings import embed_analysis
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

        # Stage 1: deterministic tools + embedding index in parallel.
        # Stage 2 (dispatch_agents): LLM agents, then finalize scores.
        tool_jobs = [run_tool.s(name, analysis_id, str(dest)) for name in TOOL_RUNNERS]
        tool_jobs.append(embed_analysis.s(analysis_id, str(dest)))
        header = group(tool_jobs)
        chord(header)(dispatch_agents.s(analysis_id, str(dest)))
        return {"ok": True, "dispatched": [*TOOL_RUNNERS, "embeddings"]}
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


@celery_app.task(name="app.tasks.analysis.dispatch_agents")
def dispatch_agents(_results: list, analysis_id: int, repo_root: str) -> dict:
    """Stage 2: run LLM agents in parallel, then finalize the score."""
    from app.agents import AGENT_CLASSES

    bus = get_bus()
    try:
        bus.publish(
            analysis_id,
            "step",
            {"step": "agents", "message": f"Dispatching {len(AGENT_CLASSES)} agents"},
        )
    except Exception:  # noqa: BLE001
        logger.exception("failed to publish agent dispatch event")

    agent_jobs = [run_agent.s(name, analysis_id, repo_root) for name in AGENT_CLASSES]
    chord(group(agent_jobs))(finalize_analysis.s(analysis_id))
    return {"ok": True, "agents": list(AGENT_CLASSES)}


@celery_app.task(name="app.tasks.analysis.finalize_analysis")
def finalize_analysis(_results: list, analysis_id: int) -> dict:
    """Compute the health score and mark the analysis done."""
    from app.analysis_engine.scoring import compute_score

    bus = get_bus()
    session = get_session_factory()()
    try:
        analysis = session.get(Analysis, analysis_id)
        if analysis is None:
            return {"ok": False, "error": "analysis not found"}
        score = compute_score(session, analysis_id)
        analysis.score_json = score
        analysis.status = AnalysisStatus.DONE
        analysis.finished_at = datetime.now(UTC)
        session.commit()
        bus.publish(
            analysis_id,
            "done",
            {"status": AnalysisStatus.DONE.value, "overall": score["overall"]},
        )
        return {"ok": True, "overall": score["overall"]}
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
