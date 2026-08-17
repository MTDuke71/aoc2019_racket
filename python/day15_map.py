"""Day 15 -- dump the 41x41 map to files.

The maze is the day's real artifact: 1,659 charted squares, 799 of them open,
in a 41x41 bounding box. `python/day15.py` prints it once and throws it away.
This writes it out, in three formats and three colourings, so it can be looked
at properly.

    python python/day15_map.py            # -> maps/
    python python/day15_map.py --out DIR  # somewhere else
    python python/day15_map.py --scale 24 # bigger pixels

Formats
    .txt   ASCII, the same glyphs day15.py prints
    .svg   vector -- scales to any size, opens in a browser, diffable text
    .png   raster, written with nothing but `zlib` from the standard library
           (no Pillow in this venv, and adding a dependency to draw 1,681
           rectangles would be silly)

Colourings
    plain     wall / open, with the droid's start and the oxygen system marked
    route     the 254-step shortest path from the start to the oxygen -- Part 1,
              drawn
    fill      every open square shaded by its distance from the oxygen system,
              which is literally Part 2: the ramp runs 0 to 268 minutes

Outputs are derived from the puzzle input, so `maps/` is gitignored for the
same reason `inputs/*.txt` and the full Intcode listings are.
"""

from __future__ import annotations

import argparse
import struct
import zlib
from pathlib import Path

from day15 import MOVES, OPEN, OXYGEN, WALL, _ahead, distances, explore, parse_input
from intcode import VM

Point = tuple[int, int]
RGB = tuple[int, int, int]

# Near-black ground so the maze reads as lit corridors rather than ink on
# paper, and so the distance ramp has somewhere to go. It has to stay clear of
# the ramp's dark end too -- a navy wall against a navy "just filled" corridor
# loses the maze exactly where the fill starts.
WALL_RGB: RGB = (10, 12, 15)
OPEN_RGB: RGB = (206, 212, 222)
START_RGB: RGB = (255, 92, 118)
OXYGEN_RGB: RGB = (120, 255, 214)
ROUTE_RGB: RGB = (255, 176, 59)

# A sequential ramp for the fill, blue -> teal -> pale yellow. Ordered so that
# "just filled" is dark and "last to fill" is bright, which puts the emphasis
# on the 268th minute -- the number Part 2 actually asks for.
RAMP: tuple[RGB, ...] = (
    (16, 78, 152),
    (12, 116, 184),
    (65, 182, 196),
    (161, 218, 180),
    (255, 255, 204),
)


# ------------------------------------------------------------------ the map


def route(grid: dict[Point, int], start: Point, goal: Point) -> list[Point]:
    """The shortest path start -> goal, walked back down the distance map.

    BFS labels every cell with its distance from `start`; from `goal`, step to
    any neighbour labelled one less, repeatedly. Any such choice is on *a*
    shortest path, and on this input the maze is a tree so there is only one.
    """
    dist = distances(grid, start)
    if goal not in dist:
        return []
    path = [goal]
    while path[-1] != start:
        here = path[-1]
        path.append(next(n for d in MOVES if (n := _ahead(here, d)) in dist and dist[n] == dist[here] - 1))
    return path[::-1]


def ramp(fraction: float) -> RGB:
    """Sample RAMP at 0.0..1.0 with linear interpolation between stops."""
    if fraction <= 0:
        return RAMP[0]
    if fraction >= 1:
        return RAMP[-1]
    scaled = fraction * (len(RAMP) - 1)
    index = int(scaled)
    lo, hi, t = RAMP[index], RAMP[index + 1], scaled - index
    return (
        round(lo[0] + (hi[0] - lo[0]) * t),
        round(lo[1] + (hi[1] - lo[1]) * t),
        round(lo[2] + (hi[2] - lo[2]) * t),
    )


