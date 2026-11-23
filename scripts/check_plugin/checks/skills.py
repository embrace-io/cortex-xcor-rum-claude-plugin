"""skills, skill-names, skill-refs and secrets-rule: the rules for each skill."""

from __future__ import annotations

from typing import Iterator, NamedTuple

from ..config import (
    DESCRIPTION_CAP,
    FRAMEWORK_PLATFORMS,
    NATIVE_PLATFORMS,
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
    """A skill name is lowercase and hyphenated, and an SDK skill's name starts
    with its platform: `apple-`, `android-`, `flutter-`, `react-native-`,
    `unity-` or `web-`.

    The check compares hyphen-separated segments, so `ios` fails but a word
    that only contains it, such as `scenarios`, passes. Skill names are
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
        problem = _skill_name_problem(_tokens(skill.name.split("-")))
        if problem:
            yield Issue(skill.rel, problem)


class _Token(NamedTuple):
    text: str  # the segment, or `react-native` when two segments spell it
    platform: str | None  # the canonical platform the token names, if any


def _tokens(segments: list[str]) -> list[_Token]:
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


def _skill_name_problem(tokens: list[_Token]) -> str | None:
    named = [t for t in tokens if t.platform]
    if not named:
        return None
    suggestion = _suggest(tokens)
    hint = f", as in {suggestion!r}" if suggestion else ""
    alias = next((t for t in named if t.text != t.platform), None)
    if alias:
        return (
            f"skill name has the informal platform name {alias.text!r}; "
            f"name the platform {alias.platform!r}{hint}"
        )
    platforms = list(dict.fromkeys(t.platform for t in named))
    primary = platforms[0]
    extra = platforms[1:]
    allowed_extra = not extra or (
        primary in FRAMEWORK_PLATFORMS
        and len(extra) == 1
        and extra[0] in NATIVE_PLATFORMS
    )
    if not allowed_extra:
        return (
            f"skill name names more than one platform ({', '.join(platforms)}); "
            "a skill for every platform takes no prefix, and only a framework "
            f"prefix ({', '.join(FRAMEWORK_PLATFORMS)}) may name a native side "
            f"({', '.join(NATIVE_PLATFORMS)}) after it{hint}"
        )
    if len(named) != len(platforms):
        return f"skill name names its platform more than once{hint}"
    if tokens[0].platform != primary:
        return f"skill name doesn't start with its platform{hint}"
    if extra and tokens[1].platform != extra[0]:
        return f"skill name puts the native side away from its prefix{hint}"
    return None


def _suggest(tokens: list[_Token]) -> str | None:
    """Returns the name with its platform tokens moved to the front, or None
    when the platforms can't form a valid prefix."""
    platforms = set(t.platform for t in tokens if t.platform)
    frameworks = [p for p in FRAMEWORK_PLATFORMS if p in platforms]
    natives = [p for p in NATIVE_PLATFORMS if p in platforms]
    if len(platforms) == 1:
        prefix = list(platforms)
    elif len(frameworks) == 1 and len(natives) == 1 and len(platforms) == 2:
        prefix = frameworks + natives
    else:
        return None
    rest = [t.text for t in tokens if not t.platform]
    return "-".join(prefix + rest)


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
