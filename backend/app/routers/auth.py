"""Authentication: GitHub OAuth, email/password accounts, dev-bypass login, JWT cookies."""

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
from app.schemas import EveTokenOut, LoginIn, RegisterIn, UserOut
from app.security import (
    EVE_TOKEN_TTL_SECONDS,
    create_access_token,
    create_eve_token,
    hash_password,
    verify_password,
)

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


def _unique_login(db: Session, base: str) -> str:
    """Derive a unique ``login`` from an email's local part."""
    cleaned = "".join(c for c in base if c.isalnum() or c in "-_")[:48] or "user"
    candidate = cleaned
    suffix = 1
    while db.scalar(select(User).where(User.login == candidate)) is not None:
        candidate = f"{cleaned}-{suffix}"
        suffix += 1
    return candidate


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, response: Response, db: Session = Depends(get_db)) -> User:
    """Create an email/password account and sign the new session in immediately."""
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        email=payload.email,
        login=_unique_login(db, payload.email.split("@", 1)[0]),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    _set_session_cookie(response, user)
    return user


@router.post("/login", response_model=UserOut)
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)) -> User:
    """Exchange an email/password pair for a session cookie.

    The error is the same for a wrong email and a wrong password so the endpoint
    cannot be used to enumerate registered addresses.
    """
    user = db.scalar(select(User).where(User.email == payload.email))
    if (
        user is None
        or not user.password_hash
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    _set_session_cookie(response, user)
    return user


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
    """Dev-only login bypass (RETRACT_DEV_LOGIN=1). Never enable in production."""
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
