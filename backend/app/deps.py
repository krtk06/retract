"""FastAPI dependencies."""

import secrets

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Analysis, Repository, User, UserRepository
from app.security import decode_access_token

AGENT_TOKEN_HEADER = "X-Agent-Token"
AGENT_USER_HEADER = "X-Agent-User"


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Authenticate a browser session, or the eve agent's service credential.

    The eve agent runs server-side and cannot present the browser's httpOnly
    cookie, so its tools authenticate with the shared ``X-Agent-Token`` secret and
    name the acting user in ``X-Agent-User``. A presented but wrong secret fails
    closed instead of falling back to the cookie.
    """
    settings = get_settings()
    presented = request.headers.get(AGENT_TOKEN_HEADER)
    if presented is not None:
        return _agent_user(request, presented, db)
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    claims = decode_access_token(token)
    if claims is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = db.get(User, claims.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User not found")
    # The token names the session generation it was minted in; a bump (logout,
    # "sign out everywhere") revokes every token that carries an older one.
    if user.token_version != claims.token_version:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session has ended")
    return user


def _agent_user(request: Request, presented: str, db: Session) -> User:
    settings = get_settings()
    # Compared as bytes: `compare_digest` refuses non-ASCII `str` operands with a
    # TypeError, so a header like `tëst` used to escape as an unhandled 500 from an
    # unauthenticated request instead of a plain 401. Bytes compare cleanly and the
    # mismatch simply fails closed.
    if not settings.agent_token or not secrets.compare_digest(
        presented.encode("utf-8"), settings.agent_token.encode("utf-8")
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid agent token")
    login = request.headers.get(AGENT_USER_HEADER)
    if login:
        user = db.scalar(select(User).where(User.login == login))
        # `isdigit()` is true for non-ASCII digits too, and `int()` rejects those
        # right back — so the ASCII check is what keeps this a lookup miss (`user`
        # stays None → 401 below) rather than a 500.
        if user is None and login.isascii() and login.isdigit():
            # The eve session's principal is the token subject: the user id.
            user = db.get(User, int(login))
        if user is not None:
            return user
    # Evals and CI have no browser session: attribute agent activity to the
    # first registered user rather than minting rows on demand. A production
    # deployment must keep that fallback closed — an unnamed agent call there
    # is an error, not CI.
    if not settings.dev_login:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Unattributed agent call: X-Agent-User is required",
        )
    user = db.scalar(select(User).order_by(User.id).limit(1))
    if user is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No user exists to own agent activity; sign in once first",
        )
    return user


def owns_repo(db: Session, user_id: int, repo_id: int) -> bool:
    """True when the user added this repository (shared rows keep one clone)."""
    return (
        db.scalar(
            select(UserRepository).where(
                UserRepository.user_id == user_id, UserRepository.repo_id == repo_id
            )
        )
        is not None
    )


def get_owned_repo_or_404(db: Session, repo_id: int, user: User) -> Repository:
    """Load a repository the user may act on, without leaking which ones exist."""
    repo = db.get(Repository, repo_id)
    if repo is None or not owns_repo(db, user.id, repo.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Repository not found")
    return repo


def get_owned_analysis_or_404(db: Session, analysis_id: int, user: User) -> Analysis:
    """Load an analysis whose repository the user owns.

    Forbidden and missing collapse into the same 404 so the endpoint cannot be
    used to probe whether other users' analysis ids exist.
    """
    analysis = db.get(Analysis, analysis_id)
    if analysis is None or not owns_repo(db, user.id, analysis.repository_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    return analysis
