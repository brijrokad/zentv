"""The only place TV commands are built (ARCHITECTURE.md §3.2).

Every command sent to the TV is a `Command` made by one of the functions below. The transport
refuses anything else. Arguments are validated against strict patterns and quoted. There is no
constructor for any ground-rule-5 command, so none can be built; `refuse.py` is the second net.

M1 has read-only constructors plus one state change, `adb_network_off`, used by `adb-close`.
The debloat and launcher state changes arrive in M2 and M4, each with a recorder.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from enum import Enum

from .errors import InvalidArgument

PACKAGE_RE = re.compile(
    r"^(android|[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+)$"
)  # `android` is the one dotless core package
PROP_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[A-Za-z0-9_\-]+)+$")
SETTING_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
APPOP_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
DUMPSYS_ARG_RE = re.compile(r"^-{0,2}[A-Za-z0-9][A-Za-z0-9_.\-]{0,127}$")
MAX_COMMAND_LEN = 1000

SETTINGS_NAMESPACES = frozenset({"global", "secure", "system"})
COMPONENT_RE = re.compile(
    r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+/(\.?[A-Za-z][A-Za-z0-9_]*)(\.[A-Za-z0-9_]+)*$"
)
APK_PATH_RE = re.compile(r"^/[A-Za-z0-9._/\-]+\.apk$")
# zentv's own packages. Installs and the TCL app-op are refused for anything else (rule 6, D5).
OWN_PACKAGES = frozenset({"io.github.brijrokad.zentv", "io.github.brijrokad.zentv.spike"})
ACCESSIBILITY_KEYS = ("enabled_accessibility_services", "accessibility_enabled")
TCL_BOOT_OPS = frozenset({"APP_AUTO_START", "AUTO_START"})
DUMPSYS_SERVICES = frozenset(
    {
        "package",
        "activity",
        "accessibility",
        "tv_input",
        "connectivity",
        "wifi",
        "meminfo",
        "gfxinfo",
        "device_policy",
        "power",
        "window",
    }
)
PM_LIST_FLAGS = frozenset({"-d", "-e", "-s", "-3", "-i", "-U", "-u"})
READABLE_FILES = frozenset({"/proc/meminfo", "/proc/uptime"})
# Settings that `adb_network_off` may set to 0. Setting them to anything else is refused (rule 5).
ADB_NETWORK_KEYS = ("adb_wifi_enabled", "adb_enabled")

_CONSTRUCTED = object()


class Kind(Enum):
    READ = "read"
    CHANGE = "change"


@dataclass(frozen=True)
class Record:
    """A value a state change touches. Its pre-state is read and stored before the change."""

    kind: str  # "setting" or "package" (M2); "home", "appop" arrive with the launcher (M4)
    key: str  # e.g. "global/adb_wifi_enabled", or a package name

    def reader(self) -> Command:
        if self.kind == "setting":
            ns, k = self.key.split("/", 1)
            return settings_get(ns, k)
        if self.kind == "package":
            return dumpsys("package", check_package(self.key))
        if self.kind == "appop":
            pkg, op = self.key.split("/", 1)
            return appops_get(pkg, op)
        raise InvalidArgument(f"no reader for record kind {self.kind!r}")

    def parse(self, output: str) -> str | None:
        """The recorded value: a setting's text, or a package's user-0 state."""
        if self.kind == "setting":
            v = output.strip()
            return None if v in ("", "null") else v
        if self.kind == "package":
            return package_state(output)
        if self.kind == "appop":
            return appop_mode(output)
        raise InvalidArgument(f"no parser for record kind {self.kind!r}")


USER0_STATE = re.compile(r"User 0:.*?\binstalled=(true|false)\b.*?\bhidden=(true|false)\b.*?\benabled=(\d+)")


def package_state(dumpsys_output: str) -> str | None:
    """'enabled=<n> hidden=<bool> installed=<bool>' for user 0, or None if the package is unknown.

    enabled: 0 default, 1 enabled, 2 disabled, 3 disabled-user, 4 disabled-until-used.
    """
    m = USER0_STATE.search(dumpsys_output)
    if not m:
        return None
    return f"enabled={m[3]} hidden={m[2]} installed={m[1]}"


APPOP_LINE = re.compile(r"^\s*([A-Z_]+):\s*([a-z]+)", re.MULTILINE)
APPOP_MODES = frozenset({"allow", "ignore", "deny", "default", "foreground"})


def appop_mode(output: str) -> str:
    """'allow'/'ignore'/... from `appops get <pkg> <op>`; 'default' when nothing is set ("No operations.")."""
    m = APPOP_LINE.search(output)
    return m[2] if m and m[2] in APPOP_MODES else "default"


def parse_state(value: str | None) -> dict[str, str]:
    return dict(kv.split("=", 1) for kv in (value or "").split())


@dataclass(frozen=True)
class Command:
    argv: tuple[str, ...]
    kind: Kind
    summary: str
    records: tuple[Record, ...] = ()
    # Exempt from the read-only gate: adb_network_off (rule 10) and a restore's `pm enable`, which
    # replays a snapshot taken on this same TV and must work even after a firmware update.
    gate_exempt: bool = False
    # Runs as `adb -s <serial> <argv>` on the Mac instead of `adb shell` (only install_apk).
    host: bool = False
    _token: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._token is not _CONSTRUCTED:
            raise TypeError("Commands are built only by zenctl.commands functions")
        if not self.argv:
            raise InvalidArgument("empty command")
        if self.kind is Kind.CHANGE and not self.records:
            raise TypeError("every state change declares what it records")
        if len(self.shell_string()) > MAX_COMMAND_LEN:
            raise InvalidArgument("command too long")

    @property
    def is_change(self) -> bool:
        return self.kind is Kind.CHANGE

    def shell_string(self) -> str:
        return " ".join(shlex.quote(a) for a in self.argv)


def _cmd(argv: list[str], kind: Kind, summary: str, **kw) -> Command:
    return Command(tuple(argv), kind, summary, _token=_CONSTRUCTED, **kw)


def check_package(name: str) -> str:
    if not isinstance(name, str) or not PACKAGE_RE.fullmatch(name) or len(name) > 255:
        raise InvalidArgument(f"not a valid package name: {name!r}")
    return name


def _check(value: str, pattern: re.Pattern[str], what: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise InvalidArgument(f"not a valid {what}: {value!r}")
    return value


# ---- read-only -------------------------------------------------------------------------------


def getprop(name: str | None = None) -> Command:
    if name is None:
        return _cmd(["getprop"], Kind.READ, "read all system properties")
    return _cmd(["getprop", _check(name, PROP_RE, "property name")], Kind.READ, f"read {name}")


def pm_list_packages(*flags: str) -> Command:
    for f in flags:
        if f not in PM_LIST_FLAGS:
            raise InvalidArgument(f"pm list flag not allowed: {f!r}")
    return _cmd(["pm", "list", "packages", *flags, "--user", "0"], Kind.READ, "list packages")


def dumpsys(service: str, *args: str) -> Command:
    if service not in DUMPSYS_SERVICES:
        raise InvalidArgument(f"dumpsys service not allowed: {service!r}")
    for a in args:
        _check(a, DUMPSYS_ARG_RE, "dumpsys argument")
    return _cmd(["dumpsys", service, *args], Kind.READ, f"dumpsys {service}")


def _home_intent() -> list[str]:
    return ["-a", "android.intent.action.MAIN", "-c", "android.intent.category.HOME"]


def resolve_home() -> Command:
    return _cmd(
        ["cmd", "package", "resolve-activity", "--brief", *_home_intent()],
        Kind.READ,
        "which activity answers HOME",
    )


def query_home() -> Command:
    return _cmd(
        ["cmd", "package", "query-activities", "--brief", *_home_intent()],
        Kind.READ,
        "every activity that can answer HOME",
    )


def settings_get(namespace: str, key: str) -> Command:
    if namespace not in SETTINGS_NAMESPACES:
        raise InvalidArgument(f"settings namespace not allowed: {namespace!r}")
    return _cmd(
        ["settings", "get", namespace, _check(key, SETTING_KEY_RE, "setting key")],
        Kind.READ,
        f"read {namespace}/{key}",
    )


def appops_get(package: str, op: str | None = None) -> Command:
    argv = ["appops", "get", check_package(package)]
    if op is not None:
        argv.append(_check(op, APPOP_RE, "app-op name"))
    return _cmd(argv, Kind.READ, f"read app-ops of {package}")


def appops_query_op(op: str, mode: str = "allow") -> Command:
    if mode not in {"allow", "ignore", "deny", "default", "foreground"}:
        raise InvalidArgument(f"app-op mode not allowed: {mode!r}")
    return _cmd(
        ["appops", "query-op", _check(op, APPOP_RE, "app-op name"), mode],
        Kind.READ,
        f"which apps hold {op}={mode}",
    )


def read_file(path: str) -> Command:
    if path not in READABLE_FILES:
        raise InvalidArgument(f"file not allowed: {path!r}")
    return _cmd(["cat", path], Kind.READ, f"read {path}")


# ---- state changes ---------------------------------------------------------------------------


def adb_network_off(key: str) -> Command:
    """`settings put global <adb key> 0`: switches network/USB debugging off (rule 10)."""
    if key not in ADB_NETWORK_KEYS:
        raise InvalidArgument(f"not an ADB switch: {key!r}")
    return _cmd(
        ["settings", "put", "global", key, "0"],
        Kind.CHANGE,
        f"switch {key} off",
        records=(Record("setting", f"global/{key}"),),
        gate_exempt=True,
    )


def disable_user(package: str) -> Command:
    """`pm disable-user --user 0 <pkg>`: reversible with `pm enable` (rule 6)."""
    p = check_package(package)
    return _cmd(
        ["pm", "disable-user", "--user", "0", p], Kind.CHANGE, f"disable {p}", records=(Record("package", p),)
    )


def enable(package: str, for_restore: bool = False) -> Command:
    """`pm enable --user 0 <pkg>`. `for_restore` only from restore.py, replaying this TV's snapshot."""
    p = check_package(package)
    return _cmd(
        ["pm", "enable", "--user", "0", p],
        Kind.CHANGE,
        f"enable {p}",
        records=(Record("package", p),),
        gate_exempt=for_restore,
    )


