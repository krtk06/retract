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

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis_engine.scoring import (
    CATEGORY_PILLAR,
    SEVERITY_WEIGHT,
    STATUS_FACTOR,
    aggregate,
)
from app.models import Analysis, Finding, FindingStatus

# Ordered roughly by how much effort a human typically needs. These are ratios,
# not durations: `high` is eight times the work of `low`, which is about right
# when `low` is "rotate a key" and `high` is "restructure a module".
EFFORT_WEIGHT = {"low": 1, "medium": 3, "high": 8}

# Categories the platform files but deliberately excludes from scoring. Advice
# about the analysis pipeline's own housekeeping is noise in a fix plan.
UNSCORED_CATEGORIES = frozenset({"inventory", "tool-error"})

# Cap on work items, so a repository with thousands of findings cannot produce an
# unreadable page. The remainder is reported in `truncated_findings` rather than
# silently dropped.
MAX_WORK_ITEMS = 40


@dataclass(frozen=True)
class Remediation:
    """How to fix one finding."""

    action: str
    steps: list[str]
    effort: str = "medium"
    verify: str = "Re-run the analysis and confirm the finding is gone."
    references: list[str] = field(default_factory=list)

    def weight(self) -> int:
        return EFFORT_WEIGHT.get(self.effort, EFFORT_WEIGHT["medium"])


class Remediatable(Protocol):
    """The finding attributes the catalog reads.

    A Protocol rather than ``Finding`` so the API schema can ask for advice about
    a partially-loaded row without importing the ORM model into ``app.schemas``.
    """

    category: str
    title: str
    evidence_json: dict[str, Any] | None
    file_path: str | None
    line_start: int | None


# --- evidence helpers ------------------------------------------------------
# Every one of these returns a value or None rather than raising: a finding with
# an unexpected evidence shape must degrade to the generic entry for its
# category, never fail the whole plan.


def _text(evidence: dict[str, Any], key: str) -> str | None:
    value = evidence.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _number(evidence: dict[str, Any], key: str) -> float | None:
    value = evidence.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _names(evidence: dict[str, Any], key: str, limit: int = 4) -> list[str]:
    value = evidence.get(key)
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()][:limit]


def _where(finding: Remediatable) -> str:
    if not finding.file_path:
        return "the repository"
    if finding.line_start:
        return f"{finding.file_path}:{finding.line_start}"
    return finding.file_path


OWASP_TOP10 = "https://owasp.org/www-project-top-10/2021"
GITHUB_PURGE = (
    "https://docs.github.com/en/authentication/keeping-your-account-and-data-secure"
    "/removing-sensitive-data-from-a-repository"
)


# --- catalog ---------------------------------------------------------------
# Keyed by finding category. Each entry receives the finding and returns advice
# as specific as the available evidence allows.


def _secret(finding: Remediatable) -> Remediation:
    return Remediation(
        action="Rotate the exposed credential",
        steps=[
            "Treat it as compromised — it is in git history now, not just the tree.",
            "Revoke and reissue at the provider, in that order, before touching code.",
            "Move the new value into the environment or a secret manager.",
            f"Remove the literal at {_where(finding)} and replace it with a lookup.",
            "Purge the value from history if the repo was ever pushed publicly.",
        ],
        effort="low",
        verify="Re-run the analysis: the secret finding should disappear.",
        references=[
            GITHUB_PURGE,
            f"{OWASP_TOP10}/A07_2021-Identification_and_Authentication_Failures/",
        ],
    )


def _vulnerability(finding: Remediatable) -> Remediation:
    rule = _text(finding.evidence_json or {}, "rule")
    steps = [
        f"Read the flagged region at {_where(finding)}; confirm it is reachable.",
        "Validate or encode untrusted input at the boundary, before the sink.",
        "Prefer a parameterised API over string-built queries or shell commands.",
    ]
    if rule:
        steps.append(f"Re-check the specific rule ({rule}) after the change.")
    return Remediation(
        action="Fix the flagged code path",
        steps=steps,
        effort="medium",
        verify="Re-run the analysis: the vulnerability finding should disappear.",
        references=[f"{OWASP_TOP10}/A03_2021-Injection/"],
    )


