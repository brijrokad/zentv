# zentv

*Make your Android TV calm again: debloat, block ads and telemetry, and swap in a fast, clutter-free launcher over Wi-Fi ADB. No root, fully reversible.*

**Status: M1 (foundation). Nothing here changes a TV yet.** The current commands are read-only, apart from `adb-close`, which switches network ADB **off**:

| Command | What it does |
|---|---|
| `zentv connect <tv-ip>` / `zentv pair <tv-ip>:<port>` | Connect over Wi-Fi ADB (port 5555, or Android 11+ Wireless debugging) |
| `zentv identify` | Which TV this is, which device profile matches, and whether zentv may change anything (read-only until Phase 3 confirms the profile) |
| `zentv survey [--out FILE]` | Read-only inventory, written **redacted** (no serials, MACs, IPs, SSIDs). Default: `~/.zentv/surveys/` |
| `zentv privacy` | Read-only: Private DNS, accessibility services, notification listeners, usage access, device admins, sideloaded apps |
| `zentv safety PKG…` | Would zentv refuse these packages? (`--offline --brand --device` works without a TV) |
| `zentv adb-close [--yes]` | Switch network ADB off and verify from your Mac that it's closed. A dry-run without `--yes`. |

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
