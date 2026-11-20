"""files: the directory's limits on what a plugin may contain."""

from __future__ import annotations

import os
import re
from typing import Iterator

from ..config import (
    FILE_CAP,
    FONT_EXT,
    IMAGE_EXT,
    JUNK_NAMES,
    MANIFEST_REL,
    MAX_FILES,
    MIN_README_WORDS,
    PLUGIN_REL,
    PLUGIN_README_REL,
    TEXT_CAP,
)
from ..report import Issue
from ..repo import Repo, RepoFile

_WINDOWS_INVALID_NAME = re.compile(r'[:<>"|?*]|[. ]$')
_GIT_FILTER = re.compile(r"export-ignore|export-subst|\bfilter=")
_CODE_FENCE = re.compile(r"```.*?```", re.S)
_LFS_POINTER = "version https://git-lfs.github.com/spec"


def check_files(repo: Repo) -> Iterator[Issue]:
    manifest = repo.json(MANIFEST_REL).data
    if isinstance(manifest, dict) and not manifest.get("license"):
        yield Issue(MANIFEST_REL, "license is not set")

    plugin_files = repo.files(PLUGIN_REL)
    for file in plugin_files:
        yield from _file_issues(repo, file)
    if len(plugin_files) > MAX_FILES:
        yield Issue(
            PLUGIN_REL, f"{len(plugin_files)} files, over the {MAX_FILES} file limit"
        )

    # A .gitattributes anywhere can change what `git archive` and a marketplace
    # clone ship, so it's checked across the whole repository.
    for file in repo.files():
        if os.path.basename(file.rel) == ".gitattributes":
            if _GIT_FILTER.search(repo.text(file.rel) or ""):
                yield Issue(
                    file.rel,
                    "uses export-ignore, export-subst or filter (including Git LFS)",
                )

    yield from _readme_issues(repo)


def _file_issues(repo: Repo, file: RepoFile) -> Iterator[Issue]:
    rel = file.rel
    name = os.path.basename(rel)
    extension = os.path.splitext(name)[1].lower()
    if name.lower() in JUNK_NAMES or "__MACOSX" in rel.split("/"):
        yield Issue(rel, "OS junk file")
    if _WINDOWS_INVALID_NAME.search(name):
        yield Issue(rel, "file name isn't valid on Windows")
    if file.path.is_symlink():
        yield Issue(rel, "symlink; commit a regular file")
        return
    size = file.path.stat().st_size
    if size > FILE_CAP:
        yield Issue(rel, f"{size} bytes, over the 5 MiB limit")
    if extension in IMAGE_EXT or extension in FONT_EXT:
        return
    if size >= TEXT_CAP:
        yield Issue(
            rel, f"{size} bytes, at or over the 256 KiB limit for non-image files"
        )
    text = repo.text(rel)
    if text is None:
        yield Issue(
            rel,
            "binary file; only PNG, JPEG, GIF, WebP, SVG and font files are allowed",
        )
    elif text.startswith(_LFS_POINTER):
        yield Issue(rel, "Git LFS pointer file")


def _readme_issues(repo: Repo) -> Iterator[Issue]:
    readme = repo.text(PLUGIN_README_REL)
    if readme is None:
        yield Issue(PLUGIN_README_REL, "plugin README is missing")
        return
    words = len(_CODE_FENCE.sub("", readme).split())
    if words < MIN_README_WORDS:
        yield Issue(
            PLUGIN_README_REL,
            f"{words} words outside code blocks, need at least {MIN_README_WORDS}",
        )
