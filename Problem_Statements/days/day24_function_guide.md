# Day 24 — Planet of Discord (function guide)

> Code: [python/day24.py](../../python/day24.py). Tests:
> [python/tests/test_day24.py](../../python/tests/test_day24.py) (19 test
> functions, 31 parametrized cases). Statement: [day24.md](day24.md).
>
> **Answers: Part 1 = 28717468, Part 2 = 2014** (both verified on
> adventofcode.com; `LOCKED = (28717468, 2014)`).

## The puzzle in one paragraph

No Intcode. A 5×5 scan of bugs evolves by a Game-of-Life-style rule — a bug
survives with **exactly one** bug neighbour, an empty tile spawns with
**one or two** (B12/S1 in the birth/survival notation Life variants are
named in). Part 1 iterates the flat grid until any layout repeats and asks
for that layout's "biodiversity rating". Part 2 announces the board was
never flat: the centre tile *is* another 5×5 grid, the whole scan sits in
the centre of a larger one, and so on both ways forever; run 200 minutes on
the recursive board and count bugs. The two parts share one life rule and
differ **only in adjacency** — which is exactly how the code is factored.

## The representation is the answer

The statement defines biodiversity as: tile *i* in row-major order is worth
2^i, sum over bugs. Read that backwards: **the rating is the grid encoded
as a 25-bit integer**, bit *i* = tile *i*. So `parse_input` produces a
plain `int`, and that one decision collapses part 1's final step to
*nothing* — the first repeated state, as represented, already **is** the
answer. No encode function exists in the module because the statement wrote
it into the data model. (Pinned digit-for-digit: the example's repeated
layout parses to `32768 + 2097152 = 2129920`, the statement's own
arithmetic for the 16th and 22nd tiles.)

Everything downstream inherits the cheapness:

* a **neighbour count** is `(grid & NEIGHBOR_MASKS[i]).bit_count()` — one
  AND and a popcount against a precomputed per-tile mask;
* the statement's "tiles off the edge count as empty" needs no code at
  all — edge tiles simply get smaller masks (corners 2 bits, edges 3,
  interior 4; the 80-directed-adjacency census is pinned);
* "seen before" is integer set membership;
* equality of whole worlds (part 2's test against the statement's eleven
  depth grids) is `dict == dict` over ints.

This is the same move as [Day 8](day08_function_guide.md)'s flat-offset
image and [Day 22](day22_function_guide.md)'s two-coefficient shuffle:
find the representation the puzzle secretly commits to, then let the
answer fall out of it.

## Part 1: iterate to the first repeat — a ρ, not a loop

`part1` is the textbook first-revisit scan: remember every state in a set,
step until membership fires, return the state. The vocabulary worth having
is **Floyd's ρ**: a deterministic map iterated from a seed traces a tail of
length μ into a cycle of length λ, and the first repeated state is the
**cycle's entry point**, seen at minute μ and again at minute μ + λ.
Measured and pinned for both inputs:

| trajectory | tail μ | cycle λ | first repeat at | entry state |
|---|---|---|---|---|
| statement example | 74 | 12 | minute 86 | 2129920 |
| real scan | 13 | 6 | minute 19 | **28717468** |

Two structural notes, both pinned as tests:

* **μ > 0, so this map is not invertible.** [Day 12](day12_function_guide.md)
  proved the opposite for its physics — the symplectic step had an explicit
  inverse, so the first repeat *had* to be the initial state and no ρ-tail
  could exist. B12/S1 has no inverse, and the real trajectory exhibits the
  consequence concretely: the cycle entry has **two distinct
  predecessors** — minute 12 (on the tail) and minute 18 (on the cycle) are
  different layouts with the same successor
  (`test_real_trajectory_is_rho_shaped` pins the pair).
* **No operator shortcut exists.** Days [12](day12_function_guide.md),
  [16](day16_function_guide.md) and [22](day22_function_guide.md) all
  collapsed "apply this k times" by composing the operator instead — lcm,
  binomials, an affine power. That trilogy's precondition was *linearity*,
  and this rule fails it: `step` is not additive over GF(2). The pinned
  counterexample is two bugs on tiles 0 and 2 — tile 1 sees two bugs and
  spawns, but it also spawns in *each* singleton run (one bug seen), so
  XORing the separate runs cancels the spawn: `step(a^b) = 170` vs
  `step(a)^step(b) = 168`. Thresholds don't superpose; simulation is the
  honest route, and at 19 minutes it is also a free one.

