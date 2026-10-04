"""Scoring curve: honest weighting (D8) and a density measure that does not saturate.

The v2 curve was linear in issue density with a 0.1-KLOC floor, so any repository
under ~230 LOC with a single medium finding clamped to 0 — the score stopped
measuring and started saturating. v3 keeps the same discounting rules (verified
counts fully, hypotheses half, dismissals not at all) and expresses the penalty as
a ratio, so the result degrades smoothly and never hard-clamps.
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from app.analysis_engine.scoring import (
    COUNT_HALF_SCORE_PENALTY,
    HALF_SCORE_DENSITY,
    WORST_PILLAR_HEADROOM,
    _pillar_score,
    _pillar_score_by_count,
    compute_score,
)
from app.db import get_session_factory
from app.models import Analysis, FindingStatus, Repository, Severity, User
from app.services.tools.findings import FindingDraft, persist_findings

# From app.analysis_engine.scoring: severity weights and status factors.
MEDIUM, HIGH, CRITICAL = 10, 20, 30


@pytest.fixture
def make_analysis():
    """Create an analysis with a given LOC so the density term can be controlled."""
    session = get_session_factory()()
    created: list[int] = []
    try:
        user = session.query(User).first()
        if user is None:
            user = User(github_id=None, login="scorefixture")
            session.add(user)
            session.commit()

        def _make(loc: int) -> int:
            suffix = uuid.uuid4().hex[:8]
            repo = Repository(
                owner="fixture",
                name=f"score-{suffix}",
                url=f"local://fixture/score-{suffix}",
                default_branch="main",
                added_by=user.id,
            )
            session.add(repo)
            session.commit()
            analysis = Analysis(repository_id=repo.id, loc=loc)
            session.add(analysis)
            session.commit()
            created.append(analysis.id)
            return analysis.id

        yield _make
    finally:
        session.close()


def add(
    session: Session,
    analysis_id: int,
    severity: Severity,
    count: int = 1,
    status: FindingStatus = FindingStatus.VERIFIED,
    category: str = "vulnerability",
) -> None:
    persist_findings(
        session,
        analysis_id,
        [
            FindingDraft(
                agent="test",
                category=category,
                severity=severity,
                title=f"{category}-{status.value}-{severity.value}-{index}",
                verifier="tool:test",
                status=status,
                confidence=1.0,
            )
            for index in range(count)
        ],
    )


def test_clean_repo_scores_full(make_analysis) -> None:
    session = get_session_factory()()
    try:
        analysis_id = make_analysis(5000)
        score = compute_score(session, analysis_id)
        assert score["overall"] == 100
        assert all(p["score"] == 100 for p in score["pillars"].values())
    finally:
        session.close()


def test_single_finding_in_a_tiny_repo_is_not_floored(make_analysis) -> None:
    """The regression: one medium finding used to clamp a 50-LOC repo to 0.

    The bar here is "informatively bad", not a specific number. v2 produced 0, which
    said nothing about how bad the code was; the calibrated curve produces 48. The
    threshold is deliberately loose so a future retune of ``HALF_SCORE_DENSITY`` does
    not read as a regression.
    """
    session = get_session_factory()()
    try:
        analysis_id = make_analysis(50)
        add(session, analysis_id, Severity.MEDIUM)
        security = compute_score(session, analysis_id)["pillars"]["security"]
        assert security["weighted_penalty"] == float(MEDIUM)
        # Stated as "unhealthy, not dead" rather than a fixed threshold: at the current
        # calibration a 50-line repository with one medium finding is ~13, which is
        # severe but still ordered. What must never happen is a clean 0 or a healthy 100.
        assert security["score"] > 0, "a tiny repo with one medium issue is unhealthy, not dead"
        assert security["score"] < 100
    finally:
        session.close()


def test_score_decreases_monotonically_with_severity(make_analysis) -> None:
    session = get_session_factory()()
    try:
        scores = {}
        for label, severity in (
            ("medium", Severity.MEDIUM),
            ("high", Severity.HIGH),
            ("critical", Severity.CRITICAL),
        ):
            analysis_id = make_analysis(2000)
            add(session, analysis_id, severity)
            scores[label] = compute_score(session, analysis_id)["pillars"]["security"]["score"]
        assert scores["medium"] > scores["high"] > scores["critical"]
    finally:
        session.close()


def test_density_still_penalises_the_same_issues_more_in_a_small_repo(make_analysis) -> None:
    """Identical findings must score worse in less code — that is the point of density."""
    session = get_session_factory()()
    try:
        small, large = make_analysis(200), make_analysis(20000)
        for analysis_id in (small, large):
            add(session, analysis_id, Severity.HIGH, count=5)
        small_score = compute_score(session, small)["pillars"]["security"]["score"]
        large_score = compute_score(session, large)["pillars"]["security"]["score"]
        assert small_score < large_score
    finally:
        session.close()


def test_hypotheses_count_half_and_dismissals_count_nothing(make_analysis) -> None:
    session = get_session_factory()()
    try:
        analysis_id = make_analysis(1000)
        add(session, analysis_id, Severity.HIGH, count=1, status=FindingStatus.VERIFIED)
        verified_score = compute_score(session, analysis_id)["pillars"]["security"]["score"]

        add(session, analysis_id, Severity.HIGH, count=1, status=FindingStatus.HYPOTHESIS)
        with_hypothesis = compute_score(session, analysis_id)["pillars"]["security"]

        dismissed_id = make_analysis(1000)
        add(session, dismissed_id, Severity.HIGH, count=1, status=FindingStatus.VERIFIED)
        add(session, dismissed_id, Severity.HIGH, count=1, status=FindingStatus.DISMISSED)
        with_dismissal = compute_score(session, dismissed_id)["pillars"]["security"]

        assert with_hypothesis["weighted_penalty"] == pytest.approx(HIGH + HIGH * 0.5)
        assert with_hypothesis["verified"] == 1
        assert with_hypothesis["hypotheses"] == 1
        assert with_dismissal["weighted_penalty"] == pytest.approx(float(HIGH))
        assert with_dismissal["score"] == verified_score, "a dismissal must not change the score"
    finally:
        session.close()


def test_halves_at_the_documented_density() -> None:
    """Pins the one calibration constant: the density that scores 50.

    Asserted on the curve rather than through finding counts, because the constant is no
    longer a multiple of the 20-point HIGH weight (30 // 20 == 1), so no whole number of
    HIGH findings lands exactly on it.
    """
    assert _pillar_score(HALF_SCORE_DENSITY, 1.0) == pytest.approx(50, abs=1)
    assert _pillar_score_by_count(COUNT_HALF_SCORE_PENALTY) == pytest.approx(50, abs=1)


def test_never_returns_zero_for_a_non_empty_pillar(make_analysis) -> None:
    """The v2 failure mode: a clamped 0 carries no information about how bad it is."""
    session = get_session_factory()()
    try:
        analysis_id = make_analysis(40)
        add(session, analysis_id, Severity.CRITICAL, count=12)
        security = compute_score(session, analysis_id)["pillars"]["security"]
        assert security["score"] > 0
        assert security["score"] < 25
    finally:
        session.close()


def test_score_payload_documents_its_calibration(make_analysis) -> None:
    session = get_session_factory()()
    try:
        analysis_id = make_analysis(1000)
        score = compute_score(session, analysis_id)
        assert score["version"] == 5
        assert score["basis"] == "density"
        assert score["half_score_density"] == HALF_SCORE_DENSITY
        assert score["worst_pillar_headroom"] == WORST_PILLAR_HEADROOM
        assert set(score["status_factors"]) == {"verified", "hypothesis", "dismissed"}
    finally:
        session.close()


def test_overall_is_capped_by_the_worst_pillar(make_analysis) -> None:
    """One catastrophic pillar must not be averaged away by five healthy ones."""
    session = get_session_factory()()
    try:
        analysis_id = make_analysis(1000)
        # Security is devastated while every other pillar stays at 100. The count is
        # chosen so the bare weighted mean still reads as healthy — that is the whole
        # point: the mean alone would mislead, and the cap is what stops it.
        # 5 HIGH over 1 KLOC: the worst pillar lands in the low twenties, which
        # is still low enough that the bare weighted mean reads as healthy above.
        add(session, analysis_id, Severity.HIGH, count=5)
        score = compute_score(session, analysis_id)
        worst = min(p["score"] for p in score["pillars"].values())
        assert score["pillars"]["security"]["score"] == worst
        assert worst < 25
        assert score["weighted_mean"] > 80, "the bare mean would have looked healthy"
        assert score["overall"] <= worst + WORST_PILLAR_HEADROOM
        assert score["overall"] < 40, "a repo this unsafe must not read as healthy"
    finally:
        session.close()


def test_cap_does_not_bite_when_every_pillar_is_healthy(make_analysis) -> None:
    session = get_session_factory()()
    try:
        analysis_id = make_analysis(10000)
        add(session, analysis_id, Severity.MEDIUM, count=1)
        score = compute_score(session, analysis_id)
        assert min(p["score"] for p in score["pillars"].values()) >= 95
        # The cap is inert only while the mean sits below worst + headroom. Compare
        # the two inputs rather than the rounded outputs, which can differ by a
        # fraction of a point purely from rounding.
        assert score["worst_pillar"] + WORST_PILLAR_HEADROOM > score["weighted_mean"]
        assert score["overall"] >= 95
    finally:
        session.close()


def test_cap_uses_the_lowest_scoring_pillar_not_the_lowest_weight(make_analysis) -> None:
    """Architecture carries the smallest weight but must still be able to cap the score."""
    session = get_session_factory()()
    try:
        analysis_id = make_analysis(1000)
        add(session, analysis_id, Severity.CRITICAL, count=4, category="import-cycle")
        score = compute_score(session, analysis_id)
        assert score["pillars"]["architecture"]["score"] == min(
            p["score"] for p in score["pillars"].values()
        )
        assert score["overall"] <= score["pillars"]["architecture"]["score"] + WORST_PILLAR_HEADROOM
    finally:
        session.close()


# --- no LOC measurement -----------------------------------------------------
#
# The indexer stores loc=0 when it indexes nothing (a repository of one README, or a
# language it does not recognise). The density curve used to divide by a MIN_KLOC
# floor of 0.001, i.e. one line of code, so a repository with two trivial findings
# scored 15/100 while a real 2,565-line repository with 13 findings — 4 of them
# high-severity security hits — scored 88. Both numbers were artefacts of the
# denominator, and the small-repository one was far worse than "unknown": it claimed
# confidence it did not have.


def test_unmeasured_loc_switches_to_the_count_basis(make_analysis) -> None:
    session = get_session_factory()()
    try:
        score = compute_score(session, make_analysis(0))
        assert score["basis"] == "count"
        assert score["kloc"] is None
    finally:
        session.close()


def test_measured_loc_keeps_the_density_basis(make_analysis) -> None:
    session = get_session_factory()()
    try:
        score = compute_score(session, make_analysis(2000))
        assert score["basis"] == "density"
        assert score["kloc"] == 2.0
    finally:
        session.close()


def test_two_trivial_findings_do_not_collapse_a_small_repo(make_analysis) -> None:
    """The regression: 1 HIGH testing + 1 MEDIUM documentation used to score 15."""
    session = get_session_factory()()
    try:
        analysis_id = make_analysis(0)
        persist_findings(
            session,
            analysis_id,
            [
                FindingDraft(
                    agent="tests",
                    category="missing-tests",
                    severity=Severity.HIGH,
                    title="no tests",
                    verifier="tool:tests",
                    status=FindingStatus.VERIFIED,
                ),
                FindingDraft(
                    agent="docs",
                    category="readme",
                    severity=Severity.MEDIUM,
                    title="no readme",
                    verifier="tool:docs",
                    status=FindingStatus.VERIFIED,
                ),
            ],
        )
        score = compute_score(session, analysis_id)
        # 20 weighted points (1 HIGH) against a half-score point of 20 -> 50.
        # 10 points (1 MEDIUM) -> 67. Four pillars are unmeasured, so 100.
        assert score["pillars"]["testing"]["score"] == 50
        assert score["pillars"]["documentation"]["score"] == 67
        # weighted mean 87, but the worst-pillar cap puts it at 50 + 15.
        assert score["overall"] == 65
    finally:
        session.close()


def test_count_basis_is_monotonic_and_bounded(make_analysis) -> None:
    """More weighted points must never raise the score, and it stays in range."""
    session = get_session_factory()()
    try:
        scores = []
        for count in range(0, 12):
            analysis_id = make_analysis(0)
            persist_findings(
                session,
                analysis_id,
                [
                    FindingDraft(
                        agent="code",
                        category="complexity",
                        severity=Severity.MEDIUM,
                        title=f"c{count}-{i}",
                        verifier="tool:complexity",
                        status=FindingStatus.VERIFIED,
                    )
                    for i in range(count)
                ],
            )
            scores.append(compute_score(session, analysis_id)["pillars"]["code-quality"]["score"])
        assert scores == sorted(scores, reverse=True)
        assert all(0 <= s <= 100 for s in scores)
        assert scores[0] == 100
    finally:
        session.close()


def test_bases_agree_on_direction_for_the_same_weighted_penalty(make_analysis) -> None:
    """A count-scored pillar and a density-scored pillar must both fall as points rise,
    so mixing the two bases in one view cannot invert a comparison's direction."""
    session = get_session_factory()()
    try:
        no_loc = make_analysis(0)
        big_loc = make_analysis(1_000_000)
        for analysis_id in (no_loc, big_loc):
            persist_findings(
                session,
                analysis_id,
                [
                    FindingDraft(
                        agent="security",
                        category="secret",
                        severity=Severity.HIGH,
                        title="secret",
                        verifier="tool:semgrep",
                        status=FindingStatus.VERIFIED,
                    )
                ],
            )
        assert (
            compute_score(session, no_loc)["pillars"]["security"]["score"]
            < compute_score(session, big_loc)["pillars"]["security"]["score"]
        )
    finally:
        session.close()
