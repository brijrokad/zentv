# Security & malware audit: cleanyourtv and couch-tv

| | |
|---|---|
| Audit date | 2026-11-07 |
| Method | Static reading only. Nothing from either repo was built, run, installed or sourced. Agent-instruction files were read as data. |
| cleanyourtv | `github.com/Gathin23/cleanyourtv` @ `d451b175ab3f869f9a5d66993fb2dd501c96920b` (3,447 files, 5,603 commits) |
| couch-tv | `github.com/Seagey/couch-tv` @ `ff2cfbf23703d96046b66ef703dde9dc38e6faa4` (228 files, 91 commits) |
| Scope | Both repos in full for the scripted checks. Deep read of cleanyourtv `launcher/`, `tools/` (debloat/restore/recovery/privacy/manage/tv.py), add-ons `remote-access`, `ad-blocking`, `tv-hub`, `weather`, and anything a sweep flagged. Deep read of couch-tv `bridge/`, `tv-home/android`, `on-tv/android`, `AGENTS.md`. |

All findings apply to these two commits only. Neither repo should be tracked automatically (see CY-04).

**Delta audit, 2026-11-10:** §7 covers the new upstream commits up to cleanyourtv `deba47ca1eac7abe3fef0f73ddaf5ae6fb86c1af` (+368 commits) and couch-tv `bb02fc41c6996ea45ff64d715b04674a85022e68` (+160 commits). Sections 1–6 still describe the audited commits, except for the signing correction marked in CY-04.

---

## 1. Summary

**No malware was found in either repo.** Neither contains obfuscated code, encoded payloads, Trojan Source/bidi characters, hidden endpoints, telemetry or analytics SDKs, data exfiltration, or download-and-execute chains. Neither writes to shell rc files, LaunchAgents or cron on its own. Both repos have clean git history: no binary was ever committed and later removed, `git fsck` reports no problems, and gitleaks found no real secrets. All 28 bundled `gradle-wrapper.jar` files are byte-identical to official Gradle releases.

The two repos carry very different levels of **design risk**:

| | cleanyourtv | couch-tv |
|---|---|---|
| Verdict | **Safe with caveats** | **Safe with caveats** (learn from the design only; **do not deploy the bridge or the on-TV app as they are**) |
| Highest severity | Medium | High |
| What it changes on the TV | `pm disable-user` / `pm enable` / `set-home-activity`. Prior state is recorded and restore replays it. A hard denylist of core packages has no override. | The same disable/HOME changes, plus persistent ADB re-enablement, self-granted secure settings, accessibility self-revival, and app install/uninstall from a LAN API |
| Network exposure | Launcher has **no `INTERNET` permission**. Opt-in add-ons call only their stated APIs. | Bridge listens on `0.0.0.0:5400` with **no auth and `CORS *`**. The home page loads over cleartext HTTP into a WebView with JS bridges. |
| Main caveats | Some device lists disable OTA updaters or the remote service. PROMPT.md drives an agent against a live TV. Upstream is very high-velocity and merges are gated by an AI reviewer. | Anyone on the Wi-Fi can drive the TV, take screenshots and install apps. The on-TV app keeps wireless ADB switched on permanently. |

Severity counts:

| Repo | Critical | High | Medium | Low | Info |
|---|---|---|---|---|---|
| cleanyourtv | 0 | 0 | 6 | 6 | 5 |
| couch-tv | 0 | 2 | 7 | 4 | 4 |

---

## 2. cleanyourtv

### 2.1 What it is

The repo has three parts. The first is a Python + shell toolset (`tools/`) that talks ADB to the TV through `adb-shell`. It debloats from a per-device list with `pm disable-user --user 0`, and writes a state record to `~/.cleanyourtv/` before the first change so `restore.sh` can replay it. The second is a small native Java launcher (`launcher/`, `com.gathin.tvhome`, minSdk 26, no `INTERNET`). The third is about 35 optional add-on apps ("module cards"), each its own Gradle project. Per-device lists live in `examples/` (456 devices, 10,495 active entries).

### 2.2 Network endpoints

| Endpoint | Where | Data sent | Notes |
|---|---|---|---|
| *(none)* | `launcher/` | – | No `INTERNET` permission (`launcher/app/src/main/AndroidManifest.xml:10-23`). |
| `api.open-meteo.com`, `geocoding-api.open-meteo.com`, `air-quality-api.open-meteo.com` | `addons/weather/.../Forecast.java:97,125,181` | City name or lat/lon | Opt-in add-on |
| `api.aladhan.com` | `addons/prayer-times/.../MainActivity.java:135`, `PrayerScheduler.java:231` | Date, location | Opt-in add-on |
| `api.jolpi.ca` | `tools/race_calendar.py:37` | Season year | Run by hand on the computer |
| `upload.wikimedia.org` | `themes/diwali/prepare_wallpapers.py:21` | – | Theme asset prep, by hand |
| User-configured LAN hosts (Pi-hole/AdGuard, Home Assistant, Frigate, M3U/XMLTV/HDHomeRun) | `addons/ad-blocking`, `smart-home`, `frigate-glance`, `tv-hub` | Credentials/tokens the user enters | `frigate-glance` and `tv-hub` set `usesCleartextTraffic="true"` |
| User-configured RSS feeds | `addons/news-screensaver/feeds.example.txt` | – | Example feeds only (DR, BBC…) |
| `cleanyour.tv` | `tools/tv.py:357`, `tools/gen_tables.py:54` | – | Printed help links only. Nothing is fetched. |

### 2.3 ADB commands

| Class | Commands | Where |
|---|---|---|
| Read-only | `getprop`, `pm list packages [-d/-s/--user 0]`, `dumpsys package/activity/wifi/usb/connectivity`, `cmd package resolve-activity/query-activities/query-services`, `settings get`, `appops get`, `screencap`, `logcat`, `wm size/density` | `tools/*`, `privacy.py` is entirely read-only |
| Reversible, recorded by `recovery.py` | `pm disable-user --user 0`, `pm enable`, `cmd package set-home-activity`, `settings put global *_animation_scale` | `tools/disable.sh`, `tools/recovery.py`, `tools/check.py` |
| Reversible, **not** in the recovery record | `pm grant` (launcher `ACCESS_FINE_LOCATION`, `WRITE_SECURE_SETTINGS`; add-on `BLUETOOTH_CONNECT`), `settings put secure enabled_accessibility_services` (sleep-timer, launcher key helpers), `cmd notification allow_listener`, `settings put secure screensaver_components` (add-ons keep their own "before" file), `cmd appops set` (headphones `APP_AUTO_START`), optional Private DNS | `launcher/build-and-install.sh:154,249`, `addons/*/install.sh`, `addons/sleep-timer/build-and-install.sh:23`, PROMPT.md |
| Reversible, list-header undo only | `pm hide`/`unhide`, `pm suspend`, `appops set … RECORD_AUDIO ignore` | Individual `examples/*/debloat.txt` comments |
| Destructive or irreversible | `pm uninstall` of **its own** add-on/launcher packages (reinstallable) | `tools/manage.py:537` (regex-validated id), `addons/{photo-screensaver,tv-static,news-screensaver,wake-app}/build-and-install.sh`, `addons/startup-branding/install.sh:17` |
| Destructive, docs only (not scripted) | `pm clear` (wipes app data), `cmd wifi forget-network`, `setprop persist.*` home overrides, setting `verifier_verify_adb_installs`/`package_verifier_enable` to 0 | `docs/devices/xiaomi-mitv-ansp0-jobs.txt:111-114`, several `examples/*` comments, `docs/devices/skyworth-7t861-a23.md:126-164`, `docs/devices/sdmc-whaletv-smart4ktvplus.md:25` |
| **Not found anywhere** | `dpm set-device-owner`, `pm uninstall` of a system package in any list (enforced by `tests/test_list_folders_ship_lists_only.py`), disabling Play Protect, `WRITE_SECURE_SETTINGS` granted to a third party | – |

