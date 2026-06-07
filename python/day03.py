"""AoC 2019 Day 3 — Crossed Wires.

Algorithm-flavored companion to src/day03.rkt. The core idea is a
**spatial hash**: rasterize each wire one unit cell at a time into a dict
mapping point -> first-arrival step count, then the crossings are exactly
the keys the two dicts share.

  * Part 1 minimizes a function of the crossing POINT (Manhattan distance).
  * Part 2 minimizes a function of the STEP COUNTS (combined arrival).

Because the trace already records step counts, one rasterization pass per
wire serves both parts.

Two algorithmic alternatives worth knowing (see the function guide):
  - points as complex numbers (translation = addition);
  - segment intersection: treat each move as an axis-aligned segment and
    intersect O(n^2) segment pairs instead of rasterizing O(path-length)
    cells. For AoC-sized inputs the rasterization wins on simplicity.
"""

from __future__ import annotations

DIRS = {"R": (1, 0), "L": (-1, 0), "U": (0, 1), "D": (0, -1)}


def parse_input(text: str) -> list[list[tuple[str, int]]]:
    """Two lines -> two wires; each wire a list of (direction, distance)."""
    wires = []
    for line in text.strip().splitlines():
        wires.append([(tok[0], int(tok[1:])) for tok in line.split(",")])
    return wires


def trace(wire: list[tuple[str, int]]) -> dict[tuple[int, int], int]:
    """Map every visited cell (origin excluded) to its first-arrival step.

    Steps only increase, so the first visit is the cheapest — we use
    ``setdefault`` to keep the earliest arrival and ignore later revisits.
    """
    seen: dict[tuple[int, int], int] = {}
    x = y = steps = 0
    for direction, dist in wire:
        dx, dy = DIRS[direction]
        for _ in range(dist):
            x, y = x + dx, y + dy
            steps += 1
            seen.setdefault((x, y), steps)
    return seen


def crossings(wires: list[list[tuple[str, int]]]) -> list[tuple[tuple[int, int], int]]:
    """One (point, combined_steps) entry per cell both wires visit."""
    h1, h2 = trace(wires[0]), trace(wires[1])
    return [(p, h1[p] + h2[p]) for p in h1.keys() & h2.keys()]


def part1(wires: list[list[tuple[str, int]]]) -> int:
    return min(abs(x) + abs(y) for (x, y), _ in crossings(wires))


def part2(wires: list[list[tuple[str, int]]]) -> int:
    return min(steps for _, steps in crossings(wires))


# ---------------------------------------------------------------------------
# Alternative: segment intersection (documented, not the shipped path).
#
# Rasterizing is O(total path length). For long paths the cheaper model is
# to keep each move as an axis-aligned SEGMENT and intersect the O(n)
# segments of one wire against the other's — O(n^2) in the segment count,
# which for ~300 segments per wire is ~90k cheap interval tests vs ~150k
# point inserts. It also generalizes to non-integer crossings. The catch is
# bookkeeping: you must carry each segment's start-step to recover Part 2's
# combined distance, and handle collinear overlaps. The dict raster is
# simpler and fast enough, which is why both languages ship it.
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    from pathlib import Path

    raw = (Path(__file__).resolve().parent.parent / "inputs" / "day03.txt").read_text()
    wires = parse_input(raw)
    print("part 1:", part1(wires))
    print("part 2:", part2(wires))
