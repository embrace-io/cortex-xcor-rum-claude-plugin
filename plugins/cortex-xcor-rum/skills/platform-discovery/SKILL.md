---
name: platform-discovery
description: Use when a Cortex XCOR RUM (formerly Embrace) SDK task needs the app's platform and the user hasn't said which platform their app runs on, for example "which XCOR RUM SDK does this project use?", "is this a React Native or a native app?", or a request that one of the plugin's platform skills covers. To diagnose a problem, use `/cortex-xcor-rum:doctor`, which calls this skill. Detects the app's platform (Android, Apple, React Native, Flutter, Unity or web) from the user's codebase and, when an App ID is known, from their XCOR RUM app data. Asks the user only when that evidence doesn't settle it, then hands off to the plugin's skill for that platform, or says so when the plugin has none yet. Not needed when the user calls a platform skill such as `/cortex-xcor-rum:apple-doctor` directly.
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

1. **Use what the user already said.** "React Native", "Flutter" and "Unity", and "web" (a website or web app) when it describes the user's own app, name the platform: use it and skip the repo search for the platform. "Web" about something else, such as "the web dashboard" or "in my browser", names nothing. If the files you read later contradict the user's words, say so and ask. Operating system and toolchain words, such as "iOS", "Android", "AGP 8" or "dSYM", don't settle the platform, because a React Native, Flutter or Unity app has them too. They settle the side (step 5), and the repo search still runs to tell a native app from a cross-platform one.

