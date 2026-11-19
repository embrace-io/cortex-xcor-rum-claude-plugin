# Tech-Support Patterns for Embrace MCP Skill

Source: one year of internal support-channel conversations (2025-04-23 → 2026-04-23), keyword-driven analysis across dSYM, symbolication, URLSession, SPM, SwiftUI, session, crash, React Native, Flutter, Unity, metadata, OpenTelemetry, WebView, hang, ANR, Expo, privacy manifest, app size, upgrade, and "not showing."

Framing for the skill: the Embrace MCP data tools (crashes, logs, spans, network, sessions) already answer "what does the dashboard show?". The *volume* in tech-support is not dashboard questions — it's **customer codebase / integration / build-pipeline** questions the MCP cannot answer from server data alone. The skill's job is to read the customer's repo and catch these before escalation.

---

## Ranked patterns (by thread volume)

### 1. dSYM / symbol upload / symbolication (highest volume, cross-framework)

Recurring sub-patterns:

- **UUID already has a dSYM mapped to it, but from the wrong build.** Server matches on UUID, not app version. Multiple app_version strings for the same UUID → indicates the customer's build pipeline is running dSYM upload twice with different metadata, or a 4-part version (e.g. `5.25.0.x`) that Embrace normalizes to 3 parts. Fix: reupload the correct dSYM against that UUID; it overwrites.
- **dsym-store.emb-api.com unreachable** from the build box (corporate proxy/firewall, or wrong region — there is only one US dsym-store, even for EU apps). Give them a small probe against `/status`.
- **Flutter / RN `run.sh` build phase script moved or missing** between SDK versions (e.g. Flutter 4.2.0 → 4.3.0; RN scripts path). Breaks customer builds.
- **React Native: empty `bundle_id` in upload logs** → upload reports success but symbolication is missing because the uploader short-circuits on a non-zero bundle length check in `tool/ios-upload/main.go:242`.
- **React Native: source map not generated** for newer RN versions because `SOURCEMAP_FILE` env var isn't picked up during the bundle phase. Fix: add `export SOURCEMAP_FILE="$CONFIGURATION_BUILD_DIR/embrace-assets/main.jsbundle.map"` in `ios/.xcode.env.local`.
- **Error-log symbolication failing while crash symbolication works** on the same app (has dSYMs). Suspected dashboard render issue rather than missing symbols.
- **API-token type confusion** (Symbol Uploads vs Pull API vs Custom Metrics vs Spans). Customers can't self-create symbol upload tokens.

> Android symbolication patterns (DexGuard/ProGuard, NDK/Gradle uploads) are out of scope — covered by the separate Android troubleshooting skill.

**What the MCP skill can do in a customer's repo:**
- Parse `Package.swift` / `Podfile` to confirm SDK version and align with dSYM-script location for that version.
- Grep build-phase scripts for hardcoded paths that newer SDK versions relocated.
- Detect Flutter/RN `run.sh` reference, confirm file exists post-install.
- For RN: parse the RN upload logs (they paste them constantly) for `bundle_id=<empty>` → emit a concrete "your RN bundle id didn't resolve; check X" diagnostic.
- For Xcode project: confirm `.xcode.env.local` contains `SOURCEMAP_FILE` when RN ≥ some version.
- Detect 4-part `CFBundleShortVersionString` and warn it will collapse to 3-part in the dashboard's version display (dSYM lookup is UUID-based, so symbolication itself is unaffected — but the version label customers see can be confusing).
- Offer a `nslookup dsym-store.emb-api.com` + `/status` probe instruction before customer goes to humans.

---

### 2. Network capture (URLSession proxy) — second-highest volume, iOS

Recurring sub-patterns:

- **Swift-only `URLSession.data(for:delegate:)` async API not swizzled.** Customers migrate to async/await and stop receiving network spans. Current answer: manual instrumentation around their centralized abstraction.
- **Apollo / GraphQL SDK created before Embrace starts.** Embrace proxy can't intercept a URLSession that already exists. Rule: Embrace.setup must precede any Alamofire SessionManager / Apollo client / custom URLSession.
- **Apollo cache policy causing requests to never fire** — we can't capture what isn't fired.
- **GraphQL path customization** using `URLSessionRequestsDataSource` + `X-APOLLO-OPERATION-NAME` header → override `modifiedRequest` to append header value as path component. Docs mix 5.x (x-emb-path) with 6.x DataSource pattern.
- **`use_legacy_urlsession_proxy` remote flag** — flipping it around breaks downloads (mp3/m3u8/streaming).
- **watchOS crash in `SessionTaskResumeSwizzler`** when setting task delegate on a `URLSession(configuration: .background: id)` request.
- **WebView network calls not captured** — customers repeatedly ask. Answer: use Web SDK inside the WebView, or use a clickstream job as a backfill.
- **`WEBVIEW_ENABLE` plist key in 6.x** — the old plist-based config is largely ignored in 6.x; requires `WebViewCaptureService` during `Embrace.Options` initialization. Seen as a regression after migration where customers still relied on plist and lost network capture.

