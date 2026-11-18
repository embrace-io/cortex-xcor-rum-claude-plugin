# Changelog

All notable changes to the `cortex-xcor-rum` plugin are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the plugin uses [semantic versioning](https://semver.org/). Versions are unreleased until the pull requests that carry them merge.

## [1.1.1] - Unreleased

### Added

- Root and plugin READMEs covering install, MCP sign-in, skills, example prompts, troubleshooting, updates and privacy.
- `LICENSE` (Apache-2.0), `CONTRIBUTING.md` and this changelog.

## [1.1.0] - Unreleased

### Added

- The plugin bundles the XCOR RUM MCP server (`https://mcp.embrace.io/mcp`, OAuth) in `.mcp.json`.
- `privacyPolicyUrl` in `plugin.json`.

## [1.0.0] - Unreleased

### Added

- One `cortex-xcor-rum` plugin with the `doctor-ios` and `doctor-android` skills, invoked as `/cortex-xcor-rum:doctor-ios` and `/cortex-xcor-rum:doctor-android`.

### Changed

- Replaces the `embrace-doctor-ios` and `embrace-doctor-android` plugins with the single `cortex-xcor-rum` plugin, and renames the marketplace from `embrace-claude-plugin` to `cortex-xcor-rum`. Uninstall the old plugins and install `cortex-xcor-rum@cortex-xcor-rum`.
- The marketplace, plugin and skills name the product Cortex XCOR RUM (formerly Embrace).
- The doctor skills stop and tell the user when their knowledge base or the app is missing.
