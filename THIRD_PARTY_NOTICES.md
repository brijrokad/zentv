# Third-party notices

zentv contains **no code copied** from other projects. The concepts below were studied statically (`docs/audit/`) and reimplemented from scratch. They're credited here with thanks.

## Concepts reimplemented

| Concept | Where in zentv | Inspired by |
|---|---|---|
| Record state before the first change (first record wins), replay restore, read-back verification | `zenctl/snapshot.py`, `restore.py` (M2) | cleanyourtv (MIT, © 2026 Gathin), `tools/recovery.py`, `restore.sh` |
| A hard core-package denylist with no override, and a package-name regex on everything sent to the TV shell | `safety/never_disable.yaml`, `zenctl/safety.py`, `zenctl/commands.py` | cleanyourtv (MIT), `AGENTS.md`, `tools/*` |
| Checking that ADB is closed by greeting the port with ADB's CNXN message (CNXN/AUTH/STLS = open) | `zenctl/adbclose.py` | cleanyourtv (MIT), `tools/adb-closed.py` |
| Runtime refusal of HOME-capable and PERSISTENT packages, plus the stock home / setup wizard (boot-loop report) | `safety/never_disable.yaml` (`dynamic`, `google`) | couch-tv (MIT, © 2026 Seagey), `tv-home/tools/apply.sh` |
| CrashGuard: step aside to the stock home after repeated failed starts | `launcher/` (M4) | couch-tv (MIT), `tv-home/.../CrashGuard.kt` |

Device facts in `devices/*/PROFILE.md` cite cleanyourtv and couch-tv device notes as data.

## Runtime and development dependencies

| Package | License | Use |
|---|---|---|
| PyYAML | MIT | Parsing `safety/` and `devices/` YAML (`safe_load` only) |
| pytest | MIT | Tests (dev only) |
| ruff | MIT | Lint and format (dev only) |
| Android SDK Platform-Tools (`adb`) | Google's terms; installed separately, not distributed | Talking to the TV |
