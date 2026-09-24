# AI Engineering Intelligence Platform

Give it a GitHub repository — get back a **Repository Health Score** with verified,
cited findings across code quality, security, testing, documentation, dependencies,
and architecture.

Hybrid design: deterministic analysis tools run first (Semgrep, gitleaks, OSV,
coverage, complexity), LLM agents reason on top of tool output, and a verification
layer checks every agent claim before it counts. See `docs/RESEARCH.md` for the
research basis and `implementation.md` for the build plan.

## Quickstart (Docker)

```bash
cp .env.example .env
cd infra
docker compose up --build
```

- Frontend: http://localhost:5173
- API: http://localhost:8000 (`/api/health`, OpenAPI at `/docs`)

Set `AI_INTEL_DEV_LOGIN=1` for passwordless dev login, or configure a GitHub OAuth
app (`AI_INTEL_GITHUB_CLIENT_ID` / `..._SECRET`).

## Local development

Backend:

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
export AI_INTEL_DATABASE_URL="postgresql+psycopg://<user>@<db>?host=/var/run/postgresql"
export AI_INTEL_REDIS_URL="redis://localhost:6379/0"
export AI_INTEL_DEV_LOGIN=1
alembic upgrade head
uvicorn app.main:app --reload            # API on :8000
celery -A app.tasks.celery_app:celery_app worker -l info   # worker
```

Frontend:

```bash
cd frontend
npm install
npm run dev                              # dev server on :5173 (proxies /api)
```

## Checks

- Backend: `ruff check . && ruff format --check . && mypy && python -m pytest` (from `backend/`)
- Frontend: `npm run lint && npm run typecheck && npm test && npm run build` (from `frontend/`)

## Layout

- `backend/` — FastAPI API, Celery analysis pipeline, Alembic migrations
- `frontend/` — React + Vite dashboard
- `infra/` — Docker Compose services
- `benchmark/` — evaluation repos + harness (Phase 7)
- `docs/` — research basis, per-phase review logs
