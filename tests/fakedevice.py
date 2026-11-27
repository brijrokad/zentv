"""An in-memory TV for tests (ARCHITECTURE.md §5). It parses the shell commands zentv sends and
changes its own state the way a real TV would, so read-back and round trips can be tested.

Fixture data is synthetic, shaped after the reference data in devices/*/PROFILE.md. The TCL serial
below is a made-up value in the TCL format, not a real set's.
"""

from __future__ import annotations

import copy
import json
import shlex
from dataclasses import asdict, dataclass, field

from zenctl.adb import ShellResult

UNSUPPORTED = 255


@dataclass
class FakeDevice:
    props: dict[str, str]
    packages: dict[str, dict]  # name -> {enabled, system, installer, uid, persistent}
    home_candidates: list[str]
    preferred_home: str | None
    settings: dict[str, dict[str, str]]
    known_ops: list[str]
    appops: dict[str, str] = field(default_factory=dict)  # "pkg/OP" -> mode
    tv_inputs: list[str] = field(default_factory=list)
    wifi_creator: str = "android.uid.system:1000"
    transport: str = "WIFI"
    mem_kb: tuple[int, int] = (2000000, 600000)
    admins: list[str] = field(default_factory=list)
    shell_can_unhide: bool = True
    install_package: str = "io.github.brijrokad.zentv.spike"  # what the next `adb install` adds
    service_labels: dict[str, str] = field(
        default_factory=dict
    )  # False on builds where `pm unhide` needs MANAGE_USERS (TCL AR10)
    log: list[str] = field(default_factory=list)

    # ---- transport protocol ----
    def shell(self, command: str, timeout: float = 30.0) -> ShellResult:
        self.log.append(command)
        argv = shlex.split(command)
        try:
            out = self._dispatch(argv)
        except _Fail as f:
            return ShellResult(f.rc, "", f.msg)
        return ShellResult(0, out, "")

    def host(self, argv: list[str], timeout: float = 30.0) -> ShellResult:
        self.log.append("adb " + " ".join(argv))
        if argv[:2] == ["install", "-r"] and len(argv) == 3:
            self.packages[self.install_package] = {
                "system": False,
                "enabled": True,
                "installer": None,
                "uid": 10500,
                "persistent": False,
            }
            return ShellResult(0, "Performing Streamed Install\nSuccess\n", "")
        return ShellResult(1, "", f"fake adb host: unsupported {argv}")

    def _bound(self) -> list[str]:
        """Services Android would bind: listed, accessibility on, and on TCL the boot app-op allowed."""
        if self.settings.get("secure", {}).get("accessibility_enabled") != "1":
            return []
        out = []
        for comp in self.settings.get("secure", {}).get("enabled_accessibility_services", "").split(":"):
            pkg = comp.split("/")[0]
            if comp and pkg in self.packages:
                tcl = self.props.get("ro.product.brand", "").lower() == "tcl"
                if not tcl or self.appops.get(f"{pkg}/APP_AUTO_START") == "allow":
                    out.append(comp)
        return out

    # ---- serialisation (for the fake adb shim) ----
    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, s: str) -> FakeDevice:
        d = json.loads(s)
        d["mem_kb"] = tuple(d["mem_kb"])
        return cls(**d)

    def clone(self) -> FakeDevice:
        return copy.deepcopy(self)

    # ---- command handling ----
    def _dispatch(self, a: list[str]) -> str:
        match a:
            case ["getprop"]:
                return "".join(f"[{k}]: [{v}]\n" for k, v in sorted(self.props.items()))
            case ["getprop", name]:
                return self.props.get(name, "") + "\n"
            case ["pm", "list", "packages", *flags]:
                return self._pm_list([f for f in flags if f not in ("--user", "0")])
            case ["dumpsys", "package", pkg]:
                p = self.packages.get(pkg)
                if p is None:
                    return f"Unable to find package: {pkg}\n"
                flags = "SYSTEM PERSISTENT" if p.get("persistent") else ("SYSTEM" if p.get("system") else "")
                hidden = str(bool(p.get("hidden"))).lower()
                enabled = p.get("state", 0 if p.get("enabled", True) else 3)
                return (
                    f"Packages:\n  Package [{pkg}] (1a2b):\n    pkgFlags=[ {flags} ]\n"
                    f"    User 0: ceDataInode=1 installed=true hidden={hidden} "
                    f"suspended=false enabled={enabled}\n"
                )
            case ["dumpsys", "connectivity"]:
                # Format as printed by a TCL AR10 build (Android 11), 2026-11-26.
                return (
                    "Active default network: 116\n"
                    f"  NetworkAgentInfo{{ ni{{[type: {self.transport}[], state: CONNECTED/CONNECTED]}}  "
                    f"network{{116}}  nethandle{{501621903373}}\n"
                    "  NetworkAgentInfo{ ni{[type: ETHERNET[], state: DISCONNECTED]}  network{90}\n"
                    "      NetworkRequest [ BACKGROUND_REQUEST id=2, [ Transports: CELLULAR ] ]\n"
                )
            case ["dumpsys", "wifi"]:
                return (
                    f'WifiConfiguration: SSID: "HomeNet-5G" BSSID: aa:bb:cc:dd:ee:ff\n'
                    f"  creatorName={self.wifi_creator} lastUpdateName={self.wifi_creator}\n"
                    "  mWifiInfo IP: /192.168.1.50\n"
                )
            case ["dumpsys", "tv_input"]:
                return "".join(
                    f"  TvInputInfo{{id={i}, uid=1000, isHardwareInput=true}}\n" for i in self.tv_inputs
                )
            case ["dumpsys", "device_policy"]:
                return "".join(f"  admin=ComponentInfo{{{c}}}\n" for c in self.admins)
            case ["cmd", "package", "resolve-activity", "--brief", *_]:
                pref = self.preferred_home if self.preferred_home in self.home_candidates else None
                return "priority=0 preferredOrder=0\n" + (
                    (pref + "\n") if pref else "android/com.android.internal.app.ResolverActivity\n"
                )
            case ["cmd", "package", "query-activities", "--brief", *_]:
                live = [
                    c
                    for c in self.home_candidates
                    if self.packages.get(c.split("/")[0], {}).get("enabled", True)
                ]
                return f"{len(live)} activities found:\n" + "".join(
                    f"  Activity #{i}:\n    {c}\n" for i, c in enumerate(live)
                )
            case ["settings", "get", ns, key]:
                return self.settings.get(ns, {}).get(key, "null") + "\n"
            case ["pm", "disable-user", "--user", "0", pkg]:
                p = self._need(pkg)
                p["enabled"], p["state"] = False, 3
                return f"Package {pkg} new state: disabled-user\n"
            case ["pm", "enable", "--user", "0", pkg]:
                p = self._need(pkg)
                p["enabled"], p["state"] = True, 1
                return f"Package {pkg} new state: enabled\n"
            case ["pm", "unhide", "--user", "0", pkg]:
                if not self.shell_can_unhide:  # real TCL AR10 output, 2026-11-26
                    raise _Fail(
                        255,
                        "Exception occurred while executing 'unhide':\njava.lang.SecurityException: "
                        "Neither user 2000 nor current process has android.permission.MANAGE_USERS.",
                    )
                p = self._need(pkg)
                p["hidden"] = False
                return f"Package {pkg} new hidden state: false\n"
            case ["settings", "delete", ns, key]:
                self.settings.get(ns, {}).pop(key, None)
                return "Deleted 1 rows\n"
            case ["appops", "set", pkg, op, mode]:
                if op not in self.known_ops:
                    raise _Fail(UNSUPPORTED, f"Error: Unknown operation string: {op}")
                if mode == "default":
                    self.appops.pop(f"{pkg}/{op}", None)
                else:
                    self.appops[f"{pkg}/{op}"] = mode
                return ""
            case ["appops", "write-settings"]:
                return "Current settings written.\n"
            case ["dumpsys", "accessibility"]:
                bound = ", ".join(f"Service[label=helper, id={c.split('/')[-1]}]" for c in self._bound())
                return f"User state[\n     Bound services:{{{bound}}}\n     Enabled services:{{}}\n]\n"
            case ["settings", "put", ns, key, value]:
                self.settings.setdefault(ns, {})[key] = value
                return ""
            case ["appops", "get", pkg, op]:
                if op not in self.known_ops:
                    raise _Fail(UNSUPPORTED, f"Error: Unknown operation string: {op}")
                mode = self.appops.get(f"{pkg}/{op}")
                if mode is None:  # real output for an op the build knows but nobody set (TCL AR10)
                    return "No operations.\nDefault mode: ignore\n"
                return f"{op}: {mode}\n"
            case ["appops", "get", pkg]:
                return "".join(
                    f"{k.split('/')[1]}: {v}\n" for k, v in self.appops.items() if k.startswith(pkg + "/")
                )
            case ["appops", "query-op", op, mode]:
                return "".join(
                    k.split("/")[0] + "\n"
                    for k, v in self.appops.items()
                    if k.endswith("/" + op) and v == mode
                )
            case ["cat", "/proc/meminfo"]:
                return f"MemTotal:       {self.mem_kb[0]} kB\nMemAvailable:   {self.mem_kb[1]} kB\n"
            case ["cat", "/proc/uptime"]:
                return "12345.67 23456.78\n"
        raise _Fail(UNSUPPORTED, f"FakeDevice: unsupported command {' '.join(a)}")

    def _need(self, pkg: str) -> dict:
        if pkg not in self.packages:
            raise _Fail(1, f"Unknown package: {pkg}")
        return self.packages[pkg]

    def _pm_list(self, flags: list[str]) -> str:
        out = []
        for name, p in sorted(self.packages.items()):
            if p.get("hidden") and "-u" not in flags:
                continue  # hidden packages only show with -u, as on a real TV
            if "-d" in flags and p.get("enabled", True):
                continue
            if "-e" in flags and not p.get("enabled", True):
                continue
            if "-s" in flags and not p.get("system"):
                continue
            if "-3" in flags and p.get("system"):
                continue
            line = f"package:{name}"
            if "-i" in flags:
                line += f"  installer={p.get('installer') or 'null'}"
            if "-U" in flags:
                line += f" uid:{p.get('uid', 10000)}"
            out.append(line)
        return "\n".join(out) + "\n"


