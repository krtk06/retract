"""graph snapshots

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-24

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:

    op.create_table(
        "graph_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "analysis_id",
            sa.Integer(),
            sa.ForeignKey("analyses.id"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("symbol_count", sa.Integer(), nullable=False),
        sa.Column("edge_count", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("built_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("graph_snapshots")
