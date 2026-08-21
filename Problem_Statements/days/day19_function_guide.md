# Day 19 — Tractor Beam (function guide)

> Code: [python/day19.py](../../python/day19.py). Tests:
> [python/tests/test_day19.py](../../python/tests/test_day19.py) (24 tests).
> Disassembly: [day19_disassembly.md](day19_disassembly.md) with tool
> [python/day19_disasm.py](../../python/day19_disasm.py).
> Statement: [day19.md](day19.md).
>
> **Answers: Part 1 = 209, Part 2 = 10450905** (the 100×100 square's
> top-left corner is (1045, 905)).

## The puzzle in one paragraph

The input is an Intcode program that answers exactly one question and
halts: *is the point (x, y) inside the tractor beam?* Feed it two inputs,
read one output bit, and the machine is dead — every further question
costs a fresh VM. Part 1 asks for a census: how many of the 2500 points
with 0 ≤ x, y < 50 are inside the beam? Part 2 asks for the 100×100
axis-aligned square closest to the emitter that fits entirely inside the
beam, answered as `10000 * x + y` of its top-left corner.

## The shape of the day: the VM is an oracle, and questions cost money

Every Intcode day since [Day 11](day11_function_guide.md) has changed
only the *peripheral* wired to opcodes 3 and 4 — the machine froze at
[Day 9](day09_function_guide.md). This day's peripheral is the most
degenerate one yet: a pure function `(x, y) -> bool`, delivered as a
program that cannot even be resumed. [Day 15](day15_function_guide.md)'s
droid was state you could only walk; Day 19's drone is the opposite
extreme, an oracle with no state at all.

That framing decides everything. The puzzle is not "run the machine" —
it is **how few questions can you get away with asking**. Part 1's 2500
questions are mandated by the statement. Part 2 naively wants a scan of
millions of points (the square lands around y ≈ 1000, so a bounding-box
scan is ~10⁶ probes at ~266 µs each — twenty minutes); the shipped
solution asks **2857**.

The other structural decision comes from the statement's worked example:
it ships a 10×10 *picture* of a beam and no program that draws it. So
everything after `beam_probe` takes a plain `probe(x, y) -> bool`
callable, and the Intcode program is just one way to manufacture a probe
— the same split that let [Day 17](day17_function_guide.md) test against
its ASCII pictures, and [Day 15](day15_function_guide.md) test a maze
with no droid. The tests drive the exact same search code with a probe
backed by the statement's picture, by a synthetic wedge, and by the real
machine.

## What the beam actually is: a cone with irrational edges

Scan the real input's 50×50 window and the shape declares itself:

```text
row  0:  #                          <- the emitter, alone
rows 1-3: (nothing)
row  4:  .....#                     <- the beam "restarts" at (5, 4)
row  8:  .........##
...
row 47:  ...(48 dots)...#           <- x=49: the left edge leaves the window
rows 48-49: (nothing again)
```

The beam is the set of lattice points between **two rays from the
origin**. On this input (the [disassembly](day19_disassembly.md)
recovers and verifies this) a point is lit iff

    |76·x² − 100·y²| ≤ 17·x·y

which is the region between rays of slope x/y ≈ 1.0407 and x/y ≈ 1.2644.
Three consequences the solution leans on, each pinned by a test rather
than assumed (`test_example_rows_are_single_runs_with_monotone_left_edge`,
`test_real_rows_are_single_runs_with_monotone_left_edge`,
`test_real_beam_starts_narrower_than_a_cell`):

1. **Each row is one contiguous run.** A row y intersects a convex cone
   in an interval.
2. **The left edge never moves left** as y grows: the run's start is
   `ceil(1.0407·y)` — nondecreasing.
3. **Near the origin the cone is thinner than the pixel grid.** Between
   the two rays a row holds ~0.22·y lattice points, so rows 1–3 hold
   *none* — the beam "restarts" at (5, 4). Row 0 is the special case the
   statement calls out: (0, 0) always reports 1, and the formula agrees
   (|0 − 0| ≤ 0). The 50-wide window also clips the cone at the bottom:
   rows 48–49 are empty again because the left edge passes x = 49 first.

Point 3 is why nothing in the solution may assume "every row has beam".
It is also the reason the classic follow-the-edge bug on this day is an
infinite loop: scan row 1 for its first lit cell and there is nothing to
find.

## Part 1: the census

