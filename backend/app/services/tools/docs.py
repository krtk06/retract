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


def _find_readme(root: Path) -> Path | None:
    for name in README_NAMES:
        candidate = root / name
        if candidate.exists():
            return candidate
    return None


def _read(path: Path) -> str:
    try:
        return path.read_text()[:200_000]
    except (OSError, UnicodeDecodeError):
        return ""
