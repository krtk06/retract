"""Match ground-truth expectations against a run's findings, and score the result.

Two precision numbers are reported on purpose, because a ground-truth file is
never exhaustive:

  * ``precision_grounded`` — of the findings in categories the ground truth
    actually enumerates, how many correspond to a real expectation. This is the
    number to quote.
  * ``precision_strict`` — of *all* open findings, how many correspond to an
    expectation. Lower by construction, and it conflates "wrong" with "not
    enumerated", so it is reported as a bound rather than a verdict.

Findings in unenumerated categories are counted as ``unreviewed`` instead of being
silently dropped or silently counted as errors.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from app.benchmark.ground_truth import Expectation, GroundTruth
from app.models import Finding, FindingStatus

# Tools report the enclosing symbol's start, the matched line, or the first line
# of a block, so an exact-line requirement is checked with a small window.
LINE_TOLERANCE = 3


class Match(StrEnum):
    EXACT = "exact"
    WRONG_LINE = "wrong-line"
    WRONG_FILE = "wrong-file"
    UNMATCHED = "unmatched"  # in ground truth, never reported


@dataclass
class ExpectationOutcome:
    expectation: Expectation
    match: Match
    finding_id: int | None = None


@dataclass
class CategoryScore:
    category: str
    expected: int = 0
    recalled: int = 0
    open_findings: int = 0
    matched_findings: int = 0
    unreviewed_findings: int = 0

    @property
    def recall(self) -> float | None:
        return self.recalled / self.expected if self.expected else None

    @property
    def precision_grounded(self) -> float | None:
        return self.matched_findings / self.open_findings if self.open_findings else None

    @property
    def precision_strict(self) -> float | None:
        return self.matched_findings / (self.open_findings + self.unreviewed_findings) or None


@dataclass
class BenchmarkResult:
    repo: str
    analysis_id: int
    outcomes: list[ExpectationOutcome] = field(default_factory=list)
    categories: dict[str, CategoryScore] = field(default_factory=dict)
    open_findings: int = 0
    dismissed_findings: int = 0
    verified_findings: int = 0
    hypothesis_findings: int = 0
    matched_finding_ids: set[int] = field(default_factory=set)
    unreviewed_categories: set[str] = field(default_factory=set)
    untriaged_planted: list[ExpectationOutcome] = field(default_factory=list)
    # Open findings that repeat a condition already matched by another finding.
    duplicate_findings: list[int] = field(default_factory=list)
    # Open findings in a grounded category that no expectation covers.
    unenumerated_findings: list[int] = field(default_factory=list)

    @property
    def expected(self) -> int:
        return sum(c.expected for c in self.categories.values())

    @property
    def recalled(self) -> int:
        return sum(c.recalled for c in self.categories.values())

    @property
    def recall(self) -> float | None:
        return self.recalled / self.expected if self.expected else None

    @property
    def matched_findings(self) -> int:
        return sum(c.matched_findings for c in self.categories.values())

    @property
    def enumerated_open_findings(self) -> int:
        """Open findings in categories the ground truth covers.

        Deliberately excludes ``unreviewed_findings``: those are findings in
        categories the ground truth never mentions, and charging them to precision
        would measure the completeness of the ground-truth file, not the pipeline.
        """
        return sum(c.open_findings for c in self.categories.values())

    @property
    def precision_grounded(self) -> float | None:
        if not self.enumerated_open_findings:
            return None
        return self.matched_findings / self.enumerated_open_findings

    @property
    def precision_deduplicated(self) -> float | None:
        """Precision ignoring duplicate reports of the same condition.

        A pipeline that flags one hardcoded key three times has not found three
        problems, and a reviewer should not read it as three false positives. This
        is the number to quote when duplicates are the dominant error; the raw
        ``precision_grounded`` stays visible next to it.
        """
        denominator = self.matched_findings + len(self.unenumerated_findings)
        return self.matched_findings / denominator if denominator else None

    @property
    def precision_strict(self) -> float | None:
        total = self.enumerated_open_findings + sum(
            c.unreviewed_findings for c in self.categories.values()
        )
        return self.matched_findings / total if total else None

    @property
    def verification_coverage(self) -> float | None:
        considered = self.verified_findings + self.hypothesis_findings
        return self.verified_findings / considered if considered else None

    @property
    def f1_grounded(self) -> float | None:
        precision, recall = self.precision_grounded, self.recall
        if precision is None or recall is None or (precision + recall) == 0:
            return None
        return 2 * precision * recall / (precision + recall)


def _paths_match(finding_file: str | None, expected_file: str | None) -> bool:
    """Compare repository-relative paths, tolerating a leading './' or a prefix."""
    if expected_file is None:
        return True
    if finding_file is None:
        return False
    actual = finding_file.replace("\\", "/").lstrip("./")
    wanted = expected_file.replace("\\", "/").lstrip("./")
    return actual == wanted or actual.endswith(f"/{wanted}")


def _line_matches(finding: Finding, expected: Expectation) -> bool:
    if expected.line is None:
        return True
    if finding.line_start is None:
        return False
    start = finding.line_start
    end = finding.line_end or start
    # The cited range must contain the expected line, or sit within tolerance.
    return expected.line - LINE_TOLERANCE <= end and start - LINE_TOLERANCE <= expected.line


def _score(expectation: Expectation, findings: Sequence[Finding]) -> Match:
    """Best match for one expectation: exact beats near-miss beats absent."""
    same_category = [f for f in findings if f.category == expectation.category]
    if not same_category:
        return Match.UNMATCHED
    in_file = [f for f in same_category if _paths_match(f.file_path, expectation.file)]
    if not in_file:
        # No finding in the right file. If the expectation named no file, the
        # category-level match above is already the best we can do.
        return Match.WRONG_FILE if expectation.file else Match.EXACT
    for finding in in_file:
        if _line_matches(finding, expectation):
            return Match.EXACT
    return Match.WRONG_LINE


def score_findings(
    ground_truth: GroundTruth, findings: list[Finding], analysis_id: int
) -> BenchmarkResult:
    result = BenchmarkResult(repo=ground_truth.repo, analysis_id=analysis_id)
    open_findings = [f for f in findings if f.status != FindingStatus.DISMISSED]
    dismissed = [f for f in findings if f.status == FindingStatus.DISMISSED]

    result.open_findings = len(open_findings)
    result.dismissed_findings = len(dismissed)
    result.verified_findings = sum(1 for f in open_findings if f.status == FindingStatus.VERIFIED)
    result.hypothesis_findings = sum(
        1 for f in open_findings if f.status == FindingStatus.HYPOTHESIS
    )

    for expectation in ground_truth.expectations:
        score = result.categories.setdefault(
            expectation.category, CategoryScore(expectation.category)
        )
        if expectation.expect_dismissed:
            # Inverted: a planted false positive is "found" only if it is still open.
            still_open = [
                f
                for f in open_findings
                if _paths_match(f.file_path, expectation.file)
                and f.category == expectation.category
            ]
            outcome = ExpectationOutcome(
                expectation, Match.EXACT if still_open else Match.UNMATCHED
            )
            result.outcomes.append(outcome)
            if still_open:
                result.untriaged_planted.append(outcome)
                score.open_findings += len(still_open)
            continue

        score.expected += 1
        match = _score(expectation, open_findings)
        outcome = ExpectationOutcome(expectation, match)
        result.outcomes.append(outcome)

        candidates = [
            f
            for f in open_findings
            if f.category == expectation.category and _paths_match(f.file_path, expectation.file)
        ]
        if match is Match.EXACT:
            score.recalled += 1
            best = min(
                candidates,
                key=lambda f: abs((f.line_start or 0) - (expectation.line or 0)),
            )
            outcome.finding_id = best.id
            result.matched_finding_ids.add(best.id)
        elif match is Match.WRONG_LINE and candidates:
            # Reported, but not at the line the ground truth names.
            outcome.finding_id = candidates[0].id

    enumerated = {e.category for e in ground_truth.detectable}
    planted_categories = {e.category for e in ground_truth.planted_false_positives}
    counted = enumerated | planted_categories
    # A finding repeats a condition when another matched finding already covers
    # the same category and file — the same real problem reported twice.
    matched_locus = {
        (f.category, f.file_path) for f in findings if f.id in result.matched_finding_ids
    }
    for finding in open_findings:
        score = result.categories.setdefault(finding.category, CategoryScore(finding.category))
        if finding.category in counted:
            if finding.id in result.matched_finding_ids:
                score.matched_findings += 1
            elif (finding.category, finding.file_path) in matched_locus:
                result.duplicate_findings.append(finding.id)
            else:
                result.unenumerated_findings.append(finding.id)
            score.open_findings += 1
        else:
            score.unreviewed_findings += 1
            result.unreviewed_categories.add(finding.category)
    return result
