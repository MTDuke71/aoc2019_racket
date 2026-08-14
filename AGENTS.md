# AGENTS.md -- AoC 2019 (Python)

This is **Matt LaDuke's** Advent of Code 2019 repo. Read this before the
first request of a new session.

## The direction of this repo

**Advent of Code is the point. The language rotation is over.** This repo
began as the Racket leg of a planned four-language rotation (2017 Rust,
2018 Haskell, 2019 Racket, 2020 Prolog, 2021 OCaml); juggling several
languages at once was not working, and the plan is retired. It did not
fail for lack of commitment -- do not propose reviving it, and do not
propose "one more language after this one".

**New work here is Python only.**

The repo is still named `aoc2019_racket` and the remote still points at
that name. The name is history; the README says so at the top. Do not
propose renaming it.

## Frozen Racket -- leave it alone

Days 1-14 were solved in Racket. That code is **frozen, not deleted**:

- `src/*.rkt`, `test/*-test.rkt`, `bench/main.rkt`, `scripts/*.rkt`,
  `tutorial/day1`..`day12` stay in the tree and stay working.
- **Do not add new Racket.** Not a new day, not a helper, not a tweak to
  an existing file.
- **Do not offer to port Python solutions back to Racket**, and do not
  offer to "keep the two in sync". They are not in sync and will not be.
- **Do not let tooling reach it.** `pyproject.toml` restricts ruff's
  `include` to `python/**/*.py` for exactly this reason. If a tool needs
  a path list, scope it to `python/`.
- Fixing a *Python* bug is normal work. Fixing a Racket one is not --
  frozen means frozen, even when the fix is obvious.

The days 1-14 function guides were written against the Racket code and
are accurate about it. They stay as they are.

