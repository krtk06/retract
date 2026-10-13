"""private repositories, and a shared pool for development accounts

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-13

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- who is a development account ------------------------------------------
    # The bypass mints accounts with no GitHub identity and no password; that is
    # also how the old rules already described one, so the backfill is exact.
    op.add_column(
        "users", sa.Column("is_dev", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.execute("UPDATE users SET is_dev = true WHERE github_id IS NULL AND password_hash IS NULL")

    # --- one repository row per (creator, url) ---------------------------------
    op.add_column(
        "repositories",
        sa.Column("is_shared", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Existing rows keep their grants and become private copies owned by the account
    # that created them. They were shared by URL before, but that is the behaviour
    # being removed; leaving them private is the safe direction, and the development
    # accounts that relied on the pool will simply add the URL again.
    op.drop_constraint("repositories_url_key", "repositories", type_="unique")
    op.create_index(
        "uq_repositories_shared_url",
        "repositories",
        ["url"],
        unique=True,
        postgresql_where=sa.text("is_shared"),
    )
    op.create_index(
        "uq_repositories_owner_url",
        "repositories",
        ["added_by", "url"],
        unique=True,
        postgresql_where=sa.text("NOT is_shared"),
    )


def downgrade() -> None:
    op.drop_index("uq_repositories_owner_url", table_name="repositories")
    op.drop_index("uq_repositories_shared_url", table_name="repositories")
    # Collapsing back to a global unique url can fail if two users now hold private
    # copies of one URL, which is the whole point of the change. The migration is
    # explicit about that rather than failing with an opaque constraint error.
    duplicates = (
        op.get_bind()
        .execute(sa.text("SELECT url FROM repositories GROUP BY url HAVING count(*) > 1 LIMIT 5"))
        .scalars()
        .all()
    )
    if duplicates:
        raise RuntimeError(
            "cannot downgrade: these URLs now have more than one private copy, so a "
            f"global unique index cannot be rebuilt: {', '.join(duplicates)}"
        )
    op.create_unique_constraint("repositories_url_key", "repositories", ["url"])
    op.drop_column("repositories", "is_shared")
    op.drop_column("users", "is_dev")
