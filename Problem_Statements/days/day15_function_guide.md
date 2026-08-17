# Day 15 — Oxygen System (function guide)

> **First Python day.** Days 1–14 were solved in Racket and that code is
> frozen ([README](../../README.md)); from here on the shipping solution is
> Python. This guide annotates [python/day15.py](../../python/day15.py) and
> [python/intcode.py](../../python/intcode.py), and it is the first guide
> whose claims are pinned by a pytest module,
> [python/tests/test_day15.py](../../python/tests/test_day15.py).

> An Intcode program you cannot read, driving a droid you cannot see, in a
> maze you have no map of. You may ask it exactly one question — *"may I step
> north?"* — and the only reply is `0`, `1` or `2`. **The droid's position is
> state you can only walk, never set**, and that single constraint is the
> entire day: it rules out driving a breadth-first search directly, because
> BFS wants to jump to an arbitrary frontier cell each iteration and there is
> no teleport instruction. What you *can* do cheaply is take a step and take
> it back, so the traversal is **depth-first search with an explicit backtrack
> stack**, where the stack of moves-taken doubles as the route home. Then —
> and this is the part that decides whether the day takes twenty minutes or an
> evening — you **stop searching and start mapping**: chart the whole region
> into a `dict[(x, y)] -> tile`, and answer both parts with ordinary BFS over
> that dict, offline, with no droid involved. Part 1 is **254**, Part 2 is
> **268**. Along the way the input gives up a fact it never promised: the maze
> is a **tree** — 799 cells, 798 edges, not one cycle.

## The puzzle in one paragraph

The Intcode program is a remote control. Send `1`/`2`/`3`/`4` (north / south /
west / east) on an input instruction; get back `0` (wall, droid did not move),
`1` (moved), or `2` (moved, and this is the oxygen system) on an output
instruction. **Part 1:** the fewest movement commands from the droid's start
to the oxygen system. **Part 2:** the oxygen spreads one cell per minute from
the repaired system; how many minutes until the whole region is full. Real
input: **254** and **268**.

---

## The shape of the day: a world behind a keyhole

Every previous Intcode day handed you the program's world in the output
stream. [Day 11](day11_function_guide.md)'s robot told you what it painted.
[Day 13](day13_function_guide.md)'s cabinet drew you the whole board, every
frame, whether you wanted it or not. Day 15 inverts that: the program knows a
40×41 maze and will tell you about **one cell per command**, and only the cell
directly adjacent to wherever the droid currently happens to be.

That makes it the year's first day where the algorithm has to **discover its
own graph before it can traverse it** — and where the traversal and the
discovery are subject to *different* constraints:

| | wants | Day 15 gives you |
|---|---|---|
| **Discovery** | to visit cells in any convenient order | one step at a time, from the current cell only |
| **Answering** | to expand a frontier in distance order | no way to place the droid on a frontier cell |

Those two rows are incompatible, and the entire design of the solution is the
observation that **they do not have to happen at the same time**. Discovery is
cheap in DFS order and impossible in BFS order; answering is trivial in BFS
order once you hold a map. So:

```
   phase 1  explore()    embodied, sequential, DFS       -> dict[(x,y)] -> tile
   phase 2  distances()  disembodied, random-access, BFS -> dict[(x,y)] -> int
```

Fusing them — trying to make the droid's own walk report the distance — is
where this puzzle eats an evening. Keep them apart and each half is textbook.

### Why not just BFS with the droid?

You can, actually, and it is instructive to see how. BFS needs to resume from
an arbitrary frontier node; you cannot move the droid there, but you *can*
**clone the machine**. Give every queue entry its own `deepcopy` of the VM and
"jump to the frontier" becomes "resume a snapshot":

```python
q = deque([((0, 0), VM(program))])
while q:
    pos, vm = q.popleft()
    for command, (dx, dy) in MOVES.items():
        clone = copy.deepcopy(vm)          # <- the teleport instruction
        status = move(clone, command)
        ...
```

