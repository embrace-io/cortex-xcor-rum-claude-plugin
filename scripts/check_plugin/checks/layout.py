"""layout: one plugin, with the same name everywhere and a semantic version."""

from __future__ import annotations

from typing import Any, Iterator

from ..config import (
    MANIFEST_REL,
    MARKETPLACE_REL,
    PLUGIN,
    PLUGIN_REL,
    SEMVER,
)
from ..report import Issue
from ..repo import Repo


def check_layout(repo: Repo) -> Iterator[Issue]:
    marketplace = repo.json(MARKETPLACE_REL)
    plugin_dirs = repo.list_dir("plugins")
    if plugin_dirs != [PLUGIN]:
        yield Issue(
            "plugins",
            f"expected exactly one plugin directory named {PLUGIN}, "
            f"found {plugin_dirs or 'none'}",
        )
    yield from _marketplace_issues(marketplace.data, marketplace.error)

    manifest = repo.json(MANIFEST_REL)
    if manifest.error:
        yield Issue(MANIFEST_REL, manifest.error)
    elif not isinstance(manifest.data, dict):
        yield Issue(MANIFEST_REL, "expected a JSON object")
    else:
        if manifest.data.get("name") != PLUGIN:
            yield Issue(
                MANIFEST_REL,
                f"plugin name is {manifest.data.get('name')!r}, expected {PLUGIN!r}",
            )
        version = manifest.data.get("version")
        if not isinstance(version, str) or not SEMVER.match(version):
            yield Issue(MANIFEST_REL, f"version {version!r} isn't a semantic version")


def _marketplace_issues(data: Any, error: str | None) -> Iterator[Issue]:
    if error:
        yield Issue(MARKETPLACE_REL, error)
        return
    if not isinstance(data, dict):
        yield Issue(MARKETPLACE_REL, "expected a JSON object")
        return
    if data.get("name") != PLUGIN:
        yield Issue(
            MARKETPLACE_REL,
            f"marketplace name is {data.get('name')!r}, expected {PLUGIN!r}",
        )
    entries = data.get("plugins")
    if not isinstance(entries, list) or len(entries) != 1:
        yield Issue(MARKETPLACE_REL, "the marketplace must list exactly one plugin")
        return
    entry = entries[0]
    if not isinstance(entry, dict):
        yield Issue(MARKETPLACE_REL, "the plugin entry isn't an object")
        return
    if entry.get("name") != PLUGIN:
        yield Issue(
            MARKETPLACE_REL,
            f"plugin entry name is {entry.get('name')!r}, expected {PLUGIN!r}",
        )
    if entry.get("source") != f"./{PLUGIN_REL}":
        yield Issue(
            MARKETPLACE_REL,
            f"plugin entry source is {entry.get('source')!r}, "
            f"expected './{PLUGIN_REL}'",
        )
