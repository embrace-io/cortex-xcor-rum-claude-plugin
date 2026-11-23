---
name: platform-discovery
description: Use when the user asks for help with a Cortex XCOR RUM (formerly Embrace) SDK problem or task without saying which platform their app runs on, for example "data stopped arriving in XCOR RUM after our release," "sessions are missing since our last release," "my XCOR RUM integration isn't working," or "which XCOR RUM SDK does this project use?" Detects the app's platform (Android, Apple, React Native, Flutter, Unity or web) from the user's codebase and, when an App ID is known, from their XCOR RUM app data. Asks the user only when that evidence doesn't settle it, then hands off to the plugin's skill for that platform, or says so when the plugin has none yet. Not needed when the user names the platform or calls a platform skill such as `/cortex-xcor-rum:apple-doctor` directly.
disallowed-tools: Bash, Edit, Write, NotebookEdit, WebFetch, Agent
---

# Cortex XCOR RUM platform discovery

This skill works out which XCOR RUM SDK platform the user's app is on, so the request reaches the skill for that platform without the user having to say it. It reads the user's repo first, uses their XCOR RUM app data when it has an App ID, and asks the user only when neither settles the answer.

Embrace was renamed Cortex XCOR RUM (often shortened to XCOR RUM). SDK packages, config files and URLs still use "embrace" (`io.embrace`, `EmbraceIO`, `@embrace-io/...`, `embrace-config.json`), so search for those names.

## What to decide

Decide two things:

1. **The platform**, one of `android`, `apple`, `react-native`, `flutter`, `unity` or `web`. These are the prefixes of the plugin's skill names. `apple` covers iOS, tvOS and watchOS. Note whether a web app uses React, since some web problems depend on it.
2. **The side**, Android or Apple, for a React Native, Flutter or Unity app. These apps build an Android app and an iOS app from one project, and a problem is usually on one of them. A native Android or Apple app has no separate side, and a web app has none.

## Procedure

1. **Use what the user already said.** "React Native", "Flutter", "Unity" and "web" (or a browser, a website, a web app) name the platform: use it and skip the repo search for the platform. Operating system and toolchain words, such as "iOS", "Android", "AGP 8" or "dSYM", don't settle the platform, because a React Native, Flutter or Unity app has them too. They settle the side (step 5), and the repo search still runs to tell a native app from a cross-platform one.

