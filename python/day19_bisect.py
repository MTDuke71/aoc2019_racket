"""Day 19 -- Part 2 by bisection instead of the row-by-row walk.

Sidebar implementation of the "input-agnostic middle ground" in the Day 19
function guide. The shipping `day19.find_square` walks every row from
y = 99 down to the answer (906 rows, 2857 probes). This module asks the
same oracle O(log y) questions instead -- and stays correct in the face of
a trap the guide's sketch did not see:

  THE ROW-FIT PREDICATE IS NOT MONOTONE IN y.  The beam is the wedge
  alpha <= x/y <= beta, so the square with its bottom-left on the left edge
  at row y fits iff  ceil(alpha*y) + 99 <= floor(beta*(y - 99)).  The real
  slack  s(y) = beta*(y-99) - alpha*y - 99  grows by (beta - alpha) per
  row, but the ceil and floor each steal up to one cell, so for
  0 <= s(y) < 2 the lattice decides row by row. On inputs/day19_alt.txt
  that reads: fits at 1427, fails 1428-1430, fits 1431-1432, fails 1433,
  fits from 1434 on. A plain bisection may return 1431 or 1434; the true
  answer is 1427. (Pinned: test_the_fit_predicate_flickers_on_the_lattice.)

The fix is to bound the flicker band from the oracle and scan it:

  * s >= 2 is SUFFICIENT and s >= 0 is NECESSARY, so every false->true
    transition lies within 2/(beta - alpha) rows of the first fit.
  * The measured run width w(y) = R(y) - L(y) + 1 <= (beta - alpha)*y + 1,
    so (beta - alpha) >= (w - 1)/y and the band is at most
    2*y/(w - 1) rows -- a number computable from two probes' worth of
    edge-finding on one row.

So: exponential search up to a row that fits, bisect down to a fitting row
`hi` whose predecessor does not, then scan the band below `hi` linearly and
take the smallest fitting row. Within a row, both edges are bisected too,
bracketed by the beam's centre ray extrapolated from a reference row.

Run:  python python/day19_bisect.py [reps]     -- benchmark vs find_square
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

from day19 import Probe, beam_probe, find_square, left_edge, parse_input


def first_true(pred, lo: int, hi: int) -> int:
    """Smallest i in (lo, hi] with pred(i), given not pred(lo) and pred(hi)
    and pred monotone on the range. O(log(hi - lo)) calls."""
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if pred(mid):
            hi = mid
        else:
            lo = mid
    return hi


def row_run(probe: Probe, y: int, centre: int) -> tuple[int, int]:
    """(L, R) of row y's lit run, given a lit cell `centre` on it.

    Left edge: first lit x in (−1, centre]. Right edge: the run's last lit
    cell, found by doubling a bracket past the centre and bisecting back.
    """
    if not probe(centre, y):
        raise ValueError(f"centre ray missed the beam at ({centre}, {y})")
    left = first_true(lambda x: probe(x, y), -1, centre)
    span = max(centre - left, 1)
    far = centre + 2 * span + 2
    while probe(far, y):
        far += span
    # lit at centre ... lit at R, unlit from R+1 through far
    right = first_true(lambda x: not probe(x, y), centre, far) - 1
    return left, right


def find_square_bisect(probe: Probe, size: int) -> tuple[int, int]:
    """Top-left corner of the first `size` x `size` square inside the beam,
    by bisection over rows. Same contract and answer as `find_square`."""
    y0 = size - 1
    left0 = left_edge(probe, y0)
    right0 = left0
    while probe(right0 + 1, y0):
        right0 += 1
    # The centre ray through row y0's run midpoint: inside the wedge for
    # every deeper row (the wedge is convex and widens).
    mid2, y0_2 = left0 + right0, 2 * y0

    def centre(y: int) -> int:
        return mid2 * y // y0_2 if y0 else 0

    lefts: dict[int, int] = {}

    def lit_left(y: int) -> int:
        if y not in lefts:
            c = centre(y)
            if not probe(c, y):
                raise ValueError(f"centre ray missed the beam at ({c}, {y})")
            lefts[y] = first_true(lambda x: probe(x, y), -1, c)
        return lefts[y]

    def fits(y: int) -> bool:
        return probe(lit_left(y) + size - 1, y - size + 1)

    # Exponential search for a fitting row (the top of the square must
    # stay at or below y0's row, hence the start at y0).
    lo, hi = y0 - 1, y0
    while not fits(hi):
        lo, hi = hi, 2 * hi + 1
    hi = first_true(fits, lo, hi)

    # Bound the flicker band from row hi's measured width and scan it.
    left, right = row_run(probe, hi, centre(hi))
    width = right - left + 1
    band = (2 * hi + width - 2) // max(width - 1, 1)  # ceil(2*hi / (w-1))
    for y in range(max(y0, hi - band - 1), hi):
        if fits(y):
            hi = y
            break
    return lit_left(hi), hi - size + 1


# ------------------------------------------------------------------ bench


class Counted:
    def __init__(self, probe: Probe) -> None:
        self.probe, self.calls = probe, 0

    def __call__(self, x: int, y: int) -> bool:
        self.calls += 1
        return self.probe(x, y)


def bench(label: str, fn, probe: Probe, reps: int) -> tuple[int, float, float]:
    samples, calls, answer = [], 0, None
    for _ in range(reps):
        counted = Counted(probe)
        start = time.perf_counter()
        answer = fn(counted, 100)
        samples.append((time.perf_counter() - start) * 1000.0)
        calls = counted.calls
    x, y = answer
    print(
        f"  {label:<22} {10000 * x + y:>9}  {calls:>5} probes  {min(samples):9.3f} / {statistics.median(samples):9.3f} ms"
    )
    return calls, min(samples), statistics.median(samples)


def main(argv: list[str] | None = None) -> None:
    from day19_disasm import formula_probe, recover_constants

    argv = sys.argv[1:] if argv is None else argv
    reps = int(argv[0]) if argv else 7
    root = Path(__file__).resolve().parents[1] / "inputs"
    for name in ("day19.txt", "day19_alt.txt"):
        path = root / name
        if not path.is_file():
            continue
        mem = parse_input(path.read_text())
        print(f"{name}  (best / median of {reps})")
        print("  -- oracle: live Intcode VM")
        bench("find_square (walk)", find_square, beam_probe(mem), reps)
        bench("find_square_bisect", find_square_bisect, beam_probe(mem), reps)
        print("  -- oracle: recovered formula")
        closed = formula_probe(*recover_constants(mem))
        bench("find_square (walk)", find_square, closed, reps)
        bench("find_square_bisect", find_square_bisect, closed, reps)


if __name__ == "__main__":
    main()
