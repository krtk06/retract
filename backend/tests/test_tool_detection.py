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

from app.services.ingestion import FileEntry, count_lines
from app.services.tools.context import ToolContext
from app.services.tools.docs import run_docs
from app.services.tools.tests import run_tests


def _context(root: Path) -> ToolContext:
    files = [
        FileEntry(
            path=p.relative_to(root).as_posix(),
            size=p.stat().st_size,
            ext=p.suffix.lower(),
            lines=count_lines(p),
        )
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


def test_inventory_honours_the_repository_ignore_file(tmp_path: Path) -> None:
    """A fixture the repo declares out of scope must not be scored as product code."""
    _write(tmp_path, ".aislopignore", "# intentional fixture\nfixture/\n")
    _write(tmp_path, "fixture/vulnerable.py", "SECRET = 'AKIAIOSFODNN7EXAMPLE'\n")
    _write(tmp_path, "app/main.py", "print('ok')\n")

    from app.services.ingestion import build_inventory

    files, _total, _truncated = build_inventory(tmp_path)

    assert [f.path for f in files if f.path.endswith(".py")] == ["app/main.py"]


def test_duplicate_import_blocks_are_not_duplication(tmp_path: Path) -> None:
    """Shared imports normalize identically and used to be reported as duplication."""
    imports = "\n".join(
        [
            "import os",
            "import sys",
            "import json",
            "import logging",
            "from pathlib import Path",
            "from typing import Any",
            "from collections import defaultdict",
            "from dataclasses import dataclass",
        ]
    )
    body_a = "\n".join(f"def alpha_{i}(value):\n    return value + {i}" for i in range(5))
    body_b = "\n".join(f"def beta_{i}(value):\n    return value * {i}" for i in range(5))
    _write(tmp_path, "a.py", imports + "\n\n" + body_a + "\n")
    _write(tmp_path, "b.py", imports + "\n\n" + body_b + "\n")

    from app.services.tools.duplication import run_duplication

    assert run_duplication(_context(tmp_path)) == []


def test_generated_migrations_are_not_maintainability_findings(tmp_path: Path) -> None:
    branchy = "def upgrade():\n" + "".join(
        f"    if {i} > 0:\n        print({i})\n" for i in range(14)
    )
    _write(tmp_path, "alembic/versions/0001_initial.py", branchy)
    _write(tmp_path, "app/hot.py", branchy)

    from app.services.tools.complexity import run_complexity

    findings = run_complexity(_context(tmp_path))

    # The migration contributes nothing; the equivalent hand-written module does.
    assert {f.file_path for f in findings} == {"app/hot.py"}
    assert any(f.category == "complexity" for f in findings)
