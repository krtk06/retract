"""Agent session mapping, idempotent usage intake, and monthly budgets."""

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.agent_usage import budget_snapshot, current_period, record_usage
from app.config import get_settings
from app.db import get_session_factory
from app.models import AgentUsage, AgentUsageEvent, User

settings = get_settings()


def _service_headers() -> dict[str, str]:
    return {"X-Agent-Token": settings.agent_token}


def _me(client: TestClient) -> int:
    response = client.get("/api/auth/me")
    assert response.status_code == 200, response.text
    return int(response.json()["id"])


def _login(client: TestClient, prefix: str) -> int:
    suffix = uuid.uuid4().hex[:8]
    response = client.get("/api/auth/dev/login", params={"login": f"{prefix}-{suffix}"})
    assert response.status_code == 200, response.text
    return _me(client)


def _map(client: TestClient, session_id: str, user_id: int) -> None:
    response = client.post(
        "/api/agent/sessions",
        json={"session_id": session_id, "user_id": user_id},
        headers=_service_headers(),
    )
    assert response.status_code == 200, response.text


def _usage(
    client: TestClient,
    *,
    session_id: str,
    key: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float = 0.0,
):
    return client.post(
        "/api/agent/usage",
        json={
            "idempotency_key": key,
            "session_id": session_id,
            "model": "deepseek-v4.1-flash",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
        },
        headers=_service_headers(),
    )


def test_agent_routes_require_the_service_token(auth_client: TestClient) -> None:
    user_id = _me(auth_client)
    path = f"/api/agent/budget?user_id={user_id}"

    # A browser session is not a service credential: budget data is account-scoped.
    assert auth_client.get(path).status_code == 401
    assert auth_client.get(path, headers={"X-Agent-Token": "wrong"}).status_code == 401
    assert auth_client.get(path, headers=_service_headers()).status_code == 200


def test_session_mapping_requires_an_existing_account(client: TestClient) -> None:
    response = client.post(
        "/api/agent/sessions",
        json={"session_id": f"s-{uuid.uuid4().hex}", "user_id": 10_000_000},
        headers=_service_headers(),
    )
    assert response.status_code == 404


def test_usage_is_recorded_once_and_drives_the_budget(auth_client: TestClient) -> None:
    user_id = _me(auth_client)
    session_id = f"s-{uuid.uuid4().hex}"
    key = f"model-{uuid.uuid4().hex}"
    _map(auth_client, session_id, user_id)

    first = _usage(
        auth_client,
        session_id=session_id,
        key=key,
        input_tokens=1_000_000,
        output_tokens=2_000_000,
        cost_usd=0.75,
    )
    assert first.status_code == 200, first.text
    assert first.json() == {"recorded": True}

    replay = _usage(
        auth_client,
        session_id=session_id,
        key=key,
        input_tokens=1_000_000,
        output_tokens=2_000_000,
        cost_usd=0.75,
    )
    assert replay.json() == {"recorded": False}

    by_user = auth_client.get(
        "/api/agent/budget", params={"user_id": user_id}, headers=_service_headers()
    )
    assert by_user.status_code == 200, by_user.text
    budget = by_user.json()
    # Dev-login accounts are created with the $2 demo budget; the standard account
    # budget must not leak into them.
    assert budget["user_budget_usd"] == 2.0
    assert budget["user_used_usd"] == 0.75
    assert budget["used_usd"] == 0.75
    assert budget["remaining_usd"] == 1.25
    assert budget["input_tokens"] == 1_000_000
    assert budget["output_tokens"] == 2_000_000

    session = get_session_factory()()
    try:
        aggregate = session.scalar(
            select(AgentUsage).where(
                AgentUsage.user_id == user_id,
                AgentUsage.period == current_period(),
            )
        )
        assert aggregate is not None
        assert aggregate.input_tokens == 1_000_000
        assert aggregate.output_tokens == 2_000_000
        assert aggregate.cost_usd == 0.75
        assert session.scalar(select(func.count()).select_from(AgentUsageEvent)) >= 1
    finally:
        session.close()


