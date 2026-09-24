"""Tool registry — name → runner function."""

from collections.abc import Callable

from app.services.tools.architecture import run_architecture
from app.services.tools.complexity import run_complexity
from app.services.tools.context import ToolContext
from app.services.tools.deps import run_deps
from app.services.tools.docs import run_docs
from app.services.tools.duplication import run_duplication
from app.services.tools.findings import FindingDraft
from app.services.tools.gitleaks import run_gitleaks
from app.services.tools.semgrep import run_semgrep
from app.services.tools.tests import run_tests

# Order is display order; runners are executed in parallel by the orchestrator.
TOOL_RUNNERS: dict[str, Callable[[ToolContext], list[FindingDraft]]] = {
    "semgrep": run_semgrep,
    "gitleaks": run_gitleaks,
    "deps": run_deps,
    "complexity": run_complexity,
    "duplication": run_duplication,
    "tests": run_tests,
    "docs": run_docs,
    "architecture": run_architecture,
}
