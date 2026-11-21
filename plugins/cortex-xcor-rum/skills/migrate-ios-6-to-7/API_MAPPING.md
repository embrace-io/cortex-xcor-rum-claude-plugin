# Embrace Apple SDK 6.x → 7.0 API Mapping

6.x signatures are from the latest 6.x release; 7.0 signatures are from the Embrace Apple SDK 7.0 public API. Sections marked **REMOVED — no replacement** require a decision from the app owner; everything else is mechanical.

---

## 1. Entry point

`Embrace` is `package` (internal) in 7.0. `EmbraceIO.shared` is the only public client.

| 6.x | 7.0 |
|---|---|
| `Embrace.client?.<anything>` | `EmbraceIO.shared.<mapped equivalent>` |
| `Embrace.client?.metadata.<x>` | `EmbraceIO.shared.<x>` (flattened — see §7) |
| `Embrace.client?.startupInstrumentation.<x>` | `EmbraceIO.shared.<x>` (flattened — see §9) |
| `Embrace.client?.options` | removed — keep your own reference to the options you built |
| `Embrace.client?.started` | `EmbraceIO.shared.state == .started` |
| `Embrace.client?.currentSessionId()` / 6.x facade `EmbraceIO.shared.currentSessionId` | `EmbraceIO.shared.currentUserSessionId` (property — **renamed**) |
| `Embrace.client?.currentDeviceId()` | `EmbraceIO.shared.deviceId` (property) |
| `Embrace.client?.state` / `isSDKEnabled` / `logLevel` / `Embrace.sdkVersion` | same names on `EmbraceIO.shared` / `EmbraceIO.sdkVersion` (`logLevel` is now `EmbraceLogLevel`) |

Note: 6.20+ already has an `EmbraceIO.shared` facade. Codebases may mix both styles; migrate both. The 6.x facade methods (`buildSpan`, throwing `setProperty`, etc.) map exactly like their `Embrace.client` counterparts below — except `EmbraceIO.setup` / `EmbraceIO.shared.start()`, which are replaced by the single `EmbraceIO.start(options:)` (§2).

## 2. Startup lifecycle

```swift
// 6.x — two-phase
try Embrace.setup(options: options).start()
// or
try Embrace.setup(options: options)
try Embrace.client?.start()
// or (6.20+ facade)
try EmbraceIO.setup(options: options)
try EmbraceIO.shared.start()

// 7.0 — one static call configures and starts the SDK
try EmbraceIO.start(options: options)
```

- There is no `EmbraceIO.setup` and no instance `start()` in 7.0. `EmbraceIO.start(options:)` is `static`, `throws` `EmbraceSetupError`, and must run on the main thread.
- `EmbraceSetupError` keeps its name; the `appGroupId`-related cases are gone (`invalidAppGroupId` removed, `failedStorageCreation` no longer carries an `appGroupId`). A `catch` that matched those cases won't compile.
- `stop()` remains: `try EmbraceIO.shared.stop()` — the SDK cannot be restarted after stop.
- **Session control:** `startNewSession()` and `endCurrentSession()` → `EmbraceIO.shared.endUserSession()` (ends the current user session and immediately starts a new one; rate-limited to once per 5 seconds). The 6.x "end the session and leave none running" behavior of `endCurrentSession()` has no 7.0 equivalent — flag it if the app depended on it.
- `resetUploadCache()` is **REMOVED — no replacement.**
- If the app deliberately separated `setup` from `start` (consent gating), move the whole call to where `start` was. Flag this to the user.

## 3. Options

```swift
// 6.x
let options = Embrace.Options(
    appId: "ABCDE",
    appGroupId: nil,                            // REMOVED in 7.0
    platform: .default,
    endpoints: Embrace.Endpoints(baseURL: b, configBaseURL: c),
    captureServices: .automatic,                // [CaptureService]
    crashReporter: KSCrashReporter(),           // protocol instance
    logLevel: .default,
    export: OpenTelemetryExport(spanExporter: se, logExporter: le)
)

// 7.0
let options = EmbraceIO.Options.withAppId(
    "ABCDE",
    platform: .default,                         // EmbracePlatform
    endpoints: EmbraceEndpoints(baseURL: b, configBaseURL: c),
    captureServices: .default(),                // EmbraceIO.CaptureServicesOptions
    crashReporter: .embrace,                    // enum
    logLevel: .default,                         // EmbraceLogLevel
    otel: EmbraceIO.OTelOptions(
        spanExporters: [se],
        logExporters: [le]
    )
)
```

7.0 factory signatures (verified):

