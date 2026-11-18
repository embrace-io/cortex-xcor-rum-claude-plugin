# Changelog

All notable changes to the `cortex-xcor-rum` plugin are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the plugin uses [semantic versioning](https://semver.org/). `Unreleased` in a version's heading is replaced with the release date (YYYY-MM-DD) when that version ships.

## [1.1.1] - Unreleased

First release of the consolidated plugin.

### Added

- One `cortex-xcor-rum` plugin with the `doctor-ios` and `doctor-android` skills, invoked as `/cortex-xcor-rum:doctor-ios` and `/cortex-xcor-rum:doctor-android`.
- The plugin bundles the XCOR RUM MCP server (`https://mcp.embrace.io/mcp`, OAuth) in `.mcp.json`.
- A listing icon at `.claude-plugin/icon.png`: the Cortex XCOR mark on a dark 1024 px square.
- `privacyPolicyUrl` in `plugin.json`.
- Root and plugin READMEs covering install, MCP sign-in, skills, example prompts, troubleshooting, updates and privacy.
- `LICENSE` (Apache-2.0), `CONTRIBUTING.md` and this changelog.

### Changed

- Replaces the `embrace-doctor-ios` and `embrace-doctor-android` plugins with the single `cortex-xcor-rum` plugin, and renames the marketplace from `embrace-claude-plugin` to `cortex-xcor-rum`.
- The marketplace, plugin and skills name the product Cortex XCOR RUM (formerly Embrace).
- The doctor skills stop and tell the user when their knowledge base or the app is missing.

### Migration

If you added the old `embrace-claude-plugin` marketplace or installed `embrace-doctor-ios` or `embrace-doctor-android`, remove them and add the new marketplace and plugin:

```bash
claude plugin marketplace remove embrace-claude-plugin
claude plugin marketplace add embrace-io/cortex-xcor-rum-claude-plugin
claude plugin install cortex-xcor-rum@cortex-xcor-rum
```
