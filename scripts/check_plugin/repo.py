"""A read-only model of the repository tree that the checks inspect.

Checks take a Repo instead of a path so they never touch the filesystem or git
directly, and a test can point one at a temporary tree. Reads are cached,
because three content checks read every file and a text file is read once per
run.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from .config import SKILLS_REL, SKIP_DIRS


@dataclass(frozen=True)
class RepoFile:
    rel: str  # POSIX path relative to the repository root
    path: Path


@dataclass(frozen=True)
class JsonFile:
    """The result of reading a JSON file: its data, or why it couldn't be read."""

    data: Any = None
    error: str | None = None


@dataclass(frozen=True)
class Skill:
    name: str
    rel: str  # the skill directory, relative to the repository root

    @property
    def skill_md(self) -> str:
        return f"{self.rel}/SKILL.md"


@dataclass(frozen=True)
class GitResult:
    returncode: int
    stdout: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class Repo:
    def __init__(self, root: Path, base: str | None = None) -> None:
        self.root = Path(root)
        # The ref the version check diffs against. None skips that check.
        self.base = base
        self._text: dict[str, str | None] = {}
        self._json: dict[str, JsonFile] = {}
        self._files: dict[str, tuple[RepoFile, ...]] = {}

    def path(self, rel: str) -> Path:
        return self.root / rel

    def is_file(self, rel: str) -> bool:
        return self.path(rel).is_file()

    def is_dir(self, rel: str) -> bool:
        return self.path(rel).is_dir()

    def list_dir(self, rel: str) -> list[str]:
        """Returns the sorted entry names of a directory, or [] if it's missing."""
        directory = self.path(rel)
        return sorted(os.listdir(directory)) if directory.is_dir() else []

    def text(self, rel: str) -> str | None:
        """Returns a file's text, or None if it's missing or isn't UTF-8 text."""
        if rel not in self._text:
            self._text[rel] = _read_text(self.path(rel))
        return self._text[rel]

    def json(self, rel: str) -> JsonFile:
        if rel not in self._json:
            self._json[rel] = _read_json(self.path(rel))
        return self._json[rel]

    def files(self, sub: str = "") -> tuple[RepoFile, ...]:
        """Returns every file under `sub` in a stable order, skipping SKIP_DIRS."""
        if sub not in self._files:
            self._files[sub] = tuple(_walk(self.root, sub))
        return self._files[sub]

    def skills(self) -> list[Skill]:
        """Returns the skill directories. Stray files in skills/ aren't skills."""
        return [
            Skill(name, f"{SKILLS_REL}/{name}")
            for name in self.list_dir(SKILLS_REL)
            if self.is_dir(f"{SKILLS_REL}/{name}")
        ]

    def git(self, *args: str) -> GitResult:
        result = subprocess.run(
            ["git", "-C", str(self.root), *args], capture_output=True, text=True
        )
        return GitResult(result.returncode, result.stdout.strip())


def _read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
        if b"\x00" in data:
            return None
        return data.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _read_json(path: Path) -> JsonFile:
    if not path.is_file():
        return JsonFile(error="file is missing")
    try:
        return JsonFile(data=json.loads(path.read_text(encoding="utf-8")))
    except (ValueError, OSError) as exc:
        return JsonFile(error=f"can't parse as JSON: {exc}")


def _walk(root: Path, sub: str) -> Iterator[RepoFile]:
    for dirpath, dirnames, filenames in os.walk(root / sub):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            path = Path(dirpath) / name
            yield RepoFile(path.relative_to(root).as_posix(), path)
