import os
import stat
import sys
from pathlib import Path

import pytest
from fakedevice import sony_vh21, tcl_g03

from zenctl.adb import Session

REPO = Path(__file__).resolve().parent.parent
SHIM = """#!{python}
import sys
sys.path.insert(0, {tests!r})
sys.path.insert(0, {repo!r})
from fake_adb_main import main
sys.exit(main(sys.argv[1:]))
"""


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Never touch the real ~/.zentv or a real TV from tests."""
    monkeypatch.setenv("ZENTV_HOME", str(tmp_path / "zentv-home"))
    monkeypatch.delenv("ZENTV_SERIAL", raising=False)
    monkeypatch.delenv("ZENTV_REPO", raising=False)


@pytest.fixture
def tcl():
    return tcl_g03()


@pytest.fixture
def sony():
    return sony_vh21()


@pytest.fixture
def session_for():
    def make(dev, yes=False, allowed=False):
        return Session(dev, yes=yes, state_changes_allowed=allowed)

    return make


@pytest.fixture
def fake_adb(tmp_path, monkeypatch):
    """Put a fake `adb` first on PATH. Returns a function that loads a FakeDevice into it."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    shim = bindir / "adb"
    shim.write_text(SHIM.format(python=sys.executable, tests=str(REPO / "tests"), repo=str(REPO)))
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    state = tmp_path / "fake-tv.json"
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_ADB_STATE", str(state))

    def load(dev, serial="192.0.2.10:5555"):
        monkeypatch.setenv("FAKE_ADB_SERIAL", serial)
        state.write_text(dev.to_json())
        return state

    return load