```swift
EmbraceIO.Options.withAppId(
    _ appId: String?,
    platform: EmbracePlatform = .default,
    endpoints: EmbraceEndpoints? = nil,
    captureServices: EmbraceIO.CaptureServicesOptions = .default(),
    crashReporter: EmbraceIO.CrashReporter = .embrace,
    logLevel: EmbraceLogLevel = .default,
    otel: EmbraceIO.OTelOptions? = nil
) -> EmbraceIO.Options

EmbraceIO.Options.withLocalConfiguration(      // replaces appId-less / export-only init
    _ localConfiguration: EmbraceConfigurable = .default,
    platform: EmbracePlatform = .default,
    captureServices: EmbraceIO.CaptureServicesOptions = .default(),
    crashReporter: EmbraceIO.CrashReporter = .embrace,
    logLevel: EmbraceLogLevel = .default,
    otel: EmbraceIO.OTelOptions               // required in this mode
) -> EmbraceIO.Options
```

- **`appGroupId` is REMOVED — no replacement.** If the app set a non-nil value (shared storage with app extensions), escalate.
- 6.x `Embrace.Options(export:)` (appId-less init for pure OTel export) → `withLocalConfiguration(otel:)`.
- The minimal 6.x init `Embrace.Options(appId: "ABCDE", logLevel: .info)` maps to `EmbraceIO.Options.withAppId("ABCDE", logLevel: .info)` — every other `withAppId` parameter has a default, so a two-argument call compiles as-is.

### 3.1 Crash reporter: protocol → enum

| 6.x | 7.0 |
|---|---|
| `crashReporter: KSCrashReporter()` (`import EmbraceCrash`) | `crashReporter: .embrace` |
| `crashReporter: CrashlyticsReporter()` (`import EmbraceCrashlyticsSupport`) | `crashReporter: .crashlytics` |
| `crashReporter: nil` | `crashReporter: .none` |
| custom `CrashReporter` conformance | **REMOVED — escalate** (protocol no longer public) |

The `EmbraceCrash` and `EmbraceCrashlyticsSupport` SPM library products no longer exist — remove the imports and any explicit package-product dependencies. Both reporters ship inside `EmbraceIO`.

### 3.2 OTelOptions

```swift
// 6.x: OpenTelemetryExport / OpenTelemetryProcessor (singular exporters)
export: OpenTelemetryExport(spanExporter: se, logExporter: le)

// 7.0: arrays, one type
otel: EmbraceIO.OTelOptions(
    resource: Resource? = nil,
    spanProcessors: [SpanProcessor] = [],
    spanExporters: [SpanExporter] = [],
    logProcessors: [LogRecordProcessor] = [],
    logExporters: [LogRecordExporter] = [],
    registersGlobalProviders: Bool = false
)
```

`registersGlobalProviders` installs the Embrace tracer and logger providers as the process-wide
OpenTelemetry providers (`OpenTelemetry.instance`). 6.x always did this; 7.0 only does it when asked.
Set it to `true` when the app relies on third-party OTel instrumentation resolving the global
providers. It is honored only on the `start(options:)` call that creates the client, is
last-writer-wins, and is never undone — not even by `stop()`.

This is the one deliberately OTel-coupled boundary: `Resource`, `SpanProcessor`, `SpanExporter`, `LogRecordProcessor`, `LogRecordExporter` are still OTel SDK types — keep `import OpenTelemetrySdk` in the file that builds `OTelOptions`, and nowhere else.

### 3.3 Capture services list

```swift
// 6.x — array via CaptureServiceBuilder or statics
captureServices: CaptureServiceBuilder()
    .add(.urlSession(options: urlOpts))
    .addDefaults()
    .build()
// or: captureServices: .automatic

// 7.0 — CaptureServicesOptions via CaptureServicesOptionsBuilder
captureServices: CaptureServicesOptionsBuilder()
    .addUrlSessionCaptureService(withOptions: urlOpts)
    .addDefaults()
    .build()
// or: captureServices: .default()
```

7.0 builder methods: `addDefaults()`, `addUrlSessionCaptureService(withOptions:)`, `addTapCaptureService(withOptions:)`, `addViewCaptureService(withOptions:)`, `addWebViewCaptureService(withOptions:)`, `addPushNotificationCaptureService(withOptions:)`, `addLowMemoryWarningCaptureService()`, `addLowPowerModeCaptureService()`, `addHangCaptureService()`, `add(_ service: CaptureService)`, `remove(ofType:)`, `remove(embraceType: EmbraceCaptureService)`, `build()`.

### 3.4 URLSessionCaptureService.Options

6.x `final class Options: NSObject` → 7.0 `struct Options` (same parameters, no `@objc`):

