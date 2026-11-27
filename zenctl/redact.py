"""Mask identifiers before anything is written to the repo or a log (ARCHITECTURE.md §3.8).

Each distinct value gets a stable token (<SERIAL-1>, <MAC-2>...) so a redacted survey still shows
which entries refer to the same thing.
"""

from __future__ import annotations

import re
from typing import Any

SERIAL_PROPS = re.compile(
    r"(^|\.)(serialno|serial|sn|boot\.serialno|deviceid|device_id|uuid|mac|wifimac|btmac)$", re.IGNORECASE
)

PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b")),
    ("MAC", re.compile(r"\b[0-9A-Fa-f]{2}([:-])(?:[0-9A-Fa-f]{2}\1){4}[0-9A-Fa-f]{2}\b")),
    (
        "IPV6",
        re.compile(
            r"(?<![\w:.])(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}(?![\w:])"
            r"|(?<![\w:.])(?:[0-9A-Fa-f]{1,4}:){1,6}:(?:[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{1,4}){0,5})?"
            r"(?:%\w+)?(?![\w:])"
        ),
    ),
    (
        "IP",
        re.compile(
            r"\b(?!127\.0\.0\.1\b)(?!0\.0\.0\.0\b)(?:25[0-5]|2[0-4]\d|1?\d?\d)"
            r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}\b"
        ),
    ),
    # TCL-style serial: 4 digits, 3 letters, 6 digits, 1 letter, 5 digits (synthetic: 1234ABC567890D12345)
    ("SERIAL", re.compile(r"\b\d{4}[A-Z]{3}\d{6}[A-Z]\d{5}\b")),
)
# Quoted Wi-Fi names in dumpsys output: SSID: "name", ssid="name", SSID="name", networkName="..."
SSID = re.compile(r'((?:SSID|ssid|networkName|mSsid|WifiSsid)\s*[:=]\s*)"([^"]{1,64})"')


class Redactor:
    def __init__(self, known_secrets: dict[str, str] | None = None) -> None:
        self._tokens: dict[tuple[str, str], str] = {}
        self._count: dict[str, int] = {}
        # Literal values (serial numbers from getprop) replaced everywhere they appear.
        self._literals: list[tuple[str, str]] = []
        for kind, value in (known_secrets or {}).items():
            self.add_literal(kind, value)

    def add_literal(self, kind: str, value: str) -> None:
        value = value.strip()
        if len(value) >= 4 and value.lower() not in {"unknown", "null", "none"}:
            self._literals.append((kind, value))
            self._literals.sort(key=lambda kv: -len(kv[1]))

    def token(self, kind: str, value: str) -> str:
        key = (kind, value)
        if key not in self._tokens:
            self._count[kind] = self._count.get(kind, 0) + 1
            self._tokens[key] = f"<{kind}-{self._count[kind]}>"
        return self._tokens[key]

    def text(self, s: str) -> str:
        for kind, value in self._literals:
            if value in s:
                s = s.replace(value, self.token(kind, value))
        s = SSID.sub(lambda m: m.group(1) + '"' + self.token("SSID", m.group(2)) + '"', s)
        for kind, pattern in PATTERNS:
            s = pattern.sub(lambda m, k=kind: self.token(k, m.group(0)), s)
        return s

    def obj(self, o: Any) -> Any:
        if isinstance(o, str):
            return self.text(o)
        if isinstance(o, list):
            return [self.obj(x) for x in o]
        if isinstance(o, dict):
            return {self.text(k) if isinstance(k, str) else k: self.obj(v) for k, v in o.items()}
        return o


def from_props(props: dict[str, str]) -> Redactor:
    """A Redactor seeded with every serial-like property value the TV reported."""
    r = Redactor()
    for k, v in props.items():
        if SERIAL_PROPS.search(k) and v:
            r.add_literal("SERIAL", v)
    return r