def unhide(package: str, approved: frozenset[str]) -> Command:
    """`pm unhide --user 0 <pkg>`, only for packages the owner listed under restore_hidden (rule 6
    exception, Checkpoint 4). It undoes another tool's `pm hide`; zentv never hides anything."""
    p = check_package(package)
    if p not in approved:
        raise InvalidArgument(f"{p} is not in the device's approved restore_hidden list")
    return _cmd(
        ["pm", "unhide", "--user", "0", p], Kind.CHANGE, f"unhide {p}", records=(Record("package", p),)
    )


# ---- launcher (M3a/M4): zentv's own APK, its Home helper, and the TCL boot app-op ----------


def install_apk(path: str, package: str) -> Command:
    """`adb install -r <apk>` (D5): zentv's own APK only, Android's normal install path, never -g/-t."""
    if package not in OWN_PACKAGES:
        raise InvalidArgument(f"install is only for zentv's own packages, not {package!r}")
    if not APK_PATH_RE.fullmatch(path):
        raise InvalidArgument(f"not an absolute .apk path with safe characters: {path!r}")
    return _cmd(
        ["install", "-r", path],
        Kind.CHANGE,
        f"install {package}",
        records=(Record("package", package),),
        host=True,
    )


def _check_services(value: str) -> str:
    parts = value.split(":")
    if not value or not all(COMPONENT_RE.fullmatch(p) for p in parts):
        raise InvalidArgument(f"not a list of components: {value!r}")
    return value


