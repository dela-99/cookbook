# Kotlin Multiplatform

## The Interview Question

> "You're shipping a mobile app to iOS and Android. How many codebases?"

The instinct says two — one in Swift, one in Kotlin. The right answer in 2026 is **one** — with Kotlin Multiplatform.

---

## The Cost of "Two Codebases"

You ship a feature in Swift on Monday. Tuesday you re-implement it in Kotlin for Android. Wednesday a designer tweaks the validation rule. Now you fix it twice. Test it twice. Ship it twice. And of course you only fix the bug in one of them, because copy-paste between two languages eats half a day every time.

Your business logic is roughly **80% of your app**. The login flow, the API client, the offline cache, the data models, the form validation — none of that should care whether it's running on iOS or Android. So why are you writing it twice?

That's the question Kotlin Multiplatform answers.

---

## What KMP Actually Is

Kotlin Multiplatform (KMP) compiles **one Kotlin codebase** down to **native binaries on every target**:

- **Android** — compiles to JVM bytecode (the same as any native Android app)
- **iOS** — compiles to native ARM/x86 binaries via LLVM (no JS runtime, no bridge, no VM)
- **Web / Desktop / Server** — also supported, but mobile is the headline use case

The key word is **native**. Unlike React Native (JS bridge) or Flutter (custom rendering engine), KMP produces real native code for each platform. Your iOS team links an Xcode framework. Your Android team gets a regular Gradle module. They each look at it and see something they recognize.

---

## The Stack — Same Tools, Every Platform

Each KMP library replaces the two native ones you'd otherwise need:

| Need | What you'd use natively (iOS / Android) | What KMP gives you |
|---|---|---|
| **UI** | SwiftUI / Jetpack Compose | **Compose Multiplatform** — same Compose UI on both |
| **HTTP client** | URLSession / Retrofit | **Ktor** — one client, shared models |
| **Local database** | Core Data / Room | **SQLDelight** — type-safe SQL, generated for every target |
| **Async / concurrency** | Combine / Coroutines | **Coroutines + Flow** — one concurrency model |
| **Dependency injection** | Manual / Hilt | **Koin** — pure Kotlin, no annotations needed |
| **Testing** | XCTest / JUnit | **One test suite**, runs on every target in CI |

The whole stack is Kotlin. The whole stack is shared. The whole stack ships native.

---

## `expect / actual` — The Escape Hatch

KMP doesn't pretend it can do everything from shared code. When you need a platform-specific API — biometric auth, push tokens, the device's IDFA — you declare it with `expect` in shared code and write the `actual` per platform.

```kotlin
// commonMain — shared code
expect fun deviceId(): String

// androidMain — Android implementation
actual fun deviceId(): String =
    Settings.Secure.getString(contentResolver, Settings.Secure.ANDROID_ID)

// iosMain — iOS implementation
actual fun deviceId(): String =
    UIDevice.currentDevice.identifierForVendor!!.UUIDString
```

This isn't a leaky abstraction — it's a deliberate one. The **shared interface is yours to define**, and the native implementation lives where it should. Your business logic doesn't care which platform it's on; the moment it does, you make it explicit.

---

## KMP vs Flutter vs React Native

The honest comparison:

| Approach | UI | Performance | Native API access | Ecosystem |
|---|---|---|---|---|
| **KMP + Compose Multiplatform** | Shared *or* native (your call per screen) | Native — no bridge, no VM | First-class via `expect/actual` | Young but growing fast |
| **Flutter** | Shared, rendered by Skia/Impeller | Near-native | Plugins | Mature, large community |
| **React Native** | Native components driven by JS | JS ↔ native bridge overhead | JS bridge or native modules | Mature, huge ecosystem |
| **Native (Swift + Kotlin)** | Native | Native | First-class | Best-in-class — and doubled |

**The KMP stance:** You only share what makes sense. Business logic, networking, persistence, validation — share it. UI is a per-screen decision: Compose Multiplatform when you want one source, native SwiftUI / Jetpack Compose when a screen needs to feel exactly like the platform.

That flexibility is what Flutter and RN can't match. They're all-in on shared UI. KMP lets you mix.

---

## What This Looks Like Day-to-Day

You open the project in IntelliJ or Android Studio. You see three source sets:

```
shared/
  commonMain/        ← Kotlin code that runs everywhere
  androidMain/       ← Android-specific actual implementations
  iosMain/           ← iOS-specific actual implementations
```

You write a screen once in Compose Multiplatform. You hit run. The iOS simulator and the Android emulator boot side by side, both showing the same screen, both running the same `LoginViewModel`, both hitting the same Ktor client, both reading from the same SQLDelight database.

When you need a new feature, the first question stops being "where do I implement this?" and becomes "is there any reason this can't be shared?" Most of the time, the answer is no.

---

## Production Considerations

| Decision | What to think about |
|---|---|
| **iOS build times** | Kotlin/Native compilation is slower than JVM. Expect your iOS build to be the long pole — invest in build caching early. |
| **Library coverage** | Many popular Android-only libraries don't have KMP equivalents yet. Be ready to write `expect/actual` wrappers around native SDKs. |
| **Team skill mix** | Your iOS devs need to learn Kotlin. Your Android devs need to learn Xcode tooling. Plan a ramp; don't pretend it's free. |
| **Compose Multiplatform on iOS** | Production-ready but younger than Compose on Android — keep an eye on releases and expect the occasional rough edge. |
| **SwiftUI interop** | You can ship Compose Multiplatform screens *and* keep critical screens in SwiftUI. Don't fight your iOS team for full coverage on day one. |
| **Crash reporting on iOS** | Kotlin/Native crashes need symbolication. Set up dSYM uploads to Crashlytics / Sentry from the start, not after your first prod crash. |

---

## The Key Insight

You don't need to share UI to win at KMP.

Even just sharing your **business logic** — models, validation, API client, database, caching — eliminates the worst class of duplication: the one where the same bug ships to one platform and not the other. Compose Multiplatform is the bonus level on top.

Most teams should start with **shared logic + native UI**, ship to both stores, and then decide whether to share UI screen-by-screen.

---

## TL;DR

- One language (Kotlin), one codebase, two App Stores.
- Share business logic, networking, persistence, async, DI, and tests. Decide UI per-screen.
- `expect/actual` lets you reach native APIs without breaking the shared model.
- Compose Multiplatform brings Jetpack Compose to iOS for teams that want shared UI too.
- KMP doesn't replace Swift or Kotlin — it eliminates the duplication *between* them.

If you're shipping the same feature twice in two languages, you're paying a tax for nothing.

---

## Resources

### Docs
- [Kotlin Multiplatform — kotlinlang.org](https://kotlinlang.org/docs/multiplatform.html)
- [Compose Multiplatform — JetBrains](https://www.jetbrains.com/compose-multiplatform/)
- [Ktor](https://ktor.io/)
- [SQLDelight](https://cashapp.github.io/sqldelight/)
- [Koin](https://insert-koin.io/)
- [Kotlin Coroutines](https://kotlinlang.org/docs/coroutines-overview.html)
