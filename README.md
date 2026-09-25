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

- Frontend: http://localhost:5173
- API: http://localhost:8000 (`/api/health`, OpenAPI at `/docs`)
- Agent: http://localhost:3000 (`/eve`)

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
needed. The suite covers tool discipline, the citation rule, and the human-in-the-loop
gates.

## Layout

- `agent/` — eve agent: instructions, tools, subagents, evals (Node 24)
- `backend/` — FastAPI API, Celery analysis pipeline, Alembic migrations
- `frontend/` — React + Vite dashboard
- `infra/` — Docker Compose services
- `benchmark/` — evaluation repos + ground truth
- `docs/` — research notes, architecture decisions, per-phase review logs
