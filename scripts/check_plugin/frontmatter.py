"""A parser for the top-level keys of a SKILL.md frontmatter block.

The standard library has no YAML parser and the check can't take a
dependency, so this handles the subset skills use: scalars, quoted scalars and
block scalars. It rejects the one input that a real YAML parser would also
reject and that authors hit often: a plain scalar containing `: `.
"""

from __future__ import annotations

import re

_KEY_VALUE = re.compile(r"^([A-Za-z0-9_.-]+):(?:\s+(.*))?$")
_BLOCK_SCALAR = re.compile(r"^[>|][+-]?$")


class FrontmatterError(ValueError):
    """The frontmatter block is missing or isn't valid for a skill."""


def parse_frontmatter(text: str) -> dict[str, str]:
    """Returns the frontmatter keys of a SKILL.md as strings.

    Raises FrontmatterError with a message that says what to fix.
    """
    lines = text.split("\n")
    if lines[0].rstrip() != "---":
        raise FrontmatterError("file doesn't start with a '---' frontmatter block")
    end = next((i for i in range(1, len(lines)) if lines[i].rstrip() == "---"), None)
    if end is None:
        raise FrontmatterError("frontmatter has no closing '---'")

    body = lines[1:end]
    fields: dict[str, str] = {}
    idx = 0
    while idx < len(body):
        line = body[idx]
        idx += 1
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = _KEY_VALUE.match(line)
        if not match:
            # idx is already past this line; +1 turns the body index into the
            # file's line number, which counts the opening '---'.
            raise FrontmatterError(
                f"frontmatter line {idx + 1} isn't a 'key: value' pair: {line[:60]!r}"
            )
        key, value = match.group(1), (match.group(2) or "").strip()
        continuation = []
        while idx < len(body) and (
            body[idx].startswith((" ", "\t")) or not body[idx].strip()
        ):
            continuation.append(body[idx].strip())
            idx += 1
        fields[key] = _scalar(key, value, [c for c in continuation if c])
    return fields


def _scalar(key: str, value: str, continuation: list[str]) -> str:
    if _BLOCK_SCALAR.match(value):
        joiner = " " if value.startswith(">") else "\n"
        return joiner.join(continuation)
    if value[:1] in ("'", '"'):
        if len(value) < 2 or value[-1] != value[0]:
            raise FrontmatterError(
                f"frontmatter key {key!r} has an unterminated quoted string"
            )
        return value[1:-1]
    if value:
        value = " ".join([value, *continuation])
        if ": " in value or " #" in value:
            raise FrontmatterError(
                f"frontmatter key {key!r} is a plain scalar with ': ' or ' #' in it, "
                "which YAML can't parse; wrap it in quotes"
            )
    return value
