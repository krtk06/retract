"""Benchmark matching: recall, the two precisions, and planted-false-positive triage."""

import pytest

from app.benchmark.ground_truth import (
    Expectation,
    GroundTruth,
    GroundTruthError,
    parse_ground_truth,
)
from app.benchmark.match import BenchmarkResult, score_findings
from app.models import Finding, FindingStatus, Severity

TRUTH = """
repo: fixture
expectations:
  - category: secret
    file: app/settings.py
    line: 2
  - category: coverage
  - category: duplication
    file: app/logic_beta.py
  - category: vulnerability
    file: app/cache_key.py
    line: 11
    expect_dismissed: true
"""


def make_finding(
    fid: int,
    category: str,
    file: str | None = None,
    line: int | None = None,
    status: FindingStatus = FindingStatus.VERIFIED,
    line_end: int | None = None,
) -> Finding:
    return Finding(
        id=fid,
        analysis_id=1,
        agent="test",
        category=category,
        severity=Severity.MEDIUM,
        title=f"finding {fid}",
        description="",
        file_path=file,
        line_start=line,
        line_end=line_end,
        evidence_json=None,
        verifier="tool:test",
        confidence=1.0,
        status=status,
    )


def score(findings: list[Finding]) -> BenchmarkResult:
    return score_findings(parse_ground_truth(TRUTH, "test"), findings, analysis_id=1)


def test_parses_expectations_including_planted_case() -> None:
    truth = parse_ground_truth(TRUTH, "test")
    assert truth.repo == "fixture"
    assert len(truth.detectable) == 3
    assert len(truth.planted_false_positives) == 1
    assert truth.planted_false_positives[0].file == "app/cache_key.py"
    assert truth.detectable[1].file is None, "an expectation may name only a category"


def test_rejects_malformed_ground_truth() -> None:
    with pytest.raises(GroundTruthError):
        parse_ground_truth("repo: x\nexpectations: []\n", "empty")
    with pytest.raises(GroundTruthError):
        parse_ground_truth("expectations:\n  - category: a\n", "no repo")
    with pytest.raises(GroundTruthError):
        parse_ground_truth("repo: x\nexpectations:\n  - note: no category\n", "no category")
    with pytest.raises(GroundTruthError):
        parse_ground_truth("repo: x\nexpectations:\n  - category: a\n    line: abc\n", "bad line")


def test_perfect_recall_and_precision() -> None:
    result = score(
        [
            make_finding(1, "secret", "app/settings.py", 2),
            make_finding(2, "coverage", None, None),
            make_finding(3, "duplication", "app/logic_beta.py", 10),
        ]
    )
    assert result.recall == pytest.approx(1.0)
    assert result.precision_grounded == pytest.approx(1.0)
    assert result.f1_grounded == pytest.approx(1.0)


def test_missing_expectation_costs_recall_not_precision() -> None:
    result = score([make_finding(2, "coverage", None, None)])
    assert result.recalled == 1
    assert result.expected == 3
    assert result.recall == pytest.approx(1 / 3)
    assert result.precision_grounded == pytest.approx(1.0)


def test_line_within_tolerance_still_counts() -> None:
    """Tools cite the enclosing symbol or block, not always the exact line."""
    result = score(
        [
            make_finding(1, "secret", "app/settings.py", 4),
            make_finding(2, "coverage", None, None),
            make_finding(3, "duplication", "app/logic_beta.py", 10),
        ]
    )
    assert result.recall == pytest.approx(1.0)


def test_cited_range_containing_the_expected_line_counts() -> None:
    result = score(
        [
            make_finding(1, "secret", "app/settings.py", 1, line_end=9),
            make_finding(2, "coverage", None, None),
            make_finding(3, "duplication", "app/logic_beta.py", 10),
        ]
    )
    assert result.recall == pytest.approx(1.0)


def test_finding_in_the_wrong_file_does_not_count_as_recalled() -> None:
    result = score(
        [
            make_finding(1, "secret", "app/other.py", 2),
            make_finding(2, "coverage", None, None),
            make_finding(3, "duplication", "app/logic_beta.py", 10),
        ]
    )
    assert result.recalled == 2
    secret_outcome = next(o for o in result.outcomes if o.expectation.category == "secret")
    assert secret_outcome.match.value == "wrong-file"


