<picture>
  <source srcset="assets/cortex-xcor-dark-bg.svg" media="(prefers-color-scheme: dark)" />
  <source srcset="assets/cortex-xcor-light-bg.svg" media="(prefers-color-scheme: light), (prefers-color-scheme: no-preference)" />
  <img src="assets/cortex-xcor-light-bg.svg" alt="Cortex XCOR Real User Monitoring" width="334" />
</picture>

# Cortex XCOR RUM plugin for Claude Code

This repository is a Claude Code plugin marketplace for Cortex XCOR RUM (Real User Monitoring), formerly Embrace. It publishes one plugin, `cortex-xcor-rum`, which holds our Claude skills and connects Claude Code to the XCOR RUM MCP server so the skills can read your app's data.

## Prerequisites

- [Claude Code](https://code.claude.com/docs/en/overview)
- An XCOR RUM account with access to at least one app

## Install

Add the marketplace, then install the plugin from it:

```bash
claude plugin marketplace add embrace-io/cortex-xcor-rum-claude-plugin
claude plugin install cortex-xcor-rum@cortex-xcor-rum
```

Restart Claude Code (or run `/reload-plugins`) so it loads the plugin. You can also run both steps inside a session with `/plugin marketplace add` and `/plugin install`.

## Sign in to the MCP server

The plugin bundles the XCOR RUM MCP server (`https://mcp.embrace.io/mcp`, named `xcor-rum`). It uses OAuth, so no token is stored in the plugin.

1. Start Claude Code and run `/mcp`.
2. Select `plugin:cortex-xcor-rum:xcor-rum` (or the name you gave it, if you added the server yourself) and choose to authenticate.
3. Sign in with your XCOR RUM account in the browser. The token carries your existing app permissions.

If you already added the server yourself with the same URL (for example with `claude mcp add`), Claude Code keeps one connection and you don't need to change anything.

For CI jobs or shared tooling, you can authenticate with a service-account token instead of OAuth. The [XCOR RUM MCP docs](https://embrace.io/docs/mcp/) describe how to create one and add the server with it.

## Skills

The plugin holds all of our Claude skills. Each skill runs as `/cortex-xcor-rum:<name>`, and Claude also loads one on its own when your request matches its description.

| Skill | What it covers |
| :- | :- |
| `/cortex-xcor-rum:apple-doctor` | Troubleshoots XCOR RUM SDK integration issues on Apple platforms (iOS, tvOS and watchOS), including the iOS side of React Native, Flutter and Unity apps, such as unsymbolicated crashes, missing crashes, uncaptured network calls, build failures after an upgrade, and dSYM upload failures. |
| `/cortex-xcor-rum:android-doctor` | Troubleshoots XCOR RUM SDK integration issues on native Android and the Android side of React Native and Unity apps, such as missing NDK crashes, failed mapping uploads, a stripped `embrace-config.json`, dependency conflicts, and missing sessions. |
| `/cortex-xcor-rum:doctor` | The one command for diagnosing an XCOR RUM SDK problem whatever your platform. It detects your app's platform with `platform-discovery`, then runs that platform's doctor skill. Where the plugin has no doctor for your platform yet (web, and the Android side of Flutter apps), it says so and points you to support. Type the full `/cortex-xcor-rum:doctor`: a bare `/doctor` runs Claude Code's own setup checkup. |
| `/cortex-xcor-rum:platform-discovery` | Works out which XCOR RUM SDK platform your app uses (Android, Apple, React Native, Flutter, Unity or web) from your codebase, and from your app's data when you give an App ID, then hands your request to the skill for that platform. Claude can load it on its own when a request needs the platform. Where the plugin has no skill for your platform yet, it says so and points you to support. It asks you only when the evidence doesn't settle the platform, such as which side of a React Native app has the problem. |

`apple-doctor` and `android-doctor` match your problem against a catalog of recurring tech-support patterns. They check your codebase and your app's data from the MCP server, then return a diagnosis, a fix, or an escalation package for XCOR RUM support. Each one sends issues for the other platform to its counterpart.

## Example prompts

Call a skill by name and describe the problem:

```text
/cortex-xcor-rum:doctor data stopped arriving in XCOR RUM after our last release
/cortex-xcor-rum:apple-doctor crashes aren't symbolicated since we moved to Xcode Cloud
/cortex-xcor-rum:android-doctor NDK crashes stopped after upgrading to 7.x
```

Or describe the problem in plain language and let Claude pick the skill:

```text
Crashes stopped showing up in the XCOR RUM dashboard for our iOS app.
Mapping file upload fails on CI after our AGP 8 upgrade.
Our React Native app has sessions on iOS but none on Android.
Data stopped arriving in XCOR RUM after our last release.
```

The last prompt names no platform. Claude can then load `doctor`, which finds the platform with `platform-discovery` before it hands off to that platform's doctor.

A skill also runs by its short name, such as `/apple-doctor`, when no other command has that name. `doctor` is the exception: `/doctor` is Claude Code's own setup checkup, so use `/cortex-xcor-rum:doctor`.

## Troubleshooting

**The MCP server needs authentication.** Run `/mcp`, select `plugin:cortex-xcor-rum:xcor-rum` (or the name you gave it, if you added the server yourself) and authenticate. If the sign-in has expired, authenticate again from the same menu.

**The MCP server can't see your app.** The server returns the apps your XCOR RUM user can access, so confirm that you signed in with an account that has access to the app and that you gave the skill the right App ID. With a bearer token, check that the service account has access to the app and that the token has the `mcp:tools:call` scope plus `mcp:read` and/or `mcp:write`.

**A skill says the knowledge base is missing.** Each doctor skill reads `MCP_SKILL_QA_INDEX.yaml` from its own folder in the installed plugin. If that file can't be read, the skill stops instead of guessing. Update or reinstall the plugin to restore it.

**You don't see a new release.** Claude Code doesn't update plugins from this marketplace automatically unless you turn on auto-update for it in `/plugin` under Marketplaces. Follow the update steps below.

## Get help

If a doctor skill escalates or you have a question it can't answer, send the escalation package to your XCOR RUM tech-support Slack channel if you have one. Otherwise, ask in the [XCOR RUM community Slack](https://community.embrace.io) or email [xcorsupport@paloaltonetworks.com](mailto:xcorsupport@paloaltonetworks.com).

## Update and uninstall

Update the marketplace listing, then the plugin, and restart Claude Code to apply it:

```bash
claude plugin marketplace update cortex-xcor-rum
claude plugin update cortex-xcor-rum@cortex-xcor-rum
```

To uninstall, remove the plugin and, if you no longer want its listing, the marketplace:

```bash
claude plugin uninstall cortex-xcor-rum@cortex-xcor-rum
claude plugin marketplace remove cortex-xcor-rum
```

## Privacy

The plugin sends no data on its own. After you sign in to the MCP server, Claude Code requests your app's data from XCOR RUM when a skill or prompt calls the server's tools, and passes the results to Claude. See the [privacy policy](https://embrace.io/docs/privacy-policy) for how XCOR RUM handles data.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add a skill, bump the version and test changes locally.

## Trademarks

CORTEX XCOR™ is our trademark. This plugin is built for Claude Code by the Cortex XCOR RUM team. It is not an official Anthropic repository, and Anthropic does not maintain or endorse it.

## License

Apache License 2.0. See [LICENSE](LICENSE).
