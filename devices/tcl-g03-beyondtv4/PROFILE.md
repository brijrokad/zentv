# Device profile: TCL 75S450G

Source: `ZENTV_BUILD_PROMPT.md` v3, "Device profile: TCL 75S450G". **Phase 3 ran on 2026-11-26, read-only**, with `zentv identify`, `zentv survey` (redacted, [`survey.json`](survey.json)), read-only `adb` queries, a remote key log while the owner pressed buttons, and a passive Bonjour browse from the Mac. It ended with `zentv adb-close --yes` (port 5555 verified closed). Nothing on the TV was changed except switching debugging off.

**Profile status: `confirmed` at Checkpoint 4 (2026-11-26) for firmware AR10.** A different fingerprint makes zentv read-only again. Approved plan: disable `gtvpai`, `com.tcl.dashboard` and `com.tcl.ocean.instructions` (**applied 2026-11-27**, each read back). **Supervised run result:** after a restart, `zentv check` showed no drift and Wi-Fi reconnected on its own. The smoke test was first recorded as passed (8 of 9, Ethernet skipped). **Corrected 2026-11-27: item 8 FAILED.** Wi-Fi did not rejoin on its own after either restart; the owner reconnected by hand both times, and I had read the TV being back online as a pass. Likely cause: a preferred hidden WPA2 entry owned by `setupwraith` (see `docs/spikes/M3a-tcl-home-key.md`). A standby wake didn't reboot (uptime kept counting, 172 s → 599 s). The session ended with `adb-close --yes`, and port 5555 was verified closed. Undo: `zentv restore --yes` (snapshot `…-5d7c343e27a67f44`). Un-hiding `mediashell` and `katniss` turned out to be impossible over ADB on this build (line 17).

**Directory name.** The live TV reports `ro.product.device=BeyondTV4`, `ro.product.name=G03_4K_US_NF_DB`, so `tcl-g03-beyondtv4` stands.

**Serial number.** The owner has it. It is **not** stored in this repo, and `survey.json` contains no identifiers (checked for serials, IPs, MACs and emails).

