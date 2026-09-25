"""Agent registry."""

from app.agents.architecture_agent import ArchitectureAgent
from app.agents.base import AgentContext, AgentRunResult, BaseAgent
from app.agents.code_agent import CodeAgent
from app.agents.docs_agent import DocsAgent
from app.agents.security_agent import SecurityAgent
from app.agents.test_agent import TestAgent

# Each agent reads the shared LLM client from app.llm.client unless one is injected.
AGENT_CLASSES: dict[str, type[BaseAgent]] = {
    "code": CodeAgent,
    "security": SecurityAgent,
    "tests": TestAgent,
    "docs": DocsAgent,
    "architecture": ArchitectureAgent,
}

__all__ = [
    "AGENT_CLASSES",
    "AgentContext",
    "AgentRunResult",
    "BaseAgent",
    "CodeAgent",
    "SecurityAgent",
    "TestAgent",
    "DocsAgent",
    "ArchitectureAgent",
]
