# Day 21 — Springdroid Adventure (function guide)

> Code: [python/day21.py](../../python/day21.py),
> [python/day21_synth.py](../../python/day21_synth.py) and
> [python/day21_disasm.py](../../python/day21_disasm.py). Tests:
> [python/tests/test_day21.py](../../python/tests/test_day21.py) (45 tests).
> Statement: [day21.md](day21.md). Disassembly:
> [day21_disassembly.md](day21_disassembly.md).
>
> **Answers: Part 1 = 19354392, Part 2 = 1139528802** (both verified on
> adventofcode.com; `LOCKED = (19354392, 1139528802)`).

## The puzzle in one paragraph

The Intcode machine — frozen since [Day 9](day09_function_guide.md) — boots
an ASCII console like [Day 17](day17_function_guide.md)'s, but this time the
console is an *assembler*: you type in a program written in **springscript**,
a three-opcode language (`AND`/`OR`/`NOT` over two writable Boolean
registers), and the machine runs it on a springdroid hopping across the
ship's damaged hull. Each tile, the droid re-runs your whole script against
sensor registers that report ground-or-hole at fixed distances ahead
(`A`–`D` when walking, `A`–`I` when running), and jumps iff the script
leaves `J` true. A jump always lands 4 tiles ahead. Cross the hull and the
machine prints the damage total — the answer; fall in and it prints an ASCII
rendering of your droid's last moments instead. Part 1 (`WALK`) and Part 2
(`RUN`) differ only in sensor range — and in how honest the hull is about
punishing a greedy jumper.

## The shape of the day: you program a program

Springscript has no branches, no loops, and both registers reset to false at
every tile. Denotationally that makes a script a **combinational circuit**:
the jump decision is a pure Boolean function of the current sensor window,
and nothing else. The droid is a **memoryless reactive policy** — it cannot
remember what it just crossed, count tiles, or plan past its sensor horizon.
So the day splits cleanly in two:

* **Choose a Boolean function** of the sensors that crosses the hull — the
  policy question.
* **Express it in the three-opcode ISA** within the droid's 15-instruction
  memory — the synthesis question.

