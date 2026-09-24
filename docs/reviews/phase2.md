# Phase 2 — Browser Review Log

**Date:** 2026-09-24
**Method:** agent-browser against the live local stack (API :8110 · Celery worker · Vite :5175 · Postgres :5433 · Redis :6390)

## Flow verified

1. Dev login → repo list (seedy + psf/requests).
2. **Seedy repo** (`local://…/benchmark/seedy-python-app`, via `AI_INTEL_ALLOW_LOCAL_REPOS=1`):
   - Analysis #3 `done` in ~7s, 16 findings, 71 LOC.
   - Health Score: 0/100 overall — all six pillars 0 (correct for a deliberately seedy repo).
   - Progress trace shows the full pipeline: clone → inventory → symbol index (15 symbols) → 8 tool events with per-tool finding counts and durations → done.
   - All ground-truth expectations found with correct file:line citations:
     secret (`app/settings.py:1`, gitleaks), SQL injection (`app/db.py:10`, semgrep),
     vulnerable deps requests==2.6.0 / flask==0.12.2 (OSV), outdated deps (PyPI),
     complexity CC 12 (`app/complex.py`, radon), duplication (logic_beta.py:4 ↔ logic_alpha.py),
     no test suite, no README, docstring coverage 0/2 (`app/db.py`), import cycle
     (module_a → module_b → module_a, resolved via the symbol graph).
   - Score screenshot: `docs/reviews/phase2-score.png`; full page: `docs/reviews/phase2.png`.
3. **Filters**: pillar filter (Security → 6 findings), severity filter (high → 6), both live-update the count.
4. **Real repo** (psf/requests): analysis `done` in ~60s, 51 findings.
   - Scores: overall 85 — Testing 98, Security 82, Architecture 100, Dependencies 100, Documentation 87, Code Quality 54 (radon: 13 CC≥10 + 2 CC≥20 functions + 17 low-MI modules — defensible for a strict tool; v1 heuristic).
   - "view on GitHub ↗" citations resolve to the analyzed SHA (verified href).
   - Screenshot: `docs/reviews/phase2-requests.png`.
5. Console: 0 errors on all pages.

## Bugs found during the phase (all fixed before/during review)

| Bug | Root cause | Fix |
|-----|-----------|-----|
| Edges table empty → no import cycles | Edge source lookup used literal `"module"` as symbol name instead of the dotted module name | Walkers now carry the real module name in the edge source key; lookup via `module_id_by_file` |
| Semgrep found 0 findings in cloned dirs | Non-git dirs make `git ls-files` empty → semgrep skips all files | Added `--no-git-ignore` to the scan command |
| OSV vulnerable deps never reported | API returns `vulns` objects; parser read `vuln_ids` | Parse `result["vulns"]` |
| Duplication missed identifier-renamed clones | Whitespace-only normalization | Type-2 clone detection: identifier/number/string token normalization |
| False vulnerable-deps for psf/requests | Floor pins (`idna>=2.5`) treated as installed versions | Only exact `==` pins (python) / exact versions (npm) are checked |
| Real repos scored 0 | Per-KLOC penalty scale too aggressive (10) | Calibrated SCALE to 2.0 (one medium per KLOC ≈ −2 points) |

## Notes

- gitleaks + semgrep both flag the planted AWS key in the seedy repo (different agents, same defect) — cross-agent dedup is a Phase 4+ concern.
- Local-repo mode (`local://…`) is a dev-only hook used by the benchmark; guarded by `AI_INTEL_ALLOW_LOCAL_REPOS`.
- Docker: gitleaks installed in the backend image; semgrep/radon/tree-sitter via pip deps.

## Acceptance criteria status

- [x] Seedy repo yields findings in every pillar with correct file:line
- [x] Scores compute and render; no LLM keys required
- [x] Score bars + findings table with filters render in dashboard
- [x] No console errors; empty states and progress streaming verified
