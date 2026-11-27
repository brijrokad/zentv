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

from . import __version__, adbclose, device, launcher, paths, privacy, redact, safety, smoke, survey
from . import apply as engine
from . import plan as planner
from . import snapshot as snapshots
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


def _need_profile(c: Ctx) -> device.Profile:
    if c.profile is None:
        raise ZenError("no device profile matches this TV; run Phase 3 first")
    return c.profile


def _plan(c: Ctx, include: list[str] | None) -> planner.Plan:
    prof = _need_profile(c)
    policy = safety.load(paths.safety_file())
    debloat = planner.load_debloat(Path(prof.path).parent / "debloat.yaml", prof)
    return planner.build(c.session, c.ident, prof, policy, debloat, set(include or []))


def _print_plan(p: planner.Plan) -> None:
    print(f"plan {p.digest} for {p.device}")
    for a in p.actions:
        print(f"  {a.op:8} {a.package:44} {a.reason[:70]}")
    if not p.actions:
        print("  (nothing to change)")
    for pkg, why in p.skipped:
        print(f"  skip     {pkg:44} {why}")


def cmd_plan(args: argparse.Namespace) -> int:
    c = Ctx(args)
    _print_plan(_plan(c, args.include))
    print(f"state changes on this TV: {'allowed' if c.allowed else 'read-only'} ({c.gate_reason})")
    c.write_log("plan")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    c = Ctx(args, yes=args.yes)
    p = _plan(c, args.include)
    _print_plan(p)
    try:
        res = engine.apply(c.session, c.ident, p, settle_s=args.settle)
    finally:
        c.write_log("apply")
    if not args.yes:
        print("DRY RUN (nothing sent). With --yes zentv would first write a snapshot, then run:")
        for cmd in c.session.planned:
            pre = c.session.recorded.get(cmd.records[0].key)
            print(f"  adb shell {cmd.shell_string()}    # was: {pre}")
        return 0
    if res.snapshot:
        print(f"snapshot: {res.snapshot.path}")
        print(f"applied {len(res.sent)} change(s), each read back.")
        print("Next: reboot, run `zentv smoke-test <device>`, then `zentv adb-close --yes`.")
        print(f"To undo: zentv restore {res.snapshot.path} --yes")
    return 0


def _snapshot_arg(c: Ctx, path: str | None) -> snapshots.Snapshot:
    p = Path(path) if path else snapshots.latest(snapshots.device_key(c.ident))
    if not p:
        raise ZenError("no snapshot for this TV")
    return snapshots.load(p)


def cmd_restore(args: argparse.Namespace) -> int:
    c = Ctx(args, yes=args.yes)
    snap = _snapshot_arg(c, args.snapshot)
    try:
        cmds, mismatches, notes = engine.restore(c.session, c.ident, snap)
    finally:
        c.write_log("restore")
    for n in notes:
        print(f"note: {n}")
    if not args.yes:
        print(f"DRY RUN (nothing sent). With --yes zentv would replay {snap.path}:")
        for s in cmds:
            print(f"  adb shell {s}")
        return 0
    if mismatches:
        print("RESTORE INCOMPLETE. Read-back mismatches:")
        for m in mismatches:
            print(f"  {m.package}: expected {m.expected}, found {m.found}")
        return 7
    print(f"restored {len(cmds)} package(s); every recorded package reads back as before.")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    c = Ctx(args)
    snap = _snapshot_arg(c, args.snapshot)
    drift = engine.check(c.session, snap)
    c.write_log("check")
    for d in drift:
        print(f"DRIFT  {d}")
    print("no drift" if not drift else "drift is reported only; zentv never re-applies (rule 8)")
    return 1 if drift else 0


def cmd_snapshots(args: argparse.Namespace) -> int:
    c = Ctx(args)
    for p in snapshots.all_for(snapshots.device_key(c.ident)):
        s = snapshots.load(p)
        print(f"{p}  {s.created_utc}  {len(s.actions)} action(s)")
    return 0


def cmd_smoke(args: argparse.Namespace) -> int:
    profiles = device.load_profiles(paths.devices_dir())
    prof = next((p for p in profiles if p.name == args.device), None)
    if prof is None:
        raise ZenError(f"unknown device profile {args.device!r}")
    failed, out = smoke.run(prof)
    print(f"results: {out}")
    if failed:
        print("SMOKE TEST FAILED, so restore: `zentv restore --yes` (latest snapshot for this TV).")
        return 8
    print("smoke test passed.")
    return 0


