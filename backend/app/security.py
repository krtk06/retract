"""Password hashing plus JWT helpers for session and eve-agent tokens."""

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.config import get_settings

EVE_TOKEN_ISSUER = "ai-intel"
EVE_TOKEN_AUDIENCE = "eve-agent"
EVE_TOKEN_TTL_SECONDS = 300


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time credential check; malformed hashes simply fail closed."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        return False


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
