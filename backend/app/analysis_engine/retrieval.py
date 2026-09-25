"""Retrieval service: semantic search + graph-first selective retrieval (D3)."""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis_engine import graph
from app.analysis_engine.embeddings import cosine_similarity, get_embedding_provider
from app.models import Chunk

MAX_SNIPPET_CHARS = 400
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def semantic_search(db: Session, analysis_id: int, query: str, k: int = 8) -> list[dict]:
    provider = get_embedding_provider()
    query_vector = provider.embed([query])[0]

    if db.get_bind().dialect.name == "postgresql":
        distance = Chunk.embedding.cosine_distance(query_vector).label("distance")
        rows = db.execute(
            select(Chunk, distance)
            .where(Chunk.analysis_id == analysis_id, Chunk.embedding.is_not(None))
            .order_by(distance)
            .limit(k)
        ).all()
        scored = [(1.0 - float(dist), chunk) for chunk, dist in rows]
    else:
        chunks = db.scalars(
            select(Chunk).where(Chunk.analysis_id == analysis_id, Chunk.embedding.is_not(None))
        ).all()
        scored = [
            (cosine_similarity(query_vector, chunk.embedding), chunk)
            for chunk in chunks
            if chunk.embedding
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        scored = scored[:k]

    return [
        {
            "chunk_id": chunk.id,
            "symbol_name": chunk.symbol_name,
            "kind": chunk.kind,
            "file_path": chunk.file_path,
            "line_start": chunk.line_start,
            "line_end": chunk.line_end,
            "score": round(score, 4),
            "snippet": chunk.text[:MAX_SNIPPET_CHARS],
        }
        for score, chunk in scored
    ]


def selective_search(db: Session, analysis_id: int, query: str, k: int = 8) -> dict:
    """Graph-first for identifier-like queries, semantic for natural language.

    RepoFormer-style gate: avoid paying for embeddings when a structural answer
    is available (Decision D3).
    """
    stripped = query.strip()
    if _IDENTIFIER_RE.match(stripped):
        matches = graph.search_symbols(db, analysis_id, query=stripped, limit=k)
        if matches:
            return {
                "mode": "graph",
                "query": query,
                "results": [
                    {
                        "chunk_id": None,
                        "symbol_name": item.name,
                        "kind": item.kind,
                        "file_path": item.file_path,
                        "line_start": item.line_start,
                        "line_end": item.line_start,
                        "score": None,
                        "snippet": "",
                    }
                    for item in matches
                ],
            }
    return {
        "mode": "semantic",
        "query": query,
        "results": semantic_search(db, analysis_id, query, k),
    }
