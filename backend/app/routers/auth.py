"""Authentication: GitHub OAuth, email/password accounts, dev-bypass login, JWT cookies."""

import logging
import secrets
from urllib.parse import urlsplit, urlunsplit

import httpx
import redis
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
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

logger = logging.getLogger(__name__)

# How long a sign-in attempt stays valid. Ten minutes was short enough to fail a
# real user: authorizing means finding a password manager, switching to a 2FA
# app, and coming back — and the only symptom was `{"detail":"Invalid OAuth
# state"}` at an API URL, naming no cause and offering no way forward. Thirty
# minutes is the conventional upper bound and is still bounded.
_STATE_TTL = 1800

# The consumed-state marker. A delete cannot tell "expired" from "already used",
# and those need different advice: one means start again, the other means the
# sign-in already succeeded and the user should simply return to the app. Same TTL
# as the state itself, so the marker outlives any plausible replay and then
# disappears on its own — no cleanup job, and ~40 bytes per attempt.
_USED_STATE_PREFIX = "oauth_state:used:"

# Fixed codes, never user input: nothing from the request reaches the redirect
# URL, so this cannot become an open redirect.
AUTH_ERROR_NOT_CONFIGURED = "not_configured"
AUTH_ERROR_EXPIRED = "expired_state"
AUTH_ERROR_USED = "used_state"
AUTH_ERROR_EXCHANGE = "exchange_failed"
AUTH_ERROR_PROFILE = "profile_failed"

_AUTH_ERROR_MESSAGES = {
    AUTH_ERROR_NOT_CONFIGURED: "GitHub sign-in is not configured",
    AUTH_ERROR_EXPIRED: "This sign-in attempt expired",
    AUTH_ERROR_USED: "This sign-in link was already used",
    AUTH_ERROR_EXCHANGE: "GitHub refused to complete the sign-in",
    AUTH_ERROR_PROFILE: "Could not read the GitHub profile",
}


def _state_store() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def _wants_redirect(request: Request) -> bool:
    """Whether this caller is a browser following the sign-in link.

    The OAuth callback is only ever reached by a browser navigation, and answering
    one with a bare JSON body dumps the user at an API URL with no way forward.
    Anything explicitly asking for JSON — a script, a test asserting the status
    code — still gets the 400 it gets today.
    """
    return "text/html" in request.headers.get("accept", "")


def _auth_failure(request: Request, code: str) -> RedirectResponse:
    """Report a failed sign-in: back to the app for a browser, JSON otherwise.

    The JSON path raises rather than returning, so this always hands back a
    redirect when it returns at all.
    """
    detail = _AUTH_ERROR_MESSAGES.get(code, "Sign-in failed")
    logger.warning("github oauth failed: %s", detail)
    if not _wants_redirect(request):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=code)
    # Built with urlsplit rather than string concatenation: the configured
    # frontend URL may or may not carry a path, a trailing slash, or an existing
    # query, and all three have to survive.
    parts = urlsplit(get_settings().frontend_url)
    query = f"{parts.query}&" if parts.query else ""
    return RedirectResponse(urlunsplit(parts._replace(query=f"{query}auth_error={code}")))


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
def github_login(request: Request) -> RedirectResponse:
    settings = get_settings()
    if not settings.github_client_id:
        return _auth_failure(request, AUTH_ERROR_NOT_CONFIGURED)
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
def github_callback(
    request: Request,
    code: str,
    state: str,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    store = _state_store()
    if not store.delete(f"oauth_state:{state}"):
        # A consumed state and a lapsed one look identical to a delete, so the
        # marker written at consume time is what separates them — and the advice
        # differs: "already signed in" versus "start again".
        if store.exists(f"{_USED_STATE_PREFIX}{state}"):
            return _auth_failure(request, AUTH_ERROR_USED)
        return _auth_failure(request, AUTH_ERROR_EXPIRED)
    store.setex(f"{_USED_STATE_PREFIX}{state}", _STATE_TTL, "1")

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
        return _auth_failure(request, AUTH_ERROR_EXCHANGE)

    user_resp = httpx.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        timeout=15.0,
    )
    gh_user = user_resp.json()
    github_id = gh_user.get("id")
    login = gh_user.get("login")
    if not github_id or not login:
        return _auth_failure(request, AUTH_ERROR_PROFILE)

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
