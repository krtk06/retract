"""tree-sitter based code indexer.

Produces the structural truth for all later analysis (Decision D4): symbols
(modules/classes/functions/methods) and edges (imports/calls). Edges store the
destination name as written; import edges get best-effort resolution to module
symbols (needed for cycle detection in Phase 2).
"""

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript
from sqlalchemy.orm import Session
from tree_sitter import Language, Node, Parser

from app.models import Edge, EdgeKind, Symbol, SymbolKind

logger = logging.getLogger(__name__)

PARSERS: dict[str, Parser] = {
    "py": Parser(Language(tree_sitter_python.language())),
    "js": Parser(Language(tree_sitter_javascript.language())),
    "mjs": Parser(Language(tree_sitter_javascript.language())),
    "ts": Parser(Language(tree_sitter_typescript.language_typescript())),
    "tsx": Parser(Language(tree_sitter_typescript.language_tsx())),
}

EXT_TO_LANG = {
    ".py": "py",
    ".js": "js",
    ".jsx": "js",
    ".mjs": "js",
    ".ts": "ts",
    ".tsx": "ts",
}

MAX_INDEX_FILES = 3000


@dataclass
class SymbolRec:
    file_path: str
    name: str
    kind: SymbolKind
    line_start: int
    line_end: int


@dataclass
class EdgeRec:
    src: str  # qualified source symbol key: "file_path:name:kind:line"
    dst_name: str
    kind: EdgeKind


@dataclass
class IndexResult:
    symbols: list[SymbolRec] = field(default_factory=list)
    edges: list[EdgeRec] = field(default_factory=list)


def _module_name(file_path: Path) -> str:
    parts = list(file_path.with_suffix("").parts)
    return ".".join(p for p in parts if p)


def _text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _walk_python(root: Node, source: bytes, rel: str, out: IndexResult) -> None:
    module = _module_name(Path(rel))
    out.symbols.append(
        SymbolRec(rel, module, SymbolKind.MODULE, root.start_point[0] + 1, root.end_point[0] + 1)
    )

    def visit(node: Node, class_stack: list[str]) -> None:
        if node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                name = _text(name_node, source)
                out.symbols.append(
                    SymbolRec(
                        rel,
                        name,
                        SymbolKind.CLASS,
                        node.start_point[0] + 1,
                        node.end_point[0] + 1,
                    )
                )
                body = node.child_by_field_name("body")
                if body is not None:
                    visit(body, [*class_stack, name])
                return
        elif node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                name = _text(name_node, source)
                kind = SymbolKind.METHOD if class_stack else SymbolKind.FUNCTION
                out.symbols.append(
                    SymbolRec(
                        rel,
                        name,
                        kind,
                        node.start_point[0] + 1,
                        node.end_point[0] + 1,
                    )
                )
        elif node.type == "import_statement":
            for child in node.children:
                if child.type == "dotted_name" or child.type == "aliased_import":
                    out.edges.append(
                        EdgeRec(
                            f"{rel}::module",
                            _text(child, source).split(" as ")[0],
                            EdgeKind.IMPORTS,
                        )
                    )
        elif node.type == "import_from_statement":
            module_node = node.child_by_field_name("module_name")
            if module_node is not None:
                prefix = _text(module_node, source)
                names = [
                    _text(c, source)
                    for c in node.children
                    if c.type == "dotted_name" or c.type == "aliased_import"
                ]
                # "from x import a, b" -> edges to x, x.a, x.b
                out.edges.append(EdgeRec(f"{rel}::module", prefix, EdgeKind.IMPORTS))
                for imported in names:
                    out.edges.append(
                        EdgeRec(
                            f"{rel}::module",
                            f"{prefix}.{imported.split(' as ')[0]}",
                            EdgeKind.IMPORTS,
                        )
                    )

        for child in node.children:
            visit(child, class_stack)

    visit(root, [])

    # Calls: any call node -> record callee name as written.
    module_key = f"{rel}::module"
    for call in _iter_type(root, "call"):
        func = call.child_by_field_name("function")
        if func is None:
            continue
        if func.type in ("identifier", "attribute"):
            callee = _text(func, source)
            if func.type == "attribute":
                callee = _text(func.child_by_field_name("attribute") or func, source)
            out.edges.append(EdgeRec(module_key, callee, EdgeKind.CALLS))


def _iter_type(node: Node, node_type: str) -> Iterator[Node]:
    if node.type == node_type:
        yield node
    for child in node.children:
        yield from _iter_type(child, node_type)


def _walk_javascript(root: Node, source: bytes, rel: str, out: IndexResult) -> None:
    module = _module_name(Path(rel))
    out.symbols.append(
        SymbolRec(rel, module, SymbolKind.MODULE, root.start_point[0] + 1, root.end_point[0] + 1)
    )
    module_key = f"{rel}::module"

    # Imports
    for node in _iter_types(root, {"import_statement"}):
        src_node = node.child_by_field_name("source")
        if src_node is not None:
            out.edges.append(
                EdgeRec(module_key, _text(src_node, source).strip("'\""), EdgeKind.IMPORTS)
            )

    # Functions / classes / arrow-assigned consts
    for node in _iter_types(root, {"function_declaration", "class_declaration"}):
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            kind = SymbolKind.CLASS if node.type == "class_declaration" else SymbolKind.FUNCTION
            out.symbols.append(
                SymbolRec(
                    rel,
                    _text(name_node, source),
                    kind,
                    node.start_point[0] + 1,
                    node.end_point[0] + 1,
                )
            )

    # Calls
    for call in _iter_type(root, "call_expression"):
        func = call.child_by_field_name("function")
        if func is None:
            continue
        if func.type == "identifier":
            out.edges.append(EdgeRec(module_key, _text(func, source), EdgeKind.CALLS))
        elif func.type == "member_expression":
            attr = func.child_by_field_name("property")
            if attr is not None:
                out.edges.append(EdgeRec(module_key, _text(attr, source), EdgeKind.CALLS))


