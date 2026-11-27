"""M3a launcher commands: install zentv's own APK, enable the Home helper (+ TCL app-op), revert."""

import pytest
from fakedevice import tcl_g03

from zenctl import device, launcher
from zenctl.adb import Session
from zenctl.errors import NotAllowed

PKG, SVC = launcher.SPIKE_PACKAGE, launcher.SPIKE_SERVICE


def _session(dev, yes=True, allowed=True):
    s = Session(dev, yes=yes, state_changes_allowed=allowed)
    return s, device.identify(s)


def _apk(tmp_path):
    p = tmp_path / "app-spike.apk"
    p.write_bytes(b"PK")
    return p


def test_install_needs_confirmed_profile_and_reads_back(tcl, tmp_path):
    s, _ = _session(tcl, allowed=False)
    with pytest.raises(NotAllowed):
        launcher.install(s, _apk(tmp_path), package=PKG)
    s, _ = _session(tcl)
    launcher.install(s, _apk(tmp_path), package=PKG)
    assert PKG in tcl.packages and any(line.startswith("adb install -r ") for line in tcl.log)


def test_install_dry_run_sends_nothing(tcl, tmp_path):
    s, _ = _session(tcl, yes=False)
    launcher.install(s, _apk(tmp_path), package=PKG)
    assert PKG not in tcl.packages and s.recorded == {PKG: None}


def test_enable_on_tcl_sets_the_boot_appop_and_binds(tcl, tmp_path):
    s, ident = _session(tcl)
    launcher.install(s, _apk(tmp_path), package=PKG)
    cmds, snap = launcher.enable_home_key(s, ident)
    assert cmds[0].argv[:3] == ("appops", "set", PKG)
    assert tcl.appops[f"{PKG}/APP_AUTO_START"] == "allow"
    st = launcher.status(s, ident)
    assert st["accessibility_enabled"] == "1" and SVC in st["enabled_accessibility_services"]
    assert st["helper_bound"] is True and st["app_auto_start"] == "allow"
    assert snap.records == {
        "secure/enabled_accessibility_services": None,
        "secure/accessibility_enabled": "0",
        f"{PKG}/APP_AUTO_START": "default",
    }


def test_without_the_appop_tcl_would_not_bind(tcl, tmp_path):
    """Why rule 6 allows the app-op: the fake models TclAppBoot refusing to bind without it."""
    s, ident = _session(tcl)
    launcher.install(s, _apk(tmp_path), package=PKG)
    tcl.settings["secure"].update(enabled_accessibility_services=SVC, accessibility_enabled="1")
    assert launcher.status(s, ident)["helper_bound"] is False


def test_sony_gets_no_appop(sony, tmp_path):
    s, ident = _session(sony)
    launcher.install(s, _apk(tmp_path), package=PKG)
    cmds, _ = launcher.enable_home_key(s, ident)
    assert all(c.argv[0] != "appops" for c in cmds)


def test_revert_puts_everything_back_and_keeps_other_services(tcl, tmp_path):
    other = "com.example.reader/com.example.reader.Svc"
    tcl.packages["com.example.reader"] = {"system": False, "enabled": True}
    tcl.settings["secure"]["enabled_accessibility_services"] = other
    s, ident = _session(tcl)
    launcher.install(s, _apk(tmp_path), package=PKG)
    launcher.enable_home_key(s, ident)
    assert tcl.settings["secure"]["enabled_accessibility_services"] == f"{other}:{SVC}"
    s2, ident2 = _session(tcl, allowed=False)  # revert works even when the gate is closed (e.g. after an OTA)
    _, mismatches = launcher.revert(s2, ident2, launcher.latest_launcher_snapshot(ident2))
    assert mismatches == []
    assert tcl.settings["secure"]["enabled_accessibility_services"] == other
    assert tcl.settings["secure"]["accessibility_enabled"] == "0"
    assert f"{PKG}/APP_AUTO_START" not in tcl.appops  # back to default
    assert PKG in tcl.packages  # never uninstalled (rule 5)


def test_revert_deletes_a_setting_that_was_unset(tcl, tmp_path):
    s, ident = _session(tcl)
    launcher.install(s, _apk(tmp_path), package=PKG)
    launcher.enable_home_key(s, ident)
    launcher.revert(*_session(tcl)[:1], ident, launcher.latest_launcher_snapshot(ident))
    assert "enabled_accessibility_services" not in tcl.settings["secure"]


def test_snapshot_from_another_tv_is_refused(tcl, tmp_path):
    s, ident = _session(tcl)
    launcher.install(s, _apk(tmp_path), package=PKG)
    _, snap = launcher.enable_home_key(s, ident)
    other = tcl_g03()
    other.props["ro.serialno"] = "9999XYZ000000Z99999"
    s2, ident2 = _session(other)
    with pytest.raises(Exception, match="different TV"):
        launcher.revert(s2, ident2, snap)


def test_enable_dry_run_sends_nothing(tcl, tmp_path):
    s, _ = _session(tcl)
    launcher.install(s, _apk(tmp_path), package=PKG)
    before = (dict(tcl.settings["secure"]), dict(tcl.appops))
    s2, ident2 = _session(tcl, yes=False)
    _, snap = launcher.enable_home_key(s2, ident2)
    assert snap is None and len(s2.planned) == 4
    assert (dict(tcl.settings["secure"]), dict(tcl.appops)) == before


def test_debloat_snapshot_lookups_ignore_launcher_snapshots(tcl, tmp_path):
    """Regression (TCL, 2026-11-27): `zentv restore` picked launcher-*.json as the latest snapshot."""
    from zenctl import snapshot

    s, ident = _session(tcl)
    launcher.install(s, _apk(tmp_path), package=PKG)
    launcher.enable_home_key(s, ident)
    assert launcher.latest_launcher_snapshot(ident) is not None
    assert snapshot.latest(snapshot.device_key(ident)) is None
    assert snapshot.all_for(snapshot.device_key(ident)) == []
