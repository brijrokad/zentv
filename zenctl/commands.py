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

    kind: str  # "setting" (M1); "package", "home", "appop" arrive with their changes
    key: str  # e.g. "global/adb_wifi_enabled"

    def reader(self) -> Command:
        if self.kind == "setting":
            ns, k = self.key.split("/", 1)
            return settings_get(ns, k)
        raise InvalidArgument(f"no reader for record kind {self.kind!r}")


@dataclass(frozen=True)
class Command:
    argv: tuple[str, ...]
    kind: Kind
    summary: str
    records: tuple[Record, ...] = ()
    # Only adb_network_off: closing ADB is allowed even on an unconfirmed profile (rule 10).
    gate_exempt: bool = False
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
