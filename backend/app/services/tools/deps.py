"""Dependency checks: vulnerable versions (OSV API) + outdated pins (PyPI/npm)."""

import json
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
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

# Neither registry offers a bulk "latest version for these names" endpoint, so each
# pinned dependency costs one request. Issuing them serially with a 20s timeout means a
# single unreachable host stalls the tool for 20s per dependency, which is how this
# became the slowest step in the pipeline on large repositories. These three settings
# bound it: a short per-request timeout, parallel lookups, and a wall-clock budget for
# the whole set. The budget is the important one, because it holds regardless of how
# many dependencies a repository pins or how the network misbehaves.
HTTP_TIMEOUT = 5.0
REGISTRY_WORKERS = 8
REGISTRY_DEADLINE_SECONDS = 45.0


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
            version = _exact_pin_version(req)
            if version:
                out.append(Dep(req.name, version, "PyPI", source, line_no))
    except OSError:
        pass
    return out


def _exact_pin_version(req: Requirement) -> str | None:
    """Only exact pins (==) represent an installed version.

    Floor pins like idna>=2.5 are minimum requirements, not what's installed —
    checking them against OSV/latest would be a false positive.
    """
    for spec in req.specifier:
        if spec.operator == "==" and "*" not in spec.version:
            return spec.version
    return None


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
        version = _exact_pin_version(req)
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
            spec_str = str(spec)
            # npm ranges (>=, ^, ~, *, x) are not exact pins — skip them.
            if any(ch in spec_str for ch in ">^~*x"):
                continue
            version = spec_str
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
        vulns = result.get("vulns") or []
        vuln_ids = [v.get("id", "?") for v in vulns if isinstance(v, dict)]
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
    """Report pinned dependencies behind the latest published version.

    Lookups run in parallel under a wall-clock budget. Whatever has not answered when
    the budget expires is dropped and recorded as an `info` finding, so a slow registry
    degrades this check instead of silently truncating it: a reader can tell the
    difference between "no dependency is outdated" and "the registry never answered".
    """
    candidates = [d for d in deps if d.version]
    if not candidates:
        return []

    # The same package can be pinned in several files; check it once.
    unique: dict[tuple[str, str], Dep] = {}
    for dep in candidates:
        unique.setdefault((dep.ecosystem, dep.name), dep)

    latest_by_key: dict[tuple[str, str], str] = {}
    started = time.monotonic()

    # The pool is deliberately not a context manager. Leaving a `with ThreadPoolExecutor`
    # block calls shutdown(wait=True), which blocks on exactly the hung requests the
    # deadline exists to abandon, reinstating the original stall. shutdown(wait=False)
    # returns at the budget and lets in-flight threads unwind on their own, each already
    # bounded by HTTP_TIMEOUT; cancel_futures drops the ones that never started.
    pool = ThreadPoolExecutor(max_workers=REGISTRY_WORKERS)
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            futures = {pool.submit(_latest_version, client, dep): dep for dep in unique.values()}

            pending = set(futures)
            while pending:
                remaining = REGISTRY_DEADLINE_SECONDS - (time.monotonic() - started)
                if remaining <= 0:
                    break
                done, pending = wait(pending, timeout=remaining, return_when=FIRST_COMPLETED)
                if not done:
                    break
                for future in done:
                    dep = futures[future]
                    latest = future.result()
                    if latest is not None:
                        latest_by_key[(dep.ecosystem, dep.name)] = latest
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    skipped = len(unique) - len(latest_by_key)
    drafts: list[FindingDraft] = []
    for (ecosystem, name), latest in latest_by_key.items():
        for dep in candidates:
            if dep.ecosystem == ecosystem and dep.name == name:
                draft = _outdated_draft(dep, latest)
                if draft is not None:
                    drafts.append(draft)
                    break
    if skipped:
        drafts.append(
            FindingDraft(
                agent="dependencies",
                category="registry-lookup-incomplete",
                severity=Severity.INFO,
                title=f"Dependency version lookup incomplete ({skipped} not answered)",
                description=(
                    f"{skipped} of {len(candidates)} pinned dependencies had no answer "
                    f"within {REGISTRY_DEADLINE_SECONDS:.0f}s. Outdated-dependency results "
                    "below cover only the ones that answered, so absence of a finding is "
                    "not evidence that a dependency is current."
                ),
                verifier="tool:registry",
                evidence_json={"skipped": skipped, "checked": len(candidates)},
            )
        )
    return drafts


def _outdated_draft(dep: Dep, latest: str) -> FindingDraft | None:
    try:
        if Version(dep.version) >= Version(latest):
            return None
    except InvalidVersion:
        return None
    return FindingDraft(
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
