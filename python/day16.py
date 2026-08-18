"""AoC 2019 Day 16 -- Flawed Frequency Transmission.

One phase of FFT is a MATRIX-VECTOR PRODUCT: out = M @ digits (mod 10, taking
absolute value first). The statement describes M row by row, but the thing to
see is its shape. Row k (1-based) is

    k-1 zeros, k ones, k zeros, k minus-ones, k zeros, k ones, ...

so M is upper triangular -- row k is zero everywhere left of column k -- and
each row is a handful of CONSTANT-VALUE RUNS, never an arbitrary vector. Two
consequences, and they are the whole day:

  * A run of +1s or -1s over a contiguous slice is a PREFIX-SUM query. Row k
    has about n/k runs, so a phase costs sum_k n/k = n*H(n) ~ n ln n instead of
    the n^2 the definition implies. That is what `phase` does below.
  * The bottom half of the matrix (k > n/2) degenerates: the first run of ones
    starts at column k and would end at column 2k-1, which is off the end. So
    every row below the midpoint is just "sum of the suffix from k on" -- and
    a suffix sum is a single running total swept right to left, no prefix array
    and no per-row loop at all.

Part 1 (n = 650) lives in the first regime; Part 2 lives entirely in the
second. Repeating the signal 10000 times makes n = 6,500,000, but the message
offset is 5,972,877 -- past the midpoint -- and triangularity says nothing left
of the offset can influence anything at or after it. So Part 2 never builds the
real signal, never runs `phase`, and never touches 92% of the digits: it takes
the 527,123-digit tail and sweeps a running total over it 100 times.

That the offset lands in the bottom half is a property of the INPUT, not a
promise of the statement, so `part2` checks it rather than assuming it.

Run:  python python/day16.py
"""

from __future__ import annotations

from itertools import accumulate
from pathlib import Path

PHASES = 100
REPEATS = 10_000


def parse_input(text: str) -> list[int]:
    """The signal as a list of single digits.

    `.strip()` is doing CRLF duty: inputs downloaded on Windows end `\r\n`, and
    an unstripped `\r` would become `int('\r')` -- a ValueError, not a silent
    wrong answer, but a crash on a fresh input all the same.
    """
    return [int(ch) for ch in text.strip()]


def phase(digits: list[int]) -> list[int]:
    """One FFT phase, via prefix sums.

    `prefix[j]` is the sum of the first j digits, so any slice total is one
    subtraction. Row k of the pattern matrix contributes the alternating runs

        +digits[k-1 : 2k-1]  -digits[3k-1 : 4k-1]  +digits[5k-1 : 6k-1]  ...

    i.e. run m starts at (2m+1)*k - 1 and is k wide, with sign (-1)**m. The
    left edge of run 0 is column k-1 (0-based) -- that is the "skip the very
    first value exactly once" offset, and it is why the matrix is triangular.

    Run starts grow by 2k, so row k does ~n/(2k) subtractions and the phase
    costs O(n log n). Slice ends are clamped by `min`, which is also what makes
    the last, truncated run of each row come out right.
    """
    n = len(digits)
    prefix = [0, *accumulate(digits)]

    out = []
    for k in range(1, n + 1):
        total = 0
        start, sign = k - 1, 1
        while start < n:
            total += sign * (prefix[min(start + k, n)] - prefix[start])
            start += 2 * k
            sign = -sign
        out.append(abs(total) % 10)
    return out


def transform(digits: list[int], phases: int = PHASES) -> list[int]:
    for _ in range(phases):
        digits = phase(digits)
    return digits


def digits_to_str(digits) -> str:
    return "".join(map(str, digits))


def part1(digits: list[int]) -> str:
    """First eight digits after 100 phases.

    A string, not an int: the answer can begin with a zero (the statement's own
    four-phase trace ends `01029498`), and `1029498` is a different answer.
    """
    return digits_to_str(transform(digits)[:8])


def message_offset(digits: list[int]) -> int:
    """The first seven digits, read as a decimal number."""
    return int(digits_to_str(digits[:7]))


def real_tail(digits: list[int], offset: int, repeats: int = REPEATS) -> list[int]:
    """The repeated signal from `offset` to its end, built without materialising it all.

    `digits * repeats` would be a 6.5-million-element list to keep half a
    million of. Instead: `offset` falls `r` digits into copy number `q`, so the
    tail is the remainder of that copy followed by every whole copy after it.

        len == (n - r) + (repeats - q - 1) * n == n * repeats - offset
    """
    q, r = divmod(offset, len(digits))
    return digits[r:] + digits * (repeats - q - 1)


def suffix_transform(tail: list[int], phases: int = PHASES) -> list[int]:
    """Run `phases` phases on a suffix that begins at or past the midpoint.

    Below the midpoint every row of the pattern matrix is a run of ones
    reaching the end of the signal (see the module docstring), so the phase
    collapses to

        out[i] = (sum of tail[i:]) % 10

    which is a suffix sum: reverse, take a running total, reverse back. The
    matrix restricted to that region is UNIT UPPER TRIANGULAR, so no digit left
    of `offset` can ever reach the answer -- that is the licence to throw away
    92% of the signal before doing any work.

    `accumulate` does the running total in C; the `% 10` comprehension is the
    only per-digit Python. Reducing every phase keeps the partial sums bounded
    by 9 * len(tail), comfortably inside a machine word.
    """
    reversed_tail = tail[::-1]
    for _ in range(phases):
        reversed_tail = [value % 10 for value in accumulate(reversed_tail)]
    return reversed_tail[::-1]


def part2(digits: list[int]) -> str:
    """The eight-digit message, 10000 repeats in.

    Precondition, and the reason the day is tractable at all: the offset lands
    in the BOTTOM HALF of the 6.5-million-digit signal. Nothing in the
    statement promises it -- it is a property every published input happens to
    share -- so it is asserted rather than assumed silently.
    """
    offset = message_offset(digits)
    total = len(digits) * REPEATS
    if offset < total // 2:
        raise ValueError(f"offset {offset} is in the upper half of {total}; suffix sums do not apply")
    return digits_to_str(suffix_transform(real_tail(digits, offset))[:8])


def solve(digits: list[int]) -> tuple[str, str]:
    return part1(digits), part2(digits)


def main() -> None:
    text = (Path(__file__).resolve().parent.parent / "inputs" / "day16.txt").read_text()
    digits = parse_input(text)
    offset = message_offset(digits)
    print(f"  signal: {len(digits)} digits; repeated {REPEATS}x -> {len(digits) * REPEATS}")
    print(f"  offset: {offset} (tail of {len(digits) * REPEATS - offset} digits)")
    print(f"  part 1: {part1(digits)}")
    print(f"  part 2: {part2(digits)}")


if __name__ == "__main__":
    main()