**Restore path.** `disable.sh` writes `~/.cleanyourtv/recovery-<tv>-<digest>.json` before the first change (`tools/recovery.py:1-30,153`). The first record wins, so a half-applied retry can't overwrite the original state. The record holds each listed package's prior state, each stock launcher's state, the HOME component and the animation scales. `restore.sh` replays exactly that. Packages the owner had already disabled stay disabled. It does **not** cover grants, appops, accessibility, notification listeners, Private DNS or `pm clear`/`forget-network` steps (CY-09).

**Safety guards (worth copying as concepts).**
- A hard denylist of core packages with no override: permission controller, package installer, ext services, module metadata, `com.android.providers.*`, systemui, shell, phone, settings, tv.settings and `android` (`AGENTS.md:25-31`).
- A HOME guard: the stock launcher is only disabled once a replacement answers HOME.
- A setupwraith Wi-Fi ownership check.
- `PACKAGE_RE` validation on every name that reaches the TV shell (`tools/recovery.py:41`, `tools/privacy.py:36`, `tools/manage.py:113`).

### 2.4 Device-list sweep (`examples/`, 456 lists)

Every active entry was matched against a critical-package denylist. Script: `critical_sweep.py`, see the appendix.

| Category | Lists | Notable entries |
|---|---|---|
| Package installer / verifier / Play Store | **0** | – |
| GMS core / GSF / Play Protect | **0** | – |
| Permission controller, settings, android core | **0** | – |
| OTA / system update | **13** | `com.mediatek.tv.systemupdater` (skyworth-swtv-24ae-4k-nf:86, xiaomi-tv-a-pro-2026:49), `com.hisense.tv.ota`, `com.apps.ota`, `com.amazon.device.software.ota(.override)` (insignia-ns55f301na25:130-131), `com.droidlogic.updater`, `com.realsil.ota`. Also BLE-remote OTA `com.airoha.ble.ota` and `com.xgimi.ota.accessories`. |
| Remote pairing | 31 | `com.google.android.tv.remote.service` in 23 lists, **3 of them Sony**: sony-bravia-4k-gb-us, sony-xbr-x900e, sony-xbr-65x900f |
| Setup wizard | 163 | `com.google.android.tungsten.setupwraith` in 158 lists (18 Sony). Guarded by the Wi-Fi ownership check. |
| TV input / tuner | 11 | sony-bravia-ae2:61-68 disables ATSC/ATSC 3.0 tuner inputs and `servicemode.tuner`. Only fine if no antenna is used. `itunerfree` is a radio app the sweep matched by mistake. |
| Input methods | 13 | Language IMEs (Japanese ×9, incl. 2 Sony). Leanback IME is untouched. |
| Content providers | 38 | Only calendar/contacts/userdictionary/blockednumber, which the repo's own allowlist permits |
| Mainline | 3 | `com.google.android.adservices.api` (Privacy Sandbox). Low risk, privacy-positive. |
| WebView | 33 | Vendor WebViews (TCL, MediaTek, Seraphic), not `com.google.android.webview` |

### 2.5 Android apps (manifests)

| App | Notable permissions | Flags / exported without permission |
|---|---|---|
| **launcher** | `ACCESS_FINE_LOCATION` (Wi-Fi SSID pill), `WRITE_SECURE_SETTINGS`, `ACCESS_WIFI_STATE`, `yandex.tv.permission.ACCESS_TV_SOURCE`. **No `INTERNET`.** | Accessibility key filter (`HomeKeyService`, no window content), notification-listener keep-alive (`GuardRevival`, reads no notifications), `allowBackup=false` |
| ad-blocking, smart-home | `INTERNET` | `networkSecurityConfig` set |
| frigate-glance | `INTERNET`, `SYSTEM_ALERT_WINDOW`, `RECEIVE_BOOT_COMPLETED`, FGS | `usesCleartextTraffic=true`, accessibility key filter, `BootReceiver` |
| tv-hub | `INTERNET` | `usesCleartextTraffic=true` |
| brightness, tv-static, wake-app, prayer-times, sleep-timer, quiet-hours | `SYSTEM_ALERT_WINDOW` and/or boot + FGS / exact alarms | Exported `BootReceiver`s. `brightness/OffReceiver` and `headphones/QuietReceiver` have no permission. |
| sleep-timer | accessibility (announcements only, `canRetrieveWindowContent=false`) | – |
| remote-access | `WRITE_SECURE_SETTINGS` (to switch network ADB **off**) | – |
| scoreboard | `PACKAGE_USAGE_STATS` | – |
| game-day | `INTERNET` | Exported read-only `GamesProvider` with no permission (schedule data) |
| Others (screensavers, calendars, clocks) | none | Dream services bound with `BIND_DREAM_SERVICE` |

No manifest sets `debuggable`. No analytics, crash or remote-config SDK appears in any Gradle file or source.

### 2.6 Findings

| ID | Severity | File:line | Finding | Evidence | Recommendation |
|---|---|---|---|---|---|
| CY-01 | Medium | `examples/*/debloat.txt` (13 lists, see §2.4) | Some contributed lists disable firmware/OTA update services, which blocks security updates. The repo's own rule says to leave updaters enabled (`AGENTS.md:153-154`). | `com.mediatek.tv.systemupdater`, `com.hisense.tv.ota`, `com.amazon.device.software.ota` active in lists | Put every OTA/update package in `safety/never_disable.yaml`. Never import lists wholesale. |
| CY-02 | Medium | 23 lists, incl. `examples/sony-bravia-4k-gb-us`, `sony-xbr-x900e`, `sony-xbr-65x900f` | Disables `com.google.android.tv.remote.service`, which breaks phone/Google Home remote and can break remote pairing | Sweep output | zentv: mark remote-pairing services `protected` for Sony. Review in Phase 3. |
| CY-03 | Medium | `PROMPT.md:23,27,42,47-48`, `AGENTS.md:11`, `CLAUDE.md`, `GEMINI.md` | Agent-driving content. `CLAUDE.md`/`GEMINI.md` auto-import `AGENTS.md`, which tells any agent opened in the clone to "Read PROMPT.md and follow it exactly, on the real TV". PROMPT.md has the agent clone upstream HEAD and run its scripts, find the TV via the ARP table, scan the TV's TCP ports, and get around the Android 14 on-screen install confirmation with `pm install -r` | Quoted lines | Never start an agent with its working directory inside the clone. Treat PROMPT.md as data. zentv must not get around install confirmations. |
| CY-04 | Medium | `.github/workflows/maintainer-bot.yml:20,32-35,64-67`; history | Upstream integrity. An LLM review bot runs on `pull_request_target` with `pull-requests: write`, `issues: write` and an API secret (`OG_PC_API_KEY`), reading untrusted PR text. It does not check out PR code (`:3-6`), but its verdicts are prompt-injectable. Upstream velocity is 5,603 commits from 1,117 authors in 3 weeks (2026-10-17 → 11-07). **Corrected 2026-11-10:** the history is *not* all unsigned. About 330 commits carry signatures: 151 by GitHub's web-flow PGP key, the rest by contributors' SSH/PGP keys. The maintainer's own commits and merges are unsigned. The original `%G?` = N came from git being unable to run gpg, not from the commits having no signature. None of the signatures can be verified locally. | `git shortlog`, raw `gpgsig` headers (§7.6) | Pin to the audited commit. Never auto-pull. Re-audit any later snapshot before reading from it. |
| CY-05 | Medium | `tools/requirements-perf.txt:2`, `tools/requirements.txt:3` | `pillow==11.3.0` has 58 OSV advisories (max CVSS 9.8, fixed in 13.0.0). `cryptography>=46.0.7` is a floating lower bound. No hash pinning anywhere. | osv-scanner 2.7.0 | Don't install these. zentv uses `uv.lock` with hashes. |
| CY-06 | Medium | `docs/devices/sdmc-whaletv-smart4ktvplus.md:25` | A device note records setting `verifier_verify_adb_installs` and `package_verifier_enable` to 0 (and disabling the vendor installer) as an attempted workaround. There is no undo. | Quoted line | zentv must refuse these keys outright (prompt ground rule 5). |
| CY-07 | Low | `launcher/app/src/main/AndroidManifest.xml:15-19`; `launcher/build-and-install.sh:154,249` | The launcher holds more than a minimal launcher needs: `ACCESS_FINE_LOCATION` (only to show the SSID), `WRITE_SECURE_SETTINGS`, an accessibility key filter and a notification listener. None reads window content or notifications. | Manifest + `GuardRevival.java` | zentv launcher: drop location (show "Wi-Fi" or use `ACCESS_WIFI_STATE` where allowed). Justify each permission. |
| CY-08 | Low | `addons/frigate-glance`, `addons/tv-hub` manifests | `usesCleartextTraffic=true` for LAN services (Frigate, M3U/HDHomeRun) | Manifest flags | Scope any cleartext to a `networkSecurityConfig` LAN allowlist |
| CY-09 | Low | `tools/recovery.py:1-30` | The restore record covers package state, HOME and animation scales only. Grants, appops, accessibility, notification listener, Private DNS and screensaver settings are outside it. | Code reading | zentv snapshots must include every `settings`/grant/appops value a command touches |
| CY-10 | Low | `tools/tv.py:182-219`, `.gitignore:2` | Generates an ADB private key **inside the repo** at `tools/adbkey/` (0600/0700, gitignored). It also reuses `~/.android/adbkey`. | Code | zentv keeps keys outside the repo only (`~/.android` or `~/.zentv`) |
| CY-11 | Low | `addons/{brightness,headphones,lich-van-nien}` manifests | Exported receivers with no permission (`OffReceiver`, `QuietReceiver`, `DayReceiver`). Any app can toggle them. | Manifest parse | Use `exported=false` or a signature permission in zentv |
| CY-12 | Low | `addons/*/build-and-install.sh`, `tools/manage.py:537` | `pm uninstall` of the repo's own add-on packages. Reinstallable, but it contradicts "disable, never uninstall". | Grep | zentv `launcher revert` disables/re-homes. It never uninstalls system apps. |
| CY-13 | Info | `addons/tv-hub/gradle/wrapper/gradle-wrapper.properties:3` | Declares Gradle 8.11.1 but ships the **8.9** wrapper jar (official hash). 8 add-on projects ship no wrapper jar at all. | §4 hash table | Cosmetic. zentv pins its own wrapper. |
| CY-14 | Info | `.../res/font/outfit.ttf` | Two different Outfit builds: `prayer-times` differs from `launcher` and `photo-prints`. Magic bytes are valid and nothing is appended. | §4 | Manual check against Google Fonts (see §5) |
| CY-15 | Info | `examples/xgimi-{vibe-one:34,mogo-4:62,mogo-3-pro:45}/debloat.txt` | 3 gitleaks `generic-api-key` hits, all false positives (comment text "remote keys") | gitleaks 8.30.1 | None |
| CY-16 | Info | `addons/tv-hub` (`org.jetbrains.kotlin.android` 2.0.21) | Kotlin Gradle plugin CVE-2026-53914 (build-cache deserialization, local, high privileges, fixed in 2.4.20) | OSV API | Build-time only. zentv uses a current Kotlin. |
| CY-17 | Info | `tools/*` | Core debloat path issues only `pm disable-user` / `pm enable` / `set-home-activity` plus reads, with shell-injection guards. **This is the safest model in either repo.** | §2.3 | Reimplement the concept: record → preview → apply → replay |

