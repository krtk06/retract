"""Core remediation types: effort weights, evidence accessors, and plan records."""

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.models import Finding

# Ordered roughly by how much effort a human typically needs. These are ratios,
# not durations: `high` is eight times the work of `low`, which is about right
# when `low` is "rotate a key" and `high` is "restructure a module".
EFFORT_WEIGHT = {"low": 1, "medium": 3, "high": 8}

# Categories the platform files but deliberately excludes from scoring. Advice
# about the analysis pipeline's own housekeeping is noise in a fix plan.
UNSCORED_CATEGORIES = frozenset({"inventory", "tool-error"})

# Cap on work items, so a repository with thousands of findings cannot produce an
# unreadable page. The remainder is reported in `truncated_findings` rather than
# silently dropped.
MAX_WORK_ITEMS = 40


@dataclass(frozen=True)
class Remediation:
    """How to fix one finding."""

    action: str
    steps: list[str]
    effort: str = "medium"
    verify: str = "Re-run the analysis and confirm the finding is gone."
    references: list[str] = field(default_factory=list)

    def weight(self) -> int:
        return EFFORT_WEIGHT.get(self.effort, EFFORT_WEIGHT["medium"])


class Remediatable(Protocol):
    """The finding attributes the catalog reads.

    A Protocol rather than ``Finding`` so the API schema can ask for advice about
    a partially-loaded row without importing the ORM model into ``app.schemas``.
    """

    category: str
    title: str
    evidence_json: dict[str, Any] | None
    file_path: str | None
    line_start: int | None


# Every one of these returns a value or None rather than raising: a finding with
# an unexpected evidence shape must degrade to the generic entry for its
# category, never fail the whole plan.


def _text(evidence: dict[str, Any], key: str) -> str | None:
    value = evidence.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _number(evidence: dict[str, Any], key: str) -> float | None:
    value = evidence.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _names(evidence: dict[str, Any], key: str, limit: int = 4) -> list[str]:
    value = evidence.get(key)
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()][:limit]


def _where(finding: Remediatable) -> str:
    if not finding.file_path:
        return "the repository"
    if finding.line_start:
        return f"{finding.file_path}:{finding.line_start}"
    return finding.file_path


OWASP_TOP10 = "https://owasp.org/www-project-top-10/2021"
GITHUB_PURGE = (
    "https://docs.github.com/en/authentication/keeping-your-account-and-data-secure"
    "/removing-sensitive-data-from-a-repository"
)


@dataclass
class WorkItem:
    key: str
    pillar: str
    action: str
    severity: str
    effort: str
    findings: list[Finding]
    steps: list[str]
    verify: str
    references: list[str]
    weighted_penalty_removed: float
    pillar_points: int
    llm_authored: bool = False

    @property
    def source(self) -> str:
        return "llm:eve" if self.llm_authored else "catalog"

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    def payoff(self) -> float:
        """Score points per unit of effort. This is the ranking key.

        Uses the additive penalty removal rather than the point delta, because
        penalty removal is exact and order-independent, so the ordering it induces
        is stable across repositories.
        """
        return self.weighted_penalty_removed / EFFORT_WEIGHT.get(self.effort, 3)


@dataclass
class RemediationPlan:
    analysis_id: int
    current_overall: int | None
    projected_overall: int | None
    loc: int | None
    work_items: list[WorkItem]
    findings_considered: int
    unverified_items: int
    truncated_findings: int = 0

    @property
    def recoverable_points(self) -> int | None:
        if self.current_overall is None or self.projected_overall is None:
            return None
        return max(0, self.projected_overall - self.current_overall)
