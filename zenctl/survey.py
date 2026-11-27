"""Read-only inventory of a TV → redacted JSON (Phase 3). Sends only read-only commands."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from . import __version__, redact
from . import commands as C
from .adb import Session
from .device import IDENTITY_PROPS, Identity

PKG_LINE = re.compile(
    r"^package:(?P<name>[A-Za-z0-9_.]+)(?:\s+installer=(?P<installer>\S+))?(?:\s+uid:(?P<uid>\d+))?"
)
TV_INPUT = re.compile(r"TvInputInfo\{id=([^,}\s]+)")
WIFI_OWNER = re.compile(r"\b(creatorName|cname|lastUpdateName)=([A-Za-z0-9_.:]+)")
ACTIVE_NET = re.compile(r"Active default network:\s*(\S+)")
MEM = re.compile(r"^(MemTotal|MemAvailable):\s+(\d+)\s+kB", re.MULTILINE)
APPOPS_PROBE = ("APP_AUTO_START", "AUTO_START")
USER0_STATE = re.compile(r"User 0:.*?\binstalled=(true|false)\b.*?\bhidden=(true|false)\b.*?\benabled=(\d+)")
UNKNOWN_OP = re.compile(r"Unknown operation", re.IGNORECASE)  # "No operations." means known but unset
NAI_TYPE = re.compile(r"NetworkAgentInfo\{.*?type: ([A-Z_]+).*?network\{(\d+)\}")


def _packages(session: Session) -> dict[str, dict[str, Any]]:
    pkgs: dict[str, dict[str, Any]] = {}
    for line in session.read(C.pm_list_packages("-i", "-U")).splitlines():
        m = PKG_LINE.match(line.strip())
        if m:
            pkgs[m["name"]] = {
                "installer": None if m["installer"] in (None, "null") else m["installer"],
                "uid": int(m["uid"]) if m["uid"] else None,
                "enabled": True,
                "system": False,
            }
    for flag, key, value in (("-d", "enabled", False), ("-s", "system", True)):
        for line in session.read(C.pm_list_packages(flag)).splitlines():
            m = PKG_LINE.match(line.strip())
            if m and m["name"] in pkgs:
                pkgs[m["name"]][key] = value
    return dict(sorted(pkgs.items()))


def absent_for_user(session: Session) -> dict[str, dict[str, Any]]:
    """Packages on the system image that user 0 can't see: hidden (`pm hide`) or uninstalled for the user.

    zentv never creates this state (ground rule 5), but a TV can arrive with it from other tools, and
    it must be recorded as the owner's starting state.
    """

    def names(cmd: C.Command) -> set[str]:
        return {m["name"] for ln in session.read(cmd).splitlines() if (m := PKG_LINE.match(ln.strip()))}

    out = {}
    for name in sorted(names(C.pm_list_packages("-u")) - names(C.pm_list_packages())):
        m = USER0_STATE.search(session.read(C.dumpsys("package", name)))
        out[name] = (
            {"installed": m[1] == "true", "hidden": m[2] == "true", "enabled_state": int(m[3])}
            if m
            else {"installed": None, "hidden": None, "enabled_state": None}
        )
    return out


def _active_transport(connectivity: str) -> str | None:
    """The transport of the active default network (WIFI, ETHERNET...), from dumpsys connectivity."""
    m = ACTIVE_NET.search(connectivity)
    if not m:
        return None
    for line in connectivity.splitlines():
        t = NAI_TYPE.search(line)
        if t and t.group(2) == m.group(1):
            return t.group(1)
    return None


def _setting(session: Session, ns: str, key: str) -> str | None:
    v = session.read(C.settings_get(ns, key)).strip()
    return None if v in ("", "null") else v


def appop_names(session: Session) -> dict[str, bool]:
    """Which TCL boot-manager app-op names this build knows (read-only, probes the `android` package)."""
    out = {}
    for op in APPOPS_PROBE:
        res = session.probe(C.appops_get("android", op))
        out[op] = res.returncode == 0 and not UNKNOWN_OP.search(res.stdout + res.stderr)
    return out


def collect(session: Session, ident: Identity, profile: str | None) -> dict[str, Any]:
    connectivity = session.read(C.dumpsys("connectivity"))
    wifi = session.read(C.dumpsys("wifi"))
    meminfo = session.read(C.read_file("/proc/meminfo"))
    data: dict[str, Any] = {
        "schema": 1,
        "zentv": __version__,
        "taken_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "profile": profile,
        "identity": {k: ident.props[k] for k in IDENTITY_PROPS if k in ident.props},
        "soc_guess": ident.soc,
        "home": {
            "resolved": (session.read(C.resolve_home()).strip().splitlines() or [None])[-1],
            "candidates": [ln.strip() for ln in session.read(C.query_home()).splitlines() if "/" in ln],
        },
        "accessibility": {
            "enabled_accessibility_services": _setting(session, "secure", "enabled_accessibility_services"),
            "accessibility_enabled": _setting(session, "secure", "accessibility_enabled"),
        },
        "adb": {k: _setting(session, "global", k) for k in ("adb_enabled", "adb_wifi_enabled")},
        "network": {
            "active_default": (m.group(1) if (m := ACTIVE_NET.search(connectivity)) else None),
            "active_transport": _active_transport(connectivity),
            "wifi_network_owners": sorted({f"{k}={v}" for k, v in WIFI_OWNER.findall(wifi)}),
        },
        "tv_inputs": sorted(set(TV_INPUT.findall(session.read(C.dumpsys("tv_input"))))),
        "memory_kb": {k: int(v) for k, v in MEM.findall(meminfo)},
        "packages": _packages(session),
        "absent_for_user": absent_for_user(session),
    }
    if ident.is_brand("tcl"):
        data["tcl_appop_names"] = appop_names(session)
    return redact.from_props(ident.props).obj(data)
