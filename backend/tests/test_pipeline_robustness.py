"""Regression tests for three defects found by the 27-repository benchmark sweep.

Each test targets a failure that was silent in production: a stalled analysis with no
error, a tool that ran for tens of minutes, and a cycle search whose bound did not
bound anything. The chord test deliberately avoids `task_always_eager`, because eager
mode never enforces time limits and therefore could not have caught the original bug.
"""

import sys
import time
import uuid
from pathlib import Path

import pytest
from celery.exceptions import ChordError, SoftTimeLimitExceeded, TimeLimitExceeded
from sqlalchemy.orm import Session

from app.db import get_session_factory
from app.models import Analysis, AnalysisStatus, Finding, Repository, Severity, User
from app.services.tools import architecture, deps
from app.services.tools.findings import FindingDraft, persist_findings
from app.tasks.analysis import on_chord_error
from app.tasks.tools import (
    TOOL_HARD_TIME_LIMIT,
    TOOL_SOFT_TIME_LIMIT,
    _describe_failure,
    _on_tool_failure,
)

# ---------------------------------------------------------------- chord failure


def _time_limit_einfo() -> object:
    """A celery ExceptionInfo carrying the exception a killed task would report.

    Built by raising and catching for real rather than fabricating a traceback object,
    because the handler only reads `exc_type` off it.
    """
    from celery.app.task import ExceptionInfo

    try:
        raise TimeLimitExceeded(1260)
    except TimeLimitExceeded:
        return ExceptionInfo(sys.exc_info())


def _make_running_analysis(session: Session) -> Analysis:
    user = session.query(User).first()
    if user is None:
        user = User(github_id=None, login=f"robust{uuid.uuid4().hex[:8]}")
        session.add(user)
        session.commit()
        session.refresh(user)
    repo = Repository(
        owner="o",
        name=f"r{uuid.uuid4().hex[:8]}",
        url=f"https://github.com/o/r{uuid.uuid4().hex[:8]}",
        added_by=user.id,
    )
    session.add(repo)
    session.commit()
    session.refresh(repo)
    analysis = Analysis(repository_id=repo.id, status=AnalysisStatus.RUNNING)
    session.add(analysis)
    session.commit()
    session.refresh(analysis)
    return analysis


def test_chord_error_marks_analysis_failed() -> None:
    """A failed fan-out must not leave the analysis stuck at `running`.

    This is the regression that matters. When a tool is killed by Celery's hard time
    limit the chord raises instead of returning, `finalize_analysis` is never called,
    and before this fix the row kept `status=running` forever: no score, no error, and
    nothing in the dashboard to explain why.
    """
    session = get_session_factory()()
    try:
        analysis = _make_running_analysis(session)
        analysis_id = analysis.id

        on_chord_error(ChordError("TimeLimitExceeded(1260)"), analysis_id)

        session.expire_all()
        failed = session.get(Analysis, analysis_id)
        assert failed is not None
        assert failed.status == AnalysisStatus.FAILED, "analysis left running after a chord error"
        assert failed.finished_at is not None, "a failed analysis must record when it finished"
        assert failed.error is not None
        assert "did not complete" in failed.error
    finally:
        session.close()


def test_chord_error_does_not_overwrite_a_finished_analysis() -> None:
    """A late error callback must not clobber a score that already landed.

    The callback can fire after `finalize_analysis` succeeded, since Celery does not
    guarantee ordering between a chord body and its error handler. Overwriting `done`
    with `failed` would turn a completed analysis into a false failure in the report.
    """
    session = get_session_factory()()
    try:
        analysis = _make_running_analysis(session)
        session.get(Analysis, analysis.id).status = AnalysisStatus.DONE
        session.get(Analysis, analysis.id).score_json = {"overall": 88}
        session.commit()

        on_chord_error(ChordError("late failure"), analysis.id)

        session.expire_all()
        done = session.get(Analysis, analysis.id)
        assert done is not None
        assert done.status == AnalysisStatus.DONE
        assert done.score_json == {"overall": 88}
    finally:
        session.close()


