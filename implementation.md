# Implementation Plan — AI Engineering Intelligence Platform

> **Document purpose:** This is the authoritative implementation plan for the AI Engineering
> Intelligence Platform. It is written to be readable by both humans and AI coding agents.
> Each phase contains: goals, tasks (with acceptance criteria), technical decisions, and a
> mandatory **browser review step** (using `agent-browser`) to catch bugs before proceeding.
>
> **Status legend:** `[ ]` not started · `[~]` in progress · `[x]` done · `[!]` blocked
>
> **Build order is strict:** complete Phase N (including its browser review + issue fixes)
> before starting Phase N+1.

---

## 0. Context & Research-Grounded Decisions

This platform analyzes GitHub repositories with a hybrid **deterministic-tools + LLM agents**
pipeline and produces a **Repository Health Score** with verified, cited findings.

Decisions made during planning (each grounded in research):

| # | Decision | Rationale / Source |
|---|----------|--------------------|
| D1 | **Deterministic-first, LLM-second.** Run real tools (tree-sitter, Semgrep, gitleaks, OSV, coverage, radon) before/alongside LLM reasoning. | arXiv:2508.04448 — LLMs beat SAST on F1 but are noisy and mislocate issues; hybrid is recommended. |
| D2 | **Every finding carries a verdict schema:** `{claim, evidence, file:line citation, verifier, confidence, status: verified|hypothesis}`. Tool-confirmed → `verified`; LLM-only → `hypothesis` (requires human review). | arXiv:2509.26546 (verified code reasoning), VerifiAgent (EMNLP 2025). |
| D3 | **Repo symbol graph instead of flat RAG.** Agents query structure (imports/calls/callees/dependents/paths/neighbourhood) and quote exact symbols. *(Revised during build: the embedding index was removed — see D11.)* | RANGER (arXiv:2509.25257), CodeX Graph (NAACL 2025), RepoFormer. |
| D4 | **Never ask the LLM to infer code structure** (call graphs, AST, dataflow). Parse with real tools and feed results in. | arXiv:2505.12118 — code LLMs are poor at static-analysis tasks. |
| D5 | **Calibrated confidence + human approval queue.** Confidence from self-consistency + cross-tool agreement; security/architecture findings need explicit approve/dismiss; dismissals feed calibration. | arXiv:2402.07632, FAccT'24 trust-in-codegen study. |
| D6 | **Chunked per-function vulnerability analysis**, never whole-file scanning. | arXiv:2512.22306 — LLM recall collapses (<0.30) on dense multi-vuln files. |
| D7 | **Test agent reports coverage gaps and test plans**; it does not blindly generate-and-trust tests. | TestGenEval (ICLR 2025) — best model reaches only ~35% coverage; CoverUp/Panta show coverage-guided loops work. |
| D8 | **Honest scoring:** hypothesis-only findings weigh less in the health score than verified findings. | Trust calibration literature; avoids "vibes-based" scores. |
| D9 | **Benchmark harness** (JITVUL-style commit pairs, seeded sample repos) to report precision/recall in the README. | JITVUL (ACL 2025). Portfolio credibility. |
| D10 | **The agent runtime is [eve](https://eve.dev)**, not hand-rolled Python. Typed tools, HITL approval gates, subagents, durable sessions, and a hermetic eval runner come from the framework. | Avoids reimplementing agent plumbing; the eval harness is the unit-test story for agent behaviour. |
| D11 | **No embeddings anywhere.** The symbol graph plus `read_source` answers the questions RAG was retrieved for, at a fraction of the moving parts: no pgvector, no chunker, no drift between an embedding index and the analysed commit. | Removing it deleted ~1.5k lines and a whole migration; the agent cites `file:line` it actually read. |

### Tech stack (confirmed)

- **Frontend:** React + Vite + TypeScript, TanStack Query, Recharts, Tailwind CSS.
- **Backend:** FastAPI (Python 3.12), Pydantic v2, SQLAlchemy 2.x, Alembic.
- **Queue:** Celery + Redis (broker + cache + rate limits).
- **DB:** PostgreSQL 16 (no vector extension — see D11; the symbol graph lives in plain tables).
- **Analysis tools:** tree-sitter, Semgrep, gitleaks, OSV-Scanner, radon, coverage.py, jscpd-style similarity hashing.
- **Agent runtime:** eve (Node >= 24). Model via the AI Gateway or any AI SDK provider; `mockModel` fixture for evals and offline review.
- **Infra:** Docker Compose, GitHub Actions CI.
- **Repo layout:** monorepo — `agent/`, `backend/`, `frontend/`, `infra/`, `benchmark/`, `docs/`.

---

## Phase 1 — Foundation `[x]`

**Goal:** runnable skeleton: auth, repo registration, async job pipeline, DB schema.

### Tasks
1. `[x]` Init monorepo: `backend/` (FastAPI), `frontend/` (Vite+TS), `infra/docker-compose.yml`, `docs/RESEARCH.md`.
2. `[x]` Docker Compose services: `api`, `worker` (Celery), `postgres` (pgvector image), `redis`, `frontend` (dev server).
3. `[x]` Postgres schema (Alembic migration 0001):
   - `users(id, github_id, login, created_at)`
   - `repositories(id, owner, name, url, default_branch, added_by → users)`
   - `analyses(id, repository_id, commit_sha, status[pending|running|done|failed], started_at, finished_at, error)`
   - `findings(id, analysis_id, agent, category, severity, title, description, file_path, line_start, line_end, evidence_json, verifier, confidence REAL, status[verified|hypothesis|dismissed], created_at)`
   - `approvals(id, finding_id, user_id, decision[approve|dismiss], note, created_at)`
   - `calibration_stats(id, agent, category, shown INT, accepted INT, dismissed INT, updated_at)`
4. `[x]` GitHub OAuth login (device-free web flow), JWT session for API.
5. `[x]` `POST /repos` (register by URL), `POST /repos/{id}/analyze` → creates `analyses` row, enqueues Celery task that (for now) shallow-clones the repo, detects languages, writes file inventory to `evidence_json` of a synthetic "ingestion" finding, marks analysis `done`.
6. `[x]` `GET /analyses/{id}` + `GET /analyses/{id}/events` (SSE progress stream).
7. `[x]` Frontend: login page, repo-submit form, analysis detail page polling/streaming status. Minimal styling (Tailwind), no dashboard yet.
8. `[x]` CI: GitHub Actions — backend lint (ruff), typecheck (mypy), pytest; frontend lint (eslint), typecheck (tsc), vitest.

**Acceptance criteria**
- `docker compose up` boots all services; `GET /health` returns 200.
- Registering a public repo and triggering analysis completes end-to-end; SSE shows step progress.
- CI green on a trivial PR.

**Browser review (agent-browser)**
- Open the frontend, log in (use a test OAuth app or a dev-bypass login flag `DEV_LOGIN=1`), submit `https://github.com/psf/requests` (small-ish, well-known), watch analysis reach `done`, verify analysis page renders without console errors.
- Capture screenshot to `docs/reviews/phase1.png`.
- Any UI/API bug found → fix, re-run review, then proceed.

---

## Phase 2 — Deterministic Analysis Layer (no LLM) `[x]`

**Goal:** a useful product with zero LLM calls: real findings from real tools, all with file:line citations.

### Tasks
1. `[x]` **Ingestion service**: shallow clone to `/data/repos/{repo_id}/{commit}`, language detection (extensions + shebangs), file inventory table or JSONB on `analyses`.
2. `[x]` **tree-sitter indexer** (Python, JS/TS first; grammar packs pinned):
   - Per file: AST → symbols (functions/classes), imports, call edges (best-effort intra-file + import-resolved cross-file).
   - Persist to tables `symbols(id, repo_file, name, kind, line_start, line_end)` and `edges(src_symbol, dst_symbol, kind[imports|calls])`.
   - *Decision D4: this graph is the ONLY source of structural truth for later agents.*
3. `[x]` **Tool runners** (each = isolated Celery subtask, timeout + output parsing → `findings` rows with `verifier='tool:<name>'`, `status='verified'`, `confidence=1.0`):
   - Semgrep (default rulesets per language: security + smells).
   - gitleaks (secrets).
   - OSV-Scanner (vulnerable deps) + simple outdated-deps check (PyPI/npm registry latest vs. lockfile).
   - radon (cyclomatic complexity, MI) → "code smell" findings above thresholds.
   - Duplication: token-hash sliding window (jscpd-like, Python impl) → duplicated-block findings.
   - Test presence: detect test dirs/frameworks; if runnable, `pytest --cov` → coverage %; else heuristic "missing tests" finding per source dir.
   - Docs: README presence/sections, docstring coverage per public symbol (from tree-sitter symbols).
4. `[x]` **Health score v1** (`analysis_engine/scoring.py`): per-pillar score = `100 − Σ severity_weight(finding)` normalized per KLOC, clamped [0,100]; pillars: Code Quality, Security, Testing, Documentation, Dependencies, Architecture.
5. `[x]` API: `GET /analyses/{id}/findings?agent=&severity=&status=` (paged), `GET /analyses/{id}/score`.
6. `[x]` Frontend: dashboard page — six score bars, findings table with file:line links, severity badges, filter by pillar.

**Acceptance criteria**
- Analyzing a deliberately-seedy sample repo (create `benchmark/seedy-python-app/` with a hardcoded secret, SQL injection, duplicated function, no tests, old deps) yields findings in every pillar with correct file:line.
- Scores compute and render; no LLM keys required.

**Browser review (agent-browser)**
- Full flow: submit the seedy repo → verify each pillar shows findings → click a finding → confirm file/line citation visible.
- Check for: empty states, loading spinners, SSE reconnect behavior, duplicate findings on re-run (dedupe by `(file,line_start,rule_id)`).
- Screenshot `docs/reviews/phase2.png`. Fix all issues before Phase 3.

---

## Phase 3 — Knowledge Graph + RAG Service `[x]`

> **Superseded in part.** The graph store (task 1) and the neighbourhood query
> (3.2) survived and are what the eve agent uses today. The embedding index (2),
> semantic/selective retrieval (3.1, 3.3), and the `/search` endpoint (4) were
> built and then **removed** in the eve migration below (D11). Kept here as the
> record of what was tried and why it is not needed.

**Goal:** queryable repo structure + semantic index that agents (Phase 4) will use. *(Decision D3.)*

### Tasks
1. `[x]` **Graph store**: build repo graph from Phase 2 tables (modules → symbols → imports/calls). Store as adjacency in Postgres (`edges` already exist; add `graph_snapshots(analysis_id, built_at)` marker). Expose query helpers: `callers(symbol)`, `callees(symbol)`, `imports(module)`, `dependents(module)`, `path(a,b)`.
2. `[x]` **Embedding index**: chunk by function/class (tree-sitter boundaries — never arbitrary line splits); embed with configurable embedding model; store in pgvector column on `chunks(id, analysis_id, symbol_id, text, embedding vector)`.
3. `[x]` **Retrieval service** (`analysis_engine/retrieval.py`):
   - `semantic_search(query, k)` → top chunks.
   - `graph_neighborhood(symbol, depth)` → related symbols + source excerpts.
   - **Selective retrieval (RepoFormer-style):** a cheap heuristic gate (symbol in graph? then graph-first, no embeddings; natural-language question? then embeddings) — avoid always-retrieve.
4. `[x]` Internal API endpoints `/analyses/{id}/graph/...` and `/analyses/{id}/search?q=` (used by UI "Explore" tab and later by agents).
5. `[x]` Frontend: Explore tab — dependency graph view (simple force layout or adjacency list MVP) + semantic search box.

**Acceptance criteria**
- For the seedy repo + one real repo: `callers()` returns correct results verified against actual imports; semantic search for "authentication" returns the auth module in top-3.
- Graph build time < 60s for ~2k files (else add incremental indexing).

**Browser review (agent-browser)**
- Use Explore tab on a real repo; verify graph view matches actual import structure; verify search relevance by eye.
- Screenshot `docs/reviews/phase3.png`. Fix issues before Phase 4.

---

## Migration — eve replaces RAG and the Python agent runtime `[x]`

**Goal:** replace the embedding index and the hand-rolled Python agent layer with
the eve agent runtime and a graph-only retrieval story. *(Decisions D3, D10, D11.)*

### What changed
1. `[x]` **RAG removed.** Deleted `analysis_engine/{embeddings,chunker,retrieval}.py`,
   `tasks/embeddings.py`, the `Chunk` model, `/analyses/{id}/search`, and the
   Explore semantic-search box. Consolidated migrations `0003`/`0004`; PostgreSQL
   no longer needs the `vector` extension.
2. `[x]` **Python agent runtime removed.** Deleted `app/agents/`, `app/llm/`,
   `tasks/agents.py`, and the `dispatch_agents` Celery stage. The orchestrator is
   now ingest → index → 8 deterministic tools → verify → score.
3. `[x]` **Backend contract for the agent** (the parts a serverless agent layer
   needs that the deleted code owned):
   - `app/analysis_engine/agent_findings.py` — server-side D2 verdict schema: the
     authority that validates, normalizes, and stores agent claims as
     `hypothesis` (moved out of the deleted `app/agents/base.py`).
   - `POST /api/analyses/{id}/findings` — intake; persists claims, then re-runs
     verification, calibration, scoring, and the publication gate.
   - `POST /api/auth/eve-token` — exchanges the httpOnly browser cookie for a
     short-lived bearer token (`iss=ai-intel`, `aud=eve-agent`).
   - Service auth: `X-Agent-Token` (shared secret) + `X-Agent-User`, because the
     agent runs server-side and cannot present the cookie. Fails closed.
4. `[x]` **eve agent in `agent/`**: `instructions.md` (no-RAG policy + verdict
   schema), 17 typed tools over graph/findings/score/trust, five review subagents
   (`code`, `security`, `tests`, `docs`, `architecture`), `approval: always()` on
   `run_analysis` and `decide_finding`, just-bash sandbox (no Docker needed).
5. `[x]` **Evals** (`agent/evals/`): fixture model + in-process fixture API, so
   the suite is hermetic (no credentials, DB, or containers). Covers tool
   discipline, the citation rule, multi-turn behaviour, and every HITL gate.
6. `[x]` **Frontend**: agent chat tab with tool-call chips and inline approval
   prompts; eve client lazy-loaded so the initial bundle is unchanged.
7. `[x]` **Infra**: `agent` service in compose, agent job in CI (typecheck/build/eval),
   `scripts/dev-local.sh` starts redis + api + worker + agent + frontend.

**Acceptance criteria**
- Backend suite green (RAG and agent tests removed, intake tests added); agent
  evals green; browser review of the chat, an approval, and a cancellation.

---

## Phase 4 — LLM Agent Layer `[x]`

**Goal:** the four agents from the concept, powered by LLM + tools + graph. *(Decisions D1, D4, D6, D7.)*

### Tasks
1. `[x]` **LLM adapter** (`backend/app/llm/`): OpenAI-compatible client; structured outputs (JSON schema); logprobs captured when available; retry/backoff; per-analysis token + cost ledger (`analyses.cost_json`).
2. `[x]` **Agent framework**: each agent = Celery task with: (a) deterministic inputs from tools/graph, (b) LLM prompt with citations required, (c) output validated against the verdict schema (D2) — reject/repair malformed outputs (one repair retry, else drop).
3. `[x]` **Code Agent**: takes static findings + complexity hotspots; LLM triages false positives and explains smells; must cite `file:line` and reference graph facts.
4. `[x]` **Security Agent**: JITVUL-style — analyzes *changed/high-risk functions* (chunked per-function, D6) with caller/callee context from graph; dependency CVEs enriched with "is the vulnerable function actually called?" via graph path check.
5. `[x]` **Test Agent** (D7): consumes coverage data → per-module branch gaps; LLM produces a *test plan* (what to test, edge cases) — not auto-generated test code presented as trustworthy.
6. `[x]` **Docs Agent**: README section coverage, docstring gaps for public API symbols (graph `kind=exported`), API surface vs. docs mismatch.
7. `[x]` **Architecture Agent**: layering/cycle detection from graph (deterministic) + LLM narrative summary; flags god-modules (fan-in/fan-out outliers).
8. `[x]` Orchestrator: run agents in parallel (Celery group), stream per-agent progress over SSE; analysis `done` only when all agents finish.
9. `[x]` All LLM-produced findings stored with `status='hypothesis'`, `verifier='llm:<model>'`, raw `confidence` from self-consistency (see Phase 5; placeholder = logprob-derived for now).

**Acceptance criteria**
- Seedy repo: Security Agent flags the SQL injection at the correct function with caller context; Code Agent correctly dismisses ≥1 planted false-positive Semgrep finding; Test Agent lists the untested modules matching coverage data.
- Malformed-LLM-output handling proven by a unit test with a mocked bad response.

**Browser review (agent-browser)**
- Re-analyze seedy repo; inspect agent findings in UI; verify citations resolve; verify progress stream shows 4+ agents; check token/cost display.
- Screenshot `docs/reviews/phase4.png`. Fix issues before Phase 5.

---

## Phase 5 — Trust Layer (Verification + Confidence + Human Approval) `[x]`

**Goal:** the differentiator. *(Decisions D2, D5, D8.)*

### Tasks
1. `[x]` **Verifier service** (`analysis_engine/verify.py`): for each LLM finding, re-check with tools:
   - Security claims → targeted Semgrep/CodeQL-lite query on cited lines + graph path check (does the claimed flow exist?).
   - Coupling/architecture claims → graph query verification.
   - Test/doc claims → recompute metric on cited symbol.
   - Pass → `status='verified'`; fail → stays `hypothesis` with `evidence_json.verification_error` recorded.
2. `[x]` **Confidence calibration**:
   - Self-consistency: sample n=3 verdicts for high-severity LLM findings; agreement fraction folds into `confidence`.
   - Cross-tool agreement bonus; single-source LLM-only → capped at 0.6.
   - Store per-category stats in `calibration_stats`.
3. `[x]` **Human approval queue**: findings with `severity >= high` AND `status='hypothesis'` require approve/dismiss before analysis is "published"; UI queue with diff/code snippet, confidence display, low-confidence token/claim highlighting, and per-category historical acceptance rate (FAccT'24 patterns).
4. `[x]` **Feedback loop**: dismissals update `calibration_stats`; future confidence scores for that agent/category adjusted (simple Beta-Bernoulli shrinkage — keep it stupidly simple).
5. `[x]` **Honest scoring v2 (D8)**: verified findings count full weight; hypotheses count ×0.5; dismissed count 0. Score endpoint returns breakdown per pillar with `verified_count` / `hypothesis_count`.

**Acceptance criteria**
- Plant one true and one false LLM finding (mock LLM): verifier marks exactly the true one `verified`.
- Dismissing a finding changes that category's acceptance rate and affects subsequent confidence.
- Score API shows the verified/hypothesis split.

**Browser review (agent-browser)**
- Walk the approval queue end-to-end: approve one, dismiss one with a note; confirm score updates; confirm dismissed finding leaves the default findings view.
- Screenshot `docs/reviews/phase5.png`. Fix issues before Phase 6.

---

## Phase 6 — Dashboard Polish & Score UX `[x]`

**Goal:** portfolio-grade dashboard matching the concept mock.

### Tasks
1. `[x]` Health Score hero: six animated bars (Code Quality / Security / Testing / Documentation / Dependencies / Architecture), overall score, delta vs. previous analysis of same repo.
2. `[x]` Findings explorer: group by pillar/severity/agent; code snippet preview with highlighted lines; citation links to GitHub blob URL at analyzed SHA.
3. `[x]` Trust panel: per-agent confidence, acceptance rates, verification coverage (% findings verified).
4. `[x]` Analysis history + compare view (two analyses side-by-side).
5. `[x]` Empty/error/loading states everywhere; dark theme; responsive to 1280px.

**Acceptance criteria**
- All concept-mock elements present; Lighthouse a11y ≥ 90; no console errors.

**Browser review (agent-browser)**
- Full UX pass: navigation, filters, compare view, mobile-width sanity at 1280px.
- Screenshot `docs/reviews/phase6.png`. Fix issues before Phase 7.

---

## Phase 7 — Evaluation Harness & Deployment `[x]`

**Goal:** credibility + shipping. *(Decisions D9, D10.)*

**Evaluation now has two layers.** The agent's behaviour is covered by `agent/evals/`
(fixture model + fixture API, hermetic, runs in CI in ~5s — see the migration
section). What remains is measuring the *analysis* itself against known truth.

### Tasks
1. `[x]` Agent behaviour evals: `agent/evals/` — tool discipline, citation rule,
   multi-turn, and every HITL gate. Wired into CI (`npm run eval`).
2. `[x]` CI: backend (ruff/mypy/pytest), frontend (lint/typecheck/test/build), and
   the new agent job (typecheck/build/eval), all on Node 24 where relevant.
3. `[x]` Compose: `agent` service added; agent and frontend wired to the API and
   each other; `agent/Dockerfile` builds with `eve build` and runs `eve start`.
4. `[x]` `scripts/dev-local.sh` starts the whole stack (redis, api, worker, agent,
   frontend) with no Docker, plus `.local/env.sh.example` documenting the knobs.
5. `[x]` Analysis-quality benchmark (`benchmark/`):
   - `backend/app/benchmark/` — scores an existing analysis against
     `benchmark/ground-truth/*.yaml`: recall, precision, F1, verification coverage,
     and planted-false-positive triage. No re-analysis, so no external tools needed.
   - Reports **recall 100%** and **precision 91% deduplicated** on
     `seedy-python-app`; the raw per-finding figure (62%) is also shown because 5 of
     its 6 "misses" are repeat reports of one condition. Output:
     `benchmark/REPORT.md`, surfaced in the README.
   - The first run surfaced a real defect (semgrep credential rules filed as
     `vulnerability`); fixed in `categorize_check()` and worth 91% → 100% on
     re-score.
   - `[ ]` Optional: JITVUL-style pairwise commits subset as an offline script.
6. `[x]` Production hardening: healthchecks on every service (`api`, `agent`, and
   `frontend` declare them in their images; `worker` declares its own in compose
   because it shares the `api` image; postgres and redis inline),
   `docker-compose.prod.yml` (internal-only API/agent, no default secrets, durable
   agent state), `.dockerignore` ×3, and README deployment notes.
   *Known gap:* only `intel` and `eve` run as non-root; the nginx frontend runs as
   root master.
7. `[x]` `docs/RESEARCH.md`: maps every D-decision (D1–D11) to its citation, and
   records where the plan changed during the build (D3 → D11, and D10).
8. `[x]` README: architecture diagram, quickstart, configuration matrix, checks,
   and benchmark numbers.
9. `[x]` Live answer-quality evals (`agent/evals/quality/`): two judge-scored cases
   that skip without a provider credential, so adding a key later is one command.

**Deferred, not done:** the JITVUL-style pairwise-commit subset (item 5, optional)
and any measurement of real-model answer quality. Both need something this
environment does not have — public-CVE commit pairs, or a provider credential.

**Acceptance criteria**
- CI green, benchmark reproducible with one command
  (`cd backend && python -m app.benchmark --repo seedy-python-app`).
- `[x]` a fresh `docker compose up` serving all services — verified by building and
  running the production stack locally, not just written. Cold start to six healthy
  containers takes ~35s (`up --wait`). Verified through nginx on the published
  port: `/` serves the hashed bundle, `/health` → `ok`, `/api/health` →
  `{"status":"ok","db":"ok","redis":"ok"}`, SPA fallback on `/analyses`, and
  `/eve/v1/info` → 401 bare / 200 with a backend-minted HS256 token (26 static
  tools advertised).

  Running it for real is what surfaced five defects that the static checks, the
  unit suites, and local `eve start` had all passed over:
  1. `addgroup -S` is rejected by the Debian trixie base behind `python:3.12-slim`
     (exit 51), so no backend image built at all.
  2. The agent healthcheck probed `/eve/v1/info`, which sits behind the channel's
     auth walk once `AI_INTEL_JWT_SECRET` is set → permanently unhealthy. It had
     looked public only because local `eve start` ran with no secret set.
  3. The worker inherited the API's HTTP healthcheck from the shared image, but a
     Celery worker serves no HTTP → permanently unhealthy while working fine.
  4. `dev` was the last stage of `frontend/Dockerfile`, and an unqualified build
     takes the last stage — so production shipped the Vite dev server and
     published host `:80` to a container serving `:5173`.
  5. `verify-container-config.sh` did not require an explicit build target, so (4)
     passed it; it now rejects any multi-stage build without one, and the CI probe
     asserted a 200 from an authenticated route.
  6. nginx resolved `api` and `agent` once at config load and cached their IPs, so
     recreating either container left the published port returning 502 until nginx
     itself was restarted — with both upstreams healthy and serving. It now
     re-resolves via Docker's embedded DNS (`resolver 127.0.0.11`), using a variable
     upstream plus `$request_uri` to keep the forwarded URI unchanged.

  Two documentation bugs also surfaced: the README implied compose reads `.env`
  from the working directory (it resolves against the compose file's directory,
  `infra/`), and the CI probe expected 200 from `/eve/v1/info`.

**Scoring a running analysis (found by browser review)**

  A finished analysis of `krtk06/Chaty` displayed **100/100 with all six pillars marked
  "not measured"** while listing 13 findings below it. The backend had it right the whole
  time — `score_json` held `overall: 88`, security 76 over 4 findings, code-quality 81
  over 6 — and `GET /score` returned exactly that. Three defects compounded:

  1. `useScore` was enabled by `id > 0` alone, so the page fetched the score while the
     analysis was still running.
  2. `GET /score` treats a missing `score_json` as "never scored" and recomputes it.
     Mid-run that counts only the findings reported so far — none, early on — so every
     pillar scored 100. It then **persisted** that value (`analysis.score_json = score`),
     which is what made it outlive the run.
  3. Nothing invalidated the `["score", id]` query when the analysis reached `done`, so
     the client kept rendering the cached 100 indefinitely.

  The 100 was therefore never computed from the findings — it was an empty analysis
  scored on demand, displayed as final. Fixed on both sides: the endpoint now returns 409
  for an unfinished analysis with no score rather than inventing and persisting one
  (`finalize_analysis` writes the real score in the same commit that flips the status),
  and the client fetches only once the analysis is done and refetches on the transition.
  Regression-tested in `tests/test_score_timing.py`, including that nothing is persisted.

  The dev compose had the same worker healthcheck gap as prod — the shared backend image's
  HTTP probe can never pass for a Celery worker — so `docker compose up` there reported
  `worker` unhealthy while it worked. Both files now carry the control-channel probe.

**Scoring: a missing denominator, and recalibration against several repositories**

  Browser review of a second repository (`octocat/Hello-World`, 2 trivial findings)
  returned **15/100** while `krtk06/Chaty` — 13 findings including 4 high-severity
  credential hits — returned **88**. Both numbers were artefacts of the denominator.
  The indexer stores `loc = 0` for a repository it cannot index, and the density curve
  divided by `MIN_KLOC = 0.001`, i.e. one line of code, giving densities in the tens of
  thousands. Two fixes:

  - A missing LOC now switches basis to raw weighted finding-points
    (`COUNT_HALF_SCORE_PENALTY = 20`) instead of substituting a tiny denominator, and the
    payload carries `basis: "count"` plus `kloc: null` so a count-scored repository is
    never silently compared with a density-scored one. `version` is now 5.
    Hello-World scores 65.
  - The stricter calibration made the asymptotic curve round its worst cases to 0, which
    reads as "clean" rather than "catastrophic" — the failure the v3 rewrite was meant to
    remove. A pillar with findings now floors at 1.

  `HALF_SCORE_DENSITY` went 250 → 100 → **30**, the first two from single runs. Measured
  across five real repositories (`krtk06/Chaty`, `psf/requests`, `pallets/click`,
  `pallets/flask`, `encode/httpx`), worst-pillar density clusters in 22–39 points per
  KLOC; at 100 every repository scored 87–92. At 30 the median repository's weakest
  dimension sits near half marks and overalls land at 59–72. Reports and the sweep are in
  `benchmark/REPORT.md`, and changing the constant invalidates every stored score, so the
  dashboard's run-over-run delta stays suppressed when the calibration differs.

  A by-product worth noting: the strictness revealed that `tests/test_scoring_curve.py`
  encoded the *previous* calibration in three places — a finding count that only produced
  a meaningful density while the constant was 20 times the HIGH weight, a "tiny repo is
  unhealthy, not dead" threshold, and a worst-pillar-cap fixture whose bare mean stopped
  looking healthy. Those now assert the behaviour rather than the old numbers.

**Navigation: getting back to the repository list**

  An analysis page offered no way back to the list, so starting a second repository meant
  editing the URL. The header title was in fact a working link to `/`, but styled as
  static text with no hover cue. Added an explicit `← Back` control above the repository
  name — present while the analysis is still running, so a run can be abandoned — and
  gave the title a hover underline and muted colour.

**Fail-closed secrets (`backend/app/config.py`)**

  Compose refuses to start without its five required variables, but the application
  did not: started directly with `AI_INTEL_ENVIRONMENT=production` and no
  `AI_INTEL_JWT_SECRET`, it booted and signed cookies and eve tokens with the literal
  `change-me-in-production` — a value published in this repository. It now refuses to
  construct in production on a default, published, or under-32-character secret, on a
  blank agent token, or with dev login enabled, reporting every problem at once.
  `.env.example`'s own example value is on the deny-list, because it is 52 characters
  long and so passes a length check on its own.

  The agent gained the matching guard for the fixture model: `.env.example` ships
  `AI_INTEL_LLM_PROVIDER=mock` so the dev quickstart works with no credentials, which
  makes it the likeliest production misconfiguration — and it looks entirely healthy
  while answering from canned transcripts. `eve start` now refuses `mock` when
  `NODE_ENV=production`, which `docker-compose.prod.yml` sets (it also makes the
  agent's auth walk fail closed when the shared secret is missing).

  Adding the API guard immediately caught a sixth defect: the Celery worker imports
  `app.config` through `celery_app` and had been silently inheriting the default
  signing secret, since the worker service was never given either secret. It receives
  both now.

**Open limitation — the model is chosen at image build time**

  Driving a live turn through the running stack (session created, message accepted,
  SSE stream flowing through nginx, model call attempted) showed everything wired
  correctly: the call reached the AI Gateway and failed only with "AI Gateway rejected
  the provided API key". So a real key is all that stands between the current image and
  live answers.

  It also exposed that `AI_INTEL_LLM_PROVIDER` and `AI_INTEL_MODEL` do nothing in the
  Docker image. eve compiles the agent definition — including the resolved model —
  into `.output/.eve/compile/compiled-agent-manifest.json` during `eve build`, which the
  image runs before any `AI_INTEL_*` variable exists. The manifest therefore froze the
  provider to its `?? "gateway"` default and the model to `anthropic/claude-sonnet-4.5`.
  Verified: a container started with `AI_INTEL_LLM_PROVIDER=openai` and a valid
  `AI_INTEL_API_KEY` still called the AI Gateway, and the manifest contained no
  occurrence of `openai`. The `NODE_ENV=production` fixture-model guard is inert in the
  image for the same reason — it holds for `eve start` on a host, not in the container.

  Moving the build to container start was tried and does not work: `eve start` refuses to
  boot without existing output, and building there fails with `EXDEV: cross-device link
  not permitted` because eve renames `.eve/builds/<hash>/output` onto `/srv/agent/.output`
  while `agent_state` is mounted at `.eve` — two filesystems.

  The corollary matters for security: a provider that needs a key (`openai`) would have
  that key baked into the manifest at build time, so the image must never be built with
  one. Leaving this open deliberately — the options are (a) find a supported way to
  relocate eve's build output so it is same-filesystem and build at start, (b) make
  provider and model build args and ship a provider-specific image, keeping keys
  runtime-only, or (c) drop the `agent_state` volume so the build can happen at start.
  Each trades cold-start time, image reusability, or durable agent state.

**Browser review (agent-browser)**
- Done for the migration: chat tab, an approval, and a cancellation, plus a live
  agent → API → findings round trip. Repeat once more after the benchmark lands.

**Browser review (agent-browser)**
- Review the deployed/dev app once more end-to-end against README quickstart exactly as a new user would.
- Screenshot `docs/reviews/phase7.png`.

---

## Cross-cutting rules for the implementing agent

1. **Never** let LLM output bypass the verdict schema (D2). Unparseable → repair once → drop.
2. **Never** let the LLM invent structure — graph/tools only (D4).
3. Every finding must cite `file:line`; findings without citations are stored but capped at confidence 0.3 and never shown as verified.
4. Secrets: LLM keys, OAuth secrets via env only; `.env.example` committed, never real values.
5. Keep phases' acceptance criteria as pytest/vitest cases where automatable.
6. After **every** phase: run the agent-browser review, log findings in `docs/reviews/phaseN.md`, fix, re-review, then proceed.
7. Minimal diffs; follow existing code style; update this file's status boxes as phases complete.
