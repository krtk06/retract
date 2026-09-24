"""Architecture runner: import cycles and god modules from the symbol graph (D4)."""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Edge, EdgeKind, Severity, Symbol, SymbolKind
from app.services.tools.context import ToolContext
from app.services.tools.findings import FindingDraft

MAX_CYCLES_REPORTED = 10
FAN_IN_FLOOR = 10
FAN_IN_FACTOR = 3


def run_architecture(ctx: ToolContext) -> list[FindingDraft]:
    """Import-cycle and god-module detection over resolved import edges."""
    from app.db import get_session_factory

    session = get_session_factory()()
    try:
        return _run(ctx, session)
    finally:
        session.close()


def _run(ctx: ToolContext, session: Session) -> list[FindingDraft]:
    analysis_id = ctx.analysis_id
    symbols = session.scalars(
        select(Symbol).where(Symbol.analysis_id == analysis_id, Symbol.kind == SymbolKind.MODULE)
    ).all()
    module_by_id = {s.id: s for s in symbols}
    module_names = {s.name for s in symbols}

    # Module-level import graph over resolved edges.
    imports_out: dict[int, set[int]] = defaultdict(set)
    imported_by: dict[int, set[int]] = defaultdict(set)
    rows = session.scalars(
        select(Edge).where(Edge.analysis_id == analysis_id, Edge.kind == EdgeKind.IMPORTS)
    ).all()
    for edge in rows:
        src = module_by_id.get(edge.src_symbol_id)
        dst = module_by_id.get(edge.dst_symbol_id) if edge.dst_symbol_id else None
        if src is None or dst is None or src.id == dst.id:
            continue
        if not _is_internal(dst.name, module_names):
            continue
        imports_out[src.id].add(dst.id)
        imported_by[dst.id].add(src.id)

    drafts: list[FindingDraft] = []
    drafts.extend(_cycles(imports_out, module_by_id))
    drafts.extend(_god_modules(imported_by, module_by_id))
    return drafts


def _is_internal(name: str, module_names: set[str]) -> bool:
    if name in module_names:
        return True
    return any(other.startswith(name + ".") for other in module_names)


def _cycles(
    imports_out: dict[int, set[int]], module_by_id: dict[int, Symbol]
) -> list[FindingDraft]:
    # Iterative DFS cycle detection, limited to keep runtime bounded.
    found: list[list[int]] = []
    seen_cycles: set[frozenset] = set()
    for start in imports_out:
        stack = [(start, [start])]
        while stack and len(found) < MAX_CYCLES_REPORTED * 2:
            node, path = stack.pop()
            for nxt in imports_out.get(node, ()):
                if nxt == start:
                    cycle = path
                    key = frozenset(cycle)
                    if key not in seen_cycles:
                        seen_cycles.add(key)
                        found.append(cycle)
                elif nxt not in path and len(path) < 10:
                    stack.append((nxt, [*path, nxt]))

    drafts: list[FindingDraft] = []
    for cycle in found[:MAX_CYCLES_REPORTED]:
        names = [module_by_id[n].name for n in cycle] + [module_by_id[cycle[0]].name]
        first = module_by_id[cycle[0]]
        drafts.append(
            FindingDraft(
                agent="architecture",
                category="import-cycle",
                severity=Severity.MEDIUM,
                title=f"Import cycle: {' → '.join(names[:6])}",
                description=(
                    "Modules form a circular import chain: "
                    + " → ".join(names)
                    + ". Circular imports make modules harder to test and refactor."
                ),
                file_path=first.file_path,
                line_start=first.line_start,
                evidence_json={"cycle": names},
                verifier="tool:architecture",
            )
        )
    return drafts


def _god_modules(
    imported_by: dict[int, set[int]], module_by_id: dict[int, Symbol]
) -> list[FindingDraft]:
    fan_in = {mid: len(sources) for mid, sources in imported_by.items()}
    if not fan_in:
        return []
    values = sorted(fan_in.values())
    median = values[len(values) // 2]
    threshold = max(FAN_IN_FLOOR, median * FAN_IN_FACTOR)
    drafts: list[FindingDraft] = []
    for mid, count in sorted(fan_in.items(), key=lambda kv: kv[1], reverse=True):
        if count < threshold:
            break
        module = module_by_id[mid]
        drafts.append(
            FindingDraft(
                agent="architecture",
                category="god-module",
                severity=Severity.MEDIUM,
                title=f"Highly imported module: {module.name} ({count} importers)",
                description=(
                    f"{module.name} is imported by {count} other modules (threshold {threshold}). "
                    "Consider splitting responsibilities to reduce coupling."
                ),
                file_path=module.file_path,
                line_start=module.line_start,
                evidence_json={"fan_in": count, "threshold": threshold},
                verifier="tool:architecture",
            )
        )
    return drafts
