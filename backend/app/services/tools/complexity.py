"""Complexity/maintainability runner (radon)."""

from radon.complexity import cc_visit
from radon.metrics import mi_visit

from app.models import Severity
from app.services.tools.context import ToolContext
from app.services.tools.findings import FindingDraft

CC_MEDIUM = 10
CC_HIGH = 20
MI_LOW = 65


def run_complexity(ctx: ToolContext) -> list[FindingDraft]:
    drafts: list[FindingDraft] = []
    for entry in ctx.code_files:
        if entry.ext != ".py":
            continue
        path = ctx.repo_root / entry.path
        try:
            source = path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        try:
            blocks = cc_visit(source)
            mi = mi_visit(source, False)
        except Exception:  # noqa: BLE001 — radon can choke on odd syntax
            continue
        for block in blocks:
            complexity = block.complexity
            if complexity >= CC_HIGH:
                severity = Severity.HIGH
            elif complexity >= CC_MEDIUM:
                severity = Severity.MEDIUM
            else:
                continue
            drafts.append(
                FindingDraft(
                    agent="static-analysis",
                    category="complexity",
                    severity=severity,
                    title=f"High cyclomatic complexity: {block.name} (CC {complexity})",
                    description=(
                        f"{block.name} in {entry.path} has cyclomatic complexity {complexity} "
                        f"(threshold {CC_MEDIUM}). Refactor into smaller functions."
                    ),
                    file_path=entry.path,
                    line_start=getattr(block, "lineno", None),
                    evidence_json={"cyclomatic_complexity": complexity, "symbol": block.name},
                    verifier="tool:radon",
                )
            )
        if mi < MI_LOW:
            drafts.append(
                FindingDraft(
                    agent="static-analysis",
                    category="maintainability",
                    severity=Severity.LOW,
                    title=f"Low maintainability index in {entry.path} (MI {mi:.0f})",
                    description=(
                        f"Maintainability index of {entry.path} is {mi:.1f}, below {MI_LOW}. "
                        "High complexity or poor structure reduces maintainability."
                    ),
                    file_path=entry.path,
                    line_start=1,
                    evidence_json={"maintainability_index": round(mi, 1)},
                    verifier="tool:radon",
                )
            )
    return drafts
