# Day 17 — Set and Forget (function guide)

> The Intcode machine is unchanged — it froze at
> [Day 9](day09_function_guide.md) and lives in
> [python/intcode.py](../../python/intcode.py). What changes, as on every
> Intcode day since 11, is the **peripheral** on opcodes 3 and 4, and this one
> is a joke the puzzle makes out loud: the outputs are ASCII codes, so the
> "video feed" is literally a text file arriving one byte at a time. `chr()`
> over the stream and the frame draws itself. After that the VM is a **file
> format, not a participant** — Part 1 is a 3×3 morphological probe over a
> character grid, and Part 2 is three unrelated sub-problems stacked: derive a
> route, **compress it into a grammar**, then drive it. The middle one is the
> real puzzle, and it has a proper name: this is the **Smallest Grammar
> Problem** with three non-terminals and a 20-character budget. Real input:
> **3888** and **927809**.

## The puzzle in one paragraph

The ASCII program prints a picture of scaffolding: `#` scaffold, `.` space,
`^v<>` the robot (always standing on scaffold), `X` the robot having fallen
off. **Part 1:** find every scaffold cell with scaffold on all four sides and
sum `x * y` over them. **Part 2:** poke address 0 from 1 to 2 to wake the
robot, then feed it a *main routine* calling movement functions `A`, `B`, `C`,
each line at most 20 characters, that drives it over every scaffold cell; it
reports collected dust as one large non-ASCII output. Real input: a 55×35 view,
319 scaffold cells, 14 intersections, answers **3888** and **927809**.

Code: [python/day17.py](../../python/day17.py). Tests:
[python/tests/test_day17.py](../../python/tests/test_day17.py).

---

## Part 1: the VM is a file format

```python
def camera_view(program: list[int]) -> str:
    vm = VM(program)
    chars = []
    while True:
        result = vm.step()
        if result == "halted":
            break
        if isinstance(result, tuple):
            code = result[1]
            if not 0 <= code < 128:
                raise ValueError(f"non-ASCII output {code} from the camera")
            chars.append(chr(code))
    return "".join(chars)
```

One opcode-4 per character, `10` for newline. That is the entire interface, and
once it returns a `str` **no Intcode concept survives into the answer**.

The `0 <= code < 128` guard looks like belt-and-braces on Part 1 and is not:
Part 2's dust report arrives on this very stream as a value far above 127.
Letting a stray large value through as `chr()` would corrupt the grid silently
rather than loudly, which is the worst kind of bug to have in a parser.

### An intersection is a morphological probe

```python
def intersections(view: str) -> list[Point]:
    cells = scaffold_points(view)
    return [
        (x, y) for (x, y) in cells
        if {(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)} <= cells
    ]
```

A plus-shaped 3×3 structuring element over a binary image — the same
neighbourhood test as a Game-of-Life step, an erosion in image processing, or
a flood-fill's frontier check. Working over a `set` of points rather than a
2-D array means edge cells need **no bounds checking**: a neighbour off the
picture is simply not in the set.

Two details that are easy to get wrong:

- **The robot's own cell counts as scaffold.** The statement is explicit that
  when the robot is drawn as `^v<>` it is standing on scaffold. On this input
  the robot happens to sit mid-path and not on a crossing, so the answer is the
  same either way — which is exactly why it needs a test rather than a shrug
  (`test_robot_cell_counts_as_scaffold`).
- **`X` does not.** That glyph means it has already tumbled off, so its cell is
  not somewhere anything may stand.

Alignment parameter is `x * y` with `(0, 0)` at the top-left of the view, and
the sum is Part 1. On the statement's example the four crossings give
4 + 8 + 24 + 40 = **76**; on the real input, 14 crossings give **3888**.

---

## Part 2, sub-problem 1: the route

The scaffold "forms a path, but it sometimes loops back onto itself." That
sentence is the whole algorithm, and it means **no search is needed**:

- Away from a crossing, a scaffold cell has at most two scaffold neighbours. So
  once you are moving, there is never a choice — you continue or you stop.
- At a crossing, all four neighbours are scaffold, but three of them are where
  you came from and the two arms of the *other* strand. Going straight is legal
  and is the only way to leave without doubling back.