def test_killed_tool_fails_the_analysis() -> None:
    """The regression for the bug that survived one round of fixes.

    A tool SIGKILLed by the hard time limit never returns, so the chord body never runs.
    Linking an errback on the chord does not help: it attaches to the *body*, and the
    body is exactly what never executes. Verified against a real 1260s timeout on
    psf/black, where the chord logged ChordError and the analysis stayed at `running`
    with nothing recorded.

    The task-level error handler runs in the pool parent, which survives the kill, so
    this is the only place that can still fail the analysis.
    """
    session = get_session_factory()()
    try:
        analysis = _make_running_analysis(session)
        analysis_id = analysis.id

        einfo = _time_limit_einfo()
        _on_tool_failure(
            "task-abc",
            ("complexity", analysis_id, "/data/repos/1/2"),
            {},
            einfo,
        )

        session.expire_all()
        failed = session.get(Analysis, analysis_id)
        assert failed is not None
        assert failed.status == AnalysisStatus.FAILED
        assert failed.error is not None
        assert "complexity" in failed.error
        assert "hard time limit" in failed.error
    finally:
        session.close()


def test_killed_tool_handler_ignores_an_unidentifiable_failure() -> None:
    """No analysis id means there is nothing safe to fail, so it must not guess."""
    # Must not raise even though it cannot resolve an analysis.
    einfo = _time_limit_einfo()
    _on_tool_failure("task-abc", ("complexity",), {}, einfo)


def test_killed_tool_handler_leaves_a_finished_analysis_alone() -> None:
    session = get_session_factory()()
    try:
        analysis = _make_running_analysis(session)
        session.get(Analysis, analysis.id).status = AnalysisStatus.DONE
        session.get(Analysis, analysis.id).score_json = {"overall": 71}
        session.commit()

        einfo = _time_limit_einfo()
        _on_tool_failure("t", ("semgrep", analysis.id, "/x"), {}, einfo)

        session.expire_all()
        done = session.get(Analysis, analysis.id)
        assert done is not None
        assert done.status == AnalysisStatus.DONE
        assert done.score_json == {"overall": 71}
    finally:
        session.close()


def test_reaper_fails_a_stranded_analysis() -> None:
    """The watchdog is the actual guarantee; the errbacks are only an optimisation.

    Everything that can strand a row — a SIGKILLed tool, a crashed worker, a host
    reboot, a `docker compose down` mid-run — was observed during the sweep, and none of
    them reliably deliver a callback. The reaper only needs to observe that the row is
    old, which survives all of them.
    """
    from datetime import UTC, datetime, timedelta

    from app.tasks.analysis import reap_stalled_analyses

    session = get_session_factory()()
    try:
        analysis = _make_running_analysis(session)
        started = datetime.now(UTC) - timedelta(hours=3)
        session.get(Analysis, analysis.id).started_at = started
        session.commit()

        result = reap_stalled_analyses()

        session.expire_all()
        reaped = session.get(Analysis, analysis.id)
        assert reaped is not None
        assert analysis.id in result["reaped"]
        assert reaped.status == AnalysisStatus.FAILED
        assert reaped.error is not None
        assert "did not finish" in reaped.error
    finally:
        session.close()


def test_reaper_leaves_a_recent_analysis_alone() -> None:
    """A slow repository is not a stall, and must not be killed mid-run."""
    from app.tasks.analysis import reap_stalled_analyses

    session = get_session_factory()()
    try:
        analysis = _make_running_analysis(session)
        result = reap_stalled_analyses()
        session.expire_all()
        still = session.get(Analysis, analysis.id)
        assert analysis.id not in result["reaped"]
        assert still is not None
        assert still.status == AnalysisStatus.RUNNING
    finally:
        session.close()


def test_reaper_interval_is_scheduled() -> None:
    """Beat must actually be pointed at the reaper, or it never runs."""
    from app.tasks.celery_app import celery_app

    schedule = celery_app.conf.beat_schedule
    assert "reap-stalled-analyses" in schedule
    entry = schedule["reap-stalled-analyses"]
    assert entry["task"] == "app.tasks.analysis.reap_stalled_analyses"
    assert entry["schedule"] > 0


def test_reap_interval_matches_the_constant_the_task_documents() -> None:
    from app.tasks.analysis import REAP_INTERVAL_SECONDS as from_task
    from app.tasks.celery_app import REAP_INTERVAL_SECONDS as from_config

    assert from_task == from_config


