# AI Engineering Intelligence Platform

Give it a GitHub repository — get back a **Repository Health Score** with verified,
cited findings across code quality, security, testing, documentation, dependencies,
and architecture.

Deterministic analysis tools run first (Semgrep, gitleaks, OSV, coverage,
complexity). An [eve](https://eve.dev) agent then answers questions and runs deep
reviews over the repository's **symbol graph** and those tool results — no vector
store, no embedding retrieval. A verification layer re-checks every agent claim
before it counts, and high-severity claims wait for a human. See `docs/RESEARCH.md`
for the research basis and `implementation.md` for the build plan.

## Architecture

```text
                    ┌──────────────────────────┐
  browser ────────► │  frontend (Vite + React) │
                    └────┬──────────────┬──────┘
                         │ /api/*       │ /eve/v1/*  (chat, approvals, streams)
                         ▼              ▼
        ┌────────────────────────┐  ┌──────────────────────────────┐
        │  backend (FastAPI)     │  │  agent/ (eve)                │
        │  repos · analyses      │  │  17 tools over graph/findings│
        │  deterministic tools   │◄─┤  5 review subagents         │
        │  verification + trust  │  │  HITL: run_analysis,         │
        └───────┬───────────────┘  │        decide_finding         │
                │                  └──────────────────────────────┘
                ▼
   Postgres (analyses, symbols, edges, findings)   Redis (progress events)
                ▲
                │  Celery worker: ingest → index → 8 analyzers → verify → score
```

The agent holds no state of its own: every fact it reports comes from the API, and
every claim it records is stored as an unverified `hypothesis` that the trust layer
re-checks. The agent cannot publish a score or judge a finding by itself.

## Quickstart (Docker)

```bash
cp .env.example .env      # set AI_INTEL_AGENT_TOKEN and AI_INTEL_JWT_SECRET
cd infra
docker compose up --build
```

- Frontend: http://localhost:5173 (Vite dev server)
- API: http://localhost:8000 (`/api/health`, OpenAPI at `/docs`)
- Agent: http://localhost:3000 (`/eve`)

### Production

```bash
cd infra
POSTGRES_USER=... POSTGRES_PASSWORD=... \
AI_INTEL_JWT_SECRET=... AI_INTEL_AGENT_TOKEN=... AI_GATEWAY_API_KEY=... \
docker compose -f docker-compose.prod.yml up --build
```

Differences from the dev stack, all deliberate:

| | dev | prod |
| --- | --- | --- |
| Frontend | Vite dev server, HMR | nginx serving the built bundle |
| Published ports | 5173, 8000, 3000 | 80 only — the API and agent are internal |
| Healthchecks | none | every service; dependents wait for `service_healthy` |
| Users | default | non-root (`intel`, `eve`), code dirs read-only |
| Agent state | ephemeral | `agent_state` volume, so sessions survive restarts |
| Secrets | dev defaults | refused at startup if unset |
| Migrations | on boot | on boot, before uvicorn |

GitHub OAuth is required in production (`AI_INTEL_DEV_LOGIN=0` is forced), and the
session cookie is marked `Secure`, so the frontend must be served over HTTPS —
put a TLS-terminating proxy in front and set `PUBLIC_URL`.

Set `AI_INTEL_DEV_LOGIN=1` for passwordless dev login, or configure a GitHub OAuth
app (`AI_INTEL_GITHUB_CLIENT_ID` / `..._SECRET`).

## Local development

The eve agent needs **Node >= 24** and the backend needs Postgres and Redis. With
those in place, one command starts everything (API, worker, agent, frontend):

```bash
cp .local/env.sh.example .local/env.sh   # machine-specific ports, paths, secrets
source ~/.nvm/nvm.sh && nvm install 24
bash scripts/dev-local.sh start
```

- Frontend: http://localhost:5175 · API: http://localhost:8110 · Agent: http://localhost:3000

Or run the pieces individually:

```bash
cd backend && . .venv/bin/activate && alembic upgrade head
uvicorn app.main:app --port 8000
celery -A app.tasks.celery_app:celery_app worker -l info

cd frontend && npm run dev
cd agent && npm run dev            # eve dev; or `npm run build && npm start`
```

## Benchmark

The pipeline is scored against fixture repositories with known planted conditions:

```bash
cd backend
python -m app.benchmark --repo seedy-python-app            # writes benchmark/REPORT.md
python -m app.benchmark --repo seedy-python-app --stdout   # print instead
```

Latest run on `benchmark/seedy-python-app` (analysis #18, 11 planted expectations):

| Metric | Value |
| --- | --- |
| Recall | **100%** (10/10 detectable expectations found) |
| Precision (deduplicated) | **91%** (10 matched, 1 unenumerated, 5 duplicate reports) |
| Precision (raw, per finding) | 62% |
| F1 | 0.77 |
| Verification coverage | 92% (23 verified / 2 hypothesis) |
| Planted false positives triaged | 1/1 dismissed |

Two numbers are reported on purpose. A ground-truth file enumerates *conditions*,
while a pipeline reports findings per *(tool × rule × occurrence)*, so flagging one
hardcoded key with three rules is three findings for one problem. `Precision
(deduplicated)` excludes repeat reports of an already-matched condition;
`Precision (raw)` does not. The report lists every duplicate so the noise is
visible rather than averaged away.

### Defect this benchmark surfaced, and the fix

The first run flagged a finding in `app/settings.py:1` under
`category: vulnerability` — the AWS key was filed as a generic vulnerability
rather than a `secret`, putting it in the wrong pillar and the wrong ground-truth
bucket. Cause: `semgrep.py` mapped *every* rule containing `.security.` to
`vulnerability`, and semgrep's credential rules live under `generic.secrets.*`,
which also satisfies that test.

`categorize_check()` now tests the secrets namespace first, covered by
`tests/test_semgrep_categories.py` (10 cases). Re-scored against the same findings
with the corrected category, deduplicated precision goes **91% → 100%** and the
finding is correctly recognised as a repeat report of the same key.

The committed report still shows 91% because analysis #18 predates the fix; the
next run with semgrep installed will show 100%. Semgrep is not installed in this
development environment, so the fix is verified by unit test and by re-scoring,
not by a fresh end-to-end run.

## Configuration

| Variable | Where | Purpose |
| --- | --- | --- |
| `AI_INTEL_DATABASE_URL`, `AI_INTEL_REDIS_URL` | backend | storage and progress bus |
| `AI_INTEL_JWT_SECRET` | backend **and** agent | signs session cookies; the agent verifies the exchanged eve token (`iss=ai-intel`, `aud=eve-agent`) |
| `AI_INTEL_AGENT_TOKEN` | backend **and** agent | shared secret the agent presents on service calls (`X-Agent-Token`); blank disables agent API access |
| `AI_INTEL_LLM_PROVIDER` | agent | `mock` for the deterministic fixture model (evals, CI, offline review) or `gateway` |
| `AI_INTEL_MODEL` | agent | model id when not mocking |
| `AI_INTEL_API_URL` | agent | base URL of the backend API (default `http://localhost:8110`) |

## Checks

```bash
# backend
cd backend && ruff check . && ruff format --check . && mypy && python -m pytest

# frontend
cd frontend && npm run lint && npm run typecheck && npm test && npm run build

# agent
cd agent && npm run typecheck && npm run build && npm run eval
```

`npm run eval` runs the agent's evals hermetically: a fixture model plus an
in-process fixture API, so no provider credentials, database, or containers are
needed. 9 cases / 30 gates cover tool discipline, the citation rule, multi-turn
behaviour, and the human-in-the-loop gates.

Two further cases grade *answer quality* with a judge model. They skip themselves
unless a provider is configured, so CI stays green while the suite stays ready:

```bash
AI_INTEL_LLM_PROVIDER=gateway \
AI_INTEL_MODEL=anthropic/claude-sonnet-4.5 \
AI_GATEWAY_API_KEY=... \
AI_INTEL_EVAL_LIVE=1 \
npm run eval -- quality
```

Set `AI_INTEL_JUDGE_MODEL` if the judge should use the same provider as the agent.

## Layout

- `agent/` — eve agent: instructions, tools, subagents, evals (Node 24)
- `backend/` — FastAPI API, Celery analysis pipeline, Alembic migrations
- `frontend/` — React + Vite dashboard
- `infra/` — Docker Compose services
- `benchmark/` — evaluation repos + ground truth
- `docs/` — research notes, architecture decisions, per-phase review logs
