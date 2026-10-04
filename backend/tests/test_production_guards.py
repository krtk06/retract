"""Production must refuse to start on placeholder secrets.

Compose enforces the required variables with `${VAR:?}`, so `docker compose up`
already fails closed. The application on its own does not: started outside Docker
with `AI_INTEL_ENVIRONMENT=production` and no `AI_INTEL_JWT_SECRET`, it boots
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
    }
    base.update(overrides)
    return Settings(**base)


def test_production_accepts_real_secrets() -> None:
    assert _production_settings().environment == "production"


@pytest.mark.parametrize(
    "secret", ["change-me", "", "x" * 31, *sorted(FORBIDDEN_JWT_SECRETS)]
)
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