"""Render a benchmark result as Markdown."""

from app.benchmark.match import BenchmarkResult


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.0f}%"


def _num(value: float | None, digits: int = 2) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def render_report(result: BenchmarkResult, command: str = "") -> str:
    lines: list[str] = []
    lines.append(f"# Benchmark report — `{result.repo}`")
    lines.append("")
    lines.append(f"Analysis: **#{result.analysis_id}**")
    if command:
        lines.append("")
        lines.append(f"Reproduce: `{command}`")
    lines.append("")

    lines.append("## Headline")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    lines.append(
        f"| Recall (grounded expectations found) | **{_pct(result.recall)}** "
        f"({result.recalled}/{result.expected}) |"
    )
    lines.append(
        f"| Precision (grounded) | **{_pct(result.precision_grounded)}** "
        f"({result.matched_findings}/{result.enumerated_open_findings}) |"
    )
    lines.append(
        f"| Precision (deduplicated) | **{_pct(result.precision_deduplicated)}** "
        f"({result.matched_findings} matched, {len(result.unenumerated_findings)} unenumerated, "
        f"{len(result.duplicate_findings)} duplicate) |"
    )
    lines.append(f"| F1 (grounded) | **{_num(result.f1_grounded)}** |")
    lines.append(f"| Precision (strict, all open findings) | {_pct(result.precision_strict)} |")
    lines.append(
        f"| Verification coverage | {_pct(result.verification_coverage)} "
        f"({result.verified_findings} verified / {result.hypothesis_findings} hypothesis) |"
    )
    lines.append(
        f"| Findings | {result.open_findings} open, {result.dismissed_findings} dismissed |"
    )
    lines.append("")

    if result.untriaged_planted:
        lines.append("## Planted false positives not triaged")
        lines.append("")
        lines.append("These were expected to be dismissed and were not:")
        lines.append("")
        for outcome in result.untriaged_planted:
            where = outcome.expectation.file or "(any file)"
            note = outcome.expectation.note or "no note"
            lines.append(f"- **{outcome.expectation.category}** in `{where}` — {note}")
        lines.append("")

    lines.append("## Per category")
    lines.append("")
    lines.append("| Category | Expected | Recalled | Recall | Open | Matched | Precision |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for name, score in sorted(result.categories.items()):
        if score.unreviewed_findings and not score.expected:
            lines.append(f"| {name} | 0 | 0 | — | 0 | 0 | {score.unreviewed_findings} unreviewed |")
            continue
        lines.append(
            f"| {name} | {score.expected} | {score.recalled} | {_pct(score.recall)} | "
            f"{score.open_findings} | {score.matched_findings} | {_pct(score.precision_grounded)} |"
        )
    lines.append("")

    missed = [
        o
        for o in result.outcomes
        if o.match.value == "unmatched" and not o.expectation.expect_dismissed
    ]
    if missed:
        lines.append("## Missed expectations")
        lines.append("")
        for outcome in missed:
            where = outcome.expectation.file or "(any file)"
            line = f":{outcome.expectation.line}" if outcome.expectation.line else ""
            note = outcome.expectation.note or "no note"
            lines.append(f"- **{outcome.expectation.category}** `{where}{line}` — {note}")
        lines.append("")

    mislocated = [o for o in result.outcomes if o.match.value in ("wrong-file", "wrong-line")]
    if mislocated:
        lines.append("## Reported, but not where expected")
        lines.append("")
        for outcome in mislocated:
            where = outcome.expectation.file or "(any file)"
            line = f":{outcome.expectation.line}" if outcome.expectation.line else ""
            lines.append(
                f"- **{outcome.expectation.category}** expected `{where}{line}`, "
                f"matched `{outcome.match.value}` (finding #{outcome.finding_id})"
            )
        lines.append("")

    if result.duplicate_findings:
        lines.append("## Duplicate reports")
        lines.append("")
        lines.append(
            f"{len(result.duplicate_findings)} open finding(s) repeat a condition another "
            "finding already covers (same category and file). These are not new problems, "
            "but they are noise a reviewer has to read past:"
        )
        lines.append("")
        for finding_id in result.duplicate_findings:
            lines.append(f"- finding #{finding_id}")
        lines.append("")

    if result.unreviewed_categories:
        lines.append("## Not covered by this ground truth")
        lines.append("")
        lines.append(
            "These categories produced findings but are not enumerated in the ground-truth "
            "file, so they are excluded from precision. Add them to make the numbers tighter:"
        )
        lines.append("")
        for name in sorted(result.unreviewed_categories):
            count = result.categories[name].unreviewed_findings
            lines.append(f"- `{name}` ({count} finding{'s' if count != 1 else ''})")
        lines.append("")

    lines.append("## How to read this")
    lines.append("")
    lines.append(
        "- **Recall** is the number to improve by adding analyzers: an expectation with no "
        "matching finding is a gap in coverage."
    )
    lines.append(
        "- **Precision (grounded)** is the number to quote. Only categories the ground truth "
        "enumerates are counted, so an incomplete ground-truth file lowers "
        "precision (strict), not precision (grounded)."
    )
    lines.append(
        "- A finding is matched by category, then file, then line within a small tolerance "
        "(tools cite the enclosing symbol or block). A dismissed finding never counts as "
        "detected — including for planted false positives, which are expected to be dismissed."
    )
    lines.append("")
    return "\n".join(lines)