**What the MCP skill can do in a customer's repo:**
- Parse Swift sources for `URLSession.shared.data(for:` / `data(for:delegate:)` and emit: "this async API isn't swizzled on your SDK version; here is the manual-instrumentation snippet."
- Find where third-party networking libs (`Apollo`, `Alamofire`, `URLSession(configuration:)`) are instantiated. Check against the `Embrace.setup(...)` call site. If Embrace.setup is in a deferred code path or a lazy singleton, emit init-ordering warning.
- Detect background-URLSession + delegate-set patterns → warn about watchOS crash until fixed upstream.
- Detect `Embrace-Info.plist` with `WEBVIEW_ENABLE` key while using 6.x → recommend deleting the plist and moving to `WebViewCaptureService` via Options.
- Scaffold the `URLSessionRequestsDataSource` template for GraphQL customers by reading the header name they're already setting.

---

### 3. SPM / XCFramework / linking (iOS, enterprise customers)

- **Recurring ask: "give us a pre-built XCFramework, we don't want SPM rebuilding from source."** Answer: not supported since 6.x moved to source-based SPM; an experimental multi-xcframework approach exists on a feature branch.
- **watchOS XCFramework not available** — only SPM or CocoaPods for watchOS, tvOS, and macOS targets.
- **Unity-as-iOS-library: `EmbraceUnityiOS` gets linked twice** (once in app binary, once in UnityFramework) → runtime crashes.
- **Static + dynamic linking across targets** → Swift type system sees two `SessionRecord` (or other) types → "NSArray element failed to match Swift Array Element" crash during migration. Customer-specific architecture, not an SDK bug.
- **SwiftSyntax version conflict** — their app requires 602+, Embrace requires 509+; major versions incompatible. Requested support for a broader range.
- **Datadog OTel fork collided with Embrace OTel on older DD SDK versions** — current upstream `DataDog/dd-sdk-ios` now depends on the official `opentelemetry-swift-core`, the same package Embrace uses, so the collision is resolved on modern DD versions. Embrace still maintains a patched fork (`https://github.com/embrace-io/dd-sdk-ios`) as a fallback for customers pinned to older DD.
- **`-ObjC` linker flag** is required (Package.swift:20-27 comment is canonical).
- **Xcode 26 build issues on 6.16.x** — OpenTelemetry package errors; freeze after splash with CoreData errors in console. CocoaPods empty-app reproduces cleanly, so it's a dep-interaction with customer setup.

**What the MCP skill can do in a customer's repo:**
- Parse `Package.swift` / `Package.resolved` and surface conflicting version ranges (SwiftSyntax, OpenTelemetry, Datadog, GRDB, KSCrash).
- Detect both static and dynamic linking of Embrace in the same project's targets and warn with the canonical explanation.
- Detect Unity-as-library pattern (`UnityFramework` target + `EmbraceUnityiOS` SPM dep in host app) and warn about duplicate linkage.
- Detect missing `-ObjC` in `OTHER_LDFLAGS` for static linking.
- Produce a size estimate using a linker-map analysis — documented contribution is ~1.44 MB compressed / ~3.2 MB uncompressed.

---

### 4. SwiftUI instrumentation — recurring misunderstanding

- **Customers assume SwiftUI view tracking is automatic.** It isn't — they must apply `.embraceTrace` / macro to the views they care about.
- **`LazyVStack` scrolling keeps the auto-instrumented "ui-load" span open** as long as network activity fires on scroll → minutes-long "load" times reported. Recommendation: disable auto-instrumentation for that screen and start/stop the span manually on first-batch-appear.
- **`UIHostingController` wrapping SwiftUI views floods events** when it's a cell in a table view. Remote-flip the server-side config `swift_ui_view_instrumentation_enabled: false` and `ui_load_instrumentation_enabled_v2: false` as a fix-in-place.
- **Duplicate breadcrumbs from state-driven re-renders** (a single screen firing the same breadcrumb 7+ times).