**Owner answers (confirmed 2026-11-26).**
- In use: TCL remote + voice, phone remote + casting, antenna/Live TV/HDMI, and the Google Home panel. Ethernet must stay usable.
- AirPlay/HomeKit is dropped: this TV doesn't support it.
- Firmware AR10 is the latest available.
- Restore casting and voice (they're hidden; see line 17).
- `com.tcl.xian.StartandroidService` stays protected, and `com.tcl.usercenter` stays `risk: high` (it's already hidden here). The TCL Channel button isn't used.

| # | Line | Result | Evidence |
|---|---|---|---|
| 1 | Retail model TCL 75S450G | **verified (as far as the TV reports it)**: `ro.product.model=Smart TV`, the same as the siblings | `zentv identify` |
| 2 | Platform G03 / `BeyondTV4`, Realtek `rtd288o` | **verified**: `BeyondTV4`, `G03_4K_US_NF_DB`, board `RTD2851M`, platform `rtd288o` (same product as the 55S450G) | `zentv identify` |
| 3 | Google TV on Android 11 (SDK 30) | **verified**: Android 11 / SDK 30, `ro.tcl.product_type=GTV`, `launcherx` present, no `tvlauncher` | identify + survey |
| 4 | Basic TV / "Apps only" mode | **not determined**: HOME resolves to `launcherx/.home.HomeActivity`. Apps-only is a `launcherx` setting that the resolver doesn't show. | survey `home` |
| 5 | Firmware | **verified, AR10** (`TCL/G03_4K_US_NF_DB/BeyondTV4:11/RP1A.200622.001/AR10:user/release-keys`), patch 2023-03-05. The owner says it's the latest. The sibling notes describe AR24. | identify |
| 6 | ABI and RAM | **verified**: `armeabi-v7a,armeabi`, `zygote32`, MemTotal 2,097,152 kB, about 380 MB available | identify + `/proc/meminfo` |
| 7 | Network: Wi-Fi today | **verified**: active transport `WIFI`. Saved-network owners include `android.uid.system`, `com.android.tv.settings` **and `setupwraith`**. | `dumpsys connectivity`, `dumpsys wifi` |
| 8 | Ethernet must stay usable | requirement, **not checked** (no `ip link` read). All Wi-Fi/Ethernet/network-stack packages are refused. | `never_disable.yaml` |
| 9 | Tuner/antenna and HDMI in use | **verified, inputs present**: `com.tcl.tvinput` tuner (`TDTVInputService`) + 5 HDMI pass-through inputs. Also app inputs from Fubo, Sling, ZEE5. Whether channels are scanned wasn't checked. | `dumpsys tv_input` |
| 10 | TCL remote incl. voice | **partly**: remote buttons work (key log). The **mic press logged `BTRemoterRcUnConnect`**, so the remote isn't paired over Bluetooth, and `katniss` (voice) is **hidden**. Voice needs both fixed. **Owner reports the remote is now paired** (to be verified read-only next session). | key log, survey, owner |
| 11 | Google TV phone remote | **verified**: `tv.remote.service` enabled, advertised over mDNS as `_androidtvremote2._tcp` "Living Room TV" (`device_name`) | Bonjour browse, `settings get global device_name` |
| 12 | Chromecast built-in | **broken now**: `com.google.android.apps.mediashell` is **hidden** (`pm hide`, by an earlier tool). The TV doesn't advertise `_googlecast._tcp` (only a Nest Mini does). | survey `absent_for_user`, Bonjour |
| 13 | AirPlay / HomeKit | **not supported**: no package, no `_airplay`/`_hap` advert. Dropped by the owner. | survey, Bonjour |
| 14 | TCL boot manager app-op | **verified**: `APP_AUTO_START` exists (default mode **ignore**). `AUTO_START` is "Unknown operation string". So the Option B helper will need the approved rule 6 app-op. | `appops get android <op>` |
| 15 | Remote buttons | **verified**: Home, Netflix (4062/scan 758), YouTube, Prime Video (4099/scan 752), Apple TV and TCL Channel (4020/scan 456) are handled in `TclPhoneWindowManager.handleCustomKey`, called from `interceptKeyBeforeDispatching`. Apple TV and TCL Channel route through `com.tcl.partnercustomizer`. Gear opens `launcherx`'s dashboard. Input opens `com.tcl.suspension`. Held Volume ramps (`isVolumeKeyLongPress=true`). | key log |
| 16 | Google Home panel (dreamx) | **package enabled**. That it hosts the panel here is assumed from sibling notes and wasn't checked. Protected. | survey |
| 17 | (found) Starting state | **8 disabled from an ADB shell** before zentv (`lastDisabledCaller: shell`): Google feedback, onetimeinitializer, partnersetup, calendar sync, `com.tcl.bi`, `esticker`, `guard`, `waterfall.overseas`. **10 hidden by Google TV's own setup** (`lastDisabledCaller: com.google.android.tungsten.setupwraith`, some `enabled=2`): mediashell, katniss, Play Games, Movies, YouTube Music, TCL assistant, gallery, messagebox, Alexa bridge, usercenter. (Corrected 2026-11-27: these were not hidden by an ADB tool. The shell can't hide or un-hide on this build.) The owner-approved un-hide of mediashell and katniss **failed**: `pm unhide` needs `MANAGE_USERS`, which the ADB shell lacks. Casting and voice therefore stay unavailable unless restored outside zentv, by Google TV itself or by a factory reset with full Google TV setup. | survey, supervised run 2026-11-27 |
| 18 | (found) Audio over HDMI ARC | Volume goes to an ARC soundbar via HDMI-CEC. Must keep working (framework + `com.tcl.tv`, both refused). | key log (`AudioInvoke`, `hdmi_cec`) |
| 19 | (found) TGuard still runs | A process named `com.tcl.guard` (pid 1004, system user) runs the TGuard memory manager **although the `com.tcl.guard` package is disabled**. It's relevant to the M3a "what does TGuard kill" test. | `ps`, key log |
| 20 | (found) Key-press telemetry | `TclPhoneWindowManager.supportUserActionCollect` fires on each custom key. `com.tcl.suspension` reports through a "BI_SDK". `com.tcl.bi` is already disabled; `suspension` is protected (the Input panel). | key log |

## Reference data (not about this TV)

Hints from cleanyourtv at `be608705`, read as data. They cover **sibling units**, not this TV. Where Phase 3 contradicted them, the table above wins.

- **TCL 55S450G** (`examples/tcl-55s450g/`): the same product `G03_4K_US_NF_DB`, on AR24 (this TV runs AR10).
- **Same platform, other firmware:** `tcl-55s546-us` (GTV93), `tcl-g03-google-tv` (AR09/AR11). "Do not copy either list onto this build."
- **`TclAppBoot`** refused to bind an accessibility service until `appops set <pkg> APP_AUTO_START allow` + `appops write-settings`.
- **`launcherx` and the remote:** with `launcherx` disabled, the app buttons, gear and Input did nothing. zentv keeps `launcherx` enabled (rule 7).
- **Injected `KEYCODE_HOME`** isn't a valid test for the real Home button.
- **A same-platform 43P735** kept `launcherx`/`setupwraith` and took Home with a window-watching redirect + `APP_AUTO_START`. "Google TV showed briefly first" after a reboot.
- **couch-tv** (`docs/TV-COMPATIBILITY.md:151-158`): `com.tcl.guard` trims a custom home, and TCL's boot controller opens Google home before any helper runs.
