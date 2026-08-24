# Day 20 — Donut Maze (function guide)

> Code: [python/day20.py](../../python/day20.py). Tests:
> [python/tests/test_day20.py](../../python/tests/test_day20.py) (18 tests).
> Statement: [day20.md](day20.md), both parts.
>
> **Answers: Part 1 = 442, Part 2 = 5208** (both verified on
> adventofcode.com; `LOCKED = (442, 5208)`).

## The puzzle in one paragraph

The input is a 109×109 character picture of a donut-shaped maze: walls,
corridors, and two-letter labels stuck to the outer rim and to the hole in
the middle. Each label names a pair of portals — stand on one, and a
single step teleports you to the other — except `AA` and `ZZ`, which mark
the start and end tiles. Part 1 asks for the shortest walk from `AA` to
`ZZ`. Part 2 re-reads the same picture *recursively*: stepping through an
**inner** portal descends into a nested copy of the whole maze, an
**outer** portal climbs back out one level, outer portals on the outermost
level are walls, and only the outermost `ZZ` counts. Same picture, same
question, different world.

## The shape of the day: one BFS, two graphs

Every edge in this puzzle costs exactly one step — a walking move and a
portal transit are both "a single step" in the statement's words — so
breadth-first search is exact and nothing fancier is ever needed. The two
parts differ only in what graph the BFS runs on:

* **Part 1** runs on the tiles. A portal tile simply has a *fifth
  neighbour* — its twin. Once the parse has paired the labels up, the
  portals stop being interesting.
* **Part 2** runs on states `(tile, level)`. A warp now carries a level
  delta — `+1` through an inner portal, `−1` through an outer one — and
  two rules key on the level: outer portals are walls at level 0, and
  `ZZ` accepts only at level 0.

This is the same move [Day 18](day18_function_guide.md) made: when a rule
makes "where am I" insufficient to know what you may do next, the missing
fact joins the state and the search runs on the **product graph**. Day
18's product was position × 2^26 key subsets — a subset lattice. Day 20's
is position × ℕ — a single unary counter. The counter version is far
tamer: the optimal walk here explores 82,724 states, against a 2^26
ceiling per position on Day 18.

One structural difference from every earlier maze day: the graph is not
planar-in-spirit anymore. [Day 15](day15_function_guide.md)'s maze was a
perfect tree, Day 18's had exactly 4 cycles; Day 20's warps are wormholes
that make distant tiles adjacent, which is precisely why no geometric
intuition ("it's on the other side of the map, it must be far") survives.

## Parsing: the labels are geometry

All of the day's fussiness lives in `parse_input`; both solvers together
are ~30 lines. Three details carry it:

* **A label is two letters read left-to-right or top-to-bottom.** The
  scan visits every letter and checks its right and down neighbours; the
  second letter of a pair can never *start* a label, because the cell
  after it is floor, wall, or void — so each pair is found exactly once,
  with its letters already in reading order. The portal tile is whichever
  end of the three-in-a-row (`.XX` or `XX.`, vertically likewise) is an
  open tile — exactly one is, and the parse raises if not.
* **Outer vs inner is a bounding-box test.** The corridor pokes through
  the rim wall only at portals, so an outer portal tile sits exactly on
  the bounding box of all open tiles (x or y ∈ {2, 106} here); inner
  tiles sit strictly inside. There is no need to find the hole.
* **Leading spaces are load-bearing.** A label's meaning *is* its
  coordinates, so lines must never be `.strip()`ed — `splitlines()` alone
  is the CRLF guard (it eats `\r\n` as one break and leaves the leading
  spaces alone). This is the one day where the usual per-line strip
  would be an outright bug rather than a harmless habit.

The classification is the kind of claim that usually rots in prose, and
the statement — unusually — hands us the pin: it narrates its 23-step
example *leg by leg* ("walk from `AA` to the **inner** `BC` portal (4
steps)… warp… walk to the **inner** `DE` (6 steps)…"). The test
`test_ex1_walk_matches_the_statement_leg_by_leg` replays every leg as a
plain walking BFS and checks each named end really is inner (`+1`) or
outer (`−1`), summing 4+1+6+1+4+1+6 = 23. That is the only external
ground truth about the inner/outer sense anywhere in the puzzle, and it
is what the bounding-box shortcut is held to.