This is not even the first time AoC has posed the walk. **2017 Day 19,
*A Series of Tubes*** -- solved in the Rust repo -- states the identical rule
for its packet: "it needs to continue going the same direction, and only turn
left or right when there's no other option." The two puzzles mirror each other
right down to their numbers (year 17 day 19, year 19 day 17): 2017 hands you
the grid as raw text and scores the walk itself; 2019 hides the grid inside a
machine and makes the machine the scorer.

So the rule is "**go straight as far as you can, then turn the only way you
can**", and it is deterministic:

```python
while True:
    for turn, table in (("L", TURN_LEFT), ("R", TURN_RIGHT)):
        if ahead(pos, table[facing]) in cells:
            facing = table[facing]
            break
    else:
        return tokens          # no legal turn: the far end of the path

    distance = 0
    while ahead(pos, facing) in cells:
        pos = ahead(pos, facing)
        distance += 1
    tokens += [turn, str(distance)]
```

Facing is stored as **the glyph the camera would draw** (`^v<>`), so a turn is
a dict lookup and no angle arithmetic appears anywhere. `TURN_RIGHT` is built
by inverting `TURN_LEFT` rather than written out twice.

### The movement language cannot say "go forward"

Every move is `turn, distance`. There is no way to express a leading straight
run, so a legal route **must** begin with `L` or `R`.

That is not pedantry — it fell out of a test. Part One's example picture has
the robot facing straight up its own scaffold with nothing to either side, so
**no legal route exists from it at all**, and `path` correctly returns `[]`.
Part Two's picture faces the robot *across* the scaffold, which is precisely
why its route can begin `R,8`. The first draft of this guide's test suite
asserted "the greedy walk covers every cell" over both examples and failed on
the first one; the fix was to understand the language, not to patch the walk
(`test_a_robot_facing_along_the_scaffold_cannot_start`).

### Completeness is a property of the input

Nothing in the statement promises a greedy route visits everything. A scaffold
shaped as a *tree* rather than a self-crossing path would strand whole branches.
So `part2` verifies rather than assumes:

```python
missed = scaffold_points(view) - covered(view, tokens)
if missed:
    raise ValueError(f"the greedy route misses {len(missed)} scaffold cells")
```

On this input it misses nothing, and the arithmetic is exact:

| quantity | value |
|---|---:|
| moves in the route | 34 |
| total steps (`sum` of distances) | 332 |
| cells stepped on, with multiplicity (`1 + 332`) | 333 |
| distinct scaffold cells | 319 |
| **revisits** | **14** |
| **intersections** | **14** |

**Every intersection is crossed exactly twice and nothing else is driven over
twice** — which is what a self-crossing path *means*, now measured rather than
assumed (`test_every_intersection_is_crossed_exactly_twice`). So the greedy
walk wastes nothing beyond the crossings themselves. Whether 333 is the
provable minimum over all covering walks is not something this repo checks —
the plausible argument is that each crossing must be traversed on both of its
strands — so it is left as an observation rather than a claim.

The route:

```text
L,10,R,12,R,12,R,6,R,10,L,10,L,10,R,12,R,12,R,10,L,10,L,12,R,6,R,6,R,10,
L,10,R,10,L,10,L,12,R,6,R,6,R,10,L,10,R,10,L,10,L,12,R,6,L,10,R,12,R,12,
R,10,L,10,L,12,R,6
```

162 characters. The robot's memory holds 20 per line. Hence:

---

## Part 2, sub-problem 2: grammar-based compression

This is the day's real content, and it has a name.

Finding a main routine plus three movement functions that derive exactly one
string is finding a **straight-line program** — a context-free grammar whose
language is a single string. Minimising such a grammar is the **Smallest
Grammar Problem**, which is NP-hard in general, and the family it belongs to is
the one LZ78, Re-Pair and Sequitur live in. The puzzle's constraints tame it
completely:

- **at most 3 non-terminals** (`A`, `B`, `C`);
- **no nesting** — "movement functions may not call other movement functions",
  so the grammar is exactly two levels deep;
- **every line ≤ 20 characters** once comma-joined, main routine included,
  which caps the main routine at 10 calls (`A,B,C,...` is 10 letters plus 9
  commas = 19 characters; 11 would be 21).

Under those bounds, exhaustive backtracking settles it instantly:

