"""The registry of checks.

A check is a function from a Repo to issues, and a check id is the name that
AGENTS.md, the baseline file and the output use for it. To add a check, write
its function in a module here and add one `Check` line to CHECKS.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from ..report import Issue
from ..repo import Repo
from .content import check_credentials, check_denylist, check_naming
from .docs import check_docs
from .files import check_files
from .layout import check_layout
from .mcp import check_mcp
from .skills import (
    check_secrets_rule,
    check_skill_names,
    check_skill_refs,
    check_skills,
)
from .version import check_version


@dataclass(frozen=True)
class Check:
    id: str
    run: Callable[[Repo], Iterable[Issue]]


# The order is the order findings print in.
CHECKS = (
    Check("layout", check_layout),
    Check("skills", check_skills),
    Check("skill-names", check_skill_names),
    Check("skill-refs", check_skill_refs),
    Check("secrets-rule", check_secrets_rule),
    Check("mcp", check_mcp),
    Check("credentials", check_credentials),
    Check("naming", check_naming),
    Check("denylist", check_denylist),
    Check("files", check_files),
    Check("docs", check_docs),
    Check("version", check_version),
)
