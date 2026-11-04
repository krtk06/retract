"""Client-IP resolution and the reuseable rate-limit primitives.

The limits themselves are only as good as the identity they are charged to. These
tests pin the proxy decision: a header from an untrusted peer is ignored, and a
header appended by a trusted proxy yields the browser address rather than the
proxy's.
"""

from collections.abc import Generator

import fakeredis
import pytest
import redis
from fastapi import HTTPException
from starlette.requests import Request

from app import rate_limit
from app.config import get_settings

PROXY_NETWORK = "172.28.0.0/16,127.0.0.1/32"


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> Generator[fakeredis.FakeRedis, None, None]:
    """An in-memory limiter store, with the limiter switched on for this test."""
    fake = fakeredis.FakeRedis(decode_responses=True)
    settings = get_settings().model_copy(
        update={
            "rate_limit_enabled": True,
            "trusted_proxy_cidrs": PROXY_NETWORK,
            "dev_repo_per_ip_ttl_seconds": 86_400,
        }
    )
    monkeypatch.setattr(rate_limit, "_redis", lambda: fake)
    monkeypatch.setattr(rate_limit, "get_settings", lambda: settings)
    yield fake


def _request(host: str, forwarded: str | None = None) -> Request:
    headers = []
    if forwarded is not None:
        headers.append((b"x-forwarded-for", forwarded.encode("latin1")))
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": headers,
            "client": (host, 50_000),
            "server": ("testserver", 80),
        }
    )


def test_an_untrusted_peer_cannot_choose_its_bucket_with_a_header(store) -> None:
    """Otherwise every request could pick a fresh bucket and evade every limit."""
    request = _request("198.51.100.9", forwarded="203.0.113.7")
    assert rate_limit.client_ip(request) == "198.51.100.9"


def test_a_trusted_proxy_supplies_the_browser_address(store) -> None:
    request = _request("172.28.0.5", forwarded="198.51.100.9")
    assert rate_limit.client_ip(request) == "198.51.100.9"


def test_the_rightmost_untrusted_hop_wins_over_a_client_supplied_prefix(store) -> None:
    """The trusted proxy appends the address it saw; a left-hand value is attacker text."""
    request = _request("172.28.0.5", forwarded="203.0.113.7, 198.51.100.9, 172.28.0.4")
    assert rate_limit.client_ip(request) == "198.51.100.9"


def test_an_all_trusted_chain_falls_back_to_its_leftmost_hop(store) -> None:
    request = _request("172.28.0.5", forwarded="172.28.0.4, 172.28.0.6")
    assert rate_limit.client_ip(request) == "172.28.0.4"


def test_forwarded_entries_tolerate_ports_and_ipv6_brackets(store) -> None:
    request = _request("172.28.0.5", forwarded="[2001:db8::1]:443, 172.28.0.4")
    assert rate_limit.client_ip(request) == "2001:db8::1"


def test_a_malformed_proxy_cidr_refuses_to_start() -> None:
    settings = get_settings().model_copy(update={"trusted_proxy_cidrs": "not-a-network"})
    with pytest.raises(ValueError, match="not an IP address or CIDR"):
        _ = settings.trusted_proxy_network_list


def test_dev_accounts_may_analyze_one_repository_per_ip(store) -> None:
    first = _request("198.51.100.20")
    rate_limit.claim_dev_repo(first, 1)
    # Re-analyzing the same repository remains allowed.
    rate_limit.claim_dev_repo(first, 1)

    with pytest.raises(HTTPException) as excinfo:
        rate_limit.claim_dev_repo(first, 2)
    assert excinfo.value.status_code == 429
    assert "one repository per IP" in excinfo.value.detail
    assert int(excinfo.value.headers["Retry-After"]) >= 1

    # A different address has its own budget.
    rate_limit.claim_dev_repo(_request("198.51.100.21"), 2)


def test_the_dev_repository_rule_fails_open_when_redis_is_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings().model_copy(
        update={"rate_limit_enabled": True, "trusted_proxy_cidrs": PROXY_NETWORK}
    )

    def boom() -> None:
        raise redis.RedisError("down")

    monkeypatch.setattr(rate_limit, "get_settings", lambda: settings)
    monkeypatch.setattr(rate_limit, "_redis", boom)

    # No exception, same availability posture as the limiter itself.
    rate_limit.claim_dev_repo(_request("198.51.100.30"), 1)
    rate_limit.claim_dev_repo(_request("198.51.100.30"), 2)


def test_the_dev_repository_rule_is_off_when_the_limiter_is_off(
    store, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings().model_copy(
        update={
            "rate_limit_enabled": False,
            "trusted_proxy_cidrs": PROXY_NETWORK,
            "dev_repo_per_ip_ttl_seconds": 86_400,
        }
    )
    monkeypatch.setattr(rate_limit, "get_settings", lambda: settings)

    request = _request("198.51.100.40")
    rate_limit.claim_dev_repo(request, 1)
    rate_limit.claim_dev_repo(request, 2)
    assert store.keys("devlogin:repo:*") == []
