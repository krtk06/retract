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

## Large-repository pass — `encode/httpx` (17 753 LOC)

The first pass used the 83-LOC fixture. A 17.7K-LOC repository was analyzed
fresh through the whole pipeline (clone → index → 8 tools → verify → calibrate →
score) to check nothing only holds at fixture scale.

| Step | Result |
| --- | --- |
| Fresh run | analysis #32, commit `b5addb6`, `done` in 35 s, 157 findings |
| Score | 59/100, `basis: density`, 17.753 KLOC, worst pillar 44 (code-quality) |
| The cap in action | weighted mean 76.2, worst 44 → overall 59 = 44 + 15. Matches the README calibration table for httpx exactly |
| Pillar honesty | Testing shows `—` / "not measured" — httpx produces no testing findings, and the UI refuses to call that clean |
| Findings table | 99 rows rendered (ingestion/meta hidden by default), 99 fix buttons, grouping and filters intact |
| Snippet on a real source file | fetched and rendered with true line numbers |
| Fix plan | 11 work items, 156 findings, +41 projected, quickest wins ranked by payoff |
| Fix brief on a large finding | longest brief 1 516 chars; the 4 000-char evidence cap correctly stayed dormant (a vulnerable-dependency finding carried its advisory IDs whole) |
| Determinism | A/B of #32 against the 4-day-old #25 on the same commit: overall 59 → 59 and every pillar delta `—`. Same commit, same numbers |

Screenshots from this pass are not committed; the run is reproducible from the
repo list with Re-analyze.

## Dogfood: the skill fixing a live Retract finding

The feature was built and its button verified, but it had not been *used*. So:
a scratch repository (`/tmp/opencode/retract-demo`, the fixture with its planted
defects, its own git history and a bare origin) was registered as `local://`,
analyzed (#33), and one finding taken through the whole loop.

1. **Install** — `npx skills add krtk06/retract --skill retract` from GitHub
   reported *no skills found*: correct, the skill is on a branch and not yet on
   `main`. Installing from the local skill folder put all four files in
   `~/.agents/skills/retract/`.
2. **Brief** — the button's clipboard text on analysis #33, for semgrep
   `formatted-sql-query` at `app/db.py:10`.
3. **Fix** — a fresh agent with *no context* except `~/.agents/skills/retract/`
   and that clipboard text. It confirmed the claim by running the pre-fix
   payload against SQLite (`alice' OR '1'='1` returned the row), made a two-line
   parameterised fix, ran `py_compile`, declined to invent a test framework (no
   suite exists; adding one would have moved the testing pillar and polluted
   the A/B), cited `categories.md` §vulnerability and `verification.md` for why
   the fix survives re-analysis, predicted the headline might not move, and
   handed back without committing — the skill's exit path, honoured.
4. **Push and re-analyze** — reviewed, committed, pushed, clicked Re-analyze.

| | #33 before | #34 after |
| --- | --- | --- |
| Findings | 17 | **15** |
| Security pillar | 2 (penalty 120) | **3** (penalty 90) |
| Overall | 11 | **11** |
| Weighted mean | 10.60 | 10.85 |

Cleared: `formatted sql query` *and* `sqlalchemy execute raw query` — the same
two semgrep rules on the same line, both matched by the construct the fix
removed. New findings: **none**. The overall did not move, and that is the
scoring model working rather than failing: on an 83-LOC repository the
weighted mean (10.85) is below the worst-pillar cap (18), so a single
medium-severity fix raises the pillar and leaves the headline alone. The
fresh agent predicted this from `scoring.md` alone, without seeing the score.

Two things this exposes for the product:

1. On very small repositories no single fix can move the headline, and the UI
   says so only implicitly (per-item "+N pts" is a pillar gain). The skill
   explains it; the score hero does not.
2. The install command only works after the skill is on `main` — as shipped,
   the button's `npx skills add krtk06/retract --skill retract` reports "no
   skills found" on an unmerged branch. Expected, but worth remembering when
   reading "install the skill" before this merges.

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
