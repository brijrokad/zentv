"""Exceptions. Each one stops the run before anything else is sent to the TV."""


class ZenError(Exception):
    """Base class. The CLI prints the message and exits non-zero."""

    exit_code = 1


class Refused(ZenError):
    """A command or package is on a hard-refuse list (ground rules 5 and 7, safety/never_disable.yaml)."""

    exit_code = 3


class NotAllowed(ZenError):
    """The read-only gate: profile not confirmed, or firmware changed (ARCHITECTURE.md §3.3)."""

    exit_code = 4


class NotRecorded(ZenError):
    """A state change was about to be sent before its pre-state was recorded (ground rule 6)."""

    exit_code = 5


class AdbError(ZenError):
    """adb failed, timed out, or is missing."""

    exit_code = 6


class InvalidArgument(ZenError):
    """A package name, property, setting key or other argument failed validation."""

    exit_code = 2
