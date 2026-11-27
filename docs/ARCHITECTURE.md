# zentv architecture and milestone plan (Phase 2 proposal)

Status: **approved at Checkpoint 3** (D1 revised to a flat `zenctl/` package; D2–D10 as recommended). Nothing is scaffolded yet, and nothing has touched either TV.
Binding inputs: `ZENTV_BUILD_PROMPT.md` v3 (ground rules 1–13), `docs/audit/SECURITY_AUDIT.md` (§8 is the baseline), `docs/audit/EVALUATION.md`, `safety/never_disable.yaml`, and `devices/*/PROFILE.md`.

## 1. Design principles

Each one comes straight from a ground rule:

1. **Dry-run is the default; the TV is the last step.**
   - Every state-changing command is built, checked and printed before anything is sent.
   - `--yes` is the only way to send it (rule 4).
2. **The allowlist is the gate, not the denylist.**
   - The ADB layer can only send commands that `commands.py` built from typed arguments.
   - The hard-refuse patterns (rule 5) are a **second** net underneath that.
3. **Snapshot before every change, read back after every change.**
   - Every value a command touches has a recorder that runs first (rule 6).
   - Restore replays the snapshot, then reads the state back and fails loudly on any mismatch.
4. **No background anything.**
   - No daemon, no loop, no scheduled re-apply.
   - Drift is reported by `zentv check` when you ask for it (rules 5 and 8).
5. **An unverified device is read-only.**
   - zentv refuses every state change until that TV's profile has `status: confirmed` with a `match` block that equals the live `getprop` values.
   - Phase 3 is what confirms it.
6. **Small, dependency-light, and offline.**
   - The Python runtime has one dependency (§3).
   - The launcher has no `INTERNET` in its core flavour.

## 2. Repository layout

**Decided at Checkpoint 3 (D1): flat layout, and the Python package is named for its role.** The package is **`zenctl`** ("zentv control"), at the repo root next to `launcher/`: `zenctl/` is the Mac side and `launcher/` is the TV side. The **command stays `zentv`** (`[project.scripts] zentv = "zenctl.cli:main"`), so you type `zentv survey` and `zentv apply`. The distribution name in `pyproject.toml` stays `zentv`. `uv_build` is told where the module lives with `[tool.uv.build-backend] module-name = "zenctl"` and `module-root = ""`. Tests run against the installed (editable) package through `uv run pytest`. The existing `src/zentv/__init__.py` placeholder is removed in M1.

```
zentv/
├── zenctl/                    # import zenctl; console command `zentv`
│   ├── __main__.py / cli.py   # argparse CLI; every state-changing subcommand is dry-run unless --yes
│   ├── adb.py                 # Transport: runs platform-tools `adb` via subprocess argv (never shell=True), timeouts, one device (-s)
│   ├── commands.py            # the ONLY constructors of TV commands; typed, read-only vs state-changing; PACKAGE_RE + shlex.quote
│   ├── refuse.py              # rule 5 hard-refuse patterns, checked on the final command string (second net)
│   ├── device.py              # identify the TV (getprop), pick the profile by its match block, brand/SoC scope
│   ├── safety.py              # never_disable.yaml: static groups by scope, dynamic rules (HOME, PERSISTENT, globs), high_risk
│   ├── survey.py              # read-only inventory → survey.json (redacted)
│   ├── redact.py              # serials, MACs, IPs, Wi-Fi SSIDs, account names → stable placeholders
│   ├── snapshot.py            # record pre-state; first-record-wins; ~/.zentv/snapshots/
│   ├── plan.py                # debloat.yaml + live state + safety → plan (diff table)
│   ├── apply.py               # snapshot → re-check plan → one package per call → read back
│   ├── restore.py             # replay snapshot in reverse → read back → fail on mismatch
│   ├── check.py               # read-only drift report against the last applied snapshot
│   ├── launcher.py            # install, set-home, enable/disable-home-key (incl. TCL app-op, rule 6), revert
│   ├── privacy.py             # read-only: ad ID / personalization settings, usage access, Private DNS, telemetry packages still enabled
│   ├── adbclose.py            # switch network ADB off, then verify from the Mac (TCP + ADB CNXN greeting, mDNS)
│   ├── smoke.py               # interactive checklist from the profile; a failure prints the restore command
│   └── bench.py               # read-only metrics (boot-to-home, free RAM, gfxinfo jank, enabled count)
├── devices/<brand>-<platform>/ # PROFILE.md, profile.yaml (machine-readable match + features), survey.json, debloat.yaml
├── safety/never_disable.yaml
├── launcher/                  # Gradle project (§6)
├── tests/                     # pytest; FakeDevice + fake `adb` shim; no TV needed
├── docs/                      # audit/, ARCHITECTURE.md, restore.md, troubleshooting.md, smoke-test.md, launcher-permissions.md
├── AGENTS.md, CLAUDE.md       # restate rules 1–13 for agents working in THIS repo
├── README.md, LICENSE, THIRD_PARTY_NOTICES.md, env.example, .gitignore
├── scripts/hooks/pre-commit   # gitleaks + ruff (plain script, no pre-commit framework; installed by `scripts/install-hooks.sh`)
└── .github/workflows/ci.yml   # ruff, pytest, gradle build/lint/unit tests, manifest permission check, gitleaks; SHA-pinned, contents: read
```

