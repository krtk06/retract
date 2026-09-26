# Benchmark report — `seedy-python-app`

Analysis: **#18**

Reproduce: `cd backend && python -m app.benchmark --repo seedy-python-app --analysis-id 18`

## Headline

| Metric | Value |
| --- | --- |
| Recall (grounded expectations found) | **100%** (10/10) |
| Precision (grounded) | **62%** (10/16) |
| Precision (deduplicated) | **91%** (10 matched, 1 unenumerated, 5 duplicate) |
| F1 (grounded) | **0.77** |
| Precision (strict, all open findings) | 40% |
| Verification coverage | 92% (23 verified / 2 hypothesis) |
| Findings | 25 open, 1 dismissed |

## Per category

| Category | Expected | Recalled | Recall | Open | Matched | Precision |
| --- | --- | --- | --- | --- | --- | --- |
| complexity | 1 | 1 | 100% | 1 | 1 | 100% |
| complexity-review | 0 | 0 | — | 0 | 0 | 1 unreviewed |
| coverage | 1 | 1 | 100% | 1 | 1 | 100% |
| docstring | 1 | 1 | 100% | 1 | 1 | 100% |
| docstring-plan | 0 | 0 | — | 0 | 0 | 1 unreviewed |
| duplication | 1 | 1 | 100% | 1 | 1 | 100% |
| import-cycle | 1 | 1 | 100% | 1 | 1 | 100% |
| injection | 0 | 0 | — | 0 | 0 | 1 unreviewed |
| inventory | 0 | 0 | — | 0 | 0 | 1 unreviewed |
| layering | 0 | 0 | — | 0 | 0 | 1 unreviewed |
| maintainability | 0 | 0 | — | 0 | 0 | 1 unreviewed |
| outdated-dependency | 1 | 1 | 100% | 2 | 1 | 50% |
| readme | 1 | 1 | 100% | 1 | 1 | 100% |
| readme-plan | 0 | 0 | — | 0 | 0 | 1 unreviewed |
| secret | 1 | 1 | 100% | 3 | 1 | 33% |
| test-plan | 0 | 0 | — | 0 | 0 | 1 unreviewed |
| vulnerability | 1 | 1 | 100% | 3 | 1 | 33% |
| vulnerable-dependency | 1 | 1 | 100% | 2 | 1 | 50% |
| weak-crypto | 0 | 0 | — | 0 | 0 | 1 unreviewed |

## Duplicate reports

5 open finding(s) repeat a condition another finding already covers (same category and file). These are not new problems, but they are noise a reviewer has to read past:

- finding #597
- finding #599
- finding #609
- finding #614
- finding #615

## Not covered by this ground truth

These categories produced findings but are not enumerated in the ground-truth file, so they are excluded from precision. Add them to make the numbers tighter:

- `complexity-review` (1 finding)
- `docstring-plan` (1 finding)
- `injection` (1 finding)
- `inventory` (1 finding)
- `layering` (1 finding)
- `maintainability` (1 finding)
- `readme-plan` (1 finding)
- `test-plan` (1 finding)
- `weak-crypto` (1 finding)

## How to read this

- **Recall** is the number to improve by adding analyzers: an expectation with no matching finding is a gap in coverage.
- **Precision (grounded)** is the number to quote. Only categories the ground truth enumerates are counted, so an incomplete ground-truth file lowers precision (strict), not precision (grounded).
- A finding is matched by category, then file, then line within a small tolerance (tools cite the enclosing symbol or block). A dismissed finding never counts as detected — including for planted false positives, which are expected to be dismissed.