Everything the solver relies on is checked at parse time, in the
[Day 16](day16_function_guide.md) refuse-loudly style: exactly one `AA`
and one `ZZ` tile, every other label on exactly two tiles, every pair one
outer + one inner. `warps` — tile → (landing tile, level delta) — is the
whole day in one dict; `labels` is kept purely for tests.

## Part 2: the level is a counter

Levels 1, 2, 3, … are *identical copies* — level 0 is the only special
layer (outer portals walled, `ZZ` live). So the recursive maze is an
infinite but **periodic** layered graph, and in automata vocabulary the
walk is a **one-counter system**: the level is a unary counter that inner
portals increment and outer portals decrement, with a zero test (outer
portals blocked at 0) and acceptance only at zero. That framing is the
problem within the problem: Part 2 is reachability in a pushdown system
whose stack alphabet has one symbol. BFS handles it without ceremony
because the counter goes *into the state*, not into the graph.

An infinite counter needs a floor under termination. A maze with no
balanced route — the statement's second example, recursively — would let
BFS descend forever, one level per portal pair per generation. `part2`
caps the depth, defaulting to the number of portal pairs (27 here), and
raises if the frontier drains: *no route returns to the outer level
within N nested mazes*.

**The cap is a heuristic, not a theorem, and the guide should say so.**
The folklore argument — "deeper than one level per portal pair must
revisit some portal, excise the loop" — does not survive contact:
excising a segment between two visits to the same tile at different
levels means level-shifting the tail, and the shifted tail can dip below
level 0 or lean on level-0-only rules. The one-counter literature has
bounds on counter values along shortest witnesses, but I have not chased
the exact theorem and the shipped code does not lean on one. Instead the
cap is *evidence-based*, per the repo's standing rule that a non-obvious
claim becomes a test:

* `test_real_depth_cap`: at cap 24 the real input has **no route at
  all**; at caps 25, 27 (default), and 54 the answer is identically
  5208. The recursion genuinely needs 25 nested mazes, and the default
  has headroom that a doubling cannot disturb.