**What the skill can do:**
- Grep SwiftUI sources for views that wrap lists/scroll content without `.embraceTrace` / macro and emit "this view will generate noisy auto-traces; consider manual instrumentation."
- Detect `UIHostingController` inside `UITableViewCell` / `UICollectionViewCell` → emit warning about event flood.

---

### 5. Session correctness / background vs foreground

- **Background session (push / prewarm / BGTaskScheduler wake) tagged as foreground** — span never ends because the normal mechanism doesn't trigger. Currently mitigated by dropping startup spans that don't make sense.
- **Cached-sessions stuck in upload queue** on 6.16.0 → fix in 6.16.1 separating retry queue. Old cached payloads returned 200 but didn't appear in dashboard (backend dropped as too-old).
- **Push wakes app → phantom foreground session** where no rendering happens and first-frame span never closes.

**What the skill can do:** limited — this is mostly SDK-side behavior. Can detect push/BGTaskScheduler usage in the app and warn the customer what will happen in current SDK versions.

---

### 6. Custom spans, OTel resources, manual vs automatic instrumentation

- **Customer adds manual network spans on top of automatic instrumentation** → duplicates, parent-child not honored in waterfall view. Turning off automatic fixes it but loses other data.
- **Custom OTel `resource` via `EmbraceIO.OTelOptions.resource` silently dropped on older 6.x** — historical issue where `EmbraceIO.setup(options:)` did not thread the resource through. Resolved in current SDK: `EmbraceIO.setup` now calls `Embrace.setup(options:, otelResources: options.otel?.resource)`. Customers on older 6.x should upgrade; deprecated `addResource(key:value:lifespan:)` remains as a stopgap.
- **`emb.type` span-type exposure** — customers set it and spans stop showing correctly on performance traces. Planned to remove from public API in 7.x.
- **RN `span.end()` with no params → status OK**, no way to end-as-failed from RN. Workaround: `span.end(errorCode: .failure)` if exposed; currently not, needs native-side change.

**What the skill can do:**
- Read customer Swift for `buildSpan(...).startSpan()` on URLs already captured by default; warn about duplication.
- Read for `EmbraceIO.OTelOptions(resource:)` usage; if the customer reports the resource isn't applied, check installed SDK version and recommend upgrading off any older 6.x where this was historically dropped.

---

### 7. `Embrace.Options` ergonomics

- **Customizing only `URLSessionCaptureService.Options`** forces supplying full crash-reporter/backtracer/symbolicator stack because default convenience init disappears. `EmbraceCrashReporter` isn't public-visible under `CrashReporter` protocol. Handled-NSException pass-through missing. Backtraces expect parsed strings instead of raw `Thread.callStackTrace` pointers.

**What the skill can do:** detect partial-option construction patterns and propose the right overload / scaffold the boilerplate.

---

### 8. React Native integration (consistent, distinct from symbolication)

- **Dual init (native + JS) is required** even though the SDK is a singleton — JS init installs ErrorUtils handler, unhandled-promise tracking, and the JS-bundle-path hash. Canonical response exists.
- **`setJavaScriptBundlePath` API for OTA / Expo** — swallowed errors, ambiguous path format (with/without `file://` prefix, URL-encoded spaces). Needs better docs and error surfacing.
- **Cross-layer span strategy** using `recordCompletedSpan` — widely used internally as canonical fix but not yet in public docs.

**What the skill can do:** detect customer `App.tsx` for missing `initialize()` / `useEmbrace()` hook when native init is present. Detect Expo + OTA pattern and scaffold `setJavaScriptBundlePath` with correct format.

---

### 9. Push notifications

- **FCM + Embrace `PushNotificationCaptureService(captureData: true)` both swizzle `UNUserNotificationCenterDelegate`** → delegate chain loop (excessive logging) or crash depending on order. Recommended fix: disable Embrace automatic push capture, use manual `Embrace.instance.logPushNotification()`.
- **PII flags capture title/body on SDK, but backend `Loader` only extracts id/category/from/type/priority/badge** — dashboard silently drops the rest. Docs imply they're visible. Pending product decision.

**What the skill can do:** detect FCM + PushNotificationCaptureService co-install and emit the canonical warning.

---

### 10. Hang detection

- Hangs were being raised for RN/Flutter/Unity iOS apps and customers complained they were false positives. Global mitigation: return 0 for `hang_per_session` in app-service for those frameworks. Dashboard-side rendering also suppressed.
- **New `HangWatchdog` crash on 6.15.0** — numeric conversion in `EmbraceClock.Instant.millisecondsValue` doesn't guard against negative delta before `UInt64` cast. **This is an actual SDK bug worth confirming and fixing.**

