from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path


OUTPUT_DIR = Path(__file__).resolve().parents[1] / "server_manager" / "web" / "assets"
TEAL = (8, 125, 120)
WHITE = (255, 255, 255)
SUPERSAMPLE = 3


def _fill_row(pixels: bytearray, width: int, y: int, left: float, right: float, color: tuple[int, int, int]) -> None:
    start = max(0, int(math.ceil(left)))
    end = min(width, int(math.ceil(right)))
    if end <= start:
        return
    pixel = bytes(color)
    pixels[(y * width + start) * 3 : (y * width + end) * 3] = pixel * (end - start)


def _rounded_rect(
    pixels: bytearray,
    width: int,
    bounds: tuple[float, float, float, float],
    radius: float,
    color: tuple[int, int, int],
) -> None:
    left, top, right, bottom = bounds
    radius = min(radius, (right - left) / 2, (bottom - top) / 2)
    first_y = max(0, int(math.floor(top)))
    last_y = min(width, int(math.ceil(bottom)))
    for y in range(first_y, last_y):
        center_y = min(max(y + 0.5, top + radius), bottom - radius)
        distance_y = abs(y + 0.5 - center_y)
        offset_x = radius - math.sqrt(max(radius * radius - distance_y * distance_y, 0))
        _fill_row(pixels, width, y, left + offset_x, right - offset_x, color)


def _circle(
    pixels: bytearray,
    width: int,
    center_x: float,
    center_y: float,
    radius: float,
    color: tuple[int, int, int],
) -> None:
    first_y = max(0, int(math.floor(center_y - radius)))
    last_y = min(width, int(math.ceil(center_y + radius)))
    for y in range(first_y, last_y):
        dy = y + 0.5 - center_y
        dx = math.sqrt(max(radius * radius - dy * dy, 0))
        _fill_row(pixels, width, y, center_x - dx, center_x + dx, color)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def _draw_png(size: int) -> bytes:
    width = size * SUPERSAMPLE
    scale = width / 192
    pixels = bytearray(bytes(TEAL) * (width * width))

    for row_y in (46, 97):
        _rounded_rect(
            pixels,
            width,
            (36 * scale, row_y * scale, 156 * scale, (row_y + 51) * scale),
            12 * scale,
            WHITE,
        )
    for center_y in (71.5, 122.5):
        _circle(pixels, width, 55 * scale, center_y * scale, 6 * scale, TEAL)
        _rounded_rect(
            pixels,
            width,
            (72.5 * scale, (center_y - 3.5) * scale, 133.5 * scale, (center_y + 3.5) * scale),
            3.5 * scale,
            TEAL,
        )

    output_size = size
    output = bytearray()
    for y in range(output_size):
        output.append(0)
        for x in range(output_size):
            sums = [0, 0, 0]
            for sub_y in range(SUPERSAMPLE):
                for sub_x in range(SUPERSAMPLE):
                    offset = (((y * SUPERSAMPLE + sub_y) * width) + x * SUPERSAMPLE + sub_x) * 3
                    sums[0] += pixels[offset]
                    sums[1] += pixels[offset + 1]
                    sums[2] += pixels[offset + 2]
            output.extend(channel // (SUPERSAMPLE * SUPERSAMPLE) for channel in sums)

    header = struct.pack(">IIBBBBB", output_size, output_size, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(bytes(output), level=9))
        + _png_chunk(b"IEND", b"")
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for size in (180, 192, 512):
        (OUTPUT_DIR / f"icon-{size}.png").write_bytes(_draw_png(size))


if __name__ == "__main__":
    main()
