"""agent usage ledger and per-account LLM budgets

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-27

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing accounts keep the standard budget. The seed and the dev-login path
    # write the demo value explicitly for the accounts that get one.
    op.add_column(
        "users",
        sa.Column(
            "llm_monthly_budget_usd",
            sa.Float(),
            nullable=False,
            server_default=sa.text("10"),
        ),
    )

    op.create_table(
        "agent_sessions",
        sa.Column("session_id", sa.String(length=200), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_agent_sessions_user_id", "agent_sessions", ["user_id"])

    op.create_table(
        "agent_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "period", name="uq_agent_usage_user_period"),
    )
    op.create_index("ix_agent_usage_user_id", "agent_usage", ["user_id"])
    op.create_index("ix_agent_usage_period", "agent_usage", ["period"])

    op.create_table(
        "agent_usage_events",
        sa.Column("idempotency_key", sa.String(length=200), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_id", sa.String(length=200), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False, server_default="unknown"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_agent_usage_events_user_id", "agent_usage_events", ["user_id"])
    op.create_index("ix_agent_usage_events_session_id", "agent_usage_events", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_usage_events_session_id", table_name="agent_usage_events")
    op.drop_index("ix_agent_usage_events_user_id", table_name="agent_usage_events")
    op.drop_table("agent_usage_events")
    op.drop_index("ix_agent_usage_period", table_name="agent_usage")
    op.drop_index("ix_agent_usage_user_id", table_name="agent_usage")
    op.drop_table("agent_usage")
    op.drop_index("ix_agent_sessions_user_id", table_name="agent_sessions")
    op.drop_table("agent_sessions")
    op.drop_column("users", "llm_monthly_budget_usd")