def test_chord_error_handles_missing_analysis() -> None:
    """The failure reporter must never raise, even for an analysis that no longer exists."""
    result = on_chord_error(ChordError("boom"), 999_999)
    # No row to update is a legitimate outcome, reported rather than raised.
    assert result["ok"] is False
    assert result["error"] == "analysis not found"


def test_chord_error_survives_an_exception_with_no_message() -> None:
    session = get_session_factory()()
    try:
        analysis = _make_running_analysis(session)
        on_chord_error(ChordError(), analysis.id)
        session.expire_all()
        failed = session.get(Analysis, analysis.id)
        assert failed is not None
        assert failed.status == AnalysisStatus.FAILED
    finally:
        session.close()


def test_soft_time_limit_is_gracefully_described() -> None:
    """A timed-out tool must be recorded, and reported as a timeout rather than a crash.

    The distinction is not cosmetic: a timeout means the repository outgrew the budget,
    while an exception means the tool is broken. They call for different responses.
    """
    description = _describe_failure("semgrep", SoftTimeLimitExceeded())
    assert str(TOOL_SOFT_TIME_LIMIT) in description
    assert "soft time limit" in description
    assert "not fixed by retrying" not in description

    crash = _describe_failure("semgrep", ValueError("bad parse"))
    assert "ValueError" not in crash  # the helper writes its own sentence
    assert "bad parse" in crash


def test_hard_time_limit_leaves_room_after_the_soft_limit() -> None:
    """The soft limit is only useful because the hard limit does not arrive instantly.

    If these were equal the task would be SIGKILLed at the same moment the soft limit
    fired, leaving no window to persist the error finding, and the whole point of
    catching `SoftTimeLimitExceeded` would be lost.
    """
    assert TOOL_HARD_TIME_LIMIT > TOOL_SOFT_TIME_LIMIT


def test_tool_error_finding_is_persisted_for_a_timed_out_tool(tmp_path: Path) -> None:
    """Simulate the graceful path end to end: a tool that times out still records itself."""
    session = get_session_factory()()
    try:
        analysis = _make_running_analysis(session)
        drafts = [
            FindingDraft(
                agent="orchestrator",
                category="tool-error",
                severity=Severity.INFO,
                title="Tool 'semgrep' failed",
                description=_describe_failure("semgrep", SoftTimeLimitExceeded()),
                verifier="tool:orchestrator",
            )
        ]
        persist_findings(session, analysis.id, drafts)
        session.commit()

        rows = session.query(Finding).filter(Finding.analysis_id == analysis.id).all()
        assert len(rows) == 1
        assert rows[0].category == "tool-error"
        assert "soft time limit" in rows[0].description
    finally:
        session.close()


# ------------------------------------------------------- registry lookup budget


def test_registry_lookups_run_within_the_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    """A registry that never answers must cost the budget, not 60x the per-request timeout.

    Before the fix each dependency was fetched serially with a 20s timeout, so an
    unreachable registry cost 20s multiplied by the number of pinned dependencies. This
    asserts the wall-clock bound holds and that the shortfall is reported rather than
    silently swallowed.
    """
    calls: list[str] = []

    def _hang(client, dep: deps.Dep) -> str | None:
        calls.append(dep.name)
        time.sleep(30)
        return None

    monkeypatch.setattr(deps, "_latest_version", _hang)
    monkeypatch.setattr(deps, "REGISTRY_DEADLINE_SECONDS", 1.0)

    pinned = [deps.Dep(f"pkg{i}", "1.0.0", "PyPI", "requirements.txt") for i in range(30)]
    started = time.monotonic()
    drafts = deps._outdated(pinned)
    elapsed = time.monotonic() - started

    assert elapsed < 10, f"registry budget ignored: took {elapsed:.1f}s"
    incomplete = [d for d in drafts if d.category == "registry-lookup-incomplete"]
    assert len(incomplete) == 1, "a truncated lookup must say so"
    assert incomplete[0].severity == Severity.INFO
    assert incomplete[0].evidence_json["checked"] == 30
    assert incomplete[0].evidence_json["skipped"] == 30
    assert "not evidence" in incomplete[0].description


