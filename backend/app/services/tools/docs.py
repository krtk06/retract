"""Documentation runner: README presence/quality + Python docstring coverage."""

import ast
from pathlib import Path

from app.models import Severity
from app.services.tools.context import ToolContext
from app.services.tools.findings import FindingDraft

README_NAMES = {"readme.md", "readme.rst", "readme.txt", "readme"}
IMPORTANT_SECTIONS = ["install", "getting started", "usage", "quickstart", "setup", "example"]

MAX_MODULES_PER_RUN = 400


def run_docs(ctx: ToolContext) -> list[FindingDraft]:
    drafts: list[FindingDraft] = []
    readme = _find_readme(ctx.repo_root)
    if readme is None:
        drafts.append(
            FindingDraft(
                agent="docs",
                category="readme",
                severity=Severity.MEDIUM,
                title="No README file",
                description="The repository has no README, so new contributors get no orientation.",
                evidence_json={"expected": "README.md at repository root"},
                verifier="tool:docs",
            )
        )
    else:
        content = _read(readme).lower()
        if not any(section in content for section in IMPORTANT_SECTIONS):
            drafts.append(
                FindingDraft(
                    agent="docs",
                    category="readme",
                    severity=Severity.LOW,
                    title="README lacks install/usage sections",
                    description=(
                        "README exists but contains none of the usual sections: "
                        + ", ".join(IMPORTANT_SECTIONS)
                    ),
                    file_path=Path(readme).name,
                    evidence_json={"checked_sections": IMPORTANT_SECTIONS},
                    verifier="tool:docs",
                )
            )

    drafts.extend(_docstring_coverage(ctx))
    return drafts


def _docstring_coverage(ctx: ToolContext) -> list[FindingDraft]:
    drafts: list[FindingDraft] = []
    py_files = [f for f in ctx.code_files if f.ext == ".py"][:MAX_MODULES_PER_RUN]
    for entry in py_files:
        if _docstring_exempt(entry.path):
            continue
        path = ctx.repo_root / entry.path
        try:
            tree = ast.parse(path.read_text())
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue

        public_symbols = []
        documented = 0
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name.startswith("_"):
                    continue
                public_symbols.append(node.name)
                if ast.get_docstring(node) is not None:
                    documented += 1

        if len(public_symbols) >= 2 and documented / len(public_symbols) < 0.5:
            missing = [
                name
                for name in public_symbols
                if not any(
                    isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                    and child.name == name
                    and ast.get_docstring(child) is not None
                    for child in ast.iter_child_nodes(tree)
                )
            ]
            drafts.append(
                FindingDraft(
                    agent="docs",
                    category="docstring",
                    severity=Severity.MEDIUM,
                    title=(
                        f"Low docstring coverage in {entry.path} "
                        f"({documented}/{len(public_symbols)})"
                    ),
                    description=(
                        f"Only {documented} of {len(public_symbols)} public symbols in "
                        f"{entry.path} have docstrings. Missing: {', '.join(missing[:8])}"
                    ),
                    file_path=entry.path,
                    line_start=1,
                    evidence_json={
                        "public_symbols": public_symbols,
                        "documented": documented,
                        "missing": missing,
                    },
                    verifier="tool:docs",
                )
            )
    return drafts


def _docstring_exempt(path: str) -> bool:
    """Tests and generated migrations are not public API documentation targets.

    Test functions are named for the case they pin and carry their intent in the
    name; a uniform docstring on them adds noise, not information. Alembic
    revisions are generated scaffolding whose message lives in the revision
    metadata.
    """
    parts = Path(path).parts
    name = parts[-1]
    return (
        any(part in {"tests", "test"} for part in parts)
        or name.startswith("test_")
        or name.endswith("_test.py")
        or name == "conftest.py"
        or ("alembic" in parts and "versions" in parts)
    )


def _find_readme(root: Path) -> Path | None:
    # Case-insensitive on purpose: the tool runs on Linux, where README.md is a
    # different path from readme.md, and the capitalised form is the common one.
    try:
        entries = sorted(root.iterdir())
    except OSError:
        return None
    for candidate in entries:
        if candidate.is_file() and candidate.name.lower() in README_NAMES:
            return candidate
    return None


def _read(path: Path) -> str:
    try:
        return path.read_text()[:200_000]
    except (OSError, UnicodeDecodeError):
        return ""
