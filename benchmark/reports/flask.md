# Benchmark report — `pallets/flask`

Analysis: **#4** · 18352 LOC

Reproduce: `cd backend && python -m app.benchmark --repo pallets/flask --analysis-id 4`

> **No ground truth for this repository.** Recall and precision are not measurable without planted expectations, so they are not reported. What follows is what the run produced and how sensitive the score is to its calibration.

## What the run produced

| Metric | Value |
| --- | --- |
| Findings | 163 open, 0 dismissed |
| Verification coverage | 100% (163 verified / 0 hypothesis) |

| Category | Findings |
| --- | --- |
| code-smell | 1 |
| complexity | 38 |
| docstring | 38 |
| duplication | 8 |
| god-module | 3 |
| import-cycle | 7 |
| inventory | 1 |
| maintainability | 44 |
| missing-tests | 1 |
| readme | 1 |
| secret | 6 |
| vulnerability | 15 |

## Calibration sensitivity

What this run's 163 open findings would score under other calibrations, at 18352 LOC. The shipped values are density 30, headroom 15.

| density \ headroom | 0 | 5 | 10 | 15 | 25 |
| --- | --- | --- | --- | --- | --- |
| 25 | 39 | 44 | 49 | 54 | 64 |
| 40 | 51 | 56 | 61 | 66 | 76 |
| 60 | 61 | 66 | 71 | 76 | 83 |
| 100 | 72 | 77 | 82 | 87 | 88 |
| 250 | 87 | 92 | 95 | 95 | 95 |
