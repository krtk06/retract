"""Deterministic offline LLM harness (AI_INTEL_LLM_PROVIDER=mock).

This is NOT an LLM. It is a rule-based stand-in that turns the deterministic
context the agents pass in (tool findings, graph facts, coverage data) into the
same JSON shape a real model would return, so the agent pipeline, schema
validation, SSE progress, cost ledger, and UI can be exercised without network
access. Findings it produces are labelled ``llm:mock`` and must never be
presented as real analysis. Real usage sets AI_INTEL_LLM_PROVIDER=openai.

It also supports scripted responses (``responses=[...]``) used by tests to
assert schema validation, repair retries, and malformed-output handling.
"""

import json
from collections.abc import Callable
from typing import Any

from app.llm.client import LLMResponse


class ScriptedMockLLM:
    """Returns queued raw strings in order (for tests)."""

    name = "mock-scripted"

    def __init__(self, responses: list[str], model: str = "mock-1") -> None:
        self._responses = list(responses)
        self.model = model
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        system: str,
        user: str,
        json_schema: dict[str, Any] | None = None,
        schema_name: str = "response",
    ) -> LLMResponse:
        self.calls.append({"system": system, "user": user, "schema_name": schema_name})
        content = self._responses.pop(0) if self._responses else "{}"
        return LLMResponse(content=content, model=self.model, tokens_in=1, tokens_out=1)


