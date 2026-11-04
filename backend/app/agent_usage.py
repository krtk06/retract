"""Monthly LLM budget accounting and the idempotent usage ledger.

The agent is a separate service, so the API is the only place that can answer
"how much has this account spent this month?" — and the only place that can make
the answer durable. Two rules keep that answer honest:

* the audit event is keyed by the instrumentation event's idempotency key, so a
  retry cannot charge twice; and
* the aggregate is updated in the same transaction as the event, using an upsert
  rather than read-modify-write, so concurrent model calls cannot lose an update.

The period is a UTC calendar month. A new month starts at zero without deleting
the prior month's rows, which keeps the history auditable.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AgentSession, AgentUsage, AgentUsageEvent, User


def current_period(now: datetime | None = None) -> str:
    """The UTC ``YYYY-MM`` period for ``now`` (default: this instant)."""
    moment = now or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).strftime("%Y-%m")


def _dialect_name(db: Session) -> str:
    return db.get_bind().dialect.name


def _sums(db: Session, period: str, user_id: int | None = None) -> tuple[int, int, float]:
    """Return (input tokens, output tokens, cost) for a period, globally or per user."""
    stmt = select(
        func.coalesce(func.sum(AgentUsage.input_tokens), 0),
        func.coalesce(func.sum(AgentUsage.output_tokens), 0),
        func.coalesce(func.sum(AgentUsage.cost_usd), 0.0),
    ).where(AgentUsage.period == period)
    if user_id is not None:
        stmt = stmt.where(AgentUsage.user_id == user_id)
    row = db.execute(stmt).one()
    return int(row[0]), int(row[1]), float(row[2])


def upsert_session(
    db: Session, *, session_id: str, user_id: int, now: datetime | None = None
) -> None:
    """Point an eve session at the account whose budget it spends.

    The channel calls this on every turn, including a child subagent session, and
    a later caller can continue an existing session, so this is an upsert rather
    than an insert. ``first_seen_at`` is preserved on update.
    """
    moment = now or datetime.now(UTC)
    values = {
        "session_id": session_id,
        "user_id": user_id,
        "first_seen_at": moment,
        "last_seen_at": moment,
    }
    dialect = _dialect_name(db)

    stmt: Any
    if dialect == "postgresql":
        stmt = pg_insert(AgentSession).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["session_id"],
            set_={"user_id": stmt.excluded.user_id, "last_seen_at": stmt.excluded.last_seen_at},
        )
    elif dialect == "sqlite":
        stmt = sqlite_insert(AgentSession).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["session_id"],
            set_={"user_id": stmt.excluded.user_id, "last_seen_at": stmt.excluded.last_seen_at},
        )
    else:  # pragma: no cover - only SQLite (tests) and PostgreSQL (deployments) are supported
        session = db.get(AgentSession, session_id)
        if session is None:
            db.add(AgentSession(**values))
        else:
            session.user_id = user_id
            session.last_seen_at = moment
        return

    db.execute(stmt)


def record_usage(
    db: Session,
    *,
    idempotency_key: str,
    user_id: int,
    session_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    period: str | None = None,
) -> bool:
    """Record one model call and update its monthly aggregate exactly once.

    Returns True when the event was new, False when the idempotency key had already
    been seen. The caller must have validated non-negative values.
    """
    period = period or current_period()
    dialect = _dialect_name(db)

    event_values = {
        "idempotency_key": idempotency_key,
        "user_id": user_id,
        "session_id": session_id,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
    }
    aggregate_values = {
        "user_id": user_id,
        "period": period,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
    }

    event_stmt: Any
    aggregate_stmt: Any
    if dialect == "postgresql":
        event_stmt = (
            pg_insert(AgentUsageEvent)
            .values(**event_values)
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
        )
        aggregate_stmt = pg_insert(AgentUsage).values(**aggregate_values)
        aggregate_stmt = aggregate_stmt.on_conflict_do_update(
            index_elements=["user_id", "period"],
            set_={
                "input_tokens": AgentUsage.input_tokens + aggregate_stmt.excluded.input_tokens,
                "output_tokens": AgentUsage.output_tokens + aggregate_stmt.excluded.output_tokens,
                "cost_usd": AgentUsage.cost_usd + aggregate_stmt.excluded.cost_usd,
            },
        )
    elif dialect == "sqlite":
        event_stmt = (
            sqlite_insert(AgentUsageEvent)
            .values(**event_values)
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
        )
        aggregate_stmt = sqlite_insert(AgentUsage).values(**aggregate_values)
        aggregate_stmt = aggregate_stmt.on_conflict_do_update(
            index_elements=["user_id", "period"],
            set_={
                "input_tokens": AgentUsage.input_tokens + aggregate_stmt.excluded.input_tokens,
                "output_tokens": AgentUsage.output_tokens + aggregate_stmt.excluded.output_tokens,
                "cost_usd": AgentUsage.cost_usd + aggregate_stmt.excluded.cost_usd,
            },
        )
    else:  # pragma: no cover - only SQLite (tests) and PostgreSQL (deployments) are supported
        existing = db.get(AgentUsageEvent, idempotency_key)
        if existing is not None:
            return False
        db.add(AgentUsageEvent(**event_values))
        aggregate = db.scalar(
            select(AgentUsage).where(AgentUsage.user_id == user_id, AgentUsage.period == period)
        )
        if aggregate is None:
            aggregate = AgentUsage(**aggregate_values)
            db.add(aggregate)
        else:
            aggregate.input_tokens += input_tokens
            aggregate.output_tokens += output_tokens
            aggregate.cost_usd += cost_usd
        return True

    result = db.execute(event_stmt)
    if (getattr(result, "rowcount", 0) or 0) == 0:
        return False

    db.execute(aggregate_stmt)
    return True


def budget_snapshot(
    db: Session, user: User, settings: Settings, now: datetime | None = None
) -> dict[str, object]:
    """The remaining budget the agent checks before dispatching a turn.

    ``remaining_usd`` is the lower of the account's remaining monthly budget and the
    deployment-wide remaining budget. ``remaining_tokens`` is present only when the
    token fallback is configured; it is the account's ceiling, not a global one.
    """
    period = current_period(now)
    user_input, user_output, user_used = _sums(db, period, user.id)
    _, _, global_used = _sums(db, period)

    user_budget = float(user.llm_monthly_budget_usd)
    global_budget = float(settings.global_llm_budget_usd)
    user_remaining = max(user_budget - user_used, 0.0)
    global_remaining = max(global_budget - global_used, 0.0)
    remaining = min(user_remaining, global_remaining)

    token_budget = settings.llm_monthly_token_budget_tokens
    used_tokens = user_input + user_output
    remaining_tokens = max(token_budget - used_tokens, 0) if token_budget else None

    return {
        "period": period,
        "user_budget_usd": round(user_budget, 6),
        "global_budget_usd": round(global_budget, 6),
        "used_usd": round(user_used, 6),
        "user_used_usd": round(user_used, 6),
        "global_used_usd": round(global_used, 6),
        "remaining_usd": round(remaining, 6),
        "input_tokens": user_input,
        "output_tokens": user_output,
        "used_tokens": used_tokens,
        "token_budget": token_budget,
        "remaining_tokens": remaining_tokens,
    }
