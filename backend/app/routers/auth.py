"""Authentication: GitHub OAuth, email/password accounts, dev-bypass login, JWT cookies."""

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta

import httpx
import redis
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import mailer, rate_limit
from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import EmailVerificationToken, User
from app.routers.auth_support import (
    AUTH_ERROR_EXCHANGE,
    AUTH_ERROR_EXPIRED,
    AUTH_ERROR_NOT_CONFIGURED,
    AUTH_ERROR_PROFILE,
    AUTH_ERROR_USED,
    AUTH_ERROR_VERIFICATION,
    _auth_failure,
    _aware,
    _primary_verified_email,
    _resolve_github_account,
    _return_origin,
    _set_session_cookie,
    _unique_login,
    _with_query,
)
from app.schemas import EveTokenOut, LoginIn, RegisterIn, UserOut
from app.security import (
    EVE_TOKEN_TTL_SECONDS,
    create_eve_token,
    decode_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

logger = logging.getLogger(__name__)

# A real bcrypt hash of a throwaway value, verified against on the "no such account"
# path so a login costs the same whether or not the address exists (see `login`).
# Hashed once at import: ~0.25s of startup, not per request.
_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(24))

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


def _state_store() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def _send_verification_email(db: Session, user: User, request: Request) -> None:
    """Issue a fresh verification link for this account and email it.

    Only the SHA-256 of the token is stored, so a database leak does not yield a
    set of working links. Delivery is best-effort (see app/mailer.py).

    The link is built from the origin the request came from rather than from a
    configured constant, for the same reason the OAuth redirect is: a constant
    drifts from reality, and the failure is invisible until someone clicks a link
    that goes nowhere. A registration made through the app knows where the app is.
    """
    settings = get_settings()
    raw = secrets.token_urlsafe(32)
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=datetime.now(UTC)
            + timedelta(seconds=settings.email_verification_ttl_seconds),
        )
    )
    db.commit()
    if user.email:
        # The link points at the API through the app's own origin: the dev server and
        # the production nginx both proxy /api, so one URL works in both and the
        # verification request stays same-origin with the app.
        link = _with_query(f"{_return_origin(request)}/api/auth/verify-email", token=raw)
        mailer.send_verification(
            user.email, link, max(settings.email_verification_ttl_seconds // 3600, 1)
        )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    """Create an email/password account and sign the new session in immediately."""
    # Registration is unauthenticated and reveals whether an address is taken (409,
    # by necessity: the user must be told). A limit is what keeps that from becoming
    # a bulk enumeration tool.
    rate_limit.enforce(request, "register", limit=10, window_seconds=3600)
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        email=payload.email,
        login=_unique_login(db, payload.email.split("@", 1)[0]),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # The check above and this insert are not atomic, so two concurrent requests
        # for one address both pass the check and one violates the unique index. That
        # is the same "already registered" outcome, not a server fault — and the
        # codebase already answers this constraint deliberately elsewhere.
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered") from None
    db.refresh(user)
    _set_session_cookie(response, user)
    # Issued after the account exists, and never allowed to fail the sign-up: an
    # unavailable mail server must not cost someone their registration. The banner
    # offers a resend.
    _send_verification_email(db, user, request)
    return user


@router.post("/login", response_model=UserOut)
def login(
    payload: LoginIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    """Exchange an email/password pair for a session cookie.

    The error is the same for a wrong email and a wrong password so the endpoint
    cannot be used to enumerate registered addresses.
    """
    rate_limit.enforce(request, "login", limit=20, window_seconds=900)
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not user.password_hash:
        # Hash anyway. Returning before bcrypt made an unknown address answer in
        # ~2ms against ~0.3s for a known one, which is a better enumeration oracle
        # than the message the code was carefully keeping uniform.
        verify_password(payload.password, _DUMMY_PASSWORD_HASH)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    _set_session_cookie(response, user)
    return user


@router.get("/github/login")
def github_login(request: Request) -> RedirectResponse:
    settings = get_settings()
    if not settings.github_client_id:
        return _auth_failure(request, AUTH_ERROR_NOT_CONFIGURED)
    state = secrets.token_urlsafe(16)
    # The origin is stored beside the nonce rather than trusted from the callback,
    # so the return target cannot be tampered with on the way back from GitHub.
    _state_store().setex(f"oauth_state:{state}", _STATE_TTL, _return_origin(request))
    url = (
        "https://github.com/login/oauth/authorize"
        f"?client_id={settings.github_client_id}"
        f"&redirect_uri={settings.github_oauth_redirect_uri}"
        f"&state={state}"
        # user:email is what lets an existing account be recognised instead of
        # shadowed by a duplicate — read-only, and it is the email address, no
        # repository access.
        "&scope=read:user%20user:email"
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
    return_to = store.get(f"oauth_state:{state}")
    if not store.delete(f"oauth_state:{state}"):
        # A consumed state and a lapsed one look identical to a delete, so the
        # marker written at consume time is what separates them — and the advice
        # differs: "already signed in" versus "start again".
        if store.exists(f"{_USED_STATE_PREFIX}{state}"):
            return _auth_failure(request, AUTH_ERROR_USED, return_to)
        return _auth_failure(request, AUTH_ERROR_EXPIRED, return_to)
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
        return _auth_failure(request, AUTH_ERROR_EXCHANGE, return_to)

    user_resp = httpx.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        timeout=15.0,
    )
    gh_user = user_resp.json()
    github_id = gh_user.get("id")
    login = gh_user.get("login")
    if not github_id or not login:
        return _auth_failure(request, AUTH_ERROR_PROFILE, return_to)

    # The email is what lets an existing account be recognised rather than
    # shadowed by a duplicate — the same person signing in with GitHub and with
    # their password must land on one account, or each gets its own dashboard.
    email = _primary_verified_email(access_token)
    user = _resolve_github_account(db, github_id, login, email)

    # Back to the host the sign-in started on, not a configured constant that
    # may name a different one — see _return_origin.
    response = RedirectResponse(return_to or settings.frontend_url)
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
        # Marked as a development account: these are the only users that share the
        # repository pool (see Repository.is_shared).
        user = User(github_id=None, login=login, is_dev=True)
        db.add(user)
        db.commit()
        db.refresh(user)

    response = JSONResponse({"ok": True, "user": UserOut.model_validate(user).model_dump()})
    _set_session_cookie(response, user)
    return response


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)) -> Response:
    """End the session on the server, not only in the browser.

    Clearing the cookie stops *this* browser, but a JWT is valid until it expires
    and may already be copied — from a shared machine, a proxy log, a backup. So
    logout also bumps the user's token version, which revokes every token minted
    before this point. An absent or invalid cookie still gets a clean response:
    logging out twice, or from a stale tab, must not error.
    """
    settings = get_settings()
    token = request.cookies.get(settings.auth_cookie_name)
    claims = decode_access_token(token) if token else None
    if claims is not None:
        user = db.get(User, claims.user_id)
        if user is not None and user.token_version == claims.token_version:
            user.token_version += 1
            db.commit()
    response = JSONResponse({"ok": True})
    response.delete_cookie(settings.auth_cookie_name)
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("/verify-email")
def verify_email(
    request: Request,
    token: str = Query(min_length=1, max_length=128),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Confirm an address from the link in the email, then return to the app.

    A GET because it is a link in an email and a browser follows it; it redirects
    rather than answering with JSON so the user lands in the app, exactly as the
    GitHub callback does.

    One failure code for "no such token", "already used", and "expired": they are
    indistinguishable to a link-follower, and separating them would let someone
    probe which tokens exist.
    """
    settings = get_settings()
    digest = hashlib.sha256(token.encode()).hexdigest()
    row = db.scalar(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == digest)
    )
    now = datetime.now(UTC)
    if row is None or row.consumed_at is not None or _aware(row.expires_at) < now:
        return _auth_failure(request, AUTH_ERROR_VERIFICATION)

    user = db.get(User, row.user_id)
    if user is None:
        return _auth_failure(request, AUTH_ERROR_VERIFICATION)

    user.email_verified = True
    row.consumed_at = now
    db.commit()
    logger.info("email verified for user %s", user.id)
    return RedirectResponse(_with_query(settings.frontend_url, email_verified="1"))


@router.post("/resend-verification")
def resend_verification(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JSONResponse:
    """Send another verification link to the signed-in account.

    Authenticated on purpose: the sender must be the account holder, or this is a
    way to mail arbitrary addresses from the deployment's domain. Rate-limited
    because it is, even then, a way to send mail.
    """
    rate_limit.enforce(
        request, "resend-verification", limit=5, window_seconds=3600, who=str(user.id)
    )
    if not user.email:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="This account has no email address to verify",
        )
    if user.email_verified:
        return JSONResponse({"ok": True, "already_verified": True})
    _send_verification_email(db, user, request)
    return JSONResponse({"ok": True, "already_verified": False})


@router.post("/eve-token", response_model=EveTokenOut)
def eve_token(user: User = Depends(get_current_user)) -> EveTokenOut:
    """Exchange the authenticated session for a short-lived eve agent token."""
    return EveTokenOut(token=create_eve_token(user.id), expires_in=EVE_TOKEN_TTL_SECONDS)
