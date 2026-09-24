"""Repository ingestion: shallow clone, commit info, language detection, file inventory."""

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

MAX_INVENTORY_FILES = 5000
MAX_FILE_SIZE_BYTES = 1_000_000

EXTENSION_LANGUAGES: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".rb": "Ruby",
    ".php": "PHP",
    ".c": "C",
    ".h": "C/C++",
    ".cpp": "C++",
    ".cc": "C++",
    ".cs": "C#",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".sh": "Shell",
    ".sql": "SQL",
    ".html": "HTML",
    ".css": "CSS",
    ".md": "Markdown",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
}

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".tox"}


@dataclass
class FileEntry:
    path: str
    size: int
    ext: str
    lines: int = 0


@dataclass
class IngestionResult:
    dest: Path
    commit_sha: str
    branch: str
    files: list[FileEntry] = field(default_factory=list)
    languages: dict[str, int] = field(default_factory=dict)
    total_files: int = 0
    total_loc: int = 0
    truncated: bool = False


def is_code_file(ext: str) -> bool:
    return ext in EXTENSION_LANGUAGES and EXTENSION_LANGUAGES[ext] not in {
        "Markdown",
        "YAML",
        "TOML",
        "JSON",
        "SQL",
        "HTML",
        "CSS",
    }


def count_lines(path: Path) -> int:
    try:
        if path.stat().st_size > MAX_FILE_SIZE_BYTES:
            return 0
        with path.open("rb") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return 0


def _git(*args: str, cwd: Path | None = None) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def clone_repo(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        # Clean previous attempt for idempotent re-runs.
        import shutil

        shutil.rmtree(dest)
    _git("clone", "--depth", "1", url, str(dest))


def repo_commit(dest: Path) -> str:
    return _git("rev-parse", "HEAD", cwd=dest)


def repo_branch(dest: Path) -> str:
    return _git("rev-parse", "--abbrev-ref", "HEAD", cwd=dest)


def build_inventory(root: Path) -> tuple[list[FileEntry], int, bool]:
    """Walk the repo; return (entries, total_files, truncated)."""
    entries: list[FileEntry] = []
    total = 0
    truncated = False
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in filenames:
            total += 1
            if len(entries) >= MAX_INVENTORY_FILES:
                truncated = True
                continue
            full = Path(dirpath) / filename
            try:
                size = full.stat().st_size
            except OSError:
                continue
            rel = full.relative_to(root).as_posix()
            ext = full.suffix.lower()
            lines = count_lines(full) if is_code_file(ext) else 0
            entries.append(FileEntry(path=rel, size=size, ext=ext, lines=lines))
    return entries, total, truncated


def detect_languages(files: list[FileEntry]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in files:
        language = EXTENSION_LANGUAGES.get(entry.ext)
        if language:
            counts[language] = counts.get(language, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))


def ingest(url: str, dest: Path) -> IngestionResult:
    if url.startswith("local://"):
        return _ingest_local(url, dest)
    clone_repo(url, dest)
    files, total, truncated = build_inventory(dest)
    return IngestionResult(
        dest=dest,
        commit_sha=repo_commit(dest),
        branch=repo_branch(dest),
        files=files,
        languages=detect_languages(files),
        total_files=total,
        total_loc=sum(f.lines for f in files),
        truncated=truncated,
    )


def _ingest_local(url: str, dest: Path) -> IngestionResult:
    """Dev-only ingestion from a local directory (local://path)."""
    import shutil

    source = Path(url.removeprefix("local://"))
    if not source.is_dir():
        raise RuntimeError(f"Local repository path does not exist: {source}")
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns(".git"))
    files, total, truncated = build_inventory(dest)
    return IngestionResult(
        dest=dest,
        commit_sha="local",
        branch="local",
        files=files,
        languages=detect_languages(files),
        total_files=total,
        total_loc=sum(f.lines for f in files),
        truncated=truncated,
    )
