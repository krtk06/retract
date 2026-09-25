"""Code Agent — triages static findings and explains code-quality insights.

Deterministic inputs (D1/D4): static tool findings (semgrep/radon/duplication)
plus complexity hotspots. The LLM's job is judgement, not discovery: confirm,
dismiss false positives, and explain in context.
"""

from typing import Any

from app.agents.base import AgentContext, BaseAgent
from app.config import get_settings
from app.models import Finding

STATIC_CATEGORIES = (
    "vulnerability",
    "code-smell",
    "complexity",
    "maintainability",
    "duplication",
)
NON_SECURITY_MARKERS = ("non-security", "cache key", "cache_key", "fingerprint")


class CodeAgent(BaseAgent):
    name = "code"

    def build_instruction(self) -> str:
        return (
            "Review the static-analysis findings and complexity hotspots. For each static "
            "finding decide whether it is a genuine issue or a false positive. Return "
            "`triage` entries as {finding_id, verdict: 'confirmed'|'false-positive', "
            "confidence, reasoning}. You may also add at most 3 `findings` for "
            "non-obvious code-quality insights, each citing file_path and line_start. "
            "A finding is a false positive when the code's documented intent makes the "
            "pattern safe (for example a non-security hash used only as a cache key)."
        )

    def build_context(self, ctx: AgentContext) -> dict[str, Any]:
        settings = get_settings()
        findings = (
            ctx.session.query(Finding)
            .filter(
                Finding.analysis_id == ctx.analysis_id,
                Finding.category.in_(STATIC_CATEGORIES),
            )
            .order_by(Finding.severity.desc(), Finding.id)
            .limit(settings.agent_max_static_findings)
            .all()
        )
        static_findings = []
        for finding in findings:
            evidence_text = _evidence_excerpt(ctx, finding)
            static_findings.append(
                {
                    "id": finding.id,
                    "rule": (finding.evidence_json or {}).get("rule", finding.category),
                    "category": finding.category,
                    "severity": finding.severity.value,
                    "title": finding.title,
                    "description": finding.description[:400],
                    "file_path": finding.file_path,
                    "line_start": finding.line_start,
                    "evidence_text": evidence_text,
                }
            )

        hotspots = [
            {
                "name": item.title,
                "complexity": (item.evidence_json or {}).get("cyclomatic_complexity"),
                "file_path": item.file_path,
                "line_start": item.line_start,
            }
            for item in findings
            if item.category == "complexity"
        ]
        return {
            "static_findings": static_findings,
            "complexity_hotspots": hotspots[:10],
            "loc": _analysis_loc(ctx),
        }


def _analysis_loc(ctx: AgentContext) -> int | None:
    from app.models import Analysis

    analysis = ctx.session.get(Analysis, ctx.analysis_id)
    return analysis.loc if analysis else None


def _evidence_excerpt(ctx: AgentContext, finding: Finding) -> str:
    """Small source excerpt around the finding so the model can judge intent."""
    if not finding.file_path:
        return ""
    try:
        lines = (ctx.repo_root / finding.file_path).read_text(errors="replace").splitlines()
    except OSError:
        return ""
    if finding.line_start is None:
        return ""
    start = max(0, finding.line_start - 4)
    end = min(len(lines), (finding.line_end or finding.line_start) + 3)
    excerpt = "\n".join(lines[start:end])
    markers = [m for m in NON_SECURITY_MARKERS if m in excerpt.lower()]
    if markers:
        excerpt += f"\n[source note: contains '{markers[0]}']"
    return excerpt[:1500]
