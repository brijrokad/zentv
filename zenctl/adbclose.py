"""Close ADB at the end of every TV session, then prove it from the Mac (ground rule 10).

Verification greets each port with ADB's CNXN message and reads the 24-byte reply header. adbd
answers CNXN, AUTH or STLS, so any of those means network ADB is still on. The greeting carries
no key, so it cannot raise the TV's "Allow USB debugging?" prompt. (Concept from cleanyourtv
tools/adb-closed.py, reimplemented; see THIRD_PARTY_NOTICES.md.)
"""

from __future__ import annotations

import re
import socket
import struct
from dataclasses import dataclass

from . import commands as C
from .adb import Session, find_adb, run_host
from .errors import AdbError

A_CNXN, A_AUTH, A_STLS = 0x4E584E43, 0x48545541, 0x534C5453
ADB_ANSWERS = {A_CNXN: "CNXN", A_AUTH: "AUTH", A_STLS: "STLS"}
ADB_PORT = 5555
CONNECT_TIMEOUT = 3.0
HANDSHAKE_TIMEOUT = 3.0


def greeting() -> bytes:
    payload = b"host::\0"
    return (
        struct.pack(
            "<6I",
            A_CNXN,
            0x01000001,
            256 * 1024,
            len(payload),
            sum(payload) & 0xFFFFFFFF,
            A_CNXN ^ 0xFFFFFFFF,
        )
        + payload
    )


def classify_header(header: bytes) -> str | None:
    if len(header) != 24:
        return None
    command, *_rest, magic = struct.unpack("<6I", header)
    if command in ADB_ANSWERS and magic == command ^ 0xFFFFFFFF:
        return ADB_ANSWERS[command]
    return None


@dataclass(frozen=True)
class PortResult:
    port: int
    state: str  # "closed" | "adb" | "not-adb" | "unknown"
    detail: str

    @property
    def ok(self) -> bool:
        return self.state == "closed"


def probe_port(host: str, port: int) -> PortResult:
    try:
        sock = socket.create_connection((host, port), timeout=CONNECT_TIMEOUT)
    except ConnectionRefusedError:
        return PortResult(port, "closed", "connection refused")
    except TimeoutError:
        return PortResult(port, "unknown", "no answer (filtered, asleep, or unreachable)")
    except OSError as e:
        return PortResult(port, "unknown", f"unreachable ({e})")
    with sock:
        header = b""
        try:
            sock.settimeout(HANDSHAKE_TIMEOUT)
            sock.sendall(greeting())
            while len(header) < 24:
                chunk = sock.recv(24 - len(header))
                if not chunk:
                    break
                header += chunk
        except TimeoutError:
            return PortResult(port, "unknown", "open, but silent to ADB's greeting")
        except OSError as e:
            return PortResult(port, "unknown", f"open, greeting failed ({e})")
    answer = classify_header(header)
    if answer:
        return PortResult(port, "adb", f"network ADB is ON (answered {answer})")
    if not header:
        return PortResult(port, "not-adb", "open, hung up on ADB's greeting")
    return PortResult(port, "not-adb", "open, answered something that is not ADB")


MDNS_TLS = re.compile(r"_adb-tls-(connect|pairing)\._tcp\.?\s+(\S+):(\d+)")


def mdns_ports(host: str, adb_path: str | None = None) -> list[int]:
    """Wireless-debugging ports this host advertises over mDNS (empty when none or mDNS unavailable)."""
    try:
        out = run_host([adb_path or find_adb(), "mdns", "services"], 10).stdout
    except AdbError:
        return []
    return sorted({int(m.group(3)) for m in MDNS_TLS.finditer(out) if m.group(2) == host})


def switch_off(session: Session, usb_debugging_too: bool = True) -> list[C.Command]:
    """Record, then (with --yes) send the switch-offs. Wireless first; adb_enabled last (it ends the link)."""
    keys = list(C.ADB_NETWORK_KEYS if usb_debugging_too else C.ADB_NETWORK_KEYS[:1])
    cmds = [C.adb_network_off(k) for k in keys]
    for cmd in cmds:
        session.record(cmd)
    for cmd in cmds:
        try:
            session.change(cmd)
        except AdbError:
            if cmd.argv[3] == "adb_enabled" and session.yes:
                continue  # the link drops as adbd stops; verification decides
            raise
    return cmds


def verify(host: str, ports: list[int] | None = None, adb_path: str | None = None) -> list[PortResult]:
    wanted = sorted(set((ports or []) + [ADB_PORT] + mdns_ports(host, adb_path)))
    return [probe_port(host, p) for p in wanted]
