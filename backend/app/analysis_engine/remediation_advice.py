"""The category -> advice catalog and its lookup entry points."""

from collections.abc import Callable
from typing import Any

from app.analysis_engine.remediation_catalog import (
    _code_smell,
    _complexity,
    _duplication,
    _generic,
    _injection,
    _insight,
    _maintainability,
    _outdated_dependency,
    _secret,
    _vulnerability,
    _vulnerable_dependency,
    _weak_crypto,
)
from app.analysis_engine.remediation_quality import (
    _coupling,
    _coverage,
    _docstring,
    _god_module,
    _import_cycle,
    _layering,
    _missing_tests,
    _readme,
    _test_plan,
)
from app.analysis_engine.remediation_types import (
    EFFORT_WEIGHT,
    Remediatable,
    Remediation,
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
