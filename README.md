# zentv

*Make your Android TV calm again: debloat, block ads and telemetry, and swap in a fast, clutter-free launcher over Wi-Fi ADB. No root, fully reversible.*

**Status: M2 (debloat engine).** Read-only commands, plus `apply`/`restore`, which are dry-runs unless you pass `--yes`, and only work on a TV whose profile you've confirmed:

| Command | What it does |
|---|---|
| `zentv connect <tv-ip>` / `zentv pair <tv-ip>:<port>` | Connect over Wi-Fi ADB (port 5555, or Android 11+ Wireless debugging) |
| `zentv identify` | Which TV this is, which device profile matches, and whether zentv may change anything (read-only until Phase 3 confirms the profile) |
| `zentv survey [--out FILE]` | Read-only inventory, written **redacted** (no serials, MACs, IPs, SSIDs). Default: `~/.zentv/surveys/` |
| `zentv privacy` | Read-only: Private DNS, accessibility services, notification listeners, usage access, device admins, sideloaded apps |
| `zentv safety PKG…` | Would zentv refuse these packages? (`--offline --brand --device` works without a TV) |
| `zentv adb-close [--yes]` | Switch network ADB off and verify from your Mac that it's closed. A dry-run without `--yes`. |
| `zentv plan` | What `apply` would change, from `devices/<profile>/debloat.yaml` (read-only) |
| `zentv apply [--yes]` | Record a snapshot first, then disable/un-hide one package per call, reading each back |
| `zentv restore [SNAPSHOT] [--yes]` | Replay this TV's snapshot and read every package back. Works even after a firmware update. |
| `zentv check` / `zentv snapshots` | Read-only drift report / list this TV's snapshots |
| `zentv smoke-test <device>` | Interactive checklist from the profile. Any failure means restore. |

## Install (for development)

```sh
brew install --cask android-platform-tools   # Google's adb
uv sync && scripts/install-hooks.sh
uv run zentv --help
```

## How it stays safe

- Dry-run by default. Commands are allowlisted. There's a hard denylist (`safety/never_disable.yaml`) with no override.
- Every value is recorded before a change and read back after it.
- Profiles are read-only until confirmed, and closing ADB is always the last step.
- Design: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Audit of the projects that inspired it: [docs/audit/](docs/audit/).

## License

MIT. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
