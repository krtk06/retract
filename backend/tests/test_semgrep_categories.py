"""Semgrep rule → finding category.

A rule's namespace decides what kind of problem it reports. Getting this wrong
puts a finding in the wrong pillar and the wrong benchmark bucket: semgrep's
credential rules live under ``generic.secrets.*`` but also match the broader
``.security.`` test, so a hardcoded AWS key was filed as a ``vulnerability``
instead of a ``secret``.
"""

import pytest

from app.services.tools.semgrep import categorize_check


@pytest.mark.parametrize(
    ("check_id", "expected"),
    [
        # Secrets rules are checked first: they also contain ".security.".
        (
            "generic.secrets.security.detected-aws-access-key-id-value.detected-aws-access-key-id-value",
            "secret",
        ),
        ("generic.secrets.python.lang.security.hardcoded-password", "secret"),
        ("python.lang.security.audit.eval-detected", "vulnerability"),
        ("python.lang.security.injection.sql-injection", "vulnerability"),
        ("python.lang.security.xss.reflected-xss", "vulnerability"),
        # Non-security rules stay code smells.
        ("python.lang.best-practice.assert-on-string-literal", "code-smell"),
        ("python.lang.style.print-found", "code-smell"),
        # A bare or unknown id must not be promoted to a security finding.
        ("semgrep", "code-smell"),
        ("", "code-smell"),
    ],
)
def test_categorize_check(check_id: str, expected: str) -> None:
    assert categorize_check(check_id) == expected


def test_secrets_category_maps_to_the_security_pillar() -> None:
    """The category must exist in the pillar map or the finding scores nowhere."""
    from app.analysis_engine.scoring import CATEGORY_PILLAR

    assert CATEGORY_PILLAR["secret"] == "security"
    assert CATEGORY_PILLAR["vulnerability"] == "security"
