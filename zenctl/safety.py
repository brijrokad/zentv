"""safety/never_disable.yaml: the hard denylist (ground rules 5 and 7, ARCHITECTURE.md §3.4).

There is no override. A refusal names the group, the entry or rule, and the reason.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import commands as C
from .adb import Session
from .errors import ZenError

SCOPE_KEYS = frozenset({"brand", "soc", "device"})
KNOWN_CHECKS = frozenset({"answers_home", "persistent_flag", "name_glob"})
PERSISTENT_RE = re.compile(r"(pkgFlags|flags)=\[[^\]]*\bPERSISTENT\b")
BRIEF_COMPONENT_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_.]*)/[A-Za-z0-9_.$]+\s*$")


@dataclass(frozen=True)
class Group:
    id: str
    scope: str | dict[str, str]
    reason: str
    source: str
    packages: tuple[str, ...] = ()
    globs: tuple[str, ...] = ()  # dynamic name_glob patterns
    checks: frozenset[str] = frozenset()

    def applies(self, brand: str, soc: str, devices: frozenset[str]) -> bool:
        if self.scope == "all":
            return True
        if not isinstance(self.scope, dict):
            return False
        for k, v in self.scope.items():
            if k == "brand" and v.lower() != brand:
                return False
            if k == "soc" and v.lower() != soc:
                return False
            if k == "device" and v not in devices:
                return False
        return True


@dataclass(frozen=True)
class HighRisk:
    package: str
    reason: str
    scope: dict[str, str]


@dataclass
class Policy:
    groups: list[Group]
    never_start: dict[str, str]
    high_risk: list[HighRisk] = field(default_factory=list)


@dataclass(frozen=True)
class Refusal:
    package: str
    group: str
    entry: str
    reason: str

    def __str__(self) -> str:
        return f"{self.package}: refused by group '{self.group}' ({self.entry}): {self.reason}"


@dataclass
class Context:
    """What the policy is evaluated against: the TV's brand/SoC/profile and live facts."""

    brand: str
    soc: str
    devices: frozenset[str]  # matched profile, or every same-brand profile when none matched
    home_packages: frozenset[str] = frozenset()
    persistent: frozenset[str] = frozenset()
    live: bool = False  # dynamic HOME/PERSISTENT facts were read from the TV


def load(path: Path) -> Policy:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict) or data.get("schema") != 1 or data.get("override") != "never":
        raise ZenError(f"{path}: expected schema: 1 and override: never")
    groups, seen = [], set()
    for g in data.get("groups") or []:
        gid = g.get("id")
        if not gid or gid in seen:
            raise ZenError(f"{path}: group id missing or duplicated: {gid!r}")
        seen.add(gid)
        scope = g.get("scope")
        if scope != "all" and not (isinstance(scope, dict) and scope and set(scope) <= SCOPE_KEYS):
            raise ZenError(f"{path}: group {gid}: bad scope {scope!r}")
        pkgs = g.get("packages") or []
        if not all(isinstance(p, str) and p for p in pkgs):
            raise ZenError(f"{path}: group {gid}: packages must be non-empty strings")
        globs, checks = [], set()
        for rule in g.get("rules") or []:
            check = rule.get("check")
            if check not in KNOWN_CHECKS:
                raise ZenError(f"{path}: group {gid}: unknown dynamic check {check!r}")
            checks.add(check)
            if check == "name_glob":
                globs.extend(rule.get("patterns") or [])
        if not pkgs and not checks:
            raise ZenError(f"{path}: group {gid} protects nothing")
        groups.append(
            Group(
                id=gid,
                scope=scope,
                reason=str(g.get("reason", "")),
                source=str(g.get("source", "")),
                packages=tuple(pkgs),
                globs=tuple(globs),
                checks=frozenset(checks),
            )
        )
    never_start = {e["package"]: e.get("reason", "") for e in data.get("never_start") or []}
    high = []
    for hr in data.get("high_risk") or []:
        scope = hr.get("scope") or {}
        for p in hr.get("packages") or []:
            high.append(HighRisk(package=p["name"], reason=p.get("reason", ""), scope=scope))
    return Policy(groups=groups, never_start=never_start, high_risk=high)


def _glob_hit(package: str, patterns: tuple[str, ...]) -> str | None:
    for pat in patterns:
        if fnmatch.fnmatchcase(package, pat):
            return pat
    return None


def check_package(policy: Policy, ctx: Context, package: str) -> Refusal | None:
    """The first refusal for `package`, or None. Static entries, globs and dynamic facts."""
    C.check_package(package)
    for g in policy.groups:
        if not g.applies(ctx.brand, ctx.soc, ctx.devices):
            continue
        hit = _glob_hit(package, g.packages)
        if hit:
            return Refusal(package, g.id, hit, g.reason)
        hit = _glob_hit(package, g.globs)
        if hit:
            return Refusal(package, g.id, f"name glob {hit}", g.reason)
        if "answers_home" in g.checks and package in ctx.home_packages:
            return Refusal(package, g.id, "answers HOME on this TV", g.reason)
        if "persistent_flag" in g.checks and package in ctx.persistent:
            return Refusal(package, g.id, "PERSISTENT flag on this TV", g.reason)
    return None


def high_risk_reason(policy: Policy, ctx: Context, package: str) -> str | None:
    for hr in policy.high_risk:
        b = hr.scope.get("brand")
        if (b is None or b.lower() == ctx.brand) and hr.package == package:
            return hr.reason
    return None


def needs_live_facts(policy: Policy) -> bool:
    return any(g.checks & {"answers_home", "persistent_flag"} for g in policy.groups)


def home_packages(session: Session) -> frozenset[str]:
    out = session.read(C.query_home())
    return frozenset(m.group(1) for line in out.splitlines() if (m := BRIEF_COMPONENT_RE.match(line)))


def is_persistent(session: Session, package: str) -> bool:
    return bool(PERSISTENT_RE.search(session.read(C.dumpsys("package", C.check_package(package)))))


def context_for(
    brand: str,
    soc: str,
    profile_name: str | None,
    profiles_same_brand: list[str],
    session: Session | None = None,
    packages: list[str] | None = None,
) -> Context:
    """Build a Context. With no matched profile, every same-brand device group applies (widens only)."""
    devices = frozenset([profile_name]) if profile_name else frozenset(profiles_same_brand)
    ctx = Context(brand=brand.lower(), soc=soc.lower(), devices=devices)
    if session is not None:
        ctx.home_packages = home_packages(session)
        ctx.persistent = frozenset(p for p in (packages or []) if is_persistent(session, p))
        ctx.live = True
    return ctx
