"""Find and remove hidden metadata (EXIF/GPS, XMP, IPTC, text chunks) from JPEG, PNG and WebP files.

Wallpapers in launcher/wallpapers/ are committed to a public repo (AGENTS.md rule 8: no identifiers).
Photos often carry GPS coordinates, camera serials and dates. This module works on the container only:
whole metadata segments/chunks are dropped and the image data is copied byte-for-byte, so nothing is
re-compressed. Colour profiles (JPEG APP2 ICC, PNG iCCP) are kept: they change how the picture looks
and say nothing about the owner.

    uv run python -m zenctl.imagemeta check launcher/wallpapers/*
    uv run python -m zenctl.imagemeta strip launcher/wallpapers/*
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

PNG_SIG = b"\x89PNG\r\n\x1a\n"
PNG_DROP = {b"eXIf", b"tEXt", b"iTXt", b"zTXt", b"tIME"}
JPEG_DROP = {0xE1: "EXIF/XMP (APP1)", 0xED: "IPTC (APP13)", 0xFE: "comment"}
WEBP_DROP = {b"EXIF", b"XMP "}


class ImageError(ValueError):
    pass


def kind(data: bytes) -> str:
    if data[:2] == b"\xff\xd8":
        return "jpeg"
    if data[:8] == PNG_SIG:
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    raise ImageError("not a JPEG, PNG or WebP file")


def _jpeg_segments(data: bytes):
    """Yields (marker, start, end) for each segment before the image data (SOS)."""
    i = 2
    while i < len(data):
        if data[i] != 0xFF:
            raise ImageError(f"broken JPEG at byte {i}")
        while i < len(data) and data[i] == 0xFF:
            i += 1
        marker = data[i]
        i += 1
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            continue
        if marker in (0xD9, 0xDA):
            yield marker, i - 2, None
            return
        (length,) = struct.unpack(">H", data[i : i + 2])
        yield marker, i - 2, i + length
        i += length


def _png_chunks(data: bytes):
    i = 8
    while i < len(data):
        (length,) = struct.unpack(">I", data[i : i + 4])
        ctype = data[i + 4 : i + 8]
        end = i + 12 + length
        yield ctype, i, end, data[i + 8 : i + 8 + length]
        i = end
        if ctype == b"IEND":
            return


def _webp_chunks(data: bytes):
    i = 12
    while i + 8 <= len(data):
        ctype = data[i : i + 4]
        (length,) = struct.unpack("<I", data[i + 4 : i + 8])
        end = i + 8 + length + (length & 1)
        yield ctype, i, end, data[i + 8 : i + 8 + length]
        i = end


def find(data: bytes) -> list[str]:
    """What metadata the file carries (empty list = clean)."""
    k = kind(data)
    found: list[str] = []
    if k == "jpeg":
        for marker, start, end in _jpeg_segments(data):
            if end is None:
                break
            if marker in JPEG_DROP:
                found.append(JPEG_DROP[marker])
            elif marker == 0xE0 and data[start + 4 : start + 9] == b"JFXX\x00":
                found.append("thumbnail (JFXX)")
    elif k == "png":
        found = [c.decode() for c, *_ in _png_chunks(data) if c in PNG_DROP]
    else:
        found = [c.decode().strip() for c, *_ in _webp_chunks(data) if c in WEBP_DROP]
    return found


def strip(data: bytes) -> bytes:
    """The same image with every metadata segment/chunk removed (pixels untouched)."""
    k = kind(data)
    if k == "jpeg":
        out = bytearray(data[:2])
        for marker, start, end in _jpeg_segments(data):
            if end is None:
                out += data[start:]
                return bytes(out)
            drop = marker in JPEG_DROP or (marker == 0xE0 and data[start + 4 : start + 9] == b"JFXX\x00")
            if not drop:
                out += data[start:end]
        raise ImageError("JPEG without image data")
    if k == "png":
        out = bytearray(PNG_SIG)
        for ctype, start, end, _ in _png_chunks(data):
            if ctype not in PNG_DROP:
                out += data[start:end]
        return bytes(out)
    body = bytearray()
    for ctype, start, end, payload in _webp_chunks(data):
        if ctype in WEBP_DROP:
            continue
        if ctype == b"VP8X":
            flags = payload[0] & ~0x0C  # clear the EXIF (0x08) and XMP (0x04) flags
            body += data[start : start + 8] + bytes([flags]) + data[start + 9 : end]
        else:
            body += data[start:end]
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WEBP" + bytes(body)


def size(data: bytes) -> tuple[int, int]:
    """(width, height) in pixels."""
    k = kind(data)
    if k == "png":
        return struct.unpack(">II", data[16:24])
    if k == "jpeg":
        for marker, start, end in _jpeg_segments(data):
            if end is None:
                break
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", data[start + 5 : start + 9])
                return w, h
        raise ImageError("JPEG without a frame header")
    for ctype, _start, _end, p in _webp_chunks(data):
        if ctype == b"VP8X":
            return 1 + int.from_bytes(p[4:7], "little"), 1 + int.from_bytes(p[7:10], "little")
        if ctype == b"VP8 ":
            w, h = struct.unpack("<HH", p[6:10])
            return w & 0x3FFF, h & 0x3FFF
        if ctype == b"VP8L":
            b = int.from_bytes(p[1:5], "little")
            return 1 + (b & 0x3FFF), 1 + ((b >> 14) & 0x3FFF)
    raise ImageError("WebP without an image chunk")


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] not in ("check", "strip"):
        print(__doc__.strip().splitlines()[-2:][0].strip())
        print("usage: python -m zenctl.imagemeta check|strip FILE...")
        return 2
    bad = 0
    for name in argv[1:]:
        p = Path(name)
        if p.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        data = p.read_bytes()
        meta = find(data)
        if argv[0] == "strip" and meta:
            p.write_bytes(strip(data))
            print(f"{p}: removed {', '.join(meta)}")
        elif meta:
            bad += 1
            print(f"{p}: has {', '.join(meta)}")
        else:
            print(f"{p}: clean")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
