# Phase 9 browser review — the retract skill and the Fix with your agent button

Dev stack: `scripts/dev-local.sh` (api :8110, eve :3000, vite :5177), dev login.
Scope: every user-facing feature, end to end, including a real pipeline run.

## What was verified

| Feature | Result | Notes |
| --- | --- | --- |
| Login page renders, dev login works | pass | header shows "Retract", email/password + GitHub buttons present |
| Dashboard: recent analyses feed | pass | score, findings count, LOC, time, Re-analyze per row |
| Dashboard row → analysis navigation | pass | the first CDP click did not take (automation quirk — trusted clicks on this element were swallowed); a JS-level click navigates to `/analyses/{id}` correctly. Not an app defect. |
| Score hero | pass | 11/100, delta −89, `83 LOC · 0.083 KLOC`, six pillar bars with v/h/d counts |
| Findings table | pass | pillar grouping, filters by pillar/severity/ingestion |
| Finding expansion → snippet | pass | cited line rendered with line numbers |
| **Fix with your agent button** | **pass** | click → `Copied ✓`; clipboard contents inspected (below) |
| Button clipboard (no snippet) | pass | 956 chars: install command, skill invocation, instruction (catalog action "Rotate the exposed credential"), full finding line (id 595, category secret, pillar security, verified, conf 0.81, verifier tool:gitleaks, agent security), title, description, `Cited location: app/settings.py:1-1`, evidence JSON with calibration block |
| Button clipboard (row expanded) | pass | 1098 chars, snippet included with true line numbers |
| Dismissed finding | pass | button replaced by a non-interactive "fix with your agent" span (planted false positive) |
| Fixes tab (remediation plan) | pass | 11 → 100 headline, 18 work items, quickest wins, honest cap note |
| `Download .md` | pass | `GET /api/analyses/18/remediation.md` → 200 with cookie, 401 bare: "Fix plan — local/seedy-python-app", headline table, work items |
| Explore tab | pass | 17 symbols / 18 edges; symbol browser; dependency view for `find_user` (leaf, no resolved links — correct) |
| Agent tab (chat) | pass with note | chat UI, session, message sent; the model call failed with "Your account is not active" — the user's OpenAI billing, not the app. The failure renders honestly in the chat. |
| HITL approval queue | pass | "Establish a test suite…" hypothesis with low-confidence badge and 33% acceptance history → Approve → analysis published |
| History A/B compare | pass | #21 → #22: overall 11 → 100 (+89), per-pillar deltas table |
| Repos page: add + analyze | pass | `local://`seedy fixture → pipeline ran: clone → index 17 symbols → gitleaks, deps, complexity, duplication, tests, docs, architecture, semgrep (9.57s) → verify → calibrate → done, SSE progress live |
| Fresh analysis score | pass | 11/100 (−89 vs previous), 17 findings, all pillars, 16 fix buttons |

## The full captured fix brief

```
# Retract

If the retract skill is not installed:
  npx skills add krtk06/retract --skill retract

Use the retract skill to resolve this finding. When you are done, tell me to
push and re-analyze so I can see the score move.

## Instruction
Rotate the exposed credential

## Finding
Retract analysis #18 of local/seedy-python-app @ local
finding_id: 595 · category: secret · pillar: security · severity: high ·
status: verified · confidence: 0.81 · verifier: tool:gitleaks · agent: security
effort: low · source: catalog

Title: Hardcoded secret (aws-access-token)

Identified a pattern that may indicate AWS credentials, …

Cited location: app/settings.py:1-1

Evidence: { rule, tool, calibration{samples, effective, corroborated, …} }
```

## Environment-only findings (not defects)

1. The eve chat model call fails with OpenAI "account is not active" — billing,
   not code. The dual failure path (3 retries → honest error in the chat) works.
2. `scripts/dev-local.sh stop` kills uvicorn regardless of `SKIP_*` flags, and
   its `start_frontend` vite lost the port to the user's portfolio dev server.
   Worked around for this review by running the frontend on :5177 manually.
3. `npm run eval` hung once against a stale eve dev server; clean, it runs in
   6.7s (10 passed, 33 gates).

## Screenshots

- `phase9-fix-button.png` — findings table with the button
- `phase9-fix-plan.png` — the fix plan the button feeds from
