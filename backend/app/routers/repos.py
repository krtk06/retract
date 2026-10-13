"""Repository registration and analysis triggering."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import rate_limit
from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user, get_owned_repo_or_404, visible_repository_ids
from app.models import Analysis, AnalysisStatus, Repository, User, UserRepository
from app.schemas import AnalysisOut, RepoCreate, RepoOut
from app.services.github import InvalidRepoUrl, canonical_url, parse_github_url
from app.tasks.analysis import run_analysis

router = APIRouter(prefix="/repos", tags=["repos"])

_ACTIVE_STATUSES = (AnalysisStatus.PENDING, AnalysisStatus.RUNNING)


def _grant_access(db: Session, repo: Repository, user: User) -> None:
    """Add the user to the repo's owners when not already associated."""
    exists = db.scalar(
        select(UserRepository).where(
            UserRepository.repo_id == repo.id, UserRepository.user_id == user.id
        )
    )
    if exists is None:
        db.add(UserRepository(repo_id=repo.id, user_id=user.id))


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
    # A private copy per creator. The previous version looked the URL up globally and
    # granted the caller access to whatever row it found, so registering someone
    # else's repository URL handed over their analyses and file contents. Nothing had
    # verified the caller could reach that repository, so the URL was the whole check.
    #
    # Development accounts are the deliberate exception: they share one row per URL,
    # so a dev machine does not clone the same repository once per test account.
    if user.is_dev:
        repo = db.scalar(select(Repository).where(Repository.url == url, Repository.is_shared))
        if repo is None:
            repo = Repository(owner=owner, name=name, url=url, added_by=user.id, is_shared=True)
            db.add(repo)
            db.commit()
            db.refresh(repo)
    else:
        repo = db.scalar(
            select(Repository).where(
                Repository.url == url,
                Repository.added_by == user.id,
                Repository.is_shared.is_(False),
            )
        )
        if repo is None:
            repo = Repository(owner=owner, name=name, url=url, added_by=user.id)
            db.add(repo)
            db.commit()
            db.refresh(repo)
    _grant_access(db, repo, user)
    db.commit()
    return _to_out(db, repo)


@router.get("", response_model=list[RepoOut])
def list_repos(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[RepoOut]:
    """Repos the caller can see: their own, plus the shared pool for dev accounts."""
    repos = (
        db.scalars(
            select(Repository)
            .where(Repository.id.in_(visible_repository_ids(user)))
            .order_by(Repository.created_at.desc())
        )
        .unique()
        .all()
    )
    return [_to_out(db, repo) for repo in repos]


@router.post("/{repo_id}/analyze", response_model=AnalysisOut, status_code=status.HTTP_201_CREATED)
def analyze_repo(
    repo_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AnalysisOut:
    # Ownership gate (404 when the repo is absent or not the caller's).
    get_owned_repo_or_404(db, repo_id, user)

    # Every run clones the repository and fans out to six tools on the Celery
    # workers. Re-running a finished analysis is legitimate, but unbounded it lets
    # one account occupy the shared queue indefinitely — so the budget is per user.
    rate_limit.enforce(request, "analyze", limit=30, window_seconds=3600, who=str(user.id))

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
