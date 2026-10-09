# Category playbook

What Retract detects, and the fix that survives re-analysis, for every scored
category. Grouped by pillar, with pillar weights (security .25, code-quality
.20, testing .20, architecture .15, documentation .10, dependencies .10).

## Security — weight 0.25, the heaviest pillar

### `secret` — semgrep `.secrets.` rules, gitleaks
Rotate first, code second. The value is compromised the moment it is
committed, not when you notice: revoke and reissue at the provider, move the
replacement into the environment or a secret manager, delete the literal.
Retract verifies secrets by re-scanning the cited lines for the credential
pattern (`AKIA…`, `password|secret|token|api_key = "…"`); a redacted string
that still looks like a credential stays a finding. Purging the value from git
history is worth doing for the exposure it removes, but Retract runs gitleaks
with `--no-git`, so deleting the literal is what clears the finding.

### `injection` — the security subagent (agent-reported)
Trace untrusted input to the sink through the caller graph, then close the
path: parameterised queries, argv lists, allow-lists at the boundary. Retract
verifies by searching the cited window for dangerous patterns
(`execute(`, f-string/`%`/`+` built SQL, `select|insert|update|delete` with
interpolation). Deleting the vulnerable line without removing the pattern from
the surrounding window leaves a finding that still verifies. Add a test that
attempts the injection and fails before your fix.

### `vulnerability` — semgrep `.security.` / `.audit.` rules
Read the flagged region, confirm it is reachable, then fix the code path:
validate or encode untrusted input at the boundary, before the sink; prefer
parameterised APIs over string-built queries and shell commands. Re-check the
specific rule the evidence names (`rule`) after the change — semgrep runs
again on the fresh clone.

### `weak-crypto` — the security subagent (agent-reported)
`hashlib.md5|sha1` for anything security-relevant is the flag. SHA-256 for
integrity, bcrypt or argon2 for passwords, AES-GCM with a unique nonce for
ciphers, the `secrets` module for randomness. Rotate existing hashes: re-derive
at next login rather than migrating in place.

### `vulnerable-dependency` — OSV advisory match on the lockfile/manifest
Upgrade to the first unaffected release, not necessarily the newest. Commit
the updated lockfile, not just the manifest. Run the test suite: a major bump
can change behaviour. Retract re-checks that the advisory no longer matches
the pin.

## Code quality — weight 0.20

### `complexity` — radon, cyclomatic complexity ≥ 10 (≥ 20 = high)
Extract branch groups into named functions, flatten guards with early returns.
Pin current behaviour with a test first. Aim below the threshold, not merely
lower — the re-run re-measures the same function with the same rule.

### `maintainability` — radon, maintainability index < 65
Complexity drives the index: shrink the longest functions, remove dead code,
collapse duplicated blocks. Re-measure after the structure changes, not after
formatting.

### `duplication` — token-hash sliding window, type-2 clones, ≥ 30 normalized lines
Extract one shared function, replace both call sites, delete the second copy.
Normalizing means renamed identifiers still match — so renaming variables does
not fix duplication, extracting it does.

### `code-smell` — semgrep rules that are neither secrets nor security/audit
Decide: real defect or idiom. Fix the construct the rule names, or make the
case that it is a false positive and let the user dismiss it. Do not suppress
the rule.

## Testing — weight 0.20

### `coverage` — no test files found at all
Stand up the runner the language implies, one end-to-end pass over the main
path first, then a regression test per verified high-severity finding. Wire it
into CI. Highest-effort item in the plan; also the one that protects every
other fix you make.

### `missing-tests` — no test file imports the cited package
Write tests for public functions by caller count, then the error branches.
Retract verifies by re-scanning `tests/` and `test/` for an import of the
package — put the tests where the checker looks, importing the package it
named in the evidence.

## Documentation — weight 0.10

### `readme` — no README.md / README.rst / README at the root
What it is (two lines), install + run command, one minimal working example.
Retract checks the root for the file; put it there.

### `docstring` — fewer than 50% of a module's public symbols documented
Documented means a docstring on each public function, class, or method —
public meaning not `_`-prefixed, and the module needs ≥ 2 public symbols to be
flagged. One line on what each returns, the arguments the signature does not
explain, what it raises, and side effects.

## Dependencies — weight 0.10

### `outdated-dependency` — pin behind the latest registry release
Move the pin, read the changelog for behaviour changes, run the test suite.
Lower priority than `vulnerable-dependency`: old-but-patched is a hygiene
issue, not a breach.

## Architecture — weight 0.15

### `import-cycle` — an actual cycle in the symbol graph
Move the shared low-level type into a module neither side imports back; if
that is too large, make one edge a local (function-level) import. Retract
verifies by re-walking the graph for a 2- or 3-cycle among the named modules —
the cycle must actually be gone, not shorter.

### `god-module` — fan-in ≥ 10 modules importing it (threshold from evidence)
Group symbols by responsibility, move each group out, keep the original as a
thin re-export while callers move over. Retract verifies fan-in ≥ 10 on the
named module, so the count must genuinely drop.

## Displayed but unscored

`inventory`, `tool-error`, `registry-lookup-incomplete`, `test-plan`,
`readme-plan`, `docstring-plan`, `layering`, `coupling`, `code-review`,
`complexity-review`, `insight` — not in `CATEGORY_PILLAR`, so they cannot
move the score. Fix them when they are real; say so either way.
