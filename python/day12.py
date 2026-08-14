"""AoC 2019 Day 12 — The N-Body Problem.

Algorithm-flavored companion to src/day12.rkt. Four moons, each with a 3-D
position and velocity; every time step, gravity nudges each velocity
component by +/-1 toward every other moon, then each position moves by its
velocity.

The one observation the whole day rests on: **the three axes never
interact**. Gravity on x depends only on the x components, so this is three
independent 1-D simulations, not one 3-D one. Part 1 (energy after 1000
steps) runs the same kernel three times and recombines. Part 2 (first repeat
of the whole state) is intractable as a 6-D state search — the answer is
~3.8e14 — but each axis repeats within a few hundred thousand steps, and the
system repeats when all three coincide, so the answer is lcm of the three
per-axis periods.

Comparing against the *initial* state (rather than remembering every state
seen) is sound because the step map is invertible: v is recoverable, then
p = p' - v', then v = v' - gravity(p). An injective map means the orbit is a
pure cycle with no lead-in tail, so the first repeat IS the start.
"""

from __future__ import annotations

import re
from math import lcm


def parse_input(text: str) -> list[tuple[int, int, int]]:
    """One (x, y, z) per line of `<x=3, y=3, z=0>`; just grab the integers."""
    return [tuple(int(n) for n in re.findall(r"-?\d+", line)) for line in text.strip().splitlines()]


def sgn(n: int) -> int:
    return (n > 0) - (n < 0)


def step_axis(ps: list[int], vs: list[int]) -> tuple[list[int], list[int]]:
    """One time step of ONE axis. Velocities update from the old positions,
    positions from the new velocities — the puzzle's two-phase ordering,
    enforced by data flow rather than by discipline. `sgn(0) == 0`, so a
    moon's self-term drops out of the gravity sum for free."""
    vs = [v + sum(sgn(q - p) for q in ps) for p, v in zip(ps, vs)]
    ps = [p + v for p, v in zip(ps, vs)]
    return ps, vs


def simulate(moons: list[tuple[int, int, int]], steps: int):
    """`steps` steps of the whole system -> per-moon position and velocity
    triples. `zip(*rows)` is the transpose, used in both directions: to
    split the moons into three axes, and to zip the results back."""
    axes = [list(a) for a in zip(*moons)]
    zeros = [0] * len(moons)
    finals = []
    for ps in axes:
        vs = zeros
        for _ in range(steps):
            ps, vs = step_axis(ps, vs)
        finals.append((ps, vs))
    positions = list(zip(*(ps for ps, _ in finals)))
    velocities = list(zip(*(vs for _, vs in finals)))
    return positions, velocities


def total_energy(positions, velocities) -> int:
    """Potential (sum |position|) x kinetic (sum |velocity|), per moon. The
    only place the three axes are ever combined."""
    return sum(sum(abs(c) for c in p) * sum(abs(c) for c in v) for p, v in zip(positions, velocities))


def part1(moons: list[tuple[int, int, int]], steps: int = 1000) -> int:
    return total_energy(*simulate(moons, steps))


def axis_period(ps0: list[int]) -> int:
    """Steps until one axis returns to its starting (positions, velocities)."""
    vs0 = [0] * len(ps0)
    ps, vs, n = ps0, vs0, 0
    while True:
        ps, vs = step_axis(ps, vs)
        n += 1
        if ps == ps0 and vs == vs0:
            return n


def part2(moons: list[tuple[int, int, int]]) -> int:
    return lcm(*(axis_period(list(a)) for a in zip(*moons)))


if __name__ == "__main__":
    from pathlib import Path

    raw = (Path(__file__).resolve().parent.parent / "inputs" / "day12.txt").read_text()
    moons = parse_input(raw)
    print("part 1:", part1(moons))
    print("part 2:", part2(moons))
