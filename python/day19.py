"""AoC 2019 Day 19 -- Tractor Beam.

The Intcode machine is unchanged (frozen at Day 9; see python/intcode.py). The
peripheral this time is an ORACLE: feed it an (x, y) coordinate, get back one
bit -- is that point inside the tractor beam? The program then halts, so every
query costs a fresh VM. The puzzle is not about running the machine, it is
about how FEW questions you can get away with asking it.

Part 1 asks 2500 questions because the statement says to (a 50x50 census).
Part 2 is where the counting-queries lens pays off: the beam is a cone -- two
rays from the origin, everything between them lit -- so each row is one
contiguous run whose left edge only ever moves right as y grows. That
monotonicity means a 100x100 axis-aligned square fits the cone exactly when
two opposite corners are lit: bottom-left in the beam and top-right in the
beam pins all four corners, and convexity fills in the interior. So the search
walks ONE point -- the candidate square's bottom-left corner -- down the
beam's left edge, asking a couple of questions per row instead of scanning
areas.

The statement's worked example ships a 10x10 picture and no Intcode program at
all, so everything after `beam_probe` takes a plain `probe(x, y) -> bool`
callable -- the same split that let Day 17 test against its ASCII picture. The
Intcode program is just one way to manufacture a probe.

Run:  python python/day19.py
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from intcode import VM

Probe = Callable[[int, int], bool]


def parse_input(text: str) -> list[int]:
    return [int(t) for t in text.strip().split(",")]


def beam_probe(program: list[int]) -> Probe:
    """Wrap the drone program as `probe(x, y) -> bool`.

    One VM per query, because the program reads two inputs, reports one bit
    and halts -- it cannot be resumed. (The VM copies the program into its own
    memory dict, so the caller's list is never mutated and can be reused.)
    """

    def probe(x: int, y: int) -> bool:
        if x < 0 or y < 0:
            raise ValueError(f"negative coordinates confuse the drone: ({x}, {y})")
        vm = VM(program)
        vm.inputs.extend((x, y))
        while True:
            result = vm.step()
            if isinstance(result, tuple):
                return bool(result[1])
            if result != "ran":
                raise RuntimeError(f"drone {result} without reporting for ({x}, {y})")

    return probe


def count_beam(probe: Probe, size: int) -> int:
    """Points the beam affects in the `size` x `size` area nearest the emitter."""
    return sum(probe(x, y) for y in range(size) for x in range(size))


def left_edge(probe: Probe, y: int, start: int = 0) -> int:
    """Leftmost lit x on row `y`, scanning rightward from `start`.

    The tripwire bound is not part of the algorithm -- a cone through the
    origin keeps its left edge within a constant slope of y, so a scan that
    has walked far past that is probing an empty row and would otherwise walk
    forever.
    """
    x = start
    while not probe(x, y):
        x += 1
        if x > 4 * y + 10:
            raise ValueError(f"no beam found on row {y}")
    return x


def find_square(probe: Probe, size: int) -> tuple[int, int]:
    """Top-left corner of the first `size` x `size` square inside the beam.

    `(x, y)` tracks the candidate square's BOTTOM-LEFT corner, riding the
    beam's left edge downward. Because each row's run starts at or right of
    the row above's (the cone widens), x never restarts at 0 -- `left_edge`
    resumes from the previous row's answer, so the whole search is O(rows)
    probes, not O(area). A square whose bottom-left corner hugs the left edge
    fits as soon as its top-right corner is lit; the first row where that
    happens is the square nearest the emitter.
    """
    y = size - 1  # the first row deep enough to be a square's bottom edge
    x = left_edge(probe, y)
    while not probe(x + size - 1, y - size + 1):
        y += 1
        x = left_edge(probe, y, x)
    return x, y - size + 1


def part1(program: list[int]) -> int:
    return count_beam(beam_probe(program), 50)


def part2(program: list[int]) -> int:
    x, y = find_square(beam_probe(program), 100)
    return 10000 * x + y


def solve(program: list[int]) -> tuple[int, int]:
    return part1(program), part2(program)


def main() -> None:
    text = (Path(__file__).resolve().parent.parent / "inputs" / "day19.txt").read_text()
    program = parse_input(text)
    probe = beam_probe(program)

    for y in range(50):
        print("".join("#" if probe(x, y) else "." for x in range(50)))
    print(f"  part 1: {count_beam(probe, 50)}")

    x, y = find_square(probe, 100)
    print(f"  100x100 square at ({x}, {y})")
    print(f"  part 2: {10000 * x + y}")


if __name__ == "__main__":
    main()
