"""Remediation plan: what to fix, in what order, and what it is worth.

The analyzers say what is wrong with a repository. This module says what to do
about it. Two properties keep it honest:

* **Specific, not generic.** Every catalog entry is a function of the finding, so
  it can read ``evidence_json`` and name the actual CVE, package version,
  duplicated symbol pair, or complex function. "Update your dependencies" is not
  advice; "bump flask 1.0.0 to clear CVE-2023-30861" is.
* **Scored with the real curve.** A projection that used a different formula than
  the score it predicts would be a second opinion dressed up as arithmetic, so
  every number here comes from :func:`app.analysis_engine.scoring.aggregate`.

A note on the numbers, because the distinction is easy to get wrong. The curve
``100 / (1 + density / 30)`` is not linear, and the overall is
``min(weighted_mean, worst_pillar + 15)``, so the points recovered by fixing two
items is not the sum of the points recovered by fixing each alone: fixing the
worst pillar lifts the ceiling for everything else. The plan therefore reports:

* ``projected_overall`` in the header — the score of a repository with *no*
  findings, run through the real curve. Exact, and the number a developer
  actually cares about.
* ``weighted_penalty_removed`` per item — additive and exact, because it is
  literally the curve's own input. This is what the ranking sorts on.
* ``pillar_points`` per item — what fixing it is worth in its own pillar. Not the
  overall delta: the overall is capped at ``worst_pillar + 15``, so clearing a
  drowning security pillar moves the overall by zero while it is not yet the
  binding constraint. Showing that would put "+0 pts" on the most valuable fix in
  the repository.

An LLM-authored remediation, when present, replaces the catalog entry for that
finding and is labelled ``llm:eve`` so a reader can always tell advice derived
from evidence apart from advice a model wrote.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis_engine.remediation_advice import (
    CATALOG,
    remediation_for,
    remediation_summary,
)
from app.analysis_engine.remediation_markdown import render_markdown
from app.analysis_engine.remediation_types import (
    EFFORT_WEIGHT,
    MAX_WORK_ITEMS,
    UNSCORED_CATEGORIES,
    Remediatable,
    Remediation,
    RemediationPlan,
    WorkItem,
)
from app.analysis_engine.scoring import (
    CATEGORY_PILLAR,
    SEVERITY_WEIGHT,
    STATUS_FACTOR,
    aggregate,
)
from app.models import Analysis, Finding, FindingStatus

__all__ = [
    "CATALOG",
    "EFFORT_WEIGHT",
    "MAX_WORK_ITEMS",
    "UNSCORED_CATEGORIES",
    "Remediation",
    "Remediatable",
    "RemediationPlan",
    "WorkItem",
    "build_plan",
    "remediation_for",
    "remediation_summary",
    "render_markdown",
]


def _penalty_of(finding: Finding) -> float:
    weight = SEVERITY_WEIGHT.get(finding.severity.value, 0)
    factor = STATUS_FACTOR.get(finding.status, 1.0)
    return weight * factor


_SEVERITY_RANK = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}


def _pillar_gain(baseline: dict, remaining: list[Finding], pillar: str, loc: int | None) -> int:
    """What fixing one group is worth, measured in its own pillar's points.

    Deliberately *not* the overall delta. The overall is capped at
    ``worst_pillar + WORST_PILLAR_HEADROOM``, so on a repository whose security
    pillar is drowning, clearing all of security moves the overall by nothing at
    all — the next-worst pillar takes over as the cap. A card reading "+0 pts" for
    the single most valuable fix in the repository is technically true and
    actively misleading, so the number shown is the one the work actually moves.

    The header's before/after remains the honest overall projection, because that
    is the figure a reader compares against the score they already have.
    """
    if pillar == "other":
        # Unscored-by-pillar categories have no pillar to move.
        return 0
    baseline_pillars = baseline.get("pillars") or {}
    remaining_pillars = aggregate(remaining, loc).get("pillars") or {}
    before = (baseline_pillars.get(pillar) or {}).get("score", 0)
    after = (remaining_pillars.get(pillar) or {}).get("score", 0)
    return max(0, after - before)


def _top_severity(findings: list[Finding]) -> str:
    return max(
        (f.severity.value for f in findings),
        key=lambda value: _SEVERITY_RANK.get(value, 0),
        default="info",
    )


def _group_key(category: str, effort: str) -> tuple[str, str]:
    """The identity of a work item.

    Grouped by category and effort rather than by action text. The catalog writes
    the offending symbol into the action ("break up parse_args"), so grouping on
    the action string yields one card per function — which is the per-finding noise
    this plan exists to remove. Every finding in one category wants the same kind
    of work, so they belong on one card, with the individual symbols listed under
    it where the reader can still see exactly which functions are involved.
    """
    return (category, effort)


# Headline for a multi-finding work item. The per-finding action stays in the
# details; the title has to describe the batch, and "break up __init__" over
# fifty-two findings is not a description of anything.
def _packages(count: int, adjective: str) -> str:
    return f"{count} {adjective} dependenc{'y' if count == 1 else 'ies'}"


def _group_action(category: str, count: int) -> str:
    plural = "s" if count != 1 else ""
    return {
        "secret": f"Rotate {count} exposed credential{plural}",
        "vulnerability": f"Fix {count} flagged code path{plural}",
        "injection": f"Close {count} injection path{plural}",
        "weak-crypto": f"Replace {count} weak cryptographic primitive{plural}",
        "code-smell": f"Address {count} code smell{plural}",
        "complexity": f"Reduce complexity in {count} over-complex function{plural}",
        "maintainability": f"Improve maintainability in {count} module{plural}",
        "duplication": f"Extract {count} duplicated block{plural}",
        "vulnerable-dependency": f"Upgrade {_packages(count, 'vulnerable')}",
        "outdated-dependency": f"Update {_packages(count, 'outdated')}",
        "coverage": "Add a test suite",
        "missing-tests": f"Add tests covering {count} untested package{plural}",
        "test-plan": f"Turn {count} coverage gap{plural} into a test plan",
        "readme": "Add a README",
        "readme-plan": "Add a README",
        "docstring": f"Document the public API ({count} module{plural} affected)",
        "docstring-plan": f"Document the public API ({count} module{plural} affected)",
        "import-cycle": f"Break {count} import cycle{plural}",
        "god-module": f"Split {count} god module{plural}",
        "layering": f"Restore {count} layer boundar{'ies' if count != 1 else 'y'}",
        "coupling": f"Reduce coupling in {count} module{plural}",
        "code-review": f"Address {count} review finding{plural}",
        "insight": f"Review {count} reported issue{plural}",
    }.get(category, f"Resolve {count} finding{plural}")


def build_plan(session: Session, analysis_id: int) -> RemediationPlan:
    """Assemble the fix plan for one analysis.

    Derived on demand rather than stored, so a plan cannot go stale: the moment a
    reviewer dismisses a finding in the approval queue, the next read reflects it.
    """
    analysis = session.get(Analysis, analysis_id)
    loc = analysis.loc if analysis is not None and analysis.loc else None

    rows = session.scalars(
        select(Finding).where(
            Finding.analysis_id == analysis_id,
            Finding.status != FindingStatus.DISMISSED,
        )
    ).all()
    considered = [f for f in rows if f.category not in UNSCORED_CATEGORIES]

    # A repository with nothing to fix must still say so: the page needs an
    # explicit empty state rather than a silently absent list. `projected_overall`
    # stays None rather than becoming 100 — "everything fixed" is only meaningful
    # when there was something to fix.
    if not considered:
        # Scored live, for the same reason as the non-empty branch below.
        return RemediationPlan(
            analysis_id=analysis_id,
            current_overall=aggregate([], loc)["overall"],
            projected_overall=None,
            loc=loc,
            work_items=[],
            findings_considered=0,
            unverified_items=0,
        )

    groups: dict[tuple[str, str], list[Finding]] = {}
    for finding in considered:
        groups.setdefault(_group_key(finding.category, remediation_for(finding).effort), []).append(
            finding
        )

    baseline = aggregate(considered, loc)

    items: list[WorkItem] = []
    for members in groups.values():
        # The lead finding supplies the steps. Members of a group share a category by
        # construction, so their catalog entries agree; an LLM entry can differ, so
        # prefer an authored one when the group has one.
        lead = next((f for f in members if (f.evidence_json or {}).get("remediation")), members[0])
        remediation = remediation_for(lead)
        penalty = sum(_penalty_of(f) for f in members)
        pillar = CATEGORY_PILLAR.get(lead.category) or "other"
        # A single finding gets its own specific action ("upgrade flask 0.12.2 to
        # clear CVE-2023-30861"), which is the most useful thing on the card. A batch
        # gets a headline that describes the batch; the specifics move into the
        # findings list underneath, where nothing is lost.
        action = (
            remediation.action if len(members) == 1 else _group_action(lead.category, len(members))
        )
        # Keyed by identity because SQLAlchemy models compare by database row.
        member_ids = {id(f) for f in members}
        remaining = [f for f in considered if id(f) not in member_ids]
        items.append(
            WorkItem(
                key=lead.category,
                pillar=pillar,
                action=action,
                severity=_top_severity(members),
                effort=remediation.effort,
                findings=members,
                steps=remediation.steps,
                verify=remediation.verify,
                references=remediation.references,
                weighted_penalty_removed=round(penalty, 2),
                pillar_points=_pillar_gain(baseline, remaining, pillar, loc),
                llm_authored=any((f.evidence_json or {}).get("remediation") for f in members),
            )
        )

    items.sort(key=lambda item: (-item.payoff(), -_SEVERITY_RANK.get(item.severity, 0)))

    truncated = 0
    if len(items) > MAX_WORK_ITEMS:
        truncated = sum(item.finding_count for item in items[MAX_WORK_ITEMS:])
        items = items[:MAX_WORK_ITEMS]

    # Scored from the live findings rather than read from `analysis.score_json`.
    # The plan is derived on every request precisely so it cannot go stale, and its
    # before/after is only meaningful if both ends come from the same computation as
    # the projection. Trusting the cached score would let a reviewer dismiss a
    # finding, watch the plan empty out, and still be shown a "before" number from
    # before the dismissal.
    return RemediationPlan(
        analysis_id=analysis_id,
        current_overall=baseline["overall"],
        projected_overall=aggregate([], loc)["overall"],
        loc=loc,
        work_items=items,
        findings_considered=len(considered),
        unverified_items=sum(
            1 for item in items if any(f.status == FindingStatus.HYPOTHESIS for f in item.findings)
        ),
        truncated_findings=truncated,
    )
