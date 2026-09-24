"""Gitleaks runner — hardcoded secrets."""

import json
import tempfile
from pathlib import Path

from app.models import Severity
from app.services.tools.context import ToolContext
from app.services.tools.findings import FindingDraft
from app.services.tools.semgrep import resolve_binary

TIMEOUT = 300


def run_gitleaks(ctx: ToolContext) -> list[FindingDraft]:
    gitleaks = resolve_binary("gitleaks_path", "gitleaks")
    if gitleaks is None:
        raise RuntimeError("gitleaks binary not found")

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as handle:
        report_path = handle.name
    cmd = [
        gitleaks,
        "detect",
        "--source",
        str(ctx.repo_root),
        "--no-git",
        "--no-banner",
        "--report-format",
        "json",
        "--report-path",
        report_path,
        "--redact",
    ]
    import subprocess

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT, check=False)
    # gitleaks exits 1 when leaks are found — that is success for us.
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"gitleaks exited {proc.returncode}: {proc.stderr[:500]}")

    report = Path(report_path)
    try:
        results = json.loads(report.read_text() or "[]")
    finally:
        report.unlink(missing_ok=True)

    drafts: list[FindingDraft] = []
    for item in results:
        file_path = _rel(ctx.repo_root, str(item.get("File", "")))
        if not file_path:
            continue
        rule = str(item.get("RuleID", "secret"))
        drafts.append(
            FindingDraft(
                agent="security",
                category="secret",
                severity=Severity.HIGH,
                title=f"Hardcoded secret ({rule})",
                description=str(item.get("Description", ""))[:1000],
                file_path=file_path,
                line_start=item.get("StartLine"),
                line_end=item.get("EndLine"),
                evidence_json={"rule": rule, "tool": "gitleaks"},
                verifier="tool:gitleaks",
            )
        )
    return drafts


def _rel(root: Path, path: str) -> str | None:
    try:
        return str(Path(path).resolve().relative_to(root.resolve()))
    except ValueError:
        return None
