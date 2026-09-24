"""Duplication runner — token-hash sliding window (jscpd-style, pure Python).

Normalizes identifiers and literals (type-2 clone detection) so that blocks
differing only in variable names still match.
"""

import hashlib
import re
from collections import defaultdict

from app.models import Severity
from app.services.tools.context import ToolContext
from app.services.tools.findings import FindingDraft

WINDOW = 8
MIN_WINDOW_LEN = 30
MAX_FINDINGS = 50

_COMMENT = re.compile(r"#.*$|//.*$")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUMBER = re.compile(r"\b\d+(?:\.\d+)?\b")
_STRING = re.compile(r'"[^"]*"|\'[^\']*\'')
_KEYWORDS = {
    "def",
    "class",
    "return",
    "if",
    "elif",
    "else",
    "for",
    "while",
    "import",
    "from",
    "as",
    "with",
    "try",
    "except",
    "finally",
    "raise",
    "pass",
    "break",
    "continue",
    "in",
    "not",
    "and",
    "or",
    "is",
    "lambda",
    "yield",
    "global",
    "function",
    "const",
    "let",
    "var",
    "true",
    "false",
    "null",
    "none",
    "void",
    "self",
    "cls",
    "int",
    "str",
    "float",
    "bool",
    "list",
    "dict",
    "set",
}


def _normalize_lines(source: str) -> list[str]:
    lines = []
    for raw in source.splitlines():
        cleaned = _COMMENT.sub("", raw)
        cleaned = _STRING.sub('"S"', cleaned)
        cleaned = _IDENT.sub(
            lambda match: match.group(0) if match.group(0).lower() in _KEYWORDS else "~",
            cleaned,
        )
        cleaned = _NUMBER.sub("#", cleaned)
        cleaned = re.sub(r"\s+", "", cleaned)
        lines.append(cleaned if len(cleaned) >= 5 else "")
    return lines


def _window_hashes(lines: list[str], start: int) -> str | None:
    window = lines[start : start + WINDOW]
    if len(window) < WINDOW or any(not line for line in window):
        return None
    joined = "\n".join(window)
    if len(joined) < MIN_WINDOW_LEN:
        return None
    return hashlib.sha1(joined.encode()).hexdigest()


def run_duplication(ctx: ToolContext) -> list[FindingDraft]:
    hash_locations: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for entry in ctx.code_files:
        path = ctx.repo_root / entry.path
        try:
            source = path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        lines = _normalize_lines(source)
        for i in range(len(lines) - WINDOW + 1):
            digest = _window_hashes(lines, i)
            if digest:
                hash_locations[digest].append((entry.path, i + 1))

    drafts: list[FindingDraft] = []
    reported_pairs: set[tuple[str, str]] = set()
    for locations in hash_locations.values():
        if len(locations) < 2:
            continue
        first_path, first_line = locations[0]
        for other_path, other_line in locations[1:]:
            pair_key = (
                (first_path, other_path) if first_path <= other_path else (other_path, first_path)
            )
            if pair_key in reported_pairs:
                continue
            reported_pairs.add(pair_key)
            same_file = first_path == other_path
            if same_file and abs(first_line - other_line) < WINDOW + 5:
                continue  # overlapping windows of the same block
            drafts.append(
                FindingDraft(
                    agent="static-analysis",
                    category="duplication",
                    severity=Severity.MEDIUM,
                    title=f"Duplicated {WINDOW}-line block ({other_path}:{other_line})",
                    description=(
                        f"Code block at {other_path}:{other_line} duplicates the block at "
                        f"{first_path}:{first_line} ({WINDOW} identical normalized lines). "
                        "Extract into a shared function."
                    ),
                    file_path=other_path,
                    line_start=other_line,
                    line_end=other_line + WINDOW - 1,
                    evidence_json={
                        "original": f"{first_path}:{first_line}",
                        "duplicate": f"{other_path}:{other_line}",
                    },
                    verifier="tool:duplication",
                )
            )
            if len(drafts) >= MAX_FINDINGS:
                return drafts
    return drafts
