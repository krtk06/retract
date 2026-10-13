"""Authentication: GitHub OAuth, email/password accounts, dev-bypass login, JWT cookies."""

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx
import redis
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import mailer, rate_limit
from app.config import get_settings, is_loopback
from app.db import get_db
from app.deps import get_current_user
from app.models import EmailVerificationToken, User
from app.schemas import EveTokenOut, LoginIn, RegisterIn, UserOut
from app.security import (
    EVE_TOKEN_TTL_SECONDS,
    create_access_token,
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

# Fixed codes, never user input: nothing from the request reaches the redirect
# URL, so this cannot become an open redirect.
AUTH_ERROR_NOT_CONFIGURED = "not_configured"
AUTH_ERROR_EXPIRED = "expired_state"
AUTH_ERROR_USED = "used_state"
AUTH_ERROR_EXCHANGE = "exchange_failed"
AUTH_ERROR_PROFILE = "profile_failed"
AUTH_ERROR_VERIFICATION = "verification_failed"

_AUTH_ERROR_MESSAGES = {
    AUTH_ERROR_NOT_CONFIGURED: "GitHub sign-in is not configured",
    AUTH_ERROR_EXPIRED: "This sign-in attempt expired",
    AUTH_ERROR_USED: "This sign-in link was already used",
    AUTH_ERROR_EXCHANGE: "GitHub refused to complete the sign-in",
    AUTH_ERROR_PROFILE: "Could not read the GitHub profile",
    AUTH_ERROR_VERIFICATION: "This verification link is invalid or has expired",
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


def _origin_of(value: str | None) -> str | None:
    """The scheme+host of an Origin or Referer header, if it has one."""
    if not value:
        return None
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}"


def _return_origin(request: Request) -> str:
    """Where to send the user once the sign-in finishes.

    ``RETRACT_FRONTEND_URL`` alone is not enough, and getting it wrong is
    invisible until a real login: a redirect that names a different **host** than
    the one the browser is on drops the session cookie (it is host-scoped), so a
    successful sign-in lands on a login page as if it had failed. A developer
    running on ``127.0.0.1:5175`` against a configured ``localhost:5177`` gets a
    dead port or a silent logout, neither of which names its cause.

    So the return target follows the request that started the sign-in, with two
    limits that keep it from becoming an open redirect:

    * only a configured origin — ``RETRACT_FRONTEND_URL`` or a ``RETRACT_CORS_ORIGINS``
      entry — is honoured anywhere;
    * outside production, a **loopback** origin is honoured too, since it can only
      ever point back at the developer's own machine, and that is precisely the
      case a single configured constant cannot express.

    Anything else falls back to the configured URL.
    """
    settings = get_settings()
    configured = _origin_of(settings.frontend_url)
    candidates = [
        _origin_of(request.headers.get("origin")),
        _origin_of(request.headers.get("referer")),
    ]
    allowed = {configured} | {_origin_of(o) for o in settings.cors_origin_list}
    for candidate in candidates:
        if candidate is None:
            continue
        if candidate in allowed:
            return candidate
        if not settings.is_production and is_loopback(urlsplit(candidate).hostname):
            return candidate
    return settings.frontend_url


def _aware(value: datetime) -> datetime:
    """Read a stored timestamp as UTC.

    The datetime columns are timezone-naive, so a value read back has no tzinfo and
    cannot be compared to an aware `utcnow()` — which raises rather than returning a
    wrong answer, but only once a real value exists to compare.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _with_query(base_url: str, **params: str) -> str:
    """A URL with query parameters added, preserving any it already carries.

    Built with urlsplit rather than string concatenation: the configured frontend
    URL may or may not carry a path, a trailing slash, or an existing query, and all
    three have to survive.
    """
    parts = urlsplit(base_url)
    added = urlencode(params)
    query = f"{parts.query}&{added}" if parts.query else added
    return urlunsplit(parts._replace(query=query))


def _with_error(frontend_url: str, code: str) -> str:
    """A frontend URL carrying an auth_error code."""
    return _with_query(frontend_url, auth_error=code)


def _auth_failure(request: Request, code: str, return_to: str | None = None) -> RedirectResponse:
    """Report a failed sign-in: back to the app for a browser, JSON otherwise.

    The JSON path raises rather than returning, so this always hands back a
    redirect when it returns at all. ``return_to`` is the origin the sign-in
    started from, so the user is put back where they were rather than wherever a
    configured constant happens to point.
    """
    detail = _AUTH_ERROR_MESSAGES.get(code, "Sign-in failed")
    logger.warning("github oauth failed: %s", detail)
    if not _wants_redirect(request):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=code)
    return RedirectResponse(_with_error(return_to or _return_origin(request), code))


def _set_session_cookie(response: Response, user: User) -> None:
    settings = get_settings()
    token = create_access_token(user.id, user.token_version)
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


def _send_verification_email(db: Session, user: User) -> None:
    """Issue a fresh verification link for this account and email it.

    Only the SHA-256 of the token is stored, so a database leak does not yield a
    set of working links. Delivery is best-effort (see app/mailer.py).
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
        # The link points at the API through the frontend's own origin: the dev server
        # and the production nginx both proxy /api, so one URL works in both and the
        # verification request stays same-origin with the app.
        link = _with_query(f"{settings.frontend_url}/api/auth/verify-email", token=raw)
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
    _send_verification_email(db, user)
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


def _primary_verified_email(access_token: str) -> str | None:
    """The account's primary verified email address, or ``None``.

    Only ``verified`` addresses are returned: attaching a GitHub identity to an
    account on the strength of an unverified address would be account takeover
    with extra steps. ``None`` is a normal outcome and never fails the sign-in —
    an organisation may forbid reading member emails (403), and a user may have
    none, and both simply leave the account GitHub-only as it was before.

    A refusal is logged, though, and deliberately not swallowed. ``None`` also
    results from a misconfigured OAuth app (a GitHub App without the Email
    addresses permission answers 403), and that failure is invisible in the
    product: sign-in succeeds and merely fails to reach the email account, which
    looks exactly like the "two empty dashboards" bug it was meant to fix.
    """
    try:
        response = httpx.get(
            "https://api.github.com/user/emails",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            timeout=15.0,
        )
    except httpx.HTTPError:
        logger.warning("github oauth: could not reach /user/emails; signing in without email")
        return None
    if response.status_code != 200:
        logger.warning(
            "github oauth: /user/emails returned %s; account linking is disabled for this "
            "sign-in. If this is every sign-in, the OAuth app lacks the email scope/permission.",
            response.status_code,
        )
        return None
    try:
        entries = response.json()
    except ValueError:
        logger.warning("github oauth: /user/emails returned a non-JSON body; ignoring it")
        return None
    if not isinstance(entries, list):
        return None
    verified = [
        e
        for e in entries
        if isinstance(e, dict) and e.get("verified") and isinstance(e.get("email"), str)
    ]
    for entry in verified:
        if entry.get("primary"):
            return entry["email"].strip().lower() or None
    return verified[0]["email"].strip().lower() or None if verified else None


def _resolve_github_account(db: Session, github_id: int, login: str, email: str | None) -> User:
    """The account this GitHub identity belongs to, creating one if it is new.

    Three rules, each excluding a way this could hand someone else's account to
    someone else:

    1. a known ``github_id`` is the same person, by definition;
    2. a verified email may attach, but only to an account whose **own** address was
       verified, that has **no** GitHub identity of its own (a different
       ``github_id`` means that account already belongs to somebody) and that has a
       password — a password-less account is a dev-bypass leftover, and silently
       adopting one would turn a shared demo login into a real person's identity;
    3. no password and no email is never enough.

    Rule 2's verification requirement is the one that took a second pass. GitHub
    reporting the address as verified says the *GitHub* account controls it; it says
    nothing about whether the local account does. Registering an address needs no
    proof at all, so anyone could pre-register a victim's email and then have the
    victim's GitHub identity attached to the attacker's password-bearing row. An
    account may only be claimed by an address it has itself proven.

    When the address is already held by an account that cannot be adopted, the
    new user is created **without** it. Storing it would violate the unique index
    on ``users.email`` and turn a sign-in into a 500; the GitHub identity is
    still recorded, and the person can link the address deliberately later.
    """
    existing = db.scalar(select(User).where(User.github_id == github_id))
    if existing is not None:
        return existing

    candidate = db.scalar(select(User).where(User.email == email)) if email else None
    if (
        candidate is not None
        and candidate.email_verified
        and candidate.github_id is None
        and candidate.password_hash
    ):
        # Attaching. The login and email stay as they are: they are the account's
        # own identity, and overwriting either would rename a record the user
        # already knows.
        candidate.github_id = github_id
        db.commit()
        return candidate

    email_taken = candidate is not None
    if email_taken:
        logger.warning(
            "github oauth: %s is already held by another account; "
            "creating a GitHub-only account without the address",
            email,
        )
    user = User(
        github_id=github_id,
        login=_unique_login(db, login),
        email=None if email_taken else email,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


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
    _send_verification_email(db, user)
    return JSONResponse({"ok": True, "already_verified": False})


@router.post("/eve-token", response_model=EveTokenOut)
def eve_token(user: User = Depends(get_current_user)) -> EveTokenOut:
    """Exchange the authenticated session for a short-lived eve agent token."""
    return EveTokenOut(token=create_eve_token(user.id), expires_in=EVE_TOKEN_TTL_SECONDS)
