"""docs: the READMEs list every skill and the CHANGELOG covers the version."""

from __future__ import annotations

import re
from typing import Iterator

from ..config import (
    CHANGELOG_REL,
    MANIFEST_REL,
    PLUGIN,
    PLUGIN_README_REL,
    ROOT_README_REL,
)
from ..report import Issue, Severity
from ..repo import Repo


def check_docs(repo: Repo) -> Iterator[Issue]:
    root_readme = repo.text(ROOT_README_REL) or ""
    plugin_readme = repo.text(PLUGIN_README_REL) or ""
    for skill in repo.skills():
        command = f"/{PLUGIN}:{skill.name}"
        if command not in root_readme:
            yield Issue(ROOT_README_REL, f"skill table doesn't list {command}")
        if command not in plugin_readme:
            # The root README's table is the list users rely on, so a gap in the
            # plugin README's shorter list is worth a reminder, not a red build.
            yield Issue(
                PLUGIN_README_REL,
                f"skill list doesn't mention {command}",
                Severity.WARN,
            )

    manifest = repo.json(MANIFEST_REL).data
    version = manifest.get("version") if isinstance(manifest, dict) else None
    changelog = repo.text(CHANGELOG_REL)
    if changelog is None:
        yield Issue(CHANGELOG_REL, "file is missing")
    elif version and not re.search(
        r"^## \[" + re.escape(version) + r"\]", changelog, re.M
    ):
        yield Issue(
            CHANGELOG_REL, f"no '## [{version}]' entry for the version in plugin.json"
        )
