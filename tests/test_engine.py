"""M2: plan, snapshot, apply, restore, check, smoke-test (ARCHITECTURE.md §5 acceptance tests)."""

import json
import shutil
from pathlib import Path

import pytest
import yaml
from fakedevice import tcl_g03

from zenctl import apply as engine
from zenctl import cli, device, paths, safety, smoke
from zenctl import commands as C
from zenctl import plan as planner
from zenctl import snapshot as snapshots
from zenctl.adb import Session
from zenctl.errors import InvalidArgument, NotAllowed, Refused

POLICY = safety.load(paths.safety_file())
REPO = Path(__file__).resolve().parent.parent

DEBLOAT = {
    "schema": 1,
    "device": "tcl-g03-beyondtv4",
    "targets": [
        {
            "package": "android.autoinstalls.config.google.gtvpai",
            "reason": "partner installs",
            "risk": "low",
            "default": "on",
            "owner": "approved: disable",
        },
        {
            "package": "com.tcl.dashboard",
            "reason": "promo",
            "risk": "low",
            "default": "on",
            "owner": "approved: disable",
        },
        {"package": "com.tcl.ocean.instructions", "reason": "manual", "risk": "low", "default": "on"},
        {
            "package": "com.tcl.partnercustomizer",
            "reason": "promo rows",
            "risk": "medium",
            "default": "off",
            "owner": "keep enabled",
        },
        {"package": "com.tcl.esticker", "reason": "already off", "risk": "low", "default": "on"},
        {"package": "com.tcl.notinstalled", "reason": "absent", "risk": "low", "default": "on"},
    ],
    "restore_hidden": [
        {"package": "com.google.android.apps.mediashell", "reason": "cast"},
        {"package": "com.google.android.katniss", "reason": "voice"},
    ],
}


def _setup(dev=None, yes=False, confirmed=True):
    dev = dev or tcl_g03()
    s = Session(dev, yes=yes)
    ident = device.identify(s)
    prof = device.Profile(
        "tcl-g03-beyondtv4",
        Path("x"),
        "confirmed" if confirmed else "unverified",
        "tcl",
        "realtek",
        {"ro.product.device": "BeyondTV4"},
        ident.fingerprint,
    )
    s.state_changes_allowed, _ = device.gate(prof, ident)
    return dev, s, ident, prof


def _plan(s, ident, prof, debloat=DEBLOAT, include=None):
    return planner.build(s, ident, prof, POLICY, debloat, include)


def _pkg_states(dev):
    return {
        n: (p.get("enabled", True), p.get("state"), p.get("hidden", False)) for n, p in dev.packages.items()
    }


# ---- plan ------------------------------------------------------------------------------------


def test_plan_selection_rules():
    _, s, ident, prof = _setup()
    p = _plan(s, ident, prof)
    acts = [(a.op, a.package) for a in p.actions]
    assert acts == [
        ("disable", "android.autoinstalls.config.google.gtvpai"),
        ("disable", "com.tcl.dashboard"),
        ("disable", "com.tcl.ocean.instructions"),  # default on, no owner field
        ("unhide", "com.google.android.apps.mediashell"),
        ("unhide", "com.google.android.katniss"),
    ]
    skipped = dict(p.skipped)
    assert "keep" in skipped["com.tcl.partnercustomizer"]
    assert "already disabled" in skipped["com.tcl.esticker"]
    assert "not installed" in skipped["com.tcl.notinstalled"]


def test_plan_refuses_whole_plan_on_a_protected_package():
    _, s, ident, prof = _setup()
    bad = {
        **DEBLOAT,
        "targets": [
            *DEBLOAT["targets"],
            {"package": "com.tcl.tv", "reason": "x", "risk": "low", "default": "on"},
        ],
    }
    with pytest.raises(Refused):
        _plan(s, ident, prof, bad)


def test_plan_refuses_other_firmware():
    _, s, ident, prof = _setup()
    with pytest.raises(NotAllowed):
        _plan(s, ident, prof, {**DEBLOAT, "fingerprint": "TCL/other/build"})


def test_plan_is_read_only():
    dev, s, ident, prof = _setup()
    before = _pkg_states(dev)
    _plan(s, ident, prof)
    assert _pkg_states(dev) == before


# ---- apply / restore round trip --------------------------------------------------------------


