"""Turn a device's debloat.yaml + the live TV + the safety policy into a plan (read-only).

Owner decisions in debloat.yaml are final: `owner: approved...` is in, `owner: keep...` is out.
Entries without an owner decision follow `default`; `default: off` entries need --include.
Any refusal stops the whole plan: nothing is ever dropped silently.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import safety, survey
from .adb import Session
from .device import Identity, Profile
from .errors import NotAllowed, Refused, ZenError


@dataclass(frozen=True)
class Action:
    op: str  # "disable" | "unhide"
    package: str
    reason: str


@dataclass
class Plan:
    device: str
    fingerprint: str
    actions: list[Action]
    skipped: list[tuple[str, str]] = field(default_factory=list)
    approved_unhide: frozenset[str] = frozenset()
    # What the owner asked for, whatever the TV's live state. The digest comes from this, so a retry
    # after a half-finished apply finds the original snapshot (first record wins).
    intent: list[tuple[str, str]] = field(default_factory=list)

    @property
    def digest(self) -> str:
        body = json.dumps([self.fingerprint, sorted(self.intent)])
        return hashlib.sha256(body.encode()).hexdigest()[:16]


def load_debloat(path: Path, profile: Profile) -> dict:
    if not path.is_file():
        raise ZenError(f"no debloat plan for {profile.name}: {path}")
    data = yaml.safe_load(path.read_text()) or {}
    if data.get("schema") != 1 or data.get("device") != profile.name:
        raise ZenError(f"{path}: expected schema: 1 and device: {profile.name}")
    for t in data.get("targets") or []:
        if t.get("risk") not in ("low", "medium", "high") or t.get("default") not in (
            "on",
            "off",
            True,
            False,
        ):
            raise ZenError(f"{path}: target {t.get('package')}: risk must be low/medium/high, default on/off")
    return data


def _selected(entry: dict, include: set[str]) -> tuple[bool, str]:
    owner = str(entry.get("owner") or "").lower()
    if owner.startswith("approved"):
        return True, "owner approved"
    if owner.startswith("keep"):
        return False, "owner: keep enabled"
    default = entry.get("default")
    if default in ("on", True):
        return True, "default on"
    if entry["package"] in include:
        return True, "included on the command line"
    return False, "default off (name it with --include to add it)"


def build(
    session: Session,
    ident: Identity,
    profile: Profile,
    policy: safety.Policy,
    debloat: dict,
    include: set[str] | None = None,
) -> Plan:
    include = include or set()
    if debloat.get("fingerprint") and debloat["fingerprint"] != ident.fingerprint:
        raise NotAllowed(
            "this debloat plan was written for different firmware; re-run Phase 3 for this build"
        )
    live = survey._packages(session)
    hidden = survey.absent_for_user(session)
    plan = Plan(device=profile.name, fingerprint=ident.fingerprint, actions=[])

    candidates: list[tuple[str, str]] = []
    for t in debloat.get("targets") or []:
        pkg = t["package"]
        ok, why = _selected(t, include)
        if ok:
            plan.intent.append(("disable", pkg))
        if not ok:
            plan.skipped.append((pkg, why))
        elif pkg not in live:
            plan.skipped.append((pkg, "not installed or hidden on this TV"))
        elif not live[pkg]["enabled"]:
            plan.skipped.append((pkg, "already disabled (left as found)"))
        else:
            candidates.append((pkg, t.get("reason", "")))

    ctx = safety.context_for(
        ident.brand, ident.soc, profile.name, [], session=session, packages=[p for p, _ in candidates]
    )
    refusals = [r for p, _ in candidates if (r := safety.check_package(policy, ctx, p))]
    if refusals:
        raise Refused("plan refused; nothing will be sent:\n  " + "\n  ".join(map(str, refusals)))
    for pkg, _ in candidates:
        if (hr := safety.high_risk_reason(policy, ctx, pkg)) and pkg not in include:
            raise Refused(f"{pkg} is high risk ({hr}); it must be named with --include")
    plan.actions += [Action("disable", p, r) for p, r in candidates]

    approved = frozenset(r["package"] for r in debloat.get("restore_hidden") or [])
    plan.approved_unhide = approved
    for r in debloat.get("restore_hidden") or []:
        pkg = r["package"]
        plan.intent.append(("unhide", pkg))
        if hidden.get(pkg, {}).get("hidden"):
            plan.actions.append(Action("unhide", pkg, r.get("reason", "")))
        else:
            plan.skipped.append((pkg, "not hidden (nothing to restore)"))
    return plan
