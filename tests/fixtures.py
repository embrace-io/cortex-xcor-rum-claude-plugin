"""Builders for the temporary repository trees that the tests check."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Callable

from scripts.check_plugin.config import PLUGIN, PLUGIN_REL, SKILLS_REL

GOOD_SKILL = """---
name: demo
description: Use when the user asks about the demo.
---

# Demo

Read ${CLAUDE_SKILL_DIR}/notes.md first.

## Hard rules

- **Never reproduce secrets.** Replace credentials with `<redacted>`.
"""

SKILL = f"{SKILLS_REL}/demo/SKILL.md"
NOTES = f"{PLUGIN_REL}/skills/demo/notes.md"
MCP = f"{PLUGIN_REL}/.mcp.json"
MANIFEST = f"{PLUGIN_REL}/.claude-plugin/plugin.json"
MARKETPLACE = ".claude-plugin/marketplace.json"
PLUGIN_README = f"{PLUGIN_REL}/README.md"


def manifest(version: str = "1.0.0") -> dict:
    return {"name": PLUGIN, "version": version, "license": "Apache-2.0"}


def marketplace_entry(name: str, source: str) -> dict:
    return {"name": name, "source": source}


class Tree:
    """A directory with write and edit helpers and an optional git history."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def write(self, rel: str, content: str | bytes) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")

    def write_json(self, rel: str, data: object) -> None:
        self.write(rel, json.dumps(data))

    def read(self, rel: str) -> str:
        return (self.root / rel).read_text(encoding="utf-8")

    def edit(self, rel: str, change: Callable[[str], str]) -> None:
        self.write(rel, change(self.read(rel)))

    def symlink(self, rel: str, target: str) -> None:
        os.symlink(target, self.root / rel)

    def git(self, *args: str) -> None:
        subprocess.run(
            ["git", "-C", str(self.root), *args], check=True, capture_output=True
        )

    def init_git(self, tag: bool = False) -> None:
        """Commits the tree as `main` and marks it as the `base` branch."""
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        self.git("branch", "base")
        if tag:
            self.git("tag", f"{PLUGIN}--v1.0.0")

    def commit_changes(self) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "change")


def rename_skill(tree: Tree, name: str) -> None:
    """Renames the demo skill's directory, frontmatter name and README entries."""
    (tree.root / SKILL).parent.rename(tree.root / SKILLS_REL / name)
    skill_md = f"{SKILLS_REL}/{name}/SKILL.md"
    tree.edit(skill_md, lambda s: s.replace("name: demo", f"name: {name}"))
    for readme in ("README.md", PLUGIN_README):
        tree.edit(readme, lambda s: s.replace(f"/{PLUGIN}:demo", f"/{PLUGIN}:{name}"))


def build_good_tree(root: Path) -> Tree:
    """Builds the smallest tree that passes every check."""
    tree = Tree(root)
    tree.write_json(
        MARKETPLACE,
        {"name": PLUGIN, "plugins": [marketplace_entry(PLUGIN, f"./{PLUGIN_REL}")]},
    )
    tree.write_json(MANIFEST, manifest())
    tree.write_json(
        MCP,
        {
            "mcpServers": {
                "xcor-rum": {"type": "http", "url": "https://mcp.example.com/mcp"}
            }
        },
    )
    tree.write(
        PLUGIN_README,
        f"# Demo\n\nSkill `/{PLUGIN}:demo`. " + " ".join(["word"] * 50) + "\n",
    )
    tree.write(SKILL, GOOD_SKILL)
    tree.write(NOTES, "notes\n")
    tree.write("README.md", f"| `/{PLUGIN}:demo` | demo |\n")
    tree.write("CHANGELOG.md", "## [1.0.0] - Unreleased\n")
    return tree
