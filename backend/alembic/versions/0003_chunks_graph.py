"""chunks (pgvector embeddings) and graph snapshots

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-24

"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 384


def upgrade() -> None:
    # pgvector is present in the deployment image and on supported clusters.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "analysis_id",
            sa.Integer(),
            sa.ForeignKey("analyses.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("symbol_id", sa.Integer(), sa.ForeignKey("symbols.id"), nullable=True),
        sa.Column("file_path", sa.String(), nullable=False, index=True),
        sa.Column("symbol_name", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=False),
        sa.Column("line_end", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
    )
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops)"
    )

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
    op.drop_index("ix_chunks_embedding_hnsw", table_name="chunks")
    op.drop_table("chunks")
