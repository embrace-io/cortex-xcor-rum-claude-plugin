"""mcp: remote servers with OAuth or userConfig, and pinned local launchers."""

from __future__ import annotations

import re
from typing import Any, Iterator

from ..config import (
    ENV_REF,
    LAUNCHER_SUBCOMMANDS,
    LAUNCHERS,
    MCP_REL,
    MCP_TRANSPORTS,
    REMOTE_URL,
    SENSITIVE_HEADER,
    USER_CONFIG,
)
from ..report import Issue
from ..repo import Repo


def check_mcp(repo: Repo) -> Iterator[Issue]:
    if not repo.is_file(MCP_REL):
        return
    loaded = repo.json(MCP_REL)
    if loaded.error:
        yield Issue(MCP_REL, loaded.error)
        return
    data = loaded.data
    servers = data.get("mcpServers", data) if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        yield Issue(MCP_REL, "expected an object of servers")
        return
    for name, server in servers.items():
        where = f"server {name!r}"
        if not isinstance(server, dict):
            yield Issue(MCP_REL, f"{where} isn't an object")
            continue
        for message in _server_problems(where, server):
            yield Issue(MCP_REL, message)


def _server_problems(where: str, server: dict[str, Any]) -> Iterator[str]:
    env = server.get("env") or {}
    if isinstance(env, dict):
        for key, value in env.items():
            if ENV_REF.search(str(value)):
                yield f"{where} env {key!r} reads from the user's environment"
    if "command" in server:
        yield from _launcher_problems(where, server)
        return
    yield from _remote_problems(where, server)


def _remote_problems(where: str, server: dict[str, Any]) -> Iterator[str]:
    if server.get("type") not in MCP_TRANSPORTS:
        yield f"{where} has type {server.get('type')!r}, expected http, sse or ws"
    url = server.get("url")
    if not isinstance(url, str) or not (
        REMOTE_URL.match(url) or USER_CONFIG.fullmatch(url) or url == ""
    ):
        yield f"{where} url {url!r} must be an absolute https:// or wss:// URL"
    elif ENV_REF.search(url):
        yield f"{where} url reads an environment variable"
    headers = server.get("headers") or {}
    if not isinstance(headers, dict):
        yield f"{where} headers isn't an object"
        return
    for header, value in headers.items():
        value = str(value)
        if ENV_REF.search(value):
            yield (
                f"{where} header {header!r} reads an environment variable; "
                "use a userConfig entry with sensitive: true"
            )
        elif not USER_CONFIG.search(value) and SENSITIVE_HEADER.search(header):
            yield (
                f"{where} header {header!r} holds a literal value; "
                "use a userConfig entry with sensitive: true"
            )


def _launcher_problems(where: str, server: dict[str, Any]) -> Iterator[str]:
    """Flags a package runner that fetches an unpinned version at start-up.

    `npx some-server@latest` runs whatever was published last, so a compromised
    release reaches every user without a plugin version bump.
    """
    command = str(server.get("command")).rsplit("/", 1)[-1]
    args = [str(a) for a in server.get("args", [])]
    if command not in LAUNCHERS:
        return
    subcommand = LAUNCHER_SUBCOMMANDS.get(command)
    if subcommand:
        if not args or args[0] != subcommand:
            return
        args = args[1:]
    if command == "uv":
        if "--locked" not in args and "--frozen" not in args:
            yield f"{where} runs uv run without --locked or --frozen"
        return
    package = next((a for a in args if not a.startswith("-")), None)
    separator = LAUNCHERS[command]
    if package is None or not re.search(
        re.escape(separator) + r"\d+\.\d+\.\d+", package.lstrip("@")
    ):
        yield (
            f"{where} runs {command} with {package!r}; pin the package to an "
            f"exact version such as name{separator}1.2.3"
        )
