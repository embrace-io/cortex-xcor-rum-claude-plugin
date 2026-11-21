---
name: apple-migrate-6-to-7
description: 'Use when the user wants to upgrade an iOS, tvOS, macOS or watchOS app from the Cortex XCOR RUM (formerly Embrace) Apple SDK 6.x to 7.x, or when the build breaks after bumping the SDK to 7.x, for example "migrate this app from Embrace 6 to 7," "upgrade the XCOR RUM SDK to 7.1," "cannot find ''Embrace'' in scope," "value of type ''EmbraceIO'' has no member ''buildSpan''," "type ''EmbraceIO'' has no member ''setup''," "no such module ''EmbraceCrash''," "Missing package product ''EmbraceCrash''," or "extra trailing closure / try expression errors after the Embrace update." Inventories every 6.x call site in the codebase, applies the verified 6.x to 7.x API mappings, flags removals that have no replacement, and builds the project to verify. Other iOS integration issues are covered by `/cortex-xcor-rum:doctor-ios`.'
allowed-tools: Read(//**/skills/apple-migrate-6-to-7/API_MAPPING.md)
---

# Cortex XCOR RUM Apple SDK 6.x to 7.x migration

You are migrating an app from the Cortex XCOR RUM Apple SDK 6.x to 7.x. Your job: inventory every 6.x call site, rewrite each one with the mapping in `${CLAUDE_SKILL_DIR}/API_MAPPING.md`, surface the removals that need the user's decision, and build the project until the XCOR RUM errors are gone.

Embrace was renamed Cortex XCOR RUM (often shortened to XCOR RUM). Treat the two names as the same product: users, docs and tickets may use either. The SDK's modules, types, packages and URLs still use "embrace" (`EmbraceIO`, `embrace-apple-sdk`, pod `EmbraceIO`), so search the repo for those names.

7.0 replaces the `Embrace.client` entry point with `EmbraceIO.shared`, collapses `setup` and `start` into a single `EmbraceIO.start(options:)`, replaces OpenTelemetry SDK types in the public API with SDK-owned types, drops `throws` from the public API, removes the Objective-C public surface, and redefines what a session is (see Behavioral changes). 7.1 only adds API, so the same mapping applies to every 7.x release. Most changes are mechanical renames. A handful are removals that need a decision from the user.

## Ground rules

- **`API_MAPPING.md` is the single source of truth.** Read `${CLAUDE_SKILL_DIR}/API_MAPPING.md` in full before you change any file. If it can't be read, stop: tell the user that this skill's API mapping is missing from their install of the `cortex-xcor-rum` plugin and that reinstalling the plugin should restore it. Don't migrate without it. Every mapping in it was verified against the 7.x public API. Don't invent APIs that aren't listed there. If a call site matches nothing in the mapping file, say so and escalate. Don't guess a replacement.
- **Never silently delete functionality.** When a call site uses an API listed under "Removed with no replacement," show the user the call site, explain the removal, and let them choose: drop it, or apply the suggested workaround. Calls that are now no-ops by design (for example a bare `try`, `try?` or `try!`) are the exception: apply those directly.
- **Migrate, don't refactor.** Keep the app's existing structure, naming and style. The diff should be the minimum needed to compile and preserve behavior on 7.x.
- **Verify with a build, not by eyeballing.** A migration that hasn't compiled isn't done.

## Procedure

### 1. Preflight

1. Determine the current SDK version and integration method. Read it from the repo, never guess:
   - SPM: `Package.swift`, `Package.resolved`, or the Xcode project's `Package.resolved` (search for `embrace-apple-sdk`).
   - CocoaPods: `Podfile` and `Podfile.lock` (pod `EmbraceIO`).
2. **If the app is on 5.x or earlier, stop.** This skill only covers 6.x to 7.x. The 5.x to 6.x migration is a separate, larger effort, and the app needs that upgrade first.
3. **Check for Objective-C usage of the SDK.** Grep `.m`, `.mm` and `.h` files for `Embrace`. The 7.x public API has no `@objc` surface, so Objective-C call sites can't be migrated. If you find any, stop and escalate before you change anything (see Escalation).
4. **Check for a custom `CrashReporter` conformance** (`: CrashReporter` outside the SDK). The protocol is no longer public in 7.x. If you find one, flag it now: the app must either drop the custom reporter or escalate.
5. **Check the working tree.** Run `git status`. If there are uncommitted changes, tell the user, so the migration diff stays separate from their own work, and ask whether to continue.
6. **Confirm before editing.** If the user asked for the migration, continue. If they only reported a build error, show what you found in steps 1 to 4 and the step 2 inventory, then ask before you change files.

### 2. Inventory 6.x call sites

Grep the app source with these patterns, excluding `Pods/`, package checkouts and build directories, and collect every hit into a checklist:

```text
Embrace\.client
Embrace\.setup|Embrace\.Options|Embrace\.Endpoints
EmbraceIO\.setup|EmbraceIO\.shared
\.start\(|\.stop\(
buildSpan|recordSpan|recordCompletedSpan|startSpan\(\)
add\(event:|add\(events:|\.breadcrumb\(
addBreadcrumb|addSessionEvent
\.log\(
setAttribute
userName|userEmail|clearUserProperties|userIdentifier
addProperty|updateProperty|removeProperty|setProperty
addResource|updateResource|removeResource|removeAllResources
addPersona|removePersona|currentPersonas|PersonaTag
lifespan:
appendCrashInfo|lastRunEndState|crash\(type:|ExampleCrash
currentSessionId|startNewSession|endCurrentSession|resetUploadCache
startupInstrumentation|StartupChildSpan|addAttributesToStartupTrace
add\(notification:|addPushNotificationEvent
tracer\(instrumentationName:|OpenTelemetryExport|OpenTelemetryProcessor
OpenTelemetry.instance|TracerProviderSdk|LoggerProviderSdk
CaptureService|CaptureServiceBuilder|KSCrashReporter|CrashlyticsReporter
WebViewCaptureService
trackExperiment|untrackExperiment|trackFeatureFlag|untrackFeatureFlag
import EmbraceCrash|import EmbraceCrashlyticsSupport|import OpenTelemetryApi|import OpenTelemetrySdk
SpanType|LogType|LogSeverity|SpanErrorCode|StackTraceBehavior|LastRunEndState|MetadataLifespan|MetadataError
injectTracingHeader|flush\(|appGroupId
```

Then grep the project files, not just the source, because some dependencies are declared only there. Grep every `project.pbxproj`, plus `Podfile` and `Podfile.lock`, for `EmbraceCrash|EmbraceCrashlyticsSupport`. A hit in `project.pbxproj` with no matching `import EmbraceCrash` in source still breaks the build: the target declares a package product that no longer exists, and step 3 must remove it. The source greps above don't catch this.

6.20 and later already ship an `EmbraceIO.shared` facade, so a codebase may mix `Embrace.client?.…` and `EmbraceIO.shared.…` styles. The mapping file covers both, so inventory both.

### 3. Update the dependency

- SPM: point `embrace-apple-sdk` at 7.x with the rule Up to Next Major Version from `7.0.0`, which resolves to the latest 7.x release.
- **Remove the dead crash products from the project, not just the imports.** The `EmbraceCrash` and `EmbraceCrashlyticsSupport` library products no longer exist, because both reporters are bundled into `EmbraceIO`. A target can declare them as package-product dependencies in `project.pbxproj` even when no source file imports them. Delete those references from every target (main app, watch app, extensions), or the build fails with `Missing package product 'EmbraceCrash'`. Step 2 finds them.
- CocoaPods: set pod `EmbraceIO` to `'~> 7.0'`.
- 7.x raises the minimum deployment targets to iOS 15, tvOS 15 and watchOS 9 (macOS stays at 13). If any target (app, watch app, extensions) is below these, tell the user and confirm before you raise it. Don't lower or otherwise change targets that already meet them.

### 4. Apply mappings

Work through the checklist from step 2 file by file, using `API_MAPPING.md`. This order minimizes intermediate breakage:

1. **Imports.** Drop `EmbraceCrash` and `EmbraceCrashlyticsSupport`. Drop `OpenTelemetryApi` and `OpenTelemetrySdk` unless the file configures `OTelOptions` exporters. `import EmbraceIO` re-exports everything else the app needs.
2. **Startup and options.** The entry point, `EmbraceIO.start(options:)`, the crash reporter enum, `OTelOptions` (including `registersGlobalProviders`) and the capture services builder.
3. **Mechanical renames** from the types table in the mapping file.
4. **Call-site rewrites** for spans, logs, session events, breadcrumbs, metadata, startup and push. Two of these fail quietly: every `lifespan: .session` becomes `lifespan: .userSession` (mapping §7.0), and `span.addEvent` has no default for `attributes:` (mapping §5.3).
5. **`try` removal.** The public API no longer throws, except `EmbraceIO.start(options:)` and `stop()`. Remove the now-dead `try`, `try?` and `try!`, `do`/`catch` blocks that only wrapped SDK calls, and error-handling branches that can no longer run. If a `catch` block did something meaningful (analytics, a fallback), point it out: on 7.x the failure is a silent no-op plus an SDK warning log, so that handling never runs.
6. **Removals.** Surface each one to the user with the suggested workaround from the mapping file.

### 5. Verify

1. Build the project with `xcodebuild` for the app's scheme, or `swift build` for a package. For CocoaPods, run `pod install` first. Tell the user which command you're about to run. Iterate until the XCOR RUM errors are gone.
2. If the build fails with `Macro "EmbraceMacroPlugin" … must be enabled before it can be used`, that is Xcode's Swift-macro trust prompt for the SDK's macro plugin, not a migration error. The user can click "Trust & Enable" in Xcode, or you can pass `-skipMacroValidation` to `xcodebuild`. Mention this before the user hits it, so they don't mistake it for a broken migration.
3. Re-run the step 2 greps. Every remaining hit must be correct 7.x usage or an item the user explicitly chose to keep or drop.
4. If the project has tests that touch the SDK, run them.
5. Report the files changed, the mappings applied, the removals the user decided on, anything escalated, and the behavioral changes below.

## Behavioral changes to call out

These compile but behave differently, so include them in the final report even when the build is clean:

- **There is no separate `setup` step.** `EmbraceIO.start(options:)` configures and starts the SDK in one call, on the main thread. If the app deliberately delayed `start()` (for example for consent gating) by calling `setup` early and `start()` later, that split is gone: call `EmbraceIO.start(options:)` where `start()` used to run.
- **Failures are silent.** APIs that used to throw now drop the operation and log an SDK warning. Code that branched on those errors never branches again.
- **A session is no longer one foreground interval.** 7.x splits the concept in two. A *session part* is one contiguous foreground or background interval (what 6.x called a session), and a *user session* groups one or more parts, bounded by a maximum duration (default 12 hours) and an inactivity timeout (default 30 minutes), both remote-configurable. The app code doesn't change for this, but the shape of the data does:
  - Session-part spans and logs carry new attributes: `emb.user_session_id`, `emb.session_part_id` and `session.id`.
  - **`emb.session_part_number` supersedes `emb.session_number`.** (`emb.user_session_part_index`, the part's position within its user session, is a different attribute.) Any XCOR RUM dashboard, saved query, alert or downstream OTel pipeline keyed on `emb.session_number` stops matching after the upgrade, with no build error to warn about it. Call this out even when the app itself never references the attribute.
- **`.userSession` metadata covers more than 6.x `.session` did.** The lifespan rename changes behavior: metadata now attaches to every part of the user session and survives process death for as long as that user session lives, instead of ending with one foreground interval. A value set once per foreground (a screen name, a funnel step) now spans more data than it used to.
- **Session control changed.** `startNewSession()`, `endCurrentSession()` and `resetUploadCache()` are gone. `EmbraceIO.shared.endUserSession()` ends the current user session and immediately starts a new one, and is rate-limited to once per 5 seconds (extra calls are ignored silently). Code that ended a session and expected no active session afterward no longer behaves that way.
- **The SDK's OTel providers are no longer registered globally.** 6.x installed them on `OpenTelemetry.instance`, so third-party OTel instrumentation reached XCOR RUM without the app doing anything. 7.x does this only when the app passes `OTelOptions(registersGlobalProviders: true)`. If the project has OTel instrumentation that never references an SDK API, its telemetry silently stops reaching XCOR RUM after the upgrade unless the app sets the flag.
- **Sanitization is visible.** `addEvent`, `addLink` and `addSessionEvent` return the stored, sanitized object (or `nil` if it was dropped at a limit), so names and attributes may differ from the inputs.

## Hard rules

- **Never reproduce secrets.** Before you quote a file or build output, replace every credential with `<redacted>`: any `*_TOKEN`, `*_KEY`, `*_SECRET` or `*PASSWORD*` value, signing and provisioning settings, repository credentials and `Authorization` headers. Quote only the lines that support the change, never a whole file. Don't read `.env` files, keystores or provisioning profiles.
- **Run only the commands this procedure names:** `git status`, `xcodebuild`, `swift build`, `swift test` and `pod install`. Say which command you're about to run before you run it. Don't run other scripts from the repo, other package-manager commands or network commands. When you need anything else, give the command to the user to run and ask for the output.
- **Edit only what the migration needs:** call sites from the inventory, imports, the SDK dependency, the dead crash products and, after the user confirms, deployment targets. Never delete a file.
- **The user sends any escalation.** Show the user what to send and where. Don't post it yourself.
- **Call the product XCOR RUM** in your answers, even when the user says Embrace. Code, package and file names stay as they are.

## Escalation

Stop and draft an escalation package when:

- The app calls the SDK from **Objective-C** (7.x has no Objective-C surface).
- The app implements a **custom `CrashReporter`** (the protocol is no longer public).
- The app sets a non-nil **`appGroupId`** in `Embrace.Options` (shared storage with app extensions has no 7.x equivalent).
- A call site matches nothing in `API_MAPPING.md`.

The package has three parts:

- **What I checked:** the SDK version, integration method and files inspected.
- **What I found:** the call sites involved, with file paths and line numbers.
- **Why I'm escalating:** which condition above holds.

Tell the user to send it to their XCOR RUM tech-support Slack channel if they have one, otherwise to the [XCOR RUM community Slack](https://community.embrace.io) or [sg-observability-sales-engineering@paloaltonetworks.com](mailto:sg-observability-sales-engineering@paloaltonetworks.com).

## What this skill does NOT do

- Cover the Android, React Native, Flutter or Unity SDKs.
- Cover the 5.x to 6.x migration.
- Upgrade unrelated dependencies or fix pre-existing build errors. Note them and continue if possible, otherwise stop and report them.
- Diagnose SDK integration issues that aren't part of the 7.x upgrade. Send those to `/cortex-xcor-rum:doctor-ios`.
