"""Session.send rules: dry-run default, read-only gate, record-before-change, first record wins."""

import pytest

from zenctl import commands as C
from zenctl.adb import Session
from zenctl.errors import AdbError, NotAllowed, NotRecorded, Refused


def _hypothetical_change():
    # A non-exempt state change, as M2 will add (built through the private constructor for the test only).
    return C._cmd(
        ["settings", "put", "secure", "accessibility_enabled", "1"],
        C.Kind.CHANGE,
        "test change",
        records=(C.Record("setting", "secure/accessibility_enabled"),),
    )


def test_dry_run_sends_no_state_change(tcl, session_for):
    s = session_for(tcl, yes=False)
    cmd = C.adb_network_off("adb_enabled")
    s.record(cmd)
    assert s.change(cmd) is None
    assert s.planned == [cmd]
    assert all(not line.startswith("settings put") for line in tcl.log)
    assert tcl.settings["global"]["adb_enabled"] == "1"


def test_yes_sends_after_recording(tcl, session_for):
    s = session_for(tcl, yes=True)
    cmd = C.adb_network_off("adb_enabled")
    s.record(cmd)
    s.change(cmd)
    assert s.recorded == {"global/adb_enabled": "1"}
    assert tcl.settings["global"]["adb_enabled"] == "0"


def test_change_without_record_is_refused(tcl, session_for):
    s = session_for(tcl, yes=True)
    with pytest.raises(NotRecorded):
        s.change(C.adb_network_off("adb_enabled"))
    assert tcl.settings["global"]["adb_enabled"] == "1"


def test_gate_blocks_non_exempt_changes_even_in_dry_run(tcl, session_for):
    s = session_for(tcl, yes=True, allowed=False)
    cmd = _hypothetical_change()
    s.record(cmd)
    with pytest.raises(NotAllowed):
        s.change(cmd)
    assert "settings put secure accessibility_enabled 1" not in tcl.log


def test_gate_allows_when_confirmed(tcl, session_for):
    s = session_for(tcl, yes=True, allowed=True)
    cmd = _hypothetical_change()
    s.record(cmd)
    s.change(cmd)
    assert tcl.settings["secure"]["accessibility_enabled"] == "1"


def test_first_record_wins(tcl, session_for):
    s = session_for(tcl, yes=True)
    cmd = C.adb_network_off("adb_enabled")
    s.record(cmd)
    s.change(cmd)
    s.record(cmd)  # re-recording after the change must not overwrite the original state
    assert s.recorded["global/adb_enabled"] == "1"


def test_only_command_objects_are_sent(tcl):
    s = Session(tcl)
    with pytest.raises(TypeError):
        s._send("pm uninstall com.example.app")  # type: ignore[arg-type]


def test_read_and_change_are_not_interchangeable(tcl):
    s = Session(tcl)
    with pytest.raises(TypeError):
        s.read(C.adb_network_off("adb_enabled"))
    with pytest.raises(TypeError):
        s.change(C.getprop())


def test_refuse_runs_on_the_wire(tcl, monkeypatch):
    s = Session(tcl, yes=True)
    cmd = C.getprop("ro.product.model")
    monkeypatch.setattr(C.Command, "shell_string", lambda self: "pm uninstall com.example.app")
    with pytest.raises(Refused):
        s.read(cmd)
    assert tcl.log == []


def test_adb_errors_surface(tcl):
    s = Session(tcl)
    with pytest.raises(AdbError):
        s.read(C.appops_get("android", "AUTO_START"))  # unknown op on this fake build
    assert s.probe(C.appops_get("android", "AUTO_START")).returncode != 0