def test_untriaged_planted_false_positive_is_reported() -> None:
    result = score(
        [
            make_finding(1, "secret", "app/settings.py", 2),
            make_finding(2, "coverage", None, None),
            make_finding(3, "duplication", "app/logic_beta.py", 10),
            make_finding(4, "vulnerability", "app/cache_key.py", 11),
        ]
    )
    assert result.untriaged_planted, "a planted false positive was left open"
    planted = result.untriaged_planted[0]
    assert planted.expectation.expect_dismissed is True
    # It must not inflate recall: the expectation is not a true positive.
    assert result.expected == 3
    assert result.recalled == 3


def test_dismissed_planted_false_positive_scores_clean() -> None:
    result = score(
        [
            make_finding(1, "secret", "app/settings.py", 2),
            make_finding(2, "coverage", None, None),
            make_finding(3, "duplication", "app/logic_beta.py", 10),
            make_finding(
                4, "vulnerability", "app/cache_key.py", 11, status=FindingStatus.DISMISSED
            ),
        ]
    )
    assert not result.untriaged_planted
    assert result.dismissed_findings == 1
    assert result.precision_grounded == pytest.approx(1.0)
    assert result.precision_strict == pytest.approx(1.0)


def test_dismissed_true_positive_is_not_recalled() -> None:
    result = score(
        [
            make_finding(1, "secret", "app/settings.py", 2, status=FindingStatus.DISMISSED),
            make_finding(2, "coverage", None, None),
            make_finding(3, "duplication", "app/logic_beta.py", 10),
        ]
    )
    assert result.recalled == 2, "a dismissed finding does not count as detected"
    assert result.dismissed_findings == 1


def test_unenumerated_categories_are_unreviewed_not_wrong() -> None:
    result = score(
        [
            make_finding(1, "secret", "app/settings.py", 2),
            make_finding(2, "coverage", None, None),
            make_finding(3, "duplication", "app/logic_beta.py", 10),
            make_finding(4, "code-smell", "app/x.py", 5),
            make_finding(5, "layering", "app/y.py", 6),
        ]
    )
    assert result.unreviewed_categories == {"code-smell", "layering"}
    assert result.precision_grounded == pytest.approx(1.0), "unreviewed findings are not errors"
    assert result.precision_strict == pytest.approx(3 / 5)
    assert result.f1_grounded == pytest.approx(1.0)


def test_false_positive_in_an_enumerated_category_lowers_grounded_precision() -> None:
    result = score(
        [
            make_finding(1, "secret", "app/settings.py", 2),
            make_finding(2, "coverage", None, None),
            make_finding(3, "duplication", "app/logic_beta.py", 10),
            make_finding(4, "duplication", "app/nowhere.py", 3),
        ]
    )
    assert result.precision_grounded == pytest.approx(3 / 4)


def test_verification_coverage_reflects_open_findings() -> None:
    result = score(
        [
            make_finding(1, "secret", "app/settings.py", 2, status=FindingStatus.VERIFIED),
            make_finding(2, "coverage", None, None, status=FindingStatus.HYPOTHESIS),
            make_finding(3, "duplication", "app/logic_beta.py", 10, status=FindingStatus.VERIFIED),
        ]
    )
    assert result.verified_findings == 2
    assert result.hypothesis_findings == 1
    assert result.verification_coverage == pytest.approx(2 / 3)


def test_per_category_breakdown_is_reported() -> None:
    result = score(
        [
            make_finding(1, "secret", "app/settings.py", 2),
            make_finding(2, "duplication", "app/logic_beta.py", 10),
        ]
    )
    assert result.categories["secret"].expected == 1
    assert result.categories["secret"].recalled == 1
    assert result.categories["coverage"].expected == 1
    assert result.categories["coverage"].recalled == 0
    assert result.categories["coverage"].recall == 0.0


def test_empty_run_reports_no_ratios_rather_than_dividing_by_zero() -> None:
    result = score([])
    assert result.recall == 0.0
    assert result.precision_grounded is None
    assert result.f1_grounded is None
    assert result.verification_coverage is None


