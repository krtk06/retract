"""Password hashing plus JWT helpers for session and eve-agent tokens."""

from datetime import UTC, datetime, timedelta
from typing import Any, NamedTuple

import bcrypt
import jwt

from app.config import get_settings

EVE_TOKEN_ISSUER = "ai-intel"
EVE_TOKEN_AUDIENCE = "eve-agent"
EVE_TOKEN_TTL_SECONDS = 300

# `jwt.decode` parses the token header as JSON *before* it verifies anything, and a
# header nested deeply enough makes CPython's JSON decoder raise `RecursionError` —
# a `RuntimeError`, not a `PyJWTError`. PyJWT 2.13.0 let that escape; 2.14.0
# translates it, but the catch is kept here so a downgrade cannot silently turn a
# crafted cookie into an unhandled 500 on an unauthenticated request.
_DECODE_FAILURES = (jwt.PyJWTError, KeyError, ValueError, RecursionError)


class AccessClaims(NamedTuple):
    """What a session token asserts: who, and which generation of their session.

    The version is what makes logout mean something. A JWT is self-contained, so
    without it a copied cookie stays valid for its full lifetime and no server-side
    action can revoke it; bumping the user's version invalidates every token minted
    before the bump.
    """

    user_id: int
    token_version: int


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time credential check; malformed hashes simply fail closed."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        return False


def create_access_token(user_id: int, token_version: int = 0) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "ver": int(token_version),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.jwt_ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> AccessClaims | None:
    """Return the claims of a valid session token, else None.

    A token minted before ``ver`` existed carries no claim; it is read as version 0
    so tokens issued by an older build keep working across a deploy, and are
    revoked the moment that user's version is first bumped.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return AccessClaims(int(payload["sub"]), int(payload.get("ver", 0)))
    except _DECODE_FAILURES:
        return None


def create_eve_token(user_id: int) -> str:
    """Mint a short-lived token scoped to the eve agent's HTTP routes.

    The browser session cookie is httpOnly, so the frontend cannot present it to
    eve. This exchanges the authenticated session for a bearer token the eve
    channel verifies with ``jwtHmac`` (issuer + audience enforced).
    """
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iss": EVE_TOKEN_ISSUER,
        "aud": EVE_TOKEN_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=EVE_TOKEN_TTL_SECONDS)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_eve_token(token: str) -> dict[str, Any] | None:
    """Return the claims of a valid eve token, else None."""
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer=EVE_TOKEN_ISSUER,
            audience=EVE_TOKEN_AUDIENCE,
        )
    except _DECODE_FAILURES:
        return None