**What stays outside the repo:**
- `~/.zentv/` holds snapshots, logs and smoke-test results, created with `0700`.
- ADB keys stay in `~/.android/` (rule 11).
- `survey.json` in `devices/` is redacted before it's written. Raw output never touches the repo.

## 3. Python CLI

### 3.1 Runtime and dependencies

- **Python 3.15** (uv-managed; `cpython-3.15.2` is already installed). `uv.lock` with hashes.
- **One runtime dependency: PyYAML**, used only through `yaml.safe_load`. The YAML files are human-edited and already exist. The alternative is converting them to TOML and using the stdlib `tomllib`, with zero dependencies (decision D2).
- **Dev dependencies:** `pytest`, `ruff`.
- **ADB transport:** Google's platform-tools `adb` binary, run through `subprocess.run([...], timeout=…)`. It handles wireless pairing (`adb pair`, Android 11+ / the Sony) and `adb connect host:5555` (the TCL, where Network/USB debugging opens 5555). I prefer this to a Python ADB library because there's no third-party crypto, and the binary is what Google ships. `adb` isn't installed yet (decision D3).

### 3.2 The command model (how rule 5 can't be broken by accident)

```
commands.py                         adb.py (Transport)
  ReadOnly(argv)  ─┐                  send(cmd):
  StateChange(argv,                    1. isinstance(cmd, Command) built by commands.py   else TypeError
     records=[...], ─┼─► final string ─► 2. refuse.check(final_string)                     else Refused
     inverse=...)    │                  3. cmd.state_change and not ctx.yes → print, return DryRun
                     │                  4. cmd.state_change and no recorder ran in ctx.snapshot → Refused
                     ┘                  5. subprocess argv, timeout, capture; log (redacted)
```

- **Constructors:** `get_prop(name)`, `pm_list(flags)`, `dumpsys(service, args)`, `resolve_home()`, `query_home()`, `settings_get(ns, key)`, `appops_get(pkg, op)` (read-only), and `disable_user(pkg)`, `enable(pkg)`, `set_home_activity(component)`, `set_accessibility(services, enabled)`, `tcl_appop(pkg, op, mode)`, `appops_write_settings()`, `adb_network_off()`. **There is no constructor** for any rule 5 command, so none can be built.
- **Arguments:** every package name passes `PACKAGE_RE = ^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$`, and components pass `pkg/.Class`. Strings are `shlex.quote`d. There's a length cap, as in cleanyourtv's command-length guard.
- **`tcl_appop` refuses unless** `device.brand == "tcl"` (from `ro.product.brand`/`manufacturer`), `pkg ==` zentv's own applicationId, `op ∈ {APP_AUTO_START, AUTO_START}`, and the op exists on the build (checked first with `appops get`). That's rule 6 as approved.
- **`refuse.py`** matches the final shell string against rule 5: `pm uninstall`, `pm clear`, `pm hide`, `pm suspend`, `dpm `, `setprop persist.`, `verifier_verify_adb_installs`, `package_verifier_enable`, `adb_enabled 1`, `adb_wifi_enabled 1`, `WRITE_SECURE_SETTINGS`, `install -g`/`--bypass`/`-t` style flags, `&&`/`;`/`|` chaining. It's a backstop for bugs in `commands.py`.

