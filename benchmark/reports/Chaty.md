# Benchmark report — `krtk06/Chaty`

Analysis: **#1** · 2565 LOC

Reproduce: `cd backend && python -m app.benchmark --repo krtk06/Chaty --analysis-id 1`

> **No ground truth for this repository.** Recall and precision are not measurable without planted expectations, so they are not reported. What follows is what the run produced and how sensitive the score is to its calibration.

## What the run produced

| Metric | Value |
| --- | --- |
| Findings | 13 open, 0 dismissed |
| Verification coverage | 100% (13 verified / 0 hypothesis) |

| Category | Findings |
| --- | --- |
| coverage | 1 |
| duplication | 6 |
| inventory | 1 |
| readme | 1 |
| secret | 4 |

## Calibration sensitivity

What this run's 13 open findings would score under other calibrations, at 2565 LOC. The shipped values are density 30, headroom 15.

| density \ headroom | 0 | 5 | 10 | 15 | 25 |
| --- | --- | --- | --- | --- | --- |
| 25 | 44 | 49 | 54 | 59 | 69 |
| 40 | 56 | 61 | 66 | 71 | 78 |
| 60 | 66 | 71 | 76 | 81 | 83 |
| 100 | 76 | 81 | 86 | 88 | 88 |
| 250 | 89 | 94 | 95 | 95 | 95 |
