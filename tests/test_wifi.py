"""One-time exception: forget owner-approved stale Wi-Fi entries, never the one in use."""

import pytest

from zenctl import commands as C
from zenctl import wifi
from zenctl.adb import Session
from zenctl.errors import InvalidArgument, NotAllowed, Refused

APPROVED = frozenset({0, 1, 2})


def _tv(tcl):
    tcl.wifi_entries = [
        {
            "id": 0,
            "hidden": "true",
            "status": "NETWORK_SELECTION_ENABLED",
            "creator": "com.google.android.tungsten.setupwraith",
            "recent": "false",
        },
        {
            "id": 1,
            "hidden": "true",
            "status": "NETWORK_SELECTION_ENABLED",
            "creator": "android.uid.system:1000",
            "recent": "false",
        },
        {
            "id": 2,
            "hidden": "false",
            "status": "NETWORK_SELECTION_PERMANENTLY_DISABLED",
            "creator": "android.uid.system:1000",
            "recent": "false",
        },
        {
            "id": 4,
            "hidden": "false",
            "status": "NETWORK_SELECTION_ENABLED",
            "creator": "com.android.tv.settings",
            "recent": "true",
        },
    ]
    tcl.wifi_connected = 4
    return tcl


def test_entries_parse_without_names(tcl):
    found, connected = wifi.entries(Session(_tv(tcl)))
    assert connected == 4 and sorted(found) == [0, 1, 2, 4]
    assert found[0]["creator"].endswith("setupwraith") and found[0]["hidden"] == "true"
    assert "HomeNet" not in str(found)


def test_forget_removes_only_the_approved_stale_entries(tcl):
    tv = _tv(tcl)
    s = Session(tv, yes=True, state_changes_allowed=True)
    wifi.forget(s, [0, 1, 2], APPROVED)
    assert [e["id"] for e in tv.wifi_entries] == [4]
    assert s.recorded["entry/0"].startswith("hidden=true")
    assert "HomeNet" not in str(s.recorded)


def test_never_the_network_in_use(tcl):
    s = Session(_tv(tcl), yes=True, state_changes_allowed=True)
    with pytest.raises(Refused):
        wifi.forget(s, [4], frozenset({4}))


def test_only_approved_ids_and_only_on_a_confirmed_profile(tcl):
    with pytest.raises(InvalidArgument):
        C.wifi_forget_network(3, APPROVED)
    s = Session(_tv(tcl), yes=True, state_changes_allowed=False)
    with pytest.raises(NotAllowed):
        wifi.forget(s, [0], APPROVED)


def test_dry_run_sends_nothing(tcl):
    tv = _tv(tcl)
    s = Session(tv, yes=False, state_changes_allowed=True)
    wifi.forget(s, [0, 1, 2], APPROVED)
    assert len(tv.wifi_entries) == 4 and len(s.planned) == 3
