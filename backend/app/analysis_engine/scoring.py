"""Health score computation.

v2 (Decision D8): honest weighting by verification status.
  - verified findings count at full severity weight;
  - hypothesis findings count at half weight;
  - dismissed findings count zero.

Formula: per-pillar score = 100 − Σ effective_weight / KLOC × SCALE, clamped [0,100].
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

SCALE = 2.0  # penalty per KLOC multiplier; one medium per KLOC costs ~2 points


def _clamp(value: float, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, round(value)))


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

    kloc = max((loc or 0) / 1000, 0.1)
    pillars = {}
    for pillar in PILLARS:
        penalty_per_kloc = pillar_penalty[pillar] / kloc
        pillars[pillar] = {
            "score": _clamp(100 - penalty_per_kloc * SCALE),
            "findings": pillar_counts[pillar],
            "verified": pillar_verified[pillar],
            "hypotheses": pillar_hypotheses[pillar],
            "dismissed": pillar_dismissed[pillar],
            "weighted_penalty": round(pillar_penalty[pillar], 2),
        }

    overall = sum(pillars[p]["score"] * PILLAR_WEIGHTS[p] for p in PILLARS)
    return {
        "version": 2,
        "overall": _clamp(overall),
        "loc": loc,
        "kloc": round(kloc, 2),
        "pillars": pillars,
        "weights": PILLAR_WEIGHTS,
        "scale": SCALE,
        "status_factors": {k.value: v for k, v in STATUS_FACTOR.items()},
    }
