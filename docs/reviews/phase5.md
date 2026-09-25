# Phase 5 — Browser Review Log

**Date:** 2026-09-25
**Method:** agent-browser against the live local stack (API :8110 · Celery worker · Vite :5175 · Postgres :5433 · Redis :6390)
**LLM provider:** `mock` (deterministic offline harness — same caveat as Phase 4: pipeline exercised, findings not real model output)

## Flow verified (seedy benchmark repo, analysis #17)

1. Analysis `done` with the header showing **"1 pending review"**; Health Score and the
   **Human Approval Queue** render below.
2. Queue shows high-severity hypotheses with severity badge, agent, verifier, calibrated
   confidence, low-confidence marker, file:line, and the historical acceptance rate for
   that agent/category.
3. Clicked **Review** → inline note field + **Approve / Dismiss / Cancel**.
4. Entered a note and clicked **Dismiss** → the queue flips to **published**
   ("All high-severity hypotheses have been reviewed"), the header badge clears, and the
   finding becomes `dismissed` (weight 0).
5. Console: 0 errors. Screenshots: `docs/reviews/phase5-queue.png`, `phase5-review.png`, `phase5.png`.

## Backend verification (API level)

- `GET /analyses/{id}` → `published`, `pending_approvals`.
- `GET /analyses/{id}/approvals/queue` → pending items with calibrated confidence.
- `POST /analyses/{id}/approvals`:
  - **approve** → finding promoted to `verified`, confidence raised (0.45 → 0.9),
    `pending_count` 0, `published` true; testing pillar moves `1v/0h`;
  - **dismiss** → finding `dismissed`, `published` true.
- `GET /calibration/stats` → `tests/test-plan` shown=3, accepted=1, dismissed=2,
  `acceptance_rate=0.333` (**feedback loop confirmed**).

## Trust-layer behaviour on the seedy repo

- **Verification** (deterministic re-checks of LLM claims):
  - SQL injection → `verified:source-pattern`;
  - architecture layering → `verified:graph-cycle` (cycle confirmed in symbol graph);
  - docs docstring-plan → `verified:docstring-check`;
  - code complexity insight → `verified:citation`;
  - the planted sha1 false positive stays **dismissed** (Code Agent triage);
  - unverifiable plans stay **hypothesis**.
- **Calibration**: verified findings ≈ 0.76–0.81 (history + corroboration), unverified
  LLM-only hypotheses capped at **0.45** (`LLM_ONLY_CAP`).
- **Honest score v2**: `{verified, hypotheses, dismissed, weighted_penalty}` per pillar;
  hypotheses count ×0.5, dismissed ×0.

## Bugs found during the phase

| Issue | Root cause | Resolution |
|-------|-----------|------------|
| Ingestion finding confidence changed 1.0 → 0.8 | calibration now runs on every finding | expected; Phase 1 assertion updated |
| Security injection finding became `verified` | verifier confirmed the SQL pattern | expected and desired; seedy acceptance test updated to assert `verified:source-pattern` |
| Browser `Review` button not visible to the a11y snapshot | button text was present but the queue list was below the fold for the ref snapshot | invoked via DOM click; UI interaction itself is correct (no code change) |

## Notes / limitations

- Publish gating applies to severity ≥ high hypotheses. Medium/low hypotheses remain
  `hypothesis` and are scored at half weight but do not block publication.
- `published` is a column (migration 0004) rather than a status value, so the pipeline
  status stays `done` while publication is gated.
- Verification coverage is intentionally conservative: it promotes a claim only when a
  deterministic signal corroborates it.

## Acceptance criteria status

- [x] Plant one true and one false LLM finding: verifier marks the true one verified and
      leaves the false one a hypothesis (see `test_trust_layer.py`)
- [x] Dismissing a finding changes the category acceptance rate and affects subsequent
      confidence (`acceptance_rate=0.333`; `history_rate` feeds calibration)
- [x] Score API shows the verified/hypothesis (and dismissed) split
- [x] Approval queue approve/dismiss end-to-end in the browser; analysis publishes when
      gates clear
- [x] No console errors