```swift
// 7.0
URLSessionCaptureService.Options(
    requestsDataSource: URLSessionRequestsDataSource? = nil,
    ignoredURLs: [String] = [],
    traceparent: Traceparent = Traceparent()      // struct in 7.0, class in 6.x
)

// W3C traceparent domain allowlist — carried over unchanged
URLSessionCaptureService.Options(
    traceparent: .init(onlyAllowDomains: ["api.myapp.com"])
)
```

- `traceparent: Traceparent(onlyAllowDomains:)` **carries over as-is.** Entries are bare hostnames (`"test.com"`), matching that host and its subdomains; malformed entries are dropped with a warning instead of throwing. `nil` = no filter; `[]` = header on no requests.
- The deprecated `injectTracingHeader` parameter/property is **gone** in 7.0. It was already a no-op in later 6.x releases (injection rate is controlled by remote config), so deleting it changes nothing — just remove the argument.

### 3.5 WebViewCaptureService.Options

6.x `final class Options: NSObject` (`@objc(EMBWebViewCaptureServiceOptions)`, with
`init(stripQueryParams:)` and a no-argument `init()` defaulting to `false`) → 7.0 `struct Options`
with defaulted parameters:

```swift
// 7.0
WebViewCaptureService.Options(
    stripQueryParams: Bool = false,
    fragmentHandling: FragmentHandling = .keep
)
```

- `WebViewCaptureService.Options(stripQueryParams: true)` carries over verbatim — the label
  and semantics are unchanged. Only a call site that stored the options as an `NSObject`
  reference, or relied on the `@objc` name, needs work.
- `fragmentHandling` is new and has no 6.x equivalent. `.keep` (the default) reproduces 6.x
  behavior — the URL fragment is captured as-is. `.redact` strips values from `key=value`
  pairs and drops unstructured segments long enough to be a payload, keeping hash routes and
  short anchors. `.remove` drops the fragment entirely. Offer `.redact` or `.remove` to any
  app whose web views carry tokens in the fragment (the OAuth 2.0 implicit grant returns
  access tokens there), but do not change it unprompted — it alters captured data.

## 4. Renamed types (mechanical)

| 6.x | 7.0 | Notes |
|---|---|---|
| `Platform` | `EmbracePlatform` | cases unchanged: `.native`, `.reactNative`, `.unity`, `.flutter`, `.default` |
| `LogLevel` | `EmbraceLogLevel` | cases: `.none/.trace/.debug/.info/.warning/.error/.critical`, `.default` |
| `LogSeverity` | `EmbraceLogSeverity` | cases unchanged: `.trace/.debug/.info/.warn/.error/.fatal/.critical` |
| `LastRunEndState` | `EmbraceLastRunEndState` | cases unchanged: `.unavailable/.crash/.cleanExit` |
| `Embrace.Endpoints` | `EmbraceEndpoints` | `init(baseURL:configBaseURL:)`, `init(appId:)`; `developmentBaseURL` dropped (was already a no-op) |
| `SpanType` | `EmbraceType` | base statics `.performance/.ux/.system`; the SDK also ships derived statics such as `.networkRequest` and `.view` (kept from 6.x). Custom: `EmbraceType(performance: "x")` etc. The base-three list is **not** exhaustive — a 6.x `.networkRequest`/`.view` still resolves. |
| `LogType` | `EmbraceType` | unified with span types; `.message` etc. still available |
| `SpanErrorCode` | `EmbraceSpanErrorCode` | cases unchanged: `.failure/.userAbandon/.unknown` |
| `StackTraceBehavior` | `EmbraceStackTraceBehavior` | cases unchanged: `.notIncluded/.default/.custom(EmbraceStackTrace)/.main` |
| `Span` (OTel) | `EmbraceSpan` (protocol) | see §5 |
| `SpanEvent` / `RecordingSpanEvent` (OTel) | `EmbraceSpanEvent` | now has a public init |
| `[String: AttributeValue]`, `[String: String]` attribute params | `EmbraceAttributes` (`[String: EmbraceAttributeValue]`) | `String`, `Bool`, all `Int`/`UInt` widths, `Float`, `Double` conform — literals keep working |
| `MetadataLifespan` | `MetadataLifespan` | same name, but **`.session` is renamed `.userSession`**; `.process` and `.permanent` are unchanged. See §7.0 |
| `EmbraceSDKState` | `EmbraceSDKState` | unchanged |
| `EmbraceSetupError` | `EmbraceSetupError` | same name; `appGroupId`-related cases removed (§2) |
| `MetadataError` | — | **REMOVED.** Metadata calls no longer throw, so the error type is gone; delete `catch` clauses that referenced it |

