# Benchmark report — `octocat/Hello-World`

Analysis: **#2** · 0 LOC

Reproduce: `cd backend && python -m app.benchmark --repo octocat/Hello-World --analysis-id 2`

> **No ground truth for this repository.** Recall and precision are not measurable without planted expectations, so they are not reported. What follows is what the run produced and how sensitive the score is to its calibration.

## What the run produced

| Metric | Value |
| --- | --- |
| Findings | 3 open, 0 dismissed |
| Verification coverage | 100% (3 verified / 0 hypothesis) |

| Category | Findings |
| --- | --- |
| coverage | 1 |
| inventory | 1 |
| readme | 1 |

## Calibration sensitivity

What this run's 3 open findings would score under other calibrations, at 0 LOC. The shipped values are density 30, headroom 15.

| density \ headroom | 0 | 5 | 10 | 15 | 25 |
| --- | --- | --- | --- | --- | --- |
| 25 | 0 | 5 | 10 | 15 | 25 |
| 40 | 0 | 5 | 10 | 15 | 25 |
| 60 | 0 | 5 | 10 | 15 | 25 |
| 100 | 0 | 5 | 10 | 15 | 25 |
| 250 | 1 | 6 | 11 | 16 | 26 |
