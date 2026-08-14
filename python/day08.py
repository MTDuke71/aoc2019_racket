"""AoC 2019 Day 8 — Space Image Format.

Companion to src/day08.rkt. A flat digit string is a stack of W×H image
**layers** (row-major, back-to-front). The day is one reshape from 1-D to
the (layer, row, col) array plus two queries:

  * Part 1 — a corruption checksum: the layer with the fewest ``0`` digits,
    scored as (#1s) × (#2s). Per-layer histogram, no geometry.
  * Part 2 — decode: stack layers front-to-back, each pixel is the first
    non-transparent (``2``) value down the layer axis (0 = black, 1 =
    white). The lit pixels spell letters.

The load-bearing fact is the index arithmetic: pixel (layer L, row r,
col c) sits at flat offset ``L*(W*H) + r*W + c``. Part 1 needs only the
layer chunking; Part 2 scans the L axis at each fixed (r, c).
"""

from __future__ import annotations


def parse_input(text: str) -> list[int]:
    """Flat digit string -> list of single-digit ints."""
    return [int(c) for c in text.strip()]


def image_layers(digits: list[int], width: int, height: int) -> list[list[int]]:
    """Chop the flat list into width*height-pixel layers."""
    size = width * height
    return [digits[i : i + size] for i in range(0, len(digits), size)]


def part1(digits: list[int], width: int, height: int) -> int:
    """Fewest-zeros layer, scored #1s * #2s."""
    layer = min(image_layers(digits, width, height), key=lambda L: L.count(0))
    return layer.count(1) * layer.count(2)


def decode_image(digits: list[int], width: int, height: int) -> list[int]:
    """Front-to-back: each pixel is the first opaque (non-2) value."""
    size = width * height
    layers = image_layers(digits, width, height)
    pixels = []
    for p in range(size):
        for layer in layers:  # front (layer 0) to back
            if layer[p] != 2:
                pixels.append(layer[p])
                break
    return pixels


def render(pixels: list[int], width: int, height: int) -> str:
    """Flat pixel list -> printable block ('#' lit, ' ' dark)."""
    return "\n".join(
        "".join("#" if pixels[r * width + c] == 1 else " " for c in range(width)) for r in range(height)
    )


def part2(digits: list[int], width: int, height: int) -> str:
    """Decode then render the human-readable letters."""
    return render(decode_image(digits, width, height), width, height)


if __name__ == "__main__":
    from pathlib import Path

    raw = (Path(__file__).resolve().parent.parent / "inputs" / "day08.txt").read_text()
    digits = parse_input(raw)
    print("part 1:", part1(digits, 25, 6))
    print("part 2:")
    print(part2(digits, 25, 6))
