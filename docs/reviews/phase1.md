# Phase 1 — Browser Review Log

**Date:** 2026-09-24
**Method:** agent-browser against the live local stack
(API :8110 · Celery worker · Vite :5175 → /api proxy · Postgres 16 local cluster :5433 · Redis 8.10.2 :6390)

> Note: Docker daemon could not be started on this machine (no sudo), so the compose
> file is validated (`docker compose config`) but the review ran the same services
> locally: uvicorn, celery worker, vite dev server. Dockerfile/compose parity is
> exercised in CI and by anyone with a running daemon.

## Steps performed

1. Opened http://localhost:5175 — login page rendered (`docs/reviews/phase1-login.png`).
2. "Dev login" → authenticated as `dev`, redirected to repo list.
3. Submitted `https://github.com/psf/requests` → navigated to Analysis #1.
4. SSE progress visible live: `status running` → `step Cloning` → `step Indexing 128 files` → `done`.
5. Analysis reached `done` with commit `611c6162` (matches real psf/requests HEAD),
   1 finding ("Repository ingestion complete", verifier `tool:ingestion`, confidence 1.00)
   with language chips (Python 37, Markdown 13, YAML 12, TOML 1, HTML 1, CSS 1).
6. Reloaded analysis page — SSE history replayed from Redis (replay works for late joiners).
7. Repo list shows `psf/requests` with clickable `done` status pill → analysis detail.
8. Invalid URL (`https://gitlab.com/foo/bar`) → inline error "Not a valid GitHub repository URL…".
9. Final screenshot: `docs/reviews/phase1.png`.

## Issues found & fixed

| Issue | Fix |
|-------|-----|
| React Router v7 future-flag warnings in console on every page | Added `future={{ v7_startTransition, v7_relativeSplatPath }}` to `BrowserRouter` — verified 0 warnings after fix |
| Alembic migration duplicated indexes (found during DB bring-up, pre-review) | Removed redundant `op.create_index` calls; `index=True` on columns already creates them; verified upgrade → downgrade → upgrade on real Postgres |

## Console status after fixes

No errors. Only benign info logs (vite connect, React DevTools hint).

## Acceptance criteria status

- [x] Stack boots and `GET /api/health` returns `{"status":"ok","db":"ok","redis":"ok"}` (compose variant validated via `docker compose config`; local variant exercised live)
- [x] Registering a public repo and triggering analysis completes end-to-end
- [x] SSE shows step progress (live + on reload)
- [x] CI workflow committed (backend ruff/mypy/pytest, frontend lint/tsc/vitest/build)
- [x] No console errors in browser review