2. **Find the project files.** Use `Glob` from the working directory for these files, at the root and up to three directories down:
   - `build.gradle`, `build.gradle.kts`, `settings.gradle`, `settings.gradle.kts`, `gradle/libs.versions.toml`, `AndroidManifest.xml`
   - `Package.swift`, `Podfile`, `*.xcodeproj/project.pbxproj`, `Embrace-Info.plist`
   - `package.json`
   - `pubspec.yaml`
   - `Packages/manifest.json`, `ProjectSettings/ProjectVersion.txt`

   Also `Glob` `**/src/main/embrace-config.json` at any depth, since a React Native app keeps it in `android/app/src/main/`. Ignore results under `node_modules/`, `Pods/`, `build/`, `.build/`, `DerivedData/`, `.dart_tool/` and `vendor/`, which hold dependencies and build output, not the user's project.

   **Check whether you're inside a larger app.** If the working directory is named `android` or `ios`, its parent may be a React Native, Flutter or Unity app. Look for `package.json`, `pubspec.yaml` or `Packages/manifest.json` in the parent directory before you treat the project as a native app.

   If the working directory has none of these files, the user may have opened a subdirectory of their app. First `Grep` the source in the working directory for SDK imports: `@embrace-io/` or `@embraceio/` (JavaScript and TypeScript), `import EmbraceIO` (Swift), `io.embrace` (Kotlin and Java), `package:embrace` (Dart) and `EmbraceSDK` (C#). The import names the platform as in step 3. If that finds nothing, `Glob` the parent directories, one level at a time and up to three levels, and stop at the first that has the files above.

3. **Look for the XCOR RUM SDK (strong signals).** Use `Grep` on the files from step 2. One match settles the platform for that project:

   | Platform | Strong signal |
   | :- | :- |
   | React Native | `@embrace-io/react-native` in `package.json` |
   | Flutter | an `embrace` dependency in `pubspec.yaml` (`embrace:` under `dependencies`) |
   | Unity | `io.embrace.sdk` in `Packages/manifest.json` |
   | Web | `@embrace-io/web-sdk` or the older `@embraceio/embrace-web-sdk` in `package.json`, or an import or `<script>` that loads `@embrace-io/web-sdk` from a CDN in the app's `.js`, `.mjs`, `.ts` or `.html` files. React when the app also imports `@embrace-io/web-sdk/react-instrumentation` or depends on `react` |
   | Android | `io.embrace` in a Gradle file (`implementation("io.embrace:...")`, the `io.embrace.gradle` or `io.embrace.swazzler` plugin, or the version catalog), or an `embrace-config.json` under `src/main` |
   | Apple | `EmbraceIO` or `embrace-apple-sdk` in `Package.swift`, the `Podfile` or a `project.pbxproj`, or an `Embrace-Info.plist` |

   **The cross-platform SDKs come first.** A React Native, Flutter or Unity app also has `io.embrace` in its `android/` Gradle files and `EmbraceIO` in its `ios/` files, because those SDKs install the native SDKs underneath. When the cross-platform signal is present, the native matches inside its `android/` and `ios/` folders are part of the same app, not separate apps.

4. **If no SDK signal matched, use the project structure (weak signals).** The user may not have installed the SDK yet, or may send OpenTelemetry data without it. Check these in order and stop at the first that matches, so a cross-platform project is never read as the native app inside it:
   1. React Native: a `react-native` or `expo` dependency in `package.json`. An Expo app may have no `android/` or `ios/` folder.
   2. Flutter: `pubspec.yaml` with `sdk: flutter`.
   3. Unity: `ProjectSettings/ProjectVersion.txt` or `Packages/manifest.json` with `com.unity.` packages.
   4. Web: `package.json` with no `react-native` or `expo` dependency, plus a web entry point (`index.html`, a `vite`, `next`, `webpack` or `react-scripts` dependency). React when it depends on `react`.
   5. Android: a Gradle project with the `com.android.application` plugin.
   6. Apple: an `.xcodeproj`, `Package.swift` or `Podfile`.

   The `android/` and `ios/` folders of a React Native, Flutter or Unity project belong to that project, so the last two apply only to a project that isn't one of those. Say that no XCOR RUM SDK was found, since that may be the user's problem.

5. **Decide the side**, for React Native, Flutter and Unity only. Use the first of these that gives an answer:
   - The user's words. Android: Android, Gradle, AGP, NDK, ProGuard, R8, mapping file, ANR, Kotlin, Play Store, APK, AAB. Apple: iOS, iPhone, iPad, tvOS, watchOS, Xcode, dSYM, Swift, Objective-C, CocoaPods, SPM, TestFlight, App Store. A problem that names both ("sessions on iOS but none on Android") is on the side that's failing.
   - The App ID (step 6).
   - Otherwise, ask (step 8).

6. **Use the App ID for anything still open.** If the user gave an App ID and the platform, the side or the app is still open, call the XCOR RUM MCP tool `list_apps` with `limit` 1000 and find the app with that `app_id`, following `next_cursor` if it isn't on the first page. Its `platform` (`ios`, `android` or `web`) is the side, or the platform of a native or web app, and its `framework` (`native`, `react_native`, `flutter` or `unity`) is the platform of a cross-platform app. If no XCOR RUM tool responds, or the App ID isn't in the list, continue without it.

7. **Check for more than one app.** If step 2 found separate projects for different platforms, such as `apps/ios/` and `apps/web/`, and the user's words don't pick one, ask which app the problem is in. A project whose only signals are inside a React Native, Flutter or Unity app's `android/` and `ios/` folders is one app, not two. When only one of the projects has a strong signal (step 3), that project is the app with XCOR RUM, so use it without asking. Ignore a project with no signal of any kind, such as a backend service.

8. **Report, and ask when needed.** Start the reply with one line in this form, so the user can correct it. Write it before anything else, even when the hand-off in step 9 fails:

   `**Platform:** <Android | Apple | React Native | Flutter | Unity | Web>[ (React)][, <Android | Apple> side][, no XCOR RUM SDK found] (<the file and line, or the user's words, that decided it>)`

   When the side or the app isn't settled, write `side not known` or `app not known` in place of the side, and ask one short question with the choices, for example "This is a React Native app. Is the problem on Android, iOS, or both?" When both the app and its side are open, ask both in that one question. When nothing identifies the platform, write `**Platform:** not detected` and ask which platform the app is on. Never guess a platform or a side to avoid asking.

9. **Hand off.** Pick the skill for the platform from the `cortex-xcor-rum` skills listed as available in this session, whose names start with the platform: `android-`, `apple-`, `react-native-`, `flutter-`, `unity-` or `web-`. Read each candidate's description and choose the one that fits the user's task. Don't search the filesystem for skills: the session's skill list is the set you can load.
   - For React Native, Flutter and Unity, prefer a skill with that platform's own prefix. If there is none, use the side's skill (`android-` or `apple-`) when its description says it covers that platform's side.
   - When the user says the problem is on both sides and no skill has the platform's own prefix, start with one side's skill and tell the user you'll check the other side's next.
   - Load the chosen skill with the user's original request and the platform you found, and let it take over.
   - If no skill covers the platform and the task, say so plainly, and point the user to their XCOR RUM tech-support Slack channel if they have one, otherwise the [XCOR RUM community Slack](https://community.embrace.io) or [xcorsupport@paloaltonetworks.com](mailto:xcorsupport@paloaltonetworks.com). Don't answer the SDK question from general knowledge.

## Hard rules

- **Never reproduce secrets.** Before you quote a file, replace every credential with `<redacted>`: `api_token` in `embrace-config.json`, any `*_TOKEN`, `*_KEY`, `*_SECRET` or `*PASSWORD*` value, signing and keystore values, repository credentials and `Authorization` headers. Quote only the lines that show the platform. Don't read `.env` files, keystores, `local.properties` or provisioning profiles. `Grep` files that can hold credentials (`embrace-config.json`, `Embrace-Info.plist`, `gradle.properties`, `.xcconfig` files) for the non-secret key you need, and never read them whole.
- **Read only.** Use `Read`, `Grep`, `Glob` and the XCOR RUM MCP tools. Don't run builds, package managers, scripts or network commands, and don't change files.
- **Evidence, not guesses.** Every platform you report names the file or the user's words behind it. When the evidence conflicts or is missing, ask. A wrong platform sends the user to the wrong skill, which costs more than one question.
- **Ask once.** Ask at most one question, with the choices in it, and continue with the user's answer.
- **Call the product XCOR RUM** in your replies, even when the user says Embrace. Code, package and file names stay as they are.
