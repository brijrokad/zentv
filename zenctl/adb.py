"""Talking to the TV: the transport (Google's `adb`) and the session that guards every send.

Session.send() is the single path to the TV (ARCHITECTURE.md §3.2):
  1. the command was built by zenctl.commands        else TypeError
  2. refuse.check() on its tokens and final string     else Refused
  3. a state change without --yes is printed, not sent (dry-run)
  4. a state change on an unconfirmed profile          else NotAllowed (except adb-close)
  5. a state change whose pre-state was not recorded   else NotRecorded
  6. adb shell, argv list, timeout; output logged redacted
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Protocol

from . import refuse
from .commands import Command, Kind
from .errors import AdbError, NotAllowed, NotRecorded

DEFAULT_TIMEOUT = 30.0


@dataclass(frozen=True)
class ShellResult:
    returncode: int
    stdout: str
    stderr: str


class Transport(Protocol):
    def shell(self, command: str, timeout: float) -> ShellResult: ...


class AdbTransport:
    """`adb -s <serial> shell <command>`; never shell=True on the Mac side."""

    def __init__(self, serial: str, adb_path: str | None = None) -> None:
        self.serial = serial
        self.adb = adb_path or find_adb()

    def shell(self, command: str, timeout: float) -> ShellResult:
        return run_host([self.adb, "-s", self.serial, "shell", command], timeout)


def find_adb() -> str:
    path = shutil.which("adb")
    if not path:
        raise AdbError(
            "adb not found. Install Google's platform-tools: brew install --cask android-platform-tools"
        )
    return path


def run_host(argv: list[str], timeout: float = DEFAULT_TIMEOUT) -> ShellResult:
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as e:
        raise AdbError(f"timed out after {timeout:.0f} s: {' '.join(argv[:4])} ...") from e
    except OSError as e:
        raise AdbError(f"could not run {argv[0]}: {e}") from e
    return ShellResult(p.returncode, p.stdout, p.stderr)


def connected_devices(adb_path: str | None = None) -> list[tuple[str, str]]:
    """(serial, state) for every device `adb devices` lists."""
    out = run_host([adb_path or find_adb(), "devices"], 15).stdout
    rows = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2:
            rows.append((parts[0], parts[1]))
    return rows


@dataclass
class Session:
    transport: Transport
    yes: bool = False
    state_changes_allowed: bool = False
    timeout: float = DEFAULT_TIMEOUT
    log: list[str] = field(default_factory=list)
    recorded: dict[str, str | None] = field(default_factory=dict)
    planned: list[Command] = field(default_factory=list)  # dry-run output

    def read(self, cmd: Command) -> str:
        if cmd.kind is not Kind.READ:
            raise TypeError("read() takes read-only commands; use change()")
        return self._send(cmd).stdout

    def probe(self, cmd: Command) -> ShellResult:
        """A read-only command whose failure is an answer (e.g. an app-op name the build lacks)."""
        if cmd.kind is not Kind.READ:
            raise TypeError("probe() takes read-only commands")
        return self._send(cmd, check=False)

    def record(self, cmd: Command) -> None:
        """Read and store the pre-state of everything `cmd` touches (ground rule 6)."""
        for rec in cmd.records:
            if rec.key in self.recorded:
                continue  # first record wins
            self.recorded[rec.key] = rec.parse(self.read(rec.reader()))

    def change(self, cmd: Command) -> ShellResult | None:
        if cmd.kind is not Kind.CHANGE:
            raise TypeError("change() takes state changes; use read()")
        if not cmd.gate_exempt and not self.state_changes_allowed:
            raise NotAllowed(
                "this TV is read-only for zentv: its profile is not confirmed, or its firmware fingerprint "
                "changed since it was confirmed (Phase 3 confirms profiles)"
            )
        missing = [r.key for r in cmd.records if r.key not in self.recorded]
        if missing:
            raise NotRecorded(f"pre-state not recorded for {', '.join(missing)}; nothing was sent")
        if not self.yes:
            refuse.check(cmd.shell_string(), cmd.argv)
            self.planned.append(cmd)
            return None
        return self._send(cmd)

    def _send(self, cmd: Command, check: bool = True) -> ShellResult:
        if not isinstance(cmd, Command):
            raise TypeError("only zenctl.commands.Command objects can be sent")
        s = cmd.shell_string()
        refuse.check(s, cmd.argv)
        self.log.append(s)
        res = self.transport.shell(s, self.timeout)
        if check and res.returncode != 0:
            raise AdbError(
                f"`{s}` failed (exit {res.returncode}): {(res.stderr or res.stdout).strip()[:300]}"
            )
        return res
