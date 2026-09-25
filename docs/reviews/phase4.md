# Phase 4 — Browser Review Log

**Date:** 2026-09-25
**Method:** agent-browser against the live local stack (API :8110 · Celery worker · Vite :5175 · Postgres :5433 · Redis :6390)
**LLM provider:** `mock` (deterministic offline harness — see caveat below)

> **Important caveat:** no LLM credentials were available in this environment, so the
> review ran with `AI_INTEL_LLM_PROVIDER=mock`. This is a rule-based harness that emits
> the same structured JSON a model would, so the pipeline, schema validation, event
> stream, cost ledger, and UI are genuinely exercised — but the findings are **not**
> real LLM analysis. The dashboard surfaces an explicit amber warning when mock mode is
> active. Real usage sets `AI_INTEL_LLM_PROVIDER=openai` (+ base URL/key/model).

## Flow verified (seedy benchmark repo)

Analysis reached `done` with 26 findings. Pipeline stages visible in the Progress stream:

1. `step clone` → `step inventory` → `step index` (17 symbols) → `tool:*` × 8 → `tool:embeddings` (18 chunks) → `step agents` ("Dispatching 5 agents") → `agent:code|tests|docs|security|architecture` → `done`.
2. **Agent Activity panel**: mock-provider warning, `2,201 tokens in · 762 out`, per-agent rows (model, findings, dismissed, tokens). Ledger example: Code `1 findings · 1 dismissed · 1298in/148out`.
3. **Acceptance — Security Agent**: hypothesis finding `find_user builds a query with string interpolation, enabling SQL injection` at `app/db.py:10` with caller context in the evidence. ✓
4. **Acceptance — Code Agent false positive**: the planted `insecure hash algorithm sha1` finding at `app/cache_key.py:11` is marked **dismissed** (verifier `tool:semgrep`, with `evidence_json.triage` recording the verdict/reasoning). ✓
5. **Acceptance — Test Agent**: hypothesis `Establish a test suite before adding features` consistent with the deterministic "No test suite detected". ✓
6. Docs + Architecture agents produced plans/layering findings; all LLM findings are `status=hypothesis`, `verifier=llm:mock`.
7. Console: 0 errors. Screenshot: `docs/reviews/phase4.png`.

## Schema / robustness (unit tests)

- Valid JSON → hypothesis finding with citation preserved.
- Malformed output → one repair retry → recovered (`repaired=1`).
- Unparseable after repair → run dropped with `error` set, no findings.
- Schema violation (missing required field) → repaired.
- LLM failure → `error` recorded, pipeline continues (chord stays alive).

## Bugs / issues found and fixed

| Issue | Root cause | Fix |
|-------|-----------|-----|
| Planted false positive not flagged by semgrep | `hashlib.md5(..., usedforsecurity=False)` is recognized safe, and the md5 rule only fires on literal args; `subprocess` constant command also not flagged | Switched the planted FP to `hashlib.sha1(payload)` with a documented non-security note — reliably flagged by `insecure-hash-algorithm-sha1` |
| Security mock claimed "SQL injection" for every risk function | crude heuristic | mock now branches on rule/snippet (injection / weak-crypto / secret) |
| Review screenshot showed a stale `verified` badge on the dismissed finding | page snapshot taken before the agent chord committed | reload confirms `dismissed`; no code change needed |

## Notes / limitations

- Agent input is capped (`agent_max_context_chars`, `agent_max_static_findings`, `agent_max_symbols`) to bound token usage on large repos.
- Confidence = mean(model-declared confidence, mean token logprob when available); calibration proper lands in Phase 5.
- `openai` provider rejects `response_format`/`logprobs` gracefully (retries without them), so Ollama/vLLM-style endpoints work.

## Acceptance criteria status

- [x] Seedy repo: Security Agent flags the SQL injection at the correct function with caller context
- [x] Seedy repo: Code Agent dismisses ≥1 planted false-positive semgrep finding
- [x] Seedy repo: Test Agent lists untested modules matching the test-presence analysis
- [x] Malformed-LLM-output handling proven by unit tests (repair then drop)
- [x] Progress stream shows 5 agents; token/cost display present
- [x] No console errors
