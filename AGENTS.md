# AGENTS.md -- AoC 2019 in Racket

This is **Matt LaDuke's** AoC 2019 / Racket repo, the second leg of
a planned four-language Advent of Code rotation. Use this file to
orient on conventions, working style, and cross-repo context before
helping on the first request of a new session.

## The four-language rotation

| Year | Language | Repo                  |
|-----:|----------|-----------------------|
| 2017 | Rust + Python side-by-side | `../rust_study/advent_of_code/aoc2017/` |
| 2018 | Haskell  | `../aoc2018_Haskell/` -- nearly complete, ~19/26 days done |
| 2019 | Racket   | **this repo**         |
| 2020 | Prolog   | (planned)             |
| 2021 | OCaml    | (planned)             |
| all other years | Rust | scattered |

**Why this rotation exists:** breadth-first language exposure --
"~1 month per language, 4 months total" -- not mastery of any one.
Matt learns for perspective and curiosity, not career; the *reading
fluency* across paradigms is the goal, not the ability to write
production Racket. **Do not suggest pausing or consolidating one
language before moving to the next.** If he says "I'm still lost
but committed to the plan", that is the literal truth -- read it,
honour it, do not propose an intervention.

## Project shape (planned, finalised on Tutorial Day 1)

The Racket repo will follow the same shape as `../aoc2018_Haskell/`:

```
aoc2019-racket/
  tutorial/
    day1/  day2/ ... day12/            -- 12-day Racket tutorial
  src/                                 -- (or equivalent Racket structure)
    day00.rkt .. day25.rkt
  test/                                -- RackUnit, one spec per day
  bench/                               -- 'time'-based bench harness
  Problem_Statements/days/
    dayNN.md                           -- official puzzle text, both parts
    dayNN_function_guide.md            -- the teaching artifact
    summary_2019.md                    -- per-day perf + answers table
  python/dayNN.py                      -- algorithm-flavored side-by-side
  reference/                           -- prior-year AoC 2019 Rust solutions,
                                          git-ignored, read-only style cues
  inputs/dayNN.txt                     -- puzzle inputs (gitignored content)
```

Toolchain choices to settle on Day 1 of the Racket tutorial:
- **Project layout**: single-file-per-day, or one `info.rkt`
  collection, or one Racket package per day. The Haskell project
  used a single cabal package; Racket has more options.
- **Type-discipline analogue of Haskell's signatures**: optional
  contracts via `contract-out`, or typed/racket. Pick early.
- **Test framework**: RackUnit (default).
- **Benchmark harness**: Racket's built-in `time` macro is the
  closest to criterion. No equivalent to criterion's mean/regression
  reporting; document the noise expectations differently.
- **REPL**: DrRacket or `racket -e` -- equivalent of GHCi for
  exploration.

Do **not** pre-decide these in this file; let Day 1 of the tutorial
work out what feels right.

## About the user

- **20+ year engineer.** Embedded / hardware roots (early-career
  PCB layout work). Senior-level depth -- write at that level, not
  introductory.
- **Rust is his anchor.** When explaining a Racket concept, find
  the Rust analogue if one exists -- it is the single highest-leverage
  comparison. (For functional concepts without a Rust analogue,
  reach for Haskell from the 2018 repo.)
- **Hobby projects in flight:**
  - Lox compiler in Rust (likely `clox` from Crafting Interpreters).
    Treat scanner/parser/bytecode VM/GC as shared vocabulary, not
    concepts to introduce.
  - Chess engines (MTLChess, Huginn, sayuri-r2018). Use chess
    analogies for search / ADT / bitboard topics where they fit.

## Working style

- **He writes nothing; I write the code, he reads.** This is the
  rate at which the language is allowed to click for him on a
  breadth-first plan. **Do not unprompted suggest "try writing this
  yourself"** or other write-drill exercises. If he asks for a
  pencil-and-paper exercise, deliver one -- otherwise the
  I-write-he-reads workflow is the agreed shape.

