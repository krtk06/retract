"""Attach a GitHub identity to the account that owns a person's repositories.

Signing in with GitHub before account linking existed minted a fresh user, and
adding a repository and analysing it are fused into one UI action — so ownership
had to be moved with a script rather than through the app. This is that script.

It is dry-run by default; pass ``--apply`` to write. Every step is idempotent, so
re-running it after a partial failure is safe.

    scripts/link_github_account.py --github-id 141238194 \
        --email owner@example.com --move-from dev
        scripts/link_github_account.py ... --apply

Three refusals, mirroring ``auth._resolve_github_account`` so a manual repair
cannot do what automatic linking will not:

* the target must exist (it is matched by email, which is unique);
* the target must not already carry a *different* GitHub identity — that account
  belongs to somebody else;
* the target must have a password, so a password-less dev-bypass leftover is
  never adopted.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import get_engine  # noqa: E402
from app.models import Approval, Repository, User, UserRepository  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


def _count(db: Session, user_id: int) -> dict[str, int]:
    return {
        "repositories": db.scalar(
            select(UserRepository).where(UserRepository.user_id == user_id).limit(1)
        )
        is not None,
        "approvals": db.scalar(select(Approval).where(Approval.user_id == user_id).limit(1))
        is not None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-id", type=int, required=True, help="GitHub numeric user id")
    parser.add_argument("--email", required=True, help="email of the account to attach to")
    parser.add_argument(
        "--move-from",
        action="append",
        default=[],
        help="login whose repositories and approvals move to the target (repeatable)",
    )
    parser.add_argument(
        "--delete-source",
        action="store_true",
        help="delete each --move-from account once it owns nothing",
    )
    parser.add_argument("--apply", action="store_true", help="write (default: dry run)")
    args = parser.parse_args()

    settings = get_settings()
    print(f"database: {settings.database_url.split('@')[-1]}")
    print(f"mode:     {'APPLY' if args.apply else 'dry run — nothing will be written'}")

    with Session(get_engine()) as db:
        target = db.scalar(select(User).where(User.email == args.email))
        if target is None:
            print(f"no account with email {args.email}", file=sys.stderr)
            return 1
        if not target.password_hash:
            print(
                f"refusing: {args.email} has no password. A password-less account is a\n"
                "dev-bypass leftover; automatic linking will not adopt one either.",
                file=sys.stderr,
            )
            return 1
        if target.github_id not in (None, args.github_id):
            print(
                f"refusing: {args.email} is already linked to GitHub id "
                f"{target.github_id}, not {args.github_id}. That account belongs to "
                "somebody else.",
                file=sys.stderr,
            )
            return 1

        print(f"\ntarget: user #{target.id} {target.login} <{target.email}>")

        # An account created by an earlier, link-less sign-in may already hold the
        # GitHub identity, and github_id is unique. That account is the superseded
        # duplicate this script exists to resolve, so the id is released from it
        # rather than left to collide.
        holder = db.scalar(select(User).where(User.github_id == args.github_id))
        if holder is not None and holder.id != target.id:
            owns_repos = (
                db.scalar(
                    select(UserRepository).where(UserRepository.user_id == holder.id).limit(1)
                )
                is not None
            )
            owns_approvals = (
                db.scalar(select(Approval).where(Approval.user_id == holder.id).limit(1)) is not None
            )
            print(
                f"\ngitHub id {args.github_id} is currently on user #{holder.id} "
                f"{holder.login} (repositories={owns_repos}, approvals={owns_approvals})"
            )
            if not args.apply:
                print("  would release the id from it and attach it to the target")
            else:
                holder.github_id = None
                db.flush()
                if not owns_repos and not owns_approvals:
                    db.delete(holder)
                    db.flush()
                    print(f"  released, and deleted user #{holder.id} (it owned nothing)")

        sources = []
        for login in args.move_from:
            source = db.scalar(select(User).where(User.login == login))
            if source is None:
                print(f"  ! no account with login {login!r}; skipped", file=sys.stderr)
                continue
            if source.id == target.id:
                continue
            sources.append(source)

        for source in sources:
            repos = db.scalars(
                select(Repository).join(UserRepository).where(UserRepository.user_id == source.id)
            ).all()
            print(f"\nmoving from user #{source.id} {source.login}:")
            print(f"  {len(repos)} repositories, {len(_count(db, source.id))} approvals")

            if not args.apply:
                continue

            for repo in repos:
                # Repositories are many-to-many by design, so this grants access
                # without touching the clone or the analysis history.
                if db.get(UserRepository, (repo.id, target.id)) is None:
                    db.add(UserRepository(repo_id=repo.id, user_id=target.id))
                db.execute(
                    UserRepository.__table__.delete().where(
                        UserRepository.repo_id == repo.id,
                        UserRepository.user_id == source.id,
                    )
                )
                # The legacy creator column, kept in step so ownership has one answer.
                if repo.added_by == source.id:
                    repo.added_by = target.id
            db.execute(
                Approval.__table__.update().where(Approval.user_id == source.id).values(
                    user_id=target.id
                )
            )

        if args.apply and target.github_id is None:
            target.github_id = args.github_id
            print(f"\nlinked GitHub id {args.github_id} to user #{target.id}")

        db.commit()

        if args.apply and args.delete_source:
            for source in sources:
                remaining = db.scalar(
                    select(UserRepository).where(UserRepository.user_id == source.id).limit(1)
                )
                approvals = db.scalar(
                    select(Approval).where(Approval.user_id == source.id).limit(1)
                )
                if remaining is None and approvals is None:
                    db.delete(source)
                    print(f"deleted user #{source.id} {source.login} (owned nothing)")
            db.commit()

        owned = db.scalar(
            select(UserRepository).where(UserRepository.user_id == target.id).limit(1)
        )
        total = len(
            db.scalars(
                select(Repository).join(UserRepository).where(UserRepository.user_id == target.id)
            ).all()
        )
        print(f"\nuser #{target.id} now owns {total} repositories (access={owned is not None})")

    if not args.apply:
        print("\nre-run with --apply to make these changes")
    return 0


if __name__ == "__main__":
    sys.exit(main())