The second question has a beautiful exact answer (see
[the sidebar below](#the-problem-within-the-problem-script-synthesis-as-bfs)),
because the space of register states is tiny once you view a register as a
truth table.

Everything above the machine is testable without it — the same split that
let [Day 17](day17_function_guide.md) test against its ASCII picture and
[Day 19](day19_function_guide.md) against a `probe(x, y)` callable.
`run_script` is a ten-line springscript interpreter, `run_droid` walks a
script across an ASCII hull row, and the statement's own death rendering
replays move for move: `NOT D J` on `#####.###########` walks one tile,
jumps, and dies on tile 5 = 1 + 4, which is what pins the jump length
(`test_suicide_program_replays_the_statement_rendering`).

## Part 1: jump iff a hole is coming and the landing is safe

A jump clears the 3 tiles between launch and landing, so there is never a
reason to jump before a hole is within 3 tiles — and never a survivable
jump onto a hole. That leaves one candidate policy:

```
J = not(A and B and C) and D          # a hole in the next 3, ground at 4
```

```
OR  A T      # T = A
AND B T      # T = A·B
AND C T      # T = A·B·C
NOT T J      # J = ¬(A·B·C)
AND D J      # J = ¬(A·B·C)·D
```

Five instructions of the fifteen — and five is *exactly* the cost of this
function: the synthesis BFS proves no 4-instruction script computes it
(`test_walk_function_takes_exactly_five_instructions`).

Is the policy *correct*? Not universally — and this is worth being precise
about, because the statement never promises it. It crosses every single-gap
hull (holes 1–3 wide, `test_part1_policy_crosses_walkable_hulls`), but
exhaustive search over synthetic hulls finds arrangements of *staggered*
holes where it jumps greedily onto a tile whose exits are both holes:
on `####.#.##.##` it dies on tile 6 while the hull is perfectly crossable
(`test_walk_policy_dies_where_the_guard_survives`). The machine accepting
the script is a fact about *this input's hull* — Part 1 hulls simply never
stagger holes that way. Part 2's do.

## Part 2: the same jump, with an exit check

`RUN` extends sight to 9 tiles and the hull starts using the trap above. The
fix is one conjunct: **never jump onto a tile you cannot leave**. After
landing on D, the droid either steps (needs `E`) or immediately jumps again
(needs `H` — tile D+4, D's own D):

```
J = not(A and B and C) and D and (E or H)
```

```
OR  E T      # T = E
OR  H T      # T = E∨H
AND D T      # T = D·(E∨H)
OR  A J      # J = A
AND B J      # J = A·B
AND C J      # J = A·B·C
NOT J J      # J = ¬(A·B·C)
AND T J      # J = ¬(A·B·C)·D·(E∨H)
```

Eight instructions. On the trap hull it waits one tile and re-aligns the
jump; on the real input it crosses and the machine pays out.

### The guard is still not a planner

The `(E or H)` conjunct checks *one step* past the landing site. Doom that
lies further out is invisible: exhaustive search finds hulls the guarded
policy still dies on while perfect planning crosses —

```
####.#.###.##.#      guard jumps 1→5 (H=9 is ground), but tile 5 is doomed;
                     planning walks 1→2→3, jumps 3→7→11, steps, jumps out
```

— and `test_run_policy_is_not_universal` pins it. Two structural facts frame
how good the policy actually is, both by exhaustion over every hull of the
form `####` + `{#,.}*` + `#`:

* below 15 tiles, the policy crosses **exactly** the hulls a planner can
  cross (`test_run_policy_is_complete_below_the_counterexample_length`) —
  the 15-tile counterexample is minimal for the family;
* "crossable at all" means the one-pass reachability DP (step +1 or jump +4
  over ground), which is the upper bound no memoryless policy is guaranteed
  to reach. The planner-vs-policy gap is the same distinction as
  lookahead-vs-evaluation in a chess engine: the circuit is a static
  evaluator, and some positions need search.

The [disassembly](day21_disassembly.md) later turned "a fact about the
input's hull" into a theorem: the machine stores its hull as 9-bit hazard
chunks with guaranteed footing between them, the 15-tile killer needs an
11-tile hazard span that encoding cannot express, and over the whole
512-chunk universe the guard crosses every chunk planning can cross
(`test_guard_is_complete_for_the_chunk_universe`). The puzzle's difficulty
is calibrated by its chunk width.

A 4-wide hole defeats *every* policy and every planner — the jump lands in
it (`test_four_wide_hole_is_impassable`) — so the statement's hull generator
is implicitly promising never to produce one.

## The problem within the problem: script synthesis as BFS

The quiet gem of the day. A springscript register, viewed denotationally, is
a **truth table** — for 4 sensors, a 16-bit integer; the machine state is
the pair (T, J); every instruction is a deterministic map state → state; and
"write the shortest script computing f" is literally a shortest-path
problem. [python/day21_synth.py](../../python/day21_synth.py) runs BFS from
(false, false), remembering the instruction that first reached each state,
and *emits a program* by walking the parent chain back.

For Part 1's function the whole universe collapses: within 4 instructions
only **6,924 distinct states** exist (out of 2³² conceivable pairs), none
carrying the target in J — and at depth 5 the search finds it. The first
script it emits is, character for character, the hand-written one above.
Minimality by exhaustion, in milliseconds, pinned as a test.

For Part 2's guard, two bounds:

* **Lower bound by counting, free of search.** A sensor's value can enter
  the registers only as some instruction's X operand, so a script computing
  a function must spend at least one instruction per *live* sensor. The
  guard depends on exactly six of the nine — {A, B, C, D, E, H}, computed
  from the truth table and pinned by
  `test_run_guard_reads_exactly_six_sensors` — so 6 is a floor.
* **Exhaustion to depth 7.** Over sources restricted to the six live sensors
  plus T and J, the BFS clears depth 7 with no hit
  (`python python/day21_synth.py deep`, ~35 s, measured this session):

  | depth | frontier | states seen |
  |------:|---------:|------------:|
  | 4 | 37,180 | 41,326 |
  | 5 | 331,914 | 373,240 |
  | 6 | 2,728,494 | 3,101,734 |
  | 7 | 20,812,420 | 23,914,154 |

  So **8 is minimal** in that source universe, and the shipping script
  spends exactly 8. One honest caveat: a hypothetical 7-instruction script
  that *reads a dead sensor* (F, G, I) on the way to a function independent
  of it lies outside the searched universe. Intuition says a wasted read
  can't help; the search doesn't prove it.

The state-dedup is the whole story of feasibility here: raw 7-instruction
scripts over 8 sources number 48⁷ ≈ 587 billion, but distinct *behaviors*
number 24 million — a 25,000-fold collapse, the same move as memoizing
positions instead of move sequences.

## The Day 21 code, form by form

### `parse_input`

The comma-split Intcode parse, CRLF-tolerant via `.strip()`. 2,050 cells —
second only to [Day 13](day13_function_guide.md)'s 2,640 among the year's
programs (Day 19's was 424).

### `run_script(script, sensors)`

The springscript interpreter: three opcodes, destination must be writable,
T and J start false, more than 15 instructions refused. It enforces what the
Intcode assembler enforces, so a script this accepts is a script the machine
accepts.

### `run_droid(hull, script, sight)`

The simulator: stand on `hull[pos]` (fall if it is not `#`), read the next
`sight` tiles into `A`… (past the string's right edge reads as ground — the
hull continues beyond the hazard section), evaluate, move +4 or +1. Returns
the fall index or `None`, which is what lets tests pin *where* a bad policy
dies, not just that it dies.

### `survey(program, script, command)`

Types the script plus `WALK`/`RUN` into the console and returns
`(transcript, damage)`: ASCII outputs decoded as text, and the single
out-of-range output — the damage total — if the droid crossed. On failure
`damage` is `None` and the transcript ends with the droid's last moments;
`part1`/`part2` raise with that transcript in the message, because it is
the only debugging channel the day offers.

## The real input, measured

* The success transcripts are terse: `Input instructions:`, `Walking...` /
  `Running...`, then the damage value — 33 ASCII characters and one big
  integer.
* The `WALK` survey executes **23,304 VM instructions**; `RUN` executes
  **558,647** — 24× as many, matching the 24× wall-clock ratio (19.3 ms vs
  464 ms) at the interpreter's usual **~1.2 M instructions/second**
  (unchanged since [Day 15](day15_function_guide.md)).
* Script length is a real cost inside the machine: the same RUN function
  expressed in 9 instructions instead of 8 costs 602,160 VM instructions —
  43,513 more, ≈ 36 ms — because the droid re-runs the whole script at
  every tile. Shorter circuits are literally faster surveys.
* The hull never appears in the transcript — the only glimpses the machine
  volunteers are the 17-tile windows in failure renderings. Running the
  statement's `NOT D J` suicide against the real machine reproduces the
  statement's example rendering *exactly*, hull line `#####.###########`
  included (`test_failed_survey_renders_the_last_moments`) — the example
  was evidently generated by this very console. The
  [disassembly](day21_disassembly.md) later recovered the hull whole from
  the program's own data cells (that hull line is cell 758's value 255,
  decoded), along with the damage formula — both answers now come off the
  disk with the VM never started.

## Possible optimization

Nothing algorithmic is on the table — the wall clock *is* the Intcode
simulation of the droid's run, and the answer requires running it. The one
lever the day exposes is measured above: dropping a single springscript
instruction from the RUN script saved 43,513 VM instructions (~36 ms),
because the droid re-runs the script at every tile — so minimal scripts
(5 and 8, both proven or bounded by the synthesizer) are also the fast
ones. Beyond that, only a faster VM would help; a compiled/JIT Intcode
interpreter is a repo-wide sidebar, not a Day 21 one.

## Tests (what is pinned and why)

* **The statement's examples**: `NOT A J` behavior; the three-hole detector
  program's full truth table; the `NOT D J` suicide replayed move-for-move
  against the statement's rendering (which pins jump = 4).
* **Scripts are circuits**: both shipping scripts checked against their
  intended functions on *every* sensor combination — 16 for WALK, 512 for
  RUN. Exhaustive truth-table equality is the cheapest strong test this
  repo has had all year.
* **Policy boundaries**, all found by exhaustive search over synthetic
  hulls, per the standing rule that identities live as tests: hulls where
  Part 1's policy needs Part 2's guard; the 15-tile hull proving the
  guarded policy is no planner; completeness of the guard below 15 tiles;
  the impassable 4-wide hole.
* **Synthesis**: 5 is exactly minimal for the WALK function; the RUN guard
  reads exactly six sensors (the counting floor of 6); the synthesizer's
  truth-table algebra cross-checked against the interpreter.
* **The machine**: a failing survey yields no damage and renders the last
  moments; CRLF fixtures; `check_locked` against the verified answers.
* **The disassembly** ([day21_disassembly.md](day21_disassembly.md)): both
  answers recovered statically from the hull cells on both users' files;
  the shared course profile; guard completeness over the 512-chunk
  universe; the four assembler diagnoses provoked live; the two-file diff
  fully classified (383 encoding-flip cells + 157 hull cells, nothing
  else).

## Benchmarks

`python\bench.py 21`, best / median ms over 7 reps:

| Day | Parse | Part 1 | Part 2 | Total |
|----:|------:|-------:|-------:|------:|
| 21 | 0.151 / 0.160 | 19.342 / 19.580 | 464.101 / 468.056 | 483.594 |

Part 2's 24× over Part 1 is pure VM instruction count (558,647 vs 23,304):
the RUN course is longer and every tile evaluates a longer script.

## If I were writing this in Rust

The truth-table representation is bitboard thinking, verbatim: a 4-sensor
function is a `u16`, a 6-sensor one a `u64`, and every springscript opcode
is a single bitwise op on whole tables — `AND X Y` is `y &= x` across all
16/64 assignments at once, the same data-parallel trick as computing knight
attacks for all squares in one shift-and-mask. The synthesis BFS state is a
`(u64, u64)` pair in an `FxHashSet`; the 24-million-state depth-7 frontier
that costs ~35 s and gigabytes in Python (each state a heap-allocated tuple
of arbitrary-precision ints) is a `Vec<(u64, u64)>` push-and-probe loop that
Rust would chew through in a couple of seconds flat — and depth 8, ~170M
states at 16 bytes each, would fit in ~3 GB and settle the dead-sensor
caveat outright. The interpreter side would be an
`enum Op { And, Or, Not }` with `match` — the `clox` scanner/dispatch
pattern at toy scale.

## What's next

[Day 22](day22_function_guide.md) — when it lands. On the Intcode side, the
springscript console joins Day 17's movement-routine console as a *program
accepting programs*; the year's remaining Intcode days (23, 25) wire the
same frozen VM to a network and to a text adventure. The hull-archaeology
idea (mapping the hull by deliberately crashing droids) died the honest
way: the [disassembly](day21_disassembly.md) read the whole hull straight
out of the file, no crashes required. The single-step Intcode debugger
remains the post-year capstone candidate.