def _iter_types(node: Node, types: set[str]) -> Iterator[Node]:
    if node.type in types:
        yield node
    for child in node.children:
        yield from _iter_types(child, types)


def index_file(root: Path, rel_path: str) -> IndexResult | None:
    ext = Path(rel_path).suffix.lower()
    lang = EXT_TO_LANG.get(ext)
    if lang is None:
        return None
    parser = PARSERS.get(lang if lang != "ts" else ("tsx" if ext == ".tsx" else "ts"))
    if parser is None:
        return None
    try:
        source = (root / rel_path).read_bytes()
    except OSError:
        return None
    if len(source) > 1_000_000:
        return None
    try:
        tree = parser.parse(source)
    except Exception:  # noqa: BLE001 — skip unparseable files
        return None
    out = IndexResult()
    if lang == "py":
        _walk_python(tree.root_node, source, rel_path, out)
    else:
        _walk_javascript(tree.root_node, source, rel_path, out)
    return out


def resolve_import(dst: str, src_module: str, module_names: set[str]) -> str | None:
    """Best-effort resolution of an import target to a module in this repo.

    Handles: absolute imports matching a module path or its parent package,
    and same-directory relative imports (a.b importing c -> a.c).
    """
    candidates = []
    if dst in module_names:
        return dst
    # from a.b import c  → maybe a.b.c is a module, or c is a symbol
    # import a.b.c       → a.b.c or a.b
    parts = dst.split(".")
    for i in range(len(parts), 0, -1):
        candidates.append(".".join(parts[:i]))
    # relative: sibling package
    if "." in src_module:
        pkg = src_module.rsplit(".", 1)[0]
        candidates.append(f"{pkg}.{dst}")
        for i in range(len(parts), 0, -1):
            candidates.append(f"{pkg}.{'.'.join(parts[:i])}")
    for candidate in candidates:
        if candidate in module_names:
            return candidate
    return None


def persist_index(session: Session, analysis_id: int, repo_root: Path, files: list[str]) -> int:
    """Index the repo files and persist symbols + edges. Returns symbol count."""
    symbol_rows: dict[tuple, Symbol] = {}
    edge_rows: dict[tuple, Edge] = {}
    keyed_files = [f for f in files if Path(f).suffix.lower() in EXT_TO_LANG]
    keyed_files = keyed_files[:MAX_INDEX_FILES]

    result = IndexResult()
    for rel in keyed_files:
        file_result = index_file(repo_root, rel)
        if file_result is not None:
            result.symbols.extend(file_result.symbols)
            result.edges.extend(file_result.edges)

    # Create module-name lookup and insert symbols first.
    module_names = {s.name for s in result.symbols if s.kind == SymbolKind.MODULE}

    def symbol_key(rec: SymbolRec) -> tuple:
        return (rec.file_path, rec.name, rec.kind.value, rec.line_start)

    for rec in result.symbols:
        key = symbol_key(rec)
        if key not in symbol_rows:
            symbol_rows[key] = Symbol(
                analysis_id=analysis_id,
                file_path=rec.file_path,
                name=rec.name,
                kind=rec.kind,
                line_start=rec.line_start,
                line_end=rec.line_end,
            )
    session.add_all(symbol_rows.values())
    session.flush()

    id_by_key = {key: symbol_rows[key].id for key in symbol_rows}
    module_id_by_name: dict[str, int] = {}
    for rec in result.symbols:
        if rec.kind == SymbolKind.MODULE:
            symbol_id = id_by_key[symbol_key(rec)]
            module_id_by_name.setdefault(rec.name, symbol_id)

    for edge in result.edges:
        src_id = id_by_key.get(
            (
                edge.src.split("::")[0],
                edge.src.split("::")[1] or "module",
                SymbolKind.MODULE.value,
                1,
            )
        )
        # module symbols have line_start recorded properly; fall back to lookup
        if src_id is None:
            continue
        dst_symbol_id = None
        if edge.kind == EdgeKind.IMPORTS:
            resolved = resolve_import(edge.dst_name, edge.src.split("::")[0], module_names)
            if resolved is not None:
                dst_symbol_id = module_id_by_name.get(resolved)
        key = (src_id, edge.dst_name, edge.kind.value)
        if key in edge_rows:
            continue
        edge_rows[key] = Edge(
            analysis_id=analysis_id,
            src_symbol_id=src_id,
            dst_name=edge.dst_name[:500],
            dst_symbol_id=dst_symbol_id,
            kind=edge.kind,
        )
    session.add_all(edge_rows.values())
    session.commit()
    return len(symbol_rows)
