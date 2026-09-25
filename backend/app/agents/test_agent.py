"""Test Agent — turns coverage/presence data into a prioritized test plan (D7).

Decision D7: this agent does not generate tests that are trusted by default. It
reports which modules lack tests and proposes what should be covered, grounded
in the deterministic test-presence analysis.
"""

from typing import Any

from app.agents.base import AgentContext, BaseAgent
from app.models import Finding


class TestAgent(BaseAgent):
    name = "tests"

    def build_instruction(self) -> str:
        return (
            "For each untested module, write a concrete, prioritized test plan: what to "
            "cover (happy path, invalid input, exception branches) and why. Cite file_path. "
            "Do not emit test code; emit planned coverage. At most 6 findings."
        )

    def build_context(self, ctx: AgentContext) -> dict[str, Any]:
        findings = (
            ctx.session.query(Finding)
            .filter(
                Finding.analysis_id == ctx.analysis_id,
                Finding.category.in_(("missing-tests", "coverage")),
            )
            .all()
        )
        untested = [
            {
                "package": finding.file_path or finding.title,
                "title": finding.title,
                "severity": finding.severity.value,
            }
            for finding in findings
            if finding.category == "missing-tests"
        ]
        has_tests = not any(finding.category == "coverage" for finding in findings)
        return {
            "untested_modules": untested,
            "repo_has_tests": has_tests,
            "coverage_note": (
                "No coverage tool run for this analysis; test presence is inferred from "
                "test directories and imports."
            ),
        }
