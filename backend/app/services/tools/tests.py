"""Test presence/coverage runner (heuristic; pytest --cov execution is opt-in)."""

import re
from pathlib import Path

from app.models import Severity
from app.services.ingestion import FileEntry
from app.services.tools.context import ToolContext
from app.services.tools.findings import FindingDraft

PY_TEST_FILE = re.compile(r"(^test_.*\.py$|.*_test\.py$|^conftest\.py$)")
JS_TEST_FILE = re.compile(r"(.*\.test\.[jt]sx?$|.*\.spec\.[jt]sx?$)")
NON_SOURCE_DIRS = {
    "docs",
    "doc",
    "examples",
    "scripts",
    "tools",
    "migrations",
    "alembic",
    "node_modules",
    "tests",
    "test",
    "data",
    "benchmark",
    "bin",
}


def run_tests(ctx: ToolContext) -> list[FindingDraft]:
    code_files = ctx.code_files
    py_test_files = [
        f.path for f in code_files if f.ext == ".py" and PY_TEST_FILE.match(Path(f.path).name)
    ]
    js_test_files = [
        f.path
        for f in code_files
        if f.ext in (".js", ".jsx", ".ts", ".tsx") and JS_TEST_FILE.match(Path(f.path).name)
    ]

    # Repo-level: no tests at all.
    if not py_test_files and not js_test_files:
        return [
            FindingDraft(
                agent="testing",
                category="coverage",
                severity=Severity.HIGH,
                title="No test suite detected",
                description=(
                    "No test files (test_*.py, *_test.py, *.test.js, *.spec.ts, or test "
                    "directories) were found in this repository."
                ),
                evidence_json={"python_test_files": 0, "js_test_files": 0},
                verifier="tool:test-presence",
            )
        ]

    # Package-level: top-level source packages never imported by any test file.
    test_contents = "\n".join(_read(ctx.repo_root / p) for p in py_test_files + js_test_files)
    drafts: list[FindingDraft] = []
    for package in _source_packages(code_files):
        pattern = re.compile(rf"(?:from|import)\s+{re.escape(package)}\b")
        if not pattern.search(test_contents):
            drafts.append(
                FindingDraft(
                    agent="testing",
                    category="missing-tests",
                    severity=Severity.MEDIUM,
                    title=f"No tests reference package '{package}'",
                    description=(
                        f"The source package '{package}' is not imported by any test file. "
                        "Consider adding unit tests for its modules."
                    ),
                    file_path=package,
                    evidence_json={"package": package},
                    verifier="tool:test-presence",
                )
            )
    return drafts


def _read(path: Path) -> str:
    try:
        return path.read_text()[:100_000]
    except (OSError, UnicodeDecodeError):
        return ""


def _source_packages(code_files: list[FileEntry]) -> list[str]:
    """The importable package names, not the repository's top-level directories.

    A package root may be nested (`backend/app`), and the tests import it by its
    package name (`app`), not by the checkout folder (`backend`). A directory is
    a package root when it holds an `__init__.py`; the *shallowest* such ancestor
    is the name tests are expected to reference — taking a deeper one would report
    `tools` for `app.services.tools`, which no test ever imports. Files outside a
    package (Alembic scripts, fixtures, test trees) contribute nothing: guessing a
    package for them produced unfixable findings against the checkout directory.
    """
    package_dirs = {
        str(Path(f.path).parent)
        for f in code_files
        if f.ext == ".py" and Path(f.path).name == "__init__.py"
    }
    packages: set[str] = set()
    for entry in code_files:
        if entry.ext != ".py":
            continue
        parts = Path(entry.path).parts
        if len(parts) < 2 or any(part in NON_SOURCE_DIRS for part in parts[:-1]):
            continue
        for index in range(1, len(parts)):
            if str(Path(*parts[:index])) in package_dirs:
                packages.add(parts[index - 1])
                break
    return sorted(packages)
