# Contributing

This repository holds one plugin, `cortex-xcor-rum`, in `plugins/cortex-xcor-rum/`. Open pull requests against `main`.

## Add a skill

Each skill is a directory under the plugin's `skills/` directory:

```text
plugins/cortex-xcor-rum/skills/<name>/SKILL.md
```

1. Create `plugins/cortex-xcor-rum/skills/<name>/SKILL.md`. Set `name` in its frontmatter to the directory name. The frontmatter `name` sets the last segment of the command, `/cortex-xcor-rum:<name>`.
2. Write a `description` that says when Claude should use the skill, since Claude reads it to decide whether to load the skill on its own.
3. Put any sibling files the skill needs (knowledge bases, templates, scripts) in the same directory and reference them as `${CLAUDE_SKILL_DIR}/<file>`. The variable expands to the skill's directory wherever the plugin is installed.
4. Add the skill to the table in the root `README.md`, with its command and what it covers, and to the skill list in `plugins/cortex-xcor-rum/README.md`.
5. Add keywords to `plugins/cortex-xcor-rum/.claude-plugin/plugin.json` if the skill covers a new area.
6. Keep the plugin `description` in `plugin.json` and in `.claude-plugin/marketplace.json` general. The plugin holds all of our Claude skills, so the descriptions don't name a single skill.
7. Bump the version (below) and add an entry to `CHANGELOG.md`. Mark it `Unreleased` in the heading, and replace that with the release date (YYYY-MM-DD) when the version ships.

## Versioning

Bump `version` in `plugins/cortex-xcor-rum/.claude-plugin/plugin.json` in every pull request that changes a file under `plugins/cortex-xcor-rum/`. Claude Code keeps using the cached copy of a plugin until its version string changes, so a change without a bump never reaches existing users.

Use semantic versioning:

- Patch (`1.1.0` to `1.1.1`): fixes, wording changes and documentation.
- Minor (`1.1.1` to `1.2.0`): a new skill, a new MCP server or another backward-compatible addition.
- Major (`1.2.0` to `2.0.0`): a removed or renamed skill, or any change that breaks how people call the plugin.

## Test locally

Load the plugin from your checkout without installing it:

```bash
claude --plugin-dir plugins/cortex-xcor-rum
```

Then run `/reload-plugins` after each edit and call the skill as `/cortex-xcor-rum:<name>`.

Before you open a pull request, validate the marketplace and the plugin:

```bash
claude plugin validate --strict .
claude plugin validate --strict plugins/cortex-xcor-rum
claude plugin validate --profile directory plugins/cortex-xcor-rum
```

The `directory` profile applies the checks for submitting the plugin to the Anthropic plugin directory. A missing icon is the only warning we expect from it until the icon is added.

Then run the standards check, which enforces the naming, safety and packaging rules in [AGENTS.md](AGENTS.md):

```bash
python3 -m scripts.check_plugin
```

It needs only Python 3.10 or later, prints `FAIL [check-id] path: message` for each problem and exits 1 if there is one. CI runs it with the validate commands on every pull request.
