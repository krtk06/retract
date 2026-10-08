"""Remediation plan: coverage, specificity, grouping, ranking, and honesty of the numbers."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.analysis_engine import remediation
from app.analysis_engine.remediation import (
    CATALOG,
    EFFORT_WEIGHT,
    UNSCORED_CATEGORIES,
    build_plan,
    remediation_for,
    remediation_summary,
    render_markdown,
)
from app.analysis_engine.scoring import CATEGORY_PILLAR, SEVERITY_WEIGHT, aggregate, compute_score
from app.config import get_settings
from app.db import get_session_factory
from app.models import (
    Analysis,
    AnalysisStatus,
    Finding,
    FindingStatus,
    Repository,
    Severity,
    User,
    UserRepository,
)

settings = get_settings()

# Categories the eve agent is allowed to emit (record_finding.ts / instructions.md).
# They are not in CATEGORY_PILLAR, so a test asserting catalog coverage over that
# map alone would miss every one of them.
AGENT_CATEGORIES = {
    "injection",
    "weak-crypto",
    "layering",
    "coupling",
    "test-plan",
    "docstring-plan",
    "readme-plan",
    "code-review",
    "insight",
}


class FakeFinding:
    """A Remediatable that is not an ORM row."""

    def __init__(
        self,
        category: str,
        evidence: dict | None = None,
        title: str = "Some issue",
        file_path: str | None = "app/mod.py",
        line_start: int | None = 10,
    ) -> None:
        self.category = category
        self.evidence_json = evidence
        self.title = title
        self.file_path = file_path
        self.line_start = line_start


@pytest.fixture
def analysis_id() -> int:
    session = get_session_factory()()
    try:
        user = session.query(User).first()
        if user is None:
            user = User(github_id=None, login="remediation")
            session.add(user)
            session.commit()
        suffix = uuid.uuid4().hex[:8]
        repo = Repository(
            owner="fixture",
            name=f"plan-{suffix}",
            url=f"local://fixture/plan-{suffix}",
            default_branch="main",
            added_by=user.id,
        )
        session.add(repo)
        session.commit()
        session.add(UserRepository(repo_id=repo.id, user_id=user.id))
        session.commit()
        analysis = Analysis(repository_id=repo.id, status=AnalysisStatus.DONE, loc=2000)
        session.add(analysis)
        session.commit()
        return analysis.id
    finally:
        session.close()


def _add(
    analysis_id: int,
    category: str,
    severity: Severity = Severity.MEDIUM,
    *,
    title: str | None = None,
    evidence: dict | None = None,
    status: FindingStatus = FindingStatus.VERIFIED,
    file_path: str | None = "app/mod.py",
    line_start: int | None = 10,
) -> int:
    session = get_session_factory()()
    try:
        finding = Finding(
            analysis_id=analysis_id,
            agent="test",
            category=category,
            severity=severity,
            title=title or f"{category} issue",
            description="",
            file_path=file_path,
            line_start=line_start,
            evidence_json=evidence,
            verifier="tool:test",
            confidence=1.0,
            status=status,
        )
        session.add(finding)
        session.commit()
        return finding.id
    finally:
        session.close()


def _set_status(finding_ids: list[int], status: FindingStatus) -> None:
    session = get_session_factory()()
    try:
        for fid in finding_ids:
            row = session.get(Finding, fid)
            assert row is not None
            row.status = status
        session.commit()
    finally:
        session.close()


# --- catalog coverage -------------------------------------------------------


def test_catalog_covers_every_scored_category() -> None:
    """A category with no entry would fall through to generic advice.

    Generic advice is better than nothing, but it loses the specificity the catalog
    exists for, so coverage is asserted rather than assumed.
    """
    missing = {
        category
        for category, pillar in CATEGORY_PILLAR.items()
        if pillar is not None and category not in CATALOG
    }
    assert not missing, f"categories without a remediation entry: {sorted(missing)}"


def test_catalog_covers_every_agent_category() -> None:
    assert not (AGENT_CATEGORIES - set(CATALOG))


def test_every_catalog_entry_produces_usable_advice() -> None:
    for category in CATALOG:
        result = remediation_for(FakeFinding(category))
        assert result.action.strip(), category
        assert len(result.steps) >= 2, category
        assert all(step.strip() for step in result.steps), category
        assert result.effort in EFFORT_WEIGHT, category


def test_unknown_category_falls_back_to_generic_advice() -> None:
    """A future category must still get a fix rather than a blank row."""
    result = remediation_for(FakeFinding("category-from-the-future", title="Odd thing"))
    assert result.steps
    assert "Odd thing" in result.action


def test_malformed_evidence_degrades_instead_of_raising() -> None:
    """Evidence arrives from tool runners; a wrong shape must not blank the plan."""
    for evidence in (None, {}, {"vuln_ids": "not-a-list"}, {"cyclomatic_complexity": "x"}, []):
        result = remediation_for(FakeFinding("vulnerable-dependency", evidence=evidence))
        assert result.steps


def test_unscored_categories_are_excluded_from_the_plan(analysis_id: int) -> None:
    _add(analysis_id, "inventory", Severity.INFO)
    _add(analysis_id, "tool-error", Severity.INFO)
    _add(analysis_id, "secret", Severity.HIGH)
    plan = _plan(analysis_id)
    assert plan.findings_considered == 1
    assert all(item.key != "inventory" for item in plan.work_items)
    assert set(UNSCORED_CATEGORIES) == {"inventory", "tool-error"}


# --- specificity ------------------------------------------------------------


def test_vulnerable_dependency_names_the_cve_and_versions() -> None:
    result = remediation_for(
        FakeFinding(
            "vulnerable-dependency",
            evidence={
                "vuln_ids": ["CVE-2023-30861", "CVE-2024-56201"],
                "package": "flask",
                "version": "1.0.0",
            },
        )
    )
    assert "flask 1.0.0" in result.action
    steps = " ".join(result.steps)
    assert "CVE-2023-30861" in steps
    assert "CVE-2024-56201" in steps


def test_outdated_dependency_names_the_version_span() -> None:
    result = remediation_for(
        FakeFinding("outdated-dependency", evidence={"installed": "2.25.0", "latest": "2.32.3"})
    )
    assert "2.25.0" in " ".join(result.steps)
    assert "2.32.3" in " ".join(result.steps)


def test_complexity_names_the_symbol_and_the_measurement() -> None:
    result = remediation_for(
        FakeFinding("complexity", evidence={"cyclomatic_complexity": 24, "symbol": "parse_config"})
    )
    assert "parse_config" in result.action
    assert "24" in " ".join(result.steps)


def test_duplication_names_both_copies() -> None:
    result = remediation_for(
        FakeFinding("duplication", evidence={"original": "a.py", "duplicate": "b.py"})
    )
    assert "a.py" in " ".join(result.steps)
    assert "b.py" in " ".join(result.steps)


def test_import_cycle_names_the_modules() -> None:
    result = remediation_for(
        FakeFinding("import-cycle", evidence={"cycle": ["app.a", "app.b", "app.c"]})
    )
    assert "app.a" in " ".join(result.steps)


def test_docstring_lists_the_missing_symbols() -> None:
    result = remediation_for(FakeFinding("docstring", evidence={"missing": ["alpha", "beta"]}))
    assert "alpha" in " ".join(result.steps)


def test_advice_cites_the_finding_location() -> None:
    result = remediation_for(FakeFinding("secret", file_path="app/cache.py", line_start=11))
    assert "app/cache.py:11" in " ".join(result.steps)


def test_repository_wide_finding_still_renders() -> None:
    """A finding with no citation must not produce a step that interpolates `None`."""
    result = remediation_for(FakeFinding("insight", file_path=None, line_start=None))
    assert result.steps
    joined = " ".join(result.steps)
    assert "the repository" in joined
    assert "None" not in joined


# --- LLM overrides ----------------------------------------------------------


def test_agent_claim_can_carry_its_own_fix(auth_client: TestClient, analysis_id: int) -> None:
    """An eve claim may bring a fix, which the plan then prefers over the catalog."""
    response = auth_client.post(
        f"/api/analyses/{analysis_id}/findings",
        json={
            "agent": "eve:code",
            "findings": [
                {
                    "claim": "parse_config re-reads the ini on every branch.",
                    "evidence": "app/cfg.py:14 constructs ConfigParser inside the loop.",
                    "file_path": "app/cfg.py",
                    "line_start": 14,
                    "severity": "medium",
                    "confidence": 0.6,
                    "category": "complexity",
                    "recommendation": "Construct ConfigParser once at module scope",
                }
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["inserted"] == 1

    plan = auth_client.get(f"/api/analyses/{analysis_id}/remediation").json()
    assert plan["work_items"][0]["action"] == "Construct ConfigParser once at module scope"
    assert plan["work_items"][0]["source"] == "llm:eve"

    findings = auth_client.get(f"/api/analyses/{analysis_id}/findings").json()
    assert findings[0]["remediation"]["action"] == "Construct ConfigParser once at module scope"


def test_agent_claim_without_a_fix_uses_the_catalog(
    auth_client: TestClient, analysis_id: int
) -> None:
    auth_client.post(
        f"/api/analyses/{analysis_id}/findings",
        json={
            "agent": "eve:security",
            "findings": [
                {
                    "claim": "Literal salt in the cache key.",
                    "evidence": "app/cache.py:11 assigns a string.",
                    "file_path": "app/cache.py",
                    "line_start": 11,
                    "severity": "high",
                    "confidence": 0.7,
                    "category": "secret",
                }
            ],
        },
    )
    plan = auth_client.get(f"/api/analyses/{analysis_id}/remediation").json()
    assert plan["work_items"][0]["action"] == "Rotate the exposed credential"
    assert plan["work_items"][0]["source"] == "catalog"


def test_authored_remediation_overrides_the_catalog() -> None:
    finding = FakeFinding(
        "complexity",
        evidence={
            "cyclomatic_complexity": 24,
            "symbol": "parse_config",
            "remediation": {
                "action": "Hoist the ini lookup out of parse_config",
                "steps": ["Lift the ConfigParser construction to module scope."],
                "effort": "low",
                "source": "llm:eve",
            },
        },
    )
    result = remediation_for(finding)
    assert result.action == "Hoist the ini lookup out of parse_config"
    assert result.steps == ["Lift the ConfigParser construction to module scope."]
    assert remediation_summary(finding)["source"] == "llm:eve"


def test_catalog_advice_is_labelled_as_such() -> None:
    summary = remediation_summary(FakeFinding("secret"))
    assert summary["source"] == "catalog"
    assert summary["effort"] in EFFORT_WEIGHT


def test_malformed_authored_remediation_falls_back() -> None:
    finding = FakeFinding("secret", evidence={"remediation": {"steps": ["no action here"]}})
    result = remediation_for(finding)
    assert result.action != ""
    assert result.steps


# --- grouping and ranking ---------------------------------------------------


def _plan(analysis_id: int) -> remediation.RemediationPlan:
    session = get_session_factory()()
    try:
        return build_plan(session, analysis_id)
    finally:
        session.close()


def test_findings_sharing_a_fix_become_one_work_item(analysis_id: int) -> None:
    for line in (10, 20, 30):
        _add(analysis_id, "secret", Severity.HIGH, line_start=line)
    plan = _plan(analysis_id)
    assert len(plan.work_items) == 1
    assert plan.work_items[0].finding_count == 3
    assert plan.findings_considered == 3


def test_a_category_batches_rather_than_producing_one_card_per_symbol(analysis_id: int) -> None:
    """The catalog names the symbol in its action, which must not become the key.

    On a real repository this is the difference between a readable plan and a wall
    of "break up X" cards: fifty-two complexity findings are one piece of work.
    """
    for n in range(52):
        _add(
            analysis_id,
            "complexity",
            Severity.MEDIUM,
            title=f"High cyclomatic complexity: fn_{n} (CC 12)",
            file_path=f"app/mod_{n}.py",
            line_start=1,
            evidence={"cyclomatic_complexity": 12, "symbol": f"fn_{n}"},
        )
    plan = _plan(analysis_id)
    assert len(plan.work_items) == 1
    assert plan.work_items[0].action == "Reduce complexity in 52 over-complex functions"
    # Every symbol stays reachable, which is what batching must not cost.
    assert plan.work_items[0].finding_count == 52
    assert len(plan.work_items[0].findings) == 52


def test_distinct_fixes_become_distinct_work_items(analysis_id: int) -> None:
    _add(analysis_id, "secret", Severity.HIGH)
    _add(analysis_id, "duplication", Severity.MEDIUM)
    _add(analysis_id, "readme", Severity.LOW)
    plan = _plan(analysis_id)
    assert len(plan.work_items) == 3


def test_findings_in_one_file_group_despite_differing_lines(analysis_id: int) -> None:
    """The catalog writes the citation into the action, which must not fragment groups.

    Two outdated pins in one requirements.txt produce actions differing only by
    line number. Grouping on the raw action string turns one two-minute fix into
    two cards, which is exactly the per-finding noise the plan exists to avoid.
    """
    _add(
        analysis_id,
        "outdated-dependency",
        Severity.LOW,
        file_path="requirements.txt",
        line_start=1,
        evidence={"installed": "2.25.0", "latest": "2.32.3"},
    )
    _add(
        analysis_id,
        "outdated-dependency",
        Severity.LOW,
        file_path="requirements.txt",
        line_start=2,
        evidence={"installed": "3.9.0", "latest": "3.11.0"},
    )
    plan = _plan(analysis_id)
    assert len(plan.work_items) == 1
    assert plan.work_items[0].finding_count == 2
    # The headline describes the batch, and both lines stay reachable underneath —
    # a card titled for one line reads as if the other was overlooked.
    assert plan.work_items[0].action == "Update 2 outdated dependencies"
    assert [f.line_start for f in plan.work_items[0].findings] == [1, 2]


def test_one_finding_keeps_its_specific_action(analysis_id: int) -> None:
    """A lone finding's own action is the most useful thing on its card.

    Batching is for batches; collapsing a single CVE-specific fix into "upgrade 1
    dependency" would throw away the detail the catalog exists to provide.
    """
    _add(
        analysis_id,
        "vulnerable-dependency",
        Severity.HIGH,
        evidence={"vuln_ids": ["CVE-2023-30861"], "package": "flask", "version": "1.0.0"},
    )
    plan = _plan(analysis_id)
    assert plan.work_items[0].action == "Upgrade flask 1.0.0 to a patched release"


def test_different_packages_batch_into_one_card_with_both_listed(analysis_id: int) -> None:
    """Two upgrades are one work item, but neither package may be lost from it."""
    _add(
        analysis_id,
        "vulnerable-dependency",
        Severity.HIGH,
        title="Vulnerable dependency: flask==0.12.2",
        file_path="requirements.txt",
        line_start=1,
        evidence={"vuln_ids": ["CVE-1"], "package": "flask", "version": "0.12.2"},
    )
    _add(
        analysis_id,
        "vulnerable-dependency",
        Severity.HIGH,
        title="Vulnerable dependency: requests==2.6.0",
        file_path="requirements.txt",
        line_start=2,
        evidence={"vuln_ids": ["CVE-2"], "package": "requests", "version": "2.6.0"},
    )
    plan = _plan(analysis_id)
    assert len(plan.work_items) == 1
    item = plan.work_items[0]
    assert item.action == "Upgrade 2 vulnerable dependencies"
    assert {f.title for f in item.findings} == {
        "Vulnerable dependency: flask==0.12.2",
        "Vulnerable dependency: requests==2.6.0",
    }


def test_ranking_is_payoff_per_effort(analysis_id: int) -> None:
    # A high-severity fix that is cheap must outrank a bigger but far costlier one,
    # which is the whole point of ranking on penalty-per-effort rather than size.
    _add(analysis_id, "import-cycle", Severity.HIGH, title="cycle")  # high effort
    for line in (1, 2, 3):
        _add(analysis_id, "secret", Severity.MEDIUM, line_start=line)  # low effort
    plan = _plan(analysis_id)
    payoffs = [item.payoff() for item in plan.work_items]
    assert payoffs == sorted(payoffs, reverse=True)
    assert plan.work_items[0].key == "secret"


def test_work_item_totals_the_additive_penalty(analysis_id: int) -> None:
    ids = [_add(analysis_id, "secret", Severity.HIGH, line_start=n) for n in (1, 2)]
    plan = _plan(analysis_id)
    item = plan.work_items[0]
    expected = sum(SEVERITY_WEIGHT["high"] * 1.0 for _ in ids)
    assert item.weighted_penalty_removed == pytest.approx(expected)


# --- the numbers are honest -------------------------------------------------


def test_projected_overall_matches_a_really_fixed_repository(analysis_id: int) -> None:
    """The header claim is that fixing everything reaches `projected_overall`.

    Verified by doing it rather than by re-deriving it: dismiss the findings, let
    the real scorer run, and compare.
    """
    ids = [
        _add(analysis_id, "secret", Severity.CRITICAL, line_start=1),
        _add(analysis_id, "vulnerability", Severity.HIGH, line_start=2),
        _add(analysis_id, "complexity", Severity.MEDIUM, line_start=3),
        _add(analysis_id, "missing-tests", Severity.MEDIUM, line_start=4),
    ]
    plan = _plan(analysis_id)
    assert plan.projected_overall == 100

    session = get_session_factory()()
    try:
        analysis = session.get(Analysis, analysis_id)
        assert analysis is not None
        analysis.score_json = compute_score(session, analysis_id)
        session.commit()
    finally:
        session.close()

    _set_status(ids, FindingStatus.DISMISSED)

    session = get_session_factory()()
    try:
        assert compute_score(session, analysis_id)["overall"] == plan.projected_overall
    finally:
        session.close()


def test_pillar_points_are_not_summed_into_the_header(analysis_id: int) -> None:
    """Guards the honesty rule: per-item points are never a share of the headline.

    The header reports the score of a clean repository. If the per-item points
    summed to the same number, the nonlinearity would be gone and one of the two
    would be wrong. This asserts they disagree, so a refactor that starts summing
    them fails here instead of shipping a plausible wrong number.
    """
    _add(analysis_id, "secret", Severity.CRITICAL, line_start=1)
    _add(analysis_id, "complexity", Severity.MEDIUM, line_start=2)

    session = get_session_factory()()
    try:
        analysis = session.get(Analysis, analysis_id)
        assert analysis is not None
        analysis.score_json = compute_score(session, analysis_id)
        session.commit()
    finally:
        session.close()

    plan = _plan(analysis_id)
    assert plan.current_overall is not None
    assert plan.recoverable_points == plan.projected_overall - plan.current_overall
    # Two items cannot account for the whole journey: fixing a pillar that is not
    # yet the worst barely moves the capped overall.
    assert sum(item.pillar_points for item in plan.work_items) > plan.recoverable_points


def test_pillar_points_measure_the_pillar_the_work_actually_moves(analysis_id: int) -> None:
    """The per-item number must not read "+0 pts" on the most valuable fix.

    The overall is capped at ``worst_pillar + 15``. On a repository drowning in
    security findings, clearing security moves the overall by nothing while
    code-quality is still the worst pillar — technically true, and useless as the
    headline value of the most important item in the plan. So the item's value is
    measured in its own pillar.
    """
    for line in range(1, 9):
        _add(analysis_id, "secret", Severity.CRITICAL, line_start=line)
    _add(analysis_id, "complexity", Severity.MEDIUM, line_start=20)

    session = get_session_factory()()
    try:
        analysis = session.get(Analysis, analysis_id)
        assert analysis is not None
        analysis.score_json = compute_score(session, analysis_id)
        session.commit()
    finally:
        session.close()

    plan = _plan(analysis_id)
    security = next(item for item in plan.work_items if item.pillar == "security")
    assert security.pillar_points > 0


def test_pillar_points_disappear_once_the_item_is_fixed(analysis_id: int) -> None:
    ids = [_add(analysis_id, "secret", Severity.CRITICAL, line_start=1)]
    _add(analysis_id, "complexity", Severity.MEDIUM, line_start=2)

    session = get_session_factory()()
    try:
        analysis = session.get(Analysis, analysis_id)
        assert analysis is not None
        analysis.score_json = compute_score(session, analysis_id)
        session.commit()
    finally:
        session.close()

    before = {item.key: item.pillar_points for item in _plan(analysis_id).work_items}
    assert before["secret"] > 0

    _set_status(ids, FindingStatus.DISMISSED)
    after = {item.key: item.pillar_points for item in _plan(analysis_id).work_items}
    assert "secret" not in after


def test_dismissed_findings_leave_the_plan(analysis_id: int) -> None:
    keep = _add(analysis_id, "secret", Severity.HIGH, title="keep")
    drop = _add(analysis_id, "duplication", Severity.MEDIUM, title="drop")
    _set_status([drop], FindingStatus.DISMISSED)
    plan = _plan(analysis_id)
    assert plan.findings_considered == 1
    assert [f.id for i in plan.work_items for f in i.findings] == [keep]


def test_hypothesis_backed_items_are_flagged(analysis_id: int) -> None:
    _add(analysis_id, "secret", Severity.HIGH, status=FindingStatus.HYPOTHESIS)
    plan = _plan(analysis_id)
    assert plan.unverified_items == 1


def test_plan_reflects_a_dismissal_immediately(analysis_id: int) -> None:
    """Derived on demand, so it cannot serve a stale plan after a review decision."""
    fid = _add(analysis_id, "secret", Severity.HIGH)
    assert _plan(analysis_id).findings_considered == 1
    _set_status([fid], FindingStatus.DISMISSED)
    assert _plan(analysis_id).findings_considered == 0


def test_plan_does_not_quote_a_stale_cached_score(analysis_id: int) -> None:
    """The before/after must come from one computation, not a score cached earlier.

    A reviewer dismissing a finding changes what counts. If the plan quoted the
    score stored at finalize time it would advertise a journey out of a number the
    findings table no longer supports.
    """
    _add(analysis_id, "secret", Severity.HIGH)
    session = get_session_factory()()
    try:
        analysis = session.get(Analysis, analysis_id)
        assert analysis is not None
        # A cached score from before the findings below were ever recorded.
        analysis.score_json = {"overall": 97, "version": 5}
        session.commit()
    finally:
        session.close()

    plan = _plan(analysis_id)
    live = aggregate(
        session_findings(analysis_id),
        2000,
    )
    assert plan.current_overall == live["overall"]
    assert plan.current_overall != 97


def session_findings(analysis_id: int) -> list:
    session = get_session_factory()()
    try:
        return list(
            session.scalars(select(Finding).where(Finding.analysis_id == analysis_id)).all()
        )
    finally:
        session.close()


def test_advertised_pillar_gain_is_exactly_what_fixing_it_does(
    auth_client: TestClient, analysis_id: int
) -> None:
    """The per-card number must be a measurement, not an estimate.

    Verified by acting on it: dismiss exactly the findings the card names, then read
    the pillar score back. If the two disagree the card is lying about the one thing
    it exists to tell the reader.
    """
    for line in range(1, 5):
        _add(analysis_id, "secret", Severity.HIGH, line_start=line)
    _add(analysis_id, "readme", Severity.LOW)

    plan = auth_client.get(f"/api/analyses/{analysis_id}/remediation").json()
    top = next(i for i in plan["work_items"] if i["pillar"] == "security")
    before = auth_client.get(f"/api/analyses/{analysis_id}/score").json()["pillars"]["security"][
        "score"
    ]

    for finding in top["findings"]:
        auth_client.post(
            f"/api/analyses/{analysis_id}/approvals",
            json={"finding_id": finding["finding_id"], "decision": "dismiss"},
        )

    after = auth_client.get(f"/api/analyses/{analysis_id}/score").json()["pillars"]["security"][
        "score"
    ]
    assert after - before == top["pillar_points"]
    assert top["pillar_points"] > 0


def test_dismissing_a_finding_rescores_the_analysis(
    auth_client: TestClient, analysis_id: int
) -> None:
    """A review decision must move the score, or the dashboard contradicts itself.

    Pre-existing gap: `record_findings` recomputed after intake, but a human
    decision did not, so the hero kept reading the pre-review number next to a
    findings table that had already changed.
    """
    fid = _add(analysis_id, "secret", Severity.CRITICAL)

    before = auth_client.get(f"/api/analyses/{analysis_id}/score").json()
    assert before["overall"] < 100

    response = auth_client.post(
        f"/api/analyses/{analysis_id}/approvals",
        json={"finding_id": fid, "decision": "dismiss", "note": "false positive"},
    )
    assert response.status_code == 200
    assert response.json()["finding_status"] == "dismissed"

    after = auth_client.get(f"/api/analyses/{analysis_id}/score").json()
    assert after["overall"] == 100
    assert after["overall"] > before["overall"]


def test_a_cleaned_up_analysis_agrees_with_its_own_projection(
    auth_client: TestClient, analysis_id: int
) -> None:
    """The live end-to-end claim: fix everything, and the advertised number happens.

    Asserted by doing it through the product's own review endpoint and then reading
    the real score back, rather than by re-deriving the projection.
    """
    ids = [
        _add(analysis_id, "secret", Severity.CRITICAL, line_start=1),
        _add(analysis_id, "vulnerability", Severity.HIGH, line_start=2),
        _add(analysis_id, "complexity", Severity.MEDIUM, line_start=3),
        _add(analysis_id, "readme", Severity.LOW, line_start=4),
    ]
    plan = auth_client.get(f"/api/analyses/{analysis_id}/remediation").json()
    assert plan["projected_overall"] == 100

    for fid in ids:
        auth_client.post(
            f"/api/analyses/{analysis_id}/approvals",
            json={"finding_id": fid, "decision": "dismiss"},
        )

    assert auth_client.get(f"/api/analyses/{analysis_id}/score").json()["overall"] == 100
    emptied = auth_client.get(f"/api/analyses/{analysis_id}/remediation").json()
    assert emptied["work_items"] == []
    assert emptied["recoverable_points"] is None


def test_clean_repository_reports_an_explicit_empty_plan(analysis_id: int) -> None:
    plan = _plan(analysis_id)
    assert plan.work_items == []
    assert plan.findings_considered == 0
    assert plan.projected_overall is None
    assert plan.recoverable_points is None


def test_count_basis_projection_works_without_loc(analysis_id: int) -> None:
    """A repository with no LOC is scored on finding count, not density."""
    session = get_session_factory()()
    try:
        analysis = session.get(Analysis, analysis_id)
        assert analysis is not None
        analysis.loc = 0
        session.commit()
    finally:
        session.close()
    _add(analysis_id, "secret", Severity.HIGH)
    plan = _plan(analysis_id)
    assert plan.loc is None
    assert plan.projected_overall == aggregate([], None)["overall"]


def test_plan_is_capped_and_reports_the_remainder(analysis_id: int, monkeypatch) -> None:
    """A pathological repository must produce a readable page, and say what it hid."""
    monkeypatch.setattr(remediation, "MAX_WORK_ITEMS", 2)
    _add(analysis_id, "secret", Severity.CRITICAL, line_start=1)
    _add(analysis_id, "complexity", Severity.MEDIUM, line_start=2)
    _add(analysis_id, "readme", Severity.LOW, line_start=3)
    _add(analysis_id, "duplication", Severity.MEDIUM, line_start=4)
    _add(analysis_id, "missing-tests", Severity.MEDIUM, line_start=5)

    plan = _plan(analysis_id)
    assert len(plan.work_items) == 2
    # The three hidden items each hold one finding, and the header says so rather
    # than implying the plan is complete.
    assert plan.truncated_findings == 3
    assert plan.findings_considered == 5


def test_identical_findings_group_into_one_item(analysis_id: int) -> None:
    """Grouping is what keeps a large repository from producing a per-finding list."""
    for n in range(remediation.MAX_WORK_ITEMS + 3):
        _add(analysis_id, "secret", Severity.HIGH, line_start=n + 1)
    plan = _plan(analysis_id)
    assert len(plan.work_items) == 1
    assert plan.work_items[0].finding_count == remediation.MAX_WORK_ITEMS + 3
    assert plan.truncated_findings == 0


# --- api --------------------------------------------------------------------


def test_remediation_requires_authentication(client: TestClient, analysis_id: int) -> None:
    assert client.get(f"/api/analyses/{analysis_id}/remediation").status_code == 401


def test_remediation_returns_a_plan(auth_client: TestClient, analysis_id: int) -> None:
    _add(
        analysis_id,
        "vulnerable-dependency",
        Severity.HIGH,
        evidence={"vuln_ids": ["CVE-2023-30861"], "package": "flask", "version": "1.0.0"},
    )
    response = auth_client.get(f"/api/analyses/{analysis_id}/remediation")
    assert response.status_code == 200
    body = response.json()
    assert body["analysis_id"] == analysis_id
    assert body["projected_overall"] == 100
    item = body["work_items"][0]
    assert "flask 1.0.0" in item["action"]
    assert item["source"] == "catalog"
    assert item["finding_count"] == 1
    assert item["findings"][0]["file_path"] == "app/mod.py"
    assert item["steps"]
    assert item["pillar_points"] >= 0
    assert item["weighted_penalty_removed"] > 0


def test_remediation_409s_while_the_analysis_is_running(
    auth_client: TestClient, analysis_id: int
) -> None:
    session = get_session_factory()()
    try:
        analysis = session.get(Analysis, analysis_id)
        assert analysis is not None
        analysis.status = AnalysisStatus.RUNNING
        session.commit()
    finally:
        session.close()
    response = auth_client.get(f"/api/analyses/{analysis_id}/remediation")
    assert response.status_code == 409
    assert "not finished" in response.json()["detail"]


def test_remediation_of_a_clean_analysis_is_an_empty_plan(
    auth_client: TestClient, analysis_id: int
) -> None:
    response = auth_client.get(f"/api/analyses/{analysis_id}/remediation")
    assert response.status_code == 200
    assert response.json()["work_items"] == []


def test_markdown_export(auth_client: TestClient, analysis_id: int) -> None:
    _add(analysis_id, "secret", Severity.CRITICAL)
    _add(analysis_id, "readme", Severity.LOW)
    response = auth_client.get(f"/api/analyses/{analysis_id}/remediation.md")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "attachment" in response.headers["content-disposition"]
    body = response.text
    assert body.startswith("# Fix plan")
    assert "Health score now" in body
    assert "Rotate the exposed credential" in body
    # The export must carry the same caveat as the page, or a reader gets the point
    # values with no explanation of what they mean.
    assert "in its own pillar" in body
    assert "not a share of" in body
    assert "in the security pillar" in body


def test_markdown_export_of_a_clean_analysis(auth_client: TestClient, analysis_id: int) -> None:
    response = auth_client.get(f"/api/analyses/{analysis_id}/remediation.md")
    assert response.status_code == 200
    assert "nothing to fix" in response.text


def test_findings_carry_their_fix_inline(auth_client: TestClient, analysis_id: int) -> None:
    _add(analysis_id, "secret", Severity.HIGH, evidence={"rule": "generic.secrets"})
    body = auth_client.get(f"/api/analyses/{analysis_id}/findings").json()
    assert len(body) == 1
    assert body[0]["remediation"]["action"] == "Rotate the exposed credential"
    assert body[0]["remediation"]["effort"] == "low"


def test_agent_can_submit_a_remediation(auth_client: TestClient, analysis_id: int) -> None:
    fid = _add(analysis_id, "complexity", Severity.MEDIUM)
    response = auth_client.post(
        f"/api/analyses/{analysis_id}/remediation",
        json={
            "agent": "eve:code",
            "remediations": [
                {
                    "finding_id": fid,
                    "action": "Hoist the config lookup",
                    "steps": ["Lift it to module scope."],
                    "effort": "low",
                }
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["recorded"] == 1

    plan = auth_client.get(f"/api/analyses/{analysis_id}/remediation").json()
    item = plan["work_items"][0]
    assert item["action"] == "Hoist the config lookup"
    assert item["source"] == "llm:eve"

    findings = auth_client.get(f"/api/analyses/{analysis_id}/findings").json()
    assert findings[0]["remediation"]["source"] == "llm:eve"
    assert findings[0]["remediation"]["action"] == "Hoist the config lookup"


def test_submitted_remediation_rejects_a_foreign_finding(
    auth_client: TestClient, analysis_id: int
) -> None:
    other = _add(analysis_id + 0, "secret", Severity.HIGH)
    response = auth_client.post(
        f"/api/analyses/{analysis_id}/remediation",
        json={
            "agent": "eve",
            "remediations": [{"finding_id": 999_999, "action": "Do the thing", "steps": ["x"]}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["recorded"] == 0
    assert body["rejected"] == 1
    assert "not found" in body["reasons"][0]
    assert other  # fixture is real


def test_remediation_is_not_stored_for_a_dismissed_finding(
    auth_client: TestClient, analysis_id: int
) -> None:
    fid = _add(analysis_id, "secret", Severity.HIGH)
    _set_status([fid], FindingStatus.DISMISSED)
    response = auth_client.post(
        f"/api/analyses/{analysis_id}/remediation",
        json={
            "agent": "eve",
            "remediations": [{"finding_id": fid, "action": "Rotate it", "steps": ["revoke"]}],
        },
    )
    assert response.json()["recorded"] == 0
    assert "dismissed" in response.json()["reasons"][0]


# --- markdown renderer ------------------------------------------------------


def test_render_markdown_is_stable_without_a_session() -> None:
    plan = remediation.RemediationPlan(
        analysis_id=1,
        current_overall=None,
        projected_overall=None,
        loc=None,
        work_items=[],
        findings_considered=0,
        unverified_items=0,
    )
    body = render_markdown(plan, "owner/name", None)
    assert "nothing to fix" in body
    assert "Commit:" not in body