def _injection(finding: Remediatable) -> Remediation:
    return Remediation(
        action="Close the injection path",
        steps=[
            f"Trace untrusted input to the sink at {_where(finding)}.",
            "Confirm the path with the caller graph, not by reading the line alone.",
            "Use a parameterised API (prepared statements, argv lists).",
            "If the sink is unavoidable, allow-list values instead of blocking them.",
            "Add a test that attempts the injection; it should fail before the fix.",
        ],
        effort="medium",
        verify="Re-run the analysis: the injection finding should be gone or dismissed.",
        references=[f"{OWASP_TOP10}/A03_2021-Injection/"],
    )


def _weak_crypto(finding: Remediatable) -> Remediation:
    return Remediation(
        action="Replace the weak cryptographic primitive",
        steps=[
            f"Identify what the algorithm at {_where(finding)} actually protects.",
            "Hashes: SHA-256 for integrity, bcrypt or argon2 for passwords.",
            "Never MD5 or SHA-1 for anything security-relevant.",
            "Ciphers: an AEAD mode such as AES-GCM, with a unique nonce per message.",
            "Randomness: the `secrets` module, never `random`.",
            "Rotate existing values — a new algorithm does not protect old data.",
        ],
        effort="medium",
        verify="Re-run the analysis: the weak-crypto finding should disappear.",
        references=[f"{OWASP_TOP10}/A02_2021-Cryptographic_Failures/"],
    )


def _vulnerable_dependency(finding: Remediatable) -> Remediation:
    evidence = finding.evidence_json or {}
    package = _text(evidence, "package")
    version = _text(evidence, "version")
    vulns = _names(evidence, "vuln_ids", limit=3)
    subject = f"{package} {version}".strip() or "the dependency"
    listed = ", ".join(vulns) if vulns else "the advisory"
    return Remediation(
        action=f"Upgrade {subject} to a patched release",
        steps=[
            f"Read the advisories for {subject}: {listed}.",
            "Upgrade to the first unaffected release, not necessarily the newest.",
            "Re-run the dependency audit; no advisory should still match the pin.",
            "Run the test suite — a major bump may change behaviour, a patch should not.",
            "Commit the updated lockfile, not just the manifest.",
        ],
        effort="low",
        verify="Re-run the analysis: the vulnerable-dependency finding should disappear.",
        references=["https://osv.dev/"],
    )


def _outdated_dependency(finding: Remediatable) -> Remediation:
    evidence = finding.evidence_json or {}
    installed = _text(evidence, "installed")
    latest = _text(evidence, "latest")
    span = f"{installed} to {latest}" if installed and latest else "the latest release"
    return Remediation(
        action=f"Update the dependency pinned at {_where(finding)}",
        steps=[
            f"Move the pin from {span}.",
            "Read the changelog for behaviour changes, not just fixes.",
            "Run the test suite; this is the step that catches a silent break.",
        ],
        effort="low",
        verify="Re-run the analysis: the outdated-dependency finding should disappear.",
        references=["https://owasp.org/www-project-dependency-check/"],
    )


def _complexity(finding: Remediatable) -> Remediation:
    evidence = finding.evidence_json or {}
    symbol = _text(evidence, "symbol") or "the flagged function"
    cc = _number(evidence, "cyclomatic_complexity")
    measured = f"a cyclomatic complexity of {cc:g}" if cc is not None else "high complexity"
    return Remediation(
        action=f"Break up {symbol}",
        steps=[
            f"{symbol} at {_where(finding)} has {measured}.",
            "Extract each distinct branch group into a named function.",
            "Use early returns to flatten the guard clauses at the top.",
            "Keep the extraction behaviour-preserving; pin current behaviour first.",
            "Re-measure afterwards: aim below the threshold, not merely lower.",
        ],
        effort="medium",
        verify="Re-run the analysis: the complexity finding should drop or disappear.",
        references=["https://en.wikipedia.org/wiki/Cyclomatic_complexity"],
    )


