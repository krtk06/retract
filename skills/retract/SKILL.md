---
name: retract
description: >-
  Resolve one Retract repository-health finding: change the cited code so the
  claim no longer holds, make the fix survive Retract's verifier and analyzers,
  and hand the user the push and re-analyze steps. Use when the user pastes a
  Retract finding block, or asks to "fix this finding", "resolve this Retract
  finding", "make the Retract score go up", or "why did my Retract score not move".
metadata:
  version: 1.0.0
---

# Retract — resolve one finding

Retract analyzed the repository you already have open and reported a finding.
Your job: change the code so the claim no longer holds, prove it with the
repo's own checks, and hand back. The pasted block is complete — parse it, do
not go hunting for more findings.

## What you were handed

- **Instruction** — the `action` line. That is the fix in one sentence.
- **Finding block** — id, category, pillar, severity, status, confidence,
  verifier, agent, effort, title, description, cited `file:lines`.
- **Snippet** — the cited region, when the analysis stored one. You have the
  repository locally: read the real file, the snippet is orientation only.
- **Evidence** — the raw JSON the detector recorded (rule id, package and
  version, measured complexity, cycle members, and so on). Read it before
  touching anything.

## Procedure

1. **Confirm the claim.** Read the cited region. If the finding is wrong, stop
   and say so — do not "fix" working code. The user can dismiss it in Retract,
   which removes its weight cleanly.
2. **Fix the code, not the symptom.** `references/categories.md` has the fix
   that survives re-analysis for each of the scored categories.
3. **Add a regression test that fails without the fix**, wherever the repo has
   a test suite or an obvious place for one.
4. **Run the repository's own checks.** Find the commands in its AGENTS.md,
   README, Makefile, or CI config — lint, typecheck, tests. Do not guess.
5. **Hand off.** Show the diff and the checks output, then say:

   > Done. Push this branch, then in Retract click **Re-analyze** on the
   > repository — it re-clones at the new HEAD and re-scores. Use the analysis
   > page's History A/B comparison to see the score move.

   Do **not** commit or push yourself unless the user asked.

## What actually moves the score

Read `references/scoring.md` before choosing how to fix. The parts that
surprise people:

- **The overall is capped at `worst_pillar + 15`.** While the cap binds, only
  raising the worst pillar moves the headline; a fix elsewhere raises its
  pillar score and nothing else.
- **Half of the weight is trust.** Unverified findings weigh half; dismissed
  weigh zero. A "fix" that leaves the pattern detectable keeps the finding a
  hypothesis at 0.5 weight — see `references/verification.md`.
- **The curve is penalty per KLOC.** Fixing the finding is the only clean
  lever. Adding or deleting lines dilutes or concentrates the density of the
  findings that remain — padding code to dilute density is gaming, not
  fixing, and the LOC is visible in the UI.

## Hard rules

- **Never silence a detector**: no lint suppression, no `# nosec`, no ignore
  lists, no deleted test, no weakened threshold. If a rule is wrong, say so
  and let the user dismiss the finding.
- **Minimal diff.** Follow the repository's existing style and conventions.
- **Cite what changed**: state the `file:line` before and after.
- **One finding per hand-off.** Do not touch unrelated code.