```python
def search(i, functions, main):
    if i == len(tokens):
        return (_encode(main), [_encode(body) for body in functions])
    if len(_encode([*main, "A"])) > limit:
        return None                                  # the main routine is full

    for name, body in zip(names, functions):         # reuse a defined function
        if tokens[i : i + len(body)] == body:
            found = search(i + len(body), functions, [*main, name])
            if found:
                return found

    if len(functions) < len(names):                  # or coin a new one
        for length in range(1, len(tokens) - i + 1):
            body = tokens[i : i + length]
            if len(_encode(body)) > limit:
                break                                # bodies only grow
            found = search(i + length, [*functions, body], [*main, names[len(functions)]])
            if found:
                return found
    return None
```

Two prunes carry the whole thing. A candidate body that has already exceeded 20
characters ends the prefix loop, because bodies only get longer as `length`
grows. And a main routine already at 20 characters cannot be extended, so the
recursion depth is capped at 10 regardless of route length.

**Measured: 0.515 ms** on the real 68-token route.

### The answer is unique

The exhaustive count — the same recursion, continuing instead of returning at
the first hit — finds **exactly one** legal factorisation of this route:

```text
main : A,B,A,C,B,C,B,C,A,C     (19 chars, 10 calls — one call from the limit)
   A : L,10,R,12,R,12          (14 chars)
   B : R,6,R,10,L,10           (13 chars)
   C : R,10,L,10,L,12,R,6      (18 chars)
```

So the backtracker's search order cannot matter on this input, and there is no
"but is this the *right* factorisation?" to worry about — there is no other.
That is a property of the puzzle input rather than of the algorithm, so it is
pinned (`test_the_factorisation_is_unique`) rather than asserted here.

The main routine at 19 of 20 characters, and `C` at 18 of 20, are a good hint
about how carefully the input was constructed.

### Why it compresses at all

The whole 34-move route draws its distances from an alphabet of **three**:
`{6, 10, 12}`. With turns that is six distinct moves total. A route drawn from
a wide alphabet would not factor under any budget — and
`test_compress_reports_failure_instead_of_guessing` builds exactly that case
(`R,100,R,101,…,R,140`: 41 distinct moves, 245 characters, no repetition, so
three 20-character bodies cover at most ~60 characters and `compress` returns
`None`).

That test is worth reading for a second reason: its **first draft was wrong**.
It used `R,1,…,R,12` and asserted `None`, on the reasoning "no repetition, so
no reuse". `compress` cheerfully returned `('A,B,C', ['R,1,R,2,R', …])` — that
route is only ~50 characters, and three 20-character functions cover 60 with no
reuse required at all. The binding constraint is **total characters**, not
repetition. The test now says so out loud.

### Where else this shows up

Procedural abstraction on a size budget is a real compiler pass, not a puzzle
conceit:

- **LLVM's `MachineOutliner`** (and GCC's `-fipa-icf` / code-folding passes)
  finds repeated instruction sequences and hoists them into functions to shrink
  `-Oz` builds. Same objective, same "calls cost something too" tension.
- **Bytecode superinstructions** — the inverse direction, fusing common opcode
  pairs into one to shrink dispatch overhead. If you have been through
  *Crafting Interpreters*' VM chapters, this is the same shape of decision made
  the other way round.
- **Storer & Szymanski's macro compression models** are the formal treatment;
  the variant here (no nesting, bounded non-terminals) is their "external
  pointer macro model".

---

## Part 2, sub-problem 3: driving it

```python
vm = VM(program)
vm.mem[0] = 2

script = "\n".join([main, *functions, video]) + "\n"
vm.inputs.extend(ord(ch) for ch in script)
```

**`mem[0] = 2` is a memory poke, not an opcode** — the same side channel
[Day 13](day13_function_guide.md) used to buy a free play. It is written into
the VM's memory rather than into the caller's list, so the parsed program stays
reusable and `solve` can run the camera and then the robot off one parse
(`test_wake_poke_does_not_mutate_the_caller_s_program`).

The poke is a genuinely clever bit of puzzle construction. The real program's
first cell is `1`, so its first instruction is an **add**; poking a `2` there
turns that same instruction into a **multiply**, and the program branches into
its Part 2 behaviour. The test module's `poke_probe` reproduces the trick in
twelve cells — `[1, 9, 10, 11, 4, 11, 99, 0, 0, 200, 3, 0]` outputs 203
unpoked and 600 poked — so the mechanism is exercised rather than imitated.