- **Language-first by default.** On the initial walkthrough of a
  day, focus on Racket mechanics: what does this form do, how does
  the macro/match/contract syntax read, what's the Rust analogue.

- **Algorithm-depth on demand.** When he steers algorithmic --
  "why does this work?", "can you prove it?", "could this be
  faster?" -- *follow him all the way down*. Proofs, helper
  scripts, plots, timings, formal complexity arguments. The raw
  answer is not the reward; the structure underneath is.

- **Name algorithms in canonical literature vocabulary.** "This is
  a topological sort." "That's an integral image / summed-area
  table." "The trick here is Floyd's cycle detection." The formal
  name is what makes the technique transferable to other puzzles
  and other languages.

- **When syntax frustrates him, pivot to algorithmic depth.** If
  he's stuck on a Racket-specific bit and says so, the move is not
  to drill the syntax -- it's to step back into the algorithm
  (visualisations, empirical questions, the canonical name). The
  reward for these puzzles is the structure, not the answer.

- **The "problem within the problem" lens.** AoC 2019 has its own
  VM-trilogy (Intcode). When a puzzle's prose hides a meta-problem
  (a real algorithm inside a brute-force scan, an obfuscated
  constant, an interpreter pattern), call it out and analyse it
  -- both Day 16 and Day 19 of the 2018 repo did this and the
  supplements are the most valuable parts of the guides.

## Per-day deliverable

Every solved day produces, at minimum:

1. **Source file** (`src/dayNN.rkt` or however Day 1 settles it)
   with explicit contracts (or type annotations) on top-level
   bindings, a `parse-input` / `part1` / `part2` / `solve` shape
   mirroring the Haskell repo's `parseInput` / `part1` / `part2` /
   `solve`. Idiomatic Racket -- not a transliteration of Haskell.
2. **Test file** (`test/dayNN-test.rkt`) pinning the puzzle's
   example AND the actual-input answer.
3. **Benchmark row** in `bench/main.rkt` (or however the harness
   lands), producing Parse / Part 1 / Part 2 timings.
4. **Function guide** at `Problem_Statements/days/dayNN_function_guide.md`.
5. **Python algorithm reference** at `python/dayNN.py` *for
   algorithm-flavored days*. Mechanics-flavored days stay
   language-first; algorithm-flavored days lead the function guide
   with a `## The algorithm in Python` section. (This convention
   started at AoC 2018 Day 12; keep it.)
6. **Summary table row** in `Problem_Statements/days/summary_2019.md`:
   `Day | Title | Parse | Part 1 | Part 2 | Total | Algorithm | Notes`
   where `Total = Parse + Part 1 + Part 2` (sum of means, **not**
   the "combined" bench, which double-counts allocation noise).

## Function guides are the durable artifact

The per-day function guides are the resource Matt plans to revisit
**next year and possibly later** when he chooses a deep Racket
dive. The code is the working example the guide annotates; the
guide is the deliverable.

- **Write every guide for a reader who is 12+ months cold.** Future
  Matt has forgotten which day introduced `match` patterns, what
  `for/fold` does, why `parameterize` exists. Restate or
  cross-link rather than assuming retention.
- **No per-day time pressure.** Quality of the guide > shipping
  cadence. A day where the code is correct but the guide is
  half-written is **not** a finished day. The bench row and
  summary entry can wait.
- **The "If I were writing this in Rust" section earns its keep.**
  Rust is Matt's anchor; a cold reread at +12 months is a Rust ->
  Racket re-translation. That section is the bridge.
- **Cross-link aggressively to other guides.** `[Day 12](day12_function_guide.md)`
  references make the guides navigable as a single resource.
- **The benchmark table is part of the guide.** Don't skip timings
  even on cheap days -- they're calibration data for the cold
  reader, and they reveal the algorithmic improvement at a glance.

## Optimisation policy: idiomatic in source, fast as sidebar

