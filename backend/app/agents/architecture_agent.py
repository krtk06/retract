"""Architecture Agent — deterministic cycles/coupling plus an LLM narrative (D4).

The graph detects cycles and god-modules deterministically (Phase 2 tool); this
agent explains why they matter and proposes a direction, grounded in that data.
"""

from typing import Any

from sqlalchemy import select

from app.agents.base import AgentContext, BaseAgent
from app.models import Finding, Symbol, SymbolKind

FAN_IN_FLOOR = 10
FAN_IN_FACTOR = 3
MAX_CYCLES = 5
MAX_GOD_MODULES = 5


class ArchitectureAgent(BaseAgent):
    name = "architecture"

    def build_instruction(self) -> str:
        return (
            "Explain the impact of each import cycle and highly-coupled module, and name a "
            "concrete refactoring direction (for example extracting a shared interface or "
            "inverting a dependency). Cite file_path and line_start from the context. "
            "At most 6 findings."
        )

    def build_context(self, ctx: AgentContext) -> dict[str, Any]:
        cycles = [
            {
                "cycle": (finding.evidence_json or {}).get("cycle", []),
                "file_path": finding.file_path,
                "line_start": finding.line_start,
            }
            for finding in ctx.session.query(Finding)
            .filter(
                Finding.analysis_id == ctx.analysis_id,
                Finding.category == "import-cycle",
            )
            .limit(MAX_CYCLES)
            .all()
        ]
        god_modules = [
            {
                "name": finding.title,
                "fan_in": (finding.evidence_json or {}).get("fan_in"),
                "file_path": finding.file_path,
                "line_start": finding.line_start,
            }
            for finding in ctx.session.query(Finding)
            .filter(
                Finding.analysis_id == ctx.analysis_id,
                Finding.category == "god-module",
            )
            .limit(MAX_GOD_MODULES)
            .all()
        ]
        return {
            "import_cycles": cycles,
            "god_modules": god_modules,
            "module_count": _count(ctx, SymbolKind.MODULE),
            "graph_summary": ctx.graph_summary(),
        }


def _count(ctx: AgentContext, kind: SymbolKind) -> int:
    from sqlalchemy import func

    return int(
        ctx.session.scalar(
            select(func.count(Symbol.id)).where(
                Symbol.analysis_id == ctx.analysis_id, Symbol.kind == kind
            )
        )
        or 0
    )