def test_dry_run_sends_nothing_and_writes_no_snapshot():
    dev, s, ident, prof = _setup(yes=False)
    before = _pkg_states(dev)
    res = engine.apply(s, ident, _plan(s, ident, prof), settle_s=0)
    assert res.snapshot is None and res.sent == []
    assert len(s.planned) == 5
    assert _pkg_states(dev) == before
    assert snapshots.all_for(snapshots.device_key(ident)) == []


def test_round_trip_restores_every_disabled_package():
    dev, s, ident, prof = _setup(yes=True)
    before = _pkg_states(dev)
    res = engine.apply(s, ident, _plan(s, ident, prof), settle_s=0)
    assert len(res.sent) == 5
    assert dev.packages["com.tcl.dashboard"]["state"] == 3
    assert dev.packages["com.google.android.katniss"]["hidden"] is False
    snap = snapshots.load(Path(res.snapshot.path))
    assert snap.records["com.tcl.dashboard"] == "enabled=0 hidden=false installed=true"

    _, s2, ident2, _ = _setup(dev, yes=True)
    cmds, mismatches, notes = engine.restore(s2, ident2, snap)
    assert mismatches == []
    assert len(cmds) == 3 and all(c.startswith("pm enable --user 0") for c in cmds)
    assert any("un-hidden" in n for n in notes)  # restore never re-hides
    after = _pkg_states(dev)
    for pkg in (
        "android.autoinstalls.config.google.gtvpai",
        "com.tcl.dashboard",
        "com.tcl.ocean.instructions",
    ):
        assert after[pkg][0] is True and before[pkg][0] is True
    assert after["com.google.android.katniss"][2] is False
    assert after["com.tcl.esticker"] == before["com.tcl.esticker"]  # owner's prior state untouched


def test_restore_reports_mismatches(monkeypatch):
    dev, s, ident, prof = _setup(yes=True)
    snap = engine.apply(s, ident, _plan(s, ident, prof), settle_s=0).snapshot
    _, s2, ident2, _ = _setup(dev, yes=True)
    real_shell = dev.shell

    def stuck(cmd, timeout=30.0):  # a TV that ignores `pm enable` for one package
        if cmd == "pm enable --user 0 com.tcl.dashboard":
            dev.log.append(cmd)
            from zenctl.adb import ShellResult

            return ShellResult(0, "", "")
        return real_shell(cmd, timeout)

    monkeypatch.setattr(dev, "shell", stuck)
    _, mismatches, _ = engine.restore(s2, ident2, snap)
    assert [m.package for m in mismatches] == ["com.tcl.dashboard"]


def test_restore_works_after_a_firmware_change_but_not_for_another_tv():
    dev, s, ident, prof = _setup(yes=True)
    snap = engine.apply(s, ident, _plan(s, ident, prof), settle_s=0).snapshot
    dev.props["ro.build.fingerprint"] = dev.props["ro.build.fingerprint"].replace("AR24", "AR30")
    s2 = Session(dev, yes=True, state_changes_allowed=False)  # gate closed after the OTA
    _, mismatches, _ = engine.restore(s2, device.identify(s2), snap)
    assert mismatches == []

    other = tcl_g03()
    other.props["ro.serialno"] = "9999XYZ000000Z99999"
    s3 = Session(other, yes=True)
    with pytest.raises(Refused):
        engine.restore(s3, device.identify(s3), snap)


def test_first_record_wins_on_a_half_finished_retry():
    dev, s, ident, prof = _setup(yes=True)
    # Simulate a run that died after the first change: the snapshot exists, one package is already off.
    p = _plan(s, ident, prof)
    for cmd in engine.commands_for(p):
        s.record(cmd)
    original = snapshots.create(ident, p, s.recorded)
    dev.packages["android.autoinstalls.config.google.gtvpai"].update(enabled=False, state=3)

    _, s2, ident2, prof2 = _setup(dev, yes=True)
    p2 = _plan(s2, ident2, prof2)
    assert p2.digest == p.digest  # same intent, same snapshot
    res = engine.apply(s2, ident2, p2, settle_s=0)
    assert res.snapshot.path == original.path
    assert res.snapshot.records["android.autoinstalls.config.google.gtvpai"].startswith("enabled=0")
    assert len(snapshots.all_for(snapshots.device_key(ident))) == 1