## Environment: Windows, not WSL

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install pytest ruff
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe python\bench.py 14
.venv\Scripts\ruff.exe format python\
```

A Windows virtualenv puts executables in `Scripts\`, not `bin/`. `.venv/`,
`.pytest_cache/` and `.ruff_cache/` are gitignored.

**Inputs downloaded on Windows are CRLF.** Every `parse_input` must
tolerate a trailing `\r` -- per-line `.strip()`, or `.splitlines()`, both
handle it -- and every day's test module should carry a CRLF case. Note
that `Path.read_text()` opens in universal-newline mode and *rewrites*
`\r\n` to `\n`, so a CRLF test that loads its fixture that way is
asserting nothing; `conftest.py`'s `real_input` uses
`open(..., newline="")` deliberately.

## Per-day deliverable

1. **`python/dayNN.py`** exposing `parse_input` / `part1` / `part2` /
   `solve` / `main`. `parse_input` does the **full** parse -- all the way
   to the structure the day reasons about, not just a line split.
   Splitting lines and finishing the parse inside `part1` spreads one
   concern across three functions.
2. **`python/tests/test_dayNN.py`**: the statement's worked examples plus
   the edge cases they imply, via `@pytest.mark.parametrize`; a CRLF
   case; and `check_locked` against the real input.
3. **Function guide** at `Problem_Statements/days/dayNN_function_guide.md`.
4. **Bench row** -- `python/bench.py NN` -- folded into the guide.
5. **Summary row** in `Problem_Statements/days/summary_2019.md`.

Days 1-14 already have Python solutions (originally written as algorithm
companions to the Racket). They are converted to the full shape lazily --
when something touches them -- not in a big-bang pass.

## The test platform

`pyproject.toml` sets `testpaths = ["python/tests"]` and
`pythonpath = ["python"]`; the latter is what lets a test say
`import day03` with no package layout, no `__init__.py`, and no
`sys.path` juggling. Bare `pytest` runs everything.

Two fixtures in `python/tests/conftest.py`:

- **`real_input(day)`** -- skips when `inputs/dayNN.txt` is missing.
  Inputs are gitignored, so a fresh clone has none; it must stay green.
- **`check_locked(day, LOCKED)`** -- asserts the real-input answers
  against the day's `LOCKED` constant, and when `LOCKED is None` reports
  what the code currently produces and skips. **An unsubmitted answer
  must never report a green pass.** Lock a value only after
  adventofcode.com accepts it.

`addopts = "-rs"` prints every skip reason, because both fixtures signal
through skips.

`python/bench.py` reports **best and median** ms per phase over N reps.
Best-of-N, not one shot: at sub-millisecond scale the single-shot spread
exceeds the differences being measured.

## Two standing rules for guides

1. **If a solution leans on a non-obvious identity or shortcut, pin it as
   a test -- do not merely assert it in prose.** "Naive rounding overpays
   by 47.9%", "the three axes never interact", "the step map is
   invertible so there is no rho-tail": each of those is a claim, and a
   claim no test checks is a claim that can rot. Write the test, then
   cite it from the guide.
2. **Anything stated as fact gets run and verified, never recalled.** A
   timing, a language behaviour, an arithmetic claim, an answer, what a
   statement's example returns -- run it, or read it out of the file, and
   quote the real output. If it cannot be verified, say so in the guide
   rather than asserting it.

## Function guides are the durable artifact

The guides are the resource Matt plans to revisit next year and later.
The code is the working example the guide annotates.

- **Write for a reader who is 12+ months cold.** Restate or cross-link
  rather than assuming retention.
- **No per-day time pressure.** A day whose code is correct but whose
  guide is half-written is **not** a finished day.
- **Cross-link aggressively** -- `[Day 12](day12_function_guide.md)` --
  so the guides read as one navigable resource.
- **The benchmark table is part of the guide**, even on cheap days: it is
  calibration data for the cold reader and it shows the algorithmic
  improvement at a glance.
- An **"If I were writing this in Rust"** section is welcome where it
  illuminates -- Rust is Matt's anchor and the comparison is high
  leverage. It is an explanatory device, not an invitation to port.

## About the user

- **20+ year engineer.** Embedded / hardware roots (early-career PCB
  layout). Senior-level depth -- write at that level, not introductory.
- **Rust is his anchor.** Reach for the Rust analogue when explaining an
  unfamiliar idea.
- **Hobby projects in flight:** a Lox compiler in Rust (`clox`, Crafting
  Interpreters) -- scanner/parser/bytecode VM/GC are shared vocabulary,
  not concepts to introduce -- and chess engines (MTLChess, Huginn,
  sayuri-r2018), good for search / ADT / bitboard analogies.

## Working style

- **He writes nothing; I write the code, he reads.** **Do not suggest
  "try writing this yourself"** or other write-drills unprompted. If he
  asks for a pencil-and-paper exercise, deliver one.
- **Algorithm-first now that the language is settled.** Python is not the
  subject; the puzzle is. Lead with the structure -- what the data really
  is, what the invariant is, why the loop terminates -- and mention
  Python mechanics when a day genuinely turns on one (a `dict` default, a
  generator's laziness, `math.lcm`).
- **Algorithm-depth on demand.** When he steers algorithmic -- "why does
  this work?", "can you prove it?", "could this be faster?" -- *follow
  him all the way down*. Proofs, helper scripts, plots, timings, formal
  complexity arguments. The raw answer is not the reward; the structure
  underneath is.
- **Name algorithms in canonical literature vocabulary.** "This is a
  topological sort." "That's an integral image / summed-area table."
  "The trick here is Floyd's cycle detection." The formal name is what
  makes the technique transferable.
- **The "problem within the problem" lens.** AoC 2019 has its Intcode
  trilogy, and several days hide a real algorithm inside a brute-force
  scan or an obfuscated constant. When a puzzle does that, call it out
  and analyse it -- those supplements are the most valuable parts of the
  guides.

## Optimisation policy: idiomatic in source, fast as sidebar

- **The shipping `python/dayNN.py` is idiomatic, readable Python.**
- **Faster algorithms live in a "Possible optimization" subsection of the
  function guide.** Untested pseudo-Python is fine there -- it documents
  the technique without committing to the rewrite. Precedent: Day 14's LP
  relaxation, Day 2's affine closed form.
- **Don't swap the shipping solution for a faster algorithm just because
  you can** -- file it as a sidebar.

## Anchor (memory infrastructure)

Memory infrastructure (MCP server, schema, CLI tooling for the shared
memory system) is maintained by **Anchor**, a separate project Matt
collaborates on. If a memory-system question comes up, surface it as
"for Anchor" and don't propose deep changes from an AoC session. Don't
mention Anchor unless asked.

## What NOT to do

- **Don't** write new Racket, or offer to port Python back to it.
- **Don't** propose reviving the language rotation, or renaming the repo.
- **Don't** rush a day to keep cadence -- the guide is what matters.
- **Don't** state a timing, an answer, or a language behaviour from
  memory. Run it.
- **Don't** leave a non-obvious identity as prose when it could be a test.
- **Don't** lock an answer that has not been accepted by the site.
