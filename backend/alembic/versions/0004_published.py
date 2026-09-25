"""add published flag and verification/approval indexes

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-25

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "analyses",
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_findings_status", "findings", ["status"])
    op.create_index("ix_findings_severity", "findings", ["severity"])


def downgrade() -> None:
    op.drop_index("ix_findings_severity", table_name="findings")
    op.drop_index("ix_findings_status", table_name="findings")
    op.drop_column("analyses", "published")