The state space is 2^25 = 33,554,432 layouts and the real trajectory
visits **19** distinct ones before minute 19 revisits the thirteenth.
Brent's or Floyd's constant-memory cycle detection is the classical
alternative to the seen-set; at 19 states
the set costs nothing and returns the entry state directly, which the
two-pointer tricks would make you re-derive.

## Part 2: same rule, new adjacency

The recursion sounds exotic and compiles to something small: **only the
neighbour function changes.** `RECURSIVE_NEIGHBORS[i]` maps each tile to
`(level delta, tile)` pairs, re-deriving the flat mask with two portal
cases spliced in:

* **off the outer edge** → *one* tile of the enclosing level: the tile on
  the corresponding side of *its* centre (walk up off the top row of level
  d and you stand on tile 8 of level d−1);
* **onto the centre** → *five* tiles of the inner level: the whole edge
  row/column facing the direction moved (walk right into the centre and
  you border the entire left column of level d+1);
* everything else is the flat neighbour at delta 0.

The statement's six worked adjacencies (tiles 19, G, D, E, 14, N) are each
pinned against this table, and so is its worked example: the same initial
scan run ten recursive minutes gives **99 bugs across depths −5..5**, all
eleven printed depth grids matching verbatim.

> **A restored line in day24.md.** The Part Two paste lost the bottom row
> of the "Depth 1" grid (four rows where every other depth has five). The
> `#####` now in the file is *this repo's verified simulation output* — the
> other ten grids reproduce character-for-character and the total is the
> statement's 99, so the eleventh grid's missing row is recovered rather
> than recalled. `test_statement_recursive_example` is the pin, and the
> test module's docstring records the provenance.

State is a dict `level → 25-bit mask`, empty levels never stored — the
sparse-world bookkeeping of [Day 3](day03_function_guide.md)'s wires and
[Day 11](day11_function_guide.md)'s hull, with an int per key instead of a
point set. One minute scans `[min−1, max+1]`: a wholly empty level's only
occupiable tiles are fed through a portal, so nothing further out can
spawn. That is also a theorem about speed — **the infestation advances at
most one level per minute** — pinned over the example's ten minutes
(depths exactly −5..5 at minute 10).