Every line is ASCII plus a newline, in prompt order: main routine, `A`, `B`,
`C`, then `n` for the video feed. Because the whole script is known in advance,
all of it can be queued before the first `step()` — the VM's block/resume
protocol is available but not needed here, unlike [Day 15](day15_function_guide.md)
where each input depended on the previous output.

### Finding the answer in the stream

```python
if isinstance(result, tuple) and result[1] > 127:
    dust = result[1]
```

The robot narrates in ASCII (`Main:`, `Function A:`, and the prompts) before
reporting, so **"the last output" and "the only large output" are different
rules** — and only the second survives switching the video feed on, which
would bury the report in thousands of frame characters. Identifying the answer
*structurally* rather than positionally costs nothing and is the more honest
statement of what the peripheral promised
(`test_dust_is_identified_structurally_not_positionally`).

---

## Testing an Intcode day without mocking Intcode

Two techniques here, and they are complementary.

**Where the VM is irrelevant, don't involve it.** Everything downstream of
`camera_view` takes a `str`, so the puzzle's own worked examples — an ASCII
picture for Part 1, a picture plus its route for Part 2 — are reachable from a
test with no Intcode program in sight. This is the same separation
[Day 15](day15_function_guide.md)'s `MazeDroid` bought, arrived at from the
other direction: there the VM had to be faked because the statement shipped no
program; here it simply is not needed.

**Where the VM *is* the thing under test, hand-assemble a real program.** A
mock of `step()` would test the mock. Instead:

```python
def echo_program(text: str) -> list[int]:
    """104 is opcode 4 in immediate mode, so `104, c` outputs the literal c."""
    return [code for ch in text for code in (104, ord(ch))] + [99]
```

Two cells of Intcode per character, and now `camera_view` is tested against
the actual machine — decode, halt condition, output protocol and all. The same
move gives `[104, 999, 99]` for the non-ASCII rejection and `poke_probe()` for
address 0. Writing tiny Intcode programs by hand is cheap and it is the only
way to test a VM-facing function without the test drifting from the VM.

---

## Tests (what is pinned and why)

`python/tests/test_day17.py` — **32 tests**, one of them the `check_locked`
skip until Part Two is accepted.

| test | claim |
|---|---|
| `test_example_intersections`, `test_example_alignment_sum` | the four crossings and 4+8+24+40 = 76 |
| `test_robot_cell_counts_as_scaffold` | `^v<>` participates in the neighbour test; the real input can't show this |
| `test_tumbling_robot_is_not_scaffold`, `test_no_robot_is_an_error` | `X` is not standable; a robotless view is an error |
| `test_camera_view_decodes_a_real_intcode_program` | decode checked against a hand-assembled program, not a mock |
| `test_camera_view_rejects_non_ascii` | a >127 output is refused rather than `chr()`-ed into the grid |
| `test_example_route_matches_the_statement` | the greedy walk reproduces the puzzle's spelled-out route **exactly** |
| `test_a_robot_facing_along_the_scaffold_cannot_start` | **the movement language cannot express a leading straight run** |
| `test_walk_goes_straight_through_crossings` | a crossing is not a decision point |
| `test_example_factorisation_round_trips`, `test_real_route_factorisation` | **the grammar expands back to the original route** and every line fits 20 chars |
| `test_the_statements_own_factorisation_is_valid` | the puzzle's `A,B,C,B,A,C` derives the same string as ours — "one approach", not "the approach" |
| `test_compress_respects_a_tighter_limit` | the limit is a real constraint, not decoration |
| `test_compress_reports_failure_instead_of_guessing` | an unfactorable route returns `None` — **and the first draft of this test was wrong** |
| `test_two_function_budget_is_honoured` | the non-terminal budget bites |
| `test_wake_poke_reaches_the_machine` | `mem[0] = 2` really arrives, shown by an opcode that changes meaning |
| `test_wake_poke_does_not_mutate_the_caller_s_program` | the parse stays reusable, which `solve` depends on |
| `test_dust_is_identified_structurally_not_positionally` | prompts are ignored; the >127 value is the answer |
| `test_greedy_walk_covers_every_cell` | **all 319 cells** — a property of the file, not the statement |
| `test_every_intersection_is_crossed_exactly_twice` | **333 − 319 = 14 = the intersection count** |
| `test_route_alphabet_is_tiny` | only `{6, 10, 12}` — why three functions suffice |
| `test_the_factorisation_is_unique` | **exactly one legal grammar exists**, by exhaustive count |
| `test_uncompressed_route_would_not_fit` | 162 characters against a 20-character budget |
| `test_real_input` | `check_locked(17, LOCKED)` |

