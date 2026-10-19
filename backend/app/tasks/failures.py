"""Failure reporting shared by the analysis orchestrator and the tool tasks.

`fail_stalled_analysis` lives here rather than in `tasks.analysis` so the tool
tasks can call it without importing the orchestrator — the orchestrator imports
them, and a lazy reverse import to break the resulting cycle is still a cycle,
just one the import checker has to be lenient about. One direction, no cycle.
"""

import logging
from datetime import UTC, datetime

from app.db import get_session_factory
from app.events import get_bus
from app.models import Analysis, AnalysisStatus

logger = logging.getLogger(__name__)


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
    except Exception as exc:  # noqa: BLE001
        logger.exception("failed to record failure for analysis %s: %s", analysis_id, exc)
    finally:
        session.close()
    return {"ok": True, "analysis_id": analysis_id, "error": message}
