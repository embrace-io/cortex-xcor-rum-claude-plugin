"""version: a change to plugin files needs a version bump once a release exists."""

from __future__ import annotations

import json
from typing import Iterator

from ..config import MANIFEST_REL, PLUGIN_REL, TAG_GLOB
from ..report import Issue, Severity
from ..repo import Repo


def check_version(repo: Repo) -> Iterator[Issue]:
    """Compares plugin.json's version with the one on the base ref.

    Claude Code keeps an installed copy until the version string changes, so a
    shipped version with edited files never reaches existing users. Before the
    first release tag exists the version hasn't shipped, and the same edit only
    warns.
    """
    base = repo.base
    if not base:
        return
    changed = repo.git("diff", "--name-only", f"{base}...HEAD", "--", PLUGIN_REL)
    if not changed.ok:
        yield Issue(
            base,
            "can't diff against the base ref (fetch full history with "
            "fetch-depth: 0); skipping the version check",
            Severity.WARN,
        )
        return
    if not changed.stdout:
        return

    new_manifest = repo.json(MANIFEST_REL).data
    if not isinstance(new_manifest, dict):
        return  # the layout check already reports an unreadable manifest
    if _base_version(repo, base) != new_manifest.get("version"):
        return

    message = (
        f"files under {PLUGIN_REL}/ changed against {base} "
        f"but version is still {new_manifest.get('version')}"
    )
    if repo.git("tag", "-l", TAG_GLOB).stdout:
        yield Issue(MANIFEST_REL, message + "; bump it")
    else:
        yield Issue(
            MANIFEST_REL,
            message + f" (not enforced: no {TAG_GLOB} tag exists, "
            "so the version hasn't shipped)",
            Severity.WARN,
        )


def _base_version(repo: Repo, base: str) -> object:
    shown = repo.git("show", f"{base}:{MANIFEST_REL}")
    if not shown.ok:
        return None
    try:
        data = json.loads(shown.stdout)
    except ValueError:
        return None
    return data.get("version") if isinstance(data, dict) else None
