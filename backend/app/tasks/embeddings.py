"""Embedding index build task — chunks symbols and embeds them (Phase 3, D3)."""

import logging
import time
from pathlib import Path

from sqlalchemy import func, select

from app.analysis_engine import chunker
from app.analysis_engine.embeddings import get_embedding_provider
from app.db import get_session_factory
from app.events import get_bus
from app.models import Chunk, Edge, FindingStatus, Severity, Symbol
from app.services.tools.findings import FindingDraft, persist_findings
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

BATCH_SIZE = 64


@celery_app.task(
    name="app.tasks.embeddings.embed_analysis",
    soft_time_limit=1800,
    time_limit=1860,
    max_retries=0,
)
def embed_analysis(analysis_id: int, repo_root: str) -> dict:
    """Build chunks from tree-sitter symbols, embed them, mark the graph snapshot.

    Never raises (chord robustness): provider failures degrade to a warning.
    """
    bus = get_bus()
    started = time.monotonic()
    session = get_session_factory()()
    try:
        drafts = chunker.build_chunks(session, analysis_id, Path(repo_root))
        chunk_count = chunker.persist_chunks(session, analysis_id, drafts)

        embedded = 0
        provider_name = "none"
        try:
            provider = get_embedding_provider()
            provider_name = provider.name
            pending = list(
                session.scalars(
                    select(Chunk).where(Chunk.analysis_id == analysis_id, Chunk.embedding.is_(None))
                ).all()
            )
            for start in range(0, len(pending), BATCH_SIZE):
                batch = pending[start : start + BATCH_SIZE]
                vectors = provider.embed([chunk.text for chunk in batch])
                for chunk, vector in zip(batch, vectors, strict=False):
                    chunk.embedding = vector
                session.commit()
                embedded += len(batch)
        except Exception as exc:  # noqa: BLE001 — embeddings are best-effort
            logger.warning("embedding failed for analysis %s: %s", analysis_id, exc)
            bus.publish(
                analysis_id,
                "tool",
                {
                    "tool": "embeddings",
                    "status": "error",
                    "error": str(exc)[:200],
                    "seconds": round(time.monotonic() - started, 2),
                },
            )

        symbol_count = (
            session.scalar(select(func.count(Symbol.id)).where(Symbol.analysis_id == analysis_id))
            or 0
        )
        edge_count = (
            session.scalar(select(func.count(Edge.id)).where(Edge.analysis_id == analysis_id)) or 0
        )
        chunker.mark_graph_snapshot(session, analysis_id, symbol_count, edge_count, chunk_count)

        if embedded or chunk_count:
            bus.publish(
                analysis_id,
                "tool",
                {
                    "tool": "embeddings",
                    "status": "ok",
                    "findings": 0,
                    "seconds": round(time.monotonic() - started, 2),
                    "message": f"{chunk_count} chunks, {embedded} embedded ({provider_name})",
                },
            )
        return {"ok": True, "chunks": chunk_count, "embedded": embedded, "provider": provider_name}
    except Exception as exc:  # noqa: BLE001
        logger.exception("embed task failed for analysis %s", analysis_id)
        try:
            persist_findings(
                session,
                analysis_id,
                [
                    FindingDraft(
                        agent="orchestrator",
                        category="tool-error",
                        severity=Severity.INFO,
                        title="Tool 'embeddings' failed",
                        description=str(exc)[:1000],
                        verifier="tool:orchestrator",
                        status=FindingStatus.VERIFIED,
                    )
                ],
            )
        except Exception:  # noqa: BLE001
            logger.exception("failed to record embeddings failure")
        return {"ok": False, "error": str(exc)}
    finally:
        session.close()
