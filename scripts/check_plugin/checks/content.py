"""credentials, naming and denylist: rules about what text a file may contain."""

from __future__ import annotations

import re
from typing import Iterator

from ..config import (
    CONTENT_CHECK_SKIP_PREFIXES,
    CREDENTIAL_PATTERNS,
    DENYLIST,
    PLUGIN_REL,
)
from ..report import Issue
from ..repo import Repo

_FORMERLY_EMBRACE = re.compile(r"formerly\s+embrace", re.I)


def _text_files(repo: Repo) -> Iterator[tuple[str, str]]:
    """Yields (path, text) for each text file the content checks should read."""
    for file in repo.files():
        if file.rel.startswith(CONTENT_CHECK_SKIP_PREFIXES):
            continue
        text = repo.text(file.rel)
        if text is not None:
            yield file.rel, text


def check_credentials(repo: Repo) -> Iterator[Issue]:
    """No file reads a credential from the environment or holds a literal one."""
    for rel, text in _text_files(repo):
        for pattern in CREDENTIAL_PATTERNS:
            if pattern.regex.search(text):
                yield Issue(rel, f"contains {pattern.description}")


def check_naming(repo: Repo) -> Iterator[Issue]:
    """The 'formerly Embrace' qualifier appears at most once per file."""
    for rel, text in _text_files(repo):
        count = len(_FORMERLY_EMBRACE.findall(text))
        if count > 1:
            yield Issue(
                rel, f"says 'formerly Embrace' {count} times; once per file at most"
            )


def check_denylist(repo: Repo) -> Iterator[Issue]:
    """Internal terms don't appear in anything the plugin ships."""
    for rel, text in _text_files(repo):
        if not rel.startswith(PLUGIN_REL + "/"):
            continue
        # Skill authors paste typographic apostrophes, so fold them before matching.
        folded = text.lower().replace("’", "'")
        for term in DENYLIST:
            if term in folded:
                yield Issue(
                    rel, f"contains {term!r}, which doesn't belong in shipped content"
                )
