"""Wallpaper metadata stripping, and the rules every committed wallpaper must meet."""

import struct
import zlib
from pathlib import Path

import pytest

from zenctl import imagemeta as M

WALLPAPERS = Path(__file__).resolve().parent.parent / "launcher" / "wallpapers"


def _png(extra_chunks=()):
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))

    ihdr = struct.pack(">IIBBBBB", 16, 9, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00" + b"\x00" * 48)
    body = chunk(b"IHDR", ihdr)
    for t, d in extra_chunks:
        body += chunk(t, d)
    return M.PNG_SIG + body + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def _jpeg(with_exif=True):
    seg = lambda m, payload: b"\xff" + bytes([m]) + struct.pack(">H", len(payload) + 2) + payload  # noqa: E731
    sof = seg(0xC0, b"\x08" + struct.pack(">HH", 2160, 3840) + b"\x01\x01\x11\x00")
    exif = seg(0xE1, b"Exif\x00\x00GPS 51.5N 0.1W serial 1234") if with_exif else b""
    jfif = seg(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
    return b"\xff\xd8" + jfif + exif + sof + b"\xff\xda\x00\x02SCANDATA\xff\xd9"


def _webp(with_exif=True):
    def chunk(t, d):
        return t + struct.pack("<I", len(d)) + d + (b"\x00" if len(d) & 1 else b"")

    flags = 0x08 if with_exif else 0
    vp8x = bytes([flags, 0, 0, 0]) + (3839).to_bytes(3, "little") + (2159).to_bytes(3, "little")
    body = chunk(b"VP8X", vp8x) + chunk(b"VP8L", b"\x2f" + b"\x00" * 9)
    if with_exif:
        body += chunk(b"EXIF", b"GPS 51.5N")
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WEBP" + body


def test_jpeg_exif_found_and_stripped_without_touching_image_data():
    data = _jpeg()
    assert M.find(data) == ["EXIF/XMP (APP1)"]
    clean = M.strip(data)
    assert M.find(clean) == [] and b"GPS" not in clean
    assert clean.endswith(b"SCANDATA\xff\xd9") and M.size(clean) == (3840, 2160)


def test_png_text_chunks_stripped():
    data = _png([(b"tEXt", b"Author\x00someone"), (b"eXIf", b"MM\x00*GPS")])
    assert set(M.find(data)) == {"tEXt", "eXIf"}
    clean = M.strip(data)
    assert M.find(clean) == [] and M.size(clean) == (16, 9) and b"someone" not in clean


def test_webp_exif_stripped_and_flag_cleared():
    data = _webp()
    assert M.find(data) == ["EXIF"]
    clean = M.strip(data)
    assert M.find(clean) == [] and b"GPS" not in clean
    assert clean[20] & 0x08 == 0  # VP8X flags byte
    assert struct.unpack("<I", clean[4:8])[0] == len(clean) - 8
    assert M.size(clean) == (3840, 2160)


def test_clean_files_are_unchanged():
    for data in (_jpeg(with_exif=False), _webp(with_exif=False), _png()):
        assert M.find(data) == []
        assert M.strip(data) == data


def test_not_an_image():
    with pytest.raises(M.ImageError):
        M.kind(b"hello")


def _wallpapers():
    return sorted(p for p in WALLPAPERS.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))


@pytest.mark.parametrize("path", _wallpapers(), ids=lambda p: p.name)
def test_committed_wallpaper_rules(path):
    """Every wallpaper in the repo: no metadata, 16:9, at most 4K, at most 4 MB."""
    data = path.read_bytes()
    assert M.find(data) == [], (
        f"{path.name} carries metadata; run: uv run python -m zenctl.imagemeta strip {path}"
    )
    w, h = M.size(data)
    assert w <= 3840 and h <= 2160, f"{path.name} is {w}x{h}; at most 3840x2160"
    assert abs(w / h - 16 / 9) < 0.01, f"{path.name} is {w}x{h}; zentv needs 16:9 (e.g. 3840x2160)"
    assert len(data) <= 4 * 1024 * 1024, f"{path.name} is over 4 MB"
    assert " " not in path.name


def test_schedule_only_names_existing_wallpapers():
    text = (WALLPAPERS / "schedule.txt").read_text()
    names = {p.name for p in _wallpapers()}
    for line in text.splitlines():
        line = line.split("#", 1)[0]
        for word in line.replace(",", " ").split():
            if word.startswith("wall:"):
                assert word[5:] in names, f"schedule.txt names {word} but there is no such file"
        parts = line.split()
        if parts[:1] == ["clock"]:
            assert parts[1] in names, f"schedule.txt places the clock on {parts[1]}, which doesn't exist"
