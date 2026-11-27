"""zentv's own APK and its Home helper on the TV (M3a spike now, M4 launcher later).

install:          `adb install -r` of zentv's own APK only; the package is checked locally first (D5).
enable-home-key:  snapshot → (TCL only) APP_AUTO_START allow + write-settings → add the helper to
                  enabled_accessibility_services → accessibility_enabled 1 → read back (rules 6, 9).
revert:           remove only zentv's helper entry, put accessibility_enabled and the app-op back as
                  recorded, read back. Never uninstalls (rule 5); the owner removes the app in Settings.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from . import commands as C
from . import paths
from .adb import Session
from .device import Identity
from .errors import ZenError
from .snapshot import device_key

SPIKE_PACKAGE = "io.github.brijrokad.zentv.spike"
SPIKE_SERVICE = f"{SPIKE_PACKAGE}/{SPIKE_PACKAGE}.HomeKeyService"
SERVICES = "secure/enabled_accessibility_services"
ENABLED = "secure/accessibility_enabled"


def default_apk() -> Path:
    return paths.repo_root() / "launcher/app/build/outputs/apk/spike/app-spike.apk"


def _build_tool(name: str) -> str:
    sdk = os.environ.get("ANDROID_HOME") or str(Path.home() / "Library/Android/sdk")
    hits = sorted((Path(sdk) / "build-tools").glob(f"*/{name}"))
    if hits:
        return str(hits[-1])
    found = shutil.which(name)
    if not found:
        raise ZenError(f"{name} not found (Android build-tools). Set ANDROID_HOME.")
    return found


def apk_package(apk: Path) -> str:
    """The APK's package name, read locally with aapt2 before anything is sent (D5)."""
    out = subprocess.run(
        [_build_tool("aapt2"), "dump", "badging", str(apk)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    ).stdout
    for line in out.splitlines():
        if line.startswith("package: name='"):
            return line.split("'")[1]
    raise ZenError(f"could not read the package name of {apk}")


def install(session: Session, apk: Path, package: str | None = None) -> C.Command:
    apk = apk.resolve()
    if not apk.is_file():
        raise ZenError(f"no APK at {apk}; build it first (launcher/: ./gradlew assembleSpike)")
    pkg = package or apk_package(apk)
    cmd = C.install_apk(str(apk), pkg)
    session.record(cmd)
    session.change(cmd)
    if session.yes:
        st = C.package_state(session.read(C.dumpsys("package", pkg)))
        if not st or "installed=true" not in st:
            raise ZenError(f"install read-back failed for {pkg} (state: {st})")
    return cmd


@dataclass
class LauncherSnapshot:
    device_key: str
    package: str
    service: str
    brand: str
    records: dict[str, str | None]
    created_utc: str
    path: str = field(default="", compare=False)

    def save(self) -> None:
        d = paths.private_subdir("snapshots") / self.device_key
        d.mkdir(mode=0o700, parents=True, exist_ok=True)
        p = d / f"launcher-{self.created_utc.replace(':', '').replace('-', '')}.json"
        body = {k: v for k, v in self.__dict__.items() if k != "path"}
        p.write_text(json.dumps(body, indent=2) + "\n")
        p.chmod(0o600)
        self.path = str(p)


def latest_launcher_snapshot(ident: Identity) -> LauncherSnapshot | None:
    d = paths.private_subdir("snapshots") / device_key(ident)
    hits = sorted(d.glob("launcher-*.json")) if d.is_dir() else []
    if not hits:
        return None
    data = json.loads(hits[-1].read_text())
    return LauncherSnapshot(path=str(hits[-1]), **data)


def _services_list(v: str | None) -> list[str]:
    return [x for x in (v or "").split(":") if x]


def enable_home_key(
    session: Session, ident: Identity, package: str = SPIKE_PACKAGE, service: str = SPIKE_SERVICE
) -> tuple[list[C.Command], LauncherSnapshot | None]:
    if not service.startswith(package + "/"):
        raise ZenError("the helper must belong to zentv's own package")
    tcl = ident.is_brand("tcl")
    probe = [
        C.put_accessibility("enabled_accessibility_services", service),
        C.put_accessibility("accessibility_enabled", "1"),
    ]
    if tcl:
        probe.insert(0, C.tcl_appop(package, "APP_AUTO_START", "allow", ident.brand))
    for cmd in probe:  # record every pre-state first (rule 6)
        session.record(cmd)
    current = _services_list(session.recorded.get(SERVICES))
    new_services = ":".join([*current, service]) if service not in current else ":".join(current)
    cmds = []
    if tcl:
        cmds += [
            C.tcl_appop(package, "APP_AUTO_START", "allow", ident.brand),
            C.appops_write_settings(package, "APP_AUTO_START"),
        ]
    cmds += [
        C.put_accessibility("enabled_accessibility_services", new_services),
        C.put_accessibility("accessibility_enabled", "1"),
    ]
    snap = None
    if session.yes:
        snap = LauncherSnapshot(
            device_key(ident),
            package,
            service,
            ident.brand,
            {
                k: session.recorded.get(k)
                for k in [SERVICES, ENABLED, f"{package}/APP_AUTO_START"]
                if k in session.recorded
            },
            datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        snap.save()
    for cmd in cmds:
        try:
            session.change(cmd)
        except ZenError as e:
            if session.yes:
                raise type(e)(f"{e}\nStopped. Revert with: zentv launcher revert --yes") from e
            raise
    if session.yes:
        st = status(session, ident, package, service)
        if (
            service not in st["enabled_accessibility_services"]
            or st["accessibility_enabled"] != "1"
            or (tcl and st["app_auto_start"] != "allow")
        ):
            raise ZenError(f"read-back failed: {st}. Revert with: zentv launcher revert --yes")
    return cmds, snap


def revert(session: Session, ident: Identity, snap: LauncherSnapshot) -> tuple[list[C.Command], list[str]]:
    """Put back what enable-home-key changed. Returns (commands, mismatches after read-back)."""
    if snap.device_key != device_key(ident):
        raise ZenError("this launcher snapshot was taken on a different TV; nothing was sent")
    session.recorded.update(snap.records)
    now = session.read(C.settings_get("secure", "enabled_accessibility_services")).strip()
    remaining = [s for s in _services_list(None if now in ("", "null") else now) if s != snap.service]
    cmds: list[C.Command] = []
    if remaining:
        cmds.append(
            C.put_accessibility("enabled_accessibility_services", ":".join(remaining), for_restore=True)
        )
    else:
        cmds.append(C.delete_accessibility("enabled_accessibility_services", for_restore=True))
    pre_enabled = snap.records.get(ENABLED)
    cmds.append(
        C.put_accessibility("accessibility_enabled", pre_enabled, for_restore=True)
        if pre_enabled
        else C.delete_accessibility("accessibility_enabled", for_restore=True)
    )
    op_key = f"{snap.package}/APP_AUTO_START"
    if op_key in snap.records and ident.is_brand("tcl"):
        cmds += [
            C.tcl_appop(
                snap.package,
                "APP_AUTO_START",
                snap.records[op_key] or "default",
                ident.brand,
                for_restore=True,
            ),
            C.appops_write_settings(snap.package, "APP_AUTO_START", for_restore=True),
        ]
    for cmd in cmds:
        session.change(cmd)
    mismatches = []
    if session.yes:
        st = status(session, ident, snap.package, snap.service)
        if snap.service in st["enabled_accessibility_services"]:
            mismatches.append("the helper is still listed in enabled_accessibility_services")
        if (st["accessibility_enabled"] or None) != (pre_enabled or None):
            mismatches.append(f"accessibility_enabled is {st['accessibility_enabled']}, was {pre_enabled}")
        if (
            op_key in snap.records
            and ident.is_brand("tcl")
            and st["app_auto_start"] != (snap.records[op_key] or "default")
        ):
            mismatches.append(f"APP_AUTO_START is {st['app_auto_start']}, was {snap.records[op_key]}")
    return cmds, mismatches


def status(
    session: Session, ident: Identity, package: str = SPIKE_PACKAGE, service: str = SPIKE_SERVICE
) -> dict:
    """Read-only: is zentv installed, is its helper enabled and bound, and the TCL app-op."""

    def setting(key: str) -> str | None:
        v = session.read(C.settings_get("secure", key)).strip()
        return None if v in ("", "null") else v

    pkg_state = C.package_state(session.read(C.dumpsys("package", package)))
    acc = session.read(C.dumpsys("accessibility"))
    out = {
        "package": package,
        "installed": bool(pkg_state and "installed=true" in pkg_state),
        "enabled_accessibility_services": _services_list(setting("enabled_accessibility_services")),
        "accessibility_enabled": setting("accessibility_enabled"),
        "helper_bound": service.split("/")[-1].split(".")[-1] in acc.split("Bound services:", 1)[-1][:2000]
        if "Bound services:" in acc
        else None,
    }
    if ident.is_brand("tcl") and out["installed"]:
        res = session.probe(C.appops_get(package, "APP_AUTO_START"))
        out["app_auto_start"] = C.appop_mode(res.stdout) if res.returncode == 0 else None
    else:
        out["app_auto_start"] = None
    return out