**Verdict: Safe with caveats.** It's safe to learn from, and the debloat/restore design and the no-network launcher are a good base. Caveats: review every device-list entry yourself (CY-01, CY-02), never run an agent inside the clone (CY-03), treat the upstream as a moving target (CY-04), and don't install its Python requirements (CY-05).

---

## 3. couch-tv

### 3.1 What it is

The project offers three ways to run it.
- **A.** A WebView-based TV home app (`tv-home/android`, `app.couchtv.launcher`) that shows an HTML/JS home (`tv-home/web`) with scenes, clock, weather, app row and "keep watching".
- **B.** The same home plus an always-on **Python aiohttp bridge** on a computer (`bridge/`). The bridge drives the TV over ADB, serves the phone remote (`remote/`) and the home page, and optionally runs `claude -p` with an MCP "tv" toolset to act on natural-language requests.
- **C.** An **on-TV app** (`on-tv/android`, `dev.couchtv.ontv`) that embeds the bridge's role. It runs an HTTP server on the TV and **connects to the TV's own ADB** (libadb-android) to press keys, type and read what's playing.

Releases are APKs on GitHub that the home's built-in updater can install.

### 3.2 Network endpoints

| Endpoint | Where | Data sent | Notes |
|---|---|---|---|
| **Bridge listens on `0.0.0.0:5400`** | `bridge/server.py:1989` (`BIND_HOST` default), `env.example:5` | Serves the full API + remote + home page to the LAN | **No auth**, `Access-Control-Allow-Origin: *` (`server.py:182-184`) |
| **On-TV server**, NanoHTTPD on all interfaces | `on-tv/.../Server.kt:22`, `App.kt:157` | API + remote + home | PIN-paired bearer token (`Auth.kt`). Plain HTTP. |
| `api.github.com/repos/<repo>/releases/latest`, `github.com`, `*.githubusercontent.com` | `tv-home/.../Updater.kt:161,171,286` | Version via User-Agent | Opt-in weekly check or manual. Downloads APK. |
| `apis.justwatch.com/graphql`, `images.justwatch.com` | `bridge/finder.py:15-17`, `on-tv/.../Finder.kt:15,49` | Titles searched, country | Unofficial API |
| `api.open-meteo.com`, `geocoding-api.open-meteo.com` | `bridge/server.py:1052`, `tv-home/web/app.js:628,1679`, `on-tv/.../Weather.kt:23` | lat/lon, place name | – |
| `api.anthropic.com/v1/messages` | `on-tv/.../Ask.kt:22` | User question, TV context, **user's API key** | Option C, opt-in, key stored in app prefs |
| `claude -p` subprocess (Claude plan) | `bridge/claude.py:123-140` | Question, watch history, taste profile | Option B. `ANTHROPIC_API_KEY` stripped (`:116`). |
| Home Assistant (user-configured) | `tv-home/.../HomeAssistant.kt` | Long-lived token (kept in the app, never given to the page) | Allowlisted entities and actions only |
| TV vendor APIs (LG webOS, Samsung Tizen SOAP/WS, Android TV Remote v2) | `bridge/lg.py`, `bridge/samsung.py`, `androidtvremote2` | Keys, deep links | LAN |
| `jitpack.io` (build time) | `on-tv/android/settings.gradle.kts:9` | – | Dependency repository for `libadb-android` |

### 3.3 ADB commands

| Class | Commands | Where |
|---|---|---|
| Read-only | `pm list packages [-d/-s]`, `dumpsys`, `settings get`, `cmd package resolve-activity/query-activities`, `screencap`, `uiautomator`-style UI read | `bridge/tv.py`, `bridge/agentic.py`, `scripts/check-tv.py`, `on-tv/.../Tv.kt:218` |
| Reversible | `pm disable-user --user 0` (Google home, ambient, setupwraith, trackers), `pm enable`, `cmd package set-home-activity`, `am start`/`force-stop`, `input keyevent/text` | `tv-home/tools/apply.sh`, `bridge/server.py:1885` |
| **Silent / persistent** | `appops set <self> SYSTEM_ALERT_WINDOW allow` and `pm grant <self> WRITE_SECURE_SETTINGS` **on first ADB connect** (`on-tv/.../Adb.kt:244-249`). **Re-enabling `adb_enabled` and `adb_wifi_enabled` after every reboot** (`Adb.kt:255-266`). Re-enabling its own accessibility service (`tv-home/.../FireWatch.kt:48-61`). **Daily re-disable** of a package list (`bridge/server.py:1865-1890`). | – |
| Install / uninstall | `pm install` (release APKs), **`pm uninstall <user app>` from the LAN API** (`bridge/agentic.py:320`, routes `:826-827`), `pm uninstall` of its own apps (`tv-home/tools/remove-all.sh:56`) | System packages and the home app are refused (`agentic.py:307-316`). Package names are regex-validated (`:183`). |
| Settings | `settings put global adb_wifi_enabled 1` (`on-tv/scripts/real-tv.py:118`), `… 0` + `development_settings_enabled 0` + `adb_enabled 0` on uninstall (`tv-home/tools/remove-all.sh:69`), `enabled_accessibility_services` | – |
| **Not found** | `dpm set-device-owner`, verifier/Play Protect changes, uninstall of system packages | – |

