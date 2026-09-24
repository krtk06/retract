"""Finding persistence with in-run dedupe."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Finding, FindingStatus, Severity


@dataclass
class FindingDraft:
    agent: str
    category: str
    severity: Severity
    title: str
    description: str = ""
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    evidence_json: dict | None = None
    verifier: str = ""
    confidence: float = 1.0
    status: FindingStatus = FindingStatus.VERIFIED


def persist_findings(session: Session, analysis_id: int, drafts: list[FindingDraft]) -> int:
    """Insert findings, deduplicating within the analysis run.

    Dedupe key: (agent, category, file_path, line_start, title).
    Returns number of rows inserted.
    """
    seen: set[tuple] = set()
    existing = session.query(Finding).filter(Finding.analysis_id == analysis_id).all()
    for finding in existing:
        seen.add(
            (
                finding.agent,
                finding.category,
                finding.file_path,
                finding.line_start,
                finding.title,
            )
        )

    inserted = 0
    for draft in drafts:
        key = (draft.agent, draft.category, draft.file_path, draft.line_start, draft.title)
        if key in seen:
            continue
        seen.add(key)
        session.add(
            Finding(
                analysis_id=analysis_id,
                agent=draft.agent,
                category=draft.category,
                severity=draft.severity,
                title=draft.title,
                description=draft.description,
                file_path=draft.file_path,
                line_start=draft.line_start,
                line_end=draft.line_end,
                evidence_json=draft.evidence_json,
                verifier=draft.verifier,
                confidence=draft.confidence,
                status=draft.status,
            )
        )
        inserted += 1
    session.commit()
    return inserted
