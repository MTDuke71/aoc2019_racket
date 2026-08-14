"""AoC 2019 Day 10 — Monitoring Station.

Algorithm-flavored companion to src/day10.rkt. Two classic lattice-geometry
moves carry the whole day:

  * **Part 1 — primitive direction vectors.** Two asteroids are on the same
    line of sight from the station iff the *reduced* (divided by gcd) delta
    vectors are equal. So the number an asteroid can SEE is the number of
    DISTINCT reduced directions to the others — collinear asteroids collapse
    to one direction, and only the nearest of each is visible. Best = the
    asteroid with the most distinct directions.

  * **Part 2 — angular sweep (round-robin by angle).** The laser starts
    pointing up and rotates clockwise, vaporizing the nearest asteroid on
    each bearing, one per bearing per rotation. Group the others by reduced
    direction, sort each group near→far, sort the groups by clockwise-from-up
    angle (atan2(dx, -dy)), then round-robin: one sweep of the angle-ordered
    groups = one full rotation. The 200th vaporized gives x*100 + y.

The gcd reduction is the same primitive-vector idea as "how many lattice
points lie strictly between two grid points" (the answer is gcd(|dx|,|dy|)-1).
"""

from __future__ import annotations

import math
from collections import defaultdict


def parse_input(text: str) -> list[tuple[int, int]]:
    return [(x, y) for y, row in enumerate(text.split()) for x, ch in enumerate(row) if ch == "#"]


def direction(dx: int, dy: int) -> tuple[int, int]:
    """Reduce a delta to its primitive (gcd-divided) direction vector."""
    g = math.gcd(abs(dx), abs(dy))
    return (dx // g, dy // g)


def count_visible(station: tuple[int, int], asteroids: list[tuple[int, int]]) -> int:
    sx, sy = station
    dirs = {direction(x - sx, y - sy) for (x, y) in asteroids if (x, y) != station}
    return len(dirs)


def best(asteroids: list[tuple[int, int]]) -> tuple[tuple[int, int], int]:
    """The station and its visible count (the Part 1 answer is the count)."""
    return max(((a, count_visible(a, asteroids)) for a in asteroids), key=lambda p: p[1])


def part1(asteroids: list[tuple[int, int]]) -> int:
    return best(asteroids)[1]


def vaporization_order(station: tuple[int, int], asteroids: list[tuple[int, int]]) -> list[tuple[int, int]]:
    sx, sy = station

    def dist2(a):
        return (a[0] - sx) ** 2 + (a[1] - sy) ** 2

    def angle(a):
        # clockwise from straight up: up=0, right=pi/2, down=pi, left=3pi/2
        theta = math.atan2(a[0] - sx, -(a[1] - sy))
        return theta if theta >= 0 else theta + 2 * math.pi

    groups: dict[tuple[int, int], list] = defaultdict(list)
    for a in asteroids:
        if a != station:
            groups[direction(a[0] - sx, a[1] - sy)].append(a)

    # each ray sorted near->far; rays ordered by clockwise angle
    rays = [
        sorted(members, key=dist2) for _, members in sorted(groups.items(), key=lambda kv: angle(kv[1][0]))
    ]

    order = []
    while any(rays):
        for ray in rays:
            if ray:
                order.append(ray.pop(0))  # nearest on this bearing dies this rotation
    return order


def part2(asteroids: list[tuple[int, int]]) -> int:
    station, _ = best(asteroids)
    x, y = vaporization_order(station, asteroids)[199]  # the 200th
    return 100 * x + y


if __name__ == "__main__":
    from pathlib import Path

    raw = (Path(__file__).resolve().parent.parent / "inputs" / "day10.txt").read_text()
    asteroids = parse_input(raw)
    print("part 1:", part1(asteroids))
    print("part 2:", part2(asteroids))
