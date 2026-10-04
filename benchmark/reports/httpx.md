# Benchmark report — `encode/httpx`

Analysis: **#6** · 17753 LOC

Reproduce: `cd backend && python -m app.benchmark --repo encode/httpx --analysis-id 6`

> **No ground truth for this repository.** Recall and precision are not measurable without planted expectations, so they are not reported. What follows is what the run produced and how sensitive the score is to its calibration.

## What the run produced

| Metric | Value |
| --- | --- |
| Findings | 157 open, 0 dismissed |
| Verification coverage | 100% (157 verified / 0 hypothesis) |

| Category | Findings |
| --- | --- |
| code-smell | 2 |
| complexity | 31 |
| docstring | 37 |
| duplication | 9 |
| god-module | 3 |
| import-cycle | 10 |
| inventory | 1 |
| maintainability | 43 |
| outdated-dependency | 11 |
| readme | 1 |
| vulnerability | 6 |
| vulnerable-dependency | 3 |

## Calibration sensitivity

What this run's 157 open findings would score under other calibrations, at 17753 LOC. The shipped values are density 30, headroom 15.

| density \ headroom | 0 | 5 | 10 | 15 | 25 |
| --- | --- | --- | --- | --- | --- |
| 25 | 39 | 44 | 49 | 54 | 64 |
| 40 | 51 | 56 | 61 | 66 | 76 |
| 60 | 61 | 66 | 71 | 76 | 85 |
| 100 | 72 | 77 | 82 | 87 | 90 |
| 250 | 87 | 92 | 95 | 95 | 95 |
