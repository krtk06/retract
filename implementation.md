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
| D3 | **Repo knowledge graph + embedding index** instead of naive flat RAG. Agents query the graph (imports/calls/contains); retrieval is selective (skip when not needed). | RANGER (arXiv:2509.25257), CodeX Graph (NAACL 2025), RepoFormer. |
| D4 | **Never ask the LLM to infer code structure** (call graphs, AST, dataflow). Parse with real tools and feed results in. | arXiv:2505.12118 — code LLMs are poor at static-analysis tasks. |
| D5 | **Calibrated confidence + human approval queue.** Confidence from self-consistency + cross-tool agreement; security/architecture findings need explicit approve/dismiss; dismissals feed calibration. | arXiv:2402.07632, FAccT'24 trust-in-codegen study. |
| D6 | **Chunked per-function vulnerability analysis**, never whole-file scanning. | arXiv:2512.22306 — LLM recall collapses (<0.30) on dense multi-vuln files. |
| D7 | **Test agent reports coverage gaps and test plans**; it does not blindly generate-and-trust tests. | TestGenEval (ICLR 2025) — best model reaches only ~35% coverage; CoverUp/Panta show coverage-guided loops work. |
| D8 | **Honest scoring:** hypothesis-only findings weigh less in the health score than verified findings. | Trust calibration literature; avoids "vibes-based" scores. |
| D9 | **Benchmark harness** (JITVUL-style commit pairs, seeded sample repos) to report precision/recall in the README. | JITVUL (ACL 2025). Portfolio credibility. |

### Tech stack (confirmed)

- **Frontend:** React + Vite + TypeScript, TanStack Query, Recharts, Tailwind CSS.
- **Backend:** FastAPI (Python 3.12), Pydantic v2, SQLAlchemy 2.x, Alembic.
- **Queue:** Celery + Redis (broker + cache + rate limits).
- **DB:** PostgreSQL 16 **with pgvector** (decision: pgvector over Qdrant — one less service, embeddings live next to findings).
- **Analysis tools:** tree-sitter, Semgrep, gitleaks, OSV-Scanner, radon, coverage.py, jscpd-style similarity hashing.
- **LLM:** OpenAI-compatible adapter (pluggable base URL/model; logprobs used for confidence signal).
- **Infra:** Docker Compose, GitHub Actions CI.
- **Repo layout:** monorepo — `backend/`, `frontend/`, `infra/`, `benchmark/`, `docs/`.

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

## Phase 5 — Trust Layer (Verification + Confidence + Human Approval) `[ ]`

**Goal:** the differentiator. *(Decisions D2, D5, D8.)*

### Tasks
1. `[ ]` **Verifier service** (`analysis_engine/verify.py`): for each LLM finding, re-check with tools:
   - Security claims → targeted Semgrep/CodeQL-lite query on cited lines + graph path check (does the claimed flow exist?).
   - Coupling/architecture claims → graph query verification.
   - Test/doc claims → recompute metric on cited symbol.
   - Pass → `status='verified'`; fail → stays `hypothesis` with `evidence_json.verification_error` recorded.
2. `[ ]` **Confidence calibration**:
   - Self-consistency: sample n=3 verdicts for high-severity LLM findings; agreement fraction folds into `confidence`.
   - Cross-tool agreement bonus; single-source LLM-only → capped at 0.6.
   - Store per-category stats in `calibration_stats`.
3. `[ ]` **Human approval queue**: findings with `severity >= high` AND `status='hypothesis'` require approve/dismiss before analysis is "published"; UI queue with diff/code snippet, confidence display, low-confidence token/claim highlighting, and per-category historical acceptance rate (FAccT'24 patterns).
4. `[ ]` **Feedback loop**: dismissals update `calibration_stats`; future confidence scores for that agent/category adjusted (simple Beta-Bernoulli shrinkage — keep it stupidly simple).
5. `[ ]` **Honest scoring v2 (D8)**: verified findings count full weight; hypotheses count ×0.5; dismissed count 0. Score endpoint returns breakdown per pillar with `verified_count` / `hypothesis_count`.

**Acceptance criteria**
- Plant one true and one false LLM finding (mock LLM): verifier marks exactly the true one `verified`.
- Dismissing a finding changes that category's acceptance rate and affects subsequent confidence.
- Score API shows the verified/hypothesis split.

**Browser review (agent-browser)**
- Walk the approval queue end-to-end: approve one, dismiss one with a note; confirm score updates; confirm dismissed finding leaves the default findings view.
- Screenshot `docs/reviews/phase5.png`. Fix issues before Phase 6.

---

## Phase 6 — Dashboard Polish & Score UX `[ ]`

**Goal:** portfolio-grade dashboard matching the concept mock.

### Tasks
1. `[ ]` Health Score hero: six animated bars (Code Quality / Security / Testing / Documentation / Dependencies / Architecture), overall score, delta vs. previous analysis of same repo.
2. `[ ]` Findings explorer: group by pillar/severity/agent; code snippet preview with highlighted lines; citation links to GitHub blob URL at analyzed SHA.
3. `[ ]` Trust panel: per-agent confidence, acceptance rates, verification coverage (% findings verified).
4. `[ ]` Analysis history + compare view (two analyses side-by-side).
5. `[ ]` Empty/error/loading states everywhere; dark theme; responsive to 1280px.

**Acceptance criteria**
- All concept-mock elements present; Lighthouse a11y ≥ 90; no console errors.

**Browser review (agent-browser)**
- Full UX pass: navigation, filters, compare view, mobile-width sanity at 1280px.
- Screenshot `docs/reviews/phase6.png`. Fix issues before Phase 7.

---

## Phase 7 — Evaluation Harness & Deployment `[ ]`

**Goal:** credibility + shipping. *(Decision D9.)*

### Tasks
1. `[ ]` `benchmark/` harness:
   - `seedy-*` sample repos with ground-truth YAML (expected findings).
   - Metrics: precision/recall/F1 per pillar; verifier agreement rate; report generated to `benchmark/REPORT.md` and surfaced in README.
   - Optional: JITVUL-style pairwise commits subset (public CVEs) as an offline eval script.
2. `[ ]` GitHub Actions: full CI (lint/type/test/build) + nightly benchmark smoke on seedy repos.
3. `[ ]` Production compose: multi-stage Dockerfiles, non-root users, healthchecks, `docker-compose.prod.yml`; deployment docs for Azure (Container Apps + Azure DB for PostgreSQL) and AWS (ECS + RDS).
4. `[ ]` `docs/RESEARCH.md`: map every D-decision to its paper citation (from section 0).
5. `[ ]` README: architecture diagram, score screenshot, benchmark numbers, quickstart.

**Acceptance criteria**
- CI green; benchmark report reproducible with one command; fresh-clone `docker compose up` works.

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
