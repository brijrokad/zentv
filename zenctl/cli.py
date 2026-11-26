"""`zentv` command line. M1: connect, pair, identify, survey, privacy, safety, adb-close.

Every state-changing subcommand is a dry-run unless --yes is given (ground rule 4).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from . import __version__, adbclose, device, paths, privacy, redact, safety, survey
from .adb import AdbTransport, Session, connected_devices, find_adb, run_host
from .errors import AdbError, ZenError


def _pick_serial(explicit: str | None) -> str:
    serial = explicit or os.environ.get("ZENTV_SERIAL")
    if serial:
        return serial
    ready = [s for s, state in connected_devices() if state == "device"]
    if len(ready) == 1:
        return ready[0]
    if not ready:
        raise AdbError("no TV connected. Run `zentv connect <tv-ip>` (or `zentv pair`) first")
    raise AdbError("more than one device connected; pass --serial")


class Ctx:
    """An open session with the TV's identity, profile and the read-only gate applied."""

    def __init__(self, args: argparse.Namespace, yes: bool = False) -> None:
        self.serial = _pick_serial(args.serial)
        self.session = Session(AdbTransport(self.serial), yes=yes)
        self.ident = device.identify(self.session)
        self.profiles = device.load_profiles(paths.devices_dir())
        self.profile = device.select_profile(self.profiles, self.ident)
        self.allowed, self.gate_reason = device.gate(self.profile, self.ident)
        self.session.state_changes_allowed = self.allowed
        self.redactor = redact.from_props(self.ident.props)

    def same_brand_profiles(self) -> list[str]:
        return [p.name for p in self.profiles if p.brand and self.ident.is_brand(p.brand)]

    def write_log(self, name: str) -> None:
        log = paths.private_subdir("logs") / f"{_stamp()}-{name}.log"
        log.write_text("\n".join(self.redactor.text(line) for line in self.session.log) + "\n")
        log.chmod(0o600)


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _print_json(obj: object) -> None:
    print(json.dumps(obj, indent=2, sort_keys=False))


def _host_of(serial: str) -> str | None:
    if ":" in serial and not serial.startswith("["):
        return serial.rsplit(":", 1)[0]
    return None


# ---- subcommands -----------------------------------------------------------------------------


def cmd_connect(args: argparse.Namespace) -> int:
    target = args.target if ":" in args.target else f"{args.target}:5555"
    res = run_host([find_adb(), "connect", target], 20)
    print((res.stdout or res.stderr).strip())
    return 0 if "connected" in res.stdout and "cannot" not in res.stdout else 1


def cmd_pair(args: argparse.Namespace) -> int:
    print("Type the 6-digit code shown under Wireless debugging > Pair device with pairing code.")
    import subprocess

    return subprocess.call([find_adb(), "pair", args.target])


def cmd_identify(args: argparse.Namespace) -> int:
    c = Ctx(args)
    _print_json(
        {
            "identity": c.redactor.obj(c.ident.summary()),
            "brand": c.ident.brand,
            "soc_guess": c.ident.soc,
            "profile": c.profile.name if c.profile else None,
            "state_changes": "allowed" if c.allowed else "read-only",
            "why": c.gate_reason,
        }
    )
    c.write_log("identify")
    return 0


def cmd_survey(args: argparse.Namespace) -> int:
    c = Ctx(args)
    data = survey.collect(c.session, c.ident, c.profile.name if c.profile else None)
    out = Path(args.out) if args.out else paths.private_subdir("surveys") / f"{_stamp()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n")
    print(f"survey written (redacted): {out}")
    print(
        f"packages: {len(data['packages'])}, disabled: "
        f"{sum(1 for p in data['packages'].values() if not p['enabled'])}"
    )
    c.write_log("survey")
    return 0


def cmd_privacy(args: argparse.Namespace) -> int:
    c = Ctx(args)
    pk = survey._packages(c.session)
    _print_json(c.redactor.obj(privacy.report(c.session, pk)))
    c.write_log("privacy")
    return 0