class _Fail(Exception):
    def __init__(self, rc: int, msg: str) -> None:
        super().__init__(msg)
        self.rc, self.msg = rc, msg


# ---- fixtures ------------------------------------------------------------------------------


def _pkg(system=True, enabled=True, installer=None, uid=1000, persistent=False) -> dict:
    return {
        "system": system,
        "enabled": enabled,
        "installer": installer,
        "uid": uid,
        "persistent": persistent,
    }


GOOGLE_TV_PACKAGES = {
    "android": _pkg(persistent=True),
    "com.android.systemui": _pkg(persistent=True),
    "com.android.tv.settings": _pkg(),
    "com.android.vending": _pkg(uid=10010),
    "com.google.android.gms": _pkg(uid=10011, persistent=True),
    "com.google.android.apps.tv.launcherx": _pkg(uid=10020),
    "com.google.android.tungsten.setupwraith": _pkg(uid=10021),
    "com.google.android.katniss": _pkg(uid=10022),
    "com.google.android.tv.remote.service": _pkg(uid=10023),
    "com.google.android.apps.mediashell": _pkg(uid=10024),
    "com.google.android.feedback": _pkg(uid=10025),
    "com.google.android.apps.tv.dreamx": _pkg(uid=10026),
    "com.netflix.ninja": _pkg(system=False, installer="com.android.vending", uid=10100),
    "com.example.sideloaded": _pkg(system=False, installer=None, uid=10101),
}
HOME = [
    "com.google.android.apps.tv.launcherx/.MainActivity",
    "com.google.android.tungsten.setupwraith/.SetupWraithActivity",
    "com.android.tv.settings/.FallbackHome",
]


