"""Device identity, the read-only gate, and safety/never_disable.yaml."""

import re

import pytest
import yaml

from zenctl import device, paths, safety
from zenctl.adb import Session
from zenctl.errors import ZenError

POLICY = safety.load(paths.safety_file())


def _profile(tmp_path, name, **data):
    d = tmp_path / name
    d.mkdir()
    (d / "profile.yaml").write_text(yaml.safe_dump(data))
    return tmp_path


# ---- identity and gate -----------------------------------------------------------------------


def test_identify_and_soc(tcl, sony):
    t = device.identify(Session(tcl))
    assert t.brand == "tcl" and t.soc == "realtek" and t.is_brand("TCL")
    s = device.identify(Session(sony))
    assert s.brand == "sony" and s.soc == "mediatek"


def test_gate_states(tmp_path, tcl):
    ident = device.identify(Session(tcl))
    fp = ident.fingerprint
    match = {"ro.product.device": "BeyondTV4", "ro.product.name": "G03_4K_US_NF_DB"}

    assert device.gate(None, ident)[0] is False

    unverified = device.Profile("t", tmp_path, "unverified", "tcl", "realtek", match, fp)
    assert device.gate(unverified, ident)[0] is False

    confirmed = device.Profile("t", tmp_path, "confirmed", "tcl", "realtek", match, fp)
    assert device.gate(confirmed, ident) == (True, "profile t confirmed for this firmware")
    assert confirmed.allows_changes(ident)

    after_ota = device.Profile(
        "t", tmp_path, "confirmed", "tcl", "realtek", match, fp.replace("AR24", "AR30")
    )
    assert device.gate(after_ota, ident)[0] is False


def test_profile_selection(tmp_path, tcl):
    ident = device.identify(Session(tcl))
    root = _profile(
        tmp_path,
        "tcl-x",
        status="confirmed",
        brand="tcl",
        match={"ro.product.device": "BeyondTV4"},
        fingerprint=ident.fingerprint,
    )
    _profile(root, "sony-x", status="unverified", brand="sony", match={"ro.product.device": "BRAVIA"})
    profiles = device.load_profiles(root)
    assert device.select_profile(profiles, ident).name == "tcl-x"
    _profile(root, "tcl-y", status="unverified", brand="tcl", match={"ro.product.name": "G03_4K_US_NF_DB"})
    with pytest.raises(ZenError):
        device.select_profile(device.load_profiles(root), ident)


def test_repo_profiles_confirmed_only_with_live_match_and_fingerprint():
    for p in device.load_profiles(paths.devices_dir()):
        if p.status == "confirmed":
            assert p.match and p.fingerprint, f"{p.name} is confirmed without a match block and fingerprint"
        else:
            assert p.status == "unverified"


# ---- policy file -----------------------------------------------------------------------------


def _ctx(brand, soc="unknown", devices=(), home=(), persistent=()):
    return safety.Context(
        brand=brand,
        soc=soc,
        devices=frozenset(devices),
        home_packages=frozenset(home),
        persistent=frozenset(persistent),
    )


def _sample(pattern: str) -> str:
    """A valid package name that the glob/entry matches."""
    if "*" not in pattern and "[" not in pattern:
        return pattern
    name = re.sub(r"\[(.)[^\]]*\]", r"\1", pattern).replace("*", "zz")
    return name if "." in name and not name.startswith(".") else "com." + name.lstrip(".")


def _ctx_for_scope(scope):
    if scope == "all":
        return _ctx("google")
    return _ctx(
        scope.get("brand", "google"),
        scope.get("soc", "unknown"),
        [scope["device"]] if "device" in scope else [],
    )


@pytest.mark.parametrize("group", POLICY.groups, ids=lambda g: g.id)
def test_every_entry_and_glob_refuses_in_its_scope(group):
    ctx = _ctx_for_scope(group.scope)
    for entry in (*group.packages, *group.globs):
        r = safety.check_package(POLICY, ctx, _sample(entry))
        assert r is not None, f"{entry} in {group.id} did not refuse"


def test_device_groups_stay_on_their_device():
    pkg = "com.sonyericsson.idd.agent"
    assert safety.check_package(POLICY, _ctx("sony", "mediatek", ["sony-bravia-4k-vh21"]), pkg)
    assert safety.check_package(POLICY, _ctx("sony", "mediatek", ["some-other-sony"]), pkg) is None


def test_brand_groups_stay_on_their_brand():
    assert safety.check_package(POLICY, _ctx("tcl"), "com.tcl.settings")
    assert safety.check_package(POLICY, _ctx("sony"), "com.tcl.settings") is None


def test_no_matched_profile_applies_every_same_brand_device_group():
    ctx = safety.context_for("tcl", "realtek", None, ["tcl-g03-beyondtv4"])
    assert safety.check_package(POLICY, ctx, "com.google.android.tv.remote.service")
    assert safety.check_package(POLICY, ctx, "com.tcl.tvinput.extra")


def test_case_sensitive_updater_names_are_caught():
    r = safety.check_package(POLICY, _ctx("hisense"), "com.vendor.versionUpdateApp")
    assert r and r.group == "dynamic"


def test_known_false_positive_stays_refused():
    assert safety.check_package(POLICY, _ctx("tcl"), "com.tcl.bootadservice")


def test_dynamic_home_and_persistent_from_the_live_tv(tcl):
    s = Session(tcl)
    ctx = safety.context_for(
        "tcl", "realtek", "tcl-g03-beyondtv4", [], session=s, packages=["com.tcl.system.server", "com.tcl.bi"]
    )
    assert "com.tcl.vendorhome" in ctx.home_packages
    r = safety.check_package(POLICY, ctx, "com.tcl.vendorhome")
    assert r and "HOME" in r.entry
    assert "com.tcl.system.server" in ctx.persistent
    assert safety.check_package(POLICY, ctx, "com.tcl.bi") is None
    assert all(not line.startswith(("settings put", "pm ")) or line.startswith("pm list") for line in tcl.log)


def test_high_risk_is_flagged_not_refused():
    ctx = _ctx("tcl")
    assert safety.check_package(POLICY, ctx, "com.tcl.usercenter") is None
    assert "standby" in safety.high_risk_reason(POLICY, ctx, "com.tcl.usercenter")
    assert safety.high_risk_reason(POLICY, _ctx("sony"), "com.tcl.usercenter") is None


def test_high_risk_and_never_disable_do_not_overlap():
    for hr in POLICY.high_risk:
        assert safety.check_package(POLICY, _ctx(hr.scope.get("brand", "x")), hr.package) is None


@pytest.mark.parametrize(
    "bad",
    [
        {"schema": 2, "override": "never", "groups": []},
        {"schema": 1, "override": "flag", "groups": []},
        {
            "schema": 1,
            "override": "never",
            "groups": [
                {"id": "a", "scope": "all", "packages": ["x.y"]},
                {"id": "a", "scope": "all", "packages": ["x.z"]},
            ],
        },
        {
            "schema": 1,
            "override": "never",
            "groups": [{"id": "a", "scope": {"model": "x"}, "packages": ["x.y"]}],
        },
        {
            "schema": 1,
            "override": "never",
            "groups": [{"id": "a", "scope": "all", "rules": [{"check": "magic"}]}],
        },
        {"schema": 1, "override": "never", "groups": [{"id": "a", "scope": "all"}]},
    ],
)
def test_malformed_policy_is_rejected(tmp_path, bad):
    p = tmp_path / "p.yaml"
    p.write_text(yaml.safe_dump(bad))
    with pytest.raises(ZenError):
        safety.load(p)
