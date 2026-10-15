"""
generate_image.py — creates a sample image (PNG) using pure Python.

No external libraries required: it builds the PNG bytes manually.
The image is a smooth diagonal gradient with a soft glowing circle
overlay and a simple checker pattern, saved as sample_image.png.
"""

import struct
import zlib

WIDTH = 512
HEIGHT = 512
OUTPUT = "sample_image.png"


def clamp(value, low=0, high=255):
    return max(low, min(high, int(value)))


def build_rows():
    """Build WIDTH x HEIGHT RGB rows as bytes (PNG-ready)."""
    rows = []
    cx, cy, radius = WIDTH * 0.5, HEIGHT * 0.5, WIDTH * 0.35

    for y in range(HEIGHT):
        row = bytearray()
        for x in range(WIDTH):
            # Diagonal gradient: purple -> teal
            t = (x + y) / (WIDTH + HEIGHT)
            r = 40 + 180 * t
            g = 30 + 280 * (1 - t) * t
            b = 90 + 160 * (1 - t)

            # Soft glowing circle in the center
            dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if dist < radius:
                glow = 1 - (dist / radius) ** 2
                r += 120 * glow
                g += 100 * glow
                b += 40 * glow

            # Subtle checker pattern near the corners
            checker = ((x // 32) + (y // 32)) % 2
            if (x < 96 or x > WIDTH - 96) and (y < 96 or y > HEIGHT - 96):
                if checker:
                    r += 25
                    g += 25
                    b += 25

            row += bytes((clamp(r), clamp(g), clamp(b)))
        rows.append(bytes(row))
    return rows


def png_chunk(tag, data):
    """Create one PNG chunk with correct length + CRC."""
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def write_png(rows, path):
    """Assemble a minimal valid PNG file from RGB rows."""
    header = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0)  # 8-bit RGB
    raw = b"".join(b"\x00" + r for r in rows)  # filter byte 0 per row

    png = b"\x89PNG\r\n\x1a\n"
    png += png_chunk(b"IHDR", header)
    png += png_chunk(b"IDAT", zlib.compress(raw, 9))
    png += png_chunk(b"IEND", b"")

    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    rows = build_rows()
    size = write_png(rows, OUTPUT)
    print(f"Created {OUTPUT} ({WIDTH}x{HEIGHT}, {size:,} bytes)")


if __name__ == "__main__":
    main()
