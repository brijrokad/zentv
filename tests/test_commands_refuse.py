"""commands.py builds every TV command; refuse.py is the ground-rule-5 backstop."""

import inspect

import pytest

from zenctl import commands as C
from zenctl import refuse
from zenctl.errors import InvalidArgument, Refused

# Ground rule 5, as written in ZENTV_BUILD_PROMPT.md, one line per form.
RULE5 = [
    "pm uninstall com.example.app",
    "pm uninstall --user 0 com.example.app",
    "pm uninstall -k --user 0 com.example.app",
    "cmd package uninstall com.example.app",
    "pm clear com.example.app",
    "pm hide com.example.app",
    "pm suspend com.example.app",
    "cmd package suspend com.example.app",
    "dpm set-device-owner com.example.app/.Admin",
    "dpm remove-active-admin com.example.app/.Admin",
    "setprop persist.sys.usb.config adb",
    "settings put global verifier_verify_adb_installs 0",
    "settings put global package_verifier_enable 0",
    "settings put global adb_enabled 1",
    "settings put global adb_wifi_enabled 1",
    "settings put global adb_enabled true",
    "pm grant io.zentv.launcher android.permission.WRITE_SECURE_SETTINGS",
    "pm grant com.example.app android.permission.READ_TV_LISTINGS",
    "pm install -g /data/local/tmp/app.apk",
    "pm install --bypass-low-target-sdk-block /data/local/tmp/app.apk",
    "while true",
    "nohup pm disable-user com.example.app",
    "am start -n com.tcl.factory.view/.MainActivity",
    "am start -n mediatek.factorymenu.ui/.Main",
]

ALLOWED = [
    "pm unhide --user 0 com.google.android.katniss",
    "settings put global adb_enabled 0",
    "settings put global adb_wifi_enabled 0",
    "getprop ro.product.model",
    "dumpsys package com.tcl.watch",
    "dumpsys package com.example.uninstaller",
    "pm list packages -d --user 0",
]


@pytest.mark.parametrize("cmd", RULE5)
def test_every_rule5_form_is_refused(cmd):
    with pytest.raises(Refused):
        refuse.check(cmd, tuple(cmd.split()))


@pytest.mark.parametrize("cmd", ALLOWED)
def test_harmless_commands_pass(cmd):
    refuse.check(cmd, tuple(cmd.split()))


@pytest.mark.parametrize("tok", ["a;b", "$(id)", "`id`", "a|b", "a&b", "a b", "x>y", "it's", "line\nbreak"])
def test_shell_metacharacters_never_pass(tok):
    with pytest.raises(Refused):
        refuse.check_tokens((tok,))


def test_commands_cannot_be_built_directly():
    with pytest.raises(TypeError):
        C.Command(("getprop",), C.Kind.READ, "x")


def test_state_change_must_declare_records():
    with pytest.raises(TypeError):
        C._cmd(["settings", "put", "global", "x", "0"], C.Kind.CHANGE, "no records")


@pytest.mark.parametrize("bad", ["com", "com.x;rm", "com.x y", "1com.x", "com..x", "-com.x", "com.x/.A", ""])
def test_package_names_are_validated(bad):
    with pytest.raises(InvalidArgument):
        C.check_package(bad)


def test_allowlists():
    with pytest.raises(InvalidArgument):
        C.pm_list_packages("-f")
    with pytest.raises(InvalidArgument):
        C.dumpsys("battery")
    with pytest.raises(InvalidArgument):
        C.dumpsys("package", "com.x;id")
    with pytest.raises(InvalidArgument):
        C.settings_get("bogus", "x")
    with pytest.raises(InvalidArgument):
        C.read_file("/data/system/packages.xml")
    with pytest.raises(InvalidArgument):
        C.adb_network_off("install_non_market_apps")
    with pytest.raises(InvalidArgument):
        C.appops_get("com.x.y", "lower_case")


