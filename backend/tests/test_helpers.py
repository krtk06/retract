"""Unit tests for pure helpers: URL parsing, language detection, inventory."""

from pathlib import Path

import pytest

from app.services.github import InvalidRepoUrl, canonical_url, parse_github_url
from app.services.ingestion import FileEntry, build_inventory, detect_languages


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/psf/requests", ("psf", "requests")),
        ("https://github.com/psf/requests/", ("psf", "requests")),
        ("https://github.com/psf/requests.git", ("psf", "requests")),
        ("git@github.com:psf/requests.git", ("psf", "requests")),
        ("http://github.com/a/b", ("a", "b")),
    ],
)
def test_parse_github_url_valid(url: str, expected: tuple[str, str]) -> None:
    assert parse_github_url(url) == expected


@pytest.mark.parametrize(
    "url",
    ["https://gitlab.com/a/b", "https://github.com/onlyowner", "not-a-url", ""],
)
def test_parse_github_url_invalid(url: str) -> None:
    with pytest.raises(InvalidRepoUrl):
        parse_github_url(url)


def test_canonical_url() -> None:
    assert canonical_url("psf", "requests") == "https://github.com/psf/requests"


def test_detect_languages() -> None:
    files = [
        FileEntry("a.py", 10, ".py"),
        FileEntry("b.py", 10, ".py"),
        FileEntry("c.ts", 10, ".ts"),
        FileEntry("d.unknownext", 10, ".unknownext"),
    ]
    assert detect_languages(files) == {"Python": 2, "TypeScript": 1}


def test_build_inventory_skips_git_and_counts(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("ignored")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.js").write_text("ignored")

    entries, total, truncated = build_inventory(tmp_path)
    # Skipped dirs are pruned before counting, so only src/main.py is seen.
    assert total == 1
    assert [e.path for e in entries] == ["src/main.py"]
    assert truncated is False
