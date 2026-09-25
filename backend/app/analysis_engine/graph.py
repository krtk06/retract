"""Repository knowledge graph queries (Decision D3).

Graph = symbols (nodes) + edges (imports/calls). Structural truth always comes
from the tree-sitter index, never from an LLM (Decision D4).
"""

from collections import deque
from dataclasses import dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Edge, EdgeKind, Symbol, SymbolKind

MAX_NEIGHBORHOOD_NODES = 120
MAX_PATH_NODES = 200


@dataclass
class SymbolRef:
    id: int
    name: str
    kind: str
    file_path: str
    line_start: int


@dataclass
class GraphNode:
    id: int
    name: str
    kind: str
    file_path: str
    line_start: int
    line_end: int


@dataclass
class GraphLink:
    source: str
    target: str
    kind: str


@dataclass
class Neighborhood:
    root: GraphNode | None
    nodes: list[GraphNode] = field(default_factory=list)
    links: list[GraphLink] = field(default_factory=list)


def _ref(symbol: Symbol) -> SymbolRef:
    return SymbolRef(
        id=symbol.id,
        name=symbol.name,
        kind=symbol.kind.value,
        file_path=symbol.file_path,
        line_start=symbol.line_start,
    )


def search_symbols(
    db: Session,
    analysis_id: int,
    query: str | None = None,
    kind: str | None = None,
    limit: int = 100,
) -> list[SymbolRef]:
    stmt = select(Symbol).where(Symbol.analysis_id == analysis_id)
    if kind:
        stmt = stmt.where(Symbol.kind == kind)
    if query:
        stmt = stmt.where(Symbol.name.ilike(f"%{query}%"))
    stmt = stmt.order_by(Symbol.file_path, Symbol.line_start).limit(limit)
    return [_ref(s) for s in db.scalars(stmt).all()]


def _find_symbols(db: Session, analysis_id: int, name: str) -> list[Symbol]:
    return list(
        db.scalars(
            select(Symbol)
            .where(Symbol.analysis_id == analysis_id, Symbol.name == name)
            .order_by(Symbol.kind, Symbol.line_start)
        ).all()
    )


def callers(db: Session, analysis_id: int, symbol_name: str) -> list[dict]:
    """Symbols that call or import ``symbol_name`` (best-effort by name)."""
    rows = db.execute(
        select(Edge, Symbol)
        .join(Symbol, Symbol.id == Edge.src_symbol_id)
        .where(
            Edge.analysis_id == analysis_id,
            Edge.dst_name == symbol_name,
        )
        .order_by(Edge.kind, Symbol.file_path)
    ).all()
    seen: set[tuple[int, str]] = set()
    out: list[dict] = []
    for edge, src in rows:
        key = (src.id, edge.kind.value)
        if key in seen:
            continue
        seen.add(key)
        out.append({"symbol": _ref(src).__dict__, "edge_kind": edge.kind.value})
    return out


def callees(db: Session, analysis_id: int, symbol_name: str) -> list[dict]:
    """Names this symbol (or its module) calls."""
    symbols = _find_symbols(db, analysis_id, symbol_name)
    if not symbols:
        # allow module names too
        symbols = list(
            db.scalars(
                select(Symbol).where(
                    Symbol.analysis_id == analysis_id,
                    Symbol.kind == SymbolKind.MODULE,
                    Symbol.name.like(f"%{symbol_name}%"),
                )
            ).all()
        )
    ids = [s.id for s in symbols]
    if not ids:
        return []
    rows = db.scalars(
        select(Edge)
        .where(Edge.analysis_id == analysis_id, Edge.src_symbol_id.in_(ids))
        .order_by(Edge.kind, Edge.dst_name)
    ).all()
    return [
        {
            "name": edge.dst_name,
            "edge_kind": edge.kind.value,
            "resolved": edge.dst_symbol_id is not None,
        }
        for edge in rows
    ]


def imports(db: Session, analysis_id: int, module_name: str) -> list[dict]:
    symbols = [
        s for s in _find_symbols(db, analysis_id, module_name) if s.kind == SymbolKind.MODULE
    ]
    if not symbols:
        symbols = list(
            db.scalars(
                select(Symbol).where(
                    Symbol.analysis_id == analysis_id,
                    Symbol.kind == SymbolKind.MODULE,
                    Symbol.name.ilike(f"%{module_name}%"),
                )
            ).all()
        )
    ids = [s.id for s in symbols]
    if not ids:
        return []
    rows = db.scalars(
        select(Edge).where(
            Edge.analysis_id == analysis_id,
            Edge.src_symbol_id.in_(ids),
            Edge.kind == EdgeKind.IMPORTS,
        )
    ).all()
    pairs = {(edge.dst_name, edge.dst_symbol_id is not None) for edge in rows}
    return [{"module": name, "resolved": resolved} for name, resolved in sorted(pairs)]


def dependents(db: Session, analysis_id: int, module_name: str) -> list[dict]:
    """Modules that import ``module_name`` (resolved targets preferred)."""
    matching = db.scalars(
        select(Symbol).where(
            Symbol.analysis_id == analysis_id,
            Symbol.kind == SymbolKind.MODULE,
            or_(
                Symbol.name == module_name,
                Symbol.name.ilike(f"{module_name}.%"),
                Symbol.name.ilike(f"%{module_name}"),
            ),
        )
    ).all()
    ids = [s.id for s in matching]
    conditions = [Edge.dst_name == module_name, Edge.dst_name.ilike(f"{module_name}.%")]
    if ids:
        conditions.append(Edge.dst_symbol_id.in_(ids))
    rows = db.execute(
        select(Edge, Symbol)
        .join(Symbol, Symbol.id == Edge.src_symbol_id)
        .where(
            Edge.analysis_id == analysis_id,
            Edge.kind == EdgeKind.IMPORTS,
            or_(*conditions),
        )
    ).all()
    seen: set[int] = set()
    out: list[dict] = []
    for _edge, src in rows:
        if src.id in seen:
            continue
        seen.add(src.id)
        out.append(_ref(src).__dict__)
    return out


