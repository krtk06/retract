"""Celery tasks for individual analysis tools."""

import logging
import time
from pathlib import Path

from celery.exceptions import SoftTimeLimitExceeded

from app.events import get_bus
from app.models import FindingStatus, Severity
from app.services.ingestion import build_inventory
from app.services.tools import TOOL_RUNNERS
from app.services.tools.context import ToolContext
from app.services.tools.findings import FindingDraft, persist_findings
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# The soft limit is raised inside the task and can be caught, so it leaves a grace
# period in which the tool's failure is recorded as a finding and the chord completes.
# The hard limit is the parent's backstop: if the task is still stuck at that point the
# child is SIGKILLed, the chord dependency never returns, and `on_chord_error` fails the
# analysis. The gap between the two is what makes the first path reachable at all.
TOOL_SOFT_TIME_LIMIT = 1200
TOOL_HARD_TIME_LIMIT = 1260


def _describe_failure(tool_name: str, exc: BaseException) -> str:
    """A tool that hit its time limit is a different problem from a tool that crashed.

    The distinction matters to whoever reads the finding: a timeout usually means the
    repository is larger than the budget allows, which is a fact about the input rather
    than a bug in the tool, and it is not fixed by retrying.
    """
    if isinstance(exc, SoftTimeLimitExceeded):
        return (
            f"Tool '{tool_name}' exceeded its {TOOL_SOFT_TIME_LIMIT}s soft time limit and "
            "was stopped. The repository is likely too large for this tool's current "
            "budget; findings from the other tools are unaffected."
        )
    return f"Tool '{tool_name}' failed: {str(exc)[:1000]}"


def _build_context(analysis_id: int, repo_root_path: str) -> ToolContext:
    root = Path(repo_root_path)
    files, _total, _truncated = build_inventory(root)
    loc = sum(f.lines for f in files)
    return ToolContext(analysis_id=analysis_id, repo_root=root, files=files, loc=loc)


@celery_app.task(
    name="app.tasks.tools.run_tool",
    soft_time_limit=TOOL_SOFT_TIME_LIMIT,
    time_limit=TOOL_HARD_TIME_LIMIT,
    max_retries=0,
)
def run_tool(tool_name: str, analysis_id: int, repo_root: str) -> dict:
    """Run one analysis tool; persist findings; never raise (chord robustness).

    The soft limit fires inside this process, so it is catchable here and buys the
    GRACE_PERIOD_SECONDS before the hard limit SIGKILLs the child. The hard limit is
    enforced by billiard in the parent and is NOT catchable here — that case is handled
    by `on_chord_error`, which fails the analysis instead of leaving it running.
    """
    runner = TOOL_RUNNERS[tool_name]
    bus = get_bus()
    started = time.monotonic()
    try:
        ctx = _build_context(analysis_id, repo_root)
        drafts: list[FindingDraft] = runner(ctx)
    except (SoftTimeLimitExceeded, Exception) as exc:  # noqa: BLE001
        # SoftTimeLimitExceeded is listed explicitly because it does not derive from
        # Exception in every celery version, and losing it here would mean the worker
        # is killed with nothing persisted. Everything becomes a finding instead.
        if isinstance(exc, SoftTimeLimitExceeded):
            logger.warning(
                "tool %s exceeded the soft time limit for analysis %s; recording as error",
                tool_name,
                analysis_id,
            )
        else:
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
                        description=_describe_failure(tool_name, exc),
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
