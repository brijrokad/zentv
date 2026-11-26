# Phase 1 evaluation: cleanyourtv vs couch-tv

**Re-run 2026-11-26** at the current pins: cleanyourtv `be608705`, couch-tv `bc5df03a`. Inputs are `SECURITY_AUDIT.md` (Phase 0, §7 delta, **§8 delta #2**) and static reading of both clones at those commits. File references point into those clones. zentv now targets **two TVs**: the Sony KD-65X80K (BRAVIA 4K VH21) and a **TCL 75S450G**. Figures marked *estimate* get measured in M3.

**Approved at Checkpoint 2.** The decisions taken on §7 (rules 6 and 9, launcher stack, keep-watching, M3a tests) are recorded in `ZENTV_BUILD_PROMPT.md` v3. Where the wording differs, the build prompt wins. One example: the re-check reads zentv's own process importance (`IMPORTANCE_FOREGROUND`), not "activity resumed".

## 0. Changes since the 2026-11-11 evaluation

- **Matrix:** couch-tv drops from 2.65 to **2.45** (more platforms, prebuilt native code, a heavier APK). cleanyourtv stays at **3.95**. The compatibility row now covers **Sony + TCL** (§2).
- **Direction:** unchanged. **Phase 6:** still not worth the risk.
- **Launcher stack:** still Kotlin + plain Views. The TCL adds hard constraints: **Android 11 / SDK 30, armeabi-v7a only, about 2 GB RAM**, and a vendor memory manager (`com.tcl.guard`) that trims background apps (§5).
- **Home button:** split by TV (§6).
  - Sony: new evidence of a `launcherx` race after Home (cleanyourtv `7b3c5465`).
  - **TCL**: the helper almost certainly can't bind without TCL's `APP_AUTO_START` appop, and that op isn't on rule 6's allowed list. **This is the main Checkpoint 2 decision** (§7, item 6).
- **New prompt items:** 6–10 in §7.

## 1. Architecture and philosophy

**cleanyourtv** is an ADB toolkit plus a deliberately small launcher.
- Python/shell tools (`tools/`) apply a per-device list with `pm disable-user`, record state before the first change, and replay it on restore with read-back. A core denylist and a HOME guard sit in front of every change.
- The launcher is plain Java with no `INTERNET` permission. It now formally supports **keeping the stock home enabled** (`STOCK_LAUNCHER=none` + `stock_home_redirect`), which is the model zentv's rule 7 requires.
- Extras live outside the core: themes and about 41 add-ons (4 new, none with permissions).
- Its philosophy is conservative, evidence-driven and per-device. It now has **518 lists** (about 50 Sony, **91 TCL**, including the 55" sibling of the zentv TCL).
- The cost is sprawl and extreme churn: 1,322 commits from 215 author emails in 16 days, with all merges by one unsigned maintainer (D2-CY-05).

**couch-tv** has grown from a smart home screen into a **multi-platform product**.
- The core is still a WebView home (`tv-home/web`) with an optional always-on Python bridge, an on-TV app that drives the TV's own ADB, a phone remote and an LLM assistant.
- New since 11-11:
  - A desktop **setup app** (localhost, signed updates)
  - A **Google Play flavour** of the on-TV app with the dangerous powers removed
  - Ports for Apple TV, Vega, Titan, LG (rooted), Samsung, Roku and VIZIO
  - A cloud design store ("Couch TV Studio")
  - Spotify, IMAP bookings and multi-provider LLM keys
  - A **Matter controller shipped as prebuilt native code** (D2-CT-01)
- Its philosophy is still "feel finished for a household". It accepts high device privilege to get there: persistent ADB, a self-reviving accessibility watch that can read windows, and a notification listener (CT-02, D2-CT-03, D2-CT-04).

## 2. Weighted decision matrix

| Criterion | Weight | cleanyourtv | couch-tv |
|---|---|---|---|
| Security posture | 20% | 4. No network in the launcher. Core changes are hardening (ADB-greeting check in `adb-closed.py`). Caveats: agent prompt, upstream bot, churn. | 2. Unauthenticated LAN bridge by default. Persistent ADB. Self-reviving watch that can read windows. Unverifiable native binaries. The setup app and Play flavour are real improvements. |
| Safety / reversibility | 15% | 4. Record → replay → read-back. Lists still disable OTA, `setupwraith` and stock homes, and the TCL install's appops aren't recorded. | 2. Re-enables and re-disables behind the user's back. A periodic repair job. `undo.sh` is good but doesn't restore earlier state per setting. |
| Performance footprint | 15% | 5. Small native launcher, no polling | 1. WebView home, video loops, about 8 MB of Matter native libraries per APK (README), bridge |
| **Sony + TCL** / Google TV compatibility | 10% | 4. Sony: VH21/VH22 lists and Home-key evidence. TCL: the G03 sibling list, `APP_AUTO_START` handling, key-repeat bisects. | 3. Sony boot-loop fix. TCL handled, but through a placeholder TV input that gets around TCL's control (D-CT-06) and an `AUTO_START` self-grant. |
| Code quality / tests | 10% | 4. Large unittest suite, CI with SHA-pinned actions | 3. Tests grew a lot (25% of the delta). Release APKs are still built off-CI, release lint is off. |
| UX finish | 10% | 3 | 5 |
| Simplicity | 10% | 3. No extra computer, but tool sprawl | 1. A dozen platforms, a cloud service, bridge + on-TV + setup app |
| Maintenance / community | 5% | 3. Very active, single unsigned merger, bot-gated | 4. Responsive maintainer, now a second merger |
| Extensibility | 5% | 5. Device lists, themes, add-ons | 4. Design store, widgets, JSON config |
| **Weighted total** | | **3.95** | **2.45** |

**Change I'm proposing:** "Sony/Google TV compatibility" becomes "Sony + TCL / Google TV compatibility". I scored each TV and took the lower of the two, so neither TV can hide a weak result on the other.

## 3. Feature inventory

| Only in cleanyourtv | Only in couch-tv |
|---|---|
| Per-device debloat lists with notes (518, including 91 TCL) | Scenes with a clock set into the photo, glass digits, video loops |
| State record + verified replay restore | Weather, people, "keep watching" (Watch Next, media sessions) |
| Core denylist, HOME guard, setupwraith Wi-Fi check | Phone remote, PIN pairing (on-TV), JustWatch search and deep links |
| Read-only privacy audit, drift check (`check.py`) | LLM assistant (Claude CLI, or keys for five other providers) |
| ADB-closed check **with an ADB handshake** (`adb-closed.py`) | CrashGuard step-aside to the stock home |
| Bench, perfetto traces, flame charts | Desktop setup app (localhost, Ed25519-signed updates, closes ADB at the end) |
| Key helpers (Home, Settings, app buttons by scancode), `volume_pauses_filter`, `stock_home_redirect` | Matter / Home Assistant control, Spotify, calendar and bookings widgets |
| Themes, add-ons, PowerShell twins | Design store, multi-platform ports, Play-store build |

## 4. Verdict on the direction

**I still agree with it.** Take the safety model from cleanyourtv, rebuild couch-tv's *look* natively, and use none of couch-tv's runtime components. The delta strengthens the case on both sides:
- cleanyourtv's launcher now officially keeps the stock home enabled, as zentv does.
- couch-tv's own Play flavour proves the Option B shape is shippable: a watch that's off until the user enables it, no self-grants, no revival (D2-CT-09).
- At the same time, couch-tv's default builds became *more* privileged (D2-CT-03, D2-CT-04) and now carry unverifiable native code (D2-CT-01).

**Phase 6 (phone remote / assistant): still not worth the risk.** Both TVs already have the Google TV phone remote, and it's protected in `never_disable.yaml`. Two things in couch-tv are worth noting if Phase 6 ever comes back: the setup app's localhost + per-run secret + Host/Origin check, and the offline-key signed updates (D2-CT-06).

## 5. Launcher stack

**Use Kotlin with plain Android Views, and neither Leanback nor Compose for the MVP.** The TCL makes this firmer.

| Constraint | Sony VH21 | TCL 75S450G (expected from the 55S450G / G03 data) |
|---|---|---|
| Android / SDK | 12 / 31 (VH21 reference data) | **11 / 30** (`docs/devices/tcl-55s450g.md:18`) |
| ABI | arm64 + armv7 | **armeabi-v7a only, zygote32** (same, `:22`; `tcl-g03-google-tv/debloat.txt:167`) |
| RAM | 3 GB, about 480 MB available | **about 2 GB** (`tcl-g03-google-tv/debloat.txt:167`). The S4-class G10 has 1.8 GB (`tcl-55s470g`). |
| Vendor process killer | – | `com.tcl.guard` trims a custom home shortly after start (couch-tv `docs/TV-COMPATIBILITY.md:151-153`) |
| Play Protect | asks for `targetSdk` ≥ 30 | same family, so use `targetSdk` ≥ 30 |

| Option | APK (release, R8) | Cold start | Fit for the couch-tv look |
|---|---|---|---|
| **Plain Views + Kotlin** | well under 1 MB (cleanyourtv's Java launcher is gated at 576 KB, and the Kotlin stdlib adds about 0.1–0.2 MB, *estimate*). Pure JVM, so no ABI split is needed for armv7. | Lowest. Matters most on a 32-bit Realtek with about 2 GB RAM and a vendor trimmer. | Good: full control over drawing, focus and animation |
| Views + Leanback | +1 MB or more (*estimate*) | Low | Poor: imposes its own browse-row look |
| Compose for TV | 1.5–3 MB (*estimate*), which threatens the 2 MB MVP | Higher first frame. Worst on the TCL. | Good, and the most productive to write |

Decisions this implies:
- `minSdk 30`, `targetSdk` ≥ 30. No NDK code, no native libraries.
- No `kotlinx-coroutines`: `Handler` and `Executor` are enough.
- Keep idle RAM minimal so `com.tcl.guard` has less reason to trim zentv.
- **CrashGuard** must count only real crashes and unsettled starts. A TGuard trim kill isn't a crash.

**The couch-tv look without a WebView** (unchanged): a full-screen WebP scene with an optional cut-out layer, a clock `View` with a `BitmapShader` glass fill, pre-blurred pills, `ViewPropertyAnimator` crossfades and a focus-scaled app row. Weather is a separate `INTERNET` flavour (Open-Meteo only). The MVP ships one scene, and the rest load from a JSON theme folder. **Art:** couch-tv's scenes and the new MP4 loops are third-party (CC BY-SA etc.), so zentv sources its own.

## 6. Home-button feasibility (Option B), per TV

### 6.1 Sony KD-65X80K (VH21)

**What's known:**
- On a VH21 unit (KD-65X85K, Google TV 12, `STT2.230505.001.S136`), a key-filter helper received Home while `launcherx` and `setupwraith` stayed enabled. Home opened the launcher even from Google home, and held Volume Up still ramped (`examples/sony-bravia-4k-vh21/debloat.txt:45-52`).
- On the sibling VH22, `set-home-activity` "prints Success and changes nothing" while `launcherx` is enabled (`examples/sony-kd-65x82l/debloat.txt:20-33`). A KD-75X82L with `launcherx` disabled reported Home and the app buttons working with no helper (new lines in the same file). That doesn't apply to zentv, which keeps `launcherx` enabled.
- **New risk (D2-CY-01):** on a Sony XR-55X90K, `launcherx` "restarts its own home screen when it has been in the background for a while … a few milliseconds after the Home key brought it up", and that start lands just after the redirect. cleanyourtv handles this by watching windows and looking again twice at 1.2 s (`HomeKeyService.java` `redirectFromStockHome`, commit `7b3c5465`). Rule 9 forbids window watching.
  - **A rule-9-compatible fix:** the helper runs in zentv's own process and knows whether zentv's own activity is resumed. After it handles `KEYCODE_HOME`, it checks at about 1.2 s and 2.4 s and starts zentv again if zentv isn't in front. It reads only the app's own state, never other windows.
- The proven mechanism passes Home through and starts the launcher **as an app**, not as a Home intent. A Home-intent start breaks the remote's YouTube and Netflix buttons on Android 10+ (`HomeKeyService.java`, cleanyourtv #1274).

### 6.2 TCL 75S450G (G03 / BeyondTV4, expected)

**What's known (all from sibling units, none from this TV yet):**
1. **`TclAppBoot` blocks the helper.** It refuses to bind an app's accessibility service unless the app holds the `APP_AUTO_START` appop. On AR24 the op is `APP_AUTO_START`; on G08 it's `AUTO_START`. `appops set … allow` + `appops write-settings` survived a reboot and a 30 s power cut (`docs/devices/tcl-55s450g.md`, "`APP_AUTO_START`"; `launcher/build-and-install.sh:268-277`). couch-tv sees the same thing and adds that TCL can **reset** the op (`HomeKeyRules.kt:57`, `AGENTS.md:531-546`). **Without this appop, Option B probably can't work on the TCL.**
2. **Keeping `launcherx` enabled is right on this platform** (and rule 7 requires it). On AR24, with `launcherx` off and no helper, the remote's Netflix, YouTube, Prime, Apple, TCL Channel, gear and Input buttons did nothing. Re-enabling `launcherx` brought them back.
3. **The only same-platform unit that kept `launcherx`** (43P735, #3949) took Home with `stock_home_redirect` + HomeKeyService, which **watches windows**. It needed `APP_AUTO_START`, and "Google TV showed briefly first" after a reboot (`examples/tcl-g03-google-tv/debloat.txt:347-351`). **No report tests a key-filter-only helper with `launcherx` enabled on G03.**
4. **An injected `KEYCODE_HOME` is not a valid test.** On AR24 it resumed `launcherx` while the real Home button behaved differently. The spike must use the real remote.
5. **Boot:** TCL's boot controller opens Google home before any helper is bound (couch-tv `TV-COMPATIBILITY.md:155-158`). Expect Google TV after power-on.
6. **Process kills:** `com.tcl.guard` trims a custom home. If the helper shares that process, a trim can leave Android listing the service as crashed and unbound. couch-tv's `WatchRepair` exists because this happened on a Hisense. Rule 9 forbids self-revival, so the helper should **run in its own small process** (`android:process=":homekey"`) to stay out of the UI process's trims.
7. **Key repeat:** on G03, held volume still ramped with both helpers bound, "a little slower" (`tcl-g03-google-tv/debloat.txt:96`). On a G09 (Amlogic), any key filter broke repeat entirely (`docs/devices/tcl-55p71b-g09-key-repeat.md`). Must be checked on this TV.
8. **"Apps only" fallback:** on G03 it also hides Google TV's Google Home panel, the lights in quick settings (`tcl-g03-google-tv/debloat.txt:69`). Worth knowing if the household uses that panel.

### 6.3 Risks (both TVs)

1. **Power-on lands on Google TV** until the first Home press. This is near-certain on both: TCL's boot controller runs first, and on Sony `set-home-activity` doesn't stick while `launcherx` is enabled.
2. **Key repeat and remote buttons:** some builds drop held-key repeats while any key filter is bound.
3. **Consume vs. pass through:** consuming Home may skip side effects the system or `launcherx` relies on.
4. **The `launcherx` restart race** (Sony evidence; probably on TCL too).
5. **Silent switch-off:** force-stop, reinstall, a TCL appop reset or a TGuard trim can drop the helper, and rule 9 forbids revival. `smoke-test` and the docs must say how to switch it back on.
6. **TCL only:** without `APP_AUTO_START`, the helper never binds after a reboot.

### 6.4 The M3a spike, run on both TVs

- Home from Google home, from an app (Netflix, YouTube), from Settings and from an HDMI input, **with the real remote**.
- Home after zentv has been in the background for several minutes (the restart race).
- Phone-remote Home. Held Volume Up and Down. App buttons (Sony YouTube/Prime; TCL Netflix/YouTube/Prime/Apple/TCL Channel/gear/Input). The voice button.
- 5 cold boots and a standby wake. **On the TCL, also a standby wake with nothing disabled**, as a baseline for #3533.
- Variants: consume vs. pass through + start as an app, and with/without the own-state re-check.
- **On the TCL, with and without `APP_AUTO_START`**, only if Checkpoint 2 allows it.

**Fallback (both TVs):** Google TV "Apps only" mode, with zentv as a normal app, no helper and no HOME change. It's also benchmark state 2.

## 7. Where I'd change the prompt

**Carried over from 2026-11-11:**
1. **Power-on behaviour isn't specified.** Accept "one Home press after each boot" on both TVs. The evidence now makes it the realistic outcome on both. Optionally allow a snapshotted `cmd role add-role-holder android.app.role.HOME` trial in M3a (not on rule 6's list today, and not likely to help).
2. **Rule 9 says the helper "consumes only `KEYCODE_HOME`".** Allow either consume or pass-through + start-as-app, and let M3a pick.
3. **Smoke test additions:** held-Volume ramp, the remote's app buttons and phone-remote Home, plus the TCL items in the new TCL smoke test.
4. **Denylist wording I interpreted** (all widen protection): `*networkstack*`, the `com.google.android.*` module names, and verifier → `com.android.vending` / `com.google.android.gms` / `*verifier*`.
5. **Keep-watching permission:** `READ_TV_LISTINGS` would be an in-app prompt (rule 6 has no `pm grant`). Decide in Phase 5. couch-tv's Play build drops it and uses only what the app sees itself, which is a reasonable default.

**New:**

6. **TCL `APP_AUTO_START` (decision needed).** I recommend adding to rule 6, scoped tightly:
   - The connected TV's brand is TCL, and the target is **zentv's own package only**.
   - zentv records `appops get <zentv> APP_AUTO_START` (and `AUTO_START` if present) in the snapshot first.
   - It sets `allow` + `appops write-settings` only inside the explicit `zentv launcher enable-home-key` step, shown in its dry-run.
   - `launcher revert` restores the recorded mode and verifies it.
   - zentv doesn't re-apply it if TCL resets it (rule 8: drift is reported, not fixed).

   Without this, Option B on the TCL is very likely dead on arrival, and the TCL falls back to "Apps only". The placeholder TV-input trick (D-CT-06) stays forbidden whatever the decision.
7. **Rule 9 wording for the re-check.** Allow the helper to re-launch zentv up to twice within about 3 s of a Home press when **zentv's own activity** isn't resumed. That's own-process state only, never other windows. It covers the `launcherx` restart race (D2-CY-01).
8. **Helper process.** State in rule 9 that the helper runs in its own process (`:homekey`), so a vendor trim of the UI process (`com.tcl.guard`) doesn't take it down.
9. **Device profiles and safety lists:**
   - Add the TCL 75S450G profile (`devices/tcl-g03-beyondtv4/`, working name until Phase 3 reads `ro.product.device`).
   - Add TCL `never_disable` groups: TCL system/input/remote/updater packages, plus `katniss`, `tv.remote.service`, `mediashell` and AirPlay/HomeKit for features in use.
   - Add `risk: high` defaults: `com.tcl.usercenter` (#3533) and `dreamx` (Google Home panel).
10. **Phases 3, 5 and 7 run once per TV.** Phase 3 cross-checks `tcl-55s450g`, `tcl-55s546-us` and `tcl-g03-google-tv` as data, never copied. Phase 5's spike runs on both. Phase 7's bench covers both.
