"""Celery tasks for individual analysis tools."""

import logging
import time
from pathlib import Path

from app.events import get_bus
from app.models import FindingStatus, Severity
from app.services.ingestion import build_inventory
from app.services.tools import TOOL_RUNNERS
from app.services.tools.context import ToolContext
from app.services.tools.findings import FindingDraft, persist_findings
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _build_context(analysis_id: int, repo_root_path: str) -> ToolContext:
    root = Path(repo_root_path)
    files, _total, _truncated = build_inventory(root)
    loc = sum(f.lines for f in files)
    return ToolContext(analysis_id=analysis_id, repo_root=root, files=files, loc=loc)


@celery_app.task(
    name="app.tasks.tools.run_tool",
    soft_time_limit=1200,
    time_limit=1260,
    max_retries=0,
)
def run_tool(tool_name: str, analysis_id: int, repo_root: str) -> dict:
    """Run one analysis tool; persist findings; never raise (chord robustness)."""
    runner = TOOL_RUNNERS[tool_name]
    bus = get_bus()
    started = time.monotonic()
    try:
        ctx = _build_context(analysis_id, repo_root)
        drafts: list[FindingDraft] = runner(ctx)
    except Exception as exc:  # noqa: BLE001 — report as finding, keep chord alive
        logger.exception("tool %s failed for analysis %s", tool_name, analysis_id)
        elapsed = round(time.monotonic() - started, 2)
        bus.publish(
            analysis_id,
            "tool",
            {"tool": tool_name, "status": "error", "error": str(exc)[:300], "seconds": elapsed},
        )
        session = None
        try:
            from app.db import get_session_factory

            session = get_session_factory()()
            persist_findings(
                session,
                analysis_id,
                [
                    FindingDraft(
                        agent="orchestrator",
                        category="tool-error",
                        severity=Severity.INFO,
                        title=f"Tool '{tool_name}' failed",
                        description=str(exc)[:1000],
                        verifier="tool:orchestrator",
                        status=FindingStatus.VERIFIED,
                    )
                ],
            )
        finally:
            if session is not None:
                session.close()
        return {"ok": False, "tool": tool_name, "error": str(exc)[:300]}

    elapsed = round(time.monotonic() - started, 2)
    session = None
    try:
        from app.db import get_session_factory

        session = get_session_factory()()
        inserted = persist_findings(session, analysis_id, drafts)
    finally:
        if session is not None:
            session.close()
    bus.publish(
        analysis_id,
        "tool",
        {"tool": tool_name, "status": "ok", "findings": inserted, "seconds": elapsed},
    )
    return {"ok": True, "tool": tool_name, "findings": inserted}