def _maintainability(finding: Remediatable) -> Remediation:
    return Remediation(
        action="Improve the module's maintainability",
        steps=[
            f"{_where(finding)} scores below the maintainability threshold.",
            "Reduce the longest functions first; complexity drives the index.",
            "Remove dead code and collapse duplicated blocks while you are there.",
            "Re-measure once the structure changes, not just the formatting.",
        ],
        effort="medium",
        verify="Re-run the analysis: the maintainability finding should disappear.",
        references=["https://radon.readthedocs.io/en/latest/maintainability.html"],
    )


def _duplication(finding: Remediatable) -> Remediation:
    evidence = finding.evidence_json or {}
    original = _text(evidence, "original")
    duplicate = _text(evidence, "duplicate")
    pair = f"{original} and {duplicate}" if original and duplicate else "the copies"
    return Remediation(
        action="Extract the duplicated logic",
        steps=[
            f"The same block appears in {pair}.",
            "Extract it into one shared function, passing differences as arguments.",
            "Replace both call sites, then delete the second copy.",
            "Fix one bug and confirm both places are fixed — that is the payoff.",
        ],
        effort="low",
        verify="Re-run the analysis: the duplication finding should disappear.",
        references=["https://en.wikipedia.org/wiki/Dry_(software)"],
    )


def _coverage(finding: Remediatable) -> Remediation:
    return Remediation(
        action="Add a test suite",
        steps=[
            "No test files were found, so nothing here is protected against regression.",
            "Stand up the runner the language already implies (pytest, or the JS peer).",
            "Start with the public entry points: one end-to-end pass over the main path.",
            "Add a regression test per verified high-severity finding.",
            "Wire the suite into CI so it runs on every push.",
        ],
        effort="high",
        verify="Re-run the analysis: the coverage finding should disappear.",
        references=["https://pytest.org/en/stable/getting-started.html"],
    )


def _missing_tests(finding: Remediatable) -> Remediation:
    package = _text(finding.evidence_json or {}, "package") or "this package"
    return Remediation(
        action=f"Add tests covering {package}",
        steps=[
            f"No test file imports {package}, so its behaviour can change silently.",
            "Write tests for the public functions first, by caller count.",
            "Cover the error branches: an untried `except` path is untested code.",
            "For each verified finding here, add a test that fails without the fix.",
        ],
        effort="medium",
        verify="Re-run the analysis: the missing-tests finding should disappear.",
        references=["https://pytest.org/en/stable/how-to/fixtures.html"],
    )


def _test_plan(finding: Remediatable) -> Remediation:
    return Remediation(
        action="Turn the coverage gaps into a test plan",
        steps=[
            "Rank the untested public functions by how many callers they have.",
            "Pin current behaviour with one test each, before changing anything.",
            "Add a test per error branch, forcing the failure deliberately.",
            "Schedule the run in CI so the suite cannot silently rot.",
        ],
        effort="medium",
        verify="Re-run the analysis once the tests exist: the testing pillar should rise.",
        references=[],
    )


def _readme(finding: Remediatable) -> Remediation:
    return Remediation(
        action="Add a README",
        steps=[
            "State what the project is and what it is for, in the first two lines.",
            "Document installation and the exact command that runs it.",
            "Show one minimal working example — the fastest orientation available.",
            "Add the headings the analyzer checks: usage, config, testing, contributing.",
        ],
        effort="low",
        verify="Re-run the analysis: the readme finding should disappear.",
        references=["https://www.makeareadme.com/"],
    )


