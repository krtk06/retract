"""JWT helpers for session tokens and the eve agent's scoped access token."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.config import get_settings

EVE_TOKEN_ISSUER = "ai-intel"
EVE_TOKEN_AUDIENCE = "eve-agent"
EVE_TOKEN_TTL_SECONDS = 300


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.jwt_ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> int | None:
    """Return user_id from a valid token, else None."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
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
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
