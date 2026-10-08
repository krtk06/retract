"""D2 verdict schema: the contract the eve agent must satisfy for every claim.

The eve agent (see ``agent/agent/instructions.md``) emits findings as
JSON. This module is the server-side authority for that schema: it validates,
normalizes, and persists agent claims as ``status='hypothesis'`` so the trust
layer (verification, calibration, human approval) can re-check them before they
count toward a score. No LLM call happens here.
"""

from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.models import Finding, FindingStatus, Severity
from app.services.tools.findings import FindingDraft, persist_findings

EVE_VERIFIER = "llm:eve"
MAX_CLAIM_CHARS = 300
MAX_EVIDENCE_CHARS = 2000
_SEVERITIES = {s.value for s in Severity}


class VerdictFinding(BaseModel):
    """One agent claim, exactly as the eve agent must produce it."""

    claim: str = Field(min_length=3, max_length=MAX_CLAIM_CHARS)
    evidence: str = Field(min_length=3, max_length=MAX_EVIDENCE_CHARS)
    file_path: str | None = None
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    severity: str = "medium"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    category: str = Field(default="insight", max_length=64)
    # Optional fix, filed as this finding's remediation. The deterministic catalog
    # covers every category, so this earns its place only when the agent can name a
    # change the catalog's generic steps would miss.
    recommendation: str | None = Field(default=None, min_length=3, max_length=300)


class RecordResult(BaseModel):
    inserted: int
    dropped: int
    reasons: list[str] = Field(default_factory=list)


def normalize_path(path: str | None) -> str | None:
    if not path:
        return None
    cleaned = path.replace("\\", "/").lstrip("./")
    return cleaned or None


def to_draft(item: VerdictFinding, agent: str) -> FindingDraft:
    severity = item.severity if item.severity in _SEVERITIES else "medium"
    evidence_json: dict[str, Any] = {
        "claim": item.claim,
        "evidence": item.evidence,
        "source": "eve",
        "verifier": EVE_VERIFIER,
    }
    if item.recommendation:
        # Same shape the remediation endpoint writes, so an agent-authored fix and a
        # later-submitted one are read by the plan identically.
        evidence_json["remediation"] = {
            "action": item.recommendation[:300],
            "steps": [],
            "source": agent,
        }
    return FindingDraft(
        agent=agent,
        category=item.category or "insight",
        severity=Severity(severity),
        title=item.claim[:MAX_CLAIM_CHARS],
        description=item.evidence[:MAX_EVIDENCE_CHARS],
        file_path=normalize_path(item.file_path),
        line_start=item.line_start,
        line_end=item.line_end,
        evidence_json=evidence_json,
        verifier=EVE_VERIFIER,
        confidence=item.confidence,
        status=FindingStatus.HYPOTHESIS,
    )


def record_findings(
    session: Session, analysis_id: int, agent: str, findings: list[dict[str, Any]]
) -> RecordResult:
    """Validate and persist agent claims. Uncited claims are dropped, not stored."""
    drafts: list[FindingDraft] = []
    reasons: list[str] = []
    for raw in findings:
        try:
            item = VerdictFinding.model_validate(raw)
        except ValidationError as exc:
            reasons.append(f"invalid finding: {exc.errors()[0].get('msg', 'schema error')}")
            continue
        if not item.file_path:
            reasons.append(f"uncited claim dropped: {item.claim[:80]}")
            continue
        drafts.append(to_draft(item, agent))

    inserted = persist_findings(session, analysis_id, drafts)
    dropped = len(findings) - len(drafts)
    if inserted < len(drafts):
        dropped += len(drafts) - inserted
        reasons.append(f"{len(drafts) - inserted} duplicate claims dropped")
    return RecordResult(inserted=inserted, dropped=dropped, reasons=reasons)


def apply_triage(session: Session, analysis_id: int, triage: list[dict[str, Any]]) -> int:
    """Apply agent false-positive verdicts to referenced static findings."""
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
            "by": "eve",
        }
        finding.evidence_json = evidence
        applied += 1
    if applied:
        session.commit()
    return applied
