"""Knowledge graph endpoints (symbol structure, not vector retrieval)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.analysis_engine import graph
from app.db import get_db
from app.deps import get_current_user
from app.models import Analysis, User
from app.schemas import (
    GraphNeighborhoodOut,
    GraphSummaryOut,
    SymbolOut,
)

router = APIRouter(prefix="/analyses", tags=["graph"])


def _ensure_analysis(db: Session, analysis_id: int) -> Analysis:
    analysis = db.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    return analysis


@router.get("/{analysis_id}/graph/summary", response_model=GraphSummaryOut)
def graph_summary(
    analysis_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> GraphSummaryOut:
    _ensure_analysis(db, analysis_id)
    return GraphSummaryOut.model_validate(graph.summary(db, analysis_id))


@router.get("/{analysis_id}/graph/symbols", response_model=list[SymbolOut])
def graph_symbols(
    analysis_id: int,
    q: str | None = None,
    kind: str | None = None,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[SymbolOut]:
    _ensure_analysis(db, analysis_id)
    return [
        SymbolOut.model_validate(item, from_attributes=True)
        for item in graph.search_symbols(db, analysis_id, query=q, kind=kind, limit=limit)
    ]


@router.get("/{analysis_id}/graph/neighborhood", response_model=GraphNeighborhoodOut)
def graph_neighborhood(
    analysis_id: int,
    symbol: str,
    depth: int = Query(default=2, ge=1, le=4),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> GraphNeighborhoodOut:
    _ensure_analysis(db, analysis_id)
    result = graph.neighborhood(db, analysis_id, symbol, depth=depth)
    return GraphNeighborhoodOut.model_validate(result, from_attributes=True)


@router.get("/{analysis_id}/graph/callers")
def graph_callers(
    analysis_id: int,
    symbol: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    _ensure_analysis(db, analysis_id)
    return graph.callers(db, analysis_id, symbol)


@router.get("/{analysis_id}/graph/callees")
def graph_callees(
    analysis_id: int,
    symbol: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    _ensure_analysis(db, analysis_id)
    return graph.callees(db, analysis_id, symbol)


@router.get("/{analysis_id}/graph/imports")
def graph_imports(
    analysis_id: int,
    module: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    _ensure_analysis(db, analysis_id)
    return graph.imports(db, analysis_id, module)


@router.get("/{analysis_id}/graph/dependents")
def graph_dependents(
    analysis_id: int,
    module: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    _ensure_analysis(db, analysis_id)
    return graph.dependents(db, analysis_id, module)


@router.get("/{analysis_id}/graph/path", response_model=list[SymbolOut])
def graph_path(
    analysis_id: int,
    from_symbol: str = Query(alias="from"),
    to_symbol: str = Query(alias="to"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[SymbolOut]:
    _ensure_analysis(db, analysis_id)
    return [
        SymbolOut.model_validate(item, from_attributes=True)
        for item in graph.path(db, analysis_id, from_symbol, to_symbol)
    ]
