# aoc2019_racket

> **The "racket" in the repo name is history, not the current language.**
> This repo began as the Racket leg of a four-language Advent of Code
> rotation. The rotation is over -- juggling several languages at once got in
> the way of the puzzles -- and **new work here is Python only**. The name
> stays so existing clones, links and remotes keep working.
>
> The Racket solutions for days 1-14 are **frozen**: still in the tree, still
> working, no longer extended. See [Frozen Racket](#frozen-racket) below.

Advent of Code 2019, solved in Python.

## Layout

| Path | What |
|------|------|
| `python/dayNN.py` | the solution for a day: `parse_input` / `part1` / `part2` / `solve` / `main` |
| `python/tests/` | one pytest module per solved day, plus `conftest.py` |
| `python/bench.py` | timing harness -- best and median ms per phase |
| `Problem_Statements/days/dayNN.md` | the official puzzle text, both parts |
| `Problem_Statements/days/dayNN_function_guide.md` | the day's function guide -- the durable artifact |
| `Problem_Statements/days/summary_2019.md` | per-day answers, timings and algorithm names |
| `inputs/dayNN.txt` | puzzle inputs -- **gitignored**, not republished |
| `src/`, `test/`, `bench/`, `scripts/`, `tutorial/` | frozen Racket (see below) |

`parse_input` does the *whole* parse -- not "split into lines" but all the way
to the structure the day actually reasons about (a dict of reactions, a list of
`(direction, length)` moves, a pair of bounds). Splitting lines and parsing them
later spreads one concern across three functions.

## Quick start (Windows)

A Windows virtualenv puts executables in `Scripts\`, not `bin/`:

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install pytest ruff
```

Then:

```
.venv\Scripts\python.exe -m pytest                 # the whole suite
.venv\Scripts\python.exe -m pytest -k day14        # one day
.venv\Scripts\python.exe python\day14.py           # run a day against its real input
.venv\Scripts\python.exe python\bench.py 14        # time one day
.venv\Scripts\ruff.exe format python\              # format (scoped to python/ only)
```

`pytest` needs no arguments and no `PYTHONPATH`: `pyproject.toml` sets
`testpaths = ["python/tests"]` and `pythonpath = ["python"]`, which is what
lets a test module say `import day03` with no package layout and no `sys.path`
juggling.

## Tests

Two fixtures in `python/tests/conftest.py` carry the policy:

- **`real_input`** loads `inputs/dayNN.txt` and **skips** when it is missing, so
  a fresh clone -- which has no inputs, since they are gitignored -- is green
  rather than red.
- **`check_locked`** compares a day's real-input answers against its `LOCKED`
  constant. When `LOCKED is None` it prints what the code currently produces
  and skips. An answer nobody has submitted to adventofcode.com can therefore
  never report a green pass.

Skip reasons are printed on every run (`addopts = "-rs"`), because both of
those signals are worthless if they scroll past silently.

## Benchmarks

`python/bench.py` reports **best and median** ms per phase over N repetitions
(default 7). Best-of-N rather than a single shot: most days here land between
0.1 ms and 100 ms, and at that scale the single-shot spread from the scheduler,
the allocator and frequency scaling is bigger than the differences being
measured. The best sample is the least polluted one; the median beside it says
how noisy the machine was. Far apart means don't trust the number.

## Frozen Racket

Days 1-14 were originally solved in Racket. That code is left exactly as it
was, and still runs:

```
raco test test\day14-test.rkt
racket bench\main.rkt
```

It is not maintained, not extended, and not kept in step with the Python. The
day 1-14 function guides in `Problem_Statements/days/` were written against it
and are accurate about it; guides from day 15 on are Python-first.
