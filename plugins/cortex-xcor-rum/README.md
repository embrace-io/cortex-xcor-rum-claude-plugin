# cortex-xcor-rum

This plugin provides Claude Code skills for working with Cortex XCOR RUM (XCOR RUM). It bundles the XCOR RUM MCP server (`https://mcp.embrace.io/mcp`) so those skills can read your app's crashes, sessions, logs, spans and network data.

To install it from the marketplace:

```bash
claude plugin marketplace add embrace-io/embrace-claude-plugin
claude plugin install cortex-xcor-rum@cortex-xcor-rum
```

After you install the plugin, run `/mcp` and sign in to `plugin:cortex-xcor-rum:embrace` (or `embrace`, if you added the server yourself) with your XCOR RUM account.

The current skills are `/cortex-xcor-rum:doctor-ios` and `/cortex-xcor-rum:doctor-android`, which troubleshoot SDK integration issues on each platform.

See the [repository README](https://github.com/embrace-io/embrace-claude-plugin#readme) for sign-in, example prompts, troubleshooting and update steps.