def _docstring(finding: Remediatable) -> Remediation:
    missing = _names(finding.evidence_json or {}, "missing", limit=6)
    listed = ", ".join(missing) if missing else "the undocumented public symbols"
    return Remediation(
        action="Document the public API",
        steps=[
            f"{_where(finding)} leaves these undocumented: {listed}.",
            "Write one line on what each returns, not a restatement of its name.",
            "Document the arguments the signature does not explain, and what it raises.",
            "Document side effects — files written, global state mutated.",
        ],
        effort="low",
        verify="Re-run the analysis: the docstring finding should disappear.",
        references=["https://peps.python.org/pep-0257/"],
    )


def _import_cycle(finding: Remediatable) -> Remediation:
    cycle = _names(finding.evidence_json or {}, "cycle", limit=6)
    chain = " -> ".join(cycle) if cycle else "the modules in the cycle"
    return Remediation(
        action="Break the import cycle",
        steps=[
            f"The cycle is {chain}.",
            "Move the shared low-level type into a module neither side imports back.",
            "If that is too large now, make one edge a local import to break it today.",
            "Verify: importing any module in the chain first must work, in any order.",
        ],
        effort="high",
        verify="Re-run the analysis: the import-cycle finding should disappear.",
        references=["https://en.wikipedia.org/wiki/Circular_dependency"],
    )


def _god_module(finding: Remediatable) -> Remediation:
    evidence = finding.evidence_json or {}
    fan_in = _number(evidence, "fan_in")
    threshold = _number(evidence, "threshold")
    count = f"imported by {fan_in:g} modules" if fan_in is not None else "heavily imported"
    limit = f" (threshold {threshold:g})" if threshold is not None else ""
    return Remediation(
        action="Split the god module",
        steps=[
            f"{_where(finding)} is {count}{limit}, so one change has wide blast radius.",
            "Group its symbols by responsibility; move each group to its own module.",
            "Keep the original as a thin re-export so no caller breaks in one step.",
            "Move callers over, then delete the re-export once nothing imports it.",
        ],
        effort="high",
        verify="Re-run the analysis: the god-module finding should disappear.",
        references=["https://en.wikipedia.org/wiki/God_object"],
    )


def _layering(finding: Remediatable) -> Remediation:
    return Remediation(
        action="Restore the layer boundary",
        steps=[
            f"{_where(finding)} points a lower layer at infrastructure.",
            "Define the interface the inner layer needs, as a protocol or ABC.",
            "Invert the dependency: the outer layer implements it and registers it.",
            "Prove it with an import check — the core must import no database client.",
        ],
        effort="high",
        verify="Re-run the analysis: the layering finding should disappear.",
        references=["https://en.wikipedia.org/wiki/Dependency_inversion_principle"],
    )


def _coupling(finding: Remediatable) -> Remediation:
    return Remediation(
        action="Reduce the coupling",
        steps=[
            f"{_where(finding)} changes require coordinated edits elsewhere.",
            "Narrow the interface: pass the values needed, not the whole object.",
            "Return data instead of exposing internal collections for mutation.",
            "If the coupling is mutual, merge the two modules rather than decoupling.",
        ],
        effort="medium",
        verify="Re-run the analysis: the coupling finding should disappear.",
        references=["https://en.wikipedia.org/wiki/Coupling_(software)"],
    )


def _code_smell(finding: Remediatable) -> Remediation:
    rule = _text(finding.evidence_json or {}, "rule")
    steps = [
        f"Review {_where(finding)}: a real defect, or an idiom here?",
        "If it is a false positive, dismiss it and say why; that is recorded.",
    ]
    if rule:
        steps.append(f"Otherwise fix the construct the rule names ({rule}).")
    steps.append("Re-run the analysis to confirm it is cleared.")
    return Remediation(
        action="Address the flagged code smell",
        steps=steps,
        effort="low",
        verify="Re-run the analysis: the finding should disappear or be dismissed.",
        references=[],
    )


