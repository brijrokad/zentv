"""Read-only privacy report: who can watch, listen, or administer this TV. Changes nothing."""

from __future__ import annotations

import re
from typing import Any

from . import commands as C
from .adb import Session

STORE_INSTALLERS = frozenset({"com.android.vending", "com.google.android.feedback", "com.amazon.venezia"})
QUERY_OP_LINE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_.]+)\s*$")
ADMIN = re.compile(r"admin=ComponentInfo\{([^}]+)\}")


def _setting(session: Session, ns: str, key: str) -> str | None:
    v = session.read(C.settings_get(ns, key)).strip()
    return None if v in ("", "null") else v


def _split_components(v: str | None) -> list[str]:
    return [x for x in (v or "").split(":") if x]


def _holders(session: Session, op: str) -> list[str] | None:
    res = session.probe(C.appops_query_op(op, "allow"))
    if res.returncode != 0:
        return None
    return sorted({m.group(1) for ln in res.stdout.splitlines() if (m := QUERY_OP_LINE.match(ln))})


def report(session: Session, packages: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "private_dns": {
            "mode": _setting(session, "global", "private_dns_mode"),
            "specifier": _setting(session, "global", "private_dns_specifier"),
        },
        "accessibility_services": _split_components(
            _setting(session, "secure", "enabled_accessibility_services")
        ),
        "notification_listeners": _split_components(
            _setting(session, "secure", "enabled_notification_listeners")
        ),
        "usage_access": _holders(session, "GET_USAGE_STATS"),
        "draw_over_apps": _holders(session, "SYSTEM_ALERT_WINDOW"),
        "device_admins": sorted(set(ADMIN.findall(session.read(C.dumpsys("device_policy"))))),
    }
    if packages is not None:
        out["sideloaded"] = sorted(
            n
            for n, p in packages.items()
            if not p.get("system") and p.get("installer") not in STORE_INSTALLERS
        )
    return out
