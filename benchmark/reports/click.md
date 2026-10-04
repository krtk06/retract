# Benchmark report — `pallets/click`

Analysis: **#3** · 30181 LOC

Reproduce: `cd backend && python -m app.benchmark --repo pallets/click --analysis-id 3`

> **No ground truth for this repository.** Recall and precision are not measurable without planted expectations, so they are not reported. What follows is what the run produced and how sensitive the score is to its calibration.

## What the run produced

| Metric | Value |
| --- | --- |
| Findings | 164 open, 0 dismissed |
| Verification coverage | 100% (164 verified / 0 hypothesis) |

| Category | Findings |
| --- | --- |
| code-smell | 2 |
| complexity | 49 |
| docstring | 31 |
| duplication | 17 |
| god-module | 2 |
| import-cycle | 6 |
| inventory | 1 |
| maintainability | 52 |
| missing-tests | 1 |
| readme | 1 |
| vulnerability | 2 |

## Calibration sensitivity

What this run's 164 open findings would score under other calibrations, at 30181 LOC. The shipped values are density 30, headroom 15.

| density \ headroom | 0 | 5 | 10 | 15 | 25 |
| --- | --- | --- | --- | --- | --- |
| 25 | 43 | 48 | 53 | 58 | 68 |
| 40 | 54 | 59 | 64 | 69 | 79 |
| 60 | 64 | 69 | 74 | 79 | 89 |
| 100 | 75 | 80 | 85 | 90 | 93 |
| 250 | 88 | 93 | 97 | 97 | 97 |
