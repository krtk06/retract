"""Shared context for analysis tool runners."""

from dataclasses import dataclass
from pathlib import Path

from app.services.ingestion import FileEntry


@dataclass
class ToolContext:
    analysis_id: int
    repo_root: Path
    files: list[FileEntry]
    loc: int

    @property
    def code_files(self) -> list[FileEntry]:
        return [f for f in self.files if f.lines > 0]