### 3.3 Device identity and the read-only gate

- `device.identify()` reads `ro.product.brand`, `manufacturer`, `model`, `device`, `name`, `board.platform`, `build.fingerprint`, `build.version.sdk` and `cpu.abilist`.
- It picks the profile whose `profile.yaml` `match` block equals those values.
- **State-changing commands need `profile.status == confirmed`, and a fingerprint that equals the one recorded in the profile.** A firmware update makes zentv drop to read-only until the profile is re-confirmed, which forces a fresh look after every OTA.
- Before Phase 3, both profiles are `unverified`, so only `survey`, `privacy`, `check`, `bench` and `adb-close` can run.

### 3.4 Safety engine

- **Static groups** (`never_disable.yaml`) are matched by scope: `all`, `{brand}`, `{brand, soc}`, `{device}`. Entries are exact names or `fnmatchcase` globs.
- **Dynamic rules run against the live TV before every `plan` and every `apply`:**
  - every package answering `CATEGORY_HOME` (zentv included)
  - every package flagged `PERSISTENT` in `dumpsys package`
  - name globs
- **`high_risk`** never refuses. The planner marks those entries `risk: high, default: off` and needs them named on the command line (`--include com.tcl.usercenter`), with the reason printed.
- **A refusal names the group, the entry or rule, and the reason.** The run stops before anything is sent.
- **`safety.py` also refuses removing anything a profile maps to a feature in use.** That's the device groups plus Phase 3's feature map.

### 3.5 Snapshots, apply, restore

**Snapshot file:** `~/.zentv/snapshots/<device-key>/<utc>-<plan-digest>.json`.
- `<device-key>` is the SHA-256 of `ro.serialno`, truncated. The serial itself is never stored.
- Contents: `schema`, `fingerprint`, `profile`, `plan_digest`, and, for each recorded key, the pre-state and how to read it back:

```json
{ "schema": 1, "fingerprint": "…", "profile": "sony-bravia-4k-vh21", "plan_digest": "…",
  "packages": {"com.example.promo": {"enabled": "default"}, "…": {}},
  "home": {"resolved": "com.google.android.apps.tv.launcherx/.MainActivity"},
  "settings": {"secure/enabled_accessibility_services": null, "secure/accessibility_enabled": "0"},
  "appops": {"<zentv>/APP_AUTO_START": "default"} }
```

- **First record wins**, per device and plan digest, so a half-applied retry can't overwrite the original state (cleanyourtv concept). Changing the plan makes a new digest and a new snapshot. Restore can take any snapshot by path.
- **Fresh** means the snapshot was taken by this same `apply` invocation, or under 10 minutes ago with an unchanged fingerprint, and the recorded pre-states still match the live TV for every key the plan touches. Otherwise `apply` refuses (prompt requirement).
- **`apply`:**
  1. Identify the device and check the read-only gate.
  2. Run the safety engine.
  3. Take the snapshot.
  4. Show the dry-run table.
  5. With `--yes`, send one change per call, read each back, and stop at the first failure (it prints the restore command).
  6. Wait for the package-state write to settle (about 25 s, a lesson from the TCL notes) before suggesting a reboot.