SAMPLE_ARGS = {
    "getprop": [("ro.product.model",), ()],
    "pm_list_packages": [("-d",), ("-i", "-U")],
    "dumpsys": [("package", "com.example.app"), ("tv_input",)],
    "resolve_home": [()],
    "query_home": [()],
    "settings_get": [("secure", "accessibility_enabled")],
    "appops_get": [("com.example.app", "APP_AUTO_START"), ("com.example.app",)],
    "appops_query_op": [("GET_USAGE_STATS",)],
    "read_file": [("/proc/meminfo",)],
    "adb_network_off": [("adb_wifi_enabled",), ("adb_enabled",)],
    "disable_user": [("com.example.promo",)],
    "enable": [("com.example.promo",), ("com.example.promo", True)],
    "unhide": [("com.google.android.katniss", frozenset({"com.google.android.katniss"}))],
}
SPIKE = "io.github.brijrokad.zentv.spike"
SPIKE_SVC = f"{SPIKE}/{SPIKE}.HomeKeyService"
SAMPLE_ARGS.update(
    {
        "install_apk": [("/tmp/zentv/app-spike.apk", SPIKE)],
        "put_accessibility": [
            ("accessibility_enabled", "1"),
            ("enabled_accessibility_services", SPIKE_SVC),
            ("accessibility_enabled", "0", True),
        ],
        "delete_accessibility": [
            ("enabled_accessibility_services",),
            ("enabled_accessibility_services", True),
        ],
        "tcl_appop": [
            (SPIKE, "APP_AUTO_START", "allow", "TCL"),
            (SPIKE, "APP_AUTO_START", "default", "tcl", True),
        ],
        "appops_write_settings": [(SPIKE, "APP_AUTO_START"), (SPIKE, "APP_AUTO_START", True)],
    }
)
NOT_CONSTRUCTORS = {"check_package", "package_state", "parse_state", "appop_mode"}


def _constructors():
    return {
        n: f
        for n, f in inspect.getmembers(C, inspect.isfunction)
        if f.__module__ == C.__name__ and not n.startswith("_") and n not in NOT_CONSTRUCTORS
    }


def test_every_constructor_is_covered_here():
    """A new constructor must be added to SAMPLE_ARGS, so the meta-tests below see it."""
    assert set(_constructors()) == set(SAMPLE_ARGS)


@pytest.mark.parametrize("name", sorted(SAMPLE_ARGS))
def test_constructor_outputs_pass_refuse_and_changes_have_readers(name):
    for args in SAMPLE_ARGS[name]:
        cmd = _constructors()[name](*args)
        refuse.check(cmd.shell_string(), cmd.argv)
        if cmd.is_change:
            assert cmd.records, f"{name} changes state without recording"
            for r in cmd.records:
                assert r.reader().kind is C.Kind.READ


def test_only_adb_close_and_restore_paths_are_gate_exempt():
    for name, arglist in SAMPLE_ARGS.items():
        for args in arglist:
            cmd = _constructors()[name](*args)
            expected = name == "adb_network_off" or (len(args) > 0 and args[-1] is True)
            assert cmd.gate_exempt == expected, (name, args)


def test_launcher_constructors_refuse_anything_not_zentvs_own():
    with pytest.raises(InvalidArgument):
        C.install_apk("/tmp/x/other.apk", "com.example.other")
    with pytest.raises(InvalidArgument):
        C.install_apk("relative/app.apk", SPIKE)
    with pytest.raises(InvalidArgument):
        C.tcl_appop(SPIKE, "APP_AUTO_START", "allow", "Sony")
    with pytest.raises(InvalidArgument):
        C.tcl_appop("com.example.other", "APP_AUTO_START", "allow", "TCL")
    with pytest.raises(InvalidArgument):
        C.tcl_appop(SPIKE, "SYSTEM_ALERT_WINDOW", "allow", "TCL")
    with pytest.raises(InvalidArgument):
        C.put_accessibility("enabled_notification_listeners", SPIKE_SVC)
    with pytest.raises(InvalidArgument):
        C.put_accessibility("enabled_accessibility_services", "evil;id")
    with pytest.raises(InvalidArgument):
        C.delete_accessibility("adb_enabled")
    assert C.install_apk("/tmp/zentv/app-spike.apk", SPIKE).host is True


def test_appop_mode_parsing():
    assert C.appop_mode("No operations.\nDefault mode: ignore\n") == "default"
    assert C.appop_mode("APP_AUTO_START: allow; time=+3m ago\n") == "allow"


def test_unhide_only_for_approved_packages():
    with pytest.raises(InvalidArgument):
        C.unhide("com.tcl.usercenter", frozenset({"com.google.android.katniss"}))


def test_package_state_parsing():
    out = "  User 0: ceDataInode=1 installed=true hidden=true suspended=false enabled=0 instant=false"
    assert C.package_state(out) == "enabled=0 hidden=true installed=true"
    assert C.parse_state(C.package_state(out)) == {"enabled": "0", "hidden": "true", "installed": "true"}
    assert C.package_state("Unable to find package: x.y") is None
