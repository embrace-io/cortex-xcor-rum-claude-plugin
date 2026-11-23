# platform-discovery eval

This eval measures how accurately the `platform-discovery` skill detects an app's platform from its repository. It runs the skill on a fixed corpus of public projects and scores each answer as right, asked or wrong. Nothing here ships with the plugin.

## The corpus

`corpus.json` lists 19 public projects, each pinned to a commit, and 2 synthetic projects built from them. Each case pairs a project with a prompt and the answer written down before any run.

- **Projects with the SDK:** our demo apps for Android, iOS, React Native and Flutter, the example apps in the Android, Apple, web, Flutter and Unity SDK repositories, a Next.js monorepo that uses the older `@embraceio/embrace-web-sdk` package, and a webOS app that loads the web SDK from a CDN with no `package.json` dependency.
- **Projects without the SDK:** open-source Android, SwiftUI, Expo, React and Flutter apps, and two of our samples that send OpenTelemetry data without the SDK. These test the structural signals alone.
- **Synthetic projects:** `multi-app` holds an Apple app and a web app, both with the SDK. `brownfield` is a native Android app with the SDK that embeds React Native screens without the React Native SDK.
- **Prompts:** a symptom that names no platform, plus symptoms that name the Android or the Apple side, for the cross-platform projects. Two cases start the session in a subdirectory (`app/`, `src/`).

For a React Native, Flutter or Unity app with a prompt that names no side, the right answer is to ask for the side. Naming a side there counts as wrong.

## How a run works

`run.py run` starts one headless Claude Code session per case (`claude -p`) in the project's directory, loads the plugin from this checkout with `--plugin-dir`, and calls `/cortex-xcor-rum:platform-discovery` with the case's prompt. It reads the `**Platform:**` line the skill writes and scores it:

- **right:** the platform matches and, where it applies, so does the side, or the skill asked where it should.
- **asked:** the skill asked where the answer was definite. This costs the user a question but sends nobody to the wrong skill.
- **wrong:** any definite answer that differs from the expected one.

Mismatches in whether the SDK is installed, or whether a web app uses React, are reported as notes and don't change the verdict.

Each session runs with only `Read`, `Grep` and `Glob`, with no MCP servers and with an empty Claude Code configuration directory. The eval therefore measures detection from the repository alone: it doesn't test the App ID lookup through `list_apps`, the hand-off to a platform skill, or whether Claude loads the skill on its own from its description. Interactive sessions can also ask for permission to read a parent directory, which a headless session can't grant.

`fetch` strips `.claude/`, `.cursor/`, `.mcp.json`, `CLAUDE.md`, `AGENTS.md`, `.git` and symlinks from each project, then runs `git init` in it. The strip keeps another project's settings, hooks and instructions out of the session. The new repository makes each project's own `.gitignore` apply, as it does for a user. It also stops ripgrep, which Claude Code's `Grep` and `Glob` use, from applying the `.gitignore` of a repository the corpus directory sits in, which would hide every file below a project's top level.

## Run it

```bash
python3 evals/platform-discovery/run.py fetch --corpus-dir /path/outside/the/plugin
python3 evals/platform-discovery/run.py run --corpus-dir /path/outside/the/plugin --model sonnet
```

`run` prints each verdict and a summary, and writes every answer, its tool calls and its cost to `platform-discovery-results.json`. `--only <regex>` runs a subset of cases by id, and `rescore <results.json>` scores a results file again after a change to the parser or the corpus. Rerun the eval after any change to the skill's procedure and compare the summary with the results below.

## Results

Measured on 2026-11-23 with Claude Code 2.1.330, against the skill in this commit. Each model ran the 29 cases once:

| Model | Right | Asked | Wrong | Cost | Mean time per case | Mean tool calls |
| :- | -: | -: | -: | -: | -: | -: |
| Sonnet (`claude-sonnet-5-5`) | 29 | 0 | 0 | $1.26 | 8 s | 3.6 |
| Opus (`claude-opus-5-5`) | 29 | 0 | 0 | $2.44 | 11 s | 3.0 |

Two rounds before these found gaps in the skill, each fixed in this commit:

- Sonnet asked for the platform in the case that starts in `src/`, twice, because a headless session can't get permission to read the parent directory. The skill now searches the source in the working directory for SDK imports first.
- One Sonnet run detected the platform correctly but wrote no `**Platform:**` line: with no skill to hand off to, it went looking for skills on disk and replied about that instead. The skill now writes the line first and loads skills only from the session's skill list.

The corpus is small. 29 of 29 shows the rules handle these layouts. It doesn't put a bound on the error rate for projects unlike them.
