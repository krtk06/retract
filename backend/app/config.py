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

    # Shared secret the eve agent presents on service calls (X-Agent-Token).
    # Blank disables agent service auth entirely; production must set it.
    agent_token: str = ""

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

    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
