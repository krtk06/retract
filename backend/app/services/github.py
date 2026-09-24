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
    return f"https://github.com/{owner}/{name}"
