"""Security Agent — per-function review with graph context (D6) and CVE reachability.

Deterministic inputs: static vulnerability findings, the source of the functions
they point at, caller/callee context from the symbol graph, and vulnerable
dependencies enriched with whether first-party code imports them.
"""

from typing import Any

from sqlalchemy import select

from app.agents.base import AgentContext, BaseAgent
from app.analysis_engine import graph
from app.config import get_settings
from app.models import Edge, EdgeKind, Finding, Symbol, SymbolKind

MAX_RISK_FUNCTIONS = 8


class SecurityAgent(BaseAgent):
    name = "security"

    def build_instruction(self) -> str:
        return (
            "Review each risk function as an isolated unit with its callers. Produce at "
            "most 5 `findings`, each describing one concrete exploitable issue: what the "
            "flaw is, how untrusted input reaches it (cite the caller when known), and the "
            "cited file_path/line_start. Do not speculate beyond the provided code. "
            "Report vulnerable dependencies only when first-party code imports them."
        )

    def build_context(self, ctx: AgentContext) -> dict[str, Any]:
        settings = get_settings()
        risk_findings = (
            ctx.session.query(Finding)
            .filter(
                Finding.analysis_id == ctx.analysis_id,
                Finding.category.in_(("vulnerability", "secret")),
            )
            .order_by(Finding.severity.desc(), Finding.id)
            .limit(settings.agent_max_static_findings)
            .all()
        )

        risk_functions = []
        for finding in risk_findings[:MAX_RISK_FUNCTIONS]:
            if not finding.file_path:
                continue
            enclosing = _enclosing_symbol(ctx, finding.file_path, finding.line_start)
            callers = graph.callers(ctx.session, ctx.analysis_id, enclosing) if enclosing else []
            risk_functions.append(
                {
                    "name": enclosing or finding.title,
                    "file_path": finding.file_path,
                    "line_start": finding.line_start or 1,
                    "rule": (finding.evidence_json or {}).get("rule", finding.category),
                    "snippet": _snippet(
                        ctx, finding.file_path, finding.line_start, finding.line_end
                    ),
                    "callers": [c["symbol"]["name"] for c in callers][:5],
                }
            )

        return {
            "risk_functions": risk_functions,
            "reachable_dependencies": _reachable_dependencies(ctx),
            "graph_summary": ctx.graph_summary(),
        }


def _reachable_dependencies(ctx: AgentContext) -> list[dict[str, Any]]:
    """Vulnerable deps whose package name appears in first-party imports."""
    dep_findings = (
        ctx.session.query(Finding)
        .filter(
            Finding.analysis_id == ctx.analysis_id,
            Finding.category == "vulnerable-dependency",
        )
        .limit(20)
        .all()
    )
    if not dep_findings:
        return []
    out: list[dict[str, Any]] = []
    for finding in dep_findings:
        import_evidence = _dependency_import_evidence(ctx, finding)
        if not import_evidence:
            continue
        evidence = finding.evidence_json or {}
        out.append(
            {
                "package": evidence.get("package", finding.title),
                "version": evidence.get("version"),
                "vuln_ids": evidence.get("vuln_ids", []),
                "imported_by": import_evidence,
                "file_path": finding.file_path,
                "line_start": finding.line_start,
            }
        )
    return out


def _dependency_import_evidence(ctx: AgentContext, finding: Finding) -> str | None:
    evidence = finding.evidence_json or {}
    package = str(evidence.get("package", "")).lower()
    if not package:
        return None
    needle = package.replace("-", "_")
    edges = ctx.session.scalars(
        select(Edge).where(
            Edge.analysis_id == ctx.analysis_id,
            Edge.kind == EdgeKind.IMPORTS,
            Edge.dst_name.ilike(f"{needle}%"),
        )
    ).all()
    return edges[0].dst_name if edges else None


def _enclosing_symbol(ctx: AgentContext, file_path: str, line: int | None) -> str | None:
    if line is None:
        return None
    candidates = ctx.session.scalars(
        select(Symbol)
        .where(
            Symbol.analysis_id == ctx.analysis_id,
            Symbol.file_path == file_path,
            Symbol.kind.in_((SymbolKind.FUNCTION, SymbolKind.METHOD)),
            Symbol.line_start <= line,
            Symbol.line_end >= line,
        )
        .order_by(Symbol.line_end - Symbol.line_start)
    ).all()
    return candidates[0].name if candidates else None


def _snippet(ctx: AgentContext, file_path: str, start: int | None, end: int | None) -> str:
    try:
        lines = (ctx.repo_root / file_path).read_text(errors="replace").splitlines()
    except OSError:
        return ""
    if start is None:
        return "\n".join(lines[:40])[:1500]
    lo = max(0, start - 3)
    hi = min(len(lines), (end or start) + 2)
    return "\n".join(lines[lo:hi])[:1500]