class HeuristicMockLLM:
    """Rule-based JSON generator keyed on the agent's structured context."""

    name = "mock"
    model = "mock-heuristic-1"

    def __init__(
        self, handler: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None
    ) -> None:
        self._handler = handler
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        system: str,
        user: str,
        json_schema: dict[str, Any] | None = None,
        schema_name: str = "response",
    ) -> LLMResponse:
        self.calls.append({"system": system, "schema_name": schema_name})
        context = _extract_context(user)
        agent = context.get("agent", "unknown")
        if self._handler is not None:
            payload = self._handler(agent, context)
        else:
            payload = _HANDLERS.get(agent, _empty)(context)
        return LLMResponse(
            content=json.dumps(payload),
            model=self.model,
            tokens_in=max(1, len(user) // 4),
            tokens_out=max(1, len(json.dumps(payload)) // 4),
            logprob_confidence=0.55,  # deliberately low: mock output is unverified
            provider=self.name,
        )


def _extract_context(user: str) -> dict[str, Any]:
    start = user.find("{")
    end = user.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        data = json.loads(user[start : end + 1])
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _empty(context: dict[str, Any]) -> dict[str, Any]:
    return {"findings": []}


def _to_finding(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim": item.get("claim", ""),
        "evidence": item.get("evidence", ""),
        "file_path": item.get("file_path"),
        "line_start": item.get("line_start"),
        "line_end": item.get("line_end"),
        "severity": item.get("severity", "medium"),
        "confidence": float(item.get("confidence", 0.5)),
        "category": item.get("category", "insight"),
    }


def _code(context: dict[str, Any]) -> dict[str, Any]:
    """Dismiss static findings that are documented non-security hash usage."""
    triage = []
    findings = []
    for item in context.get("static_findings", []):
        rule = str(item.get("rule", "")).lower()
        description = str(item.get("description", "")).lower()
        evidence = item.get("evidence_text", "").lower()
        is_hash = (
            "insecure-hash" in rule
            or "hash" in rule
            or "md5" in description
            or "sha1" in description
            or "sha-1" in description
        )
        if is_hash and (
            "non-security" in evidence or "cache key" in evidence or "fingerprint" in evidence
        ):
            triage.append(
                {
                    "finding_id": item.get("id"),
                    "verdict": "false-positive",
                    "confidence": 0.8,
                    "reasoning": (
                        "The fast digest here only fingerprints cache content; the source "
                        "documents that it is not used for security purposes."
                    ),
                }
            )
    complexity = context.get("complexity_hotspots") or []
    if complexity:
        top = complexity[0]
        findings.append(
            _to_finding(
                {
                    "claim": f"{top.get('name')} has high cyclomatic complexity "
                    f"({top.get('complexity')}) and should be decomposed.",
                    "evidence": f"radon reports CC {top.get('complexity')} at "
                    f"{top.get('file_path')}:{top.get('line_start')}.",
                    "file_path": top.get("file_path"),
                    "line_start": top.get("line_start"),
                    "severity": "medium",
                    "confidence": 0.7,
                    "category": "complexity-review",
                }
            )
        )
    if not triage and not findings:
        findings.append(
            _to_finding(
                {
                    "claim": "No additional code-quality insights beyond the static analysis.",
                    "evidence": (
                        "Static tool findings were reviewed; none warranted further triage."
                    ),
                    "file_path": None,
                    "line_start": None,
                    "severity": "info",
                    "confidence": 0.5,
                    "category": "code-review",
                }
            )
        )
    return {"findings": findings, "triage": triage, "summary": "Code triage complete."}


def _security(context: dict[str, Any]) -> dict[str, Any]:
    findings = []
    for hotspot in context.get("risk_functions", []):
        callers = hotspot.get("callers") or []
        caller_note = (
            f"Callers: {', '.join(callers[:3])}." if callers else "No internal callers resolved."
        )
        rule = str(hotspot.get("rule", "")).lower()
        snippet = str(hotspot.get("snippet", "")).lower()
        if "sql" in rule or "sql" in snippet or "execute(" in snippet:
            claim = (
                f"{hotspot.get('name')} builds a query with string interpolation, "
                "enabling SQL injection."
            )
            category = "injection"
            severity = "high"
        elif "hash" in rule or "sha1" in snippet or "md5" in snippet:
            claim = (
                f"{hotspot.get('name')} uses a weak digest; verify it is not relied on "
                "for security properties."
            )
            category = "weak-crypto"
            severity = "medium"
        elif "secret" in rule or "aws" in rule:
            claim = f"{hotspot.get('name')} exposes a hardcoded credential."
            category = "secret"
            severity = "high"
        else:
            claim = f"{hotspot.get('name')} matches a security-relevant rule ({rule})."
            category = "security-review"
            severity = "medium"
        findings.append(
            _to_finding(
                {
                    "claim": claim,
                    "evidence": (
                        f"Detected pattern at {hotspot.get('file_path')}:"
                        f"{hotspot.get('line_start')}. "
                        f"{caller_note} Untrusted input can reach the executed statement."
                    ),
                    "file_path": hotspot.get("file_path"),
                    "line_start": hotspot.get("line_start"),
                    "severity": severity,
                    "confidence": 0.75,
                    "category": category,
                }
            )
        )
    for dependency in context.get("reachable_dependencies", []):
        findings.append(
            _to_finding(
                {
                    "claim": f"Vulnerable dependency {dependency.get('package')}"
                    f"=={dependency.get('version')} is reachable from first-party code.",
                    "evidence": (
                        f"Imported by {dependency.get('imported_by')}; "
                        f"advisories: {', '.join(dependency.get('vuln_ids', [])[:3])}."
                    ),
                    "file_path": dependency.get("file_path"),
                    "line_start": dependency.get("line_start"),
                    "severity": "high",
                    "confidence": 0.6,
                    "category": "vulnerable-dependency",
                }
            )
        )
    return {"findings": findings, "summary": "Security review complete."}


def _tests(context: dict[str, Any]) -> dict[str, Any]:
    findings = []
    for package in context.get("untested_modules", []):
        findings.append(
            _to_finding(
                {
                    "claim": (
                        f"Add tests for '{package}' covering its public functions and error paths."
                    ),
                    "evidence": (
                        f"No test file imports '{package}'. Proposed coverage: happy path, "
                        "invalid input, and exception branches."
                    ),
                    "file_path": package,
                    "line_start": None,
                    "severity": "medium",
                    "confidence": 0.6,
                    "category": "test-plan",
                }
            )
        )
    if context.get("repo_has_tests") is False:
        findings.append(
            _to_finding(
                {
                    "claim": "Establish a test suite before adding features.",
                    "evidence": "No test files detected in the repository.",
                    "file_path": None,
                    "line_start": None,
                    "severity": "high",
                    "confidence": 0.75,
                    "category": "test-plan",
                }
            )
        )
    return {"findings": findings, "summary": "Test plan drafted."}


def _docs(context: dict[str, Any]) -> dict[str, Any]:
    findings = []
    for module in context.get("undocumented_modules", []):
        symbols = ", ".join((module.get("missing") or [])[:5])
        findings.append(
            _to_finding(
                {
                    "claim": f"Document the public API of {module.get('file_path')}.",
                    "evidence": f"Missing docstrings for: {symbols}.",
                    "file_path": module.get("file_path"),
                    "line_start": 1,
                    "severity": "low",
                    "confidence": 0.6,
                    "category": "docstring-plan",
                }
            )
        )
    if context.get("has_readme") is False:
        findings.append(
            _to_finding(
                {
                    "claim": "Write a README with install, usage, and examples.",
                    "evidence": "No README found at the repository root.",
                    "file_path": None,
                    "line_start": None,
                    "severity": "medium",
                    "confidence": 0.7,
                    "category": "readme-plan",
                }
            )
        )
    return {"findings": findings, "summary": "Documentation plan drafted."}


def _architecture(context: dict[str, Any]) -> dict[str, Any]:
    findings = []
    for cycle in context.get("import_cycles", []):
        chain = " → ".join(cycle.get("cycle", []))
        findings.append(
            _to_finding(
                {
                    "claim": f"Break the import cycle: {chain}.",
                    "evidence": (
                        "Circular module imports prevent isolated testing and clean layering."
                    ),
                    "file_path": cycle.get("file_path"),
                    "line_start": cycle.get("line_start"),
                    "severity": "medium",
                    "confidence": 0.65,
                    "category": "layering",
                }
            )
        )
    for module in context.get("god_modules", []):
        findings.append(
            _to_finding(
                {
                    "claim": (
                        f"Split '{module.get('name')}' — imported by "
                        f"{module.get('fan_in')} modules."
                    ),
                    "evidence": (
                        "High fan-in indicates a hub that centralizes unrelated responsibilities."
                    ),
                    "file_path": module.get("file_path"),
                    "line_start": module.get("line_start"),
                    "severity": "medium",
                    "confidence": 0.6,
                    "category": "coupling",
                }
            )
        )
    return {"findings": findings, "summary": "Architecture review complete."}


_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "code": _code,
    "security": _security,
    "tests": _tests,
    "docs": _docs,
    "architecture": _architecture,
}