2. **Find the project files.** Use `Glob` from the working directory for these files, at the root and up to three directories down:
   - `build.gradle`, `build.gradle.kts`, `settings.gradle`, `settings.gradle.kts`, `gradle/libs.versions.toml`, `AndroidManifest.xml`
   - `Package.swift`, `Podfile`, `*.xcodeproj/project.pbxproj`, `Embrace-Info.plist`
   - `package.json`
   - `pubspec.yaml`
   - `Packages/manifest.json`, `ProjectSettings/ProjectVersion.txt`

   Also `Glob` `**/src/main/embrace-config.json` at any depth, since a React Native app keeps it in `android/app/src/main/`. Ignore results under `node_modules/`, `Pods/`, `build/`, `.build/`, `DerivedData/`, `.dart_tool/` and `vendor/`, which hold dependencies and build output, not the user's project.

   **Check whether you're inside a larger app.** If any directory in the working directory's path is named `android` or `ios`, such as `android/app/` or `android/app/src/main/kotlin/`, the app may be a React Native, Flutter or Unity app opened inside its native folder. Do this check before anything else in this step, including the import search below, and settle it before you treat the project as native. Look for these framework markers in the Gradle files, `Podfile` and Xcode project files from the working directory up to that `android` or `ios` folder (`Glob` each parent directory in turn), and in the `package.json`, `pubspec.yaml` or `Packages/manifest.json` of the directory above it:
   - Flutter: `dev.flutter.flutter-gradle-plugin` or `flutter.sdk` in a Gradle file, `flutter_install_all_ios_pods` in the `Podfile`, a `Flutter/Generated.xcconfig` reference, or an `io.flutter` import (Kotlin and Java) or `import Flutter` (Swift) in the source.
   - React Native: `com.facebook.react` in a Gradle file, `use_react_native!` or `react_native_pods` in the `Podfile`, or a `com.facebook.react` import (Kotlin and Java) or `import React` (Swift and Objective-C) in the source.
   - Unity: a `unityLibrary` Gradle module or a `UnityFramework` target.

   - A manifest above the folder counts only with the conditions in step 4: a `react-native` or `expo` dependency in `package.json`, `sdk: flutter` in `pubspec.yaml`, or `com.unity.` packages in `Packages/manifest.json`. A `package.json` that holds only tooling doesn't make a native app a React Native one.

   One of these markers makes the project that framework's app, and the folder you're in is its side. The exception is a native app that embeds React Native screens or a Unity library: when the native XCOR RUM SDK (step 3) is installed and you can see the framework's manifest has no XCOR RUM SDK of its own, the app is native.

   If the working directory has none of these files, the user may have opened a subdirectory of their app. First `Grep` the source in the working directory for SDK imports: `@embrace-io/` or `@embraceio/` (JavaScript and TypeScript), `import EmbraceIO` (Swift), `io.embrace` (Kotlin and Java), `package:embrace` (Dart) and `EmbraceSDK` (C#). The import names the platform as in step 3, unless the path check above found a framework app. A package or folder name that contains `embrace`, such as `package io.embrace.shop`, isn't an import. If that finds nothing, `Glob` the parent directories, one level at a time and up to three levels, and stop at the first that has the files above.

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
   - Otherwise, ask (step 8). Don't infer the side from which native folders or exports exist: a project with only an `android/` folder or an Android export can still have the problem on iOS, or on both.

6. **Use the App ID for anything still open.** If the user gave an App ID and the platform, the side or the app is still open, call the XCOR RUM MCP tool `list_apps` with `limit` 1000 and find the app with that `app_id`, following `next_cursor` if it isn't on the first page. Its `platform` (`ios`, `android` or `web`) is the side, or the platform of a native or web app, and its `framework` (`native`, `react_native`, `flutter` or `unity`) is the platform of a cross-platform app. If no XCOR RUM tool responds, or the App ID isn't in the list, continue without it.

7. **Check for more than one app.** If step 2 found separate projects for different platforms, such as `apps/ios/` and `apps/web/`, and the user's words don't pick one, ask which app the problem is in. A project whose only signals are inside a React Native, Flutter or Unity app's `android/` and `ios/` folders is one app, not two. When only one of the projects has a strong signal (step 3), that project is the app with XCOR RUM, so use it without asking. Ignore a project with no signal of any kind, such as a backend service.

8. **Report, and ask when needed.** Start the reply with one line in this form, so the user can correct it. Write it as text before anything else, including before you load another skill in step 9, and even when that hand-off fails:

   `**Platform:** <Android | Apple | React Native | Flutter | Unity | Web>[ (React)][, <Android | Apple> side][, no XCOR RUM SDK found] (<the file and line, or the user's words, that decided it>)`

   For a React Native, Flutter or Unity app the line always names the side or says `side not known`. When the side isn't settled, write `side not known` in place of the side, and ask one short question with the choices, for example "This is a React Native app. Is the problem on Android, iOS, or both?" When several apps were found and the user's words don't pick one, write `**Platform:** app not known`, followed by the apps you found. When both the app and its side are open, ask both in that one question. When nothing identifies any platform, write `**Platform:** not detected` and ask which platform the app is on, and, if it's a React Native, Flutter or Unity app, which side has the problem, in the same question. Never guess a platform or a side to avoid asking.

9. **Hand off.** Pick the skill for the platform from the `cortex-xcor-rum` skills listed as available in this session, whose names start with the platform: `android-`, `apple-`, `react-native-`, `flutter-`, `unity-` or `web-`. Read each candidate's description and choose the one that fits the user's task. Don't search the filesystem for skills: the session's skill list is the set you can load.
   - If the user only asked about the platform or the SDK ("which XCOR RUM SDK does this project use?"), answer from what you found and stop. Hand off only when the request is a task for one of the platform skills, such as a problem to diagnose.
   - For React Native, Flutter and Unity, prefer a skill with that platform's own prefix. If there is none, a side skill (`android-` or `apple-`) covers the case only if its description contains the framework's name: "React Native", "Flutter" or "Unity". **Check this literally before you load it.** If the name isn't in the description, don't load that skill, even when its checks look relevant because the framework uses the native SDK underneath: no skill covers the case (the last bullet).
   - When the user says the problem is on both sides and no skill has the platform's own prefix, hand off to one side's skill, and tell the user to run the same command again for the other side once that is done. If the other side has no skill, say so and point to support (the last bullet) instead of suggesting a rerun.
   - Load the chosen skill with the user's original request and the platform you found, and let it take over. Hand off even when the request names no problem, such as "run the doctor": the chosen skill asks for what it needs.
   - If no skill covers the platform and the task, say so plainly, and point the user to their XCOR RUM tech-support Slack channel if they have one, otherwise the [XCOR RUM community Slack](https://community.embrace.io) or [xcorsupport@paloaltonetworks.com](mailto:xcorsupport@paloaltonetworks.com). Don't answer the SDK question from general knowledge.

## Hard rules

- **Never reproduce secrets.** Before you quote a file, replace every credential with `<redacted>`: `api_token` in `embrace-config.json`, any `*_TOKEN`, `*_KEY`, `*_SECRET` or `*PASSWORD*` value, signing and keystore values, repository credentials and `Authorization` headers. Quote only the lines that show the platform. Don't read `.env` files, keystores, `local.properties` or provisioning profiles. `Grep` files that can hold credentials (`embrace-config.json`, `Embrace-Info.plist`, `gradle.properties`, `.xcconfig` files) for the non-secret key you need, and never read them whole.
- **Read only.** Use `Read`, `Grep`, `Glob` and the XCOR RUM MCP tools. Don't run builds, package managers, scripts or network commands, and don't change files.
- **Evidence, not guesses.** Every platform you report names the file or the user's words behind it. When the evidence conflicts or is missing, ask. A wrong platform sends the user to the wrong skill, which costs more than one question.
- **Ask once.** Ask at most one question, with the choices in it, and continue with the user's answer.
- **Call the product XCOR RUM** in your replies, even when the user says Embrace. Code, package and file names stay as they are.
