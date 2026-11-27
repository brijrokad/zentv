# Third-party notices

zentv contains **no code copied** from other projects. The concepts below were studied statically (`docs/audit/`) and reimplemented from scratch. They're credited here with thanks.

## Concepts reimplemented

| Concept | Where in zentv | Inspired by |
|---|---|---|
| Record state before the first change (first record wins), replay restore, read-back verification | `zenctl/snapshot.py`, `restore.py` (M2) | cleanyourtv (MIT, © 2026 Gathin), `tools/recovery.py`, `restore.sh` |
| A hard core-package denylist with no override, and a package-name regex on everything sent to the TV shell | `safety/never_disable.yaml`, `zenctl/safety.py`, `zenctl/commands.py` | cleanyourtv (MIT), `AGENTS.md`, `tools/*` |
| Checking that ADB is closed by greeting the port with ADB's CNXN message (CNXN/AUTH/STLS = open) | `zenctl/adbclose.py` | cleanyourtv (MIT), `tools/adb-closed.py` |
| Runtime refusal of HOME-capable and PERSISTENT packages, plus the stock home / setup wizard (boot-loop report) | `safety/never_disable.yaml` (`dynamic`, `google`) | couch-tv (MIT, © 2026 Seagey), `tv-home/tools/apply.sh` |
| CrashGuard: step aside to the stock home after repeated failed starts | `launcher/.../CrashGuard.kt` | couch-tv (MIT), `tv-home/.../CrashGuard.kt` |
| Picking the home scene by time of day | `launcher/.../Scenes.kt` (`Scene.forHour`, zentv's own hours) | couch-tv (MIT), `tv-home/web/app.js` |
| A frosted-glass clock filled with the scene's pre-blurred layer, with the scene's cut-out drawn over the digits | `launcher/.../SceneView.kt` (native Canvas drawing) | couch-tv (MIT), `tv-home/web/` |

Device facts in `devices/*/PROFILE.md` cite cleanyourtv and couch-tv device notes as data.

## Images

| Files | Source | Terms |
|---|---|---|
| Home scenes `scene-night`, `scene-golden`, `scene-water`, `scene-fog`, `scene-dawn` (+ `-fg` cut-outs, `-glass` fills, `@2x` 4K copies) | couch-tv (© 2026 Seagey), `tv-home/web/backgrounds/` at `bc5df03a`. Made for couch-tv with an AI image model from text only; the 4K copies are upscaled with Real-ESRGAN. | couch-tv's `CREDITS.md`: "Use them however you like." Thanks to couch-tv. zentv ships the 1080p files only (`launcher/app/src/main/assets/scenes/`, 14 files, byte-for-byte; hashes in `docs/audit/binaries-sha256.txt`). |

## Fonts

| Files | Source | Terms |
|---|---|---|
| `launcher/app/src/main/assets/fonts/antonio.ttf` (Antonio, variable weight), used for the clock | `google/fonts` `ofl/antonio/Antonio[wght].ttf` at commit `95f4904f`; © 2013 The Antonio Project Authors | SIL Open Font License 1.1, full text in `launcher/licenses/Antonio-OFL.txt` |

## Runtime and development dependencies

| Package | License | Use |
|---|---|---|
| PyYAML | MIT | Parsing `safety/` and `devices/` YAML (`safe_load` only) |
| pytest | MIT | Tests (dev only) |
| ruff | MIT | Lint and format (dev only) |
| JUnit 4.13.2 (+ Hamcrest 1.3) | EPL 1.0 (BSD-3 for Hamcrest) | Launcher unit tests (test only, not in the APK) |
| Android Gradle Plugin, Kotlin | Apache 2.0 | Building the launcher (not in the APK; R8 keeps only the Kotlin standard library code zentv uses) |
| Android SDK Platform-Tools (`adb`) | Google's terms; installed separately, not distributed | Talking to the TV |