* `test_part2_ex2_has_no_balanced_route`: the 58-step example stays
  routeless even at cap 50 — the raise is a real negative, not a cap
  artefact at 10. (Part Two's text, once unlocked, confirmed it in as
  many words: "there is no path that brings you to `ZZ` at the
  outermost level.")

And the optimal walk itself is a pleasing object: 5208 steps = 5088
walking + **120 warp transits, exactly 60 descents and 60 ascents**,
touching level 25 at its deepest. The books balance to the step, because
they must — every descent that isn't repaid strands you below the only
`ZZ` that counts.

### The statement's worked example: 396 steps, replayed leg by leg

Part Two's own example (13 portal pairs, interleaved) answers **396**,
diving to level 10 and resurfacing twice — and, like Part One, the
statement narrates the entire walk. The tests pin it both ways: the bare
total, and `test_part2_ex3_walk_matches_the_statement_leg_by_leg`, which
replays all 33 narrated legs — each "Walk from X to Y (N steps)" checked
as a warp-blind BFS distance to the inner ("Recurse into") or outer
("Return to") end the narration names, each transit costing 1 — and
closes the books exactly: 364 walked + 32 warped = 396, ending at `ZZ`
on level 0. That extends the inner/outer classification pin from example
1's three pairs to thirteen, on the statement's own words. (The example
maze itself was extracted from [day20.md](day20.md) by script, not
retyped — a 37-line transcription is 37 chances to test a typo instead
of the parser.)

### The maze that forces recursion: `WELL`

The statement's first example answers 26 recursively *because its portals
are useless* (every warp digs deeper; the portal-free 26-step walk — a
number the statement itself supplies — stands). Its second example has no
recursive route at all. Neither shows recursion *working*, and `WELL`
predates the Part Two unlock as the tests' minimal witness that it does:
a hand-built donut whose ring corridor is cut into two arcs that only
meet through portals:

```text
        A
        A
  ######.######
  #...........#
  #.##.#.####.#
  #.# X Q   #.#
  ### X Q   ###
  #.#       #.#
XX..#       #..YY
  #.#       #.#
QQ..#     Y #.#
  #.#     Y #.#
  #.######.##.#
  #...........#
  ######.######
        Z
        Z
```

Flat, the best walk warps through `QQ` once and reaches `ZZ` in **13**
steps — but that walk ends one level down, where `ZZ` is a dead tile.
Recursively the route must balance: down through inner `QQ`, the long way
round the bottom arc at level 1, back up through `YY`, then to `ZZ` —
**28** steps. Both numbers are derived tile-by-tile in the test file's
comment, *then* checked against the code, so the map is ground truth
rather than a snapshot of the implementation's own opinion. It also pins
the cap semantics: at `max_depth=0` the two arcs never meet and `part2`
raises.

## The Day 20 code, form by form

### `Maze` and `parse_input`

A frozen dataclass: `open_tiles` (frozenset), `start`, `end`, `warps`
(tile → (twin, delta)), `labels` (for tests only). The parse does the
full job — [per the repo's standing shape](day18_function_guide.md), all
the way to the structure the day reasons about: nothing downstream ever
looks at a character again.

### `_shortest(maze, *, recursive, max_depth)`

One BFS serves both parts. State is `(tile, level)`; flat mode pins the
level at 0 (a warp is a fifth neighbour on the same layer), recursive
mode applies the delta and skips a warp that would leave `[0, max_depth]`.
First pop of `(ZZ, 0)` is the answer. Exhausting the frontier raises —
"unreachable" flat, "no balanced route within the cap" recursive.

### `part1` / `part2` / `solve` / `main`

`part1` is `_shortest` flat. `part2(maze, max_depth=None)` defaults the
cap to `len(warps) // 2` — one level per portal pair — and exists as a
keyword precisely so the tests can move it. `solve` returns both;
`main` prints the maze census and both answers.

## The real input, measured

* 109×109 characters; 3,868 open tiles spanning x, y ∈ [2, 106]; 29
  labels = 27 portal pairs + `AA` (bottom rim, (73, 106)) + `ZZ` (left
  rim, (2, 77)).
* **Six open tiles are unreachable** even with every portal: a five-tile
  pocket at (65–67, 13–15) and a lone cell at (87, 37). Decorative dead
  ends — which is why the solvers count distance and never coverage.
* Part 1: 442 steps, 10 of them warp transits; BFS pops the goal after
  exploring 3,098 of the 3,862 reachable tiles.
* Part 2: 5208 steps (5088 walking + 120 transits, 60 down / 60 up),
  deepest level 25; 82,724 states explored, against 108,136 reachable
  at the default cap.
* Cost scales with states, as BFS should: part 2 explores 26.7× the
  states of part 1 and costs 28.8× the wall clock (74.3 ms vs 2.6 ms) —
  the per-state cost is flat, there is no algorithmic surprise hiding in
  the constant.

## Possible optimization: condense to the portal graph, then Dijkstra

The BFS spends nearly all its time re-walking corridors on every level,
and the levels are identical — the walking distances between portal
tiles are the same on every layer. So condense once, in the
[Day 18](day18_function_guide.md) style: one warp-blind BFS from each of
the 56 warp tiles (plus `AA`), recording walking distances to every other
labelled tile; then run Dijkstra (edges now have weights) over the tiny
graph of (portal tile, level) — about 56 × 26 ≈ 1,500 nodes — where an
intra-level edge costs its corridor distance and a warp edge costs 1.

Untested sketch, in the spirit of Day 14's LP sidebar:

```python
def condense(maze):                      # ~57 warp-blind BFS sweeps, run once
    pois = set(maze.warps) | {maze.start, maze.end}
    return {a: walking_distances(maze, a, pois) for a in pois}

def part2_dijkstra(maze, cap):
    legs = condense(maze)
    heap = [(0, maze.start, 0)]          # (dist, tile, level)
    best = {(maze.start, 0): 0}
    while heap:
        dist, tile, level = heappop(heap)
        if (tile, level) == (maze.end, 0):
            return dist
        for nbr, steps in legs[tile].items():          # walk a whole leg
            relax(nbr, level, dist + steps)
        if tile in maze.warps:                          # or take the warp
            dest, delta = maze.warps[tile]
            if 0 <= level + delta <= cap:
                relax(dest, level + delta, dist + 1)
```

The honest caveat, from measured numbers: each warp-blind sweep floods
the same 3,868 tiles part 1's whole BFS does (~2.6 ms measured), so ~57
sweeps is roughly 150 ms of condensation *before Dijkstra starts* —
about twice the shipped 74 ms. In Python, at this input's size, the
classic optimization loses; it wins when the recursion is deeper, when
many queries share one condensation, or when the sweeps cost what they
should in a compiled language. Filed as a sidebar, not shipped — per the
repo's optimization policy, and this time with the extra reason that it
is probably a pessimization here.

## Tests (what is pinned and why)

* **Statement examples**: 23 and 58 flat, parametrized.
* **The statement's narrated walk, leg by leg** — the only external
  ground truth on inner/outer classification (see above).
* **Example 1 recursively = its portal-free walk = 26**, with the 26
  coming from the statement's own text and re-derived by stripping
  `warps` and re-running `part1` — not from the recursive code judging
  itself.
* **Example 2 has no balanced route**, at the default cap and at 50 —
  the claim Part Two's text later confirmed verbatim.
* **Part Two's worked example**: 396, plus the full 33-leg replay of the
  statement's narrated walk (see above) — walking distances, all 13
  pairs' inner/outer senses, 364 + 32 = 396, final level 0, deepest 10.
* **`WELL`**: 13 flat vs 28 recursive, both hand-counted; `max_depth=0`
  raises.
* **Parse validation raises** on a label touching two open tiles and on
  a maze with no `AA`.
* **CRLF**, constructed (because `Path.read_text()` launders `\r\n`) and
  against the real file; the constructed case doubles as the proof that
  no line-stripping crept in, since stripping would move every label.
* **Real maze shape**: tile/label/warp censuses, rim positions of
  `AA`/`ZZ`, bounding box, warp involution (each tile's twin points
  back with the opposite delta), and the six stranded tiles.
* **The depth cap's evidence**: no route at 24; identical answers at
  25 / 27 / 54.
* **`check_locked(20, LOCKED)`** with `LOCKED = (442, 5208)` — both
  parts asserted against the real input.

## Benchmarks

`python\bench.py 20` (best / median ms over 15 reps):

| Day | Parse | Part 1 | Part 2 | Total |
|-----|-------|--------|--------|-------|
| 20 | 2.243 / 2.294 | 2.579 / 2.638 | 74.292 / 75.757 | 79.114 |

Cheap day. Part 2's 74 ms is 82,724 BFS states of pure-Python dict and
deque traffic; the sidebar above explains why the classic condensation
trick would not actually help here.

## If I were writing this in Rust

The state space is small and dense enough that the whole search flattens
into arrays:

* Index the open tiles once (`Vec<(i32, i32)>` + a `HashMap` or a
  byte-grid lookup), then a state is a single
  `u32 = tile_index * (cap + 1) + level`. `seen` becomes a `Vec<bool>`
  (or a bitset) of ~110k entries and `dist` a `Vec<u32>` — no hashing in
  the hot loop at all, which is where Python's 74 ms actually goes.
* Precompute each tile's neighbour list — including the warp as a
  `(target_tile, level_delta)` — into a CSR-style flat adjacency array,
  so the BFS inner loop is index arithmetic over contiguous memory.
* Labels parse naturally as `[u8; 2]` keys; the reading-order trick
  (only a letter whose right/down neighbour is a letter starts a label)
  transcribes directly over a `&[u8]` grid.
* The `(tile, level)` packing is the same move as Day 18's
  `(positions, mask)` key, but here it is perfect-hashable into an array
  index because both factors are small and bounded — the difference
  between a `HashMap<State, u32>` and a `Vec<u32>` is the difference
  between a graph search and a memory sweep.

No timing claim — it has not been written — but the shape of the win is
the usual one: the algorithm stays byte-for-byte the same, and only the
state bookkeeping changes species.

## What's next

[Day 21](day21.md) — the Intcode machine returns.