def _insight(finding: Remediatable) -> Remediation:
    return Remediation(
        action="Review the reported issue",
        steps=[
            f"Read {_where(finding)} and confirm the claim against the code.",
            "Fix it, or dismiss it with a reason.",
            "An unreviewed claim is not a finding; it is a question.",
        ],
        effort="low",
        verify="Re-run the analysis: the finding should be fixed or dismissed.",
        references=[],
    )


def _generic(finding: Remediatable) -> Remediation:
    return Remediation(
        action=f"Resolve: {finding.title}",
        steps=[
            f"Review the finding at {_where(finding)}.",
            "Read the cited lines and decide whether it is a real problem.",
            "Fix it, or dismiss it with a reason so it stops consuming review time.",
        ],
        effort="medium",
        verify="Re-run the analysis and confirm the finding is resolved or dismissed.",
        references=[],
    )


CATALOG: dict[str, Callable[[Remediatable], Remediation]] = {
    "secret": _secret,
    "vulnerability": _vulnerability,
    "injection": _injection,
    "weak-crypto": _weak_crypto,
    "code-smell": _code_smell,
    "complexity": _complexity,
    "maintainability": _maintainability,
    "duplication": _duplication,
    "vulnerable-dependency": _vulnerable_dependency,
    "outdated-dependency": _outdated_dependency,
    "coverage": _coverage,
    "missing-tests": _missing_tests,
    "test-plan": _test_plan,
    "readme": _readme,
    "readme-plan": _readme,
    "docstring": _docstring,
    "docstring-plan": _docstring,
    "import-cycle": _import_cycle,
    "god-module": _god_module,
    "layering": _layering,
    "coupling": _coupling,
    "code-review": _code_smell,
    "insight": _insight,
}


def remediation_for(finding: Remediatable) -> Remediation:
    """Best available remediation for one finding.

    An LLM-authored one wins over the catalog, because it was written with this
    code in view. Any failure in a catalog entry falls back to the generic advice
    rather than propagating: one malformed finding must not blank the fix plan for
    the whole repository.
    """
    authored = (finding.evidence_json or {}).get("remediation")
    if isinstance(authored, dict) and isinstance(authored.get("action"), str):
        return _from_authored(authored)

    entry = CATALOG.get(finding.category, _generic)
    try:
        result = entry(finding)
    except Exception:  # noqa: BLE001 — advice must never break the plan
        return _generic(finding)
    return result if result.steps else _generic(finding)


def _from_authored(data: dict[str, Any]) -> Remediation:
    steps = data.get("steps")
    references = data.get("references")
    effort = data.get("effort")
    return Remediation(
        action=str(data["action"])[:300],
        steps=[str(s)[:500] for s in steps] if isinstance(steps, list) and steps else [],
        effort=str(effort) if effort in EFFORT_WEIGHT else "medium",
        verify=str(data.get("verify") or "")[:500]
        or "Re-run the analysis and confirm the issue is resolved.",
        references=[str(r)[:400] for r in references]
        if isinstance(references, list) and references
        else [],
    )


def remediation_summary(finding: Remediatable) -> dict[str, str]:
    """The one-line form, for embedding in a findings response.

    Deliberately not the full steps: this rides along on every finding in the
    list, so it stays small enough to be free.
    """
    authored = (finding.evidence_json or {}).get("remediation")
    result = remediation_for(finding)
    source = "llm:eve" if isinstance(authored, dict) else "catalog"
    return {"action": result.action, "effort": result.effort, "source": source}


# --- plan ------------------------------------------------------------------


@dataclass
class WorkItem:
    key: str
    pillar: str
    action: str
    severity: str
    effort: str
    findings: list[Finding]
    steps: list[str]
    verify: str
    references: list[str]
    weighted_penalty_removed: float
    pillar_points: int
    llm_authored: bool = False

    @property
    def source(self) -> str:
        return "llm:eve" if self.llm_authored else "catalog"

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    def payoff(self) -> float:
        """Score points per unit of effort. This is the ranking key.

        Uses the additive penalty removal rather than the point delta, because
        penalty removal is exact and order-independent, so the ordering it induces
        is stable across repositories.
        """
        return self.weighted_penalty_removed / EFFORT_WEIGHT.get(self.effort, 3)


