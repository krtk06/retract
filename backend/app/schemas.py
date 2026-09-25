"""Pydantic schemas for API requests/responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    login: str
    github_id: int | None


class RepoCreate(BaseModel):
    url: str


class RepoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner: str
    name: str
    url: str
    default_branch: str
    created_at: datetime
    latest_analysis_id: int | None = None
    latest_analysis_status: str | None = None


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    repository_id: int
    commit_sha: str | None
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    created_at: datetime
    finding_count: int = 0
    loc: int | None = None
    score_json: dict[str, Any] | None = None
    cost_json: dict[str, Any] | None = None
    repository: RepoOut | None = None


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    analysis_id: int
    agent: str
    category: str
    severity: str
    title: str
    description: str
    file_path: str | None
    line_start: int | None
    line_end: int | None
    evidence_json: dict[str, Any] | None
    verifier: str
    confidence: float
    status: str
    created_at: datetime


class AnalysisEvent(BaseModel):
    type: str
    payload: dict[str, Any]
    ts: float


class ScoreOut(BaseModel):
    version: int
    overall: int
    loc: int | None
    kloc: float
    pillars: dict[str, dict[str, Any]]


class SymbolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    kind: str
    file_path: str
    line_start: int


class GraphSummaryOut(BaseModel):
    symbols: dict[str, int]
    edges: dict[str, int]
    top_importing_modules: list[dict[str, Any]]


class GraphNodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    kind: str
    file_path: str
    line_start: int
    line_end: int


class GraphLinkOut(BaseModel):
    source: str
    target: str
    kind: str


class GraphNeighborhoodOut(BaseModel):
    root: GraphNodeOut | None
    nodes: list[GraphNodeOut]
    links: list[GraphLinkOut]


class SearchResult(BaseModel):
    chunk_id: int | None
    symbol_name: str
    kind: str
    file_path: str
    line_start: int
    line_end: int
    score: float | None
    snippet: str


class SearchResponse(BaseModel):
    mode: str
    query: str
    results: list[SearchResult]


class HealthOut(BaseModel):
    status: str
    db: str
    redis: str
