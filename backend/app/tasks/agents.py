"""Celery tasks for LLM agents (Phase 4)."""

import logging
import time
from pathlib import Path
from typing import Any

from app.agents import AGENT_CLASSES
from app.agents.base import AgentContext, apply_triage
from app.db import get_session_factory
from app.events import get_bus
from app.llm.client import LLMError, get_llm_client
from app.models import FindingStatus, Severity
from app.services.tools.findings import FindingDraft, persist_findings
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.agents.run_agent",
    soft_time_limit=1800,
    time_limit=1860,
    max_retries=0,
)
def run_agent(agent_name: str, analysis_id: int, repo_root: str) -> dict:
    """Run one agent; persist findings + triage. Never raises (chord robustness)."""
    bus = get_bus()
    started = time.monotonic()
    session = get_session_factory()()
    try:
        try:
            # Validates provider configuration (raises if unmisconfigured).
            get_llm_client()
        except LLMError as exc:
            bus.publish(
                analysis_id,
                "agent",
                {"agent": agent_name, "status": "skipped", "error": str(exc)[:300]},
            )
            return {"ok": False, "agent": agent_name, "error": str(exc)}

        agent = AGENT_CLASSES[agent_name]()
        ctx = AgentContext(analysis_id=analysis_id, repo_root=Path(repo_root), session=session)
        result = agent.run(ctx)

        inserted = persist_findings(session, analysis_id, result.findings)
        dismissed = apply_triage(session, analysis_id, result.triage)
        cost = dict(result.cost)
        cost["dismissed"] = dismissed
        _record_cost(session, analysis_id, cost)

        elapsed = round(time.monotonic() - started, 2)
        status = "error" if result.error else "ok"
        bus.publish(
            analysis_id,
            "agent",
            {
                "agent": agent_name,
                "status": status,
                "findings": inserted,
                "dismissed": dismissed,
                "tokens_in": result.tokens_in,
                "tokens_out": result.tokens_out,
                "model": result.model,
                "seconds": elapsed,
                "error": result.error,
            },
        )
        return {
            "ok": result.error is None,
            "agent": agent_name,
            "findings": inserted,
            "dismissed": dismissed,
        }
    except Exception as exc:  # noqa: BLE001 — report and keep the chord alive
        logger.exception("agent %s failed for analysis %s", agent_name, analysis_id)
        bus.publish(
            analysis_id,
            "agent",
            {"agent": agent_name, "status": "error", "error": str(exc)[:300]},
        )
        try:
            persist_findings(
                session,
                analysis_id,
                [
                    FindingDraft(
                        agent="orchestrator",
                        category="tool-error",
                        severity=Severity.INFO,
                        title=f"Agent '{agent_name}' failed",
                        description=str(exc)[:1000],
                        verifier="tool:orchestrator",
                        status=FindingStatus.VERIFIED,
                    )
                ],
            )
        except Exception:  # noqa: BLE001
            logger.exception("failed to record agent failure")
        return {"ok": False, "agent": agent_name, "error": str(exc)}
    finally:
        session.close()


def _record_cost(session: Any, analysis_id: int, cost: dict) -> None:
    from app.models import Analysis

    analysis = session.get(Analysis, analysis_id)
    if analysis is None:
        return
    ledger = dict(analysis.cost_json or {})
    runs = list(ledger.get("agents", []))
    runs.append(cost)
    ledger["agents"] = runs
    ledger["tokens_in"] = sum(int(r.get("tokens_in", 0) or 0) for r in runs)
    ledger["tokens_out"] = sum(int(r.get("tokens_out", 0) or 0) for r in runs)
    analysis.cost_json = ledger
    session.commit()
