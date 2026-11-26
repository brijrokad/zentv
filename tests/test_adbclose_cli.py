"""adb-close (switch-off + network verification) and the CLI end to end through a fake `adb`."""

import json
import socket
import struct
import threading

import pytest

from zenctl import adbclose, cli
from zenctl.adb import Session

SYNTH_TCL_SERIAL = "1234ABC567890D12345"


# ---- verification against local fake ports ---------------------------------------------------


class FakePort:
    """A one-connection TCP server that answers ADB's greeting with `reply` (or stays silent)."""

    def __init__(self, reply: bytes | None):
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.reply = reply
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        conn, _ = self.sock.accept()
        with conn:
            conn.recv(64)
            if self.reply is not None:
                conn.sendall(self.reply)
            else:
                conn.recv(64)  # silent until the client gives up


def _hdr(cmd: int) -> bytes:
    return struct.pack("<6I", cmd, 0x01000001, 4096, 0, 0, cmd ^ 0xFFFFFFFF)


@pytest.mark.parametrize(
    "cmd,name", [(adbclose.A_CNXN, "CNXN"), (adbclose.A_AUTH, "AUTH"), (adbclose.A_STLS, "STLS")]
)
def test_any_adb_answer_means_open(cmd, name):
    srv = FakePort(_hdr(cmd))
    r = adbclose.probe_port("127.0.0.1", srv.port)
    assert r.state == "adb" and name in r.detail and not r.ok


def test_non_adb_service_is_not_adb():
    srv = FakePort(b"HTTP/1.1 400 Bad Request\r\n\r\n")
    assert adbclose.probe_port("127.0.0.1", srv.port).state == "not-adb"


def test_silent_port_is_unknown(monkeypatch):
    monkeypatch.setattr(adbclose, "HANDSHAKE_TIMEOUT", 0.3)
    srv = FakePort(None)
    assert adbclose.probe_port("127.0.0.1", srv.port).state == "unknown"


def test_refused_port_is_closed():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    assert adbclose.probe_port("127.0.0.1", port).ok


def test_greeting_is_a_valid_cnxn_without_a_key():
    g = adbclose.greeting()
    assert adbclose.classify_header(g[:24]) == "CNXN"
    assert g[24:] == b"host::\0"


# ---- switch-off ------------------------------------------------------------------------------


def test_switch_off_dry_run_records_and_sends_nothing(sony):
    s = Session(sony, yes=False, state_changes_allowed=False)
    cmds = adbclose.switch_off(s)
    assert [c.argv[3] for c in cmds] == ["adb_wifi_enabled", "adb_enabled"]
    assert s.recorded == {"global/adb_wifi_enabled": "1", "global/adb_enabled": "1"}
    assert sony.settings["global"] == {"adb_enabled": "1", "adb_wifi_enabled": "1"}


def test_switch_off_with_yes_works_on_an_unconfirmed_profile(sony):
    s = Session(sony, yes=True, state_changes_allowed=False)
    adbclose.switch_off(s)
    assert sony.settings["global"] == {"adb_enabled": "0", "adb_wifi_enabled": "0"}
    puts = [line for line in sony.log if line.startswith("settings put")]
    assert puts == ["settings put global adb_wifi_enabled 0", "settings put global adb_enabled 0"]


def test_keep_usb_debugging(sony):
    s = Session(sony, yes=True)
    adbclose.switch_off(s, usb_debugging_too=False)
    assert sony.settings["global"] == {"adb_enabled": "1", "adb_wifi_enabled": "0"}


# ---- CLI end to end through the fake adb -----------------------------------------------------


def test_cli_identify_is_read_only_and_redacted(fake_adb, tcl, capsys):
    state = fake_adb(tcl)
    assert cli.main(["identify"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["state_changes"] == "read-only" and out["profile"] is None
    assert SYNTH_TCL_SERIAL not in json.dumps(out)
    assert json.loads(state.read_text())["settings"] == tcl.settings


def test_cli_survey_writes_redacted_file(fake_adb, tcl, tmp_path):
    fake_adb(tcl)
    out = tmp_path / "survey.json"
    assert cli.main(["survey", "--out", str(out)]) == 0
    text = out.read_text()
    assert SYNTH_TCL_SERIAL not in text and '"com.tcl.bi"' in text


def test_cli_safety_live(fake_adb, tcl, capsys):
    fake_adb(tcl)
    rc = cli.main(["safety", "com.tcl.tv", "com.tcl.bi", "com.tcl.vendorhome", "com.tcl.usercenter"])
    out = capsys.readouterr().out
    assert rc == 3
    assert "REFUSED  com.tcl.tv" in out and "REFUSED  com.tcl.vendorhome" in out
    assert "allowed  com.tcl.bi" in out and "HIGH RISK com.tcl.usercenter" in out


def test_cli_adb_close_is_dry_run_by_default(fake_adb, sony, capsys):
    state = fake_adb(sony)
    assert cli.main(["adb-close"]) == 0
    assert "DRY RUN" in capsys.readouterr().out
    assert json.loads(state.read_text())["settings"]["global"] == {
        "adb_enabled": "1",
        "adb_wifi_enabled": "1",
    }


def test_cli_adb_close_yes_switches_off_then_verifies(fake_adb, sony, monkeypatch, capsys):
    state = fake_adb(sony, serial="127.0.0.1:5555")
    monkeypatch.setattr(
        adbclose,
        "verify",
        lambda host, ports=None, adb_path=None: [adbclose.PortResult(5555, "closed", "connection refused")],
    )
    assert cli.main(["adb-close", "--yes"]) == 0
    assert "ADB is closed." in capsys.readouterr().out
    assert json.loads(state.read_text())["settings"]["global"] == {
        "adb_enabled": "0",
        "adb_wifi_enabled": "0",
    }


def test_cli_reports_missing_tv(fake_adb, tcl, monkeypatch, capsys):
    fake_adb(tcl)
    monkeypatch.setenv("ZENTV_SERIAL", "198.51.100.9:5555")
    assert cli.main(["identify"]) != 0
    assert "not found" in capsys.readouterr().err


def test_cli_offline_safety(capsys):
    rc = cli.main(
        [
            "safety",
            "--offline",
            "--brand",
            "sony",
            "--device",
            "sony-bravia-4k-vh21",
            "com.sonyericsson.idd.agent",
            "com.sony.dtv.promo.example",
        ]
    )
    out = capsys.readouterr().out
    assert (
        rc == 3
        and "REFUSED  com.sonyericsson.idd.agent" in out
        and "allowed  com.sony.dtv.promo.example" in out
    )
