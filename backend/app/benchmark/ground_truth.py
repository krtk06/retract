"""Ground truth for the benchmark harness (Phase 7).

An expectation is a planted condition we know to be true about a fixture
repository. Expectations drive two different measurements:

  * recall — did the pipeline report the condition at all?
  * precision — did it report things that are not in the ground truth?

``expect_dismissed`` marks a deliberately planted *false* finding. Those
expectations are excluded from recall (the finding should never have counted) and
inverted for precision: if a matching finding is still open, the pipeline failed to
triage it, and that is reported as a miss.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class GroundTruthError(ValueError):
    """The ground-truth file is missing, malformed, or internally inconsistent."""


@dataclass(frozen=True)
class Expectation:
    category: str
    file: str | None = None
    line: int | None = None
    note: str = ""
    expect_dismissed: bool = False

    @property
    def key(self) -> tuple[str, str | None]:
        return (self.category, self.file)


@dataclass(frozen=True)
class GroundTruth:
    repo: str
    expectations: list[Expectation] = field(default_factory=list)
    source: str = ""

    @property
    def categories(self) -> list[str]:
        return sorted({e.category for e in self.expectations})

    @property
    def detectable(self) -> list[Expectation]:
        """Expectations that should produce a real finding."""
        return [e for e in self.expectations if not e.expect_dismissed]

    @property
    def planted_false_positives(self) -> list[Expectation]:
        return [e for e in self.expectations if e.expect_dismissed]


def _expectation(raw: dict[str, Any], index: int) -> Expectation:
    if not isinstance(raw, dict):
        raise GroundTruthError(f"expectation #{index} is not a mapping")
    category = raw.get("category")
    if not isinstance(category, str) or not category:
        raise GroundTruthError(f"expectation #{index} has no category")
    line = raw.get("line")
    if line is not None and not isinstance(line, int):
        raise GroundTruthError(f"expectation #{index} has a non-integer line: {line!r}")
    file_path = raw.get("file")
    if file_path is not None and not isinstance(file_path, str):
        raise GroundTruthError(f"expectation #{index} has a non-string file: {file_path!r}")
    return Expectation(
        category=category,
        file=file_path,
        line=line,
        note=str(raw.get("note", "")).strip(),
        expect_dismissed=bool(raw.get("expect_dismissed", False)),
    )


def parse_ground_truth(text: str, source: str = "<string>") -> GroundTruth:
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise GroundTruthError(f"{source}: {exc}") from exc
    if not isinstance(raw, dict):
        raise GroundTruthError(f"{source}: expected a mapping at the top level")

    repo = raw.get("repo")
    if not isinstance(repo, str) or not repo:
        raise GroundTruthError(f"{source}: missing 'repo'")

    raw_expectations = raw.get("expectations")
    if not isinstance(raw_expectations, list) or not raw_expectations:
        raise GroundTruthError(f"{source}: 'expectations' must be a non-empty list")

    expectations = [_expectation(item, index) for index, item in enumerate(raw_expectations)]
    return GroundTruth(repo=repo, expectations=expectations, source=source)


def load_ground_truth(path: str | Path) -> GroundTruth:
    file_path = Path(path)
    if not file_path.is_file():
        raise GroundTruthError(f"ground-truth file not found: {file_path}")
    return parse_ground_truth(file_path.read_text(), source=str(file_path))
