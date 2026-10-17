"""Security, dependency, and code-quality remediation advice.

Keyed by finding category. Each entry receives the finding and returns advice
as specific as the available evidence allows.
"""

from app.analysis_engine.remediation_types import (
    GITHUB_PURGE,
    OWASP_TOP10,
    Remediatable,
    Remediation,
    _names,
    _number,
    _text,
    _where,
)


def _secret(finding: Remediatable) -> Remediation:
    return Remediation(
        action="Rotate the exposed credential",
        steps=[
            "Treat it as compromised — it is in git history now, not just the tree.",
            "Revoke and reissue at the provider, in that order, before touching code.",
            "Move the new value into the environment or a secret manager.",
            f"Remove the literal at {_where(finding)} and replace it with a lookup.",
            "Purge the value from history if the repo was ever pushed publicly.",
        ],
        effort="low",
        verify="Re-run the analysis: the secret finding should disappear.",
        references=[
            GITHUB_PURGE,
            f"{OWASP_TOP10}/A07_2021-Identification_and_Authentication_Failures/",
        ],
    )


def _vulnerability(finding: Remediatable) -> Remediation:
    rule = _text(finding.evidence_json or {}, "rule")
    steps = [
        f"Read the flagged region at {_where(finding)}; confirm it is reachable.",
        "Validate or encode untrusted input at the boundary, before the sink.",
        "Prefer a parameterised API over string-built queries or shell commands.",
    ]
    if rule:
        steps.append(f"Re-check the specific rule ({rule}) after the change.")
    return Remediation(
        action="Fix the flagged code path",
        steps=steps,
        effort="medium",
        verify="Re-run the analysis: the vulnerability finding should disappear.",
        references=[f"{OWASP_TOP10}/A03_2021-Injection/"],
    )


def _injection(finding: Remediatable) -> Remediation:
    return Remediation(
        action="Close the injection path",
        steps=[
            f"Trace untrusted input to the sink at {_where(finding)}.",
            "Confirm the path with the caller graph, not by reading the line alone.",
            "Use a parameterised API (prepared statements, argv lists).",
            "If the sink is unavoidable, allow-list values instead of blocking them.",
            "Add a test that attempts the injection; it should fail before the fix.",
        ],
        effort="medium",
        verify="Re-run the analysis: the injection finding should be gone or dismissed.",
        references=[f"{OWASP_TOP10}/A03_2021-Injection/"],
    )


def _weak_crypto(finding: Remediatable) -> Remediation:
    return Remediation(
        action="Replace the weak cryptographic primitive",
        steps=[
            f"Identify what the algorithm at {_where(finding)} actually protects.",
            "Hashes: SHA-256 for integrity, bcrypt or argon2 for passwords.",
            "Never MD5 or SHA-1 for anything security-relevant.",
            "Ciphers: an AEAD mode such as AES-GCM, with a unique nonce per message.",
            "Randomness: the `secrets` module, never `random`.",
            "Rotate existing values — a new algorithm does not protect old data.",
        ],
        effort="medium",
        verify="Re-run the analysis: the weak-crypto finding should disappear.",
        references=[f"{OWASP_TOP10}/A02_2021-Cryptographic_Failures/"],
    )


def _vulnerable_dependency(finding: Remediatable) -> Remediation:
    evidence = finding.evidence_json or {}
    package = _text(evidence, "package")
    version = _text(evidence, "version")
    vulns = _names(evidence, "vuln_ids", limit=3)
    subject = f"{package} {version}".strip() or "the dependency"
    listed = ", ".join(vulns) if vulns else "the advisory"
    return Remediation(
        action=f"Upgrade {subject} to a patched release",
        steps=[
            f"Read the advisories for {subject}: {listed}.",
            "Upgrade to the first unaffected release, not necessarily the newest.",
            "Re-run the dependency audit; no advisory should still match the pin.",
            "Run the test suite — a major bump may change behaviour, a patch should not.",
            "Commit the updated lockfile, not just the manifest.",
        ],
        effort="low",
        verify="Re-run the analysis: the vulnerable-dependency finding should disappear.",
        # aislop-ignore-next-line ai-slop/hardcoded-url -- stable public advisory site
        references=["https://osv.dev/"],
    )


