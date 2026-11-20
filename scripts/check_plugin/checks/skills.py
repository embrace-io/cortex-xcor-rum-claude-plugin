"""skills, skill-refs and secrets-rule: what each SKILL.md must contain."""

from __future__ import annotations

from typing import Iterator

from ..config import (
    DESCRIPTION_CAP,
    SECRETS_RULE,
    SKILL_DIR_REF,
    SKILLS_REL,
)
from ..frontmatter import FrontmatterError, parse_frontmatter
from ..report import Issue
from ..repo import Repo


def check_skills(repo: Repo) -> Iterator[Issue]:
    """Each skill directory has a SKILL.md whose frontmatter matches it."""
    if not repo.is_dir(SKILLS_REL):
        yield Issue(SKILLS_REL, "directory is missing")
        return
    for entry in repo.list_dir(SKILLS_REL):
        if not repo.is_dir(f"{SKILLS_REL}/{entry}"):
            yield Issue(f"{SKILLS_REL}/{entry}", "skills/ holds only skill directories")
    for skill in repo.skills():
        text = repo.text(skill.skill_md)
        if text is None:
            yield Issue(skill.skill_md, "SKILL.md is missing or isn't UTF-8 text")
            continue
        try:
            fields = parse_frontmatter(text)
        except FrontmatterError as exc:
            yield Issue(skill.skill_md, str(exc))
            continue
        if fields.get("name") != skill.name:
            yield Issue(
                skill.skill_md,
                f"frontmatter name is {fields.get('name')!r}, "
                f"expected the directory name {skill.name!r}",
            )
        description = fields.get("description", "")
        if not description.strip():
            yield Issue(skill.skill_md, "frontmatter description is missing or empty")
        elif len(description) > DESCRIPTION_CAP:
            yield Issue(
                skill.skill_md,
                f"description is {len(description)} characters, "
                f"over the {DESCRIPTION_CAP} cap",
            )


def check_skill_refs(repo: Repo) -> Iterator[Issue]:
    """Every ${CLAUDE_SKILL_DIR}/<file> reference resolves inside its skill.

    The variable expands to the installed skill directory, so a reference to a
    file that isn't there fails at run time on every user's machine.
    """
    for skill in repo.skills():
        text = repo.text(skill.skill_md)
        if text is None:
            continue
        refs = {m.group(1).rstrip(".,;:") for m in SKILL_DIR_REF.finditer(text)}
        for ref in sorted(refs):
            if not repo.is_file(f"{skill.rel}/{ref}"):
                yield Issue(
                    skill.skill_md,
                    f"references ${{CLAUDE_SKILL_DIR}}/{ref}, "
                    f"which isn't in {skill.rel}/",
                )


def check_secrets_rule(repo: Repo) -> Iterator[Issue]:
    """Every SKILL.md has a hard rule that tells Claude to redact secrets."""
    for skill in repo.skills():
        text = repo.text(skill.skill_md)
        if text is not None and not SECRETS_RULE.search(text):
            yield Issue(
                skill.skill_md,
                "missing the secrets hard rule: a list item that says to redact "
                "secrets, such as 'Never reproduce secrets'",
            )
