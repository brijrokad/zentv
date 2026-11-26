"""The fake `adb` executable's logic (see conftest.fake_adb). Serves one FakeDevice from a JSON file."""

import os
import sys
from pathlib import Path

from fakedevice import FakeDevice


def main(argv: list[str]) -> int:
    state = Path(os.environ["FAKE_ADB_STATE"])
    serial = os.environ.get("FAKE_ADB_SERIAL", "192.0.2.10:5555")
    if argv[:1] == ["devices"]:
        print("List of devices attached")
        print(f"{serial}\tdevice")
        return 0
    if argv[:1] in (["connect"], ["disconnect"]):
        print(f"{argv[0]}ed to {argv[1]}" if argv[0] == "connect" else f"disconnected {argv[1]}")
        return 0
    if argv[:2] == ["mdns", "services"]:
        print("List of discovered mdns services")
        return 0
    if len(argv) == 4 and argv[0] == "-s" and argv[2] == "shell":
        if argv[1] != serial:
            print(f"adb: device '{argv[1]}' not found", file=sys.stderr)
            return 1
        dev = FakeDevice.from_json(state.read_text())
        res = dev.shell(argv[3])
        state.write_text(dev.to_json())
        sys.stdout.write(res.stdout)
        sys.stderr.write(res.stderr)
        return res.returncode
    print(f"fake adb: unsupported {argv}", file=sys.stderr)
    return 1
