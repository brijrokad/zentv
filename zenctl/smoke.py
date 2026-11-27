"""Interactive smoke test from the device profile's `smoke:` list. Any failure means restore."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import yaml

from . import paths
from .device import Profile


def items(profile: Profile) -> list[str]:
    data = yaml.safe_load(Path(profile.path).read_text()) or {}
    smoke = data.get("smoke") or []
    if not smoke:
        raise ValueError(f"{profile.path}: no smoke: checklist")
    return [str(s) for s in smoke]


def run(profile: Profile, ask: Callable[[str], str] = input) -> tuple[list[str], Path]:
    """Ask each item (y = works, n = broken, s = skipped/not testable). Skips are recorded as skips,
    never as passes. Returns (failed items, results file in ~/.zentv/smoke/)."""
    results, failed = [], []
    for i, item in enumerate(items(profile), 1):
        while True:
            ans = ask(f"[{i}] {item}  — works? [y/n/s] ").strip().lower()
            if ans in ("y", "n", "s"):
                break
        results.append({"item": item, "ok": {"y": True, "n": False, "s": None}[ans]})
        if ans == "n":
            failed.append(item)
    out = (
        paths.private_subdir("smoke") / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{profile.name}.json"
    )
    out.write_text(json.dumps({"profile": profile.name, "results": results}, indent=2) + "\n")
    return failed, out
