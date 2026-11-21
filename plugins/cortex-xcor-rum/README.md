# cortex-xcor-rum

This plugin provides Claude Code skills for working with Cortex XCOR RUM (Real User Monitoring). It bundles the XCOR RUM MCP server (`https://mcp.embrace.io/mcp`) so those skills can read your app's crashes, sessions, logs, spans and network data.

To install it from the marketplace:

```bash
claude plugin marketplace add embrace-io/cortex-xcor-rum-claude-plugin
claude plugin install cortex-xcor-rum@cortex-xcor-rum
```

After you install the plugin, run `/mcp` and sign in to `plugin:cortex-xcor-rum:xcor-rum` (or the name you gave it, if you added the server yourself) with your XCOR RUM account.

The current skills are `/cortex-xcor-rum:doctor-ios` and `/cortex-xcor-rum:doctor-android`, which troubleshoot SDK integration issues on each platform, and `/cortex-xcor-rum:apple-migrate-6-to-7`, which migrates an Apple platform app from SDK 6.x to 7.x and builds it to verify.

See the [repository README](https://github.com/embrace-io/cortex-xcor-rum-claude-plugin#readme) for sign-in, example prompts, troubleshooting and update steps.