def put_accessibility(key: str, value: str, for_restore: bool = False) -> Command:
    """`settings put secure <key> <value>` for the two accessibility keys only (rule 6/9)."""
    if key == "accessibility_enabled":
        if value not in ("0", "1"):
            raise InvalidArgument("accessibility_enabled must be 0 or 1")
    elif key == "enabled_accessibility_services":
        _check_services(value)
    else:
        raise InvalidArgument(f"not an accessibility key zentv may set: {key!r}")
    return _cmd(
        ["settings", "put", "secure", key, value],
        Kind.CHANGE,
        f"set {key}",
        records=(Record("setting", f"secure/{key}"),),
        gate_exempt=for_restore,
    )


def delete_accessibility(key: str, for_restore: bool = False) -> Command:
    """`settings delete secure <key>`: only to put back a value that was unset before zentv."""
    if key not in ACCESSIBILITY_KEYS:
        raise InvalidArgument(f"not an accessibility key zentv may reset: {key!r}")
    return _cmd(
        ["settings", "delete", "secure", key],
        Kind.CHANGE,
        f"reset {key}",
        records=(Record("setting", f"secure/{key}"),),
        gate_exempt=for_restore,
    )


def tcl_appop(package: str, op: str, mode: str, brand: str, for_restore: bool = False) -> Command:
    """`appops set <zentv> APP_AUTO_START|AUTO_START <mode>`: TCL only, zentv's own package only
    (rule 6, approved at Checkpoint 2)."""
    if brand.lower() != "tcl":
        raise InvalidArgument("the boot app-op is for TCL TVs only")
    if package not in OWN_PACKAGES:
        raise InvalidArgument(f"the boot app-op is only for zentv's own package, not {package!r}")
    if op not in TCL_BOOT_OPS or mode not in APPOP_MODES:
        raise InvalidArgument(f"app-op/mode not allowed: {op} {mode}")
    return _cmd(
        ["appops", "set", package, op, mode],
        Kind.CHANGE,
        f"{op}={mode} for {package}",
        records=(Record("appop", f"{package}/{op}"),),
        gate_exempt=for_restore,
    )


def appops_write_settings(package: str, op: str, for_restore: bool = False) -> Command:
    """`appops write-settings`: TCL keeps an app-op across reboots only after this."""
    if package not in OWN_PACKAGES or op not in TCL_BOOT_OPS:
        raise InvalidArgument("write-settings only follows zentv's own TCL boot app-op")
    return _cmd(
        ["appops", "write-settings"],
        Kind.CHANGE,
        "persist app-ops",
        records=(Record("appop", f"{package}/{op}"),),
        gate_exempt=for_restore,
    )
