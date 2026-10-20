"""Detection tests for the docs and tests tools.

Both rules were wrong in ways that only dogfooding exposed:

* the README lookup compared names case-sensitively, so the ordinary
  `README.md` was missed on a case-sensitive filesystem;
* package detection took the repository's checkout directory (`backend`) as the
  importable package, while the tests import the package root (`app`), which
  produced a permanent, unfixable "no tests reference backend" finding.

These tests pin the corrected behaviour, including the docstring exemption for
tests and generated migrations.
"""

from pathlib import Path

from app.services.ingestion import FileEntry
from app.services.tools.context import ToolContext
from app.services.tools.docs import run_docs
from app.services.tools.tests import run_tests


def _context(root: Path) -> ToolContext:
    files = [
        FileEntry(path=p.relative_to(root).as_posix(), size=p.stat().st_size, ext=p.suffix.lower())
        for p in root.rglob("*")
        if p.is_file()
    ]
    return ToolContext(analysis_id=1, repo_root=root, files=files, loc=0)


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_readme_is_found_regardless_of_case(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", "# Demo\n\n## Install\n\npip install demo\n")
    _write(
        tmp_path,
        "app.py",
        "def public_one():\n    '''One.'''\n\ndef public_two():\n    '''Two.'''\n",
    )

    findings = run_docs(_context(tmp_path))

    assert not [f for f in findings if f.category == "readme"]


def test_docstring_coverage_skips_tests_and_generated_migrations(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", "# Demo\n\n## Install\n\npip install demo\n")
    undocumented = "def first():\n    pass\n\ndef second():\n    pass\n"
    _write(tmp_path, "tests/test_example.py", undocumented)
    _write(tmp_path, "alembic/versions/0001_initial.py", undocumented)

    findings = run_docs(_context(tmp_path))

    flagged = {f.file_path for f in findings if f.category == "docstring"}
    assert "tests/test_example.py" not in flagged
    assert "alembic/versions/0001_initial.py" not in flagged


def test_package_detection_uses_the_importable_package(tmp_path: Path) -> None:
    _write(tmp_path, "backend/app/__init__.py", "")
    _write(tmp_path, "backend/app/core.py", "def work():\n    return 1\n")
    _write(
        tmp_path,
        "backend/tests/test_core.py",
        "from app.core import work\n\ndef test_work():\n    assert work() == 1\n",
    )

    findings = run_tests(_context(tmp_path))

    assert not [f for f in findings if f.category == "missing-tests"]


def test_package_detection_reports_the_shallowest_package_once(tmp_path: Path) -> None:
    """A nested package must not be reported under its deepest component."""
    _write(tmp_path, "backend/app/__init__.py", "")
    _write(tmp_path, "backend/app/services/__init__.py", "")
    _write(tmp_path, "backend/app/services/tools/__init__.py", "")
    _write(tmp_path, "backend/app/services/tools/run.py", "def work():\n    return 1\n")
    # Alembic scripts sit outside any package and must not become a package name.
    _write(tmp_path, "backend/alembic/env.py", "print('migrations')\n")
    _write(
        tmp_path,
        "backend/tests/test_run.py",
        "from app.services.tools.run import work\n\ndef test_work():\n    assert work() == 1\n",
    )

    findings = run_tests(_context(tmp_path))

    assert not [f for f in findings if f.category == "missing-tests"]