**Restore path.** `docs/UNINSTALL.md` and `tv-home/tools/remove-all.sh` re-enable what `apply.sh` disabled, uninstall couch-tv's own apps and switch ADB/developer options off. Prior state is not snapshotted per setting (it re-enables a fixed list). Two persistence mechanisms work against undo while couch-tv is still installed: the bridge's daily `keep_disabled_loop` and the on-TV app's ADB re-enablement.

### 3.4 Android apps (manifests)

| App | Permissions | Flags / components |
|---|---|---|
| **tv-home** (`app.couchtv.launcher`) | `INTERNET`, `REQUEST_INSTALL_PACKAGES`, `REQUEST_DELETE_PACKAGES`, `SYSTEM_ALERT_WINDOW`, `WRITE_SECURE_SETTINGS`, `RECEIVE_BOOT_COMPLETED`, `READ_TV_LISTINGS` | `usesCleartextTraffic=true`. HOME + LEANBACK. Two accessibility services (key filter, window-state). WebView with `addJavascriptInterface` ×3 (`TVOS`, `TVHA`, `TVUP`; `MainActivity.kt:269-271`). Exported `FireWatch$Restore` receiver with no permission. |
| **on-tv** (`dev.couchtv.ontv`) | `INTERNET`, `QUERY_ALL_PACKAGES`, `PACKAGE_USAGE_STATS`, `SYSTEM_ALERT_WINDOW`, `WRITE_SECURE_SETTINGS`, `RECEIVE_BOOT_COMPLETED`, `CHANGE_WIFI_MULTICAST_STATE`, FGS | `usesCleartextTraffic=true`. HOME alias. Accessibility (window-state). WebView `TVOS` bridge. Embedded ADB client + RSA/TLS keys. HTTP server. |

No analytics, crash or remote-config SDKs. No `debuggable`.

### 3.5 Services and LAN exposure

