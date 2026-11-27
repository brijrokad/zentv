"""apply, restore and check (ARCHITECTURE.md §3.5).

apply:   record pre-state → write snapshot (before any change) → one change per call → read each back.
restore: replay a snapshot of THIS TV in reverse → read back → report every mismatch.
check:   read-only drift report against a snapshot's intended state. Never fixes anything (rule 8).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from . import commands as C
from . import snapshot as S
from .adb import Session
from .device import Identity
from .errors import Refused, ZenError
from .plan import Plan

DISABLED_STATES = {"2", "3", "4"}


def _state(session: Session, pkg: str) -> dict[str, str]:
    return C.parse_state(C.package_state(session.read(C.dumpsys("package", pkg))))


def commands_for(plan: Plan) -> list[C.Command]:
    out = []
    for a in plan.actions:
        if a.op == "disable":
            out.append(C.disable_user(a.package))
        elif a.op == "unhide":
            out.append(C.unhide(a.package, plan.approved_unhide))
        else:
            raise ZenError(f"unknown plan action {a.op!r}")
    return out


@dataclass
class ApplyResult:
    snapshot: S.Snapshot | None
    sent: list[str]


def apply(
    session: Session, ident: Identity, plan: Plan, settle_s: float = 25.0, say: Callable[[str], None] = print
) -> ApplyResult:
    cmds = commands_for(plan)
    if not cmds:
        say("Nothing to do: every planned change is already in place.")
        return ApplyResult(None, [])
    existing = S.find(S.device_key(ident), plan.digest)
    if existing:  # first record wins: the original pre-state, not today's half-applied state
        session.recorded.update(S.load(existing).records)
    for cmd in cmds:
        session.record(cmd)
    snap = S.create(ident, plan, session.recorded) if session.yes else None
    sent = []
    for cmd, action in zip(cmds, plan.actions, strict=True):
        try:
            session.change(cmd)
        except ZenError as e:
            if not session.yes:
                raise
            done = f"{len(sent)} of {len(cmds)} change(s) were made and read back before this. "
            raise type(e)(
                f"{e}\nStopped. {done}Restore with: zentv restore {snap.path if snap else ''} --yes"
            ) from e
        if not session.yes:
            continue
        st = _state(session, action.package)
        ok = st.get("enabled") in DISABLED_STATES if action.op == "disable" else st.get("hidden") == "false"
        if not ok:
            raise ZenError(
                f"read-back failed after `{cmd.shell_string()}` (now {st or 'unknown'}). "
                f"Stopped. Restore with: zentv restore {snap.path if snap else ''} --yes"
            )
        sent.append(cmd.shell_string())
        if snap is not None:
            S.mark_done(snap, action.op, action.package)
    if session.yes and settle_s:
        say(f"Waiting {settle_s:.0f} s so the package state is written to disk before any reboot ...")
        time.sleep(settle_s)
    return ApplyResult(snap, sent)


@dataclass
class Mismatch:
    package: str
    expected: str
    found: str


def restore(
    session: Session, ident: Identity, snap: S.Snapshot
) -> tuple[list[str], list[Mismatch], list[str]]:
    """Returns (commands, mismatches, notes). With session.yes False it only plans (dry-run)."""
    if snap.device_key != S.device_key(ident):
        raise Refused("this snapshot was taken on a different TV; nothing was sent")
    session.recorded.update(snap.records)
    cmds, notes = [], []
    for a in snap.actions:
        if not a.get("done", True):
            notes.append(f"{a['package']}: planned {a['op']} was never completed; nothing to undo")
    for a in reversed(S.completed(snap)):
        pkg = a["package"]
        pre = C.parse_state(snap.records.get(pkg))
        if a["op"] == "unhide":
            notes.append(
                f"{pkg}: an un-hide was planned; restore never hides anything (zentv has no `pm hide`)"
            )

            continue
        if pre.get("enabled") in DISABLED_STATES:
            notes.append(f"{pkg}: was already disabled before zentv; left as is")
            continue
        cmd = C.enable(pkg, for_restore=True)
        session.change(cmd)
        cmds.append(cmd.shell_string())
    mismatches = verify(session, snap) if session.yes else []
    return cmds, mismatches, notes


def verify(session: Session, snap: S.Snapshot) -> list[Mismatch]:
    """Read back every package zentv disabled and compare with its pre-state class (enabled/disabled)."""
    out = []
    for a in S.completed(snap):
        if a["op"] != "disable":
            continue
        pkg = a["package"]
        pre = C.parse_state(snap.records.get(pkg)).get("enabled")
        now = _state(session, pkg).get("enabled")
        want_disabled = pre in DISABLED_STATES
        if (now in DISABLED_STATES) != want_disabled:
            out.append(Mismatch(pkg, "disabled" if want_disabled else "enabled", f"enabled={now}"))
    return out


def check(session: Session, snap: S.Snapshot) -> list[str]:
    """Drift since `snap` was applied. Read-only; reports, never fixes."""
    drift = []
    for a in S.completed(snap):
        st = _state(session, a["package"])
        if a["op"] == "disable" and st.get("enabled") not in DISABLED_STATES:
            drift.append(f"{a['package']}: zentv disabled it, now enabled={st.get('enabled')}")
        if a["op"] == "unhide" and st.get("hidden") != "false":
            drift.append(f"{a['package']}: zentv un-hid it, now hidden={st.get('hidden')}")
    return drift
