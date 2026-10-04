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

v4: the overall is no longer a bare weighted mean. Five healthy pillars could
average away one catastrophic one, so the overall is capped at
``worst_pillar + WORST_PILLAR_HEADROOM``. Both calibration constants are exported
and covered by tests in ``tests/test_scoring_curve.py``.

Formula: per-pillar score = 100 / (1 + weighted_penalty / KLOC / HALF_SCORE_DENSITY)
        overall       = min(Σ pillar×weight, min(pillar) + WORST_PILLAR_HEADROOM)
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
# constant for the whole curve.
#
# History: 250 until the pipeline ran on a real repository rather than only the 83-LOC
# fixture; then 100, chosen from a single run. Both were too lenient once measured
# against several repositories at once, because one run cannot show where the curve
# should bend.
#
# Recalibrated against five real repositories — krtk06/Chaty, psf/requests,
# pallets/click, pallets/flask, encode/httpx — whose worst-pillar densities land in a
# tight band of 22–39 weighted points per KLOC:
#
#   HALF   Chaty  requests  click  flask  httpx   (overall)
#     25      59       67     58     54     54
#     30      64       72     62     59     59
#     35      68       75     66     62     63
#    100      88       92     90     87     87
#
# At 100 every repository scored in the high eighties or above: Chaty's 4 high-severity
# security findings read as 88/100, which is not a number a reader should act on. At 30
# the median repository's weakest dimension sits near half marks (worst pillars 44–57)
# and overalls land in the high fifties to low seventies — uncomfortable, and honest
# about what the analyzers actually found. benchmark/REPORT.md holds the per-repository
# reports and this table.
#
# Only the benchmark should move it, and moving it invalidates every stored score.
# `tests/test_scoring_curve.py` pins the behaviour relative to this constant rather than
# to literals, and `app/benchmark/calibration.py` shows the trade-off.
HALF_SCORE_DENSITY = 30.0

# How far above its worst pillar the overall may sit. A weighted mean alone lets
# five healthy pillars average away one catastrophic one — a repository with
# secrets and no tests still read as "mostly fine". The cap keeps the mean as the
# headline while making sure the weakest dimension is visible in it.
#
# The two constants partly substitute for each other: a stricter curve lowers the
# mean on its own, which is why this one was left at 15.
WORST_PILLAR_HEADROOM = 15

# Guards division by zero for an unknown or empty LOC. Not a density assumption:
# with the ratio curve a small denominator no longer saturates the score.
MIN_KLOC = 0.001

# Weighted finding-points at which a pillar scores 50 when the repository has no LOC
# measurement, so density cannot be computed.
#
# Density is the right basis only when the denominator was actually measured. The
# indexer stores `loc = 0` when it indexes nothing — a repository of one README, or
# a language it does not recognise — and dividing by MIN_KLOC then yields densities in
# the tens of thousands, so two trivial findings ("no test suite", "no README") scored
# a repository 15/100, while 13 findings including 4 high-severity security hits on a
# real 2,565-line repository scored 88. Both numbers were artefacts of the denominator.
#
# So a missing LOC switches basis instead of substituting a tiny one: the same ratio
# curve over raw weighted finding-points. It stays monotonic and saturating, and the
# payload records which basis produced the number so a reader is never misled about
# comparing a count-scored repository with a density-scored one.
#
# 20 points is roughly two high-severity or four medium findings, which reads as
# "half marks" for a repository too small to measure.
COUNT_HALF_SCORE_PENALTY = 20.0


def _clamp(value: float, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, round(value)))


def _pillar_score(weighted_penalty: float, kloc: float) -> int:
    """Ratio curve: 100 with no findings, 50 at HALF_SCORE_DENSITY, asymptotic to 0."""
    density = weighted_penalty / kloc
    return _clamp(100 / (1 + density / HALF_SCORE_DENSITY))


def _pillar_score_by_count(weighted_penalty: float) -> int:
    """Ratio curve over raw weighted points, for a repository with no LOC measurement.

    Same shape as the density curve so the aggregation, the worst-pillar cap, and the
    direction of every comparison are unchanged; only the denominator differs.
    """
    return _clamp(100 / (1 + weighted_penalty / COUNT_HALF_SCORE_PENALTY))


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

    # A measured LOC means density is meaningful. An absent one does not, and the old
    # MIN_KLOC floor turned "unmeasured" into a density of tens of thousands, so
    # switch basis to raw weighted points rather than invent a denominator.
    basis = "density" if loc else "count"
    kloc = (loc / 1000) if loc else None
    pillars = {}
    for pillar in PILLARS:
        penalty = pillar_penalty[pillar]
        if kloc is not None:
            pillar_score = _pillar_score(penalty, kloc)
        else:
            pillar_score = _pillar_score_by_count(penalty)
        # A pillar with findings never reports 0. The curve is asymptotic, so a strict
        # calibration rounds the worst cases down to 0, which reads as "clean" rather
        # than "catastrophic" and is indistinguishable from a pillar nothing was measured
        # on unless the reader also checks the finding count. 1 is the floor: still
        # terrible, still ordered, never ambiguous.
        if penalty > 0:
            pillar_score = max(1, pillar_score)
        pillars[pillar] = {
            "score": pillar_score,
            "findings": pillar_counts[pillar],
            "verified": pillar_verified[pillar],
            "hypotheses": pillar_hypotheses[pillar],
            "dismissed": pillar_dismissed[pillar],
            "weighted_penalty": round(penalty, 2),
        }

    weighted_mean = sum(pillars[p]["score"] * PILLAR_WEIGHTS[p] for p in PILLARS)
    worst_pillar = min(pillars[p]["score"] for p in PILLARS)
    # An unmeasured pillar scores 100, so it can never lower the cap.
    overall = min(weighted_mean, worst_pillar + WORST_PILLAR_HEADROOM)
    return {
        "version": 5,
        "overall": _clamp(overall),
        "loc": loc,
        "kloc": round(kloc, 4) if kloc is not None else None,
        "basis": basis,
        "count_half_score_penalty": COUNT_HALF_SCORE_PENALTY,
        "pillars": pillars,
        "weights": PILLAR_WEIGHTS,
        "half_score_density": HALF_SCORE_DENSITY,
        "worst_pillar_headroom": WORST_PILLAR_HEADROOM,
        "worst_pillar": worst_pillar,
        "weighted_mean": round(weighted_mean, 2),
        "status_factors": {k.value: v for k, v in STATUS_FACTOR.items()},
    }