def _outdated_dependency(finding: Remediatable) -> Remediation:
    evidence = finding.evidence_json or {}
    installed = _text(evidence, "installed")
    latest = _text(evidence, "latest")
    span = f"{installed} to {latest}" if installed and latest else "the latest release"
    return Remediation(
        action=f"Update the dependency pinned at {_where(finding)}",
        steps=[
            f"Move the pin from {span}.",
            "Read the changelog for behaviour changes, not just fixes.",
            "Run the test suite; this is the step that catches a silent break.",
        ],
        effort="low",
        verify="Re-run the analysis: the outdated-dependency finding should disappear.",
        references=["https://owasp.org/www-project-dependency-check/"],
    )


def _complexity(finding: Remediatable) -> Remediation:
    evidence = finding.evidence_json or {}
    symbol = _text(evidence, "symbol") or "the flagged function"
    cc = _number(evidence, "cyclomatic_complexity")
    measured = f"a cyclomatic complexity of {cc:g}" if cc is not None else "high complexity"
    return Remediation(
        action=f"Break up {symbol}",
        steps=[
            f"{symbol} at {_where(finding)} has {measured}.",
            "Extract each distinct branch group into a named function.",
            "Use early returns to flatten the guard clauses at the top.",
            "Keep the extraction behaviour-preserving; pin current behaviour first.",
            "Re-measure afterwards: aim below the threshold, not merely lower.",
        ],
        effort="medium",
        verify="Re-run the analysis: the complexity finding should drop or disappear.",
        references=["https://en.wikipedia.org/wiki/Cyclomatic_complexity"],
    )


def _maintainability(finding: Remediatable) -> Remediation:
    return Remediation(
        action="Improve the module's maintainability",
        steps=[
            f"{_where(finding)} scores below the maintainability threshold.",
            "Reduce the longest functions first; complexity drives the index.",
            "Remove dead code and collapse duplicated blocks while you are there.",
            "Re-measure once the structure changes, not just the formatting.",
        ],
        effort="medium",
        verify="Re-run the analysis: the maintainability finding should disappear.",
        references=["https://radon.readthedocs.io/en/latest/maintainability.html"],
    )


def _duplication(finding: Remediatable) -> Remediation:
    evidence = finding.evidence_json or {}
    original = _text(evidence, "original")
    duplicate = _text(evidence, "duplicate")
    pair = f"{original} and {duplicate}" if original and duplicate else "the copies"
    return Remediation(
        action="Extract the duplicated logic",
        steps=[
            f"The same block appears in {pair}.",
            "Extract it into one shared function, passing differences as arguments.",
            "Replace both call sites, then delete the second copy.",
            "Fix one bug and confirm both places are fixed — that is the payoff.",
        ],
        effort="low",
        verify="Re-run the analysis: the duplication finding should disappear.",
        references=["https://en.wikipedia.org/wiki/Dry_(software)"],
    )


def _code_smell(finding: Remediatable) -> Remediation:
    rule = _text(finding.evidence_json or {}, "rule")
    steps = [
        f"Review {_where(finding)}: a real defect, or an idiom here?",
        "If it is a false positive, dismiss it and say why; that is recorded.",
    ]
    if rule:
        steps.append(f"Otherwise fix the construct the rule names ({rule}).")
    steps.append("Re-run the analysis to confirm it is cleared.")
    return Remediation(
        action="Address the flagged code smell",
        steps=steps,
        effort="low",
        verify="Re-run the analysis: the finding should disappear or be dismissed.",
        references=[],
    )


def _insight(finding: Remediatable) -> Remediation:
    return Remediation(
        action="Review the reported issue",
        steps=[
            f"Read {_where(finding)} and confirm the claim against the code.",
            "Fix it, or dismiss it with a reason.",
            "An unreviewed claim is not a finding; it is a question.",
        ],
        effort="low",
        verify="Re-run the analysis: the finding should be fixed or dismissed.",
        references=[],
    )


def _generic(finding: Remediatable) -> Remediation:
    return Remediation(
        action=f"Resolve: {finding.title}",
        steps=[
            f"Review the finding at {_where(finding)}.",
            "Read the cited lines and decide whether it is a real problem.",
            "Fix it, or dismiss it with a reason so it stops consuming review time.",
        ],
        effort="medium",
        verify="Re-run the analysis and confirm the finding is resolved or dismissed.",
        references=[],
    )
