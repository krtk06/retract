"""Authentication: GitHub OAuth web flow + dev-bypass login + JWT cookie sessions."""

import secrets

import httpx
import redis
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import EveTokenOut, UserOut
from app.security import EVE_TOKEN_TTL_SECONDS, create_access_token, create_eve_token

router = APIRouter(prefix="/auth", tags=["auth"])

_STATE_TTL = 600


def _state_store() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def _set_session_cookie(response: Response, user: User) -> None:
    settings = get_settings()
    token = create_access_token(user.id)
    response.set_cookie(
        settings.auth_cookie_name,
        token,
        max_age=settings.jwt_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.auth_cookie_secure,
    )


@router.get("/github/login")
def github_login() -> RedirectResponse:
    settings = get_settings()
    if not settings.github_client_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="GitHub OAuth is not configured")
    state = secrets.token_urlsafe(16)
    _state_store().setex(f"oauth_state:{state}", _STATE_TTL, "1")
    url = (
        "https://github.com/login/oauth/authorize"
        f"?client_id={settings.github_client_id}"
        f"&redirect_uri={settings.github_oauth_redirect_uri}"
        f"&state={state}"
        "&scope=read:user"
    )
    return RedirectResponse(url)


@router.get("/github/callback")
def github_callback(code: str, state: str, db: Session = Depends(get_db)) -> RedirectResponse:
    settings = get_settings()
    store = _state_store()
    if not store.delete(f"oauth_state:{state}"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    token_resp = httpx.post(
        "https://github.com/login/oauth/access_token",
        data={
            "client_id": settings.github_client_id,
            "client_secret": settings.github_client_secret,
            "code": code,
            "redirect_uri": settings.github_oauth_redirect_uri,
        },
        headers={"Accept": "application/json"},
        timeout=15.0,
    )
    access_token = token_resp.json().get("access_token")
    if not access_token:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="GitHub token exchange failed")

    user_resp = httpx.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        timeout=15.0,
    )
    gh_user = user_resp.json()
    github_id = gh_user.get("id")
    login = gh_user.get("login")
    if not github_id or not login:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Failed to fetch GitHub profile")

    user = db.scalar(select(User).where(User.github_id == github_id))
    if user is None:
        user = User(github_id=github_id, login=login)
        db.add(user)
        db.commit()
        db.refresh(user)

    response = RedirectResponse(settings.frontend_url)
    _set_session_cookie(response, user)
    return response


@router.get("/dev/login")
def dev_login(
    login: str = Query(default="dev", min_length=1, max_length=64),
    db: Session = Depends(get_db),
) -> Response:
    """Dev-only login bypass (AI_INTEL_DEV_LOGIN=1). Never enable in production."""
    settings = get_settings()
    if not settings.dev_login:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")

    user = db.scalar(select(User).where(User.login == login))
    if user is None:
        user = User(github_id=None, login=login)
        db.add(user)
        db.commit()
        db.refresh(user)

    response = JSONResponse({"ok": True, "user": UserOut.model_validate(user).model_dump()})
    _set_session_cookie(response, user)
    return response


@router.post("/logout")
def logout() -> Response:
    settings = get_settings()
    response = JSONResponse({"ok": True})
    response.delete_cookie(settings.auth_cookie_name)
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/eve-token", response_model=EveTokenOut)
def eve_token(user: User = Depends(get_current_user)) -> EveTokenOut:
    """Exchange the authenticated session for a short-lived eve agent token."""
    return EveTokenOut(token=create_eve_token(user.id), expires_in=EVE_TOKEN_TTL_SECONDS)
