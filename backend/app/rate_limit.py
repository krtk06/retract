"""Fixed-window rate limiting, on the Redis the app already depends on.

Nothing here protects confidentiality; it protects *availability* and the cost
budget. The endpoints it guards are the ones an unauthenticated or authenticated
caller can make expensive: `register` and `login` each run a deliberately slow
bcrypt hash (~0.25s of CPU), and `analyze` fans a repository out across six tools
and a `git clone`. Without a limit, a single caller can spend the server's CPU or
starve the worker queue, and brute-forcing a password or enumerating addresses is
free.

A fixed window (count per key, expiring) is deliberately the simplest thing that
works: it needs no sorted sets, its memory is one key per caller, and its one
weakness — a burst can straddle a window boundary and admit up to 2x the limit at
the seam — is irrelevant at these thresholds.
"""

import logging

import redis
from fastapi import HTTPException, Request, status

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None


def _redis() -> redis.Redis:
    """The Redis client, created once. Tests monkeypatch this to inject fakeredis."""
    global _client
    if _client is None:
        _client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
    return _client


def enforce(
    request: Request, bucket: str, *, limit: int, window_seconds: int, who: str | None = None
) -> None:
    """Allow the request, or raise 429 once ``limit`` is passed within the window.

    ``who`` defaults to the client address. Uvicorn runs with ``--proxy-headers``
    in production, so that address is the real client behind nginx rather than the
    proxy; a caller behind a shared NAT shares a budget, which is the standard and
    acceptable trade for not trusting a spoofable header.

    A Redis outage fails **open** with a warning. Failing closed would turn a cache
    outage into "nobody can sign in" — a self-inflicted denial of service, and the
    limiter is not the thing keeping the accounts safe.
    """
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return

    identity = who or (request.client.host if request.client else "unknown")
    key = f"ratelimit:{bucket}:{identity}"
    try:
        store = _redis()
        count = store.incr(key)
        if count == 1:
            store.expire(key, window_seconds)
        if count > limit:
            retry_after = max(int(store.ttl(key)), 1)
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests — please slow down and try again shortly.",
                headers={"Retry-After": str(retry_after)},
            )
    except HTTPException:
        raise
    except redis.RedisError as exc:
        logger.warning("rate limiter unavailable; allowing the request: %s", exc, exc_info=True)
