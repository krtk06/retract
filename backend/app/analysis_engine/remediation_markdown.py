"""Render a remediation plan as a Markdown document."""

from collections.abc import Iterable

from app.analysis_engine.remediation_types import (
    MAX_WORK_ITEMS,
    RemediationPlan,
    _where,
)

# Markdown rendering.


def _bullets(lines: list[str], items: Iterable[str]) -> None:
    lines.extend(f"- {item}" for item in items)


def render_markdown(plan: RemediationPlan, repo_label: str, commit_sha: str | None) -> str:
    """Render the plan as a Markdown document.

    Shaped for pasting into an issue or a PR description: ranked, each item
    self-contained, and explicit about which numbers are exact.
    """
    lines: list[str] = [f"# Fix plan — `{repo_label}`", ""]
    if commit_sha:
        lines.extend([f"Commit: `{commit_sha[:8]}`", ""])

    lines.extend(["## Headline", ""])
    if plan.current_overall is None or plan.projected_overall is None:
        lines.extend(["No open findings — there is nothing to fix.", ""])
        return "\n".join(lines)

    lines.extend(
        [
            "| Metric | Value |",
            "| --- | --- |",
            f"| Health score now | **{plan.current_overall}/100** |",
            f"| Health score with every item below fixed | **{plan.projected_overall}/100** |",
            f"| Points available | **{plan.recoverable_points}** |",
            f"| Work items | {len(plan.work_items)} |",
            f"| Findings covered | {plan.findings_considered} |",
        ]
    )
    if plan.unverified_items:
        lines.append(f"| Items resting on unverified claims | {plan.unverified_items} |")
    lines.extend(
        [
            "",
            "The headline is exact: it is this platform's own scoring curve, run over a",
            "repository with none of these findings. Each item's point value is the gain",
            "**in its own pillar**, measured against today's score. It is not a share of",
            "the headline: the curve is nonlinear, and the overall is capped at the worst",
            "pillar plus 15, so fixing anything but the current worst pillar can move the",
            "headline by very little. Use the ranking, not a sum, to sequence the work.",
            "",
        ]
    )

    lines.extend(["## Work items, highest payoff per unit of effort first", ""])
    for index, item in enumerate(plan.work_items, start=1):
        plural = "s" if item.finding_count != 1 else ""
        lines.extend(
            [
                f"### {index}. {item.action}",
                "",
                f"`+{item.pillar_points} pts` in the {item.pillar} pillar · "
                f"`{item.effort}` effort · {item.finding_count} finding{plural} · "
                f"removes **{item.weighted_penalty_removed:g}** penalty points · "
                f"source `{item.source}`",
                "",
            ]
        )
        _bullets(lines, item.steps)
        lines.append("")
        lines.extend(["<details><summary>Affected findings</summary>", ""])
        for finding in item.findings:
            where = f"`{_where(finding)}`" if finding.file_path else "repository-wide"
            lines.append(f"- [{finding.severity.value}] {finding.title} — {where}")
        lines.extend(["", "</details>", ""])
        lines.extend([f"**Verify:** {item.verify}", ""])
        if item.references:
            _bullets(lines, item.references)
            lines.append("")

    if plan.truncated_findings:
        lines.extend(
            [
                f"_{plan.truncated_findings} further findings were grouped into work items "
                f"beyond the {MAX_WORK_ITEMS}-item display limit._",
                "",
            ]
        )

    return "\n".join(lines)
