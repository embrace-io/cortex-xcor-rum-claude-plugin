---
name: embrace-apple-sdk-6to7-migration
description: Use this when you want to upgrade your app from Embrace Apple (iOS) SDK 6.x to 7.0, or when your build breaks after bumping to 7.0 — e.g. "cannot find 'Embrace' in scope," "value of type 'EmbraceIO' has no member 'buildSpan'," "type 'EmbraceIO' has no member 'setup'," "no such module 'EmbraceCrash'," "extra trailing closure / try expression errors after Embrace update." Inventories every 6.x call site in your codebase, applies the verified 6.x → 7.0 API mappings, flags removals that have no replacement, and verifies the project builds.
---

# Embrace Apple SDK 6.x → 7.0 Migration

You are migrating an app from Embrace Apple SDK 6.x to 7.0. The 7.0 release replaces the `Embrace.client` entry point with `EmbraceIO.shared`, collapses `setup` + `start` into a single `EmbraceIO.start(options:)`, removes OpenTelemetry SDK types from the public API in favor of Embrace-owned types, drops `throws` from the public API, removes the Objective-C public surface, and redefines what a session is (see Behavioral changes). Most changes are mechanical renames; a handful are removals that need a decision from the user.

## Ground rules

- **`API_MAPPING.md` (in this folder) is the single source of truth.** Every mapping in it was verified against the Embrace Apple SDK 7.0 public API. Do not invent APIs that are not listed there. If a call site doesn't match anything in the mapping file, say so and escalate — do not guess a replacement.
- **Never silently delete functionality.** When a call site uses an API listed under "Removed with no replacement," show the user the call site, explain the removal, and let them choose (drop it, or apply the suggested workaround). Exception: calls that are now no-ops by design (e.g. removing a bare `try`/`try?`/`try!`) — apply those directly.
- **Migrate, don't refactor.** Keep the app's existing structure, naming, and style. The diff should be the minimum needed to compile and preserve behavior on 7.0.
- **Verify with a build, not by eyeballing.** A migration that hasn't compiled isn't done.

## Procedure

### 1. Preflight

1. Determine the current SDK version and integration method:
   - SPM: `Package.swift`, `Package.resolved`, or the Xcode project's `Package.resolved` (search for `embrace-apple-sdk`).
   - CocoaPods: `Podfile` / `Podfile.lock` (pod `EmbraceIO`).
2. **If the app is on 5.x or earlier, stop.** This skill only covers 6.x → 7.0. The 5.x → 6.x migration is a separate, larger effort — do that upgrade first.
3. **Check for Objective-C usage of Embrace.** Grep `.m`/`.h` files for `Embrace`. The 7.0 public API has no `@objc` surface — Objective-C call sites cannot be migrated. If found, stop and escalate to Embrace support before touching anything (see Escalation).
4. **Check for a custom `CrashReporter` conformance** (`: CrashReporter` outside the SDK). The protocol is no longer public in 7.0. If found, flag it now — the app must either drop the custom reporter or contact Embrace.

### 2. Inventory 6.x call sites

Run these greps over the app source (exclude `Pods/`, checkouts, and build dirs) and collect every hit into a checklist:

