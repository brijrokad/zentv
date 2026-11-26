# Device profile: TCL 75S450G

Source: `ZENTV_BUILD_PROMPT.md` v3, "Device profile: TCL 75S450G". Every line stays **unverified** until Phase 3 confirms it with read-only `adb` and records the evidence. Nothing here has been read from the TV yet.

**Directory name.** `tcl-g03-beyondtv4` is a working name taken from the 55" sibling's platform. Phase 3 renames this directory, and the `tcl-g03-beyondtv4-*` scopes in `safety/never_disable.yaml`, if `ro.product.device` / `ro.product.name` say otherwise.

**Serial number.** The owner has it. It is **not** stored in this repo. Its prefix suggests the set was built in May 2023 (unverified). `survey.json` redacts serials and other identifiers.

**Owner answers (confirmed 2026-11-26).** Lines 7–13 and 16 are what the owner uses and requires. They are still `unverified` on the TV itself until Phase 3 maps them to packages. Decisions: `com.tcl.xian.StartandroidService` is protected (firmware updates). `com.tcl.usercenter` is `risk: high`, asked by name. `com.tcl.bootadservice` is revisited at Checkpoint 4. The TCL Channel button isn't used.

| # | Line | Status | Phase 3 check |
|---|---|---|---|
| 1 | **Retail model:** TCL 75S450G (75", S4 class, 2023) | unverified | `getprop ro.product.model` (siblings report "Smart TV"), `ro.product.name`, `ro.boot.product.hardware.sku` |
| 2 | **Platform:** expected G03 / `BeyondTV4`, Realtek `rtd288o` (`RTD2851M`) | unverified | `getprop ro.product.device`, `ro.product.board`, `ro.board.platform` |
| 3 | **OS:** expected Google TV on Android 11 (SDK 30), `ro.tcl.product_type=GTV` | unverified | `getprop ro.build.version.release`, `ro.build.version.sdk`, `ro.tcl.product_type`; `pm list packages` for `com.google.android.apps.tv.launcherx` vs `com.google.android.tvlauncher` |
| 4 | **OS:** Basic TV / "Apps only" mode on or off | unverified | HOME resolver (`cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME`); home packages present and enabled |
| 5 | **Firmware:** owner updates to the latest TCL firmware before Phase 3. Record the fingerprint and incremental (sibling: `AR24`, patch 2023-03-05). | unverified | `getprop ro.build.fingerprint`, `ro.build.version.incremental`, `ro.build.version.security_patch` |
| 6 | **ABI and RAM:** expected armeabi-v7a only (zygote32), about 2 GB RAM | unverified | `getprop ro.product.cpu.abilist`, `ro.zygote`; `cat /proc/meminfo` (MemTotal, MemAvailable) |
| 7 | **Network:** Wi-Fi today | unverified | `dumpsys connectivity` (active transport); `dumpsys wifi` (saved-network owner, `cname=`: `setupwraith` vs `com.android.tv.settings`) |
| 8 | **Network:** built-in Ethernet must stay usable | unverified (requirement) | Ethernet interface present (`ip link`, read-only); smoke test links Ethernet if a cable is available |
| 9 | **Tuner/antenna:** **in use** (antenna, Live TV) and HDMI inputs in use. Keep every tuner and input service enabled. | unverified | `dumpsys tv_input` (input services, HDMI and tuner inputs); report whether channels are configured |
| 10 | **Feature in use:** TCL remote, including the voice button | unverified | map to packages (`com.tcl.tcl_bt_rcu_service`, `com.tcl.autopair`, `com.google.android.katniss` expected); smoke test |
| 11 | **Feature in use:** Google TV phone remote | unverified | map to packages (`com.google.android.tv.remote.service` expected); smoke test |
| 12 | **Feature in use:** Google Home casting (Chromecast built-in) | unverified | map to packages (`com.google.android.apps.mediashell` expected); smoke test |
| 13 | **Feature in use:** AirPlay / HomeKit | unverified | find the AirPlay/HomeKit packages (names unknown for TCL); smoke test |
| 14 | **TCL boot manager:** which app-op `TclAppBoot` checks (`APP_AUTO_START` or `AUTO_START`) | unverified | `cmd appops help` / `appops get <any app>` shows which op names exist (read-only); `dumpsys package com.tcl.appboot` if present |
| 15 | **Remote app buttons** (Netflix, YouTube, Prime, Apple, TCL Channel, gear, Input) depend on `launcherx` on this platform | unverified | read-only: `logcat -s TclPhoneWindowManager` while the owner presses them (no state change) |
| 16 | **Feature in use:** Google TV's Google Home panel (lights in quick settings), hosted by `com.google.android.apps.tv.dreamx`. Note: "Apps only" mode hides this panel on G03, so that fallback would cost it. | unverified | confirm `dreamx` hosts the panel (`dumpsys package com.google.android.apps.tv.dreamx`, look for SmartHomeMainActivity); smoke test |

## Reference data (not about this TV)

Hints from cleanyourtv at `be608705`, read as data. They cover **sibling units**, not the 75S450G, and Phase 3 checks each one.

- **TCL 55S450G** (`examples/tcl-55s450g/`, `docs/devices/tcl-55s450g.md`):
  - Product `G03_4K_US_NF_DB`, device `BeyondTV4`, board `RTD2851M`, platform `rtd288o`.
  - Google TV 11 / SDK 30, fingerprint `TCL/G03_4K_US_NF_DB/BeyondTV4:11/RP1A.200622.001/AR24:user/release-keys`. armeabi-v7a only.
- **Same platform, other firmware:** `tcl-55s546-us` (GTV93) and `tcl-g03-google-tv` (AR09/AR11, 2 GB RAM). "Do not copy either list onto this build."
- **`TclAppBoot`** refused to bind an accessibility service until `appops set <pkg> APP_AUTO_START allow` + `appops write-settings`. On AR24, `AUTO_START` was "Unknown operation string".
- **`launcherx` and the remote:** with `launcherx` disabled and no helper, the remote's app buttons, gear and Input did nothing. Re-enabling `launcherx` restored them. zentv keeps `launcherx` enabled anyway (rule 7).
- **An injected `KEYCODE_HOME`** resumed `launcherx`, while the real Home button behaved differently. Injected keys aren't a valid Home test.
- **Saved Wi-Fi owner** on the 55S450G was `com.android.tv.settings` (system UID), not `setupwraith`.
- **A same-platform 43P735** kept `launcherx`, `setupwraith`, the updater, the inputs and the remote services, and took Home with a window-watching redirect + `APP_AUTO_START`. "Google TV showed briefly first" after a reboot (`tcl-g03-google-tv/debloat.txt:347-351`).
- **Keep enabled** (sibling DO-NOT-DISABLE notes): `com.tcl.tv`, `com.tcl.tvinput`, `com.tcl.suspension`, `com.tcl.settings`, `com.tcl.system.server`, `com.tcl.providers.config`, `com.tcl.initsetup`, `com.tcl.factory.view`, `com.tcl.tcl_bt_rcu_service`, `com.tcl.autopair`, `com.tcl.inputmethod.international`, `com.google.android.tv.remote.service`, `com.tcl.versionUpdateApp`. Also `com.tcl.xian.StartandroidService`, because the updater needs it.
- **Risky:**
  - `com.tcl.usercenter` (a 43C641 rebooted on every standby wake with it off, #3533).
  - `com.google.android.apps.tv.dreamx` (it also hosts the Google Home panel).
  - `com.tcl.partnercustomizer` + `com.tcl.waterfall.overseas` (the TCL Channel button needs both).
- **couch-tv** (`docs/TV-COMPATIBILITY.md:151-158`):
  - `com.tcl.guard` trims a custom home shortly after start.
  - TCL's boot controller opens Google home before any accessibility helper runs.
  - A TCL on Android TV 11 starts Google home as `.home.VanillaModeHomeActivity`.
