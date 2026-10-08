# Verification rules

Why a fix counts at full weight or half. Source of truth:
`backend/app/analysis_engine/verify.py` — CI asserts this file still describes
it.

After every analysis, Retract re-checks each hypothesis finding with
deterministic means. A finding that passes becomes `verified` (weight 1.0,
confidence floored at 0.8). One that fails stays a `hypothesis` with
`verification_error` recorded (weight 0.5, confidence capped at 0.4).

Your fix is done when the finding it addresses no longer verifies — or better,
when the detector no longer reports it at all.

## The checks, per agent

Only findings from the `security`, `code`, `tests`, `docs`, and `architecture`
agents are verified; tool findings (`tool:semgrep`, `tool:gitleaks`, …) are
already deterministic.

1. **Citation (everything).** The cited file must exist in the analysis
   snapshot, and the cited line must exist in the file. A fix that moves code
   without leaving the cited region valid can flip a verified finding into a
   failed citation — expect the line numbers to change and re-cite them.
2. **Security — source-pattern.** The cited window (±3 lines, then the whole
   file) is searched for the category's dangerous patterns:
   - `injection`: `execute(`, f-string/`%`/`+`-built SQL, keywords with
     interpolation;
   - `secret`: `AKIA…`, `password|secret|token|api_key = "<literal>"`;
   - `weak-crypto`: `hashlib.md5|sha1(`, `hashlib.new("md5"|"sha1")`.
   If any pattern survives anywhere in the cited file, the finding still
   verifies. Remove the pattern, not just the flagged line.
3. **Security — cross-tool fallback.** A secret claim can also verify by a
   deterministic tool (`tool:gitleaks`, `tool:semgrep`) flagging the same
   file and line. After removing a secret, confirm the tool would not flag
   the replacement.
4. **Architecture — graph-cycle.** For cycles, Retract parses the cycle
   members from the finding and re-walks the import graph. Any 2- or 3-cycle
   among the named modules keeps the finding. The cycle must be truly gone.
5. **Architecture — graph-fan-in.** For coupling/split claims, fan-in must
   be ≥ 10 to verify. A split that leaves 10 importers keeps the finding.
6. **Tests — test-presence.** Inverted: a `missing-tests` finding *verifies
   when no test imports the package*. Your fix — adding the test — makes the
   check fail, which is correct: the finding disappears because the checker
   no longer reports it, and the verification pass simply never sees it again.
7. **Docs — readme-check.** Inverted the same way: `readme` verifies only
   while no README exists at the root.
8. **Docs — docstring-check.** For `docstring-plan`, the module is re-parsed;
   the finding verifies only while public-symbol docstring coverage is < 50%.
   Document enough public symbols to cross the line.

## What re-flags your fix on the next run

The deterministic analyzers run again from scratch on the fresh clone:

- **semgrep** re-scans the whole tree — a pattern moved to another file is a
  new finding, not a fix;
- **gitleaks** re-scans history and tree for credentials;
- **radon** re-measures every function: complexity ≥ 10 re-files immediately;
- the **duplication** detector re-walks the tree — a copy you left behind
  re-files;
- the **tests** checker re-scans for imports of every package;
- the **docs** checker re-counts docstrings and README presence;
- the **architecture** walker re-finds cycles and fan-in on the new graph.

## Before you hand back

- [ ] The claim is false: reading the new code, no dangerous pattern exists at
      the cited site — or the missing thing now exists.
- [ ] A regression test covers the fix and fails without it (where a suite exists).
- [ ] The repo's lint, typecheck, and tests pass with your change.
- [ ] Nothing was suppressed, ignored, or deleted to make a finding vanish.
- [ ] The diff is minimal and cites before/after `file:line`.
- [ ] If the finding was wrong: say so, do not change code, suggest dismissal.
