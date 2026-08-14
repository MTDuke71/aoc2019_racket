r"""Timing harness: best and median milliseconds per phase.

    .venv\Scripts\python.exe python\bench.py            # every day with a module and an input
    .venv\Scripts\python.exe python\bench.py 12 14      # just those days
    .venv\Scripts\python.exe python\bench.py 3 -n 25    # 25 repetitions instead of 7

Why best-of-N and not a single shot: most days here land between 0.1 ms and
100 ms, and at the low end the run-to-run spread from the OS scheduler, the
allocator and CPU frequency scaling is larger than the differences you are
usually trying to measure. The BEST sample is the one least polluted by that
noise -- it is the closest thing to "how long the work actually takes" -- and
the MEDIAN next to it tells you how noisy the machine was while measuring. If
best and median are far apart, distrust the number and re-run on an idle box.

Each part is timed against a freshly parsed copy of the input, parsed OUTSIDE
the timed region, because the Intcode days mutate their program list in place.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import re
import statistics
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON_DIR = REPO_ROOT / "python"
INPUTS = REPO_ROOT / "inputs"

DEFAULT_REPS = 7
_PROBE = object()  # stand-in argument for the arity check below


def solved_days() -> list[int]:
    """Day numbers with a python/dayNN.py module (variants like day03a excluded)."""
    found = []
    for path in sorted(PYTHON_DIR.glob("day*.py")):
        m = re.fullmatch(r"day(\d{2})", path.stem)
        if m:
            found.append(int(m.group(1)))
    return found


def measure(fn, reps: int) -> tuple[float, float]:
    """Return (best_ms, median_ms) over `reps` calls of a zero-argument thunk."""
    samples = []
    for _ in range(reps):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000.0)
    return min(samples), statistics.median(samples)


def bench_day(day: int, reps: int) -> dict[str, tuple[float, float] | str]:
    """Time parse / part 1 / part 2 for one day.

    A phase that cannot be called as `f(parsed)` -- a day not yet converted to
    the uniform shape -- is reported rather than silently dropped.
    """
    path = INPUTS / f"day{day:02d}.txt"
    if not path.is_file():
        return {"note": f"inputs/day{day:02d}.txt absent"}

    module = importlib.import_module(f"day{day:02d}")
    text = path.read_text(encoding="utf-8")
    result: dict[str, tuple[float, float] | str] = {}

    result["parse"] = measure(lambda: module.parse_input(text), reps)

    for name, fn in (("part 1", getattr(module, "part1", None)), ("part 2", getattr(module, "part2", None))):
        if fn is None:
            result[name] = "missing"
            continue
        try:
            inspect.signature(fn).bind(_PROBE)
        except TypeError as exc:
            # A day not yet on the uniform f(parsed) shape -- reported, not
            # silently dropped, so the row cannot be mistaken for a fast one.
            result[name] = f"signature: {exc}"
            continue
        try:
            fn(module.parse_input(text))  # warm-up; also surfaces a broken part
        except Exception as exc:
            result[name] = f"{type(exc).__name__}: {exc}"
            continue

        samples = []
        for _ in range(reps):
            data = module.parse_input(text)  # parsed outside the timed region
            start = time.perf_counter()
            fn(data)
            samples.append((time.perf_counter() - start) * 1000.0)
        result[name] = (min(samples), statistics.median(samples))

    return result


def format_cell(value) -> str:
    if isinstance(value, tuple):
        best, median = value
        return f"{best:9.3f} {median:9.3f}"
    return f"{'--':>9} {'--':>9}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("days", nargs="*", type=int, help="day numbers (default: all solved)")
    parser.add_argument("-n", "--reps", type=int, default=DEFAULT_REPS, help="repetitions per phase")
    args = parser.parse_args()

    days = args.days or solved_days()
    print(f"best / median ms over {args.reps} repetitions\n")
    header = f"{'day':>3}  {'parse':>19}  {'part 1':>19}  {'part 2':>19}  {'total':>9}"
    print(header)
    print("-" * len(header))

    for day in days:
        row = bench_day(day, args.reps)
        if "note" in row:
            print(f"{day:>3}  {row['note']}")
            continue
        cells = [format_cell(row.get(phase)) for phase in ("parse", "part 1", "part 2")]
        bests = [
            row[phase][0] for phase in ("parse", "part 1", "part 2") if isinstance(row.get(phase), tuple)
        ]
        total = f"{sum(bests):9.3f}"
        print(f"{day:>3}  " + "  ".join(cells) + f"  {total}")
        for phase in ("part 1", "part 2"):
            if isinstance(row.get(phase), str):
                print(f"     {phase}: {row[phase]}")


if __name__ == "__main__":
    main()
