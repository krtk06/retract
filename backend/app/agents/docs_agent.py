"""Docs Agent — README and docstring gaps turned into a documentation plan."""

from typing import Any

from app.agents.base import AgentContext, BaseAgent
from app.models import Finding


class DocsAgent(BaseAgent):
    name = "docs"

    def build_instruction(self) -> str:
        return (
            "Produce a concise documentation plan: for each undocumented module list the "
            "public symbols that need docstrings and what each docstring should explain; "
            "if the README is missing or thin, state the sections to add. Cite file_path. "
            "At most 6 findings."
        )

    def build_context(self, ctx: AgentContext) -> dict[str, Any]:
        findings = (
            ctx.session.query(Finding)
            .filter(
                Finding.analysis_id == ctx.analysis_id,
                Finding.category.in_(("docstring", "readme")),
            )
            .all()
        )
        undocumented = []
        for finding in findings:
            if finding.category != "docstring":
                continue
            evidence = finding.evidence_json or {}
            undocumented.append(
                {
                    "file_path": finding.file_path,
                    "documented": evidence.get("documented"),
                    "public_symbols": evidence.get("public_symbols", []),
                    "missing": evidence.get("missing", []),
                }
            )
        return {
            "undocumented_modules": undocumented,
            "has_readme": not any(finding.category == "readme" for finding in findings),
            "readme_gaps": [finding.title for finding in findings if finding.category == "readme"],
        }
