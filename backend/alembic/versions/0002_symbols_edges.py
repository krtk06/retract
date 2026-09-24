"""symbols/edges tables and analysis metrics columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-24

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

symbol_kind = sa.Enum(
    "module", "class", "function", "method", name="symbol_kind", native_enum=False
)
edge_kind = sa.Enum("imports", "calls", name="edge_kind", native_enum=False)


def upgrade() -> None:
    op.add_column("analyses", sa.Column("loc", sa.Integer(), nullable=True))
    op.add_column("analyses", sa.Column("score_json", postgresql.JSONB(), nullable=True))

    op.create_table(
        "symbols",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "analysis_id",
            sa.Integer(),
            sa.ForeignKey("analyses.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("file_path", sa.String(), nullable=False, index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("kind", symbol_kind, nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=False),
        sa.Column("line_end", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "analysis_id", "file_path", "name", "kind", "line_start", name="uq_symbol"
        ),
    )
    op.create_table(
        "edges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "analysis_id",
            sa.Integer(),
            sa.ForeignKey("analyses.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "src_symbol_id",
            sa.Integer(),
            sa.ForeignKey("symbols.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("dst_name", sa.String(), nullable=False),
        sa.Column(
            "dst_symbol_id",
            sa.Integer(),
            sa.ForeignKey("symbols.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("kind", edge_kind, nullable=False),
        sa.UniqueConstraint("src_symbol_id", "dst_name", "kind", name="uq_edge"),
    )


def downgrade() -> None:
    op.drop_table("edges")
    op.drop_table("symbols")
    op.drop_column("analyses", "score_json")
    op.drop_column("analyses", "loc")