- **`restore <snapshot>`:** replays the inverses in reverse order, for exactly the keys recorded. Packages the owner had disabled before stay disabled. Then it reads back every key and exits non-zero with a mismatch table.
- **Implemented in M2.** Two details were settled while building it:
  - The snapshot digest comes from the plan's **intent** (the selected targets and restores), not the remaining actions. That way a retry after a half-finished apply finds the original snapshot.
  - `restore`'s `pm enable` is **exempt from the read-only gate**, but only when the snapshot's device key matches this TV. A firmware update closes the gate, and restore must still work after it.
- **Un-hide exception (Checkpoint 4):** `commands.unhide()` only accepts packages listed under the device's `restore_hidden`. `restore` never re-hides, because zentv has no `pm hide`.
- **`check`:** read-only. It compares the live TV with the last applied snapshot's intended state and reports drift. It never changes anything.

### 3.6 Launcher commands (run in M4, specified now)

- **`launcher install <apk>`:** `adb install` of **zentv's own APK only** (the package and signing certificate are checked locally first), through Android's normal install path. Never `-g`, never a Play Protect bypass. This needs a rule 6 addition (decision D5).
- **`launcher set-home`:** snapshots the HOME resolver, runs `cmd package set-home-activity <zentv>/.MainActivity`, then reads back. If it reports Success but nothing changes (the VH22 behaviour), that's recorded as "HOME not taken" and the helper becomes the route.
- **`launcher enable-home-key`:**
  1. Snapshot `enabled_accessibility_services` and `accessibility_enabled`, plus the TCL app-op modes on TCL.
  2. Dry-run.
  3. With `--yes`, append the helper to the list, set `accessibility_enabled 1`, and on TCL run `tcl_appop` + `appops write-settings`.
  4. Read back, including `dumpsys accessibility` to confirm the service is bound.
- **`launcher disable-home-key` / `revert`:**
  1. Remove only zentv's entry and restore `accessibility_enabled` from the snapshot.
  2. Restore the HOME preference.
  3. On TCL, restore the app-op modes + `write-settings`.
  4. Read back.

  zentv stays installed: rule 5 forbids `pm uninstall` in any form. You remove it in Settings if you want it gone.

### 3.7 adb-close

1. Optionally capture the pre-state (that's the point of the command, so there's no restore).
2. Send `settings put global adb_wifi_enabled 0` and/or `adb_enabled 0`. Only `=1` is refused.
3. From the Mac, retry a TCP connect to port 5555 and to the last wireless-debugging port.
4. Send ADB's CNXN greeting and read the 24-byte header. CNXN/AUTH/STLS means network ADB is still on (concept from cleanyourtv D2-CY-04, reimplemented). It never sends a key.
5. Check `adb mdns services` for `_adb-tls-connect`.

Exit 0 only when everything reads closed. Every TV session ends with it (rule 10), and the CLI prints a reminder if a session ends without it.

### 3.8 Redaction

`redact.py` runs on everything written to `devices/` and on logs. It masks `ro.serialno`, `ro.boot.serialno`, the TCL serial format, MACs, IPv4/IPv6 addresses, SSIDs and BSSIDs, Google account names, and Android IDs, with stable `<SERIAL-1>`-style tokens. A test feeds it a fixture containing known identifiers, including the TCL serial pattern (`^\d{4}[A-Z]{3}\d{6}[A-Z]\d{5}$`), and asserts none survive.

## 4. Data files

- **`devices/<d>/profile.yaml`** (new, machine-readable; `PROFILE.md` stays the human record): `status: unverified|confirmed`, `match: {ro.product.device: …, ro.product.name: …}`, `fingerprint`, `brand`, `soc`, `features: {remote: [pkgs], voice: [...], cast: [...], airplay: [...], tuner: [...]}`, `network: {required: [wifi, ethernet, usb_ethernet]}`, `smoke: [checklist ids]`. Phase 3 fills it.
- **`devices/<d>/debloat.yaml`**: entries of `package`, `reason`, `risk: low|medium|high`, `default: on|off`, `feature:` (optional; an entry mapped to a feature in use is refused), `source:` (survey line, or "cross-checked with cleanyourtv <list>:<line> as data").
- **`safety/never_disable.yaml`**: as it is now (schema 1, `groups`, `never_start`, `high_risk`).

