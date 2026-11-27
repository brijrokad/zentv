"""Identify the connected TV, pick its profile, and decide whether state changes are allowed.

The read-only gate (ARCHITECTURE.md §3.3): state changes need a profile with status `confirmed`
whose `match` block equals the live properties and whose `fingerprint` equals the live build
fingerprint. A firmware update therefore drops the TV back to read-only until re-confirmed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import commands as C
from .adb import Session
from .errors import ZenError

IDENTITY_PROPS = (
    "ro.product.brand",
    "ro.product.manufacturer",
    "ro.product.model",
    "ro.product.device",
    "ro.product.name",
    "ro.product.board",
    "ro.board.platform",
    "ro.hardware",
    "ro.build.fingerprint",
    "ro.build.version.release",
    "ro.build.version.sdk",
    "ro.build.version.incremental",
    "ro.build.version.security_patch",
    "ro.product.cpu.abilist",
    "ro.zygote",
    "ro.tcl.product_type",
    "ro.boot.product.hardware.sku",
)
PROP_LINE = re.compile(r"^\[([^\]]+)\]: \[(.*)\]$")


def parse_getprop(text: str) -> dict[str, str]:
    props = {}
    for line in text.splitlines():
        m = PROP_LINE.match(line.strip())
        if m:
            props[m.group(1)] = m.group(2)
    return props


def soc_of(props: dict[str, str]) -> str:
    plat = (props.get("ro.board.platform") or props.get("ro.hardware") or "").lower()
    if plat.startswith(("mt", "m7", "m5")) or "mediatek" in plat:
        return "mediatek"
    if plat.startswith("rtd") or "realtek" in plat:
        return "realtek"
    if plat.startswith(("meson", "amlogic", "g12", "sm1", "t9", "s9")):
        return "amlogic"
    return "unknown"


@dataclass
class Identity:
    props: dict[str, str]  # full getprop; never written unredacted

    @property
    def brand(self) -> str:
        return (self.props.get("ro.product.brand") or self.props.get("ro.product.manufacturer") or "").lower()

    @property
    def manufacturer(self) -> str:
        return (self.props.get("ro.product.manufacturer") or "").lower()

    @property
    def fingerprint(self) -> str:
        return self.props.get("ro.build.fingerprint", "")

    @property
    def soc(self) -> str:
        return soc_of(self.props)

    def is_brand(self, name: str) -> bool:
        name = name.lower()
        return self.brand == name or self.manufacturer == name

    def summary(self) -> dict[str, str]:
        return {k: self.props[k] for k in IDENTITY_PROPS if k in self.props}


def identify(session: Session) -> Identity:
    return Identity(parse_getprop(session.read(C.getprop())))


@dataclass
class Profile:
    name: str
    path: Path
    status: str
    brand: str
    soc: str
    match: dict[str, str] = field(default_factory=dict)
    fingerprint: str | None = None

    def matches(self, ident: Identity) -> bool:
        return bool(self.match) and all(ident.props.get(k) == v for k, v in self.match.items())

    def allows_changes(self, ident: Identity) -> bool:
        return (
            self.status == "confirmed"
            and self.matches(ident)
            and bool(self.fingerprint)
            and self.fingerprint == ident.fingerprint
        )


def load_profiles(devices_dir: Path) -> list[Profile]:
    out = []
    for p in sorted(devices_dir.glob("*/profile.yaml")):
        data = yaml.safe_load(p.read_text()) or {}
        status = data.get("status", "unverified")
        if status not in ("unverified", "confirmed"):
            raise ZenError(f"{p}: status must be 'unverified' or 'confirmed'")
        match = data.get("match") or {}
        if not isinstance(match, dict) or not all(isinstance(v, str) for v in match.values()):
            raise ZenError(f"{p}: match must map property names to strings")
        out.append(
            Profile(
                name=p.parent.name,
                path=p,
                status=status,
                brand=str(data.get("brand", "")).lower(),
                soc=str(data.get("soc", "unknown")).lower(),
                match=match,
                fingerprint=data.get("fingerprint"),
            )
        )
    return out


def select_profile(profiles: list[Profile], ident: Identity) -> Profile | None:
    hits = [p for p in profiles if p.matches(ident)]
    if len(hits) > 1:
        raise ZenError("more than one device profile matches this TV: " + ", ".join(p.name for p in hits))
    return hits[0] if hits else None


def gate(profile: Profile | None, ident: Identity) -> tuple[bool, str]:
    """(allowed, reason) for state changes on this TV."""
    if profile is None:
        return False, "no device profile matches this TV (read-only)"
    if profile.status != "confirmed":
        return False, f"profile {profile.name} is {profile.status} (read-only until Phase 3 confirms it)"
    if not profile.fingerprint or profile.fingerprint != ident.fingerprint:
        return (
            False,
            f"firmware fingerprint differs from profile {profile.name} (read-only until re-confirmed)",
        )
    return True, f"profile {profile.name} confirmed for this firmware"