New 7.0 types referenced in signatures: `EmbraceSpanStatus` (`.ok/.unset/.error`), `EmbraceSpanContext` (`spanId`, `traceId`), `EmbraceSpanLink` (public init), `EmbraceLogAttachment`, `EmbraceIdentifier`.

**Imports (SPM):** `import EmbraceIO` is sufficient — it does `@_exported import EmbraceCore` and `@_exported import EmbraceSemantics`, so every type in this file (`EmbraceSpan`, `EmbraceType`, `EmbraceSpanErrorCode`, `EmbraceLogSeverity`, the `end(errorCode:endTime:)` extension on `EmbraceSpan`, …) resolves through it. Adding `import EmbraceSemantics` is harmless but redundant; don't bother. The only import you must *remove* is `import OpenTelemetryApi`/`import OpenTelemetrySdk` everywhere except `OTelOptions` construction (§3.2). CocoaPods builds the SDK as a single module; `import EmbraceIO` suffices there too.

## 5. Spans

### 5.1 Creating

```swift
// 6.x — builder pattern
let span = Embrace.client?.buildSpan(
    name: "checkout",
    type: .performance,
    attributes: ["cart": "5 items"]
)
.setStartTime(time: startTime)        // optional builder steps
.startSpan()

// 7.0 — one call, returns a started EmbraceSpan?
let span = EmbraceIO.shared.createSpan(
    name: "checkout",
    type: .performance,
    startTime: startTime,
    attributes: ["cart": "5 items"]
)
```

Full 7.0 signature:

```swift
@discardableResult
func createSpan(
    name: String,
    parentSpan: EmbraceSpan? = nil,
    type: EmbraceType = .performance,
    status: EmbraceSpanStatus = .unset,
    startTime: Date = Date(),
    endTime: Date? = nil,
    events: [EmbraceSpanEvent] = [],
    links: [EmbraceSpanLink] = [],
    attributes: EmbraceAttributes = [:],
    autoTerminationCode: EmbraceSpanErrorCode? = nil
) -> EmbraceSpan?
```

Builder-step mapping: `.setParent(span)` → `parentSpan:`; `.setStartTime(time:)` → `startTime:`; `.addLink(spanContext: ctx)` → `links: [EmbraceSpanLink(spanId: ctx.spanId.hexString, traceId: ctx.traceId.hexString)]` (`attributes:` defaults to `[:]`; carry over any attributes passed to `addLink(spanContext:attributes:)`); `.markAsKeySpan()` and other OTel builder steps have no 7.0 equivalent — drop them and flag them if the app depends on them.

### 5.2 Completed spans

```swift
// 6.x
Embrace.client?.recordCompletedSpan(
    name: "import", type: .performance,
    parent: nil, startTime: start, endTime: end,
    attributes: [...], events: [...], errorCode: nil
)
```

**No error code** — `createSpan` with `endTime` is exact:

```swift
EmbraceIO.shared.createSpan(
    name: "import", type: .performance,
    startTime: start, endTime: end, attributes: [...]
)
```

**With an error code** — `createSpan` has **no `errorCode` parameter**, and passing
`endTime` returns an already-ended span, so you cannot attach the code afterward.
Create the span *without* `endTime`, then end it with the code. This is the only way
to preserve `.failure` / `.userAbandon` on a completed span:

```swift
let span = EmbraceIO.shared.createSpan(
    name: "import", type: .performance,
    startTime: start, attributes: [...]
)
span?.end(errorCode: .failure, endTime: end)   // see §5.3 for end(errorCode:endTime:)
```

Following the no-error form for a span that had an `errorCode` silently downgrades it
to a non-error span — do not do this.

### 5.3 Operating on a span

| 6.x (OTel `Span`) | 7.0 (`EmbraceSpan`) |
|---|---|
| `span.end()` | `span.end()` |
| `span.end(time: t)` | `span.end(endTime: t)` |
| `span.end(errorCode: .failure, time: t)` | `span.end(errorCode: .failure, endTime: t)` |
| `try span.addEvent(name:attributes:)` | `span.addEvent(name:type:timestamp:attributes:) -> EmbraceSpanEvent?` (no throw; nil = dropped at limit) — **`attributes:` has no default**, see below |
| — | `span.addEvent(_ event: EmbraceSpanEvent) -> EmbraceSpanEvent?` |
| — | `span.addLink(spanId:traceId:attributes:) -> EmbraceSpanLink?` / `span.addLink(_:)` (new in 7.0; 6.x links were builder-only, see §5.1) |
| `span.setAttribute(key:value:)` | `span.setAttribute(key: String, value: EmbraceAttributeValue?)` — no throw; passing `nil` removes the attribute |
| `span.status = ...` | `span.setStatus(_ status: EmbraceSpanStatus)` |
| readable members | `name`, `context`, `parentSpanId`, `type`, `status`, `startTime`, `endTime`, `events`, `links`, `attributes`, `sessionId`, `processId` |

