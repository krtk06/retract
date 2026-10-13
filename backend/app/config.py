"""Application settings, loaded from environment with prefix RETRACT_."""

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Published in this repository, so it must never be usable as a real secret. Both the
# code default and the value shipped in .env.example are listed: the example is the
# one most likely to reach production by being copied without being edited, and it is
# long enough to satisfy a length check on its own.
FORBIDDEN_JWT_SECRETS = frozenset(
    {
        "change-me-in-production",
        "change-me-to-a-long-random-string-at-least-32-bytes",
    }
)

# Short enough to be brute-forced or, worse, guessed. HS256 keys want >=256 bits.
MIN_JWT_SECRET_CHARS = 32

# Environments that relax the production guards. Membership is opt-in on purpose:
# anything not listed here — including a value nobody anticipated, like `prod` or
# `staging` — is treated as production and must satisfy every guard below. The
# inverse (guarding only when `environment == "production"`) is what let `prod`
# and `PRODUCTION ` sail past every check, since one exact spelling was the whole
# lock. Failing closed on an unrecognised name costs a developer a boot error and
# costs a misconfigured deployment nothing.
DEVELOPMENT_ENVIRONMENTS = frozenset({"dev", "development", "local", "test", "testing", "ci"})

# The two spellings of this machine. They are the same host to a program and
# different hosts to a browser: a cookie set on one is never sent to the other.
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def is_loopback(hostname: str | None) -> bool:
    """Whether a hostname can only ever refer to the machine it is used on."""
    if not hostname:
        return False
    return hostname.strip("[]") in LOOPBACK_HOSTS


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RETRACT_", env_file=".env", extra="ignore")

    environment: str = "dev"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/ai_intel"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_ttl_seconds: int = 7 * 24 * 3600
    auth_cookie_name: str = "ai_intel_token"
    auth_cookie_secure: bool = False

    # Shared secret the eve agent presents on service calls (X-Agent-Token).
    # Blank denies every agent call rather than permitting open access — see
    # deps._agent_user — but production must set it, so the agent can talk to the API.
    agent_token: str = ""

    github_client_id: str = ""
    github_client_secret: str = ""
    github_oauth_redirect_uri: str = "http://localhost:8000/api/auth/github/callback"
    frontend_url: str = "http://localhost:5173"

    dev_login: bool = False

    # Outbound email, used only for address verification. Blank means "no transport":
    # development and tests log the link instead of sending it.
    #   smtp://user%40gmail.com:app-password@smtp.gmail.com:587   (STARTTLS)
    #   smtps://user%40gmail.com:app-password@smtp.gmail.com:465  (implicit TLS)
    smtp_url: str = ""
    mail_from: str = "Retract <no-reply@localhost>"
    email_verification_ttl_seconds: int = 24 * 3600

    # Fixed-window limiter on login/register/analyze (see app/rate_limit.py).
    # On by default; tests turn it off so they are not limited by their own volume.
    rate_limit_enabled: bool = True

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

    @property
    def is_development(self) -> bool:
        """Whether the guards are relaxed for this environment.

        Case- and whitespace-insensitive, and the single definition every caller
        uses — the OAuth loopback allowance in ``routers/auth.py`` compared the raw
        string to ``"production"`` and so treated ``Production`` as development,
        which is the drift this property exists to stop.
        """
        return self.environment.strip().lower() in DEVELOPMENT_ENVIRONMENTS

    @property
    def is_production(self) -> bool:
        """Everything that is not an explicit development environment (fail closed)."""
        return not self.is_development

    @model_validator(mode="after")
    def _refuse_insecure_production(self) -> "Settings":
        """Fail closed in production rather than boot on placeholder secrets.

        `docker compose up` already refuses to start without these (`:?` in the
        compose files), but the app is also run directly — uvicorn in CI, a
        developer's shell, a one-off analysis box. Without this check, production
        there starts silently and signs session cookies and eve tokens with a
        secret published in this repository.

        Development is untouched, so a fresh clone still runs with zero config.
        """
        if not self.is_production:
            return self

        problems: list[str] = []
        if len(self.jwt_secret) < MIN_JWT_SECRET_CHARS:
            problems.append(
                f"RETRACT_JWT_SECRET must be at least {MIN_JWT_SECRET_CHARS} characters "
                f"(got {len(self.jwt_secret)})"
            )
        if self.jwt_secret in FORBIDDEN_JWT_SECRETS:
            problems.append(
                "RETRACT_JWT_SECRET is a published placeholder value "
                "(the code default or the .env.example value); generate a real one"
            )
        if not self.agent_token:
            problems.append("RETRACT_AGENT_TOKEN must be set so the agent can reach the API")
        if self.dev_login:
            problems.append("RETRACT_DEV_LOGIN must be disabled (0) in production")
        # Not merely hygiene: without `Secure`, the session cookie is sent over
        # plaintext HTTP to the same host, so any downgrade leaks it. The prod
        # compose sets it, but the guard is what protects the deployment that does
        # not use that file.
        if not self.auth_cookie_secure:
            problems.append(
                "RETRACT_AUTH_COOKIE_SECURE must be 1 so the session cookie is HTTPS-only"
            )
        # `*` with credentials makes Starlette reflect any origin, so every site can
        # read authenticated responses as a signed-in user.
        if "*" in self.cors_origin_list:
            problems.append(
                "RETRACT_CORS_ORIGINS must list explicit origins, not '*': "
                "with credentials allowed, '*' lets any site call the API as the user"
            )
        # Reading arbitrary host paths is a development convenience; in production it
        # is a filesystem-disclosure primitive, and nothing else here would object.
        if self.allow_local_repos:
            problems.append("RETRACT_ALLOW_LOCAL_REPOS must be 0 in production")

        if problems:
            raise ValueError("refusing to start in production: " + "; ".join(problems))
        return self

    @model_validator(mode="after")
    def _refuse_a_mismatched_oauth_host(self) -> "Settings":
        """Refuse a GitHub callback that cannot hand its cookie back.

        The session cookie carries no ``Domain`` attribute, so it is scoped to the
        host that issued it — and for a GitHub sign-in that host is the one in
        ``RETRACT_GITHUB_OAUTH_REDIRECT_URI``, not the frontend. A mismatch is
        therefore not a cosmetic one: the callback succeeds, sets the cookie for
        ``localhost``, and every later request from ``127.0.0.1`` arrives without
        it. The user is bounced back to the login page by a sign-in that worked,
        which reads as "GitHub sign-in is broken" and sends you looking at GitHub
        rather than at the hostnames.

        Production is exempt only because there the two are the same origin by
        construction (one nginx serves both); the check below is a development
        guard for the loopback spelling trap, which is the one case that differs
        between the callback and the page by accident.
        """
        if not self.github_client_id or not self.github_oauth_redirect_uri:
            return self
        if self.is_production:
            return self
        callback_host = urlsplit(self.github_oauth_redirect_uri).hostname
        frontend_host = urlsplit(self.frontend_url).hostname
        if not callback_host or not frontend_host or callback_host == frontend_host:
            return self
        if not (is_loopback(callback_host) and is_loopback(frontend_host)):
            return self

        raise ValueError(
            f"the GitHub callback host ({callback_host}) does not match the frontend host "
            f"({frontend_host}), so the session cookie set by the callback is never sent "
            f"back and every GitHub sign-in silently fails. Open the app on "
            f"http://{callback_host}:<frontend port>, or set "
            f"RETRACT_GITHUB_OAUTH_REDIRECT_URI to a URL on {frontend_host} and register "
            f"that same URL as the callback URL on the GitHub OAuth app."
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
