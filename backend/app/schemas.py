"""Pydantic schemas for API requests/responses."""

from datetime import datetime
from types import SimpleNamespace
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import Severity


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    login: str
    github_id: int | None
    email: str | None = None


class RegisterIn(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def _normalize(self) -> "RegisterIn":
        self.email = self.email.strip().lower()
        return self


class LoginIn(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def _normalize(self) -> "LoginIn":
        self.email = self.email.strip().lower()
        return self


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
    # Optional: the deterministic catalog already has generic advice for every
    # category, so the agent only supplies one when it can name a change specific
    # to the code it read.
    recommendation: str | None = Field(default=None, min_length=3, max_length=300)


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


class RemediationTargetOut(BaseModel):
    """One finding a work item covers."""

    finding_id: int
    title: str
    severity: str
    status: str
    file_path: str | None = None
    line_start: int | None = None


class RemediationItemOut(BaseModel):
    """A group of findings sharing one fix, with what that fix is worth."""

    key: str
    pillar: str
    action: str
    severity: str
    effort: str
    source: str
    steps: list[str]
    verify: str
    references: list[str]
    findings: list[RemediationTargetOut]
    finding_count: int
    # What this item is worth in its own pillar, against today's score. Not a share
    # of `recoverable_points`: the overall is capped at worst_pillar + 15, so
    # clearing a non-worst pillar barely moves the headline.
    pillar_points: int
    # Additive and exact: the curve's own input, and what the ranking sorts on.
    weighted_penalty_removed: float
    payoff: float


class RemediationPlanOut(BaseModel):
    analysis_id: int
    loc: int | None = None
    current_overall: int | None = None
    projected_overall: int | None = None
    recoverable_points: int | None = None
    work_items: list[RemediationItemOut] = Field(default_factory=list)
    findings_considered: int = 0
    unverified_items: int = 0
    truncated_findings: int = 0


class RemediationBriefOut(BaseModel):
    """The one-line fix, embedded in a findings response."""

    action: str
    effort: str
    source: str


class RemediationIn(BaseModel):
    """One LLM-authored remediation, as submitted by the eve agent."""

    finding_id: int = Field(ge=1)
    action: str = Field(min_length=3, max_length=300)
    steps: list[str] = Field(default_factory=list, max_length=10)
    effort: str = "medium"
    verify: str = Field(default="", max_length=500)
    references: list[str] = Field(default_factory=list, max_length=5)
    reasoning: str = Field(default="", max_length=1000)


class RemediationSubmitIn(BaseModel):
    agent: str = Field(min_length=1, max_length=64, pattern=r"^eve(:[a-z0-9-]+)?$")
    remediations: list[RemediationIn] = Field(default_factory=list, max_length=100)


class RemediationSubmitOut(BaseModel):
    analysis_id: int
    agent: str
    recorded: int
    rejected: int
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
    # Derived, not a column: the fix for this finding, whether the catalog
    # produced it or an LLM did. Carried on every finding so the table can show
    # advice inline without a second request.
    remediation: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _attach_remediation(self) -> "FindingOut":
        """Fill the derived ``remediation`` field from the finding itself.

        A validator rather than a column: the fix is a function of category plus
        evidence, so storing it would create a second source of truth that the
        catalog could drift from.
        """
        if self.remediation:
            return self
        from app.analysis_engine.remediation import remediation_summary

        try:
            self.remediation = remediation_summary(
                SimpleNamespace(
                    category=self.category,
                    title=self.title,
                    evidence_json=self.evidence_json,
                    file_path=self.file_path,
                    line_start=self.line_start,
                )
            )
        except Exception:  # noqa: BLE001 — advice must never break the list
            self.remediation = {}
        return self


class AnalysisEvent(BaseModel):
    type: str
    payload: dict[str, Any]
    ts: float


class ScoreOut(BaseModel):
    version: int
    overall: int
    loc: int | None
    # None when no LOC was measured: the score then comes from raw weighted
    # finding-points rather than density, and `basis` says so.
    kloc: float | None = None
    basis: str | None = None
    count_half_score_penalty: float | None = None
    pillars: dict[str, dict[str, Any]]
    previous_overall: int | None = None
    delta: int | None = None
    # The curve's calibration constants and the aggregation's inputs, so a client
    # can explain the number instead of restating it: score = 100 / (1 + density /
    # half_score_density) per pillar, overall = min(weighted_mean, worst_pillar +
    # worst_pillar_headroom).
    half_score_density: float | None = None
    worst_pillar_headroom: int | None = None
    worst_pillar: int | None = None
    weighted_mean: float | None = None


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


class AnalysisSummaryOut(BaseModel):
    """One row of the user dashboard: recent analyses across the user's repos."""

    id: int
    repository_id: int
    repo_owner: str
    repo_name: str
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