No span API throws in 7.0 — `setAttribute` silently drops the attribute (with an SDK
warning) when the per-span limit is hit. Any `try`/`try?` on a span call is dead and must
be removed.

**`addEvent` always takes `attributes:`.** The protocol requirement
`addEvent(name:type:timestamp:attributes:)` defaults nothing; the convenience overload is
`addEvent(name:type: EmbraceType? = .performance, attributes:)`. There is no bare
`addEvent(name:)` form, so a 6.x `span.addEvent(name: "x")` becomes
`span.addEvent(name: "x", attributes: [:])`. Note the convenience `type:` defaults to
`.performance`, not `nil`.

Returned events/links are the *sanitized stored copies* — names/attributes may be rewritten or truncated. `nil` means dropped (per-span limit), with an SDK warning logged.

### 5.4 Flush — REMOVED

`Embrace.client?.flush(span)` and `flush()` have no 7.0 equivalent. Delete the calls; export timing is SDK-managed.

### 5.5 Block-based `recordSpan` helper — REMOVED, reimplement

6.x shipped a block-based helper as both a static and an instance method
(`Embrace.recordSpan(...)` and `Embrace.client?.recordSpan(...)`):

```swift
// 6.x — starts a span, runs the block, ends the span (block runs even if the SDK
// isn't started yet)
try Embrace.recordSpan(name: "checkout", type: .performance, attributes: [...]) { span in
    // work
}
```

There is **no 7.0 equivalent and no entry elsewhere in this file** — do not escalate,
reimplement it inline with `createSpan` + `end()`:

```swift
let span = EmbraceIO.shared.createSpan(name: "checkout", type: .performance, attributes: [...])
defer { span?.end() }
return try block(span)
```

`createSpan` returns `nil` when the SDK isn't started, so the block still runs in that
case — preserving the 6.x behavior. If the call site needs the error-code form, end with
`span?.end(errorCode:endTime:)` instead of the bare `end()` in the `defer`.

## 6. Session events, breadcrumbs, logs

### 6.1 Session events

```swift
// 6.x
Embrace.client?.add(event: someSpanEvent)
Embrace.client?.add(events: [e1, e2])

// 7.0 — no batch form; call per event
EmbraceIO.shared.addSessionEvent(
    name: "user_action",
    type: .performance,            // EmbraceType? = nil
    timestamp: Date(),
    attributes: ["k": "v"]
)                                   // -> EmbraceSpanEvent? (discardable)
EmbraceIO.shared.addSessionEvent(someEmbraceSpanEvent)
```

### 6.2 Breadcrumbs

```swift
// 6.x
Embrace.client?.add(event: .breadcrumb("Tapped login"))

// 7.0
EmbraceIO.shared.addBreadcrumb("Tapped login")
// full: addBreadcrumb(_ message: String, timestamp: Date = Date(), attributes: EmbraceAttributes = [:])
```

The `Breadcrumb` class and `.breadcrumb(_:)` `SpanEvent` factory are gone.

### 6.3 Logs

6.x had four overloads (plain, explicit-timestamp, `attachment: Data`, `attachmentId:`+`attachmentUrl:`). 7.0 has one:

```swift
EmbraceIO.shared.log(
    _ message: String,
    severity: EmbraceLogSeverity,
    timestamp: Date = Date(),
    attachment: EmbraceLogAttachment? = nil,
    attributes: EmbraceAttributes = [:],
    stackTraceBehavior: EmbraceStackTraceBehavior = .default
)
```

**There is no `type:` parameter.** The facade always logs as `.message`. A 6.x call that
passed a non-default `type:` (e.g. `log(msg, severity: .info, type: someType)`) has no 7.0
facade equivalent — drop the argument and tell the user their logs will now carry
`emb.type = sys.log`, or move the distinction into an attribute. Do not invent a `type:`
argument; it will not compile.

| 6.x | 7.0 |
|---|---|
| `attachment: someData` | `attachment: EmbraceLogAttachment(data: someData)` |
| `attachmentId: id, attachmentUrl: url` | `attachment: EmbraceLogAttachment(id: id, url: url)` |
| `try`/`try?` prefix (6.20 facade) | remove — does not throw |

## 7. Metadata

### 7.0 `MetadataLifespan.session` → `.userSession`