def tcl_g03() -> FakeDevice:
    pk = dict(GOOGLE_TV_PACKAGES)
    pk.update(
        {
            "com.tcl.tv": _pkg(uid=1000),
            "com.tcl.tvinput": _pkg(uid=1000),
            "com.tcl.suspension": _pkg(),
            "com.tcl.system.server": _pkg(persistent=True),
            "com.tcl.bi": _pkg(uid=10200),
            "com.tcl.usercenter": _pkg(uid=10201),
            "com.tcl.versionUpdateApp": _pkg(uid=10202),
            "com.tcl.bootadservice": _pkg(uid=10203),
            "com.tcl.esticker": _pkg(uid=10204, enabled=False),
            "com.tcl.vendorhome": _pkg(uid=10205),  # synthetic: a vendor package that also answers HOME
            "com.tcl.messagebox": {**_pkg(uid=10206), "hidden": True},  # arrived hidden by another tool
            "com.google.android.apps.mediashell": {**_pkg(uid=10024), "hidden": True},  # as on the real TCL
            "com.google.android.katniss": {**_pkg(uid=10022), "hidden": True},
            "android.autoinstalls.config.google.gtvpai": _pkg(uid=10207),
            "com.tcl.dashboard": _pkg(uid=10208, installer="com.android.vending"),
            "com.tcl.ocean.instructions": _pkg(uid=10209),
            "com.tcl.partnercustomizer": _pkg(uid=10210),
        }
    )
    return FakeDevice(
        props={
            "ro.product.brand": "TCL",
            "ro.product.manufacturer": "TCL",
            "ro.product.model": "Smart TV",
            "ro.product.device": "BeyondTV4",
            "ro.product.name": "G03_4K_US_NF_DB",
            "ro.product.board": "RTD2851M",
            "ro.board.platform": "rtd288o",
            "ro.build.fingerprint": "TCL/G03_4K_US_NF_DB/BeyondTV4:11/RP1A.200622.001/AR24:user/release-keys",
            "ro.build.version.release": "11",
            "ro.build.version.sdk": "30",
            "ro.build.version.incremental": "AR24",
            "ro.product.cpu.abilist": "armeabi-v7a",
            "ro.zygote": "zygote32",
            "ro.tcl.product_type": "GTV",
            "ro.serialno": "1234ABC567890D12345",
            "ro.boot.serialno": "1234ABC567890D12345",
        },
        packages=pk,
        home_candidates=[*HOME, "com.tcl.vendorhome/.Home"],
        preferred_home=None,
        settings={
            "global": {"adb_enabled": "1", "adb_wifi_enabled": "0", "private_dns_mode": "off"},
            "secure": {"accessibility_enabled": "0"},
        },
        known_ops=["APP_AUTO_START", "GET_USAGE_STATS", "SYSTEM_ALERT_WINDOW"],
        appops={"com.tcl.bi/GET_USAGE_STATS": "allow"},
        tv_inputs=["com.tcl.tvinput/.TvPassThroughService/HW15", "com.tcl.tvinput/.TunerService/HW0"],
        mem_kb=(1900000, 500000),
        shell_can_unhide=False,
    )


