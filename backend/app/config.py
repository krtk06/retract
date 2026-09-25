"""Application settings, loaded from environment with prefix AI_INTEL_."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AI_INTEL_", env_file=".env", extra="ignore")

    environment: str = "dev"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/ai_intel"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_ttl_seconds: int = 7 * 24 * 3600
    auth_cookie_name: str = "ai_intel_token"
    auth_cookie_secure: bool = False

    github_client_id: str = ""
    github_client_secret: str = ""
    github_oauth_redirect_uri: str = "http://localhost:8000/api/auth/github/callback"
    frontend_url: str = "http://localhost:5173"

    dev_login: bool = False

    # Dev-only: allow local:// path URLs (for the seedy benchmark repo).
    allow_local_repos: bool = False

    data_dir: Path = Path("./data")

    # Analysis tool paths (blank → auto-detect: venv sibling, then PATH)
    semgrep_path: str = ""
    gitleaks_path: str = ""
    semgrep_config: str = "p/default"

    # Embeddings (RAG index). Provider: fastembed | openai | hashing.
    embedding_provider: str = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    max_chunks_per_analysis: int = 3000

    # LLM agents. Provider: openai (any OpenAI-compatible endpoint) | mock.
    # "mock" is a deterministic offline harness — never real analysis.
    llm_provider: str = "openai"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 120.0
    llm_max_retries: int = 2
    llm_temperature: float = 0.0
    llm_request_logprobs: bool = True
    agent_max_output_tokens: int = 4000
    # Input caps keep token usage bounded on large repos.
    agent_max_static_findings: int = 40
    agent_max_symbols: int = 60
    agent_max_context_chars: int = 12_000

    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