The type keeps its name, but the case is renamed: 7.0 has `.userSession`, `.process` and
`.permanent`. **Every `lifespan: .session` argument must become `lifespan: .userSession`**
— in properties, personas, and the `lifespans:` arrays of `removeAllProperties` /
`removeAllPersonas`. `.process` and `.permanent` carry over unchanged.

The rename is not cosmetic. In 6.x `.session` meant one foreground or background interval.
In 7.0 that interval is a *session part*, and `.userSession` scopes the metadata to the whole
user session — so the value is attached to every part of that user session and survives
process death for as long as the user session does. Metadata that was set once per foreground
interval on purpose now spans more data than before. Flag it; don't silently rescope it.

### 7.1 User identity

```swift
// 6.x
Embrace.client?.metadata.userName = "Jane"          // REMOVED
Embrace.client?.metadata.userEmail = "j@x.com"      // REMOVED
Embrace.client?.metadata.userIdentifier = "abc123"
Embrace.client?.metadata.clearUserProperties()       // REMOVED

// 7.0
EmbraceIO.shared.userIdentifier = "abc123"
EmbraceIO.shared.userIdentifier = nil                // clear
```

For dropped `userName`/`userEmail` values, offer the user a session property (`setProperty(key: "user_name", ...)`) or persona — their call.

### 7.2 Properties

```swift
// 6.x (throws)
try Embrace.client?.metadata.addProperty(key: "tier", value: "pro", lifespan: .session)
try Embrace.client?.metadata.updateProperty(key: "tier", value: "max", lifespan: .session)
try Embrace.client?.metadata.removeProperty(key: "tier", lifespan: .session)
Embrace.client?.metadata.removeAllProperties(lifespans: [...])

// 7.0 (one non-throwing setter; nil value removes)
EmbraceIO.shared.setProperty(key: "tier", value: "pro", lifespan: .userSession)   // add or update
EmbraceIO.shared.setProperty(key: "tier", value: nil, lifespan: .userSession)     // remove
EmbraceIO.shared.removeAllProperties(lifespans: [.userSession, .process, .permanent])
```

**Lifespan is now required to remove.** 6.x `removeProperty(key:)` could be called with no
`lifespan` (it defaulted to `.session`). 7.0's removal is `setProperty(value: nil, lifespan:)`
and the lifespan is mandatory. Map a 6.x `removeProperty(key: k)` with no lifespan to
`setProperty(key: k, value: nil, lifespan: .userSession)` (the 7.0 spelling of the same
default). **Caveat:** if the property was *added* with a different lifespan
(`.permanent`/`.process`), a `.userSession` removal won't target it — match the lifespan to
how the property was added, or call `setProperty(value: nil)` once per relevant lifespan.

### 7.3 Resources — REMOVED

`metadata.addResource(key:value:lifespan:)`, `updateResource`, `removeResource`, `removeAllResources` have **no 7.0 equivalent**. If resource-level metadata is needed on OTel exports, set it via `OTelOptions(resource:)` at startup; otherwise migrate values to session properties. Surface the choice.

### 7.4 Personas

```swift
// 6.x (throws; PersonaTag and String variants; sync currentPersonas)
try Embrace.client?.metadata.add(persona: "power_user", lifespan: .permanent)
try Embrace.client?.metadata.remove(persona: "power_user", lifespan: .permanent)
let tags = Embrace.client?.metadata.currentPersonas            // [PersonaTag], sync

// 7.0 (non-throwing, String only, async read)
EmbraceIO.shared.addPersona("power_user", lifespan: .permanent)
EmbraceIO.shared.removePersona("power_user", lifespan: .permanent)
EmbraceIO.shared.removeAllPersonas(lifespans: [...])
EmbraceIO.shared.getCurrentPersonas { personas in ... }        // [String]
```

`PersonaTag` and the synchronous `currentPersonas` getter are gone — rewrite sync reads into the completion-handler form.

## 8. Crashes

```swift
// 6.x
try Embrace.client?.appendCrashInfo(key: "step", value: "payment")
let state = Embrace.client?.lastRunEndState()
Embrace.client?.crash(type: .fatalError)          // debug helper

// 7.0
EmbraceIO.shared.appendCrashInfo(key: "step", value: "payment")   // no throw
let state = EmbraceIO.shared.lastRunEndState()    // EmbraceLastRunEndState
EmbraceCrashHelper.crash(example: .fatalError)    // standalone enum, returns Never
```

`EmbraceExampleCrash` cases: `.fatalError`, `.unwrapOptional`, `.indexOutOfBounds`.