def sony_vh21() -> FakeDevice:
    pk = dict(GOOGLE_TV_PACKAGES)
    pk.update(
        {
            "com.sony.dtv.tvx": _pkg(),
            "com.sony.dtv.sonysystemservice": _pkg(persistent=True),
            "com.sonyericsson.idd.agent": _pkg(uid=10300),
            "com.sony.dtv.sonybugreportsys": _pkg(uid=10301),
            "com.mediatek.tis": _pkg(),
            "com.vewd.core.service": _pkg(uid=10302),
            "com.sony.dtv.promo.example": _pkg(uid=10303),  # synthetic debloat candidate
        }
    )
    return FakeDevice(
        props={
            "ro.product.brand": "Sony",
            "ro.product.manufacturer": "Sony",
            "ro.product.model": "KD-65X80K",
            "ro.product.device": "BRAVIA_VH21_M",
            "ro.product.name": "BRAVIA_VH21_M_PA",
            "ro.board.platform": "mt5895",
            "ro.build.fingerprint": (
                "Sony/BRAVIA_VH21_M_PA/BRAVIA_VH21_M:12/STT2.230505.001.S136/682241:user/release-keys"
            ),
            "ro.build.version.release": "12",
            "ro.build.version.sdk": "31",
            "ro.product.cpu.abilist": "arm64-v8a,armeabi-v7a,armeabi",
            "ro.serialno": "SYNTHSONY0001",
        },
        packages=pk,
        home_candidates=HOME,
        preferred_home=None,
        settings={"global": {"adb_enabled": "1", "adb_wifi_enabled": "1"}, "secure": {}},
        known_ops=["GET_USAGE_STATS", "SYSTEM_ALERT_WINDOW"],
        tv_inputs=["com.sony.dtv.tvinput.tuner/.TunerInputService/HW0"],
    )