- **The shipping `src/dayNN.rkt` is idiomatic Racket.** Clear,
  readable, taking advantage of the language's strengths
  (pattern matching, tail recursion, sequences, contracts).
- **Faster algorithms live in a "Possible optimization" subsection
  of the function guide.** Untested pseudo-Racket is fine for these
  sidebars -- they document the technique without committing to the
  rewrite. Example: AoC 2018 Day 19's brute-force Part 1 simulator
  stayed in the source; the σ(N) closed form was sidebar'd.

## Tutorial style

The Racket tutorial runs 12 days (one longer than the 11-day
Haskell ramp). Each tutorial day produces a function guide of its
own at `tutorial/dayN/README.md` plus a small working example. The
Haskell tutorial's Day 1 README is the validated skeleton; reuse
its shape (problem framing -> approach -> code with annotations ->
key takeaways -> what's next). When in doubt, open
`../aoc2018_Haskell/tutorial/day1/README.md` and copy its
structure with Racket vocabulary swapped in.

## When asked to "walk through this"

Draft per-token tables in chat *and* offer to fold a tightened copy
into the day's function guide as a `### Token by token` subsection.
The chat version is the conversation; the guide version is the
durable artifact. The same pattern fits Racket's macro expansion --
"walk through the expansion" is a candidate for the same treatment.

## Cross-referencing AoC 2018 (Haskell)

When a Racket concept has a strong Haskell analogue, *do* reach
into `../aoc2018_Haskell/Problem_Statements/days/` for a side-by-side.
Examples:
- Racket `match` vs Haskell pattern matching (Day 4 / Day 13 / Day 16).
- Racket `for/fold` vs Haskell `foldl'` (Day 1 / Day 5).
- Racket `vector` mutable operations vs Haskell `STUArray` (Day 9 /
  Day 11 / Day 14).
- Racket `parameterize` and dynamic binding -- *no clean Haskell
  analogue*; explain on Racket's own terms with a Reader-monad sidebar.

The Haskell function guides have a `## If I were writing this in
Rust` section at the end of each day. Match that pattern in Racket
guides -- the Rust analogue is the high-leverage comparison even
when the Haskell precedent also exists.

## Anchor (memory infrastructure)

Memory infrastructure (MCP server, schema, CLI tooling for the
shared memory system) is maintained by **Anchor**, a separate
project Matt collaborates on. If a memory-system question comes up
("the memory got corrupted", "can we change the frontmatter
schema?"), surface it as "for Anchor" and don't propose deep
changes from an AoC session.

## What NOT to do

- **Don't** suggest "let's pause Racket and consolidate Haskell"
  even when he says he's lost.
- **Don't** suggest writing exercises unprompted.
- **Don't** rush a day to keep cadence -- the guide is what
  matters.
- **Don't** pre-emptively introduce concepts the day doesn't need
  ("let me show you continuations" / "since we're here, let me
  cover phases" / etc.). Introduce concepts when puzzles justify
  them, the way the 2018 repo introduced ST on Day 9 not Day 1.
- **Don't** swap the shipping source for a faster algorithm just
  because you can -- file it as a sidebar.
- **Don't** mention Anchor unless asked.

## What the first session will likely ask for

Day 1 of the Racket tutorial. Expect a request along the lines of
"set up the project skeleton and let's do day 1 of the Racket
tutorial". Be ready to:

1. Decide and document the toolchain (project layout, contracts vs
   typed/racket, RackUnit, bench harness).
2. Scaffold `tutorial/day1/` with the validated README skeleton
   from the Haskell tutorial Day 1.
3. Pick a small puzzle for tutorial day 1 -- a port of AoC 2018
   Day 0 (Inverse Captcha) or AoC 2017 Day 1 is the natural
   precedent. Matt did the same shape for the Haskell tutorial.
4. Write a function guide for it even though it is a tutorial day,
   not an AoC day. The guide habit starts on day 1.

The 12-day Racket tutorial begins 2026-05-20. AoC 2019 proper
begins 2026-06-01.
