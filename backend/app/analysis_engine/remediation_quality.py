"""Testing, documentation, and architecture remediation advice."""

from app.analysis_engine.remediation_types import (
    Remediatable,
    Remediation,
    _names,
    _number,
    _text,
    _where,
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