def cmd_safety(args: argparse.Namespace) -> int:
    policy = safety.load(paths.safety_file())
    if args.offline:
        profiles = device.load_profiles(paths.devices_dir())
        same = [p.name for p in profiles if p.brand == (args.brand or "").lower()]
        ctx = safety.context_for(args.brand or "", args.soc or "", args.device, same)
        print("offline: static entries and name globs only (HOME/PERSISTENT need a connected TV)")
    else:
        c = Ctx(args)
        ctx = safety.context_for(
            c.ident.brand,
            c.ident.soc,
            c.profile.name if c.profile else None,
            c.same_brand_profiles(),
            session=c.session,
            packages=args.packages,
        )
        c.write_log("safety")
    refused = 0
    for pkg in args.packages:
        r = safety.check_package(policy, ctx, pkg)
        if r:
            refused += 1
            print(f"REFUSED  {r}")
        elif reason := safety.high_risk_reason(policy, ctx, pkg):
            print(f"HIGH RISK {pkg}: never in a default plan; name it explicitly. {reason}")
        else:
            print(f"allowed  {pkg} (not on the hard denylist; Phase 3/Checkpoint 4 still decide)")
    return 3 if refused else 0


def cmd_adb_close(args: argparse.Namespace) -> int:
    host = args.host
    if not args.verify_only:
        c = Ctx(args, yes=args.yes)
        host = host or _host_of(c.serial)
        cmds = adbclose.switch_off(c.session, usb_debugging_too=not args.keep_usb_debugging)
        c.write_log("adb-close")
        if not args.yes:
            print("DRY RUN (nothing sent). With --yes zentv would run, in order:")
            for cmd in cmds:
                print(
                    f"  adb shell {cmd.shell_string()}    # was: {c.session.recorded.get(cmd.records[0].key)}"
                )
            print("Then it verifies from this Mac that network ADB is closed.")
            return 0
        run_host([find_adb(), "disconnect", c.serial], 10)
    if not host:
        print("No host to verify: pass --host <tv-ip> (USB-connected TVs can't be checked over the network).")
        return 1
    results = adbclose.verify(host, args.port)
    for r in results:
        print(f"{host}:{r.port:<6} {r.state:<8} {r.detail}")
    if all(r.ok for r in results):
        print("ADB is closed.")
        return 0
    print(
        "ADB is NOT confirmed closed. On the TV, switch off USB debugging, Network debugging and Wireless "
        "debugging, then run `zentv adb-close --verify-only --host <tv-ip>` again."
    )
    return 1


# ---- parser ----------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="zentv", description="Calm your Android TV: rootless, reversible, dry-run by default."
    )
    p.add_argument("--version", action="version", version=f"zentv {__version__}")
    p.add_argument(
        "--serial", help="adb serial (ip:port); default: $ZENTV_SERIAL or the only connected device"
    )
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("connect", help="adb connect <tv-ip>[:port] (port 5555 by default)")
    s.add_argument("target")
    s.set_defaults(func=cmd_connect)

    s = sub.add_parser("pair", help="adb pair <tv-ip>:<pairing-port> (Wireless debugging, Android 11+)")
    s.add_argument("target")
    s.set_defaults(func=cmd_pair)

    s = sub.add_parser(
        "identify", help="who is this TV, which profile matches, may zentv change anything (read-only)"
    )
    s.set_defaults(func=cmd_identify)

    s = sub.add_parser("survey", help="read-only inventory, written redacted (default: ~/.zentv/surveys/)")
    s.add_argument("--out", help="where to write the redacted JSON (e.g. devices/<device>/survey.json)")
    s.set_defaults(func=cmd_survey)

    s = sub.add_parser("privacy", help="read-only privacy report")
    s.set_defaults(func=cmd_privacy)

    s = sub.add_parser("safety", help="would zentv refuse these packages? (read-only)")
    s.add_argument("packages", nargs="+")
    s.add_argument(
        "--offline", action="store_true", help="no TV: evaluate static entries for --brand/--soc/--device"
    )
    s.add_argument("--brand")
    s.add_argument("--soc")
    s.add_argument("--device", help="device profile directory name")
    s.set_defaults(func=cmd_safety)

    s = sub.add_parser(
        "adb-close", help="switch network ADB off and verify it from this Mac (dry-run without --yes)"
    )
    s.add_argument("--yes", action="store_true", help="actually send the switch-off")
    s.add_argument("--host", help="TV address to verify (default: from the adb serial)")
    s.add_argument("--port", type=int, action="append", help="extra port to verify (repeatable)")
    s.add_argument("--keep-usb-debugging", action="store_true", help="switch off Wireless debugging only")
    s.add_argument("--verify-only", action="store_true", help="send nothing; only check the ports")
    s.set_defaults(func=cmd_adb_close)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ZenError as e:
        print(f"zentv: {e}", file=sys.stderr)
        return e.exit_code


if __name__ == "__main__":
    sys.exit(main())
