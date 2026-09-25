"""Chunk repository symbols into embeddable text (function/class boundaries only)."""

import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Chunk, GraphSnapshot, Symbol, SymbolKind

logger = logging.getLogger(__name__)

MAX_CHUNK_CHARS = 4000
MIN_SYMBOL_LINES = 2
CHUNKABLE_KINDS = {SymbolKind.FUNCTION, SymbolKind.METHOD, SymbolKind.CLASS}


@dataclass
class ChunkDraft:
    symbol_id: int | None
    file_path: str
    symbol_name: str
    kind: str
    line_start: int
    line_end: int
    text: str


def _read_lines(root: Path, file_path: str) -> list[str] | None:
    try:
        return (root / file_path).read_text(errors="replace").splitlines()
    except OSError:
        return None


def build_chunks(db: Session, analysis_id: int, repo_root: Path) -> list[ChunkDraft]:
    """Build one chunk per function/method/class, using tree-sitter symbol boundaries."""
    settings = get_settings()
    symbols = (
        db.query(Symbol)
        .filter(Symbol.analysis_id == analysis_id, Symbol.kind.in_(list(CHUNKABLE_KINDS)))
        .order_by(Symbol.file_path, Symbol.line_start)
        .all()
    )

    drafts: list[ChunkDraft] = []
    cache: dict[str, list[str] | None] = {}
    for symbol in symbols:
        if len(drafts) >= settings.max_chunks_per_analysis:
            logger.warning("chunk cap reached for analysis %s", analysis_id)
            break
        if symbol.line_end - symbol.line_start + 1 < MIN_SYMBOL_LINES:
            continue
        if symbol.file_path not in cache:
            cache[symbol.file_path] = _read_lines(repo_root, symbol.file_path)
        lines = cache[symbol.file_path]
        if lines is None:
            continue
        source = "\n".join(lines[symbol.line_start - 1 : symbol.line_end])
        if len(source.strip()) < 20:
            continue
        header = f"{symbol.kind.value} {symbol.name} in {symbol.file_path}"
        text = f"{header}\n{source}"[:MAX_CHUNK_CHARS]
        drafts.append(
            ChunkDraft(
                symbol_id=symbol.id,
                file_path=symbol.file_path,
                symbol_name=symbol.name,
                kind=symbol.kind.value,
                line_start=symbol.line_start,
                line_end=symbol.line_end,
                text=text,
            )
        )
    return drafts


def persist_chunks(db: Session, analysis_id: int, drafts: list[ChunkDraft]) -> int:
    """Insert chunks (no embeddings yet); returns inserted count."""
    db.query(Chunk).filter(Chunk.analysis_id == analysis_id).delete()
    db.flush()
    for draft in drafts:
        db.add(
            Chunk(
                analysis_id=analysis_id,
                symbol_id=draft.symbol_id,
                file_path=draft.file_path,
                symbol_name=draft.symbol_name,
                kind=draft.kind,
                line_start=draft.line_start,
                line_end=draft.line_end,
                text=draft.text,
            )
        )
    db.commit()
    return len(drafts)


def mark_graph_snapshot(
    db: Session, analysis_id: int, symbol_count: int, edge_count: int, chunk_count: int
) -> None:
    from sqlalchemy import select

    snapshot = db.scalar(select(GraphSnapshot).where(GraphSnapshot.analysis_id == analysis_id))
    if snapshot is None:
        snapshot = GraphSnapshot(analysis_id=analysis_id)
        db.add(snapshot)
    snapshot.symbol_count = symbol_count
    snapshot.edge_count = edge_count
    snapshot.chunk_count = chunk_count
    from app.models import utcnow

    snapshot.built_at = utcnow()
    db.commit()
