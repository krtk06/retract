"""Pydantic schemas for API requests/responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import Severity


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
    published: bool = False
    pending_approvals: int = 0
    repository: RepoOut | None = None


class AgentFindingIn(BaseModel):
    """One D2 verdict claim as submitted by the eve agent."""

    claim: str = Field(min_length=3, max_length=300)
    evidence: str = Field(min_length=3, max_length=2000)
    file_path: str | None = None
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    severity: Severity
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    category: str = Field(default="insight", max_length=64)


class AgentFindingsIn(BaseModel):
    agent: str = Field(min_length=1, max_length=64, pattern=r"^eve(:[a-z0-9-]+)?$")
    findings: list[AgentFindingIn] = Field(default_factory=list, max_length=100)
    triage: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    summary: str = Field(default="", max_length=4000)


class AgentFindingsOut(BaseModel):
    analysis_id: int
    agent: str
    inserted: int
    dropped: int
    dismissed: int = 0
    promoted: int = 0
    checked: int = 0
    overall: int | None = None
    published: bool = False
    reasons: list[str] = Field(default_factory=list)


class EveTokenOut(BaseModel):
    token: str
    expires_in: int


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
    previous_overall: int | None = None
    delta: int | None = None


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


class ApprovalRequest(BaseModel):
    finding_id: int
    decision: str  # "approve" | "dismiss"
    note: str | None = None


class ApprovalOut(BaseModel):
    finding_id: int
    decision: str
    finding_status: str
    confidence: float
    note: str | None = None
    pending_count: int = 0
    published: bool = False


class QueueOut(BaseModel):
    analysis_id: int
    published: bool
    pending_count: int
    approved_count: int
    dismissed_count: int
    pending: list[FindingOut]


class CalibrationStatOut(BaseModel):
    agent: str
    category: str
    shown: int
    accepted: int
    dismissed: int
    acceptance_rate: float | None = None


class AnalysisHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    repository_id: int
    commit_sha: str | None
    status: str
    created_at: datetime
    finished_at: datetime | None
    loc: int | None = None
    published: bool = False
    finding_count: int = 0
    overall: int | None = None


class AgentTrustOut(BaseModel):
    agent: str
    findings: int
    verified: int
    hypotheses: int
    dismissed: int
    avg_confidence: float | None = None


class TrustTotalsOut(BaseModel):
    findings: int
    verified: int
    hypotheses: int
    dismissed: int


class TrustSummaryOut(BaseModel):
    analysis_id: int
    totals: TrustTotalsOut
    verification_coverage: float | None = None
    avg_confidence: float | None = None
    agents: list[AgentTrustOut]
    acceptance_rates: list[CalibrationStatOut]


class CompareSideOut(BaseModel):
    id: int
    commit_sha: str | None
    created_at: str | None
    overall: int | None
    loc: int | None


class PillarCompareOut(BaseModel):
    pillar: str
    left_score: int
    right_score: int
    delta: int
    left_findings: int
    right_findings: int


class CompareOut(BaseModel):
    left: CompareSideOut
    right: CompareSideOut
    overall_delta: int | None
    pillars: list[PillarCompareOut]


class HealthOut(BaseModel):
    status: str
    db: str
    redis: str
