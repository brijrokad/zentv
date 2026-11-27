# M3a spike: the Home key on the TCL 75S450G (2026-11-26/27)

**Verdict: GO for the TCL**, using the **consume** variant plus the own-process re-check.

| | |
|---|---|
| TV | TCL 75S450G, G03_4K_US_NF_DB / BeyondTV4, Google TV 11 (SDK 30), firmware AR10, profile `tcl-g03-beyondtv4` (confirmed) |
| APK | `io.github.brijrokad.zentv.spike` 0.0.1-spike, debug-signed, no permissions, no native code; built from `launcher/` (`./gradlew assembleSpike`) |
| Helper | `HomeKeyService` in `:homekey`. Only `flagRequestFilterKeyEvents`, `canRetrieveWindowContent=false`, no event types, no boot receiver, no self-enable (rule 9). |
| TV changes | `zentv launcher install` → `enable-home-key` (snapshot, `APP_AUTO_START allow` + `appops write-settings`, accessibility on) → tests → `revert` (read back clean). The spike app stays installed: zentv never uninstalls (rule 5), so the owner removes it in Settings → Apps. |
| Evidence | The spike's own log (`zentv-spike`) and the system log, both read-only. The owner pressed the **real remote** throughout; no injected keys were used. |

## Results

| Test | Passthrough + start-as-app | Consume |
|---|---|---|
| Home from Google TV home, YouTube, Settings, an HDMI input | ✅ 6/6. Spike front about 100 ms after launch (350 ms after release). | ✅ 7/7 |
| Phone remote (Google TV app) Home, device 8, source 0x701 | ✅ | ✅ |
| Home after about 4 min in YouTube (the `launcherx` race, D2-CY-01) | ✅ but **Google TV showed for about 1 s**. `launcherx` re-took the front ("Wake by home key", "LauncherX to foreground") 143 ms after the spike resumed. Re-check 1 (+1.2 s) found the UI not foreground and re-launched once. | ✅ **no flash**. `TclPhoneWindowManager.processHome` never ran (0 calls), so `launcherx` never raced. |
| Held Volume Up/Down | ramps ✅ | ramps ✅ |
| Gear, Input, app buttons | unaffected ✅ | unaffected ✅ |
| Restart: does the helper re-bind? | — | ✅ `APP_AUTO_START` stayed `allow` (write-settings persisted). TclAppBoot logged no refusal. The helper was bound with no action. |
| Power-on | — | Google TV home (expected; accepted "one Home press after power-on", rule 9) |
| Standby wake, then Home | — | ✅ (Home arrived from input device 2, scan 102) |
| TGuard (`com.tcl.guard` process) vs `:homekey` | Both spike processes stayed alive about 25 min, including in the background during YouTube. No kill or trim was logged. **Not proven**: zentv can't force a trim. | |
| Helper **without** `APP_AUTO_START` | not tested (it needs a revert and a restart). Sibling-TV evidence says it won't bind. | |

## How Home flows on this firmware

The accessibility key filter sees `KEYCODE_HOME` **before** `PhoneWindowManager.interceptKeyBeforeDispatching` → `TclPhoneWindowManager.handleCustomKey` → `processHome`, which starts `launcherx`'s `HomeActivity`.
- **Passthrough** lets that happen, then starts zentv as an app. A `launcherx` that has been in the background for a while can come back over it, so the re-check is needed.
- **Consume** stops the event before TCL's handler runs, so nothing races.

The trade-off with consume: whatever TCL or Google TV normally does on Home is skipped. No problem showed up in these tests (gear, Input, app buttons and HDMI all still work), but M4 should watch for overlays or dialogs that expect Home to close them.

## Decisions for M4 (proposed)

1. Ship **consume + re-check**, and keep passthrough as a build-time fallback.
2. Keep the helper in `:homekey`. Re-check at 1.2 s and 2.4 s, at most 2 re-launches, own process only.
3. On TCL, `enable-home-key` includes the rule 6 app-op, and `revert` restores it. Both verified on the real TV.
4. `launcher status` and the smoke test check that the helper is bound after a restart.

## Found along the way (not caused by the spike)

**Wi-Fi did not rejoin on its own after either restart today** (the owner reconnected by hand both times). The saved networks include a **hidden WPA2 entry owned by `setupwraith` that Wi-Fi prefers** ("connect choice"), next to the WPA3 network actually in use, plus an entry disabled for a wrong password. This is recorded as a smoke-test failure (item 8). The decision is in `devices/tcl-g03-beyondtv4/PROFILE.md`.
