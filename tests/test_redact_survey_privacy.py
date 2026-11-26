"""Redaction, the read-only survey, and the privacy report."""

import json

from zenctl import device, privacy, redact, survey
from zenctl.adb import Session

SYNTH_TCL_SERIAL = "1234ABC567890D12345"  # synthetic, TCL format


def test_redaction_masks_identifiers_with_stable_tokens():
    r = redact.Redactor()
    text = (
        f"serial {SYNTH_TCL_SERIAL} mac aa:bb:cc:dd:ee:ff ip 192.168.1.50 v6 fe80::1c2b:3a4d "
        'owner someone@example.com SSID: "HomeNet-5G" again aa:bb:cc:dd:ee:ff loop 127.0.0.1'
    )
    out = r.text(text)
    for secret in (
        SYNTH_TCL_SERIAL,
        "aa:bb:cc:dd:ee:ff",
        "192.168.1.50",
        "fe80::1c2b:3a4d",
        "someone@example.com",
        "HomeNet-5G",
    ):
        assert secret not in out
    assert out.count("<MAC-1>") == 2
    assert "127.0.0.1" in out


def test_redaction_leaves_package_names_and_versions_alone():
    r = redact.Redactor()
    s = "com.tcl.versionUpdateApp 11.0.2 RP1A.200622.001 uid:10202 12:30:45"
    assert r.text(s) == s


def test_from_props_masks_the_serial_anywhere():
    r = redact.from_props({"ro.serialno": "SYNTHSONY0001", "ro.product.model": "KD-65X80K"})
    assert r.text("device SYNTHSONY0001 attached") == "device <SERIAL-1> attached"


def test_survey_is_redacted_and_read_only(tcl):
    s = Session(tcl)
    ident = device.identify(s)
    data = survey.collect(s, ident, None)
    dumped = json.dumps(data)
    assert SYNTH_TCL_SERIAL not in dumped
    assert "HomeNet-5G" not in dumped and "192.168.1.50" not in dumped
    assert all(
        not line.startswith(("settings put", "pm disable", "pm enable", "appops set")) for line in tcl.log
    )
    pk = data["packages"]
    assert pk["com.tcl.esticker"]["enabled"] is False
    assert pk["com.tcl.bi"]["enabled"] is True and pk["com.tcl.bi"]["system"] is True
    assert pk["com.example.sideloaded"]["installer"] is None
    assert data["tcl_appop_names"] == {"APP_AUTO_START": True, "AUTO_START": False}
    assert data["identity"]["ro.build.version.sdk"] == "30"
    assert data["memory_kb"]["MemTotal"] == 1900000
    assert "com.tcl.tvinput/.TunerService/HW0" in data["tv_inputs"]
    assert data["network"]["transports_seen"] == ["WIFI"]
    assert "creatorName=android.uid.system:1000" in data["network"]["wifi_network_owners"]


def test_survey_on_sony_has_no_tcl_section(sony):
    s = Session(sony)
    data = survey.collect(s, device.identify(s), None)
    assert "tcl_appop_names" not in data
    assert "SYNTHSONY0001" not in json.dumps(data)


def test_privacy_report(tcl):
    s = Session(tcl)
    rep = privacy.report(s, survey._packages(s))
    assert rep["usage_access"] == ["com.tcl.bi"]
    assert rep["sideloaded"] == ["com.example.sideloaded"]
    assert rep["private_dns"]["mode"] == "off"
    assert all(not line.startswith(("settings put", "appops set")) for line in tcl.log)
