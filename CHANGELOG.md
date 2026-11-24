# Changelog

All notable changes to the `cortex-xcor-rum` plugin are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the plugin uses [semantic versioning](https://semver.org/). `Unreleased` in a version's heading is replaced with the release date (YYYY-MM-DD) when that version ships.

## [1.1.1] - Unreleased

First release of the consolidated plugin.

### Added

- One `cortex-xcor-rum` plugin with the `apple-doctor` and `android-doctor` skills, invoked as `/cortex-xcor-rum:apple-doctor` and `/cortex-xcor-rum:android-doctor`. `apple-doctor` covers iOS, tvOS and watchOS apps.
- The `doctor` skill, invoked as `/cortex-xcor-rum:doctor`: one command that detects the app's platform with `platform-discovery` and runs that platform's doctor skill, or points to support where the plugin has no doctor for the platform yet. A bare `/doctor` runs Claude Code's own setup checkup, so the README says to type the full command.
- The `platform-discovery` skill, invoked as `/cortex-xcor-rum:platform-discovery`. It detects an app's platform (Android, Apple, React Native, Flutter, Unity or web) from the codebase, and from XCOR RUM app data when an App ID is known, then hands the request to that platform's skill. It asks the user only when the evidence doesn't settle the platform or, for a React Native, Flutter or Unity app, the side. Where the plugin has no skill for the platform yet, it says so and points to support.
- The plugin bundles the XCOR RUM MCP server (`https://mcp.embrace.io/mcp`, OAuth) in `.mcp.json`.
- A listing icon at `.claude-plugin/icon.png`: the Cortex XCOR mark on a dark 1024 px square.
- `privacyPolicyUrl` in `plugin.json`.
- Root and plugin READMEs covering install, MCP sign-in, skills, example prompts, troubleshooting, getting help, updates and privacy.
- `LICENSE` (Apache-2.0), `CONTRIBUTING.md` and this changelog.

### Changed

- Replaces the `embrace-doctor-ios` and `embrace-doctor-android` plugins with the single `cortex-xcor-rum` plugin, and renames the marketplace from `embrace-claude-plugin` to `cortex-xcor-rum`.
- The marketplace, plugin and skills name the product Cortex XCOR RUM (formerly Embrace).
- Knowledge bases for both doctor skills: `MCP_SKILL_QA_INDEX.yaml` (24 Apple entries, 12 Android entries) beside each `SKILL.md`.
- The doctor skills stop and tell the user when their knowledge base or the app is missing.

### Migration

If you added the old `embrace-claude-plugin` marketplace or installed `embrace-doctor-ios` or `embrace-doctor-android`, remove them and add the new marketplace and plugin:

```bash
claude plugin marketplace remove embrace-claude-plugin
claude plugin marketplace add embrace-io/cortex-xcor-rum-claude-plugin
claude plugin install cortex-xcor-rum@cortex-xcor-rum
```