def test_apply_needs_a_confirmed_profile():
    dev, s, ident, prof = _setup(yes=True, confirmed=False)
    with pytest.raises(NotAllowed):
        engine.apply(s, ident, _plan(s, ident, prof), settle_s=0)
    assert all(not c.startswith("pm ") or c.startswith("pm list") for c in dev.log)


def test_unhide_is_limited_to_the_approved_list():
    with pytest.raises(InvalidArgument):
        C.unhide("com.tcl.messagebox", frozenset({"com.google.android.katniss"}))


def test_snapshot_files_are_private():
    _dev, s, ident, prof = _setup(yes=True)
    snap = engine.apply(s, ident, _plan(s, ident, prof), settle_s=0).snapshot
    p = Path(snap.path)
    assert oct(p.stat().st_mode & 0o777) == "0o600"
    assert "1234ABC567890D12345" not in p.read_text()  # synthetic serial never stored


# ---- check -----------------------------------------------------------------------------------


def test_check_reports_drift_and_changes_nothing():
    dev, s, ident, prof = _setup(yes=True)
    snap = engine.apply(s, ident, _plan(s, ident, prof), settle_s=0).snapshot
    dev.packages["com.tcl.dashboard"].update(enabled=True, state=1)
    before = _pkg_states(dev)
    drift = engine.check(Session(dev), snap)
    assert drift == ["com.tcl.dashboard: zentv disabled it, now enabled=1"]
    assert _pkg_states(dev) == before


# ---- smoke -----------------------------------------------------------------------------------


def test_smoke_records_skips_and_failures(tmp_path):
    prof_file = tmp_path / "profile.yaml"
    prof_file.write_text(yaml.safe_dump({"smoke": ["remote works", "casting works", "ethernet links"]}))
    prof = device.Profile("t", prof_file, "confirmed", "tcl", "realtek", {}, "fp")
    answers = iter(["y", "maybe", "n", "s"])
    failed, out = smoke.run(prof, ask=lambda _q: next(answers))
    assert failed == ["casting works"]
    results = json.loads(out.read_text())["results"]
    assert [r["ok"] for r in results] == [True, False, None]


def test_repo_tcl_profile_has_a_smoke_list():
    prof = next(p for p in device.load_profiles(paths.devices_dir()) if p.name == "tcl-g03-beyondtv4")
    assert len(smoke.items(prof)) >= 8


# ---- CLI end to end through the fake adb, with a confirmed test profile ---------------------


@pytest.fixture
def test_repo(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    shutil.copytree(REPO / "safety", repo / "safety")
    d = repo / "devices" / "tcl-g03-beyondtv4"
    d.mkdir(parents=True)
    fake = tcl_g03()
    (d / "profile.yaml").write_text(
        yaml.safe_dump(
            {
                "status": "confirmed",
                "brand": "tcl",
                "soc": "realtek",
                "match": {"ro.product.device": "BeyondTV4", "ro.product.name": "G03_4K_US_NF_DB"},
                "fingerprint": fake.props["ro.build.fingerprint"],
            }
        )
    )
    (d / "debloat.yaml").write_text(yaml.safe_dump(DEBLOAT))
    monkeypatch.setenv("ZENTV_REPO", str(repo))
    return repo


def test_cli_apply_dry_run_then_yes_then_restore(fake_adb, test_repo, capsys):
    state = fake_adb(tcl_g03())
    assert cli.main(["plan"]) == 0
    assert "allowed" in capsys.readouterr().out

    assert cli.main(["apply"]) == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "pm disable-user --user 0 com.tcl.dashboard" in out
    assert json.loads(state.read_text())["packages"]["com.tcl.dashboard"]["enabled"] is True

    assert cli.main(["apply", "--yes", "--settle", "0"]) == 0
    out = capsys.readouterr().out
    assert "snapshot:" in out and "To undo: zentv restore" in out
    tv = json.loads(state.read_text())
    assert tv["packages"]["com.tcl.dashboard"]["enabled"] is False
    assert tv["packages"]["com.google.android.apps.mediashell"]["hidden"] is False

    assert cli.main(["check"]) == 0
    assert cli.main(["restore"]) == 0
    assert "DRY RUN" in capsys.readouterr().out
    assert cli.main(["restore", "--yes"]) == 0
    assert "every recorded package reads back as before" in capsys.readouterr().out
    assert json.loads(state.read_text())["packages"]["com.tcl.dashboard"]["enabled"] is True
