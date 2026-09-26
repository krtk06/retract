"""Semgrep runner — security findings and code smells from p/default rulesets."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

from app.config import get_settings
from app.models import Severity
from app.services.ingestion import SKIP_DIRS
from app.services.tools.context import ToolContext
from app.services.tools.findings import FindingDraft

TIMEOUT = 900

_SEVERITY_MAP = {
    "CRITICAL": Severity.CRITICAL,
    "ERROR": Severity.HIGH,
    "HIGH": Severity.HIGH,
    "WARNING": Severity.MEDIUM,
    "WARN": Severity.MEDIUM,
    "MEDIUM": Severity.MEDIUM,
    "INFO": Severity.LOW,
    "LOW": Severity.LOW,
    "INVENTORY": Severity.INFO,
}


def resolve_binary(env_key: str, name: str) -> str | None:
    """Find a tool binary: explicit env override → venv sibling → PATH."""
    settings = get_settings()
    override = getattr(settings, env_key, "")
    if override and Path(override).exists():
        return override
    venv_sibling = Path(sys.executable).parent / name
    if venv_sibling.exists():
        return str(venv_sibling)
    return shutil.which(name)


def _skip_roots(root: Path) -> list[str]:
    return [str(root / d) for d in SKIP_DIRS]


def categorize_check(check_id: str) -> str:
    """Map a semgrep rule id to the finding category it should be filed under.

    Order matters: semgrep's credential rules live under ``generic.secrets.*`` and
    also satisfy the broader ``.security.`` check, so testing secrets first keeps a
    hardcoded key out of the ``vulnerability`` bucket. A rule is only called a
    vulnerability when it is a security/audit rule that is not about credentials.
    """
    lowered = check_id.lower()
    if ".secrets." in lowered or lowered.startswith("generic.secrets"):
        return "secret"
    if ".security." in lowered or ".audit." in lowered:
        return "vulnerability"
    return "code-smell"


def run_semgrep(ctx: ToolContext) -> list[FindingDraft]:
    semgrep = resolve_binary("semgrep_path", "semgrep")
    if semgrep is None:
        raise RuntimeError("semgrep binary not found")
    settings = get_settings()
    cmd = [
        semgrep,
        "scan",
        "--json",
        "--quiet",
        "--no-git-ignore",
        "--config",
        settings.semgrep_config,
        "--exclude",
        ",".join(SKIP_DIRS),
        str(ctx.repo_root),
    ]
    proc = _execute(cmd, ctx.repo_root)
    data = json.loads(proc.stdout or "{}")
    drafts: list[FindingDraft] = []
    for result in data.get("results", []):
        check_id = result.get("check_id", "semgrep")
        extra = result.get("extra", {})
        severity = _SEVERITY_MAP.get(str(extra.get("severity", "WARNING")).upper(), Severity.MEDIUM)
        path = _rel(ctx.repo_root, result.get("path", ""))
        if not path:
            continue
        start = (result.get("start") or {}).get("line")
        end = (result.get("end") or {}).get("line")
        drafts.append(
            FindingDraft(
                agent="static-analysis",
                category=categorize_check(check_id),
                severity=severity,
                title=check_id.split(".")[-1].replace("-", " ").replace("_", " "),
                description=str(extra.get("message", ""))[:2000],
                file_path=path,
                line_start=start,
                line_end=end,
                evidence_json={"rule": check_id, "tool": "semgrep"},
                verifier="tool:semgrep",
            )
        )
    return drafts


def _execute(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT, check=False
    )
    if proc.returncode not in (0, 1):  # 1 = findings found is fine for some tools
        raise RuntimeError(f"{Path(cmd[0]).name} exited {proc.returncode}: {proc.stderr[:500]}")
    return proc


def _rel(root: Path, path: str) -> str | None:
    try:
        return str(Path(path).resolve().relative_to(root.resolve()))
    except ValueError:
        return path if not Path(path).is_absolute() else None
