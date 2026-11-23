"""skills, skill-names, skill-refs and secrets-rule: the rules for each skill."""

from __future__ import annotations

from typing import Iterator, NamedTuple

from ..config import (
    DESCRIPTION_CAP,
    PLATFORM_ALIASES,
    SECRETS_RULE,
    SKILL_DIR_REF,
    SKILL_NAME,
    SKILL_PLATFORMS,
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


def check_skill_names(repo: Repo) -> Iterator[Issue]:
    """A skill name is `<platform>-<skill>` for one SDK, or has no platform in
    it for a skill that works across platforms.

    The check compares hyphen-separated segments, so `ios` fails but a word
    that only contains it, such as `scenarios`, passes. Anything after a
    platform prefix passes except an informal platform name. Skill names are
    permanent once a version ships, so the check stops a new name from
    breaking the pattern rather than leaving a rename for later.
    """
    for skill in repo.skills():
        if not SKILL_NAME.fullmatch(skill.name):
            yield Issue(
                skill.rel,
                "skill name must be lowercase letters and digits joined by "
                "hyphens, such as 'apple-doctor'",
            )
            continue
        problem = _skill_name_problem(skill.name)
        if problem:
            yield Issue(skill.rel, problem)


class _Token(NamedTuple):
    text: str  # the segment, or `react-native` when two segments spell it
    platform: str | None  # the canonical platform the token names, if any


def _tokens(name: str) -> list[_Token]:
    segments = name.split("-")
    tokens: list[_Token] = []
    i = 0
    while i < len(segments):
        if segments[i : i + 2] == ["react", "native"]:
            tokens.append(_Token("react-native", "react-native"))
            i += 2
            continue
        segment = segments[i]
        if segment in SKILL_PLATFORMS:
            tokens.append(_Token(segment, segment))
        else:
            tokens.append(_Token(segment, PLATFORM_ALIASES.get(segment)))
        i += 1
    return tokens


def _platform_prefix(name: str) -> str | None:
    return next((p for p in SKILL_PLATFORMS if name.startswith(f"{p}-")), None)


def _skill_name_problem(name: str) -> str | None:
    tokens = _tokens(name)
    alias = next((t for t in tokens if t.platform and t.text != t.platform), None)
    suggestion = _suggest(tokens)
    if alias:
        example = f", as in {suggestion!r}" if suggestion else ""
        return (
            f"skill name has the informal platform name {alias.text!r}; "
            f"use {alias.platform!r}{example}"
        )
    hint = f"; name it {suggestion!r}" if suggestion else ""
    if _platform_prefix(name):
        return None
    platform = next((t.platform for t in tokens if t.platform), None)
    if platform is None:
        return None
    if not suggestion:
        hint = f"; add the skill's name after '{platform}-'"
    return (
        f"skill name has the platform {platform!r} but doesn't start with "
        f"'{platform}-'; a name without a platform prefix is for a skill that "
        f"works across platforms{hint}"
    )


def _suggest(tokens: list[_Token]) -> str | None:
    """Returns the name with informal platform names made canonical and the
    first platform moved to the front, or None when no skill name is left."""
    canonical: list[_Token] = []
    seen: set[str] = set()
    for token in tokens:
        if token.platform:
            if token.platform in seen:
                continue
            seen.add(token.platform)
            token = _Token(token.platform, token.platform)
        canonical.append(token)
    first = next((t for t in canonical if t.platform), None)
    if first is None:
        return None
    rest = [t.text for t in canonical if t is not first]
    return "-".join([first.text, *rest]) if rest else None


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