def colours(grid: dict[Point, int], oxygen: Point, scheme: str) -> dict[Point, RGB]:
    """One RGB per charted square, under the named colouring."""
    out = {p: (WALL_RGB if tile == WALL else OPEN_RGB) for p, tile in grid.items()}

    if scheme == "fill":
        fill = distances(grid, oxygen)
        longest = max(fill.values())
        for p, minutes in fill.items():
            out[p] = ramp(minutes / longest)
    elif scheme == "route":
        for p in route(grid, (0, 0), oxygen):
            out[p] = ROUTE_RGB

    out[(0, 0)] = START_RGB
    out[oxygen] = OXYGEN_RGB
    return out


def bounds(grid: dict[Point, int]) -> tuple[int, int, int, int]:
    xs = [x for x, _ in grid]
    ys = [y for _, y in grid]
    return min(xs), min(ys), max(xs), max(ys)


# ------------------------------------------------------------------- ASCII


def as_text(grid: dict[Point, int], oxygen: Point, scheme: str) -> str:
    glyph = {WALL: "#", OPEN: ".", OXYGEN: "O"}
    on_route = set(route(grid, (0, 0), oxygen)) if scheme == "route" else set()
    x0, y0, x1, y1 = bounds(grid)

    rows = []
    for y in range(y0, y1 + 1):
        row = []
        for x in range(x0, x1 + 1):
            here = (x, y)
            if here == (0, 0):
                row.append("D")
            elif here == oxygen:
                row.append("O")
            elif here in on_route:
                row.append("*")
            else:
                row.append(glyph.get(grid.get(here), " "))
        rows.append("".join(row))
    return "\n".join(rows)


# --------------------------------------------------------------------- SVG


def as_svg(grid: dict[Point, int], oxygen: Point, scheme: str, scale: int) -> str:
    """One <rect> per charted square. Runs of equal colour are merged along a
    row, which takes the 1,659 rectangles down to a few hundred and makes the
    file readable."""
    paint = colours(grid, oxygen, scheme)
    x0, y0, x1, y1 = bounds(grid)
    width, height = (x1 - x0 + 1) * scale, (y1 - y0 + 1) * scale
    strip = 3 * scale  # a band under the map for the caption and the ramp

    header = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height + strip}" '
        f'viewBox="0 0 {width} {height + strip}" shape-rendering="crispEdges" '
        f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">'
    )
    parts = [header, f'<rect width="{width}" height="{height + strip}" fill="rgb{WALL_RGB}"/>']

    for y in range(y0, y1 + 1):
        run_start, run_colour = None, None
        for x in range(x0, x1 + 2):
            here = paint.get((x, y)) if x <= x1 else None
            if here == run_colour:
                continue
            if run_colour is not None and run_colour != WALL_RGB:
                parts.append(
                    f'<rect x="{(run_start - x0) * scale}" y="{(y - y0) * scale}" '
                    f'width="{(x - run_start) * scale}" height="{scale}" fill="rgb{run_colour}"/>'
                )
            run_start, run_colour = x, here

    parts.extend(_svg_legend(grid, oxygen, scheme, width, height, scale))
    parts.append("</svg>")
    return "\n".join(parts)


def _svg_legend(
    grid: dict[Point, int], oxygen: Point, scheme: str, width: int, height: int, scale: int
) -> list[str]:
    """Caption under the map, plus a colour ramp for the `fill` scheme.

    SVG gets this and PNG does not, because SVG has <text> and the hand-rolled
    PNG writer would need a font renderer to say the same thing.
    """
    text = f'fill="rgb{OPEN_RGB}" font-size="{scale * 0.62:.1f}"'
    caption = legend(grid, oxygen, scheme)
    parts = [f'<text x="{scale // 2}" y="{height + scale}" {text}>Day 15 - {caption}</text>']

    if scheme != "fill":
        return parts

    bar_y, bar_h = height + scale * 1.5, scale
    bar_x, bar_w = scale * 4, width - scale * 8
    steps = 128
    for i in range(steps):
        r, g, b = ramp(i / (steps - 1))
        parts.append(
            f'<rect x="{bar_x + bar_w * i / steps:.2f}" y="{bar_y}" '
            f'width="{bar_w / steps + 1:.2f}" height="{bar_h}" fill="rgb({r},{g},{b})"/>'
        )
    label = f'{text} dominant-baseline="middle"'
    parts.append(f'<text x="{scale // 2}" y="{bar_y + bar_h / 2}" {label}>0</text>')
    longest = max(distances(grid, oxygen).values())
    parts.append(f'<text x="{bar_x + bar_w + scale // 2}" y="{bar_y + bar_h / 2}" {label}>{longest}</text>')
    return parts


