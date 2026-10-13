"""GitHub URL parsing utilities."""

import re

_PATTERNS = [
    re.compile(r"^https?://github\.com/(?P<owner>[\w.-]+)/(?P<name>[\w.-]+?)(?:\.git)?/?$"),
    re.compile(r"^git@github\.com:(?P<owner>[\w.-]+)/(?P<name>[\w.-]+?)(?:\.git)?$"),
]


class InvalidRepoUrl(ValueError):
    pass


def parse_github_url(url: str) -> tuple[str, str]:
    """Return (owner, name) for a GitHub repo URL, or raise InvalidRepoUrl."""
    url = url.strip()
    for pattern in _PATTERNS:
        match = pattern.match(url)
        if match:
            return match.group("owner"), match.group("name")
    raise InvalidRepoUrl(f"Not a valid GitHub repository URL: {url}")


def canonical_url(owner: str, name: str) -> str:
    """The URL a repository is identified by, with its case folded.

    GitHub treats owner and repository names case-insensitively —
    ``https://github.com/krtk06/RETRACT`` resolves to the same repository as the
    lower-case form (checked with ``git ls-remote``). Without folding, the same
    repository submitted twice with different casing becomes two rows, two clones,
    and two analyses of identical code. The row keeps the case it was given, so the
    display is untouched; only the identity is normalized.
    """
    return f"https://github.com/{owner.lower()}/{name.lower()}"
