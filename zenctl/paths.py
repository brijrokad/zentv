"""Where zentv reads its data from and writes its private state to."""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    """The zentv checkout (safety/, devices/). ZENTV_REPO overrides it (tests)."""
    env = os.environ.get("ZENTV_REPO")
    return Path(env) if env else Path(__file__).resolve().parent.parent


def safety_file() -> Path:
    return repo_root() / "safety" / "never_disable.yaml"


def devices_dir() -> Path:
    return repo_root() / "devices"


def state_dir() -> Path:
    """~/.zentv (0700): snapshots, logs, surveys. Never inside the repo. ZENTV_HOME overrides it."""
    env = os.environ.get("ZENTV_HOME")
    d = Path(env) if env else Path.home() / ".zentv"
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    d.chmod(0o700)
    return d


def private_subdir(name: str) -> Path:
    d = state_dir() / name
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    return d
