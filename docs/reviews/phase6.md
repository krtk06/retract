# Phase 6 — Browser Review Log

**Date:** 2026-09-25
**Method:** agent-browser against the live local stack (API :8110 · Celery worker · Vite :5175 · Postgres · Redis)
**LLM provider:** `mock` (offline harness, same caveat as Phases 4–5)

## Flow verified (seedy benchmark repo, analysis #18)

1. **Score hero** (`docs/reviews/phase6-hero.png`): animated overall score (`requestAnimationFrame`
   count-up), "no change vs previous" delta, LOC/KLOC, and six pillar bars ordered by risk
   (Security first) with `v / h / d` counts and ARIA `progressbar` values.
2. **Findings explorer** (`docs/reviews/phase6.png`): findings grouped by pillar, each with
   severity badge, verified/hypothesis/dismissed badge, verifier + calibrated confidence,
   `file:line`, and a **show code** preview — the snippet endpoint serves the analyzed
   snapshot with the cited line highlighted (`app/settings.py:1` AWS key confirmed).
3. **Trust Summary** (`docs/reviews/phase6-trust.png`): verification coverage **92%**, average
   confidence **0.78**, status chips (26 findings / 23 verified / 2 hypotheses / 1 dismissed),
   a per-agent table (Static-Analysis 0.84, Security 0.78, Docs 0.71, Dependencies 0.81,
   Architecture 0.79, Testing 0.80, Ingestion 0.80, Code 0.76, Tests 0.41) and human acceptance
   rates per agent/category.
4. **History + compare** (`docs/reviews/phase6-trust-history.png`): the repository's analysis
   history (newest first, with status, timestamp, commit, finding count, score) and a
   side-by-side comparison (`#17 → #18`) with overall delta and a per-pillar Δ table.
5. **Explore tab** still functional after the refactor (graph summary, search, dependency view).
6. **A11y / responsive**: exactly one `<h1>` per page, all buttons/inputs/selects labeled or
   wrapped, no `img` without `alt`, `<html lang="en">`, descriptive `<title>`, no horizontal
   overflow at 1280px, all body text at `zinc-400`+ (AA contrast).
7. Console: **0 errors** on a clean load.

## Bugs found during the phase

| Issue | Root cause | Fix |
|-------|-----------|-----|
| `GET /analyses/compare` returned 422 | route declared after `/{analysis_id}`, so the literal path was shadowed by the int path param | moved the route above the parameterized ones (documented in a comment) |
| `Query(min_length=1)` on int params | `min_length` applies to sized types | switched to `Query(ge=1)` |
| `trust-summary` 500 on real data | agent buckets were keyed `hypotheses` but incremented with `status.value` (`hypothesis`) | aligned the bucket key to the enum value |
| no `<h1>` on the analysis page | repo title rendered as `<h2>` | promoted it to `<h1>` |
| HMR-transient React errors during editing | live-reload of partially saved files | cleared on reload; not a code defect |

## Notes

- The snippet endpoint is snapshot-based (reads the analyzed commit) and rejects any path
  escaping the repository root.
- The delta ("vs previous") uses the most recent earlier analysis **with a score**, so the
  first run correctly shows no delta.
- `docs/reviews/phase6.png` is the full overview tab; `phase6-hero.png`, `phase6-trust.png`,
  and `phase6-trust-history.png` cover the individual sections.

## Acceptance criteria status

- [x] Health Score hero: animated bars, overall score, delta vs previous analysis
- [x] Findings explorer: grouping, code snippet preview, GitHub blob links
- [x] Trust panel: per-agent confidence, acceptance rates, verification coverage
- [x] Analysis history + compare view
- [x] Empty/error/loading states, dark theme, no horizontal overflow at 1280px, no console errors
- [x] a11y fundamentals: single `h1`, labeled controls, `lang`/`title` present
