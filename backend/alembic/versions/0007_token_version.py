"""session revocation via a user token version

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-13

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Existing rows predate the column; 0 is the value their tokens are read as, so they
# keep their sessions until the first logout bumps them. `server_default` is what
# makes the column NOT NULL on a populated table in one step.
DEFAULT = "0"


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default=DEFAULT),
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")
