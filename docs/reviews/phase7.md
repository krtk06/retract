# Phase 7 — Browser Review Log (eve migration)

**Date:** 2026-09-25
**Method:** agent-browser against the live local stack (redis :6390 · API :8110 · Celery
worker · eve agent :3000 · Vite :5175 · Postgres :5433), plus `npm run eval` for the
agent suite.
**Model:** `AI_INTEL_LLM_PROVIDER=mock` (deterministic fixture model — see
"Limits of this review" below).

## Flows verified

1. **Live agent round trip over HTTP.** `POST /api/auth/eve-token` (cookie session →
   `iss=ai-intel`, `aud=eve-agent` bearer) → `POST /eve/v1/session` (202) →
   `GET /eve/v1/session/:id/stream`. The agent called `get_analysis`, the tool reached
   the real API with `X-Agent-Token`, and a missing analysis surfaced as a
   `404` in the transcript instead of a fabricated answer.
2. **Findings intake against the real backend.** `POST /api/analyses/17/findings` with a
   cited claim → `inserted: 1`, stored as `HYPOTHESIS` with `verifier: llm:eve`,
   confidence recalibrated `0.6 → 0.65`, score recomputed, and the analysis
   **unpublished** because a high-severity hypothesis was now pending. The
   approval endpoint then dismissed it and the analysis republished — the full
   trust loop, end to end, on real data.
3. **Chat tab** (`docs/reviews/phase7-agent-chat.png`): user and assistant turns, the
   tools-called chips row, and a real streamed reply.
4. **HITL approval** (`docs/reviews/phase7-approval.png`): asking the agent to re-analyze
   parked the turn on an inline "Approve tool call: run_analysis" prompt with
   Approve/Cancel. Nothing hit the API before the click.
5. **HITL cancellation** (`docs/reviews/phase7-after-cancel.png`): clicking Cancel rendered
   `⊘ run_analysis was not approved` and the gated action never ran.
6. **Cost-ledger removal:** `AgentCostPanel` and `Analysis.cost_json` are gone; the
   migration `0005` drops the column. No dangling references.

## Bugs found and fixed during the phase

1. **Silent send when the token was not yet issued.** The first click after page load
   did nothing: `useEveAgent` captured `auth: undefined` when the store was created and
   the guard dropped the message. Fixed by passing a *resolver* (`{ bearer: () => … }`),
   which eve calls per request — the agent now authorizes itself, and an expiring token
   refreshes without rebuilding the client.
2. **Fixture model was turn-naive.** The scripted fixtures branched on
   `request.toolResults.length`, which is cumulative over the whole session, so in a
   multi-turn conversation the second turn skipped its first tool call. Found by
   clicking through the UI, then pinned by a new eval (`smoke/multi-turn`) that counts
   steps from the prompt's trailing `tool` messages instead.
3. **Empty assistant rows and silent tool failures.** The renderer ignored message
   parts with no text, and only drew successful tool calls, so a failed call looked
   like an unsupported claim. Now every dynamic-tool state renders
   (`✓`/`✗ … failed`/`⊘ … was not approved`/`…`) and empty messages are dropped.
4. **Approval clicks that lie.** The fixture's canned reply claimed "Started analysis
   43" even after a human cancelled. The fixture now reads the last tool result and
   acknowledges the refusal — a demo that misreports a denial teaches the wrong thing.
5. **Sandbox selection broke builds on Docker-less hosts.** `DefaultSandbox` fell
   through to `microsandbox`, which is not bundled, so `eve build` and `eve eval`
   failed. The agent declares `just-bash` (pure JS, no container) — it needs no
   sandbox for analysis anyway.
6. **Local stack was four commands and two of them wrong.** `dev-local.sh` did not
   start the frontend or the agent, and Vite proxied `/api` to `:8000` because
   `VITE_API_PROXY` was unset. One command now starts redis, api, worker, agent, and
   frontend with the right proxy targets.
7. **Stale closures in `evals.config.ts`.** Evals shared one fixture API, so
   concurrent runs interleaved in its request log and assertions saw each other's
   calls. Each eval now marks the log on entry and asserts on its own delta, and the
   suite runs serially (it is ~5s).

## Checks at review time

