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
| backend `ruff check` / `format` / `mypy` / `pytest` | clean · 51 passed |
| frontend `lint` / `typecheck` / `test` / `build` | clean · 1 passed · initial chunk 245 kB (agent lazy-loaded) |
| agent `typecheck` / `build` | clean · 0 diagnostics, 26 tools, 5 subagents |
| agent `npm run eval` | 9 evals, 30 gates, all passing, no credentials |
| `docker compose config` | valid (`agent` service included) |

## Limits of this review

- The fixture model follows scripts, so this validates **wiring, tool discipline, and
  the HITL gates** — not answer quality. Answer quality needs a real provider and the
  Phase 7 benchmark (precision/recall per pillar), which is still open.
- The browser window was ~390px wide for the agent panel, so the two-column
  dashboard layout was not re-checked at 1280px in this pass.
- The Docker path is validated by `docker compose config` only; the daemon is not
  available on this machine, so `agent/Dockerfile` has never been built.
