"""Snapshots: the pre-state of everything a plan touches, written before the first change (rule 6).

~/.zentv/snapshots/<device-key>/<utc>-<plan-digest>.json, mode 0600. <device-key> is a hash of the
TV's serial, so the serial itself is never stored. First record wins: re-running the same plan on
the same TV reuses the original snapshot, so a half-applied retry can't overwrite the true pre-state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from . import paths
from .device import Identity
from .errors import ZenError
from .plan import Plan


def device_key(ident: Identity) -> str:
    seed = ident.props.get("ro.serialno") or ident.props.get("ro.boot.serialno") or ident.fingerprint
    return hashlib.sha256(seed.encode()).hexdigest()[:16]


@dataclass
class Snapshot:
    schema: int
    device_key: str
    profile: str
    fingerprint: str
    plan_digest: str
    created_utc: str
    records: dict[str, str | None]
    actions: list[dict[str, str]] = field(default_factory=list)
    path: str = ""

    def to_json(self) -> str:
        d = asdict(self)
        d.pop("path")
        return json.dumps(d, indent=2) + "\n"


def _dir(key: str) -> Path:
    d = paths.private_subdir("snapshots") / key
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    return d


def find(key: str, digest: str) -> Path | None:
    hits = sorted(_dir(key).glob(f"*-{digest}.json"))
    return hits[0] if hits else None  # the oldest one is the original pre-state


def latest(key: str) -> Path | None:
    hits = sorted(_dir(key).glob("*.json"))
    return hits[-1] if hits else None


def all_for(key: str) -> list[Path]:
    return sorted(_dir(key).glob("*.json"))


def load(path: Path) -> Snapshot:
    try:
        d = json.loads(Path(path).read_text())
    except (OSError, ValueError) as e:
        raise ZenError(f"cannot read snapshot {path}: {e}") from e
    if d.get("schema") != 1 or not isinstance(d.get("records"), dict):
        raise ZenError(f"{path}: not a zentv snapshot (schema 1)")
    return Snapshot(path=str(path), **d)


def create(ident: Identity, plan: Plan, records: dict[str, str | None]) -> Snapshot:
    """Write the snapshot (or return the existing original for this plan). Call before any change."""
    key = device_key(ident)
    existing = find(key, plan.digest)
    if existing:
        return load(existing)
    snap = Snapshot(
        schema=1,
        device_key=key,
        profile=plan.device,
        fingerprint=plan.fingerprint,
        plan_digest=plan.digest,
        created_utc=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        records=dict(records),
        actions=[{"op": a.op, "package": a.package} for a in plan.actions],
    )
    p = _dir(key) / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{plan.digest}.json"
    p.write_text(snap.to_json())
    p.chmod(0o600)
    snap.path = str(p)
    return snap
