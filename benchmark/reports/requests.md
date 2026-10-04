# Benchmark report — `psf/requests`

Analysis: **#5** · 12032 LOC

Reproduce: `cd backend && python -m app.benchmark --repo psf/requests --analysis-id 5`

> **No ground truth for this repository.** Recall and precision are not measurable without planted expectations, so they are not reported. What follows is what the run produced and how sensitive the score is to its calibration.

## What the run produced

| Metric | Value |
| --- | --- |
| Findings | 63 open, 0 dismissed |
| Verification coverage | 100% (63 verified / 0 hypothesis) |

| Category | Findings |
| --- | --- |
| complexity | 15 |
| docstring | 7 |
| duplication | 2 |
| god-module | 2 |
| import-cycle | 10 |
| inventory | 1 |
| maintainability | 17 |
| missing-tests | 1 |
| readme | 1 |
| secret | 4 |
| vulnerability | 3 |

## Calibration sensitivity

What this run's 63 open findings would score under other calibrations, at 12032 LOC. The shipped values are density 30, headroom 15.

| density \ headroom | 0 | 5 | 10 | 15 | 25 |
| --- | --- | --- | --- | --- | --- |
| 25 | 52 | 57 | 62 | 67 | 77 |
| 40 | 64 | 69 | 74 | 79 | 83 |
| 60 | 72 | 77 | 82 | 87 | 88 |
| 100 | 81 | 86 | 91 | 92 | 92 |
| 250 | 92 | 96 | 96 | 96 | 96 |
