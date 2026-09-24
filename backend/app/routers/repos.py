"""Repository registration and analysis triggering."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import Analysis, AnalysisStatus, Repository, User
from app.schemas import AnalysisOut, RepoCreate, RepoOut
from app.services.github import InvalidRepoUrl, canonical_url, parse_github_url
from app.tasks.analysis import run_analysis

router = APIRouter(prefix="/repos", tags=["repos"])

_ACTIVE_STATUSES = (AnalysisStatus.PENDING, AnalysisStatus.RUNNING)


def _to_out(db: Session, repo: Repository) -> RepoOut:
    latest = db.scalar(
        select(Analysis)
        .where(Analysis.repository_id == repo.id)
        .order_by(Analysis.created_at.desc())
        .limit(1)
    )
    out = RepoOut.model_validate(repo)
    if latest is not None:
        out.latest_analysis_id = latest.id
        out.latest_analysis_status = latest.status.value
    return out


@router.post("", response_model=RepoOut, status_code=status.HTTP_201_CREATED)
def create_repo(
    payload: RepoCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RepoOut:
    settings = get_settings()
    try:
        owner, name = parse_github_url(payload.url)
        url = canonical_url(owner, name)
    except InvalidRepoUrl as github_error:
        if settings.allow_local_repos and payload.url.startswith("local://"):
            from pathlib import Path

            source = Path(payload.url.removeprefix("local://"))
            if not source.is_dir():
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Local path does not exist: {source}",
                ) from github_error
            owner, name = "local", source.name
            url = f"local://{source}"
        else:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(github_error)
            ) from github_error
    repo = db.scalar(select(Repository).where(Repository.url == url))
    if repo is None:
        repo = Repository(owner=owner, name=name, url=url, added_by=user.id)
        db.add(repo)
        db.commit()
        db.refresh(repo)
    return _to_out(db, repo)


@router.get("", response_model=list[RepoOut])
def list_repos(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[RepoOut]:
    repos = db.scalars(select(Repository).order_by(Repository.created_at.desc())).all()
    return [_to_out(db, repo) for repo in repos]


@router.post("/{repo_id}/analyze", response_model=AnalysisOut, status_code=status.HTTP_201_CREATED)
def analyze_repo(
    repo_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> AnalysisOut:
    repo = db.get(Repository, repo_id)
    if repo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Repository not found")

    active = db.scalar(
        select(Analysis).where(
            Analysis.repository_id == repo_id, Analysis.status.in_(_ACTIVE_STATUSES)
        )
    )
    if active is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Analysis {active.id} is already {active.status.value}",
        )

    analysis = Analysis(repository_id=repo_id, status=AnalysisStatus.PENDING)
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    run_analysis.delay(analysis.id)

    return AnalysisOut.model_validate(analysis)
