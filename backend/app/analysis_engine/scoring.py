"""Health score computation (v1, deterministic).

Formula (per implementation.md Phase 2): per-pillar score =
100 − Σ severity_weight(finding) normalized per KLOC, clamped [0, 100].
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Analysis, Finding

SEVERITY_WEIGHT = {"critical": 30, "high": 20, "medium": 10, "low": 5, "info": 0}

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

    rows = session.execute(
        select(Finding.category, Finding.severity, func.count(Finding.id))
        .where(Finding.analysis_id == analysis_id)
        .group_by(Finding.category, Finding.severity)
    ).all()

    pillar_penalty: dict[str, float] = {p: 0.0 for p in PILLARS}
    pillar_counts: dict[str, int] = {p: 0 for p in PILLARS}
    pillar_verified: dict[str, int] = {p: 0 for p in PILLARS}
    for category, severity, count in rows:
        pillar = CATEGORY_PILLAR.get(category)
        if pillar is None:
            continue
        weight = SEVERITY_WEIGHT.get(severity, 0)
        pillar_penalty[pillar] += weight * count
        pillar_counts[pillar] += count
        pillar_verified[pillar] += count  # v1: tool findings are all verified

    kloc = max((loc or 0) / 1000, 0.1)
    pillars = {}
    for pillar in PILLARS:
        penalty_per_kloc = pillar_penalty[pillar] / kloc
        pillars[pillar] = {
            "score": _clamp(100 - penalty_per_kloc * SCALE),
            "findings": pillar_counts[pillar],
            "verified": pillar_verified[pillar],
            "hypotheses": 0,
        }

    overall = sum(pillars[p]["score"] * PILLAR_WEIGHTS[p] for p in PILLARS)
    return {
        "version": 1,
        "overall": _clamp(overall),
        "loc": loc,
        "kloc": round(kloc, 2),
        "pillars": pillars,
        "weights": PILLAR_WEIGHTS,
        "scale": SCALE,
    }
