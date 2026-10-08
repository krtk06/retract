"""email accounts and repository ownership

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-08

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column("users", sa.Column("email", sa.String(length=320), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "user_repositories",
        sa.Column("repo_id", sa.Integer(), sa.ForeignKey("repositories.id"), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
    )
    # Backfill ownership from the single-creator column so existing repos keep
    # their visibility. INSERT OR IGNORE (SQLite) / ON CONFLICT DO NOTHING (Post)
    # is idempotent if the migration ever re-runs on a repaired database.
    if bind.dialect.name == "postgresql":
        op.execute(
            "INSERT INTO user_repositories (repo_id, user_id) "
            "SELECT DISTINCT id, added_by FROM repositories ON CONFLICT DO NOTHING"
        )
    else:
        op.execute(
            "INSERT OR IGNORE INTO user_repositories (repo_id, user_id) "
            "SELECT DISTINCT id, added_by FROM repositories"
        )


def downgrade() -> None:
    op.drop_table("user_repositories")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_column("users", "password_hash")
    op.drop_column("users", "email")
