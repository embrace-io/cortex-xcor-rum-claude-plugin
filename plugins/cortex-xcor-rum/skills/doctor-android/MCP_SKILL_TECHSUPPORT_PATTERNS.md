# Tech-Support Patterns for Embrace MCP Skill (Android)

Source: a 12-month sweep of the internal `#tech-support` and `#guild-android` channels for recurring Android and Android+React-Native issues — keyword-driven across crash parity, NDK signal handlers, mapping/symbol upload, Gradle/AGP, `embrace-config.json`, `androidx.startup`, sessions, OkHttp, logging, `Embrace.disable()`, and FCM/push.

Framing for the skill: the Embrace MCP data tools (crashes, logs, spans, sessions, versions) already answer "what does the dashboard show?". The *volume* in Android tech-support is not dashboard questions — it's **customer codebase / integration / build-pipeline** questions the MCP cannot answer from server data alone: is the Gradle plugin applied to the right module, is the upload failing on the CI runner, is `androidx.startup` stripped by a manifest merge, is there a custom `Application` subclass for the native RN start call. The skill's job is to read the customer's repo and catch these before escalation.

This is the Android counterpart to the iOS `embrace-doctor-ios` skill. The two skills share the same schema and voice; the catalogs are disjoint except for genuinely cross-platform backend gaps (the FCM title/body drop), which are duplicated so each skill stands alone.

---

## Ranked patterns (by thread volume)

### 1. Crashes — parity, NDK signal handlers, and instrumentation crashes (highest volume)

Recurring sub-patterns:

- **Embrace crash counts differ from Crashlytics / Firebase / Sentry.** Almost always a false alarm rooted in different grouping algorithms, different crash-rate denominators, restart-to-send timing, or — for NDK — signal-handler conflict where whichever reporter installs last wins. Compare long-run totals, not group-vs-group.
- **NDK crashes disappear after 6.x → 7.x upgrade.** From 7.x, Embrace no longer reinstalls itself over another reporter's native signal handlers by default. If Crashlytics/Sentry/Bugsnag NDK init runs after Embrace, they take the handlers. Fix: `sdk_config.sig_handler_detection = true` in `embrace-config.json`. JVM crashes are unaffected (separate uncaught-exception chain).
- **`NoSuchMethodError` in `StreamHandlerFactoryInstaller$WrappingFactory.openConnection`.** Our `HttpURLConnection` instrumentation wraps `URL.openConnection` via a custom `URLStreamHandlerFactory`; certain Firebase Storage/Auth reflective paths hit a case the wrapper doesn't handle. **Open SDK investigation — no in-product fix yet.** Interim: disable bytecode HUC capture for the affected build.

**What the skill can do in a customer's repo:** grep for co-installed reporters (`com.google.firebase.crashlytics`, `io.sentry`, `com.bugsnag`) and their NDK variants; read `embrace-config.json` for `sig_handler_detection`; grep for `firebase-storage`/`firebase-auth`; inspect `Application.onCreate` init ordering of all reporters. Confirm signatures via `list_crashes` / `get_crash_stack_samples`.

---

### 2. Symbolication — mapping & NDK symbol upload at build time

- **`jvmMappingUploadTask FAILED` / `[EmbraceGradlePlugin] [OkHttpNetworkService] Exception`.** One error message, several distinct causes: upload disabled by a forgotten `gradle.properties` flag; CI egress blocked (firewall, missing LetsEncrypt intermediate cert, proxy); R8 mapping >100 MB timing out; the 7.3.0+ default that *fails the build* on upload failure (previously a warning — surfaces as new CI breakage on upgrade); and task-ordering issues where a CI publish plugin (`gradle-play-publisher`) runs release tasks without depending on Embrace's compression/upload task.

**What the skill can do:** grep `gradle.properties` for `embrace.disableMappingFileUpload` / `embrace.disableNdkUploads`; confirm the plugin is applied to the right module; flag `gradle-play-publisher`; check compressed mapping size if the build output is present; use `get_app_details` (mapping registered?) and `list_crashes` (crashes arriving un-deobfuscated ⇒ SDK reports but symbols never uploaded).

---

### 3. Sessions — none, or background-only

- **No sessions / only background sessions.** Ranked causes: `androidx.startup.InitializationProvider` disabled in the manifest (often an unintended `tools:node="remove"` meant only for the WorkManager initializer) so the SDK never gets lifecycle callbacks; `Embrace.getInstance().start(this)` called late or off the main thread; network egress blocked at the customer site (sessions cache on-device, upload on next reachable launch); or the dashboard's "Finish Integration" label persisting despite real ingestion (a UI signal, not an SDK problem).

**What the skill can do:** grep the **merged** manifest for `androidx.startup.InitializationProvider` and any `tools:node` directives; locate the `start()` call and confirm it's first in `onCreate()` on the main thread; use `get_session_distribution` to quantify foreground vs background.

---

### 4. Linking / build — AGP and dependency resolution

