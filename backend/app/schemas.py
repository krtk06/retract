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


class HealthOut(BaseModel):
    status: str
    db: str
    redis: str
