"""SQLAlchemy models — schema mirrors implementation.md Phase 1 task 3."""

import enum
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# Portable JSON: JSONB on PostgreSQL, generic JSON elsewhere (tests use SQLite).
JSONVariant = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(UTC)


class AnalysisStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class FindingStatus(enum.StrEnum):
    VERIFIED = "verified"
    HYPOTHESIS = "hypothesis"
    DISMISSED = "dismissed"


class Severity(enum.StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalDecision(enum.StrEnum):
    APPROVE = "approve"
    DISMISS = "dismiss"


class User(Base):
    """An authenticated account, linked to GitHub or an email address."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    github_id: Mapped[int | None] = mapped_column(unique=True, nullable=True)
    login: Mapped[str] = mapped_column(unique=True)
    # Email accounts (bcrypt hash) are optional: a user may exist with either or
    # both credential sets (GitHub-only, email-only, or GitHub + a set password).
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Whether the address has been proven. This is the gate on GitHub account
    # *linking*: an address alone is not ownership, and registering one requires no
    # proof, so linking on an unverified address let anyone pre-register a victim's
    # email and have the victim's GitHub identity attached to it.
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Bumped on logout and on any future "sign out everywhere". Session tokens carry
    # the version they were minted with; a mismatch means the token is revoked. A
    # self-contained JWT cannot otherwise be invalidated before it expires.
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Accounts created by the development bypass (`/api/auth/dev/login`) rather than
    # by a real sign-in. They exist only to make development convenient, and they are
    # the one kind of user that shares the repository pool — everyone else's analyses
    # are private (see Repository.is_shared).
    is_dev: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    repositories: Mapped[list["Repository"]] = relationship(back_populates="added_by_user")
    repository_access: Mapped[list["UserRepository"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserRepository(Base):
    """Ownership table: which users may see (and analyze) which repositories.

    Still the grant record for a private repository, but no longer a way to *reach*
    someone else's. A repository is private to the user who added it, and the grant
    is written when they add it — see ``Repository.is_shared`` for the one exception.
    """

    __tablename__ = "user_repositories"

    repo_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)

    repository: Mapped["Repository"] = relationship(back_populates="owners")
    user: Mapped["User"] = relationship(back_populates="repository_access")


class Repository(Base):
    """A repository someone has asked us to analyze.

    One row per (creator, url), not one row per url. It used to be the latter — a
    single shared row that any caller was granted access to by submitting the same
    url — which meant registering someone else's repository URL handed over their
    analyses, findings, and file contents. Since nothing verified that a caller could
    actually reach the repository on GitHub, the url was enough.

    ``is_shared`` keeps the old convenience for development bypass accounts only:
    they share one row per url, so a dev machine does not clone the same repository
    once per test account. Real accounts never see a shared row.
    """

    __tablename__ = "repositories"
    # Two partial unique indexes rather than one unique `url`: a private repository is
    # unique per creator, a shared one is unique across the pool. Written dialect-
    # agnostically — SQLite runs `create_all` in tests, Postgres runs the migrations.
    __table_args__ = (
        Index(
            "uq_repositories_shared_url",
            "url",
            unique=True,
            sqlite_where=text("is_shared"),
            postgresql_where=text("is_shared"),
        ),
        Index(
            "uq_repositories_owner_url",
            "added_by",
            "url",
            unique=True,
            sqlite_where=text("NOT is_shared"),
            postgresql_where=text("NOT is_shared"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner: Mapped[str]
    name: Mapped[str]
    url: Mapped[str]
    default_branch: Mapped[str] = mapped_column(default="main")
    added_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    added_by_user: Mapped[User] = relationship(back_populates="repositories")
    owners: Mapped[list["UserRepository"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    analyses: Mapped[list["Analysis"]] = relationship(back_populates="repository")


class SymbolKind(enum.StrEnum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"


class EdgeKind(enum.StrEnum):
    IMPORTS = "imports"
    CALLS = "calls"


class Analysis(Base):
    """One analysis run of a repository at a specific commit."""

    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"), index=True)
    commit_sha: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus, native_enum=False, validate_strings=True),
        default=AnalysisStatus.PENDING,
    )
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    loc: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_json: Mapped[dict | None] = mapped_column(JSONVariant, nullable=True)
    published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    repository: Mapped[Repository] = relationship(back_populates="analyses")
    findings: Mapped[list["Finding"]] = relationship(back_populates="analysis")
    symbols: Mapped[list["Symbol"]] = relationship(back_populates="analysis")


class Finding(Base):
    """A single issue reported by one agent within an analysis."""

    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), index=True)
    agent: Mapped[str] = mapped_column(index=True)
    category: Mapped[str] = mapped_column(index=True)
    severity: Mapped[Severity] = mapped_column(
        Enum(Severity, native_enum=False, validate_strings=True), default=Severity.INFO
    )
    title: Mapped[str]
    description: Mapped[str] = mapped_column(Text, default="")
    file_path: Mapped[str | None] = mapped_column(nullable=True)
    line_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_json: Mapped[dict | None] = mapped_column(JSONVariant, nullable=True)
    verifier: Mapped[str] = mapped_column(default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[FindingStatus] = mapped_column(
        Enum(FindingStatus, native_enum=False, validate_strings=True),
        default=FindingStatus.HYPOTHESIS,
    )
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    analysis: Mapped[Analysis] = relationship(back_populates="findings")
    approvals: Mapped[list["Approval"]] = relationship(back_populates="finding")


class Approval(Base):
    """A human decision recorded against one finding."""

    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(primary_key=True)
    finding_id: Mapped[int] = mapped_column(ForeignKey("findings.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[ApprovalDecision] = mapped_column(
        Enum(ApprovalDecision, native_enum=False, validate_strings=True)
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    finding: Mapped[Finding] = relationship(back_populates="approvals")


class CalibrationStat(Base):
    __tablename__ = "calibration_stats"
    __table_args__ = (UniqueConstraint("agent", "category", name="uq_calibration_agent_category"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    agent: Mapped[str]
    category: Mapped[str]
    shown: Mapped[int] = mapped_column(Integer, default=0)
    accepted: Mapped[int] = mapped_column(Integer, default=0)
    dismissed: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class EmailVerificationToken(Base):
    """A one-time link proving control of an email address.

    Only the SHA-256 of the token is stored, so the table is not a set of usable
    links if it leaks: the value in the email cannot be recovered from the row.
    """

    __tablename__ = "email_verification_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime]
    consumed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Symbol(Base):
    """An indexed definition from the repository's symbol graph."""

    __tablename__ = "symbols"
    __table_args__ = (
        UniqueConstraint(
            "analysis_id", "file_path", "name", "kind", "line_start", name="uq_symbol"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), index=True)
    file_path: Mapped[str] = mapped_column(index=True)
    name: Mapped[str]
    kind: Mapped[SymbolKind] = mapped_column(
        Enum(SymbolKind, native_enum=False, validate_strings=True)
    )
    line_start: Mapped[int]
    line_end: Mapped[int]

    analysis: Mapped[Analysis] = relationship(back_populates="symbols")
    outgoing_edges: Mapped[list["Edge"]] = relationship(
        back_populates="src_symbol", foreign_keys="Edge.src_symbol_id"
    )


class Edge(Base):
    """A relationship between two indexed symbols."""

    __tablename__ = "edges"
    __table_args__ = (UniqueConstraint("src_symbol_id", "dst_name", "kind", name="uq_edge"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), index=True)
    src_symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id"), index=True)
    dst_name: Mapped[str]
    dst_symbol_id: Mapped[int | None] = mapped_column(
        ForeignKey("symbols.id"), nullable=True, index=True
    )
    kind: Mapped[EdgeKind] = mapped_column(Enum(EdgeKind, native_enum=False, validate_strings=True))

    src_symbol: Mapped[Symbol] = relationship(
        back_populates="outgoing_edges", foreign_keys=[src_symbol_id]
    )


class GraphSnapshot(Base):
    __tablename__ = "graph_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), unique=True, index=True)
    symbol_count: Mapped[int] = mapped_column(Integer, default=0)
    edge_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    built_at: Mapped[datetime] = mapped_column(default=utcnow)
