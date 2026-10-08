# Scoring model (Retract score v5)

Source of truth: `backend/app/analysis_engine/scoring.py`. CI runs
`scripts/verify-skill.sh`, which asserts every number below still matches it.
If the repository's curve changed, this file is stale — re-read the source.

## The formula

Per pillar:

```
score = 100 / (1 + weighted_penalty_per_KLOC / 30)
```

Overall:

```
overall = min(weighted_mean, worst_pillar + 15)
```

- **30** weighted points per KLOC is half marks (`HALF_SCORE_DENSITY`). The
  curve is a ratio: 100 with no findings, 50 at the half-score density,
  asymptotic to 0, never hard-clamped.
- **No LOC measured → count basis.** The same curve over raw weighted points,
  half marks at **20** points (`COUNT_HALF_SCORE_PENALTY`). The score payload
  records which basis produced it (`basis: "density" | "count"`); the two
  kinds of number are not comparable.
- **A pillar with findings floors at 1**, never 0 — still terrible, still
  ordered, never ambiguous with "not measured".
- A pillar no analyzer measured scores 100 and can never lower the cap.
  The UI shows it as "not measured", which is not the same as clean.
- **15** above the worst pillar is the cap's slack (`WORST_PILLAR_HEADROOM`);
  **0.001** KLOC is the density floor (`MIN_KLOC`), only a guard against
  division by zero when LOC exists but is tiny.

## The weights

Severity weight (`SEVERITY_WEIGHT`): critical **30**, high **20**, medium
**10**, low **5**, info **0**.

Status factor (`STATUS_FACTOR`): verified **1.0**, hypothesis **0.5**,
dismissed **0.0**. Penalty per finding = severity × status.

Pillar weights (`PILLAR_WEIGHTS`): security **0.25**, code-quality **0.2**,
testing **0.2**, architecture **0.15**, documentation **0.1**,
dependencies **0.1**.

## Consequences for fixing

1. **The only clean lever is making the claim false.** Fixing a finding
   removes its severity × status weight from the numerator. Everything else —
   LOC churn, formatting, moving code around — only dilutes or concentrates
   the findings that remain.
2. **The cap decides whether the headline moves.** `overall` is
   `min(weighted_mean, worst_pillar + 15)`. While the cap binds, fixing a
   non-worst pillar raises the pillar score and the weighted mean but leaves
   the headline exactly where it was. Raising the worst pillar always moves
   it. If you were handed a non-worst finding, fix it anyway — its pillar
   rises — but be honest that the headline may not move until the worst
   pillar is addressed.
3. **Trust doubles the value of a verifiable fix.** A finding that ends up
   verified weighs double a hypothesis. A fix that survives
   `references/verification.md` is therefore worth twice one that leaves the
   pattern detectable — and a dismissed false positive removes the weight
   entirely.
4. **LOC is a denominator.** Adding lines lowers every remaining finding's
   density; deleting lines raises it. Do not chase this in either direction:
   padding code to dilute density is gaming, and a huge diff that "fixes" one
   finding while adding hundreds of lines will read as exactly that.
5. **Some categories display but score zero.** `inventory`, `tool-error`,
   `registry-lookup-incomplete`, and the agent plan categories (`test-plan`,
   `readme-plan`, `docstring-plan`, `layering`, `coupling`, `code-review`,
   `insight`, `complexity-review`) are not in `CATEGORY_PILLAR`. Fixing them
   is often still right — but they cannot move the score until Retract maps
   them.