---

## Benchmarks

`.venv\Scripts\python.exe python\bench.py 17` — best / median ms over 7 reps:

| day | parse | part 1 | part 2 | total |
|---|---:|---:|---:|---:|
| 17 | 0.124 / 0.135 | 35.493 / 35.680 | 110.031 / 118.254 | 145.649 |

The breakdown of Part 2 is the interesting number:

| phase | ms | share |
|---|---:|---:|
| `camera_view` (VM run 1) | 37.360 | 33.5% |
| `path` (greedy walk) | 0.198 | 0.2% |
| `compress` (backtracking) | 0.515 | 0.5% |
| `run_robot` (VM run 2) | 73.416 | 65.8% |
| total | 111.489 | |

**99.3% of Part 2 is Intcode interpretation and 0.7% is solving the puzzle.**
The grammar search — the thing the day is *about*, and the thing that is
NP-hard in its unbounded form — costs half a millisecond. This is the same
shape as [Day 15](day15_function_guide.md), where the droid's walk was 99% of
the day and the BFS 1%, and it is worth internalising as the standing cost
model for Intcode days: the VM is the budget, the algorithm is free.

Where Day 17 sits in the year:

| day | total | note |
|---|---:|---|
| 16 | 2027.6 ms | the outlier |
| 03 | 185.0 ms | |
| **17** | **145.6 ms** | |
| 13 | 134.4 ms | |
| 15 | 133.2 ms | |

---

## If I were writing this in Rust

**Part 1 barely changes.** A `HashSet<(i32, i32)>` for the scaffold and the same
four-neighbour probe; if anything the temptation would be to use a
`Vec<Vec<u8>>` and index it, which then reintroduces the bounds checks the set
was avoiding. The set version is the better design in both languages, and the
reason is the same in both.

**The walk wants an enum.** Facing as `enum Dir { N, E, S, W }` with
`fn left(self) -> Dir` / `fn right(self)` as `match` arms, rather than Python's
glyph-keyed dicts. The Python version stores facing as the camera glyph
precisely *because* dict lookup is the cheapest thing available; in Rust the
enum is cheaper still and the compiler checks exhaustiveness, which the dict
cannot. This is the one place where the idiomatic Rust is clearly better rather
than merely different.

**The compressor is where Rust would show.** The search allocates a fresh
`Vec` for `main` and for each candidate body at every node —
`[*main, name]` in Python builds a new list per recursion step. The Rust
version wants a single `Vec<u8>` with push/pop around the recursive call:

```rust
main.push(name);
if let Some(found) = search(i + body.len(), functions, main) { return Some(found) }
main.pop();
```

Classic backtracking with an explicit undo, no allocation in the hot path, and
bodies as `&[Token]` slices into the original route rather than copies. At 0.5
ms the Python is already irrelevant next to the VM, so this is an aesthetic
point rather than a performance one — but it is exactly the pattern a chess
engine's move generator uses around make/unmake, and the reflex transfers.

**The VM is where the 111 ms lives**, and a Rust Intcode interpreter running
this program would be somewhere in the sub-millisecond range — `Vec<i64>` for
memory instead of a `defaultdict`, no boxed integers, no per-instruction
closure construction. That is a 100× on the day's actual cost and 0× on the
day's actual difficulty, which is a fair summary of what the language choice
buys here.

---

## What's next

Day 18 is not Intcode — a first since [Day 16](day16_function_guide.md) — and
from the statement it is a key-and-door maze, which usually means BFS over a
state space larger than the map itself.

Since [Day 13](day13_function_guide.md) no day's difficulty has lived inside
the VM. Day 13 framed a flat stream into triples,
[Day 15](day15_function_guide.md) mapped a world it could only walk, and Day 17
uses the machine as a text file and a motor —
[Day 14](day14_function_guide.md) and [Day 16](day16_function_guide.md) do not
run Intcode at all. The instruction set stopped being the puzzle at
[Day 9](day09_function_guide.md); everything since has been about what is wired
to opcodes 3 and 4.
