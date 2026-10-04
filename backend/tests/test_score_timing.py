"""A running analysis must never be scored.

Findings land progressively, so scoring mid-run counts only what exists at that
moment. For an analysis whose analyzers had not yet reported, that is zero
findings — every pillar 100 and an overall of a confident-looking 100, which was
then persisted and cached by the client. The page went on displaying that 100 next
to a finished analysis that had actually scored 88, because nothing invalidated
the score query when the run completed.
"""

from fastapi.testclient import TestClient

from app.db import get_session_factory
from app.models import Analysis, AnalysisStatus


def _create(status: AnalysisStatus) -> int:
    session = get_session_factory()()
    try:
        analysis = Analysis(repository_id=1, commit_sha="deadbeef", status=status)
        session.add(analysis)
        session.commit()
        return analysis.id
    finally:
        session.close()


def _score_json(analysis_id: int) -> dict | None:
    session = get_session_factory()()
    try:
        return session.get(Analysis, analysis_id).score_json
    finally:
        session.close()


def test_running_analysis_is_not_scored(auth_client: TestClient) -> None:
    analysis_id = _create(AnalysisStatus.RUNNING)
    response = auth_client.get(f"/api/analyses/{analysis_id}/score")
    assert response.status_code == 409
    assert "not finished" in response.json()["detail"]


def test_pending_analysis_is_not_scored(auth_client: TestClient) -> None:
    analysis_id = _create(AnalysisStatus.PENDING)
    assert auth_client.get(f"/api/analyses/{analysis_id}/score").status_code == 409


def test_scoring_a_running_analysis_persists_nothing(auth_client: TestClient) -> None:
    """The regression itself: the 100 used to be written to the row and outlive the run."""
    analysis_id = _create(AnalysisStatus.RUNNING)
    auth_client.get(f"/api/analyses/{analysis_id}/score")
    assert _score_json(analysis_id) is None


def test_finished_analysis_without_a_score_is_scored(auth_client: TestClient) -> None:
    """A done analysis with no cached score is still recoverable — the endpoint exists
    for exactly that case, per the note in AnalysisDetailPage."""
    analysis_id = _create(AnalysisStatus.DONE)
    response = auth_client.get(f"/api/analyses/{analysis_id}/score")
    assert response.status_code == 200
    assert response.json()["overall"] == 100  # no findings, nothing measured
    assert _score_json(analysis_id) is not None


def test_cached_score_is_returned_for_an_unfinished_analysis(auth_client: TestClient) -> None:
    """If a score already exists it is returned rather than 409, so a re-run that is
    still in flight keeps showing the previous result instead of erroring."""
    done_id = _create(AnalysisStatus.DONE)
    assert auth_client.get(f"/api/analyses/{done_id}/score").status_code == 200

    session = get_session_factory()()
    try:
        payload = dict(session.get(Analysis, done_id).score_json)
        payload["overall"] = 88
        running = Analysis(repository_id=1, commit_sha="cafe", status=AnalysisStatus.RUNNING)
        running.score_json = payload
        session.add(running)
        session.commit()
        analysis_id = running.id
    finally:
        session.close()

    response = auth_client.get(f"/api/analyses/{analysis_id}/score")
    assert response.status_code == 200
    assert response.json()["overall"] == 88