"""Auth helpers: return origins, session cookies, GitHub account resolution, mail."""

import logging
from datetime import UTC, datetime
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx
from fastapi import HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings, is_loopback
from app.models import User
from app.security import create_access_token

logger = logging.getLogger(__name__)

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