# --------------------------------------------------------------------- PNG


def as_png(grid: dict[Point, int], oxygen: Point, scheme: str, scale: int) -> bytes:
    """A minimal 8-bit truecolour PNG, built from `zlib` and `struct`.

    PNG is four things: the 8-byte signature, an IHDR chunk describing the
    raster, an IDAT chunk holding zlib-compressed scanlines each prefixed with
    a filter byte (0 = none, which is all this needs), and an IEND. Every chunk
    is length + type + payload + CRC32 of (type + payload).
    """
    paint = colours(grid, oxygen, scheme)
    x0, y0, x1, y1 = bounds(grid)
    width, height = (x1 - x0 + 1) * scale, (y1 - y0 + 1) * scale

    raw = bytearray()
    for y in range(y0, y1 + 1):
        line = bytearray()
        for x in range(x0, x1 + 1):
            line += bytes(paint.get((x, y), WALL_RGB)) * scale
        for _ in range(scale):
            raw += b"\x00" + line  # filter byte 0, then the row, `scale` times

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit, truecolour
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


# -------------------------------------------------------------------- driver


def legend(grid: dict[Point, int], oxygen: Point, scheme: str) -> str:
    """The caption for a colouring, with the numbers read off the map itself."""
    if scheme == "plain":
        return "# wall, . open, D droid start, O oxygen system"
    if scheme == "route":
        steps = len(route(grid, (0, 0), oxygen)) - 1
        return f"* = the {steps}-step shortest path from D to O (Part 1)"
    longest = max(distances(grid, oxygen).values())
    return f"shaded by distance from O: 0 to {longest} minutes (Part 2)"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=None, help="output directory (default: maps/)")
    parser.add_argument("--scale", type=int, default=16, help="pixels per square (default: 16)")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    out = args.out or root / "maps"
    out.mkdir(parents=True, exist_ok=True)

    program = parse_input((root / "inputs" / "day15.txt").read_text())
    grid, oxygen = explore(VM(program))
    x0, y0, x1, y1 = bounds(grid)
    print(f"charted {len(grid)} squares in a {x1 - x0 + 1}x{y1 - y0 + 1} box; oxygen at {oxygen}\n")

    for scheme in ("plain", "route", "fill"):
        stem = f"day15_map_{scheme}"

        if scheme != "fill":  # a distance ramp says nothing in ASCII
            text = as_text(grid, oxygen, scheme)
            header = f"AoC 2019 Day 15 -- {legend(grid, oxygen, scheme)}\n\n"
            (out / f"{stem}.txt").write_text(header + text + "\n", encoding="utf-8")
            print(f"  {(out / f'{stem}.txt').relative_to(root)}")

        (out / f"{stem}.svg").write_text(as_svg(grid, oxygen, scheme, args.scale), encoding="utf-8")
        print(f"  {(out / f'{stem}.svg').relative_to(root)}")

        (out / f"{stem}.png").write_bytes(as_png(grid, oxygen, scheme, args.scale))
        print(f"  {(out / f'{stem}.png').relative_to(root)}   {legend(grid, oxygen, scheme)}")


if __name__ == "__main__":
    main()