**Can someone else on your Wi-Fi control the TV?**
- **Option B (bridge): yes, fully.** Every `/api/*` route is unauthenticated: keys, text, launch, play, `/api/ask` (drives Claude on the owner's plan), `/api/install`, `/api/uninstall`, `/api/screenshot`, `/api/ui`, `/api/import`, `/api/settings`, `/api/people`, `/api/power`. The README says so itself (`README.md:481`). With `CORS *`, any web page open in a browser on the LAN can call it too, if it knows or guesses the bridge's IP.
- **Option C (on-TV app): not without the PIN.** A 6-digit code shown on the TV lasts 3 minutes and dies after 5 wrong tries. A successful pairing returns a 256-bit SecureRandom token, stored only as a SHA-256 hash and compared in constant time (`Auth.kt`). Residual risks: traffic is plain HTTP (the token can be sniffed on the LAN), the token is also accepted as a `?token=` URL parameter (`Server.kt:59`), the Anthropic key is typed into a page served over HTTP, and wireless ADB stays on permanently (CT-02).
- **LLM key handling.** Option B never uses an API key (`claude -p`, key stripped, `--tools ""`, `--strict-mcp-config`, only `mcp__tv`, isolated workdir, `bridge/claude.py:114-140`). Option C stores the user's key in app-private SharedPreferences and sends it only to `api.anthropic.com` over HTTPS (`Ask.kt:22-46`).

### 3.6 Findings

| ID | Severity | File:line | Finding | Evidence | Recommendation |
|---|---|---|---|---|---|
| CT-01 | **High** | `bridge/server.py:1989`, `:153-185`, `:1914-1960`; `bridge/agentic.py:820-834`; `README.md:481` | The bridge binds `0.0.0.0:5400` with **no authentication** and `Access-Control-Allow-Origin: *`. Any LAN device, or a malicious web page in a LAN browser, can inject keys and text, take screenshots, install or uninstall apps and drive the Claude agent. | Route table + middleware | zentv Phase 6: bind to localhost by default, require a pairing token on every route, no wildcard CORS |
| CT-02 | **High** | `on-tv/.../Adb.kt:244-249`, `:252-266` | On first ADB connection the on-TV app quietly grants itself `SYSTEM_ALERT_WINDOW` and `WRITE_SECURE_SETTINGS`. It then switches **`adb_enabled` and `adb_wifi_enabled` back on after every reboot**, so the TV's network ADB is permanently open. The app also holds an ADB key, so compromising the app means a shell on the TV. | Code | zentv must never keep ADB on. Close-ADB-afterwards is a goal (see cleanyourtv `tools/adb-closed.py`). |
| CT-03 | Medium | `tv-home/.../MainActivity.kt:252,264-271`; `Updater.kt:438-443`; `HomeAssistant.kt:270-275`; manifest `usesCleartextTraffic` | The home page loads over **cleartext HTTP** from the LAN bridge into a WebView exposing `TVOS` (list/launch apps, read Watch Next, uninstall dialog), `TVHA` (scenes/climate) and `TVUP` (update check/install). "Trust" is a URL-prefix match on the bridge's `http://` URL, so a LAN MITM or a compromised bridge host gets these JS powers. Updater installs still require GitHub, a matching signature and on-screen confirmation. | Code | zentv launcher: native UI, no WebView JS bridges, no cleartext |
| CT-04 | Medium | `tv-home/.../Updater.kt:150-192,316-331`; `.github/workflows/build.yml` | Self-updater (`REQUEST_INSTALL_PACKAGES`) installs `couch-tv-home.apk` from GitHub Releases. The APK's SHA-256 comes from the same GitHub API response (single trust root). Releases are **built off-CI** (no release workflow), so they can't be reproduced from source. Mitigations: opt-in, host allowlist per redirect hop, same-package/higher-versionCode/same-signer checks, Android installer prompt. | Code | No self-update in zentv. Users build or install by hand. |
| CT-05 | Medium | `tv-home/.../FireWatch.kt:40-61` | Using `WRITE_SECURE_SETTINGS`, re-adds its own accessibility service to `enabled_accessibility_services` whenever the user removed it. An exported receiver with no permission (`FireWatch$Restore`) triggers this. Fire TV only. Persistence of the kind normally seen in malware, used here for a feature. | Code | Never re-enable anything the user turned off |
| CT-06 | Medium | `bridge/server.py:1865-1890` | `keep_disabled_loop` re-runs `pm disable-user` daily on a package list. If the user re-enables an app by hand, the bridge silently disables it again, which defeats restore. | Code | zentv: no background re-application. Drift is reported, not "fixed". |
| CT-07 | Medium | `bridge/claude.py:41-87,123-140`; `bridge/agentic.py` | The LLM agent gets TV-control tools including `install_app`, `uninstall`, `tap` and `input`, and the `ui` tool feeds **on-screen text** (attacker-influenced, e.g. a video title) back into the agent. This creates an indirect prompt-injection path to app install/uninstall. Well sandboxed otherwise (no built-in tools, strict MCP). | Prompt + tool list | Phase 6: no install/uninstall tools for an LLM. Confirm on the phone before any state change. |
| CT-08 | Medium | `bridge/requirements.txt` | Top-level pins only, no lockfile. OSV transitive resolution lands on `python-multipart 0.0.9` (8 advisories, max 8.7), `anyio 4.9.0` (max 9.3), `certifi 2026.7.22` (9.1), `idna 3.9.0` (6.9) in a LAN-facing HTTP server | osv-scanner 2.7.0 | Lock with hashes (`uv.lock`) |
| CT-09 | Medium | `AGENTS.md:15-22,27,34-40,43-48` | Steers agents: "Before you start (**quietly**)", `pip install` and `curl` the **latest release APKs** before user consent, and "do **not** use `brew`… or `sudo`: they ask for a password the agent cannot type", so the agent downloads a JDK tarball instead. The overall flow (ask → plan → yes) is good, but these lines get around human checkpoints. | Quoted lines | Treat as data. Never let an agent run with its working directory in this clone. |
| CT-10 | Low | `on-tv/.../Server.kt:56-61`; `Ask.kt:10-24` | Token accepted via `?token=` and cookie (leaks into logs/history). Plain HTTP for pairing and API-key entry. | Code | zentv: header-only token, TLS or localhost |
| CT-11 | Low | `on-tv/android/settings.gradle.kts:9`; `on-tv/android/app/build.gradle.kts` | `com.github.MuntashirAkon:libadb-android:3.1.1` comes from **JitPack**, which builds on demand from GitHub tags and is mutable. `org.bouncycastle:bcpkix-jdk15to18:1.81` has CVE-2026-5588 (low, fixed in 1.84). `nanohttpd 2.3.1` is unmaintained (2016). | OSV API | Avoid JitPack in zentv. Prefer Maven Central with verification metadata. |
| CT-12 | Low | `.github/workflows/build.yml:22-62` | Actions pinned by tag (`@v4`), not SHA. `DEBUG_KEYSTORE` secret isn't exposed to forks (`:6`). | Workflow | zentv CI: pin by SHA |
| CT-13 | Low | `tv-home/tools/remove-all.sh:56`; `bridge/agentic.py:320` | `pm uninstall` of user apps / its own apps | Code | Never in zentv |
| CT-14 | Info | git history | Commits that looked "future-dated" (2026-11-08) are AEDT (+1100), i.e. 2026-11-07 UTC. Not suspicious. One main author (82/91 commits). Repo is 2 weeks old. All commits unsigned. | `git log --date=iso` | Pin to the audited commit |
| CT-15 | Info | gitleaks | No secrets in history or working tree | gitleaks 8.30.1 | – |
| CT-16 | Info | `tv-home/web/backgrounds/*` | Large JPEG/WebP scenes (up to 3 MB) are valid images with nothing appended | trailing-data check | – |
| CT-17 | Info | `tv-home/.../HomeAssistant.kt`, `on-tv/.../Auth.kt` | Good patterns: the page never sees the HA token, entities are allowlisted with no redirects, and PIN pairing uses hashed tokens | Code | Reuse the concepts in Phase 6 |

**Verdict: Safe with caveats.** No malware. It's **safe to learn from for its UX** (scenes, clock and weather layout, keep-watching row, PIN pairing, the HA allowlist pattern). **Do not deploy its bridge (option B) or on-TV app (option C) as they are:** the bridge is an unauthenticated LAN remote with install, uninstall and screenshot powers (CT-01), and the on-TV app keeps wireless ADB open permanently (CT-02). Don't use its release APKs or self-updater (CT-04).

---

## 4. Binaries and SHA-256

433 non-text files in total: 28 `gradle-wrapper.jar`, 3 TTF, 2 WOFF2, 271 JPEG, 117 PNG, 12 WebP. There are **no** APK, AAR, DEX, `.so`, executables or archives besides the wrapper jars. Every image and font has valid magic bytes and **nothing appended** after the end-of-file marker. The full per-file manifest is in [`binaries-sha256.txt`](binaries-sha256.txt).

### Gradle wrappers (verified against `https://services.gradle.org/distributions/gradle-<v>-wrapper.jar.sha256`)

| SHA-256 | Official for | Files | Result |
|---|---|---|---|
| `498495120a03b9a6ab5d155f5de3c8f0d986a449153702fb80fc80e134484f17` | Gradle 8.9 wrapper | cleanyourtv `launcher/` + 26 add-ons (incl. `tv-hub`, which declares 8.11.1, CY-13) | **MATCH** |
| `2db75c40782f5e8ba1fc278a5574bab070adccb2d21ca5a6e5ed840888448046` | Gradle 8.11.1 wrapper | couch-tv `tv-home/android` | **MATCH** |

Every `gradle-wrapper.properties` points at `https://services.gradle.org` and sets `distributionSha256Sum`. The 26 projects on 8.9 use `d725d707…cecab` and the 2 on 8.11.1 use `f397b287…151c6`, all equal to the official `-bin.zip.sha256`. These projects ship no wrapper jar: cleanyourtv `wake-app`, `flock`, `sleep-timer`, `capacity-stats`, `news-screensaver`, `tv-inspector`, `tv-static`, `photo-screensaver`, and couch-tv `on-tv/android`.

### Fonts

| SHA-256 | File(s) |
|---|---|
| `fc7287273e66929776e2ba54f144fe699080bec29f61bf649d70d871468aeade` | cleanyourtv `launcher/…/font/outfit.ttf`, `addons/photo-prints/…/outfit.ttf` |
| `80067c50530d6d1a42f7755d585c75f6e017328fd75a2a7463d99a3ea29e8e4c` | cleanyourtv `addons/prayer-times/…/outfit.ttf` (different build, CY-14) |
| `64218306606f079637bd2185f8d9ae9c4d4033df1fe35194c9b82494df27819d` | couch-tv `tv-home/web/fonts/antonio-latin-300.woff2` |
| `f052ee44c3728dfd23aba8a4567150bc314d23903026fbb6ad089422c2df56af` | couch-tv `tv-home/web/fonts/inter-latin-wght-normal.woff2` |

### Dependencies

| Ecosystem | Repo | Result |
|---|---|---|
| npm (`couch-tv/remote/package-lock.json`, v3, 44 pkgs) | couch-tv | No known vulnerabilities |
| PyPI `bridge/requirements.txt` (6 top-level, unlocked) | couch-tv | Transitive: python-multipart 0.0.9, anyio 4.9.0, certifi 2026.7.22, idna 3.9.0 (CT-08) |
| PyPI `tools/requirements.txt` | cleanyourtv | `adb-shell==0.4.4`, `rsa==4.9.1`: none known. `cryptography>=46.0.7` floats. |
| PyPI `tools/requirements-perf.txt` | cleanyourtv | `pillow==11.3.0`: 58 advisories (CY-05) |
| PyPI `tools/requirements-photos.txt` | cleanyourtv | `pillow==13.0.0`, `pillow-heif==1.8.1`: none known |
| Maven (OSV API, 22 coordinates) | both | `bcpkix-jdk15to18:1.81` → CVE-2026-5588 (low). `kotlin-gradle-plugin:2.0.21` → CVE-2026-53914 (build-time). AGP 8.5.2/8.7.3, media3 1.4.1, recyclerview, nanohttpd, libadb-android, junit, org.json, kxml2: none known. No dynamic (`+`) versions. |

---

## 5. Manual verification checklist

1. **VirusTotal**: look up the 2 wrapper-jar hashes and 4 font hashes in §4. The wrapper jars already match Gradle's published hashes, so VirusTotal is a second opinion only. Optionally check the 7 largest couch-tv background JPEGs as well. Their hashes are in `binaries-sha256.txt`.
2. **Outfit font**: compare the two `outfit.ttf` hashes with the files from Google Fonts or the upstream Outfit release. Make sure you know which build zentv would ship, if any.
3. **Upstream state**: a fresh clone's reflog can't show force-pushes. On GitHub, check each repo's activity view for force-pushes or deleted tags around the audited commits (`d451b175`, `ff2cfbf`). Also confirm the clones' HEADs match `origin/main` at those SHAs.
4. **Maintainer identity (optional)**: cleanyourtv's main author commits as two identities (`gathint23@gmail.com`, `gathin@0g.ai`), and the repo runs a third-party LLM bot (`Gathin23/maintainer-bot@dc295e24`). Decide whether that matters to you before borrowing anything beyond concepts.
5. **Sony lists**: before Phase 3, read `examples/sony-*` entries for `com.google.android.tv.remote.service`, setupwraith and the tuner inputs. The device audit will compare them with your TV's real package list.
6. **Re-audit on update**: if you ever `git pull` either clone, these results no longer apply.

---

## 6. What zentv takes from this audit

- **Copy as concepts:** record-before-change with first-record-wins, replay restore, a hard core-package denylist with no override, the HOME guard (replacement answers HOME before the stock launcher is disabled), the setupwraith Wi-Fi check, a package-name regex on everything sent to the shell, a no-network launcher, and closing ADB afterwards with a verification step.
- **Avoid:** unauthenticated LAN services, wildcard CORS, WebView JS bridges over cleartext, self-updaters, persistent ADB re-enablement, self-granted secure settings, re-enabling things the user turned off, background re-disabling, `pm uninstall`, verifier changes, JitPack, unpinned or unlocked dependencies, and any LLM tool that can install or uninstall.
- **Denylist seeds for `safety/never_disable.yaml`:** cleanyourtv's core list (§2.3), plus every OTA/system-update package (CY-01), remote-pairing services (CY-02), TV input/tuner/HDMI-CEC services, Play Store, GMS/GSF and the package verifier. **§7.8 adds to this list** (stock Google TV homes, setupwraith, Sony system and TV packages, and dynamic rules).

---

## 7. Delta audit (2026-11-10)

### 7.1 Scope and clone state

| | cleanyourtv | couch-tv |
|---|---|---|
| Audited → new | `d451b175` → `deba47ca` (2026-11-10 19:30 +0530) | `ff2cfbf` → `bb02fc41` (2026-11-11 11:44 +1100) |
| New commits | 368 (166 merges) | 160 (51 merges) |
| Diff | 336 files, +19,457 / −974. No deletions of files. | 210 files, +18,437 / −716. No deletions of files. |
| History | Fast-forward from the audited commit (no rewrite) | Fast-forward from the audited commit (no rewrite) |

**Clone state.** Both clones were found **on `main` at the new tips**, not on the audited commits. The reflog shows `pull: Fast-forward` at 2026-11-10 22:44 (cleanyourtv) and 22:43 (couch-tv), and no checkout afterwards. I made no checkout or fetch and left the working trees as they were. All reading went through git objects (`diff`, `show`, `log`, `cat-file`) and through `git archive` extracts in a scratch directory outside the repos.

**Method.** Phase 0's scripts were re-run on the old and new trees and the results diffed: the binary/appended-data check, the manifest parser and the device-list sweep. Phase 0's pattern scans were re-run over **added lines only**. gitleaks was run on the new commit ranges only. osv-scanner was run on new lockfiles only. Deep reads covered cleanyourtv `tools/`, `launcher/`, `examples/sony-*` and the agent files, plus everything security-relevant in couch-tv: `bridge/` middleware and new routes, `on-tv/`, `tv-home/android`, `tv-home/tools`, `sync/`, `examples/docker`, `AGENTS.md` and the workflow.

### 7.2 Verdict

- **No malware.** The delta has no obfuscation, encoded blobs, bidi/zero-width characters or download-and-execute chains. gitleaks finds no secrets in either range. Every new binary is clean (§7.7).
- **Phase 0 verdicts stand.** cleanyourtv is **Safe with caveats**. couch-tv is **Safe with caveats, learn from the design only, do not deploy the bridge or on-TV app.** CT-01 is partly mitigated but its default is unchanged. CT-02 is unchanged. CT-05 is escalated to High (D-CT-03).
- **The `never_disable` list changes**, and so does an assumption in the zentv launcher plan (§7.8). New evidence from both repos makes **disabling the stock Google TV home and `setupwraith` on a Sony Bravia a boot-loop risk**. It also shows that two Sony "telemetry" packages break USB-Ethernet when disabled.

### 7.3 Status of Phase 0 findings

| ID | Phase 0 | Now | What changed |
|---|---|---|---|
| CY-01 | Medium | Medium | 13 → **14** lists disable an OTA updater (`tim-timvision-box-uzw4010tim/debloat.txt:50`, `com.technicolor.app.ota`) |
| CY-02 | Medium | Medium | Unchanged: 23 lists, 3 Sony |
| CY-03 | Medium | Medium | `PROMPT.md`, `CLAUDE.md`, `GEMINI.md` unchanged. `AGENTS.md` changed cosmetically only (adds "DeepSeek Harness" and two README languages). |
| CY-04 | Medium | Medium | Velocity reinforced (D-CY-04). Signing statement corrected (see CY-04 row). |
| CY-05/06 | Medium | Medium | Unchanged (`tools/requirements*.txt` untouched) |
| CY-07 | Low | Low | Launcher manifest unchanged: no new permissions or components, still no `INTERNET` |
| CY-08–17 | Low/Info | unchanged | No workflow changes (`.github/` untouched) |
| CT-01 | High | **High (partly mitigated)** | Optional pairing key, Host allowlist, Origin allowlist instead of `*`, JSON-only POST, rate limiting (couch-tv#73). **But the key is empty by default** (`config.example.json:6`), the bridge still binds `0.0.0.0`, and `Origin: null` is accepted (`bridge/server.py:215-235`, `null` at `:227`). Any website can send `null` from a sandboxed iframe, so drive-by control still works when no key is set, as the project's own `docs/CONFIG.md:337-344` admits. When set, the key travels as `?token=`/`?key=` over cleartext HTTP, in `localStorage`, and on the TV's `am start` command line (`tv-home/tools/apply.sh:161`). New routes `/api/pointer`, `/api/music`, `/api/watch-next`, `/api/roku/*` are open by default too. |
| CT-02 | High | High | `selfEnableWireless` unchanged (`on-tv/.../Adb.kt:258-266`). Two **more** silent self-grants on first ADB connect: `appops GET_USAGE_STATS allow` (`:249`), and `pm grant READ_TV_LISTINGS` or `READ_EPG_DATA` (`:251`). |
| CT-03 | Medium | Medium (broader) | The `TVOS` JS bridge, which still has no origin check, gains `setSleepTimer`, `startScreensaver` (changes the screen timeout), `tvInputs`/`openInput` (HDMI switching) and `openSettingsScreen` |
| CT-04 | Medium | Medium | Updater unchanged apart from an API-level fix. The new sync APK also ships via Releases. |
| CT-05 | Medium | **High → D-CT-03** | Escalated, see below |
| CT-06 | Medium | Medium | The daily re-disable loop remains. Its list is now only ambient mode plus `EXTRA_OFF`. |
| CT-07 | Medium | Medium | LLM tools unchanged. `uninstall`/`force-stop` now run package names through `check_package()` (`bridge/agentic.py:324,667`). |
| CT-08 | Medium | Medium | `bridge/requirements.txt` unchanged, still unlocked |
| CT-09 | Medium | Medium | "Before you start (quietly)", pre-consent `pip install` and release-APK downloads unchanged in `AGENTS.md` |
| CT-10–13 | Low | Low | Unchanged |

### 7.4 New findings: cleanyourtv

| ID | Severity | File:line | Finding | Evidence | Recommendation |
|---|---|---|---|---|---|
| D-CY-01 | **Medium** | `examples/sony-bravia-4k-vh2/debloat.txt:166-187`; still active in `examples/sony-xr-65a80j/debloat.txt:62-63` and 32 more Sony lists | Report #3608: on BRAVIA_VH2 (build `STT2.230505.001.S136 682241`), disabling **`com.sony.dtv.sonybugreportsys`** *or* **`com.sonyericsson.idd.agent`** stops Ethernet through a USB adapter. Both sit in the shared system UID beside `com.sony.dtv.networksettings` and hold `NETWORK_SETTINGS`. Only the vh2 list was fixed. **34 Sony lists still disable one or both**, including `sony-xr-65a80j`, which runs the same VH2 build. | Diff + grep of the new tree | Mark both `risk: high` and off by default on Sony. Hard-refuse when the TV's active transport is Ethernet-over-USB: losing the network means losing the ADB restore path. |
| D-CY-02 | **Medium** | `examples/sony-bravia-ae1/debloat.txt:81-82`, `sony-bravia-vu3/debloat.txt:62-63`, `sony-kdl-43w950d/debloat.txt:149,155`; new `sony-bravia-8-ii/debloat.txt:70` (+ launcherx disabled by `build-and-install.sh`) | Sony lists still disable the stock home **and** `setupwraith` together. couch-tv now reports this exact pair boot-looping a Sony Bravia Google TV (D-CT-04). cleanyourtv's own reports say the opposite (Bravia 8 II and K-55XR35M2 rebooted fine, `docs/devices/sony-k-55xr35m2.md`). The evidence conflicts. | Sweep + diff | Treat as unresolved risk. **zentv must not depend on disabling either** (§7.8). |
| D-CY-03 | Low | `examples/tim-timvision-box-uzw4010tim/debloat.txt:50` | One more list disables a firmware updater (`com.technicolor.app.ota`) | Sweep | Already covered by the OTA rule |
| D-CY-04 | Info | git history | 368 commits in ~3.5 days (44 → 114 → 120 → 84 per day), 81 authors, 40+ identities never seen before, including local-machine identities (`jim@localhost`, `Petrov-AV@nft.local`). The maintainer makes all but two merges, locally and unsigned, as in the week before the audit. **No signing or maintainer change.** | `git log`, raw `gpgsig` | Supports CY-04: snapshot only |
| D-CY-05 | Info | `tools/restore.{sh,ps1}`, `tools/b64push.py:128-139`, `tools/tv.py:265`, `tools/recovery.py:271`, `tools/disable.{sh,ps1}` | Core-path changes are all hardening. Restore now reads back package state and HOME and fails on a mismatch. Other changes: a shell-command length guard, `LC_ALL=C` matching, record type checking, `-LiteralPath`. **No new ADB commands in `tools/`.** | Deep read | Copy the restore read-back idea |
| D-CY-06 | Info | `launcher/.../ServiceRepair.java:66-90`, `HomeKeyService.java`, `config.xml` | `ServiceRepair` (opt-in `restore_key_services`) now also re-cycles its own helper when `ACCESSIBILITY_ENABLED=0` after a firmware kill (#3404). It drops its record when the user turns a helper off, so it respects that choice. New `settings_key_clear_task` switch, off by default. | Deep read | – |
| D-CY-07 | Info | `addons/files-card/`, `addons/koi-pond/` | Two new add-ons with **no permissions**, official Gradle 8.9 wrappers, and AGP 8.5.2 with no libraries. `koi-pond` saves the screensaver setting in a "before" file. Device-list comments add `settings put global auto_time`, `set_auto_play`, `set_patchwall_default`, `cached_apps_freezer`, `user_experience_enabled` and `settings put secure upload_log_pref`. These are **docs only, not scripted**. | Manifest diff + added-line scan | – |

### 7.5 New findings: couch-tv

| ID | Severity | File:line | Finding | Evidence | Recommendation |
|---|---|---|---|---|---|
| D-CT-03 | **High** (was CT-05, Medium) | `tv-home/.../FireWatch.kt` (whole file), `res/xml/fire_watch.xml:9`, `tv-home/tools/apply.sh:163-190` | The Home-button watch now runs on **every Google TV / Android TV / Fire TV** that has a stock home, not only Fire TV. It declares **`canRetrieveWindowContent="true"`**, so it can read screen content (the code says it doesn't). `rebindIfUnbound` deletes and re-adds its own entry in `enabled_accessibility_services`. `apply.sh` grants `WRITE_SECURE_SETTINGS` on any such TV, and on Fire OS boot it brings itself to the front. It also has a new TCL-only fake TV input (D-CT-06). Phase 0's "no accessibility service can read window content" no longer holds for couch-tv. | Diff | Never in zentv: no screen-reading capability, no self-revival |
| D-CT-04 | **Medium** | `README.md:672-700`, `AGENTS.md:358-361`, `tv-home/tools/apply.sh:10-15,55-123`, `tv-home/tools/undo.sh:29-31`, `on-tv/.../App.kt:150,161-180` | **Boot-loop disclosure.** couch-tv ≤0.10 disabled `launcherx`/`tvlauncher` + `setupwraith`, which "can leave a Google TV in a boot loop … Reported on a Sony Bravia Google TV". 0.11+ refuses them, and `apply.sh`, `undo.sh` and the on-TV app **switch them back on**. The on-TV app does this silently, once, over its own ADB, so it would undo another tool's deliberate debloat. `apply.sh` adds a runtime refusal set: HOME-capable or PERSISTENT packages, `com.android.*`, GMS/GSF, `*webview*`, `trichromelibrary`, `tv.remote.service`, `katniss`, `permissioncontroller`, `packageinstaller`, `networkstack*`, `ext.*`, `providers.*`, `com.sony.dtv.sonysystemservice`, `com.sony.dtv.tvx`, `*setupwizard*`, `*.setup`, `*provision*`. | Diff | Adopt as denylist input (§7.8). Never re-enable packages behind the user's back. |
| D-CT-05 | **Medium** | `sync/android/.../Listener.kt:20-50`, `sync/android/.../AndroidManifest.xml`, `sync/install.sh:46` | New experimental helper `dev.couchtv.sync`. It answers **unauthenticated UDP on port 5417 on all interfaces** (reveals uptime; 8-byte request → 24-byte reply, a small reflector). It is granted **notification-listener access** over ADB, so in principle it can read every notification. It has `INTERNET`. Its commands are `DUMP`-protected (ADB only). | Code | Not relevant to zentv. Don't install. |
| D-CT-06 | **Medium** | `tv-home/.../TclPlaceholderInput.kt`, manifest `BIND_TV_INPUT` service, `AGENTS.md:362-381` | **Gets around a vendor control.** A do-nothing `TvInputService` exists only to get past TCL's `TclAppBoot` auto-start block. `AGENTS.md` also tells agents to `appops set … AUTO_START allow` and rewrite accessibility settings after reboots on TCL. Inactive on Sony (enabled only when the manufacturer or brand is TCL). | Code + docs | Never in zentv |
| D-CT-07 | Low | `tv-home/.../MainActivity.kt:895-950`, `apply.sh:90`, `undo.sh:46` | Writes `Settings.System.SCREEN_OFF_TIMEOUT` (`WRITE_SETTINGS` appop granted by `apply.sh`) to trigger the screensaver, saves the original value and restores it. `undo.sh` resets the appop. | Code | – |
| D-CT-08 | Low | `bridge/server.py:1769`, `on-tv/.../Music.kt:58`, `bridge/lg.py:765-780` | New endpoints. `itunes.apple.com/search` receives now-playing song titles from media sessions. `developer.lge.com/secure/CheckDevModeSession.dev` receives the LG Developer Mode session token (HTTPS, not logged). | Added-line URL scan | Note for privacy docs |
| D-CT-09 | Low | `examples/docker/{Dockerfile,compose.yaml,entrypoint.sh}` | Bridge Docker example: **unpinned** `node:22-bookworm-slim` base, runs as root, `network_mode: host` with `0.0.0.0`. `pip install` without hashes, and a global `npm install -g @webos-tools/cli@3.2.6` without a lockfile. The ADB key sits in the mounted repo (`bridge/data/adbkey`, gitignored). | Files | – |
| D-CT-10 | Low | `{on-tv,tv-home}/android/app/build.gradle.kts`, `docs/ROKU.md`, `AGENTS.md:140-158` | `minSdk` lowered 25 → 23. `tv-home` release lint is off (`checkReleaseBuilds=false`, `abortOnError=false`). The Roku path asks users to set "Control by mobile apps" to **Permissive**, which opens Roku ECP control to the whole LAN. | Diff | – |
| D-CT-11 | Info | `AGENTS.md` | New rules: "**Never switch off the Google TV home … or the setup app**", a Roku section and a sync section that requires the same "yes". The pre-consent download steps are unchanged (CT-09). The workflow only adds `sync/` to the compile and parse checks. | Diff | – |
| D-CT-12 | Info | `roku/package-lock.json`, `examples/docker/Dockerfile:10` | New npm lockfile: 160 packages, all dev-only, all from `registry.npmjs.org`, **0 vulnerabilities**. `@webos-tools/cli@3.2.6`: none known. `sync/` and `tests/fake-player` add no Maven libraries (AGP 8.7.3, Kotlin 2.0.21 as before). | osv-scanner 2.7.0, OSV API | – |
| D-CT-13 | Info | git history | 9 new author identities. 3 SSH-signed commits from one contributor (Anand Kumar). The maintainer is unchanged and unsigned. | Raw `gpgsig` | – |
| D-CT-14 | Info | `tv-home/.../CrashGuard.kt` | Good pattern: after two unsettled starts or crashes within 3 minutes, the custom home **steps aside to the stock home** for 5 minutes, so a broken launcher can't trap the TV. This only works when the stock home stays enabled. | Code | **Adopt in the zentv launcher** |

### 7.6 Authors and signing

| | cleanyourtv delta | couch-tv delta |
|---|---|---|
| Authors / new identities | 81 / 40+ | 10 / 9 |
| Merge committer | Gathin23 (164 of 166) | Seagey (50 of 51) |
| Signed commits (raw `gpgsig`) | 15 (contributors' SSH/PGP, 1 GitHub web-flow) | 3 (one contributor's SSH key) |
| Pre-audit, for comparison | ≈330 signed (151 GitHub web-flow) | 0 |
| Change in signing practice | None | None |

### 7.7 New binaries (SHA-256)

67 added or changed non-text files: cleanyourtv has 2 `gradle-wrapper.jar` + 15 images, couch-tv has 3 TTF + 47 images. There is **no** APK, DEX, `.so`, executable or archive. All have valid magic bytes and **nothing appended**. The full list is appended to [`binaries-sha256.txt`](binaries-sha256.txt).

| SHA-256 | File | Check |
|---|---|---|
| `498495120a03b9a6ab5d155f5de3c8f0d986a449153702fb80fc80e134484f17` | cleanyourtv `addons/{files-card,koi-pond}/gradle/wrapper/gradle-wrapper.jar` | **MATCH** official Gradle 8.9. `distributionSha256Sum` matches the official bin.zip. URL is `services.gradle.org`. |
| `57b0834f486ec935ad7ec49ba7e39cb3ad14274c075879f588a3178ed41ed2fb` | couch-tv `roku/channel/fonts/Antonio-Light.ttf` | VirusTotal / upstream check (§7.9) |
| `141d611218560b46a8155b5fa0f551d879fbd2c47cd04f81b09f68f9d691cbfc` | couch-tv `roku/channel/fonts/Inter-Medium.ttf` | VirusTotal / upstream check |
| `b02555899225ec3fef680368a4dfcb572d5b950e3b03f3c7f57f54850111cc40` | couch-tv `roku/channel/fonts/Inter-Regular.ttf` | VirusTotal / upstream check |

### 7.8 Impact on zentv: `never_disable` and the launcher plan

**Add to `safety/never_disable.yaml` (hard refuse, no override):**

| Scope | Packages / rule | Source |
|---|---|---|
| Google TV / Android TV (incl. Sony) | `com.google.android.apps.tv.launcherx`, `com.google.android.tvlauncher`, `com.google.android.tungsten.setupwraith` | D-CT-04 (Sony Bravia boot loop), D-CY-02 (conflicting evidence, so take the safe side) |
| Generic, dynamic | Any package that answers `CATEGORY_HOME`. Any package with the `PERSISTENT` flag (`dumpsys package`). `*webview*`, `com.google.android.trichromelibrary`, `*provision*`, `*setupwizard*`, `*.setup`. | `couch-tv/tv-home/tools/apply.sh:105-113` |
| Sony | `com.sony.dtv.sonysystemservice`, `com.sony.dtv.tvx`, `com.sony.dtv.tvlin`, `com.sony.dtv.smartui`, `com.sony.dtv.networksettings`, `com.sony.dtv.imeproxy`, `com.sony.dtv.irblaster`/`irbservice`, `com.uei.quicksetsdk` | couch-tv `apply.sh`, `cleanyourtv/examples/sony-bravia-8-ii/debloat.txt:27-30`, `docs/devices/sony-k-55xr35m2.md` |
| Sony on MediaTek | `com.mediatek.*` (incl. `com.mediatek.external` for HDMI, `com.mediatek.tis`, `com.mediatek.tv.oneworld.tvcenter` for Live TV on CT1), never start `mediatek.factorymenu.ui` | Same |

**Add as `risk: high`, off by default (asked per TV, never in a default plan):**
- **`com.sonyericsson.idd.agent` and `com.sony.dtv.sonybugreportsys`.** These break USB-Ethernet on BRAVIA_VH2 (D-CY-01). **Refuse them outright when the active transport is Ethernet-over-USB.**
- **`com.google.android.katniss`** (Assistant/voice), **`com.google.android.tv.remote.service`** (phone remote, CY-02), and **`com.vewd.core.service`** (AirPlay crash-loops without it).
- Sony tuner inputs (`com.sony.dtv.tvinput.*`, `com.mediatek.dtv.tvinput.*`). These are only safe to disable with no aerial or tuner use.

**Change to the launcher plan (needs your decision at Checkpoint 3).** The build prompt's guard ("never disable the stock launcher until the zentv launcher is installed **and** answers HOME") assumes the stock home is disabled once the guard passes. With the stock home in `never_disable`, zentv takes over HOME **without disabling anything**. It uses `cmd package set-home-activity`, plus a Home-key fallback that watches window changes only and has **no window-content capability and no self-revival**. Google TV's "Apps only" mode is the zero-install alternative (`examples/sony-xr-65a80j/debloat.txt:53-55`). A CrashGuard-style step-aside (D-CT-14) depends on the stock home staying enabled. One further note: if a user keeps the stock home and uses DNS blocking, they must allow `androidtvlauncherxfe-pa.googleapis.com` (`sony-xr-65a80j/debloat.txt:53-55`).

### 7.9 Manual checks added by the delta

1. VirusTotal or upstream comparison for the 3 new Roku TTF hashes in §7.7. The wrapper jar already matches Gradle.
2. If you want the boot-loop evidence first-hand: read couch-tv's GitHub issues about the Sony loop, and cleanyourtv #3608 (Ethernet). The repos only paraphrase them.
3. **Clone state.** If the clones should sit on the audited commits, run `git -C ~/forgelab/reference/cleanyourtv switch --detach d451b175` and `git -C ~/forgelab/reference/couch-tv switch --detach ff2cfbf` yourself, or ask me to. Until then, anything that opens those folders (an IDE indexer, an agent reading `CLAUDE.md`) sees the unaudited tips.

---

## Appendix A: Commands and tools

Tools: ripgrep 14.1.1, gitleaks 8.30.1, osv-scanner 2.7.0, Python 3.11.10 (stdlib only, `-I`), git 2.54.0, `shasum`, `file`, `curl` (Gradle checksums and the OSV API only). macOS 27.2, Apple Silicon.

Main commands, with all output written to a scratch directory outside both repos:

```sh
# inventory + hashes
find <repo> -path <repo>/.git -prune -o -type f -print0 | xargs -0 file --mime-type   # non-text files
shasum -a 256 <each non-text file>                                                       # binaries-sha256.txt
curl -fsSL https://services.gradle.org/distributions/gradle-{8.9,8.11.1}-{wrapper.jar,bin.zip}.sha256
python3 -I trailing.py         # bytes after JPEG EOI / PNG IEND / WebP RIFF / WOFF2 length

# pattern scans (ripgrep): URLs/IPs, curl|sh, eval/exec, base64 -d, shell=True, Runtime.exec,
# DexClassLoader, bidi U+202A-202E/U+2066-2069, zero-width, >=200-char base64/hex, writes to ~/rc/LaunchAgents/cron
rg -n -P '<pattern>' cleanyourtv couch-tv

# ADB command extraction + classification
rg -o -P '(pm (uninstall|disable-user|enable|grant|...)|settings (put|delete) ...|appops set|dpm ...|setprop ...)' ...
python3 -I critical_sweep.py cleanyourtv/examples out.json   # active list entries vs critical categories
python3 -I manifests.py out.json <every AndroidManifest.xml>  # refuses DOCTYPE; perms/exported/flags

# dependencies (lockfile parsing only, nothing installed)
osv-scanner scan source --lockfile=couch-tv/remote/package-lock.json \
  --lockfile=requirements.txt:<each requirements*.txt> --format json
curl -X POST https://api.osv.dev/v1/querybatch -d @maven-queries.json   # 22 Maven coordinates

# history + secrets
git log --stat / shortlog -sne / --format='%G?' / --date=iso; git rev-list --objects --all | git cat-file --batch-check
git fsck; git reflog
gitleaks git <repo> --redact --report-path <scratch>; gitleaks dir <repo> --redact --report-path <scratch>
```

Verification that the references were not modified: `git -C <repo> status --porcelain` was empty, and HEAD was unchanged (`d451b175`, `ff2cfbf`), both before and after the audit.