def test_the_global_budget_can_bind_before_the_account_budget(client: TestClient) -> None:
    first_user = _login(client, "global-first")
    second_user = _login(client, "global-second")

    first_session = f"s-{uuid.uuid4().hex}"
    second_session = f"s-{uuid.uuid4().hex}"
    _map(client, first_session, first_user)
    _map(client, second_session, second_user)

    assert _usage(
        client, session_id=first_session, key=f"u-{uuid.uuid4().hex}", cost_usd=1.0
    ).json() == {"recorded": True}
    assert _usage(
        client, session_id=second_session, key=f"u-{uuid.uuid4().hex}", cost_usd=1.0
    ).json() == {"recorded": True}

    budget = client.get(
        "/api/agent/budget", params={"user_id": first_user}, headers=_service_headers()
    ).json()
    assert budget["user_used_usd"] == 1.0
    assert budget["global_used_usd"] >= 2.0
    # The lower of the two remaining amounts is what the agent may spend.
    assert budget["remaining_usd"] == 0.0


def test_usage_for_an_unknown_session_is_refused(client: TestClient) -> None:
    response = _usage(client, session_id=f"s-{uuid.uuid4().hex}", key=f"u-{uuid.uuid4().hex}")
    assert response.status_code == 404
    assert "Unknown agent session" in response.json()["detail"]


def test_negative_usage_is_rejected(client: TestClient) -> None:
    user_id = _login(client, "negative")
    session_id = f"s-{uuid.uuid4().hex}"
    _map(client, session_id, user_id)
    response = client.post(
        "/api/agent/usage",
        json={
            "idempotency_key": f"u-{uuid.uuid4().hex}",
            "session_id": session_id,
            "model": "m",
            "input_tokens": -1,
            "cost_usd": -0.01,
        },
        headers=_service_headers(),
    )
    assert response.status_code == 422


def test_a_new_utc_month_starts_at_zero_and_the_old_month_remains() -> None:
    session = get_session_factory()()
    try:
        user = User(github_id=None, login=f"period-{uuid.uuid4().hex}", is_dev=True)
        session.add(user)
        session.commit()
        session.refresh(user)

        key = f"u-{uuid.uuid4().hex}"
        assert record_usage(
            session,
            idempotency_key=key,
            user_id=user.id,
            session_id="s-period",
            model="m",
            input_tokens=10,
            output_tokens=20,
            cost_usd=1.5,
            period="2025-01",
        )
        record_usage(
            session,
            idempotency_key=f"u-{uuid.uuid4().hex}",
            user_id=user.id,
            session_id="s-period",
            model="m",
            input_tokens=1,
            output_tokens=2,
            cost_usd=0.25,
        )
        session.commit()

        snapshot = budget_snapshot(session, user, settings)
        assert snapshot["period"] == current_period()
        assert snapshot["input_tokens"] == 1
        assert snapshot["output_tokens"] == 2
        assert snapshot["user_used_usd"] == 0.25

        old = session.scalar(
            select(AgentUsage).where(AgentUsage.user_id == user.id, AgentUsage.period == "2025-01")
        )
        assert old is not None
        assert old.cost_usd == 1.5
    finally:
        session.close()


def test_an_existing_dev_account_is_repaired_to_the_demo_budget(client: TestClient) -> None:
    """Accounts predating the budget column carry the standard default; dev login fixes it."""
    login = f"legacy-{uuid.uuid4().hex}"
    session = get_session_factory()()
    try:
        user = User(github_id=None, login=login, is_dev=True)
        session.add(user)
        session.commit()
        session.refresh(user)
        user_id = user.id
        assert user.llm_monthly_budget_usd == 10.0
    finally:
        session.close()

    response = client.get("/api/auth/dev/login", params={"login": login})
    assert response.status_code == 200, response.text

    budget = client.get(
        "/api/agent/budget", params={"user_id": user_id}, headers=_service_headers()
    ).json()
    assert budget["user_budget_usd"] == 2.0


def test_current_period_is_evaluated_in_utc() -> None:
    # 2026-01-31T23:30 in UTC is already February in a positive-offset zone; the
    # ledger must not roll over early for a caller whose clock is elsewhere.
    assert current_period(datetime(2026, 1, 31, 23, 30, tzinfo=UTC)) == "2026-01"
    assert current_period(datetime(2026, 2, 1, 0, 30, tzinfo=UTC)) == "2026-02"