def test_a_category_only_expectation_matches_any_file() -> None:
    result = score(
        [
            make_finding(1, "secret", "app/settings.py", 2),
            make_finding(2, "coverage", "some/where/else.py", 42),
            make_finding(3, "duplication", "app/logic_beta.py", 10),
        ]
    )
    assert result.recall == pytest.approx(1.0)


def test_path_prefixes_do_not_break_matching() -> None:
    truth = GroundTruth(
        repo="fixture",
        expectations=[Expectation(category="secret", file="app/settings.py", line=2)],
    )
    result = score_findings(
        truth, [make_finding(1, "secret", "./app/settings.py", 2)], analysis_id=1
    )
    assert result.recall == pytest.approx(1.0)


def test_repeat_reports_of_one_condition_are_duplicates_not_false_positives() -> None:
    """Three findings for one planted key is noise, not three wrong answers."""
    result = score(
        [
            make_finding(1, "secret", "app/settings.py", 2),
            make_finding(2, "secret", "app/settings.py", 2),
            make_finding(3, "secret", "app/settings.py", 1),
            make_finding(4, "coverage", None, None),
            make_finding(5, "duplication", "app/logic_beta.py", 10),
        ]
    )
    assert sorted(result.duplicate_findings) == [2, 3]
    assert result.unenumerated_findings == []
    assert result.precision_grounded == pytest.approx(3 / 5)
    assert result.precision_deduplicated == pytest.approx(1.0), "duplicates are not false positives"
    assert result.recall == pytest.approx(1.0)


def test_distinct_unenumerated_finding_lowers_deduplicated_precision() -> None:
    result = score(
        [
            make_finding(1, "secret", "app/settings.py", 2),
            make_finding(2, "coverage", None, None),
            make_finding(3, "duplication", "app/logic_beta.py", 10),
            make_finding(4, "secret", "app/other_keys.py", 9),
        ]
    )
    assert result.duplicate_findings == []
    assert result.unenumerated_findings == [4]
    assert result.precision_deduplicated == pytest.approx(3 / 4)


def test_a_different_file_is_not_a_duplicate() -> None:
    result = score(
        [
            make_finding(1, "secret", "app/settings.py", 2),
            make_finding(2, "secret", "app/creds.py", 4),
            make_finding(3, "coverage", None, None),
            make_finding(4, "duplication", "app/logic_beta.py", 10),
        ]
    )
    assert result.duplicate_findings == []
    assert result.unenumerated_findings == [2]


def test_calibration_sweep_is_monotonic_in_both_constants() -> None:
    """Stricter density or less headroom can only lower the score."""
    from app.benchmark.calibration import sweep

    # Dense enough that one pillar sits far below the mean, so the cap binds.
    findings = [make_finding(i, "vulnerability", f"app/f{i}.py", 1) for i in range(1, 26)] + [
        make_finding(100, "coverage", None, None)
    ]
    rows = sweep(findings, loc=5000, densities=(40.0, 250.0), headrooms=(0, 15))
    by_key = {(r.half_score_density, r.worst_pillar_headroom): r for r in rows}
    assert by_key[(40.0, 0)].overall < by_key[(250.0, 0)].overall
    assert by_key[(250.0, 0)].overall < by_key[(250.0, 15)].overall


def test_calibration_sweep_ignores_dismissed_findings() -> None:
    from app.benchmark.calibration import sweep

    open_only = [make_finding(1, "vulnerability", "app/a.py", 1)]
    with_dismissal = open_only + [
        make_finding(2, "vulnerability", "app/b.py", 2, status=FindingStatus.DISMISSED)
    ]
    a = sweep(open_only, loc=500, densities=(100.0,), headrooms=(0,))[0]
    b = sweep(with_dismissal, loc=500, densities=(100.0,), headrooms=(0,))[0]
    assert a.overall == b.overall


def test_calibration_sweep_covers_every_combination() -> None:
    from app.benchmark.calibration import DEFAULT_DENSITIES, DEFAULT_HEADROOMS, sweep

    rows = sweep([make_finding(1, "secret", "app/a.py", 1)], loc=1000)
    assert len(rows) == len(DEFAULT_DENSITIES) * len(DEFAULT_HEADROOMS)
    assert all(0 <= r.overall <= 100 for r in rows)
    assert all(r.worst_pillar <= r.overall or r.capped for r in rows)