## 5. Tests (no TV)

- **`FakeDevice`** is an in-memory model of a TV: packages with enabled state and flags, HOME candidates and preference, `settings`, appops (including whether an op name exists), accessibility bound state, and props. The transport sends parsed commands to it, so state changes actually happen and read-back works.
- **Fixtures:** `sony_vh21` and `tcl_g03` FakeDevices, built from the reference data in each `PROFILE.md`. They're replaced by redacted Phase 3 surveys later.
- **Fake `adb` shim:** an executable on `PATH` that serves the FakeDevice, for end-to-end CLI tests.
- **Required tests (acceptance for M1–M2):**
  - Every rule 5 form is refused at `refuse.py`, and none has a constructor. These are table-driven from the prompt text.
  - Every `never_disable` entry, glob and dynamic rule refuses on the matching fixture. Device groups only apply to their device. `high_risk` needs `--include`.
  - The dry-run path sends **zero** state-changing calls (asserted with a transport spy).
  - **Round trip:** `apply` → `restore` returns the FakeDevice to a byte-identical state for every recorded key. A mutated device makes `restore` exit non-zero with a mismatch table.
  - Every `StateChange` type has a recorder, and `apply` refuses if it didn't run. This is a meta-test over `commands.py`.
  - First record wins. A stale or mismatched snapshot is refused.
  - `tcl_appop` is refused on Sony, refused for any package other than zentv's, and refused when the op doesn't exist. `revert` restores the mode and verifies it.
  - Read-only gate: an unverified profile or a changed fingerprint blocks every state change.
  - Redaction: no identifier from the fixture survives.
  - `adb-close` treats CNXN/AUTH/STLS as open, and a refusal or a non-ADB reply as closed or not-ADB (a fake socket server).

## 6. Launcher (Kotlin)

- **One Gradle project** in `launcher/`, with a pinned wrapper (official `distributionSha256Sum`) and **Gradle dependency verification** (`gradle/verification-metadata.xml`, SHA-256). Only Google and Maven Central repositories, no JitPack. AGP and Kotlin at current stable versions.
- **Flavours:**
  - `core`: no `INTERNET`, the default.
  - `weather`: adds `INTERNET`, plus a `networkSecurityConfig` that allows only the Open-Meteo hosts, with cleartext off.