@dataclass
class RemediationPlan:
    analysis_id: int
    current_overall: int | None
    projected_overall: int | None
    loc: int | None
    work_items: list[WorkItem]
    findings_considered: int
    unverified_items: int
    truncated_findings: int = 0

    @property
    def recoverable_points(self) -> int | None:
        if self.current_overall is None or self.projected_overall is None:
            return None
        return max(0, self.projected_overall - self.current_overall)


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
    before = baseline["pillars"].get(pillar, {}).get("score", 0)
    after = aggregate(remaining, loc)["pillars"].get(pillar, {}).get("score", 0)
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


# --- markdown --------------------------------------------------------------


def _bullets(lines: list[str], items: Iterable[str]) -> None:
    lines.extend(f"- {item}" for item in items)


def render_markdown(plan: RemediationPlan, repo_label: str, commit_sha: str | None) -> str:
    """Render the plan as a Markdown document.

    Shaped for pasting into an issue or a PR description: ranked, each item
    self-contained, and explicit about which numbers are exact.
    """
    lines: list[str] = [f"# Fix plan — `{repo_label}`", ""]
    if commit_sha:
        lines.extend([f"Commit: `{commit_sha[:8]}`", ""])

    lines.extend(["## Headline", ""])
    if plan.current_overall is None or plan.projected_overall is None:
        lines.extend(["No open findings — there is nothing to fix.", ""])
        return "\n".join(lines)

    lines.extend(
        [
            "| Metric | Value |",
            "| --- | --- |",
            f"| Health score now | **{plan.current_overall}/100** |",
            f"| Health score with every item below fixed | **{plan.projected_overall}/100** |",
            f"| Points available | **{plan.recoverable_points}** |",
            f"| Work items | {len(plan.work_items)} |",
            f"| Findings covered | {plan.findings_considered} |",
        ]
    )
    if plan.unverified_items:
        lines.append(f"| Items resting on unverified claims | {plan.unverified_items} |")
    lines.extend(
        [
            "",
            "The headline is exact: it is this platform's own scoring curve, run over a",
            "repository with none of these findings. Each item's point value is the gain",
            "**in its own pillar**, measured against today's score. It is not a share of",
            "the headline: the curve is nonlinear, and the overall is capped at the worst",
            "pillar plus 15, so fixing anything but the current worst pillar can move the",
            "headline by very little. Use the ranking, not a sum, to sequence the work.",
            "",
        ]
    )

    lines.extend(["## Work items, highest payoff per unit of effort first", ""])
    for index, item in enumerate(plan.work_items, start=1):
        plural = "s" if item.finding_count != 1 else ""
        lines.extend(
            [
                f"### {index}. {item.action}",
                "",
                f"`+{item.pillar_points} pts` in the {item.pillar} pillar · "
                f"`{item.effort}` effort · {item.finding_count} finding{plural} · "
                f"removes **{item.weighted_penalty_removed:g}** penalty points · "
                f"source `{item.source}`",
                "",
            ]
        )
        _bullets(lines, item.steps)
        lines.append("")
        lines.extend(["<details><summary>Affected findings</summary>", ""])
        for finding in item.findings:
            where = f"`{_where(finding)}`" if finding.file_path else "repository-wide"
            lines.append(f"- [{finding.severity.value}] {finding.title} — {where}")
        lines.extend(["", "</details>", ""])
        lines.extend([f"**Verify:** {item.verify}", ""])
        if item.references:
            _bullets(lines, item.references)
            lines.append("")

    if plan.truncated_findings:
        lines.extend(
            [
                f"_{plan.truncated_findings} further findings were grouped into work items "
                f"beyond the {MAX_WORK_ITEMS}-item display limit._",
                "",
            ]
        )

    return "\n".join(lines)