- **`embrace-config.json` stripped at compile time after an AGP bump.** AGP 8.x tightened asset/resource merging; on older Embrace plugin versions the config sits where AGP now strips it, so the App ID never resolves at runtime. Fix: upgrade SDK + Gradle plugin together, keep the config in `app/src/main/` (per-flavor under `app/src/<flavor>/`), verify with `unzip -l <apk> | grep embrace`.
- **Unexpected OkHttp version after an Embrace upgrade.** Embrace doesn't add OkHttp 5.x as a first-party dep, but it can arrive transitively (e.g. `opentelemetry-exporter-sender-okhttp`); Gradle resolves to the highest version. Diagnose with `dependencyInsight`; pin with standard Gradle mechanisms if needed (unsupported but usually works).

**What the skill can do:** read AGP/Gradle-plugin/SDK versions from `build.gradle*`; glob every `embrace-config.json` and note which sourceSets own them; grep for explicit `com.squareup.okhttp3:okhttp` declarations.

---

### 5. React Native on Android (distinct from symbolication)

- **iOS reports data, Android doesn't, because there's no custom `Application` class.** The RN integration needs native init on both platforms; on Android that's `Embrace.getInstance().start(this)` in `Application.onCreate()`. Some RN templates ship no custom `Application` subclass, so `android:name` is absent or points at `android.app.Application` and the native start call has nowhere to live.
- **`emb-app-startup-cold` span count far below session count on RN + Android.** Orders-of-magnitude gap (e.g. 2M sessions, ~80 startup spans). **Open investigation** — possibly tied to how the RN host process initializes the SDK relative to the JS bridge. No confirmed root cause or workaround.

**What the skill can do:** confirm RN via `package.json`; grep `AndroidManifest.xml` for `android:name`; glob for a custom `*Application*.{kt,java}`; locate the native `start()` call; quantify with `get_session_distribution` and `list_root_spans`.

---

### 6. Logging

- **Android logs don't include stacktraces automatically.** `logMessage()` records message + severity only. Customers expecting iOS-parity stacktraces need the explicit APIs: `logException(message, severity, throwable, properties)` or `logCustomStacktrace(...)`. High INFO-log volume is usually a separate triage (which logs accumulate), answered via `get_log_distribution`.

---

### 7. API lifecycle

- **`IllegalStateException("SDK not initialized")` after `Embrace.disable()`.** Up to 8.3.0, calling `disable()` then a public API method (`addBreadcrumb`, `setUserIdentifier`) could crash — some methods were wrapped in `runCatching`, `addBreadcrumb` was not. Common trigger: start in `onCreate` → `disable()` pending consent → user hits code that calls a public API. **Fixed in 8.3.1** (PRs #3326 / #3328, commit `af4c34dd0`). Workaround if not upgrading: gate public API calls behind your own consent flag.

---

### 8. Push notifications (cross-platform backend gap)

- **FCM/push title and body never shown in the dashboard.** Both SDKs capture title/body as span-event attributes when the customer opts in (`sdk_config.capture_fcm_pii_data: true` on Android, `PushNotificationCaptureService.Options(captureData: true)` on iOS) and the payload arrives correctly. The backend Loader maps only a fixed field set (id, category, from, type, priority, badge) into the session payload; title/body are dropped there. **Backend gap — no customer-side fix.** This entry is shared with the iOS skill.

---

## Coverage map: MCP data tools vs. skill gaps

| Customer question class | Already answerable via MCP data tools | Needs codebase/build inspection (the skill) |
|---|---|---|
| "Why is crash group X rising?" | Yes — crash/session/version queries | No |
| "Why does Embrace show fewer crashes than Crashlytics?" | Partially (crash/session distribution) | **Yes** — co-installed reporters, NDK signal-handler order, init ordering |
| "Why did NDK crashes stop after upgrading?" | Partially (crash volume by version) | **Yes** — `sig_handler_detection`, other NDK reporter presence |
| "Why does my mapping/symbol upload fail?" | Partially (mapping registered?) | **Yes** — gradle.properties flags, CI egress, mapping size, task ordering |
| "Why do I have no sessions / only background?" | Partially (session distribution) | **Yes** — `androidx.startup` provider, start() timing/thread |
| "Why does my build fail / config go missing after AGP upgrade?" | No | **Yes** — AGP version, config file location, APK packaging |
| "Why did Embrace pull in OkHttp 5.x?" | No | **Yes** — dependency graph resolution |
| "RN: iOS reports but Android doesn't" | Partially (app existence, sessions) | **Yes** — custom Application class + native start call |
| "Why is the startup trace count so low on RN Android?" | Partially (span vs session counts) | Partial — flag start() placement; otherwise SDK-side (open) |
| "Push title/body not showing" | Partially (raw payloads) | **Yes** — opt-in config confirmation; root cause is backend |

---

## Routing rules

- If inspection reveals an SDK bug or open investigation (`StreamHandlerFactory` `NoSuchMethodError`, RN Android startup-trace gap, FCM title/body backend drop): still escalate to humans — produce a pre-filled issue body. Do not attempt an inline "fix."
- If it's a version-gated bug already fixed upstream (`Embrace.disable()` `IllegalStateException` fixed in 8.3.1): give the upgrade target and the interim workaround, no escalation unless they're already on the fixed version and still see it.
- If it's an anti-pattern or misconfiguration in customer code/build (missing `Application` class, stripped `InitializationProvider`, upload flag left on, config in the wrong sourceSet): answer inline, link the doc, stop.