- **Build type `spike`** for M3a (retired in M4: its helper became `HomeKeyService`; the code stays in git history and `docs/spikes/M3a-tcl-home-key.md`).
- **SDK:** `minSdk 30`, `targetSdk` ≥ 30, Kotlin + Views. No AndroidX beyond what's justified (`recyclerview` at most). No coroutines, no NDK.
- **Components:**
  - `MainActivity`: `MAIN` + `LEANBACK_LAUNCHER`/`LAUNCHER`. The `HOME` filter sits on an activity-alias `.Home` that is **off by default**: on the TCL Home reaches zentv through the helper (consume mode), so there is never a second HOME app for the system to ask about. `launcher set-home` turns the alias on only for TVs that honour `set-home-activity`.
  - `AllAppsActivity`: six-column grid over the scene's `-glass` layer (110%, saturation 1.25) under a 20–80% tint; hold OK for favourite / move / hide; a footer toggles hidden apps.
  - `SceneView`: scene → frosted-glass or tall clock → cut-out → flip or analog clock → date → scrim, all on Canvas. Scenes follow the time of day (dawn 05–08, water 08–16, golden 16–19, night) unless one is chosen in zentv settings. Only the 1080p scene files ship: the UI renders at 1920×1080, and the 4K copies would add ~8 MB and four times the bitmap memory on a 2 GB TV.
  - `AppCatalog`: `PackageManager` query for `LEANBACK_LAUNCHER`. Package visibility comes from `<queries><intent>` for the launcher intents, not `QUERY_ALL_PACKAGES`.
  - `HomeKeyService` in `android:process=":homekey"`: key filter only, `canRetrieveWindowContent=false`, no event types beyond what key filtering needs.
  - `ForegroundProbe` (in `:homekey`): `ActivityManager.getRunningAppProcesses()` filtered to zentv's own UI process, checking `IMPORTANCE_FOREGROUND`. The fallback is a binder `ZentvStateService` in the UI process, protected by a `signature`-level custom permission.
  - `CrashGuard`: an uncaught-exception handler writes a crash record to app storage. A start with no "settled" mark within N seconds counts as unsettled. Two of those in 3 minutes means step aside to the stock home for 5 minutes. A process death with no crash record (a vendor trim, LMK) isn't counted.
  - `InputTiles` (approved 2026-11-27): HDMI inputs come from `TvInputManager`, plus the HDMI-CEC device on each port.
    - The tile **label is the port only** (`HDMI 1`, `HDMI 2`, …).
    - The **icon** is the owner's private logo from `launcher/local-icons/` (git-ignored; the `copyLocalIcons*` task copies PNG/WebP/JPG as-is into `assets/consoles/`, since Android decodes all three; `-Pzentv.localIcons=false` leaves them out) when the CEC name matches PlayStation, Xbox or Nintendo.
    - Otherwise the icon is zentv's fallback: a controller glyph with the console's short name (`PS5`, `XBOX`, `SWITCH`) underneath, drawn as one icon.
    - A plain input with no CEC device gets an HDMI-port glyph.
    - No trademarked artwork is ever committed.
  - `ThemeStore`: JSON themes bundled in assets, plus an optional import folder in app-specific storage (decision D6).
- **No boot receiver, no notification listener, no `WRITE_SECURE_SETTINGS`, no `READ_TV_LISTINGS`, no location.**
- **CI checks the built APKs** (`aapt2 dump permissions`): `coreRelease` must have no uses-permission at all, `weatherRelease` exactly `INTERNET`; neither may contain `.so` files or `assets/consoles/`; `coreRelease` must stay under 3 MB. The accessibility binding is a `permission=` attribute, not a uses-permission.
- **Weather:** `WeatherProvider` exists in two flavour source sets. The core one is a stub with no network code; the weather one talks only to `api.open-meteo.com` and `geocoding-api.open-meteo.com`, enforced in `OpenMeteo.checked` (HTTPS, host allowlist, port 443, no credentials) and unit-tested, because Android's network security config cannot block hosts. No location permission: the owner types a town once.
- **Signing:** a release key you generate, kept in `~/.zentv/keys/` (`release.properties` + keystore), never in the repo. The Gradle build signs release APKs with it only if that file exists. CI builds unsigned release APKs only.

## 7. Milestones and acceptance criteria

I propose two changes to the prompt's sequence: **`survey` and `adb-close` move into M1**, so Phase 3 runs on zentv's own redacting, allowlisted tool rather than ad hoc `adb` commands. And **M6 becomes Phase 7**, because Phase 6 isn't pursued (decision D7).