Contrast with [Day 20](day20_function_guide.md), the year's other
recursive-levels puzzle: there the level was a *counter carried by one
walker* (a single token's depth in a one-counter system), so state was one
integer per search node. Here every level holds live state simultaneously
and the dynamics couple adjacent levels both ways — the recursion is the
*board*, not the path.

## The problem within the problem: the board is a tube

Strip away the fractal framing and look at the graph the adjacency table
actually builds. Each level contributes 24 usable tiles (the 5×5 minus its
centre, which is "really" the next level) — a **square annulus**. Levels
stack bi-infinitely, and each junction between adjacent annuli carries
**exactly 20 edges**, counted from both sides (pinned in
`test_recursive_adjacency_shape`):

* from outside going in: 4 corner tiles × 2 crossings + 12 edge tiles × 1
  = 20;
* from inside going out: 4 portal-ring tiles × 5 fan-out = 20.

So the recursive board is not a plane and not a tree — it is an **infinite
tube of 24-tile rings**, each ring internally wired with 36 of its flat 40
edges (4 led to the centre and became the junction), each junction a
20-edge bottleneck where degree redistributes: twenty tiles per level keep
degree 4, and the four tiles ringing the centre carry degree 8 (three flat
neighbours plus a whole inner edge).

The tube picture makes part 2's dynamics predictable before running them:
population per level is capped at 24, the frontier moves at ≤ 1
level/minute, so **bug count grows at most linearly**, bounded by
24·(2t+1). Measured on the real input:

| minute | bugs | occupied depths | non-empty levels | densest level |
|---|---|---|---|---|
| 10 | 107 | −5..5 | 10 | 15/24 |
| 50 | 452 | −25..25 | 50 | 15/24 |
| 100 | 1009 | −50..50 | 101 | 19/24 |
| 150 | 1545 | −75..75 | 149 | 23/24 |
| 200 | **2014** | −100..100 | 200 | 18/24 |

The frontier runs at exactly its speed limit (depth ±t throughout), growth
settles to ~10 bugs/minute ((2014 − 107)/190 = 10.0), and the answer sits
at 20.9% of the 9,624-tile geometric ceiling — an average density of ~10
bugs per level, 42% of an annulus. Two of the row's oddities are worth a
second look: already at minute 10 one in-range level is bug-free (the example, by
contrast, fills all eleven), and at minute 200 level **−84** is
momentarily empty while its neighbours hold 6 and 12 bugs — interior
levels can locally go extinct while the frontier marches on,
which is why the code prunes empty masks instead of assuming a solid
interval. (Full extinction is handled too: the empty board is a fixed
point at every layer of the API, `test_extinction_is_a_fixed_point`.)

## The Day 24 code, form by form

### `parse_input(text) -> int`

Strips each line (the CRLF guard), validates the 5×5 shape and the
`#`/`.` alphabet loudly, and ORs bit `row*5+col` per bug. The returned int
is simultaneously the state, the set-membership key, and part 1's answer
format.

### `render(grid) -> str`

The exact inverse, for tests and eyeballs; round-tripped on three example
layouts.

### `NEIGHBOR_MASKS` / `step(grid)`

The flat adjacency as 25 bitmasks, built once at import. `step` is
count-then-update: popcount the masked neighbours of every tile, then
`bugs == 1 or (bugs == 2 and empty)` — one expression carrying both rule
clauses. The statement's four worked minutes are each pinned as a single
`step` transition.

### `part1(grid)`

Seen-set first-revisit scan. Returns the repeated state itself — see
[the representation section](#the-representation-is-the-answer).

### `RECURSIVE_NEIGHBORS` / `step_recursive(levels)`

The recursive adjacency table (tuples of `(delta, tile)`; the centre maps
to the empty tuple, so it can never spawn — pinned), and the same
count-then-update sweep over `[min−1, max+1]`, building a fresh pruned
dict. Guarded for the empty dict so extinction is a fixed point rather
than a `min()` crash.

### `part2(grid, minutes=200)`

Seeds level 0, refuses a scan with a centre bug (the centre *is* the inner
grid), steps 200 times, sums popcounts.

### `solve` / `main`

Both parts off one parse; parts read the parsed int by value, so there is
no shared-mutation hazard to manage ([Day 22](day22_function_guide.md)'s
situation, not the Intcode days').

## The real input, measured

* **Initial scan:** 12 bugs, biodiversity 22372462 as parsed.
* **Part 1 trajectory:** tail 13, cycle 6, first repeat at minute 19 —
  19 distinct layouts out of a 2^25 = 33.6 M state space.
* **Part 2 at minute 200:** 2014 bugs over depths −100..100, 200 of 201
  levels non-empty (−84 empty at that instant), mean ~10 bugs/level.
* **Work done:** stepping `[min−1, max+1]` for 200 minutes evaluates
  Σ(2t+3) = 40,400 level-minutes ≈ 1.01 M tile updates in 289 ms — about
  290 ns per tile update, all of it Python-level dict lookups, shifts and
  popcounts.

## Possible optimization

Not needed at 0.29 s, so both live here as sidebars in the usual way
(untested pseudo-Python documenting the technique):

**Bit-parallel neighbour counting (SWAR).** The per-tile loop is the whole
cost, and Life implementations classically delete it: shift the board four
ways and add the four one-bit planes with half-adders, giving "exactly
one" and "exactly two" as bitmask expressions evaluated for all 25 tiles
at once.

```python
RIGHT = 0b01111_01111_01111_01111_01111  # tiles with an in-grid right neighbour
N, S = grid >> 5, (grid << 5) & ALL25
W, E = (grid & RIGHT) << 1, (grid >> 1) & RIGHT
ones = twos = fours = 0               # a 3-plane bit-sliced counter, 0..7
for plane in (N, S, W, E):
    c1 = ones & plane                 # carry out of the ones place
    ones ^= plane
    fours |= twos & c1                # carry out of the twos place
    twos ^= c1
exactly1 = ones & ~twos & ~fours
exactly2 = twos & ~ones & ~fours
new = (exactly1 | (exactly2 & ~grid)) & ~CENTER_BIT
```

Three planes count to 7, which covers the flat board (max 4) and almost
all of part 2 — the four degree-8 portal tiles can see 8, so give them a
scalar epilogue (there are only four) or a fourth plane. Cross-level
contributions bolt on as extra planes in the same loop: the outer level's
four portal bits broadcast into edge masks, and the inner level's edge
popcounts feed the portal tiles. This turns a 25-iteration Python loop
into a dozen int ops per level.

**Memoized level transitions.** A level's next mask depends on exactly
`(outer's 4 portal bits, own 25 bits, inner's 16 edge bits)` — a
hashable triple. A `dict` cache in front of the per-level computation
would trade memory for repeat hits; hit rate unmeasured, hence the
sidebar.

## Tests (what is pinned and why)

* **The four worked minutes** of the flat example, each as one `step`
  transition, plus the first-repeat layout `== 2129920 == 32768 + 2097152`
  — the statement's arithmetic reproduced digit for digit.
* **Flat adjacency census**: corner/edge/interior mask sizes 2/3/4, no
  self-neighbours, symmetry.
* **The six worked recursive adjacencies** (19, G, D, E, 14, N) against
  `RECURSIVE_NEIGHBORS`, with the letter/number levels mapped explicitly;
  tile N's "five tiles within the sub-grid" checked as *exactly five inner
  pairs* without asserting which, since the statement doesn't.
* **Recursive adjacency structure**: every non-centre tile has 4 or 8
  neighbours, cross-level symmetry, the 20/72/20 delta census, degrees
  [4]×20 + [8]×4 — the tube section's numbers are this test.
* **The full ten-minute recursive example**: 99 bugs, all eleven depth
  grids verbatim (including the restored Depth 1 row), and
  `part2(..., minutes=10)` agreeing.
* **Frontier speed**: depth extent ≤ ±minute for each of the first ten
  minutes, landing exactly on −5..5.
* **The centre invariant**: never infested across the example run, empty
  neighbour tuple, and `part2` refusing a centre-bug scan.
* **ρ structure of both trajectories** (μ, λ, first-repeat minute), the
  entry state equalling the locked part 1 answer, and the two-predecessor
  witness that the map is not injective.
* **GF(2) nonlinearity** — the 170-vs-168 counterexample that closes the
  door on operator composition.
* **Extinction as a fixed point** at every API layer.
* **CRLF** twice: constructed `\r\n` example, and the real file against
  its LF-normalized self.
* **`check_locked`** against `LOCKED = (28717468, 2014)`, locked only
  after adventofcode.com accepted each.

## Benchmarks

`python python/bench.py 24`, best/median ms:

| phase | best | median |
|---|---|---|
| parse | 0.003 | 0.003 |
| part 1 | 0.038 | 0.039 |
| part 2 | 289.256 | 291.385 |
| **total** | **289.297** | |

Part 1's 19 flat steps cost 2 µs each. Part 2 is 7,600× part 1 for 10.5×
the steps because the board is ~200× wider: ~1.01 M tile updates at ~290
ns apiece, a pure interpreter-loop cost with no algorithmic content — the
sidebar's SWAR rewrite attacks exactly and only that constant.

## If I were writing this in Rust

The representation ports better than the Python: a level is a `u32`
bitboard, popcount is the `count_ones()` intrinsic (one instruction on
anything modern), and the mask tables are `const` — buildable in a
`const fn` at compile time, so the adjacency is baked into the binary.
The dict of levels dissolves into a fixed array: 200 minutes reach at most
±200, so `[u32; 403]` indexed by `depth + 201` replaces every
`levels.get(depth + dd, 0)` hash lookup with an add and a load, and the
double-buffered step is two such arrays swapped by reference. Nothing
allocates after startup. The per-tile inner loop that costs Python ~290 ns
per tile — boxed-int shifts, dict probes, a generator into `sum` — becomes
a handful of register ops, and the SWAR formulation above is where the
`u32` representation stops being an optimization and starts being the
idiom: Rust Life implementations write the half-adder planes as a matter
of course. The one genuinely Rusty design question is the neighbour
table's type: Python's ragged tuples of `(delta, tile)` want to become
something flat — say a `[(i8, u8); 8]` padded with sentinels, or three
separate `u32` mask tables (same-level, outer, inner-edge) so the counts
come from masked popcounts instead of pair iteration, which is the shape
the SWAR step wants anyway.

## What's next

[Day 25](day25_function_guide.md) — when it lands. The year's last day,
and per the running structure of 2019, the frozen VM's final outing:
[Day 21](day21_function_guide.md) and [Day 23](day23_function_guide.md)
wired it to a survey droid and a network; Day 25 wires it to a text
adventure. Today was the year's last non-Intcode day — a Game of Life
with a twist that turned out to be an adjacency table, closing the same
loop [Day 20](day20_function_guide.md) opened: recursion as a *place* you
can be, rather than a thing code does.