`count_beam(probe, 50)` is 2500 probes, a full grid scan, because the
statement asks for exactly that. There is nothing to optimise legally —
the answer *is* a property of all 2500 points (though the closed form
makes each answer arithmetic; see the
[sidebar](#possible-optimization-fewer-questions-cheaper-questions)).
209 of them are lit.

## Part 2: ride the left edge, check two corners

```python
y = size - 1                        # the first row deep enough
x = left_edge(probe, y)
while not probe(x + size - 1, y - size + 1):
    y += 1
    x = left_edge(probe, y, x)      # resume the scan; never restart at 0
return x, y - size + 1
```

`(x, y)` is the candidate square's **bottom-left corner**, and it rides
the beam's left edge downward. Everything interesting is in why this
tiny loop is allowed to be this lazy:

* **Why only two corners?** The candidate square has its bottom-left
  corner *on* the left edge at row y, and we test only the top-right
  corner (x+99, y−99). Rows are contiguous runs, the left edge is
  nondecreasing in y, and the right edge is too. So: every row of the
  square starts at or left of x's row-start maximum, which is the
  *bottom* row — bottom-left lit pins the whole left column. Every row
  of the square ends at or right of the right edge's minimum, which is
  the *top* row — top-right lit pins the whole right column. Columns
  between are between. Two lit corners ⇒ 10,000 lit cells. The tests
  do not take the proof's word for it: the brute-force
  `first_fit_oracle` re-checks *every* cell on the example and on a
  synthetic wedge, and `test_real_square_is_lit_and_flush_left`
  samples the real square's interior.

* **Why is the left edge the only x worth trying?** Sliding the square
  right from the left edge can only hurt: the binding constraint on the
  left is the bottom row (already satisfied at the edge, with maximal
  slack), and the binding constraint on the right is the top row, which
  sliding right makes strictly worse. So per bottom-row there is exactly
  one candidate, and the first bottom-row that works gives the square
  nearest the emitter.

* **Why does resuming the scan lose nothing?** `left_edge(probe, y, x)`
  starts from the previous row's edge — legal because the edge never
  retreats (pinned at depth by `test_real_deep_left_edges_stay_monotone`).
  This is what makes the whole search O(rows + edge-drift) instead of
  O(rows × edge-position): across the entire run from row 99 to row
  1004, the x cursor advances 941 times total, not per-row.

* **Why start at row `size − 1`?** A 100-tall square's bottom edge
  cannot sit above row 99, and rows 1–3 are empty — `left_edge` on an
  empty row would scan forever, which is why it carries a slope tripwire
  (`x > 4y + 10 → ValueError`) instead of trust.

* **Why does it terminate?** The beam's width at row y is
  ~(1.2644 − 1.0407)·y ≈ 0.224·y, unbounded — and the fit condition
  needs width ≈ 100 across a 100-row band, which holds for all
  sufficiently large y. On this input the first fit is exact on *both*
  sides: at bottom row 1004 the square spans x = 1045..1144 and
  R(905) = 1144 — the top-right corner is the last lit cell of its row —
  while one row earlier the fit misses by one cell (L(1003)+99 = 1143 >
  R(904) = 1142). The puzzle constants were clearly tuned so that
  off-by-ones die loudly.

The walk asks 2857 questions: one corner probe per row (906), one
hit-confirmation per `left_edge` call (906), 941 cursor advances, plus
the 104 spent locating the edge on the first row.

## The Day 19 code, form by form

| function | role |
| --- | --- |
| `parse_input` | comma-split to `list[int]`; `.strip()` eats the CRLF |
| `beam_probe(program)` | wraps the program as `probe(x, y) -> bool`; fresh VM per call because the drone halts after one report; rejects negative coordinates (the statement: they "confuse the drone") |
| `count_beam(probe, size)` | Part 1's census, a generator-sum over the grid |
| `left_edge(probe, y, start)` | first lit x on row y scanning right from `start`, with the empty-row tripwire |
| `find_square(probe, size)` | the edge-riding walk above; returns the top-left corner |
| `part1` / `part2` / `solve` | assemble the above; `part2` encodes `10000x + y` |

One VM detail worth a sentence: `VM.__init__` copies the program into
its own `defaultdict`, so a thousand probes share one parsed list and
nothing mutates it (`test_probe_does_not_consume_the_program`). The days
that poke memory ([13](day13_function_guide.md),
[17](day17_function_guide.md)) mutate the *VM's* copy for the same
reason.

## The problem within the problem

The drone program does not trace rays or simulate physics — it
evaluates the quadratic form `|76x² − 100y²| ≤ 17xy` through four
subroutines' worth of deliberate obfuscation: a three-way product
disguised as a sorting recursion, an indirect-call trampoline that
patches its own jump target, constants mined out of the program's own
instruction operands, and an algebraic no-op that destroys the code
behind it as it runs. Recovering and verifying that formula — and both
answers, statically, with the VM never started — is the
[Day 19 disassembly guide](day19_disassembly.md)'s subject, continuing
the series from [Day 15](day15_disassembly.md) and
[Day 17](day17_disassembly.md).

## Possible optimization: fewer questions, cheaper questions

Not shipped — the shipping solution stays the oracle-honest walk — but
measured, because the machinery already exists in
[python/day19_disasm.py](../../python/day19_disasm.py):

* **Cheaper questions.** The recovered predicate turns a 266 µs probe
  into three multiplications. Same 2857-question walk, ~1 ms.
* **Fewer questions: none.** Both edges are exact ray intersections, so
  each row's run is computable outright: `left_edge(y)` is
  `ceil(y·(√30689 − 17)/152)` via `math.isqrt` plus a one-step fix-up,
  and likewise the right edge. Part 1 becomes 50 interval widths
  (measured **0.054 ms**), Part 2 a walk down two integer sequences
  (measured **0.994 ms**) — the pair about 1350× faster than the VM
  route, verified equal to it by the disasm tool's pass 5 and by
  `test_static_answers_match_the_live_machine`.
* **Input-agnostic middle ground.** Without reading the formula out of
  the file, the row-fit predicate is monotone in y once the beam is
  wider than the square, so binary search over y (probing `left_edge`
  fresh per query from a slope estimate) would cut the 906-row walk to
  ~10 rows — worth reaching for if the square landed at y ≈ 10⁵ instead
  of 10³. Untested sketch, filed in the
  [Day 14](day14_function_guide.md) tradition.

## Tests (what is pinned and why)

* **The statement's examples**: Part 1's 10×10 picture (27 lit) drives
  the census, the cone-shape pins (single runs, monotone left edge), and
  three square sizes against a brute-force first-fit oracle that checks
  every cell — the shortcuts (`two corners`, `left edge only`) validated
  against a search with none. Part Two's 40-wide picture lands its
  marked 10×10 square at (25, 20) through both the real search and the
  oracle, and encodes to the statement's 250020.
* **A synthetic wedge** (`5y ≤ 6x ≤ 9y`): the same oracle agreement at a
  size the example can't host (10×10), plus full-square litness and
  scan-resume equivalence for `left_edge`.
* **The machinery**: negative coordinates raise, a silent halt raises
  (a broken drone is not a 0), the empty-row tripwire fires, the program
  list survives probing.
* **The real input** (window probed once per module): row 0 = {0}, rows
  1–3 empty, rows 48–49 empty *again* (window clipping), single runs
  with monotone left edges in between; deep-row monotonicity at y = 100,
  200, 300; the found square fully-lit-sampled and flush against the
  edge — property-based, no answer values, because
  **`LOCKED` stays `None` until adventofcode.com accepts the answers**.
* **The disassembly**: recovered formula reproduces the VM's window
  exactly; disc = 30689 is not a perfect square (the rays never touch a
  lattice point, so the program's `≤` never actually ties away from the
  origin); the static isqrt edges flip exactly where the formula flips;
  both static answers equal both live answers.

## Benchmarks

`python\bench.py 19`, best/median ms over 7 reps:

| day | parse | part 1 | part 2 | total |
|----:|------:|-------:|-------:|------:|
| 19 | 0.037 / 0.041 | 666.348 / 688.885 | 758.484 / 770.004 | 1424.869 |

The cost model is pure interpretation, as on every Intcode day since
[15](day15_function_guide.md): Part 1 executes 796,366 VM instructions
across its 2500 probes (298–377 each) in 666 ms — **1.20 M instr/s**,
right at Day 15's measured 1.26 M — and Part 2's 2857 probes price out
identically. The *algorithm* on top of the oracle costs nothing
measurable; the closed-form sidebar shows the same answers for ~1 ms
total once the oracle itself is bypassed.

## If I were writing this in Rust

* `beam_probe` returns a closure; the Rust shape is a struct holding the
  parsed program plus `fn probe(&self, x: i64, y: i64) -> bool` — or
  `impl Fn(i64, i64) -> bool` if you enjoy fighting the borrow checker
  over the captured `Vec`. The per-probe VM would be
  `Intcode::new(&self.program)` cloning into a `Vec<i64>` arena instead
  of a hash map; at ~330 instructions per probe the interpreter
  overhead, not the copy, still dominates.
* The probe counts and the instr/s figure make this a fun benchmark
  target: a straightforward Rust Intcode VM runs ~100× the Python
  dispatch rate, pulling Part 1+2 under 15 ms with no algorithmic
  change — the language buys what the sidebar's closed form buys,
  without reading the input's constants.
* `left_edge`'s tripwire is where Rust's type system doesn't help: the
  bug it guards (an unbounded scan of an empty row) is a logic error,
  and you'd write the same `assert!(x <= 4 * y + 10)`.
* The quadratic form is i64-safe to y ≈ 10⁸ (100·y² < 2⁶³); Python's
  bignums never asked the question. `isqrt` on u64 is
  `integer_sqrt`-crate territory or four lines of Newton.

## What's next

Day 20 (Donut Maze) returns to grid search — BFS with portal edges, and
a recursive-depth twist that echoes [Day 18](day18_function_guide.md)'s
product-graph state. The remaining Intcode days are 21 (springscript),
23 (a 50-VM network), and 25 (the text adventure, for which
[intcode-disasm's](day19_disassembly.md#how-the-tool-fared) symbol file
already ships annotated).
