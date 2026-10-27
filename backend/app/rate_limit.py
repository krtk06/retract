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

import ipaddress
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


def _forwarded_host(value: str) -> str:
    """Extract a host from one X-Forwarded-For entry, tolerating a port or brackets."""
    value = value.strip()
    if not value:
        return ""
    if value.startswith("["):
        end = value.find("]")
        return value[1:end] if end != -1 else value
    # A bare IPv6 address has several colons and no port; do not split it.
    if value.count(":") > 1:
        return value
    return value.partition(":")[0]


def _is_trusted_proxy(
    host: str, networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network]
) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(address.version == network.version and address in network for network in networks)


def client_ip(request: Request) -> str:
    """The address a rate limit should be charged to.

    Uvicorn's ``--proxy-headers`` rewrites ``request.client`` only when the direct
    peer is in ``--forwarded-allow-ips``. This function repeats that decision for
    callers that reach it without the middleware (tests, scripts) and for the
    application's own trust list, so both layers agree.

    A forwarded header from an untrusted peer is ignored: otherwise any client
    could choose a fresh bucket per request by sending ``X-Forwarded-For``. Behind
    a trusted proxy, walk the header right-to-left and take the first untrusted
    address — the rightmost hop is the one the trusted proxy itself appended, so a
    client-supplied prefix cannot spoof it.
    """
    peer = request.client.host if request.client else "unknown"
    networks = get_settings().trusted_proxy_network_list
    if not _is_trusted_proxy(peer, networks):
        return peer

    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return peer

    hosts = [host for host in (_forwarded_host(part) for part in forwarded.split(",")) if host]
    for host in reversed(hosts):
        if not _is_trusted_proxy(host, networks):
            return host
    # Every hop was a trusted proxy: the leftmost is the closest thing to a client.
    return hosts[0] if hosts else peer


def enforce(
    request: Request, bucket: str, *, limit: int, window_seconds: int, who: str | None = None
) -> None:
    """Allow the request, or raise 429 once ``limit`` is passed within the window.

    ``who`` defaults to ``client_ip(request)``, which uses the real client behind
    trusted proxies rather than the proxy address. A caller behind a shared NAT
    shares a budget, which is the standard and acceptable trade for not trusting a
    spoofable header. Only proxies in ``RETRACT_TRUSTED_PROXY_CIDRS`` may set it.

    A Redis outage fails **open** with a warning. Failing closed would turn a cache
    outage into "nobody can sign in" — a self-inflicted denial of service, and the
    limiter is not the thing keeping the accounts safe.
    """
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return

    identity = who or client_ip(request)
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


def claim_dev_repo(request: Request, repo_id: int) -> None:
    """Allow a dev account to analyze one repository per client IP per window.

    Re-analyzing the same repository is allowed. The key stores the repository id,
    and ``SET NX`` makes the first claim atomic. A second repository raises 429 with
    the remaining TTL so the caller knows when the window resets.

    This is a development convenience, not tenant isolation: shared NATs share the
    budget, and a Redis outage fails open (with a warning) exactly as the rate
    limiter does. A real account is never subject to it.
    """
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return

    identity = client_ip(request)
    key = f"devlogin:repo:{identity}"
    ttl = settings.dev_repo_per_ip_ttl_seconds
    try:
        store = _redis()
        # Two attempts cover the only race: the key expiring between a failed SET
        # and the GET that explains why it failed. A third attempt cannot help.
        for _ in range(2):
            if store.set(key, str(repo_id), nx=True, ex=ttl):
                return
            current = store.get(key)
            if current is None:
                continue
            if str(current) == str(repo_id):
                return
            retry_after = max(int(store.ttl(key)), 1)
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Dev login is limited to one repository per IP address. "
                    "Re-analyzing the same repository is allowed."
                ),
                headers={"Retry-After": str(retry_after)},
            )
    except HTTPException:
        raise
    except redis.RedisError as exc:
        logger.warning(
            "dev one-repository rule unavailable; allowing the request: %s",
            exc,
            exc_info=True,
        )
