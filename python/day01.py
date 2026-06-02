"""AoC 2019 Day 1 — The Tyranny of the Rocket Equation.

Algorithm-flavored companion to src/day01.rkt. Day 1 is mostly
mechanics, but Part 2 is a genuine named technique — a *fixed-point
iteration*: feed a function's output back into itself until it stops
changing (here, until it stops being positive). The Racket version uses
a tail-recursive named-let; this is the same loop in Python so the
shape is legible at a glance.
"""

from __future__ import annotations


def parse_input(text: str) -> list[int]:
    return [int(tok) for tok in text.split()]


def fuel(mass: int) -> int:
    """floor(mass / 3) - 2."""
    return mass // 3 - 2


def total_fuel(mass: int) -> int:
    """Fixed-point iteration of `fuel`, summing every positive step."""
    total = 0
    f = fuel(mass)
    while f > 0:
        total += f
        f = fuel(f)
    return total


def part1(masses: list[int]) -> int:
    return sum(fuel(m) for m in masses)


def part2(masses: list[int]) -> int:
    return sum(total_fuel(m) for m in masses)


if __name__ == "__main__":
    from pathlib import Path

    raw = (Path(__file__).resolve().parent.parent / "inputs" / "day01.txt").read_text()
    masses = parse_input(raw)
    print("part 1:", part1(masses))
    print("part 2:", part2(masses))