def test_outdated_reports_real_lag(monkeypatch: pytest.MonkeyPatch) -> None:
    """The parallel path still produces the finding it used to."""
    latest = {"old-pkg": "2.0.0", "new-pkg": "1.0.0"}
    monkeypatch.setattr(deps, "_latest_version", lambda client, dep: latest.get(dep.name))

    drafts = deps._outdated(
        [
            deps.Dep("old-pkg", "1.0.0", "PyPI", "requirements.txt", 3),
            deps.Dep("new-pkg", "1.0.0", "PyPI", "requirements.txt", 4),
        ]
    )

    outdated = [d for d in drafts if d.category == "outdated-dependency"]
    assert len(outdated) == 1
    assert "old-pkg" in outdated[0].title
    assert outdated[0].evidence_json["latest"] == "2.0.0"
    assert outdated[0].line_start == 3
    assert not [d for d in drafts if d.category == "registry-lookup-incomplete"]


def test_unpinned_and_duplicate_dependencies_are_handled(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unpinned dependency is skipped, and one pinned twice is looked up once."""
    seen: list[str] = []

    def _count(client, dep: deps.Dep) -> str | None:
        seen.append(dep.name)
        return "3.0.0"

    monkeypatch.setattr(deps, "_latest_version", _count)

    drafts = deps._outdated(
        [
            deps.Dep("dup", "1.0.0", "PyPI", "requirements.txt", 1),
            deps.Dep("dup", "1.0.0", "PyPI", "pyproject.toml", 9),
            deps.Dep("floored", "", "PyPI", "requirements.txt", 5),
        ]
    )

    assert seen.count("dup") == 1, "the same package pinned twice must be fetched once"
    assert "floored" not in seen
    outdated = [d for d in drafts if d.category == "outdated-dependency"]
    assert len(outdated) == 1
    assert outdated[0].file_path == "requirements.txt"


def test_outdated_returns_nothing_when_there_is_nothing_pinned() -> None:
    assert deps._outdated([deps.Dep("x", "", "PyPI", "requirements.txt")]) == []


# ---------------------------------------------------------- cycle-search bounds


class _FakeSymbol:
    """Minimal stand-in for a Symbol row; _cycles only reads id, name and location."""

    def __init__(self, symbol_id: int, name: str) -> None:
        self.id = symbol_id
        self.name = name
        self.file_path = f"{name}.py"
        self.line_start = 1


def test_cycle_search_is_bounded_on_an_acyclic_graph() -> None:
    """The regression: a bound on "cycles found" does not bound work on a graph with none.

    The original loop restarted a DFS from every module and only stopped once
    `MAX_CYCLES_REPORTED * 2` cycles existed. On a large acyclic graph that number is
    never reached, so the search ran to exhaustion. This asserts the step budget ends
    it, which is what stopped `architecture` timing out on the biggest repositories.
    """
    nodes = 400
    # A wide DAG: every node points at several later nodes, so the number of distinct
    # paths grows combinatorially while no cycle exists anywhere.
    imports_out: dict[int, set[int]] = {}
    for i in range(nodes):
        imports_out[i] = {j for j in range(i + 1, min(i + 6, nodes))}
    by_id = {i: _FakeSymbol(i, f"m{i}") for i in range(nodes)}

    started = time.monotonic()
    drafts = architecture._cycles(imports_out, by_id)
    elapsed = time.monotonic() - started

    assert drafts == [], "an acyclic graph must report no cycles"
    assert elapsed < 5, f"cycle search is unbounded on an acyclic graph: {elapsed:.1f}s"


def test_cycle_search_still_finds_a_real_cycle() -> None:
    """The bound must not cost correctness on the case that matters."""
    imports_out = {1: {2}, 2: {3}, 3: {1}}
    by_id = {1: _FakeSymbol(1, "a"), 2: _FakeSymbol(2, "b"), 3: _FakeSymbol(3, "c")}

    drafts = architecture._cycles(imports_out, by_id)

    assert len(drafts) == 1
    assert drafts[0].category == "import-cycle"
    assert drafts[0].severity == Severity.MEDIUM
    assert "a" in drafts[0].description


def test_cycle_search_handles_an_empty_graph() -> None:
    assert architecture._cycles({}, {}) == []