def _adjacency(
    db: Session, analysis_id: int
) -> tuple[dict[int, list[tuple[int, str]]], dict[int, Symbol]]:
    edges = db.scalars(select(Edge).where(Edge.analysis_id == analysis_id)).all()
    symbols = {
        s.id: s for s in db.scalars(select(Symbol).where(Symbol.analysis_id == analysis_id)).all()
    }
    adj: dict[int, list[tuple[int, str]]] = {}
    for edge in edges:
        if edge.dst_symbol_id is None or edge.src_symbol_id not in symbols:
            continue
        if edge.dst_symbol_id not in symbols:
            continue
        adj.setdefault(edge.src_symbol_id, []).append((edge.dst_symbol_id, edge.kind.value))
    return adj, symbols


def neighborhood(db: Session, analysis_id: int, symbol_name: str, depth: int = 2) -> Neighborhood:
    """BFS neighborhood around a symbol (both directions), for the Explore graph."""
    adj, symbols = _adjacency(db, analysis_id)
    reverse: dict[int, list[tuple[int, str]]] = {}
    for src, dests in adj.items():
        for dst, kind in dests:
            reverse.setdefault(dst, []).append((src, kind))

    roots = db.scalars(
        select(Symbol).where(Symbol.analysis_id == analysis_id, Symbol.name == symbol_name)
    ).all()
    if not roots:
        roots = db.scalars(
            select(Symbol)
            .where(
                Symbol.analysis_id == analysis_id,
                Symbol.name.ilike(f"%{symbol_name}%"),
            )
            .limit(1)
        ).all()
    if not roots:
        return Neighborhood(root=None)
    root = roots[0]

    visited = {root.id}
    queue: deque[tuple[int, int]] = deque([(root.id, 0)])
    links: dict[tuple[int, int, str], GraphLink] = {}
    while queue and len(visited) < MAX_NEIGHBORHOOD_NODES:
        node_id, dist = queue.popleft()
        if dist >= depth:
            continue
        for dst, kind in adj.get(node_id, []):
            links[(node_id, dst, kind)] = GraphLink(
                source=symbols[node_id].name, target=symbols[dst].name, kind=kind
            )
            if dst not in visited:
                visited.add(dst)
                queue.append((dst, dist + 1))
        for src, kind in reverse.get(node_id, []):
            links[(src, node_id, kind)] = GraphLink(
                source=symbols[src].name, target=symbols[node_id].name, kind=kind
            )
            if src not in visited:
                visited.add(src)
                queue.append((src, dist + 1))

    nodes = [
        GraphNode(
            id=node_id,
            name=symbols[node_id].name,
            kind=symbols[node_id].kind.value,
            file_path=symbols[node_id].file_path,
            line_start=symbols[node_id].line_start,
            line_end=symbols[node_id].line_end,
        )
        for node_id in visited
    ]
    root_node = next((n for n in nodes if n.id == root.id), None)
    return Neighborhood(root=root_node, nodes=nodes, links=list(links.values()))


def path(db: Session, analysis_id: int, from_name: str, to_name: str) -> list[SymbolRef]:
    """Shortest edge path between two symbols (BFS)."""
    adj, symbols = _adjacency(db, analysis_id)
    starts = db.scalars(
        select(Symbol).where(Symbol.analysis_id == analysis_id, Symbol.name == from_name)
    ).all()
    goals = {
        s.id
        for s in db.scalars(
            select(Symbol).where(Symbol.analysis_id == analysis_id, Symbol.name == to_name)
        ).all()
    }
    if not starts or not goals:
        return []
    for start in starts:
        prev: dict[int, int] = {start.id: start.id}
        queue: deque[int] = deque([start.id])
        while queue and len(prev) < MAX_PATH_NODES:
            node = queue.popleft()
            if node in goals:
                chain = [node]
                while prev[chain[-1]] != chain[-1]:
                    chain.append(prev[chain[-1]])
                chain.reverse()
                return [_ref(symbols[i]) for i in chain if i in symbols]
            for dst, _kind in adj.get(node, []):
                if dst not in prev:
                    prev[dst] = node
                    queue.append(dst)
    return []


def summary(db: Session, analysis_id: int) -> dict:
    from sqlalchemy import func

    symbol_counts: dict[str, int] = {}
    for kind, count in db.execute(
        select(Symbol.kind, func.count(Symbol.id))
        .where(Symbol.analysis_id == analysis_id)
        .group_by(Symbol.kind)
    ).all():
        symbol_counts[kind.value] = count
    edge_counts: dict[str, int] = {}
    for kind, count in db.execute(
        select(Edge.kind, func.count(Edge.id))
        .where(Edge.analysis_id == analysis_id)
        .group_by(Edge.kind)
    ).all():
        edge_counts[kind.value] = count
    top_modules = db.execute(
        select(Symbol.name, func.count(Edge.id).label("imports"))
        .join(Edge, Edge.src_symbol_id == Symbol.id)
        .where(
            Symbol.analysis_id == analysis_id,
            Symbol.kind == SymbolKind.MODULE,
            Edge.kind == EdgeKind.IMPORTS,
        )
        .group_by(Symbol.name)
        .order_by(func.count(Edge.id).desc())
        .limit(10)
    ).all()
    return {
        "symbols": symbol_counts,
        "edges": edge_counts,
        "top_importing_modules": [
            {"module": name, "imports": count} for name, count in top_modules
        ],
    }
