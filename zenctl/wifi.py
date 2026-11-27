"""Stale saved Wi-Fi entries (owner-approved one-time exception, TCL 2026-11-27).

Only entries the owner named, never the network in use, never one marked most-recently-connected.
Deleting a saved entry can't be undone by zentv; the network can always be re-added in Settings.
Network names are never recorded or printed.
"""

from __future__ import annotations

from . import commands as C
from .adb import Session
from .errors import Refused, ZenError


def entries(session: Session) -> tuple[dict[int, dict[str, str]], int | None]:
    out = session.read(C.dumpsys("wifi"))
    return C.wifi_entries(out), C.wifi_connected_id(out)


def forget(session: Session, ids: list[int], approved: frozenset[int]) -> list[C.Command]:
    found, connected = entries(session)
    for i in ids:
        if i not in found:
            raise ZenError(f"no saved Wi-Fi entry {i} on this TV")
        if i == connected or found[i]["recent"] == "true":
            raise Refused(f"Wi-Fi entry {i} is the network in use; zentv never removes it")
    cmds = [C.wifi_forget_network(i, approved) for i in ids]
    for cmd in cmds:
        session.record(cmd)
    for cmd in cmds:
        session.change(cmd)
    if session.yes:
        left, _ = entries(session)
        still = [i for i in ids if i in left]
        if still:
            raise ZenError(f"read-back: entries {still} are still saved")
    return cmds