---

### 11. App size / binary impact

- Customer claims Embrace adds 8-9 MB; linker-map analysis shows ~1.44 MB compressed / ~3.2 MB uncompressed. Static vs dynamic linking matters; release vs debug matters; dSYMs are often wrongly included in the customer's measurement.

**What the skill can do:** run a `LD_GENERATE_MAP_FILE=YES` mini-workflow in the customer's Xcode project and produce a size-attribution table per library.

---

### 12. Crash attribution and customer misreads

- **Customers read Embrace symbols on bystander threads as "crashing frames."** Canonical framing: thread 0 empty ≠ Embrace crashed; the empty frames mean the crashing thread's stack wasn't captured, and the Embrace frames visible on other threads are bystanders. Map threads to roles before blaming.
- **Stray app versions crashing with no symbols** (zero symbolicated, thousands not) while all other versions symbolicate fine. Points at a specific version/build's symbol pipeline failing on the customer side.

---

## Coverage map: MCP data tools vs. skill gaps

| Customer question class | Already answerable via MCP data tools | Needs codebase/build inspection (the skill) |
|---|---|---|
| "Why is crash group X rising?" | Yes — crash/session/version queries | No |
| "Why are my network calls missing?" | Partially (domain/endpoint counts) | **Yes** — URLSession init ordering, async API usage, Apollo/Alamofire ordering |
| "Why are stack frames not symbolicated?" | Partially (upload records) | **Yes** — build-phase scripts, 4-part versions, Unity/RN bundle id, RN source-map env |
| "Which SDK version should I be on?" | Partially (sdk_version in sessions) | **Yes** — Package.swift/Podfile comparison to changelog gates |
| "Why does my build fail after upgrade?" | No | **Yes** — Xcode/SwiftSyntax/OTel/Cocoapods dependency graph |
| "Why am I seeing duplicate/noisy SwiftUI events?" | Partially (event counts per view) | **Yes** — grep for `UIHostingController`, LazyVStack patterns |
| "Why does customizing captureServices require everything else?" | No | **Yes** — Options-construction boilerplate lint |
| "Why is my session tagged foreground when it shouldn't be?" | No (SDK-side) | Partial — can flag push/BGTask usage |
| "Push notifications crash my app" | Partially (crash stack) | **Yes** — FCM + Embrace co-presence detection |
| "How much does the SDK add to app size?" | No | **Yes** — linker-map + per-library attribution |

---

## Recommended skill capabilities (prioritized)

1. **`embrace-doctor` — a single repo inspector** that runs:
   - Package/Podfile parse → SDK version, linking type, conflicting peer deps (SwiftSyntax, OTel, Datadog, KSCrash).
   - Build-phase script audit → dSYM upload, RN `run.sh`, Flutter `run.sh`, `.xcode.env.local`.
   - Swift source scan → URLSession async APIs, Apollo/Alamofire init ordering, `Embrace.setup` placement, `EmbraceIO.OTelOptions(resource:)` usage, WEBVIEW_ENABLE plist.
   - Xcode project audit → `-ObjC`, mixed static/dynamic, targets that duplicate-link Embrace.
   - Output: a ranked list of likely issues with the same phrasing tech-support uses today.

2. **`embrace-network-trace-ordering`** — focused diagnostic for "my network calls aren't captured" (the single highest-volume question). Confirms SDK starts before any session-creating code path.

3. **`embrace-dsym-preflight`** — replicates what tech-support manually does: verifies upload-token presence, the right build-phase script exists for the installed SDK version, dsym-store reachability, and bundle-id isn't empty on RN.

4. **`embrace-swiftui-lint`** — flags LazyVStack / UIHostingController cell patterns; suggests manual instrumentation points with `.embraceTrace`.

5. **Canned-answer retrieval** — index the canonical responses used repeatedly by the support team (many already quoted verbatim in threads) so the skill can return an exact tech-support-voice answer for the top ~25 questions.

## Routing rules

- If inspection reveals an SDK bug (HangWatchdog UInt64 cast, RN `end()` can't fail, RN bundle_id empty): still escalate to humans — produce a pre-filled issue body.
- If it's a known dashboard/UX quirk (filter-first-party-domain lag, timeline crash on bad timestamps): note and route.
- If it's an anti-pattern in customer code: answer inline, link the doc, stop.
