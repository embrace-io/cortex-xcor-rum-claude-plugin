# AGENTS.md

This repository is a Claude Code plugin marketplace for Cortex XCOR RUM (Real User Monitoring), formerly Embrace. It publishes one plugin, `cortex-xcor-rum`, whose skills help developers diagnose SDK problems with their app's data from the XCOR RUM MCP server. The repository is public, so everything in it, including commit messages and pull request text, must be fit for customers to read.

Read [CONTRIBUTING.md](CONTRIBUTING.md) first for the contributor workflow. This file adds the rules an agent must not break and the check that enforces them.

## Layout

```text
.claude-plugin/marketplace.json            marketplace: one entry, source ./plugins/cortex-xcor-rum
plugins/cortex-xcor-rum/
  .claude-plugin/plugin.json               manifest and version
  .mcp.json                                connectors (MCP servers)
  README.md                                plugin README, shown in the directory listing
  skills/<name>/SKILL.md                   one directory per skill, plus its sibling files
README.md                                  install, sign-in and skill table for users
CHANGELOG.md                               one entry per plugin version
scripts/check_plugin/                      the standards check (standard library only)
scripts/check-plugin-baseline.txt          known findings that predate the check
tests/                                     unit tests for the check and the eval scorer
evals/platform-discovery/                  accuracy eval for the platform-discovery skill (not shipped)
pyproject.toml                             black settings for the Python above
.github/workflows/validate.yml             CI: claude plugin validate and the check script
```

Everything the plugin ships lives under `plugins/cortex-xcor-rum/`. Users who install the plugin get only that folder, so a skill can't read a file outside it.

## Names and the command prefix

The marketplace, the plugin, the plugin directory and the marketplace entry are all named `cortex-xcor-rum`. Claude Code builds a skill's command from the plugin name, so every skill runs as `/cortex-xcor-rum:<skill>` and installs as `cortex-xcor-rum@cortex-xcor-rum`.

