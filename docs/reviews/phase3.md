# Phase 3 — Browser Review Log

**Date:** 2026-09-25
**Method:** agent-browser against the live local stack (API :8110 · Celery worker · Vite :5175 · Postgres :5433 · Redis :6390 · pgvector 0.6.0)

## Flow verified (psf/requests)

1. Dev login → opened the latest requests analysis (63 findings) → **Explore** tab.
2. **Graph summary** rendered: 844 symbols (37 modules / 96 classes / 166 functions / 545 methods), 2170 call edges, 857 import edges, 3027 total.
3. **Semantic search** ("authentication") → mode `semantic`, 8 results, `src/requests/auth.py` and `src/requests/utils.py:get_auth_from_url` as top hits.
4. **Graph search** ("Session") → mode `graph`, returns `src.requests.sessions`, `Session`, `SessionRedirectMixin`.
5. **Symbol browser** filter + selection → clicked `module auth` → dependency view populated.
6. **Dependency view** for `src.requests.auth`:
   - Depends on: `_internal_utils`, `compat`, `cookies`, `utils`, `models` (resolved module names).
   - Used by: `adapters`, `_types`, `models`, `sessions`, `tests.test_requests`.
7. **Seedy repo** (`local://…/benchmark/seedy-python-app`, analysis #10): neighborhood(`entry_point_a`) → `entry_point_a → helper_b` (calls) and `helper_b → entry_point_a` (calls) — the import cycle is visible as real call links; 8 call + 7 import edges.
8. Console: 0 errors.

Screenshots: `docs/reviews/phase3.png`, `docs/reviews/phase3-explore-top.png`.

## Backend verification (API level)

- `GET /graph/summary`, `/graph/symbols`, `/graph/callers`, `/graph/callees`, `/graph/imports`, `/graph/dependents`, `/graph/path`, `/graph/neighborhood`, `/search` — all exercised.
- Seedy: `dependents(app.module_a)` → `[app.module_b]`; `path(app.module_a → app.module_b)` → `[app.module_a, app.module_b]`.
- Embeddings: requests analysis produced 794 chunks, all 794 embedded with fastembed `BAAI/bge-small-en-v1.5` (384-dim) stored in pgvector; HNSW index created.

## Bugs found & fixed during the phase

| Bug | Root cause | Fix |
|-----|-----------|-----|
| `callees(login)` returned nothing | call edges were attached to the module, not the enclosing function | indexer now attributes each call to its enclosing symbol (function/method/class scope); callers/callees work on real symbols |
| Relative imports unresolved (0 dependents for requests) | `from .models import X` / `from . import x` not handled; `__init__.py` mapped to `…__init__` | `resolve_import` handles relative levels, `.`-prefix joining, `__init__` → package, and a shortest-suffix fallback for `src/` layouts |
| Call graph invisible in neighborhood/path | `Edge.dst_symbol_id` is NULL for calls | `_adjacency` resolves call targets by name (same-file preferred) |
| "Used by" listed the root node instead of dependents | UI rendered `link.target` for both directions | `LinkList` takes a `field` prop (`target` for outgoing, `source` for incoming) |
| Long module names overlapped the IMPORTS label | no truncation + 2-column squeeze | truncate with title tooltip; stack lists vertically |
| Import edges surfaced raw relative names (`._types`) | `imports()` returned `dst_name` | prefers the resolved symbol name when available |

## Notes / known limitations

- Call resolution is best-effort by simple name (no full type inference); ambiguous names prefer same-file matches. Documented as a deliberate v1 bound — it is still ≥ the plan's "best-effort" target.
- Import resolution covers ~43% of raw import edges on requests (mostly `from x import symbol` clauses that name attributes, plus stdlib); all *module-level* dependencies used by the graph resolve.
- Dev environment restarts wiped `/tmp` (redis build + env), so these were moved to persistent, gitignored `.local/` plus a committed `scripts/dev-local.sh`.

## Acceptance criteria status

- [x] `callers()` / `dependents()` / `imports()` correct against real imports; semantic "authentication" returns the auth module in top results
- [x] Graph build + embed for ~850 symbols / 3000 edges completes well within the time budget (~5 min including semgrep + embedding on a small CPU)
- [x] Explore tab: graph summary, semantic + graph search, symbol browser, dependency neighborhood
- [x] No console errors
