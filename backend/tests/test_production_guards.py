"""Production must refuse to start on placeholder secrets.

Compose enforces the required variables with `${VAR:?}`, so `docker compose up`
already fails closed. The application on its own does not: started outside Docker
with `RETRACT_ENVIRONMENT=production` and no `RETRACT_JWT_SECRET`, it boots
happily and signs session cookies and eve agent tokens with the literal default
`change-me-in-production` — a value published in this repository, so anyone could
forge them. These tests pin the fail-closed behaviour that closes that gap.
"""

import pytest
from pydantic import ValidationError

from app.config import FORBIDDEN_JWT_SECRETS, Settings

GOOD_SECRET = "a-32-byte-secret-value-used-only-in-tests"

PLACEHOLDER_SECRET = "change-me-in-production"


def _production_settings(**overrides) -> Settings:
    base = {
        "environment": "production",
        "jwt_secret": GOOD_SECRET,
        "agent_token": "agent-service-token",
        "dev_login": False,
        "auth_cookie_secure": True,
    }
    base.update(overrides)
    return Settings(**base)


def test_production_accepts_real_secrets() -> None:
    assert _production_settings().environment == "production"


@pytest.mark.parametrize("secret", ["change-me", "", "x" * 31, *sorted(FORBIDDEN_JWT_SECRETS)])
def test_production_rejects_weak_or_published_jwt_secret(secret: str) -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        _production_settings(jwt_secret=secret)


def test_the_env_example_secret_is_rejected() -> None:
    """The value shipped in .env.example is long enough to pass a length check, so
    without an explicit deny-list it would sail into production unnoticed."""
    example = "change-me-to-a-long-random-string-at-least-32-bytes"
    assert len(example) >= 32
    assert example in FORBIDDEN_JWT_SECRETS


def test_production_accepts_a_32_character_secret() -> None:
    assert _production_settings(jwt_secret="x" * 32).jwt_secret == "x" * 32


def test_production_rejects_blank_agent_token() -> None:
    with pytest.raises(ValidationError, match="AGENT_TOKEN"):
        _production_settings(agent_token="")


def test_production_rejects_dev_login() -> None:
    with pytest.raises(ValidationError, match="DEV_LOGIN"):
        _production_settings(dev_login=True)


def test_every_problem_is_reported_at_once() -> None:
    """One restart should surface every misconfiguration, not one per attempt."""
    with pytest.raises(ValidationError) as excinfo:
        _production_settings(jwt_secret=PLACEHOLDER_SECRET, agent_token="")
    message = str(excinfo.value)
    assert "JWT_SECRET" in message
    assert "AGENT_TOKEN" in message


def test_development_tolerates_defaults() -> None:
    """Local development must keep working with nothing configured."""
    settings = Settings(environment="dev", jwt_secret=PLACEHOLDER_SECRET, agent_token="")
    assert settings.environment == "dev"
    assert settings.agent_token == ""


def test_environment_match_is_case_insensitive() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        _production_settings(environment="Production", jwt_secret=PLACEHOLDER_SECRET)


# --- A GitHub callback whose host cannot hand the cookie back -----------------
#
# The session cookie has no `Domain`, so it belongs to the host that issued it,
# and for a GitHub sign-in that host is the callback's — not the frontend's.
# `localhost` and `127.0.0.1` are the same machine and different hosts to a
# browser, so this pair boots fine and fails at every login instead: the callback
# succeeds, sets the cookie for `localhost`, and the app then reads every request
# without it. It is worth a boot-time refusal because the symptom points at GitHub.


def _dev_oauth_settings(**overrides) -> Settings:
    base = {
        "environment": "dev",
        "jwt_secret": GOOD_SECRET,
        "github_client_id": "Iv1.0123456789abcdef",
        "github_client_secret": "test-github-client-secret-not-real",
        "github_oauth_redirect_uri": "http://localhost:8110/api/auth/github/callback",
        "frontend_url": "http://localhost:5175",
    }
    return Settings(**{**base, **overrides})


def test_a_loopback_host_mismatch_is_refused() -> None:
    with pytest.raises(ValidationError, match="never sent back"):
        _dev_oauth_settings(frontend_url="http://127.0.0.1:5175")


