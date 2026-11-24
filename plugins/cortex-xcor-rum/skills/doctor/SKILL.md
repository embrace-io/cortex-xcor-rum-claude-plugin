---
name: doctor
description: Use when the user asks to run the Cortex XCOR RUM (formerly Embrace) doctor, or to diagnose or troubleshoot an XCOR RUM SDK integration problem without saying which platform their app runs on, for example "run the XCOR RUM doctor," "diagnose my XCOR RUM setup," "check my XCOR RUM integration," "data stopped arriving in XCOR RUM after our release," or "sessions are missing since our last release." Detects the app's platform with `/cortex-xcor-rum:platform-discovery`, then runs that platform's doctor skill, such as `/cortex-xcor-rum:apple-doctor` or `/cortex-xcor-rum:android-doctor`. Not needed when the user calls a platform's doctor directly.
disallowed-tools: Bash, Edit, Write, NotebookEdit, WebFetch, Agent
---

# Cortex XCOR RUM doctor

This skill is the one command for diagnosing an XCOR RUM SDK problem whatever the platform. It finds the app's platform, then runs the doctor skill for that platform, or points the user to support where the plugin has no doctor for it yet. The doctor matches the problem against known patterns and checks the user's repo and XCOR RUM data.

## Procedure

1. **Check that `cortex-xcor-rum:platform-discovery` is listed** among the skills available in this session. If it isn't, say that the plugin install looks incomplete and that reinstalling the `cortex-xcor-rum` plugin should restore it. Then ask which platform the app is on, and load the doctor skill whose description covers that platform, or that platform's side for a React Native, Flutter or Unity app. If no doctor's description covers it, say so and point the user to their XCOR RUM tech-support Slack channel if they have one, otherwise the [XCOR RUM community Slack](https://community.embrace.io) or [xcorsupport@paloaltonetworks.com](mailto:xcorsupport@paloaltonetworks.com).

2. **Otherwise, load `cortex-xcor-rum:platform-discovery`**, and pass it the user's request plus a note that the task is a doctor diagnosis. Don't write anything to the user first. Load it even when the user names a platform: a word such as "Android" or "iOS" doesn't tell a native app from a React Native, Flutter or Unity app, and `platform-discovery` uses the user's words where they settle the answer. It writes the `**Platform:**` line, asks the user only when the evidence doesn't settle the platform, and hands off to the platform's `-doctor` skill, or points the user to support when no doctor covers the platform. Load it even when the user gave no problem: the platform's doctor asks for what it needs.

3. **Don't diagnose from general knowledge.** The platform's doctor does the diagnosis.

## Hard rules

- **Never reproduce secrets.** If you quote a file, replace every credential with `<redacted>`: `api_token` in `embrace-config.json`, any `*_TOKEN`, `*_KEY`, `*_SECRET` or `*PASSWORD*` value, signing and keystore values, repository credentials and `Authorization` headers. Don't read `.env` files, keystores, `local.properties` or provisioning profiles.
- **Read only.** Use `Read`, `Grep`, `Glob`, the XCOR RUM MCP tools and the plugin's skills. Don't run builds, package managers, scripts or network commands, and don't change files.
- **Call the product XCOR RUM** in your replies, even when the user says Embrace. Code, package and file names stay as they are.