| M | Phase | Scope | Acceptance criteria |
|---|---|---|---|
| **M1** | 2→3 | Scaffold, transport, `commands.py`, `refuse.py`, device identity + read-only gate, safety engine, redaction, `survey`, `privacy` (read-only), `adb-close`, FakeDevice, fake `adb`, CI, hooks, AGENTS.md/CLAUDE.md, README stub, THIRD_PARTY_NOTICES | All §5 tests that apply to M1 pass. `ruff` is clean. CI is green with SHA-pinned actions and `contents: read`. gitleaks is clean. `zentv survey` against the fake TV writes a redacted `survey.json`. `adb-close` passes its fake-socket tests. **No state-changing constructor except `adb_network_off` is reachable from the CLI.** |
| — | 3 | Device discovery, **TCL first**, then Sony (read-only, `survey` + `adb-close`) | Each profile has confirmed `match` + fingerprint, a feature map, a Wi-Fi owner, the tuner state, and on TCL the app-op names and app-button keycodes. Redacted `survey.json` committed. Draft `debloat.yaml` with every disagreement with cleanyourtv explained. **⛔ Checkpoint 4.** |
| **M2** | 4 | `plan`, `snapshot`, `apply`, `restore`, `check`, `smoke-test` | All §5 round-trip, snapshot, gate and refusal tests pass. Then the supervised run per TV, TCL first: snapshot → dry-run → OK → apply → reboot → smoke test → `adb-close`. Smoke tests pass on both TVs. A restore rehearsal on each TV reads back clean. The restore command is shown before we finish. |
| **M3** | 5 | **M3a spike** per TV, TCL first: `spike` APK, helper in `:homekey`, test activity | A written spike report per TV, a results matrix over every M3a test in the prompt (real-remote Home, background race with and without re-check, held Volume, TCL `com.tcl.guard` package-vs-process kill and `:homekey` survival, consume vs pass-through, TCL with and without the app-op), and a go/no-go per TV. A no-go stops work for that TV and brings options. |
| **M4** | 5 | Launcher MVP: app row/grid, favorites, hide, `set-home`, `enable-home-key` (with TCL app-op), CrashGuard, `revert`, `docs/launcher-permissions.md` | `coreRelease` APK < 3 MB (revised 2026-11-27: the five reused 1080p scenes are ~2.0 MB of already-compressed JPEG/WebP). Cold start < 500 ms (`am start -W`, median of 5) on both TVs. The merged-manifest check passes (no `INTERNET`). `revert` reads back HOME, accessibility and app-ops clean on both TVs. CrashGuard unit tests (including "trim kill isn't a crash"). Launcher smoke test passes per TV. |
| **M5** | 5 | Finish: scene + cut-out, glass clock, pills, themes JSON, `weather` flavour, keep-watching without `READ_TV_LISTINGS` | `core` still has no `INTERNET` and stays < 3 MB. `weather` reaches only Open-Meteo (network security config + test). No jank regression against M4 (`dumpsys gfxinfo`, janky-frame share). |
| **M6** | 7 | `bench` across three states per TV; `docs/restore.md`, `troubleshooting.md`, `smoke-test.md`; README table | 3 runs per state, median reported. The table is in the README. Docs walk through restore from a fresh shell on each TV. |

## 8. Decisions for Checkpoint 3

| # | Decision | My recommendation |
|---|---|---|
| D1 | Python layout | **Decided:** flat `zenctl/` package at the repo root; command stays `zentv` |
| D2 | YAML parsing | PyYAML (`safe_load` only, hash-locked), rather than converting the data files to TOML |
| D3 | ADB transport | Google platform-tools `adb` via subprocess. **Needs `brew install --cask android-platform-tools` on your Mac (your OK first).** |
| D4 | Launcher `applicationId` | A reverse domain you control (for example `io.github.<your-github-user>.zentv`). Your call, since it's public and permanent. |
| D5 | Installing zentv's own APK | Add to rule 6: `adb install` of zentv's own APK only (package + signer checked), normal install path, never `-g` or bypass flags. Revert never uninstalls (rule 5). |
| D6 | Themes beyond the bundled ones | Defer to M5. Then either bundle them all in the APK, or allow `adb push` into zentv's own app-specific folder (another rule 6 addition) |
| D7 | Milestone shape | `survey`/`adb-close` move into M1. M6 = Phase 7. |
| D8 | Hooks | A plain `scripts/hooks/pre-commit` (gitleaks + ruff) instead of the `pre-commit` framework, which would be one fewer third-party tool |
| D9 | JDK 17 for `launcher/` | Needed from M3 on. Not installed (`java_home` finds none). Install Temurin 17 with Homebrew when we get there (your OK first). |
| D10 | Commits for `devices/` and `safety/` | Commit them at the start of M1, once you've sent the TCL answers and made the held decisions |
