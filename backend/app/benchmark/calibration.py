"""Scoring calibration sweep.

The two constants in ``scoring.py`` (``HALF_SCORE_DENSITY`` and
``WORST_PILLAR_HEADROOM``) were set by reasoning about one 83-LOC fixture. Running
the pipeline on a real 12 000-LOC repository showed that is not enough: the curve
scored ``psf/requests`` 96/100 with a worst pillar of 92, which is not a
defensible reading of a codebase carrying 10 import cycles and SHA1-based HMAC
authentication.

Choosing a new constant by anecdote is how the original value got into trouble, so
this module re-scores the *actual findings* of a real analysis across a grid of
candidate values. The output is a table to argue with, not a recommendation.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.analysis_engine.scoring import (
    CATEGORY_PILLAR,
    PILLAR_WEIGHTS,
    PILLARS,
    SEVERITY_WEIGHT,
    STATUS_FACTOR,
)
from app.models import Finding, FindingStatus

# Candidate values, spanning the range that separates "one medium finding per
# KLOC barely matters" (lenient) from "that is half the score" (strict).
DEFAULT_DENSITIES = (25.0, 40.0, 60.0, 100.0, 250.0)
DEFAULT_HEADROOMS = (0, 5, 10, 15, 25)


@dataclass(frozen=True)
class CalibrationRow:
    half_score_density: float
    worst_pillar_headroom: int
    overall: int
    weighted_mean: float
    worst_pillar: int
    capped: bool
    pillars: dict[str, int]


def _weighted_penalty(findings: Sequence[Finding]) -> dict[str, float]:
    penalty = dict.fromkeys(PILLARS, 0.0)
    for finding in findings:
        pillar = CATEGORY_PILLAR.get(finding.category)
        if pillar is None:
            continue
        weight = SEVERITY_WEIGHT.get(finding.severity.value, 0)
        factor = STATUS_FACTOR.get(finding.status, 1.0)
        penalty[pillar] += weight * factor
    return penalty


def score_with(
    penalty: dict[str, float], kloc: float, density: float, headroom: int
) -> tuple[dict[str, int], float, int, bool]:
    """Per-pillar scores and the aggregate for one candidate calibration."""
    pillars = {
        pillar: max(0, min(100, round(100 / (1 + (penalty[pillar] / kloc) / density))))
        for pillar in PILLARS
    }
    weighted_mean = sum(pillars[p] * PILLAR_WEIGHTS[p] for p in PILLARS)
    worst = min(pillars.values())
    overall = min(weighted_mean, worst + headroom)
    return pillars, round(weighted_mean, 2), worst, overall < weighted_mean


def sweep(
    findings: Sequence[Finding],
    loc: int | None,
    densities: Sequence[float] = DEFAULT_DENSITIES,
    headrooms: Sequence[int] = DEFAULT_HEADROOMS,
    min_kloc: float = 0.001,
) -> list[CalibrationRow]:
    """Re-score one run's findings under every candidate calibration."""
    open_findings = [f for f in findings if f.status != FindingStatus.DISMISSED]
    penalty = _weighted_penalty(open_findings)
    kloc = max((loc or 0) / 1000, min_kloc)

    rows: list[CalibrationRow] = []
    for density in densities:
        for headroom in headrooms:
            pillars, mean, worst, capped = score_with(penalty, kloc, density, headroom)
            rows.append(
                CalibrationRow(
                    half_score_density=density,
                    worst_pillar_headroom=headroom,
                    overall=max(0, min(100, round(min(mean, worst + headroom)))),
                    weighted_mean=mean,
                    worst_pillar=worst,
                    capped=capped,
                    pillars=pillars,
                )
            )
    return rows


def current_settings() -> tuple[float, int]:
    from app.analysis_engine.scoring import HALF_SCORE_DENSITY, WORST_PILLAR_HEADROOM

    return HALF_SCORE_DENSITY, WORST_PILLAR_HEADROOM
