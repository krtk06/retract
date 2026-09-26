"""Health score computation.

v2 (Decision D8): honest weighting by verification status.
  - verified findings count at full severity weight;
  - hypothesis findings count at half weight;
  - dismissed findings count zero.

v3: the same discounting, but the penalty is applied as a ratio instead of a
linear subtraction. v2 computed ``100 − density × 2.0`` and clamped at 0, so any
repository below roughly 230 LOC with a single medium finding scored 0: the number
stopped carrying information about how bad the code was. v3 scores
``100 / (1 + density / HALF_SCORE_DENSITY)``, which reaches 50 at the documented
density, degrades smoothly past it, and never hard-clamps.

Formula: per-pillar score = 100 / (1 + weighted_penalty / KLOC / HALF_SCORE_DENSITY)
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Analysis, Finding, FindingStatus

SEVERITY_WEIGHT = {"critical": 30, "high": 20, "medium": 10, "low": 5, "info": 0}

# D8: hypotheses are less trusted than verified findings; dismissals are noise.
STATUS_FACTOR = {
    FindingStatus.VERIFIED: 1.0,
    FindingStatus.HYPOTHESIS: 0.5,
    FindingStatus.DISMISSED: 0.0,
}

PILLARS = ["code-quality", "security", "testing", "documentation", "dependencies", "architecture"]

# category → pillar
CATEGORY_PILLAR = {
    "code-smell": "code-quality",
    "complexity": "code-quality",
    "maintainability": "code-quality",
    "duplication": "code-quality",
    "secret": "security",
    "vulnerability": "security",
    "vulnerable-dependency": "security",
    "missing-tests": "testing",
    "coverage": "testing",
    "readme": "documentation",
    "docstring": "documentation",
    "outdated-dependency": "dependencies",
    "import-cycle": "architecture",
    "god-module": "architecture",
    "inventory": None,
    "tool-error": None,
}

PILLAR_WEIGHTS = {
    "code-quality": 0.20,
    "security": 0.25,
    "testing": 0.20,
    "documentation": 0.10,
    "dependencies": 0.10,
    "architecture": 0.15,
}

# Weighted finding-points per KLOC at which a pillar scores 50. One calibration
# constant for the whole curve: 250 means 12.5 high findings (or 25 medium) in
# every thousand lines. Only the benchmark has evidence to move it, so it is
# named, exported, and asserted in tests rather than buried in a formula.
HALF_SCORE_DENSITY = 250.0

# Guards division by zero for an unknown or empty LOC. Not a density assumption:
# with the ratio curve a small denominator no longer saturates the score.
MIN_KLOC = 0.001


def _clamp(value: float, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, round(value)))


def _pillar_score(weighted_penalty: float, kloc: float) -> int:
    """Ratio curve: 100 with no findings, 50 at HALF_SCORE_DENSITY, asymptotic to 0."""
    density = weighted_penalty / kloc
    return _clamp(100 / (1 + density / HALF_SCORE_DENSITY))


def compute_score(session: Session, analysis_id: int) -> dict:
    analysis = session.get(Analysis, analysis_id)
    loc = analysis.loc if analysis is not None and analysis.loc else None

    findings = session.scalars(select(Finding).where(Finding.analysis_id == analysis_id)).all()

    pillar_penalty: dict[str, float] = {p: 0.0 for p in PILLARS}
    pillar_counts: dict[str, int] = {p: 0 for p in PILLARS}
    pillar_verified: dict[str, int] = {p: 0 for p in PILLARS}
    pillar_hypotheses: dict[str, int] = {p: 0 for p in PILLARS}
    pillar_dismissed: dict[str, int] = {p: 0 for p in PILLARS}
    for finding in findings:
        pillar = CATEGORY_PILLAR.get(finding.category)
        if pillar is None:
            continue
        weight = SEVERITY_WEIGHT.get(finding.severity.value, 0)
        factor = STATUS_FACTOR.get(finding.status, 1.0)
        pillar_penalty[pillar] += weight * factor
        pillar_counts[pillar] += 1
        if finding.status == FindingStatus.VERIFIED:
            pillar_verified[pillar] += 1
        elif finding.status == FindingStatus.HYPOTHESIS:
            pillar_hypotheses[pillar] += 1
        elif finding.status == FindingStatus.DISMISSED:
            pillar_dismissed[pillar] += 1

    kloc = max((loc or 0) / 1000, MIN_KLOC)
    pillars = {}
    for pillar in PILLARS:
        pillars[pillar] = {
            "score": _pillar_score(pillar_penalty[pillar], kloc),
            "findings": pillar_counts[pillar],
            "verified": pillar_verified[pillar],
            "hypotheses": pillar_hypotheses[pillar],
            "dismissed": pillar_dismissed[pillar],
            "weighted_penalty": round(pillar_penalty[pillar], 2),
        }

    overall = sum(pillars[p]["score"] * PILLAR_WEIGHTS[p] for p in PILLARS)
    return {
        "version": 3,
        "overall": _clamp(overall),
        "loc": loc,
        "kloc": round(kloc, 4),
        "pillars": pillars,
        "weights": PILLAR_WEIGHTS,
        "half_score_density": HALF_SCORE_DENSITY,
        "status_factors": {k.value: v for k, v in STATUS_FACTOR.items()},
    }