The **no-argument** form is common too — `Embrace.client?.crash()` (the bare debug
helper) → `EmbraceCrashHelper.crash()` (the `example:` parameter defaults to
`.unwrapOptional`). If the app has several distinct crash functions intended to show as
separate crash groups, pass distinct cases (`.fatalError` / `.unwrapOptional` /
`.indexOutOfBounds`) to preserve that separation.

## 9. Startup instrumentation

```swift
// 6.x
Embrace.client?.startupInstrumentation.buildChildSpan(name: "boot", type: .startup)?.startSpan()
Embrace.client?.startupInstrumentation.recordCompletedChildSpan(name: "warm", startTime: t1, endTime: t2)
Embrace.client?.startupInstrumentation.addAttributesToTrace(["cold": "true"])
// 6.20 facade: buildStartupChildSpan / recordCompletedStartupChildSpan / addAttributesToStartupTrace

// 7.0 — flat on EmbraceIO
EmbraceIO.shared.createStartupChildSpan(name: "boot")                              // -> EmbraceSpan?
EmbraceIO.shared.createStartupChildSpan(name: "warm", startTime: t1, endTime: t2)
EmbraceIO.shared.addAttributesToStartupTrace(["cold": "true"])                     // EmbraceAttributes, -> Void
```

`createStartupChildSpan(name:startTime:endTime:attributes:)` has no `type:` parameter —
a 6.x `type:` argument on the startup child-span call is dropped.

`StartupInstrumentation` is no longer publicly reachable.

## 10. Push notifications

```swift
// 6.x
try Embrace.client?.add(notification: someUNNotification)

// 7.0 (no throw)
EmbraceIO.shared.addPushNotificationEvent(
    notification: someUNNotification,
    timestamp: Date(),            // default
    attributes: [:],              // default
    captureData: true             // default
)
EmbraceIO.shared.addPushNotificationEvent(userInfo: apsDict, captureData: true)
```

`PushNotificationError` is no longer thrown.

6.x also exposed a `PushNotificationEvent.push(userInfo:)` factory, usually paired with
`add(event:)`:

```swift
// 6.x
if let event = try? PushNotificationEvent.push(userInfo: userInfo) {
    Embrace.client?.add(event: event)
}

// 7.0 — the factory + add(event:) is replaced by the userInfo: overload
EmbraceIO.shared.addPushNotificationEvent(userInfo: userInfo)
```

`PushNotificationEvent` is no longer part of the public push API — do not look for a
replacement type, use the `addPushNotificationEvent(userInfo:)` / `(notification:)`
methods directly.

## 11. OTel interop

- `Embrace.client?.tracer(instrumentationName:)` → `EmbraceIO.shared.tracer(instrumentationName:instrumentationVersion:)`. The receiver changes and the result is now optional: it returns `nil` unless the SDK was started with an `EmbraceIO.OTelOptions`. If the app has no exporters to register, pass an empty `EmbraceIO.OTelOptions()` purely to enable the providers.
- New in 7.0, with no 6.x equivalent: `EmbraceIO.shared.logger(instrumentationScopeName:instrumentationVersion:)`, plus `EmbraceIO.shared.tracerProvider` / `loggerProvider` (`TracerProvider?` / `LoggerProvider?`) for the options the convenience accessors don't cover (schema URL, scope attributes, trace-context inclusion).
- Spans and logs created through these providers are captured by Embrace, forwarded to the `OTelOptions` processors and exporters, and count against the same per-session limits as `createSpan` / `log`. The providers outlive `stop()`; signals created after it carry an empty session id.
- **Global registration is now opt-in.** 6.x registered the Embrace providers on `OpenTelemetry.instance` unconditionally. In 7.0, pass `registersGlobalProviders: true` in `OTelOptions` (§3.2) to restore that. An app whose third-party OTel instrumentation "just worked" in 6.x without touching Embrace APIs needs this flag — there is no build error to flag it.
- `OpenTelemetryExport`, `OpenTelemetryProcessor` types → replaced by `EmbraceIO.OTelOptions` (§3.2).

## 12. Custom `CaptureService` subclasses

Only reachable in CocoaPods integrations, where the whole SDK builds as one `EmbraceIO`
module. Under SPM, `CaptureService` lives in the `EmbraceCaptureService` target, which is
not exposed as a package product and is not re-exported by `EmbraceIO` — `import EmbraceIO`
+ `: CaptureService` fails to compile. That is true in 6.x as well, so an SPM app cannot
have arrived here with a custom capture service.

`CaptureService` is no longer an `NSObject` subclass and has no `@objc` members.