- Add new capabilities as skills inside this plugin. A second plugin would give its skills a different prefix and split the users.
- Never rename the plugin, the marketplace or a published skill. Installed copies are keyed by those names, so a rename breaks existing installs. A removed or renamed skill is a major version bump.
- The product is Cortex XCOR RUM (Real User Monitoring). In prose, write "Cortex XCOR RUM" on first mention and "XCOR RUM" after that. Add the "formerly" qualifier at most once per file.
- Keep "Embrace" only where it is a literal name: code identifiers (`Embrace.setup`, `EmbraceIO`), packages (`io.embrace`), files (`embrace-config.json`), URLs and hosts (`embrace.io`, `mcp.embrace.io`, `*.emb-api.com`), the GitHub organization `embrace-io`, environment variable names, and a skill's `symptoms`, because users still say Embrace.
- Name a skill for one SDK `<platform>-<skill>`, with one platform per SDK on the [SDK repositories page](https://embrace.io/docs/open-telemetry/sdk-repositories/): `android`, `apple`, `flutter`, `react-native`, `unity` or `web`. Examples are `apple-doctor` and `android-doctor`. The prefix groups each platform's skills together in the command list, and the rest of the name is free.
- Give a skill that works across platforms a name with no platform in it, such as `platform-discovery`. A platform name anywhere but the start (`doctor-flutter`) reads as a misnamed SDK skill and fails the check.
- Name Apple platforms `apple`, never `ios`, `tvos`, `watchos` or another Apple OS name, and React Native `react-native`, never `rn`. One Apple SDK covers iOS, tvOS and watchOS, so a name with one operating system in it is wrong for the others. Prose can still name a specific OS where only that OS applies, such as an iOS-only build setting.
- Keep the plugin and marketplace descriptions general. The plugin holds all of our skills, so a description doesn't name one.
- Name connectors after the product, not the old name: the bundled server's key in `.mcp.json` is `xcor-rum`, which Claude Code shows as `plugin:cortex-xcor-rum:xcor-rum`.

## Add a skill

1. Create `plugins/cortex-xcor-rum/skills/<name>/SKILL.md`. Use a lowercase, hyphenated `<name>`, named `<platform>-<skill>` if the skill targets one SDK (`apple-doctor`) or with no platform in it if it works across platforms (`platform-discovery`), and set the frontmatter `name` to the same string. A mismatch or a misplaced platform fails the check.
2. Write a `description` that says when to use the skill, with the phrases a user would type. Claude matches on it to load the skill on its own. Keep it under 1,536 characters, and quote it if it contains `: `, which YAML can't parse in a plain scalar.
3. Put sibling files (knowledge base, templates) in the skill's directory and refer to them as `${CLAUDE_SKILL_DIR}/<file>`. The variable expands to the installed skill directory. The check fails on a reference that doesn't resolve.
4. Include the hard rules below in the skill. The check requires the secrets rule: a list item that says to redact secrets.
5. Add the skill to the table in `README.md` and to the skill list in `plugins/cortex-xcor-rum/README.md`. Add keywords to `plugin.json` if the skill covers a new area.
6. Bump the version and add a CHANGELOG entry (see Versioning), then run the check.

A minimal skeleton:

````markdown
---
name: example
description: Use when the user reports <problem>, for example "<phrase they would type>". Inspects <what> and returns <what>.
---

# Example

One paragraph on what the skill does and the first thing it does.

## Procedure

1. Read `${CLAUDE_SKILL_DIR}/knowledge.md`. If it can't be read, stop and tell the user that the skill's files are missing from their install.
2. <Steps that use Read, Grep, Glob and the XCOR RUM MCP tools.>
3. Cite the file path, line number or MCP result behind every conclusion.

## Hard rules

- **Never reproduce secrets.** Before you quote a file, a log line or an MCP result, replace every credential with `<redacted>`: `api_token` in `embrace-config.json`, any `*_TOKEN`, `*_KEY`, `*_SECRET` or `*PASSWORD*` value, signing and keystore values, repository credentials and `Authorization` headers. Quote only the lines that support the answer, never a whole file. Don't read `.env` files, keystores, `local.properties` or provisioning profiles. Redact end users' personal data (emails, names, device identifiers) in log and span payloads the same way.
- **Read only.** Use `Read`, `Grep`, `Glob` and the MCP tools. Don't run builds, package managers, scripts or network commands. When a step needs a command, give it to the user to run and ask for the output.
- **The user sends any escalation.** Show the user what to send and where. Don't post it yourself.
````

The diagnostic skills (`apple-doctor`, `android-doctor`) use all three rules. A skill that only explains a concept can omit the last two, but it keeps the secrets rule.

## Add a connector

A connector is an MCP server declared in `plugins/cortex-xcor-rum/.mcp.json`:

```json
{
  "mcpServers": {
    "xcor-rum": {
      "type": "http",
      "url": "https://mcp.embrace.io/mcp"
    }
  }
}
```

- Set `type` to `http`, `sse` or `ws`, and `url` to an absolute `https://` or `wss://` URL.
- Use OAuth, which is the default when the server advertises it. Don't add a `headers` entry that reads an environment variable or holds a credential. An Authorization header built from an environment variable stops Claude Code from falling back to OAuth, and the directory holds the submission for review.
- If a credential is unavoidable, declare a `userConfig` entry with `sensitive: true` in `plugin.json` and refer to it as `${user_config.KEY}` in the header. Never read a credential from the user's environment and send it to a server, including in a README example.
- Pin a launcher (`npx`, `uvx`, `bunx`) to an exact version such as `npx some-server@1.2.3`. A local server also puts the submission on reviewer hold, so prefer a remote one and say in the PR why a local one is needed.
- Describe in `README.md` what the server receives from Claude Code and what it returns, as the existing Privacy section does for `embrace`.

## Content and safety rules

- No credentials anywhere in the repository, including README examples and test strings. Use `<redacted>` or a `userConfig` reference.
- Diagnostic skills are read only: `Read`, `Grep`, `Glob` and MCP tools. Commands go to the user to run.
- Skills and knowledge bases describe product behavior and fixes. They don't include internal process, internal Slack channels, internal URLs or source paths, or promises ("we'll", flipping flags, calls with engineers, roadmap, "we're tracking"). Write to the user, a developer, and not to support staff.
- Don't claim an Anthropic endorsement. The README states that this is not an official Anthropic repository.
- Directory limits for files under the plugin: each non-image file under 256 KiB, at most 512 files, no binaries other than PNG, JPEG, GIF, WebP, SVG and font files, no OS junk files (`.DS_Store`, `Thumbs.db`), no symlinks or Git LFS pointers, and a plugin README of at least 40 words.

## Versioning and the CHANGELOG

`CONTRIBUTING.md` has the semantic versioning rules. Bump `version` in `plugin.json` in every pull request that changes a file under `plugins/cortex-xcor-rum/`, because Claude Code keeps the cached copy until the version string changes. Add a matching `## [x.y.z]` entry to `CHANGELOG.md`, marked `Unreleased` until the version ships.

Version 1.1.1 hasn't shipped, so while it is unreleased, edits to it don't need another bump. The check enforces this: on a pull request, `python3 -m scripts.check_plugin --base origin/<base branch>` fails if plugin files changed and `version` didn't, but only once a tag matching `cortex-xcor-rum--v*` exists. With no such tag it prints a warning. Create the tag when a version ships.

Changes outside the plugin folder (this file, `scripts/`, `.github/`, root docs) need no bump.

## Validate and run the checks

Run all of these before opening a pull request. CI runs the same commands in `.github/workflows/validate.yml`.

```bash
claude plugin validate --strict .
claude plugin validate --strict plugins/cortex-xcor-rum
claude plugin validate --profile directory plugins/cortex-xcor-rum
python3 -m scripts.check_plugin
python3 -m unittest
black --check .
```

The check needs only Python 3.10 or later. `black` is a development tool, pinned in `.github/workflows/validate.yml`; run `pip install black==26.10.1` to match CI. The check prints `FAIL [check-id] path: message` and exits 1 on any failure. Pass a directory to check another tree, and `--base <ref>` for the version check.

| Check id | What it enforces |
| :- | :- |
| `layout` | One plugin. The marketplace name, the entry name, the `plugin.json` name and the plugin directory all equal `cortex-xcor-rum`. The version is semver. |
| `skills` | Each skill directory has a `SKILL.md` with parseable frontmatter, `name` equal to the directory, and a non-empty `description` of at most 1,536 characters. |
| `skill-names` | A skill name is lowercase letters and digits joined by hyphens. A name for one SDK is `<platform>-<skill>`, where the platform is `android`, `apple`, `flutter`, `react-native`, `unity` or `web`, and anything may follow the prefix. A name without a platform prefix is for a skill that works across platforms and can't have a platform in it. An informal platform name fails anywhere: an Apple OS name (`ios`, `ipados`, `macos`, `osx`, `tvos`, `visionos`, `watchos`) instead of `apple`, or `rn` instead of `react-native`. The check compares hyphen-separated segments, so `doctor-ios` fails and `scenarios` and `webview` pass, and it can't catch an informal name it doesn't list, such as `iphone`. |
| `skill-refs` | Every `${CLAUDE_SKILL_DIR}/<file>` reference points to a file in that skill's directory. |
| `secrets-rule` | Every `SKILL.md` has a list item that says to redact secrets, such as "Never reproduce secrets". |
| `mcp` | Every server uses `http`, `sse` or `ws` with an `https://` or `wss://` URL, has no header that reads an environment variable or holds a literal credential, and pins any launcher version. |
| `credentials` | No file reads an environment variable into an Authorization header or a URL credential parameter, and none holds a literal key, token or private key. |
| `naming` | The "formerly" qualifier appears at most once per file in the plugin folder and the root README. |
| `denylist` | Internal terms (`#tech-support`, `#guild-`, `we'll flip`, `we're tracking`, `professional services`) don't appear under `plugins/`. |
| `files` | Directory limits for size, count, file types, junk files, symlinks and LFS, and a plugin README of 40 or more words. |
| `docs` | Every skill is in the root README table (a skill missing from the plugin README only warns), and `CHANGELOG.md` has an entry for the current version. |
| `version` | Plugin files changed without a version bump (enforced after the first release tag). |

`scripts/check-plugin-baseline.txt` lists findings that existed when the check was added, one `<check-id> <path>` per line. A baselined finding prints as a warning. Don't add a line to hide a new problem. Delete a line when you fix its finding, and the check warns about lines that no longer match.

The check can't judge prose. Review product naming, voice and the "no promises" rule yourself.

To add a check:

1. Write a function in a module under `scripts/check_plugin/checks/`. It takes a `Repo` (see `repo.py`) and yields `Issue(path, message)` for each problem, and `Issue(path, message, Severity.WARN)` for a warning.
2. Add `Check("<check-id>", check_function)` to `CHECKS` in `scripts/check_plugin/checks/__init__.py`.
3. Add a failing case to `MUTATIONS` in `tests/test_checks.py`. The test that every registered check has a failing case fails until you do. Add a test to `GoodTreeTests` for any input that must keep passing.
4. Put new limits and patterns in `scripts/check_plugin/config.py`, and add the check to the table above.

## Writing style

Follow these rules for every piece of prose in this repository: skill and knowledge-base text, READMEs and other docs, code comments, commit messages and pull request descriptions.

- **Write straightforward technical prose.** Write like an engineer explaining a system to a teammate. Use a period, comma, colon or parentheses instead of an em dash.
- **Lead with the main point.** State what happens or what was decided first, then explain how it works and why.
- **Put the subject first.** Write "`plugin.json` sets the version" rather than "The version is set in `plugin.json`."
- **Use precise terms, not paraphrases.** Name the file, field, tool or command (`version`, `.mcp.json`, `list_apps`) instead of "the thing that holds it".
- **Use literal verbs.** Write `reads`, `returns`, `calls`, `sends`, `validates`, not metaphors such as "travels", "sits" or "buries".
- **Explain the mechanism.** Say how something works and how it fails, so the reader can verify the claim.
- **Distinguish measurements from assumptions.** Say whether a number or behavior was measured ("measured at 40 s per run") or assumed.
- **Document tradeoffs.** When a choice isn't obvious, note the alternatives you considered and why you didn't pick them.
- **Don't end with an aphorism or punchline.** State the concrete reason and stop.
- **Start each section with a complete sentence**, not a fragment that repeats the heading.
- **Refer to roles and components, not individuals.**
- **Use American English spelling.**

In code, let clear names explain what the code does, and keep comments for why: invariants, workarounds for a specific bug, external constraints, non-obvious tradeoffs. Cite the concrete failure mode rather than "be careful here".

A commit message has a short imperative subject line and a body that says what changed and why. A pull request uses the template in `.github/pull_request_template.md`: a summary that leads with the change, the testing you ran with its results, and the checklist.

## What not to do

- Don't create a second plugin or marketplace entry, and don't rename `cortex-xcor-rum`.
- Don't put files that a skill needs outside `plugins/cortex-xcor-rum/`.
- Don't add a `headers` entry, `env` value or README example that sends a credential from the user's environment to a server.
- Don't paste real customer data, tokens or app IDs into skills, knowledge bases or tests.
- Don't edit a plugin file without the version bump and CHANGELOG entry once a version has shipped.
- Don't loosen a check or add a baseline line to get a build green. Fix the content, or change the check in the same pull request and explain why.
- Don't open pull requests against anything but `main`, and don't push to `main` directly.
