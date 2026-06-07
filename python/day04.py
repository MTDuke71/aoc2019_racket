"""AoC 2019 Day 4 — Secure Container.

Algorithm-flavored companion to src/day04.rkt. The puzzle is a digit-string
filter over a numeric range: count six-digit numbers whose digits are
**non-decreasing** and which contain an **adjacent repeated** digit.

The whole thing collapses once you **run-length encode** the digits —
``itertools.groupby`` does exactly this, turning a sorted digit string into
its maximal runs. Then:

  * non-decreasing  <=>  ``list(digits) == sorted(digits)``;
  * Part 1          <=>  some run has length >= 2;
  * Part 2          <=>  some run has length exactly 2.

The shipped approach brute-forces every number in the range and filters.
The closed-form combinatorial count is in the "problem within the problem"
sidebar of the function guide (non-decreasing strings are combinations with
repetition — stars and bars).
"""

from __future__ import annotations

from itertools import groupby


def parse_input(text: str) -> tuple[int, int]:
    """'lo-hi' -> (lo, hi) inclusive bounds."""
    lo, hi = text.strip().split("-")
    return int(lo), int(hi)


def run_lengths(n: int) -> list[int]:
    """Lengths of the maximal runs of consecutive equal digits.

    111122 -> [4, 2];  123444 -> [1, 1, 1, 3].  ``groupby`` IS run-length
    encoding: it yields one group per maximal run of equal adjacent items.
    """
    return [len(list(g)) for _, g in groupby(str(n))]


def non_decreasing(n: int) -> bool:
    s = str(n)
    return list(s) == sorted(s)  # digit chars sort the same as digit values


def part1_ok(n: int) -> bool:
    return non_decreasing(n) and any(r >= 2 for r in run_lengths(n))


def part2_ok(n: int) -> bool:
    return non_decreasing(n) and any(r == 2 for r in run_lengths(n))


def part1(bounds: tuple[int, int]) -> int:
    lo, hi = bounds
    return sum(part1_ok(n) for n in range(lo, hi + 1))


def part2(bounds: tuple[int, int]) -> int:
    lo, hi = bounds
    return sum(part2_ok(n) for n in range(lo, hi + 1))


# ---------------------------------------------------------------------------
# Sidebar: counting without enumeration (documented, not the shipped path).
#
# A non-decreasing d-digit string is a multiset of d digits drawn from
# {0..9} (here {1..9}, since a leading 0 would drop a digit) — i.e.
# "combinations with repetition", counted by stars and bars as
# C(d + k - 1, d) for k symbols. The "at least one double" and "exactly one
# clean double" constraints can then be subtracted off combinatorially
# (inclusion-exclusion over which digit forms the run), giving an O(1)
# answer independent of the range width. The brute force is ~510k cheap
# checks here, fast enough that the closed form is a curiosity rather than a
# necessity — but it's the transferable trick when the range is astronomical.
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    from pathlib import Path

    raw = (Path(__file__).resolve().parent.parent / "inputs" / "day04.txt").read_text()
    bounds = parse_input(raw)
    print("part 1:", part1(bounds))
    print("part 2:", part2(bounds))