| 6.x | 7.0 |
|---|---|
| `class MyService: CaptureService` (NSObject inherited) | same declaration; add explicit `init` calls if you relied on NSObject behavior |
| `onInstall()`, `onStart()`, `onStop()` | unchanged |
| `onSessionStart(_ session: EmbraceSession)` | `onSessionStart()` — **session parameter removed** |
| `onSessionWillEnd(_ session: EmbraceSession)` | `onSessionWillEnd()` — **session parameter removed** |
| `onConfigUpdated(_ config: EmbraceConfigurable)` | unchanged |
| `buildSpan(name:type:attributes:) -> SpanBuilder?` | `createSpan(...) -> EmbraceSpan?` — same signature as §5.1, no throw |
| `add(event:)` / `add(events:)` `-> Bool` | `addSessionEvent(...) -> EmbraceSpanEvent?` (no throw) |
| `log(...)` | `log(...)` — no throw (`severity` defaults to `.info` on this side) |
| `service.install(otel:logger:)` / `.start()` / `.stop()` called manually | now `package` — not callable; the SDK drives the lifecycle |
| `otel` property (`EmbraceOpenTelemetry?`) | now `package` — use the `CaptureService` helper methods (`logger` is still public) |

Inside subclasses, apply the §4 type renames (`[String: AttributeValue]` → `EmbraceAttributes`, `SpanType`/`LogType` → `EmbraceType`, `LogSeverity` → `EmbraceLogSeverity`).

## 13. Objective-C

6.x exposed `Embrace`, `MetadataHandler`, options, and several capture services to Objective-C. **7.0 has no `@objc` public API at all.** Objective-C call sites cannot be migrated — escalate. (Swift files in a mixed project migrate normally.)

## 14. Packaging summary

| | 6.x | 7.0 |
|---|---|---|
| SPM products | `EmbraceIO`, `EmbraceCore`, `EmbraceSemantics`, `EmbraceMacros`, `EmbraceCrash`, `EmbraceKSCrashBacktraceSupport`, `EmbraceCrashlyticsSupport` | `EmbraceIO`, `EmbraceCore`, `EmbraceSemantics`, `EmbraceMacros`, `EmbraceKSCrashBacktraceSupport` — **`EmbraceCrash` and `EmbraceCrashlyticsSupport` removed** (bundled into `EmbraceIO`) |
| Typical app imports | `import EmbraceIO` (+ `EmbraceCrash`, `OpenTelemetryApi` as needed) | `import EmbraceIO` only; `import OpenTelemetrySdk` where `OTelOptions` is built |
| CocoaPods | pod `EmbraceIO` | pod `EmbraceIO` (new `EmbraceOTelBridge` subspec, Crashlytics support folded in — no Podfile change beyond the version) |
| Min platforms | iOS 13 / tvOS 13 / macOS 13 / watchOS 6 | iOS 15 / tvOS 15 / macOS 13 / watchOS 9 |

## 15. Removed with no replacement — checklist

Surface each of these to the user if found; do not silently delete:

1. `appGroupId` in Options (§3)
2. Custom `CrashReporter` conformances (§3.1)
3. `resetUploadCache()`, and `endCurrentSession()`'s "leave no session running" behavior (§2)
4. `flush(_ span:)` / `flush()` (§5.4)
5. `userName` / `userEmail` / `clearUserProperties()` (§7.1)
6. Resource metadata: `addResource` / `updateResource` / `removeResource` / `removeAllResources` (§7.3)
7. `PersonaTag` type and synchronous `currentPersonas` (§7.4)
8. Manual `CaptureService` lifecycle driving (`install`/`start`/`stop`) and the `otel` property (§12)
9. The entire Objective-C API surface (§13)
10. OTel `SpanBuilder` extras: `markAsKeySpan()` and other builder steps without a `createSpan` parameter (§5.1)

## 16. Carried over unchanged — do not escalate

These are public in both 6.22+ and 7.0 with identical names and signatures. A call site that
matches one of them needs **no** change, and is not a gap in this file:

- **Experiments and feature flags:** `trackExperiment(id:variant:startedAt:)`,
  `trackExperiments(_:)`, `untrackExperiment(id:endedAt:)`, `untrackExperiments(ids:endedAt:)`,
  and the four `…FeatureFlag…` equivalents, plus the `TrackedExperiment` / `TrackedFeatureFlag`
  types. In 6.x these were reached through `EmbraceIO.shared`, which is also the 7.0 entry
  point, so even the receiver is unchanged. They remain process-scoped and are not persisted
  across launches, so they must be declared again on every start — same as 6.x.
- `URLSessionCaptureService.Options(traceparent:)` domain allowlisting (§3.4).
- `EmbraceType` statics in inferred position (`.networkRequest`, `.view`, `.message`, …). Call
  sites that name the type (`SpanType.view`, `let t: LogType = …`) still need the §4 rename.
