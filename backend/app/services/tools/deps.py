"""Dependency checks: vulnerable versions (OSV API) + outdated pins (PyPI/npm)."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

import httpx
from packaging.requirements import Requirement
from packaging.version import InvalidVersion, Version

from app.models import Severity
from app.services.tools.context import ToolContext
from app.services.tools.findings import FindingDraft

OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"
PYPI_URL = "https://pypi.org/pypi/{name}/json"
NPM_URL = "https://registry.npmjs.org/{name}"
MAX_DEPS_CHECKED = 60
HTTP_TIMEOUT = 20.0

_RE_NPM_RANGE = re.compile(r"^[\^~>=< ]*")


@dataclass
class Dep:
    name: str
    version: str  # empty when not pinned
    ecosystem: str  # "PyPI" | "npm"
    source_file: str
    line: int | None = None


def collect_dependencies(ctx: ToolContext) -> list[Dep]:
    deps: list[Dep] = []
    for entry in ctx.files:
        path = ctx.repo_root / entry.path
        if entry.path == "pyproject.toml":
            deps.extend(_parse_pyproject(path, entry.path))
        elif entry.path.startswith("requirements") and entry.ext == ".txt":
            deps.extend(_parse_requirements(path, entry.path))
        elif entry.path == "package.json":
            deps.extend(_parse_package_json(path, entry.path))
    return deps


def _parse_requirements(path: Path, source: str) -> list[Dep]:
    out = []
    try:
        for line_no, raw in enumerate(path.read_text().splitlines(), start=1):
            line = raw.split("#", 1)[0].strip()
            if not line or line.startswith("-"):
                continue
            try:
                req = Requirement(line)
            except Exception:  # noqa: BLE001
                continue
            version = next(iter(req.specifier)).version if req.specifier else ""
            if version:
                out.append(Dep(req.name, version, "PyPI", source, line_no))
    except OSError:
        pass
    return out


def _parse_pyproject(path: Path, source: str) -> list[Dep]:
    try:
        import tomllib

        data = tomllib.loads(path.read_text())
    except (OSError, ValueError, ModuleNotFoundError):
        return []
    out: list[Dep] = []
    project = data.get("project", {})
    for raw in project.get("dependencies", []) or []:
        try:
            req = Requirement(raw)
        except Exception:  # noqa: BLE001
            continue
        version = next(iter(req.specifier)).version if req.specifier else ""
        if version:
            out.append(Dep(req.name, version, "PyPI", source))
    return out


def _parse_package_json(path: Path, source: str) -> list[Dep]:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    out: list[Dep] = []
    for section in ("dependencies", "devDependencies"):
        for name, spec in (data.get(section) or {}).items():
            version = _RE_NPM_RANGE.sub("", str(spec)).split("+")[0]
            if version and version[0].isdigit():
                out.append(Dep(name, version, "npm", source))
    return out


def run_deps(ctx: ToolContext) -> list[FindingDraft]:
    deps = collect_dependencies(ctx)[:MAX_DEPS_CHECKED]
    if not deps:
        return []
    drafts: list[FindingDraft] = []
    drafts.extend(_vulnerable(deps, ctx))
    drafts.extend(_outdated(deps))
    return drafts


def _vulnerable(deps: list[Dep], ctx: ToolContext) -> list[FindingDraft]:
    queries = [
        {"package": {"name": d.name, "ecosystem": d.ecosystem}, "version": d.version}
        for d in deps
        if d.version
    ]
    if not queries:
        return []
    try:
        response = httpx.post(OSV_BATCH_URL, json={"queries": queries}, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        results = response.json().get("results", [])
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError(f"OSV query failed: {exc}") from exc

    drafts: list[FindingDraft] = []
    checked = [d for d in deps if d.version]
    for dep, result in zip(checked, results, strict=False):
        vuln_ids = result.get("vuln_ids", [])
        if not vuln_ids:
            continue
        drafts.append(
            FindingDraft(
                agent="security",
                category="vulnerable-dependency",
                severity=Severity.HIGH,
                title=f"Vulnerable dependency: {dep.name}=={dep.version}",
                description=(
                    f"{len(vuln_ids)} known vulnerabilities for {dep.name} {dep.version} "
                    f"(pinned in {dep.source_file})."
                ),
                file_path=dep.source_file,
                line_start=dep.line,
                evidence_json={
                    "vuln_ids": vuln_ids[:20],
                    "package": dep.name,
                    "version": dep.version,
                },
                verifier="tool:osv",
            )
        )
    return drafts


def _outdated(deps: list[Dep]) -> list[FindingDraft]:
    drafts: list[FindingDraft] = []
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        for dep in deps:
            if not dep.version:
                continue
            latest = _latest_version(client, dep)
            if latest is None:
                continue
            try:
                if Version(dep.version) < Version(latest):
                    drafts.append(
                        FindingDraft(
                            agent="dependencies",
                            category="outdated-dependency",
                            severity=Severity.LOW,
                            title=f"Outdated dependency: {dep.name}=={dep.version}",
                            description=(
                                f"{dep.name} is pinned to {dep.version} in {dep.source_file}; "
                                f"latest published version is {latest}."
                            ),
                            file_path=dep.source_file,
                            line_start=dep.line,
                            evidence_json={"installed": dep.version, "latest": latest},
                            verifier="tool:registry",
                        )
                    )
            except InvalidVersion:
                continue
    return drafts


def _latest_version(client: httpx.Client, dep: Dep) -> str | None:
    try:
        if dep.ecosystem == "PyPI":
            response = client.get(PYPI_URL.format(name=dep.name))
            response.raise_for_status()
            return response.json().get("info", {}).get("version")
        if dep.ecosystem == "npm":
            response = client.get(NPM_URL.format(name=dep.name))
            response.raise_for_status()
            return response.json().get("dist-tags", {}).get("latest")
    except (httpx.HTTPError, ValueError):
        return None
    return None