This is correct, and it finds `254` and the oxygen at `(16, 18)` and decides
the same 1,659 cells. It is also **675 ms against the DFS walk's ~66 ms**, a
roughly 10× tax, because every frontier cell pays for a full copy of a
1,045-cell memory image. Worth knowing as a technique — persistent/snapshotted VM state
turns *any* embodied search into a free-standing one, and it is the only
option on days where actions are irreversible — but here the actions are
perfectly reversible, so the backtrack stack is strictly better. It is written
up under [Possible optimizations](#possible-optimizations-and-one-deliberate-non-optimization)
as the road not taken.

### The wall probe is free

One clause in the statement does more work than it looks like:

> `0`: The repair droid hit a wall. **Its position has not changed.**

A failed move costs one command and teaches you one cell, and there is
*nothing to undo*. Only successful moves need a matching retreat. That turns
into an exact cost identity for the walk, pinned in
`test_command_count_identity`:

```
commands = 2 * (open_cells - 1) + walls
```

Every open cell except the origin is stepped into once and retreated from
once; the origin is never stepped into at all; every wall is probed exactly
once. On the real input: `2 * (799 - 1) + 860 = 2456`, and the instrumented
droid issues **2456**. Not "about", not "at most" — exactly.

---

## The algorithm in Python

```python
WALL, OPEN, OXYGEN = 0, 1, 2                       # reply codes ARE tile ids
NORTH, SOUTH, WEST, EAST = 1, 2, 3, 4
MOVES = {NORTH: (0, -1), SOUTH: (0, 1), WEST: (-1, 0), EAST: (1, 0)}
BACK  = {NORTH: SOUTH, SOUTH: NORTH, WEST: EAST, EAST: WEST}


def explore(droid):
    grid, pos, oxygen, trail = {(0, 0): OPEN}, (0, 0), None, []
    while True:
        unseen = next((d for d in MOVES if _ahead(pos, d) not in grid), None)
        if unseen is None:                          # nothing new here
            if not trail:
                break                               # ...and nowhere to retreat
            command = BACK[trail.pop()]
            _move(droid, command)
            pos = _ahead(pos, command)
            continue
        target = _ahead(pos, unseen)
        status = _move(droid, unseen)
        grid[target] = status
        if status != WALL:
            pos, oxygen = target, target if status == OXYGEN else oxygen
            trail.append(unseen)
    return grid, oxygen


def distances(grid, start):                         # plain BFS, unit weights
    dist, queue = {start: 0}, deque([start])
    while queue:
        here = queue.popleft()
        for command in MOVES:
            there = _ahead(here, command)
            if there not in dist and grid.get(there, WALL) != WALL:
                dist[there] = dist[here] + 1
                queue.append(there)
    return dist


part1 = lambda p: (lambda g, o: distances(g, (0, 0))[o])(*explore(VM(p)))
part2 = lambda p: (lambda g, o: max(distances(g, o).values()))(*explore(VM(p)))
```

(The last two lines are a sketch; the shipping file spells them out as
functions. Everything above is the real code.)

---

## The key idea: `trail` is the recursion stack *and* the route home

In an ordinary DFS you keep a stack so you know where to resume. In an
**embodied** DFS the stack is also the only thing that can get you back —
popping it does not just restore a variable, it issues a movement command. The
two roles collapse into one object, and that is the whole trick of the
traversal:

```python
command = BACK[trail.pop()]     # pop the frame ...
_move(droid, command)           # ... and physically walk it in reverse
pos = _ahead(pos, command)
```

`trail` holds *commands*, not positions, precisely so that popping yields
something you can send. Storing positions would force you to derive the
command from a coordinate difference on every retreat — the same information,
in the less useful form.

The Rust analogue is exact: this is why you write an iterative DFS with an
explicit `Vec<Dir>` rather than a recursive one. The recursive version's stack
is the *call* stack, and the "unwind" that happens on `return` is invisible —
but here the unwind has a side effect on the outside world, so it has to be
something you can see and control.

### The loop invariant

> `grid` holds every cell whose status has been observed, and the droid stands
> at the cell reached by following `trail` from `(0, 0)`.

Each iteration does exactly one of three things, each preserving it:

1. **Probe a wall.** `grid` grows by one; droid and `trail` unchanged (the
   statement guarantees the droid did not move).
2. **Step into a new open cell.** `grid` grows by one, `trail` grows by one,
   droid moves to match.
3. **Retreat.** `trail` shrinks by one, droid moves to match, `grid`
   unchanged.

### Why it terminates, and why the map is complete

`grid` only ever grows, and it is bounded by the finitely many cells adjacent
to the reachable region, so cases 1 and 2 can happen only finitely often. Case
3 shrinks `trail`, which only grows in case 2, so it too is bounded. The loop
exits only when `trail` is empty *and* all four neighbours of the origin are
charted — that is, when the DFS has fully unwound.

Completeness is the standard DFS argument: a cell is left uncharted only if no
open cell adjacent to it was ever visited, and DFS from `(0, 0)` visits every
cell in `(0, 0)`'s connected component. Pinned end-to-end in
`test_example_charts_every_open_cell`, and on the real input by
`test_real_maze_is_a_tree` (BFS from the start reaches all 799 open cells).

One free corollary: since the loop exits with `trail` empty, **the droid is
physically back at its starting cell**. Nothing in the puzzle needs that, but
it is a sharp check on the retreat logic — a sign error in `BACK` desynchronises
`pos` from the real droid and the final position drifts. That is
`test_droid_returns_home`, and it is the test most likely to catch a broken
edit to this function.

---

## Part 2: a flood fill *is* a breadth-first search

> It takes one minute for oxygen to spread to all open locations that are
> adjacent to a location that already contains oxygen.

Read that again with BFS in mind and it is a definition of a BFS *level*. The
set of cells that have oxygen after `t` minutes is exactly the set at distance
`≤ t` from the source, so:

```python
def part2(program):
    grid, oxygen = explore(VM(program))
    return max(distances(grid, oxygen).values())
```

There is no simulation loop, no `while any_still_empty`, no set-of-frontiers
being repeatedly expanded and diffed. The minute counter *is* the level
number, and BFS already computes it. The answer is the **eccentricity** of the
oxygen cell — the greatest distance from it to any other cell — which is the
canonical name worth storing, because "how long until this spreads everywhere"
is an eccentricity question every time you meet it.

Note what changed between the parts: **one argument.** Part 1 roots the BFS at
the origin and reads off one entry; Part 2 roots it at the oxygen and takes
the max. Same map, same traversal, same function.

---

## The Day 15 code, form by form

### `intcode.py` — the VM, extracted

The instruction set froze at [Day 9](day09_function_guide.md). Days 11, 13 and
15 all leave the machine untouched and change only the *peripheral* wired to
opcodes 3 and 4, so the VM belongs in one module. The Racket tree made this
move at Day 13 ([src/intcode.rkt](../../src/intcode.rkt)); the Python tree
makes it here.

`python/day11.py` and `python/day13.py` keep their own verbatim copies
deliberately — their guides annotate those lines, and rewriting code out from
under a guide breaks the guide. New days import.

The protocol is [Day 7](day07_function_guide.md)'s. `step()` runs one
instruction and reports:

| return | meaning |
|---|---|
| `"ran"` | state advanced, nothing to see |
| `"blocked"` | opcode 3 with an empty input queue — **`ip` has not moved** |
| `"halted"` | opcode 99 (idempotent) |
| `("output", v)` | opcode 4 produced `v` |

Returning `"blocked"` instead of demanding an input list up front is the whole
difference between a batch program and an interactive one: it lets the caller
compute the next input *from the output it just saw*. Day 15 is the purest use
of that so far — the next movement command depends on the reply to the last.

### `MOVES` and `BACK` — why `BACK` is a table

```python
NORTH, SOUTH, WEST, EAST = 1, 2, 3, 4
BACK = {NORTH: SOUTH, SOUTH: NORTH, WEST: EAST, EAST: WEST}
```

The puzzle numbers the directions **N, S, W, E** — the two axes paired up, not
a walk round the compass. So the tempting `(d + 2) % 4` is wrong here; the
opposite of direction `d` is `d ^ 1` on 0-based codes, or just a four-entry
dict on the puzzle's 1-based ones. A table is the honest encoding of an
arbitrary numbering, and `test_back_is_an_involution` pins both that
`BACK[BACK[d]] == d` and that stepping `d` then `BACK[d]` returns you to where
you started — the property the retreat logic actually depends on.

Compare [Day 11](day11_function_guide.md), where the robot's turns *were*
modular arithmetic on a clockwise ordering. The difference is not style; it is
that Day 11's numbering was rotational and this one is not.

### `parse_input` — the program

```python
def parse_input(text: str) -> list[int]:
    return [int(t) for t in text.strip().split(",")]
```

1,045 integers. The `.strip()` is the Windows CRLF guard the repo requires of
every day — inputs downloaded here arrive with `\r\n`, and `int("99\r")`
raises. Pinned across four line-ending shapes in
`test_parse_input_tolerates_crlf`.

For an Intcode day the program *is* the structure the day reasons about, so
this is a full parse and not a lazy one. The maze is not part of the parse:
recovering it requires running the machine, which is solving, not parsing.

### `_move` — one request, one reply

```python
def _move(vm, command):
    vm.inputs.append(command)
    while True:
        result = vm.step()
        if isinstance(result, tuple):
            return result[1]
        if result == "halted":
            raise RuntimeError("droid program halted mid-walk")
```

The program's loop is strictly synchronous — one input, one output, forever —
so we can run to the next output and stop. That is a real simplification over
[Day 13](day13_function_guide.md), which had to *frame* a flat output stream
into `(x, y, tile)` triples and could not assume any alignment between reads
and writes.

The `halted` branch is defensive and never fires: this program has no exit. It
is there so that a future edit that sends an invalid command (anything outside
1–4) fails loudly instead of hanging.

### `explore` — the walk

Covered above. One detail worth calling out: it takes a **droid**, not a
program.

```python
def explore(droid: VM) -> tuple[dict[Point, int], Point]:
```

That is not gratuitous generality. The puzzle ships worked examples but **no
Intcode program to reach them with** — the statement draws its maze in ASCII
and narrates the replies in prose. Accepting anything that answers `.inputs` /
`.step()` is what lets the test module hand in a `MazeDroid` built from that
ASCII and run the *real* walk against the puzzle's *own* example. See
[Tests](#tests-what-is-pinned-and-why).

### `distances` — BFS over the finished map

```python
if there in dist or grid.get(there, WALL) == WALL:
    continue
```

`grid.get(there, WALL)` treats unknown cells as wall. That is safe rather than
lucky: `explore` leaves nothing reachable uncharted, so an unknown cell is
necessarily one we could not have got to anyway. Unit edge weights mean the
first arrival is the shortest — no priority queue, no relaxation, no Dijkstra.

### `render` — the map as text

Not needed for either answer; kept because it is the fastest way to see that
`explore` worked, and because a 41×41 maze printed to a terminal is the sort
of thing worth having twelve months from now. `python python/day15.py` prints
it, with `D` at the origin and `O` at the oxygen system.

For anything more than a glance, [python/day15_map.py](../../python/day15_map.py)
writes the map to `maps/` in three formats and three colourings:

```
python python/day15_map.py              # ASCII, SVG and PNG into maps/
python python/day15_map.py --scale 24   # bigger pixels
```

| colouring | what it shows |
|---|---|
| `plain` | wall / open, with `D` and `O` marked |
| `route` | the 254 steps from `D` to `O` — **Part 1, drawn** |
| `fill` | every square shaded by distance from `O` — **Part 2, drawn**, 0 to 268 minutes |

The PNG writer is about twenty lines of `zlib` and `struct` — signature, IHDR,
one IDAT of zlib-compressed scanlines each prefixed with a zero filter byte,
IEND — because this venv has no Pillow and taking a dependency to draw 1,681
squares would be absurd. The SVG merges runs of equal colour along each row,
which takes 1,659 rectangles down to 424.

The `fill` image is the one worth looking at. The bright end of the ramp — the
last squares to fill — sits **around the droid's own starting cell**, because
the start is 254 minutes from the oxygen out of a total of 268. And the shading
does not decrease smoothly with distance across the picture: corridors that are
adjacent on the page can be a hundred minutes apart, because in a maze the
graph distance and the Euclidean distance have almost nothing to do with each
other. That is the whole reason Part 2 needs a BFS rather than a formula.

Outputs land in `maps/`, which is gitignored for the same reason
`inputs/*.txt` is: they are derived from a puzzle input.

### `part1`, `part2`, `solve`, `main`

`part1` and `part2` are independent by design — each explores from scratch —
because the harnesses require parts callable in isolation. `solve` is the entry
point that pays for the droid once and answers both questions from the single
map, and on this day that is worth 1.98×; see
[Possible optimizations](#possible-optimizations-and-one-deliberate-non-optimization).
`main` prints the rendered maze, the cell counts, the oxygen's coordinates and
both answers.

---

## The problem within the problem: the maze is a tree

Instrument the finished map and it gives up a fact the statement never
promised:

```
open cells        799
edges             798
degree histogram  {1: 37, 2: 727, 3: 35}
```

`|E| = |V| - 1` on a connected graph means **acyclic**. This is a *perfect
maze*: exactly one simple path between any two cells, 37 dead ends, 35
T-junctions, no four-way crossings, no loops at all. That is
`test_real_maze_is_a_tree`, pinned because the consequences below are quoted
as fact and a claim no test checks is a claim that can rot.

**And the [disassembly](day15_disassembly.md) says why.** The maze is not
computed by the Intcode program, it is *stored* in it — a 39×20 table at
address 252 holding one entry per potential wall, with the bit hidden as
`value < 37`. That table has exactly **399 passages over a 20×20 grid of 400
cells**, and 399 = 400 − 1 is a spanning tree by definition. The acyclicity
was never a property of the traversal; it is a property of the file, carved by
whatever generated the puzzle input. Everything below is a consequence of that
one line of the data region.

Four consequences, in increasing order of how much they should tempt you:

**1. The bounding box is 41×41 and mostly wall.** 1,659 cells decided, 860 of
them wall. A tree maze on a 41×41 grid is the classic maze-generator output —
almost certainly a randomised DFS or Kruskal carve, which is why it has no
loops.

**2. The droid starts at an end of the diameter.** Double-sweep BFS (the
standard two-pass trick: BFS from anywhere to find one extremal vertex, BFS
again from there) gives a **diameter of 466, between `(6, -8)` and `(0, 0)`**.
The origin is one of the two most eccentric cells in the whole maze. The
oxygen at `(16, 18)` is much more central — eccentricity 268, ranking 127th of
799 — and the maze's true centre is `(-3, 18)` with radius 233. So Part 2's
answer is not far off the best possible fill time and is a long way off the
worst (466).

**3. On a tree, DFS's trail *is* the shortest path.** Exactly one simple path
exists between two cells, and DFS's trail is always simple, so the trail depth
when the droid first stands on the oxygen must equal the BFS distance. It
does: **measured depth 254, and Part 1 is 254**. Which means you could have
read Part 1 straight off the walk, with no BFS at all.

**4. …and you should not.** Nothing in the statement promises a tree. A maze
with one loop breaks consequence 3 immediately, and it breaks it *silently* —
you get a plausible number that happens to be too large. That failure mode is
pinned in `test_the_walk_is_not_the_answer`, on a five-by-five ring where the
DFS tie-break sends the droid the long way round and the walk reports a value
larger than the answer of 2.

This is the recurring shape of the "problem within the problem" lens: **the
input has more structure than the specification, and taking the shortcut is a
bet on the input rather than on the problem.** The two-phase design costs 0.56
ms of BFS on top of a 66 ms walk — under 1% — to be right for reasons that do
not depend on which maze you were handed. Cheap insurance. But knowing the
maze is a tree is worth having anyway, because it explains the timings, it
explains why a right-hand-wall-follower would also work here, and it is the
kind of thing that will be the *whole* puzzle on some future day.

---

## Possible optimizations (and one deliberate non-optimization)

### Explore once, answer twice — this one ships, as `solve`

`part1` and `part2` each call `explore`, so running both walks the maze twice:
66.08 ms + 65.91 ms, of which the two BFS passes are 0.56 ms each. **Under 1%
of each part is the part that differs.**

They stay independent on purpose — `bench.py` and `check_locked` both require
parts callable in isolation, and sharing state between them is exactly the
coupling those harnesses exist to prevent. So the win goes into a third entry
point rather than into either part:

```python
def solve(program):
    grid, oxygen = explore(VM(program))
    return distances(grid, (0, 0))[oxygen], max(distances(grid, oxygen).values())
```

Measured: **66.67 ms for both answers against 131.99 ms for the two parts run
separately — 1.98×**, for four lines. This is the shape the repo's per-day
deliverable asks for anyway (`parse_input` / `part1` / `part2` / `solve` /
`main`), and Day 15 is the first day where `solve` is more than a convenience
wrapper.

The bench table below therefore *overstates* the day by almost exactly 2×: it
times the parts, and the parts are deliberately redundant.

### Where the 66 ms actually goes

| | |
|---|---|
| VM instructions executed by the walk | **83,123** |
| Movement commands issued | **2,456** |
| Instructions per command | **~34** |
| `explore` | **~66 ms** |
| `distances` (either root) | **0.56 ms** |

So the day is 99% Intcode interpretation and 1% graph algorithm, and the only
lever that matters is the interpreter.

(A caveat on that table, and a lesson about benchmarking. Timed in isolation
`explore` came out at **68.4 ms** — *slower* than the 66.08 ms `part1` that
contains it, which is impossible. The 2.3 ms gap is run-to-run drift, and it
is larger than the 0.56 ms BFS it is supposed to be measuring. That the graph
half of the day sits below the noise floor is the real finding here, and it is
exactly why `bench.py` reports best *and* median rather than one shot.)

83,123 instructions in 66 ms is about **1.26 M instructions/s** — call it
**3.8× slower** than the ~4.8 M steps/s
[Day 13](day13_function_guide.md)'s Racket VM managed on a different program.
That is the Python tax on a dispatch loop, plus this VM's per-instruction
closure allocation (`mode`, `val` and `addr` are defined fresh inside every
`step`).

Hoisting those closures, or replacing the `if`-chain with a dispatch dict, or
running the whole thing under PyPy, are all real wins available here — and all
of them belong to `intcode.py`, not to Day 15. When a later day needs the VM
to be fast, that is the file to change, and every day from 11 onward benefits
at once. That is the payoff for extracting it.

### State-cloning BFS — the road not taken

Written up above. **674.9 ms, 10.2× slower**, correct, and worth carrying in the
toolkit for the day when actions are *not* reversible and a backtrack stack is
therefore unavailable. It is the imperative-search analogue of a persistent
data structure: you do not undo, you keep the old version.

### Right-hand-wall following

Because the maze is a tree, a wall-follower visits every cell and returns to
the start, tracing every edge exactly twice — the same `2 * (open - 1)`
successful moves the DFS makes, but with *no* `grid` lookup needed to decide
the next move. It is the classic maze algorithm and it would work on this
input. It is not shipped for the same reason as consequence 4 above: it is a
bet on the input's acyclicity, and it stops finding all cells the moment the
maze has a loop that encloses something.

---

## Tests (what is pinned and why)

[python/tests/test_day15.py](../../python/tests/test_day15.py), 22 tests.

The central design decision: the puzzle ships worked examples but **no Intcode
program**, so the tests supply `MazeDroid` — an ASCII maze wearing the VM's
interface.

```python
class MazeDroid:
    """`#` wall, `.` open, `O` oxygen, `D` the droid's start."""
    def step(self):
        command = self.inputs.pop(0)
        ...
        if ch == "#":
            return ("output", WALL)      # status 0: the droid did NOT move
```

This is better than a mock in the usual sense, because nothing is stubbed
*out*: `_move`, the retreat logic and the whole `explore` loop run for real
against it. And it makes observable two things the Intcode program never will
— where the droid ends up, and how many commands it took.

- **The statement's example, both parts.** The Part Two map with the Part One
  starting cell marked: `2` moves to the oxygen, `4` minutes to fill, 8 open
  cells. Plus a ring and a straight corridor, parametrized.
- **`test_droid_returns_home`** — the backtrack stack is a real route home,
  not just a recursion stack. The test most likely to catch a broken `BACK`.
- **`test_command_count_identity`** — `commands == 2 * (open - 1) + walls`,
  on all three mazes. Pins "a wall probe is free" as arithmetic rather than
  prose.
- **`test_the_walk_is_not_the_answer`** — on the ring, the droid meets the
  oxygen only after circling, so the command count exceeds the answer. This is
  the test that justifies the two-phase design, on a maze the real input
  cannot produce.
- **`test_back_is_an_involution`** — `BACK[BACK[d]] == d`, and stepping `d`
  then `BACK[d]` returns to the origin.
- **`test_real_maze_is_a_tree`** — `(799, 798)` cells and edges, and
  `edges == cells - 1`. Pins the structural claim the whole "problem within
  the problem" section is built on.
- **CRLF** across four line-ending shapes, per the repo's Windows rule.
- **`check_locked(15, (254, 268))`** — verified on adventofcode.com.

Four more come from the [disassembly](day15_disassembly.md), because its claims
are claims about the input file and deserve the same treatment:

- **`test_static_recovery_matches_the_walk`** — the maze read out of the data
  region is the maze the droid walks, cell for cell, and yields both answers.
- **`test_oxygen_is_a_literal_in_the_code`** — `(37, 39)` at addresses 146 and
  153, start `(21, 21)` at 1034/1035.
- **`test_wall_threshold_is_a_hole_in_the_value_set`** — 37 is the only integer
  in 1..99 absent from the table, so `< 37` and `< 38` are the only thresholds
  that give the right partition.
- **`test_the_maze_is_a_spanning_tree_of_a_20x20_cell_grid`** — 400 cells, 399
  passages. This is the *cause* of `test_real_maze_is_a_tree`'s effect: one
  observes acyclicity by walking, the other reads it out of the generator's
  output.

Two things are deliberately *not* pinned. The DFS trail depth to the oxygen
(254) would require a second implementation of `explore` inside the test to
observe; the tree property implies it, so the tree property is what is pinned.
And no test asserts a literal rendered map — it would break on any change to
the bounding box and assert nothing the code promises.

---

## Benchmarks

```
| Day | Parse (ms) | Part 1 (ms) | Part 2 (ms) | Total (ms) |
|-----|-----------|-------------|-------------|------------|
| 15  | 0.074     | 66.624      | 66.462      | 133.160    |
```

Best of **15** repetitions (`python/bench.py 15 -n 15`); medians were 0.075 /
67.301 / 67.047 — about 1% above best, so the machine was quiet during the
run, though successive whole-run bests still wander by ~3%.

**Parse (0.074 ms)** — 1,045 integers, about 40% of
[Day 13](day13_function_guide.md)'s 2,640-cell program and, at 0.074 ms,
roughly 29× faster than Day 13's 2.15 ms Racket parse. Different language,
different harness, different program; the useful comparison is not between
those two numbers but between this and the 66 ms below.

**Part 1 and Part 2 are the same number** — 66.6 and 66.5 ms — because they do
the same work. Each explores the maze in full and then runs one BFS that costs
0.56 ms. Two days this year had parts that differed by orders of magnitude
([Day 9](day09_function_guide.md)'s 530×, [Day 14](day14_function_guide.md)'s
26×); Day 15's parts differ by **0.2%**, which is inside the noise, and that is
itself the finding: the puzzle's two questions are two reads of one artifact.

Put next to the alternatives, all measured back to back in one session so the
ratios mean something (best of 15, or of 5 for the slow one):

| approach | time | vs one part |
|---|---|---|
| `part1` — DFS walk + BFS from the origin | 66.08 ms | 1.00× |
| `part2` — DFS walk + BFS from the oxygen | 65.91 ms | 1.00× |
| `solve` — one walk, both answers | 66.67 ms | **1.98× faster than running both parts** |
| `distances` alone, handed the finished map | 0.56 ms | 1/118th of a part |
| state-cloning BFS | 674.9 ms | 10.2× slower |

---

## If I were writing this in Rust

The interesting part is not the maze, it is the droid interface. `explore`
taking "anything with `.inputs` and `.step()`" is Python duck typing; in Rust
it becomes a trait, and the test's `MazeDroid` becomes a second implementor —
which is the same design, but checked.

```rust
use std::collections::{HashMap, VecDeque};

#[derive(Clone, Copy, PartialEq, Eq)]
enum Tile { Wall, Open, Oxygen }

#[derive(Clone, Copy, PartialEq, Eq, Hash)]
enum Dir { North, South, West, East }

impl Dir {
    const ALL: [Dir; 4] = [Dir::North, Dir::South, Dir::West, Dir::East];

    fn back(self) -> Dir {
        match self {
            Dir::North => Dir::South,  Dir::South => Dir::North,
            Dir::West  => Dir::East,   Dir::East  => Dir::West,
        }
    }

    fn step(self, (x, y): (i32, i32)) -> (i32, i32) {
        match self {
            Dir::North => (x, y - 1), Dir::South => (x, y + 1),
            Dir::West  => (x - 1, y), Dir::East  => (x + 1, y),
        }
    }
}

/// What `explore` needs. The Intcode VM implements it; so does the test maze.
trait Droid {
    fn go(&mut self, dir: Dir) -> Tile;
}

fn explore(droid: &mut impl Droid) -> (HashMap<(i32, i32), Tile>, (i32, i32)) {
    let mut grid = HashMap::from([((0, 0), Tile::Open)]);
    let (mut pos, mut oxygen, mut trail) = ((0, 0), None, Vec::new());

    loop {
        match Dir::ALL.iter().find(|d| !grid.contains_key(&d.step(pos))) {
            None => match trail.pop() {
                None => break,
                Some(d) => { let b = Dir::back(d); droid.go(b); pos = b.step(pos); }
            },
            Some(&d) => {
                let target = d.step(pos);
                let tile = droid.go(d);
                grid.insert(target, tile);
                if tile != Tile::Wall {
                    pos = target;
                    trail.push(d);
                    if tile == Tile::Oxygen { oxygen = Some(target); }
                }
            }
        }
    }
    (grid, oxygen.expect("no oxygen system in the maze"))
}
```

Three things the type system buys that Python leaves to comments:

1. **`Tile` is an enum, not an `i32`.** In Python, `WALL, OPEN, OXYGEN = 0, 1,
   2` deliberately coincide with the droid's reply codes — a pun that is
   convenient and completely unchecked. Rust forces a `match` at the boundary
   where the status code becomes a tile, which is where the pun should be
   audited anyway.
2. **`Dir::back` is total.** No dict lookup that could `KeyError`, no
   `(d + 2) % 4` that silently means the wrong thing under an N-S-W-E
   numbering.
3. **`trait Droid` makes the test's stand-in a first-class alternative
   implementation** rather than a convention. The Python version's contract —
   "anything with `.inputs` and `.step()`" — exists only in a docstring and in
   the fact that `MazeDroid` happens to satisfy it.

The one place Rust is *worse*: the state-cloning BFS sidebar. `deepcopy` in
Python is one call on an arbitrary object graph; in Rust you would need
`#[derive(Clone)]` on the VM and the `HashMap` memory, which is fine — but the
whole reason that approach is attractive in a scripting language is that
snapshotting is free to write. Here it would be about as much code as the
backtrack stack, and 10× slower, so nobody would write it.

`distances` is a straight transcription: `VecDeque`, a `HashMap<(i32,i32),
u32>`, `while let Some(here) = queue.pop_front()`. Nothing to say about it,
which is the point — once you hold a map, this half of the day is boring in
every language.

---

## What's next

Day 15 is the year's first **discover-the-graph-then-traverse-it** day, and
the separation it forces — an embodied, sequential mapping phase feeding a
disembodied, random-access answering phase — is the transferable lesson. Store
it next to the two names that carry it: **DFS with an explicit backtrack
stack** for exploration under a movement constraint, and **eccentricity** for
"how long until this spreads everywhere". Both recur.

It is also the day the Python tree grew an
[`intcode.py`](../../python/intcode.py) of its own, which is where every
remaining Intcode day (17, 19, 21, 23, 25) will now import from — and where
any future work on interpreter speed belongs.

Day 15's own program is examined instruction by instruction in the companion
[disassembly](day15_disassembly.md).

See the [summary table](summary_2019.md) for the running scoreboard.