def test_the_refusal_names_both_hosts() -> None:
    """The message has to say which way round to fix it."""
    with pytest.raises(ValidationError) as excinfo:
        _dev_oauth_settings(frontend_url="http://127.0.0.1:5175")
    message = str(excinfo.value)
    assert "localhost" in message
    assert "127.0.0.1" in message


def test_matching_loopback_hosts_boot() -> None:
    """The common case — both on localhost — must not be caught by this."""
    assert _dev_oauth_settings().frontend_url == "http://localhost:5175"


def test_the_check_is_skipped_without_an_oauth_app() -> None:
    """A dev machine with no OAuth configured cannot trip this."""
    settings = Settings(
        environment="dev",
        jwt_secret=GOOD_SECRET,
        frontend_url="http://127.0.0.1:5175",
        github_client_id="",
        github_oauth_redirect_uri="",
    )
    assert settings.frontend_url == "http://127.0.0.1:5175"


def test_production_is_exempt() -> None:
    """One nginx serves both in production, so the two hosts are one by design."""
    settings = Settings(
        environment="production",
        jwt_secret=GOOD_SECRET,
        agent_token="agent-service-token",
        github_client_id="Iv1.0123456789abcdef",
        github_oauth_redirect_uri="https://app.example.com/api/auth/github/callback",
        frontend_url="https://frontend.example.com",
        dev_login=False,
        auth_cookie_secure=True,
    )
    assert settings.frontend_url == "https://frontend.example.com"


def test_a_real_host_mismatch_is_not_this_guard() -> None:
    """Only the loopback trap is ours to catch; a split deployment is not."""
    settings = _dev_oauth_settings(
        github_oauth_redirect_uri="https://api.example.com/api/auth/github/callback",
        frontend_url="http://127.0.0.1:5175",
    )
    assert settings.frontend_url == "http://127.0.0.1:5175"


# --- The guards that were missing, and the spelling that used to bypass them ---


@pytest.mark.parametrize(
    "env", ["dev", "development", "local", "test", "testing", "ci", "DEV", " Dev "]
)
def test_development_environments_are_not_guarded(env: str) -> None:
    """The relaxed set is explicit and matched case-insensitively."""
    settings = Settings(
        environment=env,
        jwt_secret=PLACEHOLDER_SECRET,
        agent_token="",
        dev_login=True,
        auth_cookie_secure=False,
    )
    assert settings.is_development


@pytest.mark.parametrize(
    "env", ["prod", "staging", "production", "Production", "PRODUCTION", "production "]
)
def test_anything_that_is_not_a_known_dev_environment_is_guarded(env: str) -> None:
    """`prod` and `PRODUCTION ` used to sail past every check, because one exact
    spelling was the entire lock. Now the guard is the default and development is
    the opt-in."""
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        _production_settings(environment=env, jwt_secret=PLACEHOLDER_SECRET)


def test_production_rejects_an_insecure_session_cookie() -> None:
    """Without `Secure`, the cookie is sent over plaintext HTTP to the same host."""
    with pytest.raises(ValidationError, match="AUTH_COOKIE_SECURE"):
        _production_settings(auth_cookie_secure=False)


def test_production_rejects_a_wildcard_cors_origin() -> None:
    """`*` with credentials makes Starlette reflect any origin, so every site can
    call the API as the signed-in user."""
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        _production_settings(cors_origins="*")


def test_production_rejects_a_wildcard_among_listed_origins() -> None:
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        _production_settings(cors_origins="https://app.example.com,*")


def test_production_rejects_local_repo_reading() -> None:
    """`local://` reads arbitrary host paths; it must not be reachable in production."""
    with pytest.raises(ValidationError, match="ALLOW_LOCAL_REPOS"):
        _production_settings(allow_local_repos=True)


def test_the_new_problems_are_reported_together() -> None:
    with pytest.raises(ValidationError) as excinfo:
        _production_settings(auth_cookie_secure=False, cors_origins="*", allow_local_repos=True)
    message = str(excinfo.value)
    assert "AUTH_COOKIE_SECURE" in message
    assert "CORS_ORIGINS" in message
    assert "ALLOW_LOCAL_REPOS" in message


def test_production_accepts_the_full_correct_configuration() -> None:
    """The guards must not reject a properly configured deployment."""
    settings = _production_settings(
        cors_origins="https://app.example.com",
        allow_local_repos=False,
    )
    assert settings.is_production
    assert settings.auth_cookie_secure