| Check | Result |
| --- | --- |
| backend `ruff check` / `format` / `mypy` / `pytest` | clean · 56 passed |
| frontend `lint` / `typecheck` / `test` / `build` | clean · 1 passed · initial chunk 245 kB (agent lazy-loaded) |
| agent `typecheck` / `build` | clean · 0 diagnostics, 26 tools, 5 subagents |
| agent `npm run eval` | 9 evals, 30 gates, all passing, no credentials |
| agent `eve build` | 18.1 MB output (5.2 MB gzip) |
| `docker compose config` | valid (`agent` service included) |

## Second pass — desktop width (1280px), after the first round of fixes

Re-ran the whole flow at 1280x900 (the first pass used a ~390px window, which
stacked the layout and hid width problems).

| Check | Result |
| --- | --- |
| `/analyses/18` Overview at 1280px | score hero, six pillar bars, approval queue, findings — no overflow |
| Explore tab after RAG removal | graph summary (17 symbols / 10 calls / 8 imports), symbol filter, dependency drill-down works; **no search box**, as intended |
| Agent tab at 1280px | tool chips, failed tool call in red with the real error, honest assistant reply |
| Approval → approve | tool attempted after approval, 404 surfaced, agent did **not** claim success |
| `h1` per page | `/analyses/:id` 1, `/` 1 — `/repos` had **0**, fixed with a visually-hidden `h1` |
| Horizontal overflow | none on any page |
| Console errors | 0 |

### Two more bugs found and fixed

8. **The fixture contradicted its own tool output.** After a visible
   `404 /api/analyses/42`, the scripted reply still said "Analysis 42 is done:
   3 findings, overall 71, published." The same class as the cancellation bug
   above, missed for the read-only scripts. Every script now derives its final
   line from the last tool result, so a failed call produces a failure message.
9. **`/repos` had no `<h1>`.** Pre-existing (Phase 6 fixed the analysis page only),
   caught by checking heading structure on every route rather than one.

## Follow-up: the score curve (`docs/reviews/phase7-score-v3.png`)

The review above flagged that every local analysis scored 0/100. Investigated and
fixed — it was a real defect, not a small-repo quirk.

**v2 was saturating.** `100 − density × 2.0`, clamped at 0, with a 0.1-KLOC floor.
A single medium finding scored a repo 0 below ~230 LOC and 96 at 5 000 LOC, so the
number carried no information about how bad the code was. `SCALE = 2.0` also
contradicted its own comment ("one medium per KLOC costs ~2 points" implies 0.2).

**v3** scores `100 / (1 + density / HALF_SCORE_DENSITY)` — one exported constant
(250 weighted points per KLOC = the density that scores 50), no hard clamp.

**v4** caps the overall at `worst_pillar + 15`, because a weighted mean let five
healthy pillars average away a catastrophic one.

Same 19 real findings from analysis 18, at four repo sizes:

| LOC | v2 | v3 | v4 | worst pillar |
| --- | --- | --- | --- | --- |
| 83 (seedy) | 0 | 37 | **27** | security 12 |
| 500 | 9 | 73 | 57 | security 42 |
| 2 000 | 55 | 90 | 90 | security 75 |
| 20 000 | 94 | 99 | 99 | security 97 |

Covered by `backend/tests/test_scoring_curve.py` (11 cases: monotonicity, density
ordering, the discounting rules, the half-score constant, and the cap).

Two consequences handled rather than left dangling:
- Deltas are suppressed across curve versions, so a v2 and a v4 score are never
  subtracted from each other (`test_score_delta_is_suppressed_across_curve_versions`).
- The detail page now reads `/score` rather than only the cached `score_json`, so
  an analysis whose finalize step never cached a score still shows one.
  `useScore` existed but was never called.

**Known limit of the cap:** at 2 000 LOC, security 75 plus 15 headroom equals the
weighted mean, so the cap does not bite and the overall stays 90. A repository
with ~5 high-severity findings per KLOC therefore still reads as "mostly fine".
Tightening `WORST_PILLAR_HEADROOM` is a one-constant change; left at 15 because
that is the value agreed, and the benchmark (the remaining Phase 7 item) is what
should provide evidence to move it.

- **The pending review item is fixture data** ("Establish a test suite before
  adding features", from the deleted mock-agent run), not a live finding.

## Limits of this review

- The fixture model follows scripts, so this validates **wiring, tool discipline, and
  the HITL gates** — not answer quality. Answer quality needs a real provider and the
  Phase 7 benchmark (precision/recall per pillar), which is still open.
- The first pass used a ~390px window; the second pass covered 1280px. Only these
  two widths were checked.
- The Docker path is validated by `docker compose config` only; the daemon is not
  available on this machine, so `agent/Dockerfile` has never been built.