```
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

Then scan the **project files**, not just source — some dependencies live only there:

```
# Xcode project: dead crash products declared on targets with no matching import
grep -nE "EmbraceCrash|EmbraceCrashlyticsSupport" **/*.pbxproj
# CocoaPods
grep -nE "EmbraceCrash|EmbraceCrashlyticsSupport" Podfile Podfile.lock
```

A hit here with **no** corresponding `import EmbraceCrash` in source still breaks the build — the product reference itself must be removed (step 3). The source-only greps above will not catch this.

Note: 6.20+ already ships an `EmbraceIO.shared` facade, so a codebase may mix `Embrace.client?.…` and `EmbraceIO.shared.…` styles. Both are covered in the mapping file — inventory both.

### 3. Update the dependency

- SPM: point `embrace-apple-sdk` at the 7.0 release (Up to Next Major, from `7.0.0`). If SPM reports that no such version exists, 7.0 has not shipped a release tag yet — confirm the intended version with Embrace support rather than guessing.
- **Remove the dead crash products from the project, not just the imports.** `EmbraceCrash` and `EmbraceCrashlyticsSupport` library products no longer exist (both reporters are bundled into `EmbraceIO`). A target can declare them as package-product dependencies in `project.pbxproj` even when no source file imports them — those references must be deleted from every target (main app, watch, extensions) or the build fails with `Missing package product 'EmbraceCrash'`. See step 2 for how to find them.
- CocoaPods: bump pod `EmbraceIO` to the 7.0 release.
- 7.x raises the minimum deployment targets to iOS 15, tvOS 15 and watchOS 9 (macOS stays at 13). If any target (app, watch app, extensions) is below these, tell the user and confirm before raising it; do not lower or otherwise change targets that already meet them.

### 4. Apply mappings

Work through the checklist from step 2 file by file, using `API_MAPPING.md`. Order that minimizes intermediate breakage:

1. **Imports** — drop `EmbraceCrash`, `EmbraceCrashlyticsSupport`; drop `OpenTelemetryApi`/`OpenTelemetrySdk` unless the file configures `OTelOptions` exporters. `import EmbraceIO` re-exports everything else you need.
2. **Startup & Options** — entry point, `EmbraceIO.start(options:)`, crash reporter enum, `OTelOptions` (including `registersGlobalProviders`), capture services builder.
3. **Mechanical renames** — types table in the mapping file.
4. **Call-site rewrites** — spans, logs, session events, breadcrumbs, metadata, startup, push. Two of these bite quietly: every `lifespan: .session` becomes `lifespan: .userSession` (mapping §7.0), and `span.addEvent` has no default for `attributes:` (mapping §5.3).
5. **`try` removal** — the public API no longer throws except `EmbraceIO.start(options:)` and `stop()`. Remove now-dead `try`/`try?`/`try!`, `do/catch` blocks that only wrapped Embrace calls, and error-handling branches that can no longer fire. If a `catch` block did something meaningful (analytics, fallback), point it out: on 7.0 the failure is a silent no-op plus an SDK warning log, so that handling has no trigger anymore.
6. **Removals** — surface each one to the user with the suggested workaround from the mapping file.

### 5. Verify

1. Build the project (`xcodebuild` for the app's scheme, or `swift build` for a package). Iterate until Embrace-related errors are gone.
2. If the build fails with `Macro "EmbraceMacroPlugin" … must be enabled before it can be used`, that is Xcode's Swift-macro trust prompt for the SDK's macro plugin, **not** a migration error: click "Trust & Enable" in the Xcode GUI, or pass `-skipMacroValidation` to `xcodebuild`. Mention it before the user hits it so they don't mistake it for a broken migration.
3. Re-run the step-2 greps. Remaining hits must be either correct 7.0 usage or items the user explicitly chose to keep or drop.
4. If the project has tests touching Embrace, run them.
5. Report: files changed, mappings applied, removals decided on, and anything escalated.

## Behavioral changes to call out (even if the build is clean)

These compile fine but behave differently — include them in the final report:

- **There is no separate `setup` step.** `EmbraceIO.start(options:)` configures and starts the SDK in one call, on the main thread. If the app deliberately delayed `start()` (e.g. consent gating) by calling `setup` early and `start()` later, that split is gone — call `EmbraceIO.start(options:)` at the moment `start()` used to run.
- **Failures are silent.** APIs that used to throw now drop the operation and log an SDK warning. Code that branched on those errors will never branch again.
- **A session is no longer one foreground interval.** 7.0 splits the concept in two: a *session part* is one contiguous foreground or background interval (what 6.x called a session), and a *user session* groups one or more parts, bounded by a maximum duration (default 12 hours) and an inactivity timeout (default 30 minutes), both remote-configurable. Nothing in the app code has to change for this, but the shape of the data does:
  - New attributes on session-part spans and logs: `emb.user_session_id`, `emb.session_part_id`, `session.id`.
  - **`emb.session_number` is superseded by `emb.session_part_number`.** (`emb.user_session_part_index`, the part's position within its user session, is a different attribute.) Any dashboard, saved query, alert, or downstream OTel pipeline keyed on `emb.session_number` stops matching after the upgrade, with no build error to warn you. Call this out even when the app itself never references the attribute.
- **`.userSession` metadata is broader than 6.x `.session` was.** The lifespan rename is not cosmetic — metadata now attaches to every part of the user session and survives process death for as long as that user session lives, instead of ending with one foreground interval. Anything set once per foreground (a screen name, a funnel step) now spans more data than it used to.
- **Session control changed.** `startNewSession()` / `endCurrentSession()` / `resetUploadCache()` are gone. `EmbraceIO.shared.endUserSession()` ends the current user session and immediately starts a new one, and is rate-limited to once per 5 seconds (extra calls are ignored silently). Code that ended a session and expected *no* active session afterward no longer behaves that way.
- **The Embrace OTel providers are no longer registered globally.** 6.x installed them on `OpenTelemetry.instance`, so third-party OTel instrumentation emitted through Embrace without the app doing anything. 7.0 only does this when `OTelOptions(registersGlobalProviders: true)` is passed. If the project has OTel instrumentation that never references an Embrace API, its telemetry silently stops reaching Embrace after the upgrade — set the flag.
- **Sanitization is visible.** `addEvent`/`addLink`/`addSessionEvent` return the *stored, sanitized* object (or `nil` if dropped at a limit) — names and attributes may differ from the inputs.

## Escalation

Stop and produce an escalation summary (what you checked, what you found, why you're escalating) for Embrace support when:

- The app calls Embrace from **Objective-C** (no 7.0 ObjC surface exists).
- The app implements a **custom `CrashReporter`** (protocol no longer public).
- The app sets a non-nil **`appGroupId`** in `Embrace.Options` (shared storage with app extensions has no 7.0 equivalent).
- A call site matches nothing in `API_MAPPING.md`.

## What this skill does NOT do

- Cover Android, React Native, Flutter, or Unity Embrace SDKs.
- Cover 5.x → 6.x migration.
- Upgrade unrelated dependencies or fix pre-existing build errors (note them and continue if possible; otherwise stop and report them).

## Installation

Copy this folder to `~/.claude/skills/embrace-apple-sdk-6to7-migration/`:

```
~/.claude/skills/embrace-apple-sdk-6to7-migration/
├── SKILL.md         (this file)
└── API_MAPPING.md   (verified 6.x → 7.0 API reference — required)
```

Then, from the app repo: "Migrate this app from Embrace 6 to 7."
