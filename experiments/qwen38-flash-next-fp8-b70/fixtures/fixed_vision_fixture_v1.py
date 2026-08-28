#!/usr/bin/env python3
"""Generate the byte-exact synthetic Flash-Next vision fixture v1."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path


FIXTURE_ID = "qwen38-flash-next-fixed-vision-v1"
WIDTH = 256
HEIGHT = 256
MIME_TYPE = "image/png"
EXPECTED_PNG_SHA256 = "ffbac32956e25357b1a3985a8562da7f725dc1eb6c8f7845e73028f76553e207"

_FONT_5X7 = {
    "B": (
        "11110",
        "10001",
        "10001",
        "11110",
        "10001",
        "10001",
        "11110",
    ),
    "7": (
        "11111",
        "00001",
        "00010",
        "00100",
        "01000",
        "01000",
        "01000",
    ),
    "X": (
        "10001",
        "10001",
        "01010",
        "00100",
        "01010",
        "10001",
        "10001",
    ),
    "9": (
        "01110",
        "10001",
        "10001",
        "01111",
        "00001",
        "00010",
        "11100",
    ),
}


def _set_pixel(pixels: bytearray, x: int, y: int, rgb: tuple[int, int, int]) -> None:
    if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
        return
    offset = (y * WIDTH + x) * 3
    pixels[offset : offset + 3] = bytes(rgb)


def _fill_rect(
    pixels: bytearray,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    rgb: tuple[int, int, int],
) -> None:
    for y in range(y0, y1):
        for x in range(x0, x1):
            _set_pixel(pixels, x, y, rgb)


def _fill_circle(
    pixels: bytearray,
    center_x: int,
    center_y: int,
    radius: int,
    rgb: tuple[int, int, int],
) -> None:
    radius_squared = radius * radius
    for y in range(center_y - radius, center_y + radius + 1):
        for x in range(center_x - radius, center_x + radius + 1):
            if (x - center_x) ** 2 + (y - center_y) ** 2 <= radius_squared:
                _set_pixel(pixels, x, y, rgb)


def _draw_text(
    pixels: bytearray,
    text: str,
    x0: int,
    y0: int,
    scale: int,
    rgb: tuple[int, int, int],
) -> None:
    cursor_x = x0
    for character in text:
        glyph = _FONT_5X7[character]
        for row_index, row in enumerate(glyph):
            for column_index, value in enumerate(row):
                if value == "1":
                    _fill_rect(
                        pixels,
                        cursor_x + column_index * scale,
                        y0 + row_index * scale,
                        cursor_x + (column_index + 1) * scale,
                        y0 + (row_index + 1) * scale,
                        rgb,
                    )
        cursor_x += 6 * scale


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    body = chunk_type + payload
    return (
        struct.pack(">I", len(payload))
        + body
        + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    )


def build_rgb_pixels() -> bytes:
    """Return the canonical 256x256 RGB pixel buffer."""
    pixels = bytearray(bytes((255, 255, 255)) * WIDTH * HEIGHT)

    # OCR/code region: a unique high-contrast code that cannot be inferred
    # from the question alone.
    _fill_rect(pixels, 6, 6, 250, 88, (255, 244, 180))
    _draw_text(pixels, "B7X9", 13, 12, 10, (0, 0, 0))

    # Spatial/color region: two same-sized squares with distinct positions.
    _fill_rect(pixels, 32, 98, 110, 176, (0, 0, 0))
    _fill_rect(pixels, 38, 104, 104, 170, (220, 36, 36))
    _fill_rect(pixels, 146, 98, 224, 176, (0, 0, 0))
    _fill_rect(pixels, 152, 104, 218, 170, (36, 88, 220))

    # Count region: exactly three isolated black circles along the bottom.
    for center_x in (56, 128, 200):
        _fill_circle(pixels, center_x, 218, 14, (0, 0, 0))

    return bytes(pixels)


def build_png() -> bytes:
    """Return the canonical PNG bytes without timestamps or metadata."""
    pixels = build_rgb_pixels()
    scanlines = b"".join(
        b"\x00" + pixels[y * WIDTH * 3 : (y + 1) * WIDTH * 3]
        for y in range(HEIGHT)
    )
    ihdr = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(scanlines, level=9))
        + _png_chunk(b"IEND", b"")
    )


def fixture_receipt() -> dict[str, object]:
    png = build_png()
    sha256 = hashlib.sha256(png).hexdigest()
    if EXPECTED_PNG_SHA256 != "TO_BE_FILLED" and sha256 != EXPECTED_PNG_SHA256:
        raise RuntimeError(
            f"fixture SHA-256 changed: expected {EXPECTED_PNG_SHA256}, got {sha256}"
        )
    if png[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("fixture does not have the PNG signature")
    width, height = struct.unpack(">II", png[16:24])
    if (width, height) != (WIDTH, HEIGHT):
        raise RuntimeError(f"fixture dimensions changed: {(width, height)}")
    return {
        "fixture_id": FIXTURE_ID,
        "mime_type": MIME_TYPE,
        "width": width,
        "height": height,
        "color_mode": "RGB",
        "byte_count": len(png),
        "sha256": sha256,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        type=Path,
        default=None,
        help="Optionally materialize the verified canonical PNG at this path.",
    )
    args = parser.parse_args()
    receipt = fixture_receipt()
    if args.write is not None:
        if args.write.exists():
            raise SystemExit(f"refusing to overwrite {args.write}")
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_bytes(build_png())
        receipt["materialized_path"] = str(args.write)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