def cmd_launcher(args: argparse.Namespace) -> int:
    action = args.launcher_action
    if action == "status":
        c = Ctx(args)
        _print_json(launcher.status(c.session, c.ident))
        c.write_log("launcher-status")
        return 0
    c = Ctx(args, yes=args.yes)
    try:
        if action == "install":
            apk = Path(args.apk) if args.apk else launcher.default_apk()
            cmd = launcher.install(c.session, apk)
            pre = c.session.recorded.get(cmd.records[0].key)
            if not args.yes:
                print(
                    f"DRY RUN (nothing sent). With --yes zentv would run:\n  adb {cmd.shell_string()}"
                    f"    # {cmd.records[0].key} was: {pre or 'not installed'}"
                )
                return 0
            print(
                f"installed {cmd.records[0].key} (read back). zentv never uninstalls it: remove it yourself "
                "in Settings > Apps when you're done."
            )
            return 0
        if action == "enable-home-key":
            cmds, snap = launcher.enable_home_key(c.session, c.ident)
            if not args.yes:
                print("DRY RUN (nothing sent). With --yes zentv would write a launcher snapshot, then run:")
                for cmd in cmds:
                    was = c.session.recorded.get(cmd.records[0].key)
                    print(f"  adb shell {cmd.shell_string()}    # was: {was}")
                return 0
            print(
                f"helper enabled (read back). snapshot: {snap.path if snap else '-'}\n"
                "Undo: zentv launcher revert --yes"
            )
            return 0
        if action == "revert":
            snap = launcher.latest_launcher_snapshot(c.ident)
            if snap is None:
                raise ZenError("no launcher snapshot for this TV")
            cmds, mismatches = launcher.revert(c.session, c.ident, snap)
            if not args.yes:
                print(f"DRY RUN (nothing sent). With --yes zentv would put back {snap.path}:")
                for cmd in cmds:
                    print(f"  adb shell {cmd.shell_string()}")
                return 0
            if mismatches:
                print("REVERT INCOMPLETE: " + "; ".join(mismatches))
                return 7
            print("reverted: the helper is off and every recorded value reads back as before.")
            return 0
    finally:
        c.write_log(f"launcher-{action}")
    raise ZenError(f"unknown launcher action {action}")


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

    s = sub.add_parser(
        "plan", help="what apply would change on this TV, from devices/<profile>/debloat.yaml (read-only)"
    )
    s.add_argument("--include", action="append", help="add a default-off or high-risk target by name")
    s.set_defaults(func=cmd_plan)

    s = sub.add_parser("apply", help="snapshot, then disable/unhide per the plan (dry-run without --yes)")
    s.add_argument("--yes", action="store_true", help="actually send the changes")
    s.add_argument("--include", action="append", help="add a default-off or high-risk target by name")
    s.add_argument(
        "--settle", type=float, default=25.0, help="seconds to wait after the last change (default 25)"
    )
    s.set_defaults(func=cmd_apply)

    s = sub.add_parser(
        "restore", help="replay a snapshot of this TV and read it back (dry-run without --yes)"
    )
    s.add_argument("snapshot", nargs="?", help="snapshot file (default: this TV's latest)")
    s.add_argument("--yes", action="store_true")
    s.set_defaults(func=cmd_restore)

    s = sub.add_parser("check", help="read-only drift report against a snapshot (default: latest)")
    s.add_argument("snapshot", nargs="?")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("snapshots", help="list this TV's snapshots")
    s.set_defaults(func=cmd_snapshots)

    s = sub.add_parser("launcher", help="zentv's own APK and its Home helper (M3a spike)")
    lsub = s.add_subparsers(dest="launcher_action", required=True)
    li = lsub.add_parser("install", help="adb install -r zentv's own APK (dry-run without --yes)")
    li.add_argument("--apk", help="default: launcher/app/build/outputs/apk/spike/app-spike.apk")
    li.add_argument("--yes", action="store_true")
    le = lsub.add_parser("enable-home-key", help="snapshot, then enable the Home helper (+ TCL app-op)")
    le.add_argument("--yes", action="store_true")
    lr = lsub.add_parser("revert", help="disable the helper and put back what enable-home-key changed")
    lr.add_argument("--yes", action="store_true")
    lsub.add_parser("status", help="read-only: installed, helper enabled/bound, TCL app-op")
    s.set_defaults(func=cmd_launcher)

    s = sub.add_parser(
        "smoke-test", help="interactive checklist from the device profile; any failure means restore"
    )
    s.add_argument("device", help="device profile name, e.g. tcl-g03-beyondtv4")
    s.set_defaults(func=cmd_smoke)
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
