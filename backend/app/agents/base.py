"""Agent framework: verdict schema (D2), validation, repair retry, cost ledger.

Every agent follows the same contract:
  1. gather deterministic inputs (tool findings, graph facts, coverage data);
  2. ask the LLM for findings in a strict JSON schema with mandatory citations;
  3. validate each finding; on failure, one repair retry, then drop invalid items;
  4. persist survivors as ``status='hypothesis'`` (LLM-only, needs verification).
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.analysis_engine import graph
from app.config import get_settings
from app.llm.client import LLMClient, LLMError, parse_json_object
from app.models import Finding, FindingStatus, Severity
from app.services.tools.findings import FindingDraft

logger = logging.getLogger(__name__)


class AgentFinding(BaseModel):
    """The D2 verdict schema an LLM must satisfy for every claim."""

    claim: str = Field(min_length=3, description="What the agent asserts")
    evidence: str = Field(min_length=3, description="Why it believes this (must reference code)")
    file_path: str | None = Field(default=None, description="Cited repository-relative path")
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    severity: str = "medium"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    category: str = "insight"


class AgentOutput(BaseModel):
    findings: list[AgentFinding] = Field(default_factory=list)
    triage: list[dict[str, Any]] = Field(default_factory=list)
    summary: str = ""


OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "evidence": {"type": "string"},
                    "file_path": {"type": ["string", "null"]},
                    "line_start": {"type": ["integer", "null"]},
                    "line_end": {"type": ["integer", "null"]},
                    "severity": {
                        "type": "string",
                        "enum": ["info", "low", "medium", "high", "critical"],
                    },
                    "confidence": {"type": "number"},
                    "category": {"type": "string"},
                },
                "required": ["claim", "evidence", "severity"],
            },
        },
        "triage": {"type": "array", "items": {"type": "object"}},
        "summary": {"type": "string"},
    },
    "required": ["findings"],
}

_SEVERITY = {s.value for s in Severity}


@dataclass
class AgentRunResult:
    agent: str
    findings: list[FindingDraft] = field(default_factory=list)
    triage: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    dropped: int = 0
    repaired: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = ""
    provider: str = ""
    error: str | None = None

    @property
    def cost(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "provider": self.provider,
            "model": self.model,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "findings": len(self.findings),
            "dropped": self.dropped,
            "repaired": self.repaired,
            "error": self.error,
        }


@dataclass
class AgentContext:
    analysis_id: int
    repo_root: Path
    session: Session

    def graph_summary(self) -> dict[str, Any]:
        return graph.summary(self.session, self.analysis_id)


class BaseAgent:
    name = "agent"
    system_prompt = (
        "You are a precise software engineering analyst. Only report issues you can "
        "justify from the provided context. Every finding MUST cite a repository file "
        "path and line number taken from the context; never invent paths. Return only "
        "JSON matching the requested schema."
    )

    def __init__(self, llm: LLMClient | None = None) -> None:
        if llm is None:
            from app.llm.client import get_llm_client

            llm = get_llm_client()
        self.llm = llm

    # --- extension points -------------------------------------------------
    def build_context(self, ctx: AgentContext) -> dict[str, Any]:
        raise NotImplementedError

    def build_instruction(self) -> str:
        return "Analyze the context and return findings."

    # --- shared pipeline --------------------------------------------------
    def run(self, ctx: AgentContext) -> AgentRunResult:
        settings = get_settings()
        result = AgentRunResult(agent=self.name, model=self.llm.model, provider=self.llm.name)
        try:
            context = self.build_context(ctx)
        except Exception as exc:  # noqa: BLE001 — a bad context must not kill the run
            logger.exception("agent %s failed building context", self.name)
            result.error = f"context error: {exc}"
            return result

        payload = {**context, "agent": self.name, "instruction": self.build_instruction()}
        user = self._render_user(payload)
        try:
            response = self.llm.complete(
                system=self.system_prompt,
                user=user,
                json_schema=OUTPUT_SCHEMA,
                schema_name=f"{self.name}_output",
            )
        except LLMError as exc:
            result.error = str(exc)
            return result

        result.tokens_in += response.tokens_in
        result.tokens_out += response.tokens_out
        result.model = response.model or self.llm.model

        output = self._parse_and_validate(response.content, result)
        if output is None:
            # One repair attempt with an explicit error message.
            repaired_output = self._repair(user, response.content, result)
            if repaired_output is None:
                return result
            output = repaired_output

        result.summary = output.summary
        result.triage = [t for t in output.triage if isinstance(t, dict)]
        result.findings = self._to_drafts(output.findings, response.logprob_confidence)
        _ = settings  # context caps applied in build_context
        return result

    def _parse_and_validate(self, content: str, result: AgentRunResult) -> AgentOutput | None:
        try:
            data = parse_json_object(content)
            output = AgentOutput.model_validate(data)
        except (LLMError, ValidationError) as exc:
            logger.warning("agent %s produced invalid output: %s", self.name, exc)
            return None
        result.dropped += 0
        return output

    def _repair(self, user: str, bad_content: str, result: AgentRunResult) -> AgentOutput | None:
        repair_prompt = (
            f"{user}\n\nYour previous response was invalid or did not match the schema.\n"
            f"Previous response:\n{bad_content[:2000]}\n\n"
            "Return ONLY a corrected JSON object matching the schema."
        )
        try:
            response = self.llm.complete(
                system=self.system_prompt,
                user=repair_prompt,
                json_schema=OUTPUT_SCHEMA,
                schema_name=f"{self.name}_repair",
            )
            data = parse_json_object(response.content)
            output = AgentOutput.model_validate(data)
        except (LLMError, ValidationError) as exc:
            logger.warning("agent %s repair failed, dropping run: %s", self.name, exc)
            result.error = "unparseable output after repair"
            return None
        result.repaired += 1
        result.tokens_in += response.tokens_in
        result.tokens_out += response.tokens_out
        return output

    def _to_drafts(
        self, findings: list[AgentFinding], logprob_confidence: float | None
    ) -> list[FindingDraft]:
        drafts: list[FindingDraft] = []
        for item in findings:
            severity_value = item.severity if item.severity in _SEVERITY else "medium"
            file_path = _normalize_path(item.file_path)
            confidence = item.confidence
            if logprob_confidence is not None:
                confidence = round((confidence + logprob_confidence) / 2, 3)
            drafts.append(
                FindingDraft(
                    agent=self.name,
                    category=item.category or "insight",
                    severity=Severity(severity_value),
                    title=item.claim[:300],
                    description=item.evidence[:2000],
                    file_path=file_path,
                    line_start=item.line_start,
                    line_end=item.line_end,
                    evidence_json={
                        "claim": item.claim,
                        "evidence": item.evidence,
                        "model": self.llm.model,
                        "provider": self.llm.name,
                        "logprob_confidence": logprob_confidence,
                    },
                    verifier=f"llm:{self.llm.name}",
                    confidence=max(0.0, min(1.0, confidence)),
                    status=FindingStatus.HYPOTHESIS,
                )
            )
        return drafts

    @staticmethod
    def _render_user(payload: dict[str, Any]) -> str:
        import json

        settings = get_settings()
        body = json.dumps(payload, default=str)
        if len(body) > settings.agent_max_context_chars:
            body = body[: settings.agent_max_context_chars] + "... [truncated]"
        return f"Context (JSON):\n{body}"


def _normalize_path(path: str | None) -> str | None:
    if not path:
        return None
    cleaned = path.replace("\\", "/").lstrip("./")
    return cleaned or None


def apply_triage(session: Session, analysis_id: int, triage: list[dict[str, Any]]) -> int:
    """Apply Code Agent false-positive verdicts to referenced static findings."""
    applied = 0
    for verdict in triage:
        finding_id = verdict.get("finding_id")
        decision = str(verdict.get("verdict", "")).lower()
        if not finding_id or decision not in ("false-positive", "false_positive", "dismiss"):
            continue
        finding = session.get(Finding, int(finding_id))
        if finding is None or finding.analysis_id != analysis_id:
            continue
        finding.status = FindingStatus.DISMISSED
        evidence = dict(finding.evidence_json or {})
        evidence["triage"] = {
            "verdict": "false-positive",
            "reasoning": str(verdict.get("reasoning", ""))[:1000],
            "confidence": verdict.get("confidence"),
            "by": "llm",
        }
        finding.evidence_json = evidence
        applied += 1
    if applied:
        session.commit()
    return applied
