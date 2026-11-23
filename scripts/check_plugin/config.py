"""Names, limits and patterns that the checks share.

Every value that a standard in AGENTS.md states lives here, so changing a limit
or a denylist term is a one-line edit that doesn't touch check logic.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

# This file is scripts/check_plugin/config.py, so the repository root is two
# directories above its package.
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASELINE = REPO_ROOT / "scripts" / "check-plugin-baseline.txt"

PLUGIN = "cortex-xcor-rum"
PLUGIN_REL = f"plugins/{PLUGIN}"
MARKETPLACE_REL = ".claude-plugin/marketplace.json"
MANIFEST_REL = f"{PLUGIN_REL}/.claude-plugin/plugin.json"
MCP_REL = f"{PLUGIN_REL}/.mcp.json"
SKILLS_REL = f"{PLUGIN_REL}/skills"
PLUGIN_README_REL = f"{PLUGIN_REL}/README.md"
ROOT_README_REL = "README.md"
CHANGELOG_REL = "CHANGELOG.md"
# The version check only fails once a release tag exists, because a version
# that hasn't shipped can still change.
TAG_GLOB = f"{PLUGIN}--v*"

DESCRIPTION_CAP = 1536
TEXT_CAP = 256 * 1024
FILE_CAP = 5 * 1024 * 1024
MAX_FILES = 512
MIN_README_WORDS = 40

IMAGE_EXT = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"})
FONT_EXT = frozenset({".woff", ".woff2", ".ttf", ".otf"})
JUNK_NAMES = frozenset({".ds_store", "thumbs.db", "desktop.ini", "__macosx"})

# Directories that aren't part of the shipped repository. `.agentd` holds
# agent scratch space and is git-ignored.
SKIP_DIRS = frozenset({".git", ".agentd", "node_modules"})

# The content checks skip the checker's own source and tests: they hold
# credential-shaped strings and "formerly Embrace" twice on purpose, and would
# otherwise fail on the strings that prove the checks work.
CONTENT_CHECK_SKIP_PREFIXES = ("scripts/check_plugin/", "tests/")

# The secrets hard rule is found by meaning, not exact wording: a list item
# that mentions secrets and redaction. Rewording the rule shouldn't fail CI.
SECRETS_RULE = re.compile(r"^\s*[-*].*\bsecrets?\b.*\bredact", re.I | re.M)
# Files whose prose the naming check reads: what the plugin ships and the
# README users see first. Changelogs and contributor docs may explain the
# rename more than once.
NAMING_SCOPE_PREFIXES = (f"{PLUGIN_REL}/", ROOT_README_REL)
# AGENTS.md requires lowercase, hyphenated skill names. Without this,
# `iOS-doctor` or `doctor_ios` would slip past the platform segment match.
SKILL_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
# A skill for one SDK is named `<platform>-<skill>`, so each platform's skills
# sort together in the `/cortex-xcor-rum:` command list. A name with no
# platform in it is for a skill that works across platforms. The list matches
# the SDKs at https://embrace.io/docs/open-telemetry/sdk-repositories/.
SKILL_PLATFORMS = ("android", "apple", "flutter", "react-native", "unity", "web")
# Informal names for a platform, which fail anywhere in a name. One Apple SDK
# covers iOS, tvOS and watchOS, so a name with one Apple operating system in
# it is wrong for the others.
PLATFORM_ALIASES = {
    **{
        os_name: "apple"
        for os_name in ("ios", "ipados", "macos", "osx", "tvos", "visionos", "watchos")
    },
    "rn": "react-native",
    "reactnative": "react-native",
}
SKILL_DIR_REF = re.compile(r"\$\{CLAUDE_SKILL_DIR\}/([^\s`'\"<>)\]]+)")

DENYLIST = (
    "#tech-support",
    "#guild-",
    "we'll flip",
    "we're tracking",
    "professional services",
)

SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")

# `${user_config.KEY}` is the sanctioned way to pass a credential. Any other
# `$NAME` or `${NAME}` reads the user's environment, and an Authorization
# header built that way stops Claude Code from falling back to OAuth.
USER_CONFIG = re.compile(r"\$\{user_config\.[A-Za-z0-9_]+\}")
_ENV_READ = r"\$\{?(?!user_config\.)[A-Za-z_]"
ENV_REF = re.compile(_ENV_READ)

MCP_TRANSPORTS = ("http", "sse", "ws")
SENSITIVE_HEADER = re.compile(r"auth|token|key|secret|cookie|password", re.I)
REMOTE_URL = re.compile(r"^(https|wss)://[^\s/$]")

# Launcher command -> separator between a package name and its version.
LAUNCHERS = {
    "npx": "@",
    "bunx": "@",
    "uvx": "==",
    "pipx": "==",
    "pnpm": "@",
    "yarn": "@",
    "uv": "==",
}
# Launchers that only fetch a package under one subcommand, such as `yarn dlx`.
# `uv run` runs a local project, so it needs a lockfile flag and not a pin.
LAUNCHER_SUBCOMMANDS = {"pnpm": "dlx", "yarn": "dlx", "pipx": "run", "uv": "run"}


class CredentialPattern(NamedTuple):
    regex: re.Pattern[str]
    description: str


CREDENTIAL_PATTERNS = (
    CredentialPattern(
        re.compile(r"Bearer\s+" + _ENV_READ),
        "an Authorization header that reads an environment variable",
    ),
    CredentialPattern(
        re.compile(
            r"[?&](?:api[_-]?key|token|access[_-]?token|key|secret)=" + _ENV_READ,
            re.I,
        ),
        "a URL that reads an environment variable into a credential parameter",
    ),
    CredentialPattern(
        re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{24,}"),
        "a literal bearer token",
    ),
    CredentialPattern(
        re.compile(
            r"\b(?:sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{30,}"
            r"|github_pat_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16}"
            r"|xox[abpr]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35})"
        ),
        "a literal API key",
    ),
    CredentialPattern(
        re.compile(
            r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}"
        ),
        "a literal JWT",
    ),
    CredentialPattern(
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        "a private key",
    ),
)
