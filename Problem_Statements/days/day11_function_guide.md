# Day 11 — Space Police (function guide)

> The Intcode VM ([Day 9](day09_function_guide.md)) comes back as a
> **hull-painting robot**, and it's the first Intcode day where the program's
> own output feeds back into its own next input: it reads the color of the
> panel it's sitting on, emits *(paint color, turn direction)*, moves forward
> one panel, and repeats — so the input for cycle *N+1* depends on where
> cycle *N*'s output moved the robot. That rules out Day 9's batch
> `run/inputs` (which needs every input known before the machine starts) and
> calls for [Day 7](day07_function_guide.md)'s cooperative-pause `vm-step!`
> instead — stepped one instruction at a time, blocking on an empty input
> queue until the caller (here, the hull-painting loop) supplies one. The
> whole day is those two prior days fused: Day 9's operand resolution
> (relative mode, opcode 9, growable memory) inside Day 7's step-and-block
> shape, driving a `(x . y) -> color` hash exactly like
> [Day 10](day10_function_guide.md)'s coordinate bookkeeping.
> [day11_disassembly.md](day11_disassembly.md) takes the real puzzle
> program apart and finds something sharper than expected: the very first
> camera reading is a one-time fork into one of two nearly disjoint
> programs sharing the same 659 cells — a self-modifying, non-recursive
> loop for the black-start path, and a relative-base recursive engine (real
> `jump rel[0]` call/return) for the white-start path — and because every
> input is a live world-dependent value, disassembling it completely
> required actually running `paint-hull`, not feeding it a canned list.

## The puzzle in one paragraph

The Intcode program is the brain of a robot sitting on an infinite grid of
panels. Each cycle: the robot reports the color of its current panel as
input (`0` black, `1` white); the program answers with two outputs — a
color to paint the current panel, and a turn (`0` left, `1` right) — after
which the robot turns and moves forward exactly one panel. This repeats
until the program halts. **Part 1:** starting on an all-black hull, how many
panels does the robot paint at least once (regardless of final color, and
even if some panels are painted more than once)? **Part 2:** starting on a
*single white* panel instead, the panels the robot paints spell an
eight-letter registration code as a lit/unlit pixel grid — render it and
read the letters off. On the real input, Part 1 is **2129** and Part 2
renders as **`PECKRGZL`**.

---

## The algorithm in Python

Day 11 is *interpreter-flavored* like Days 5/7/9, so the Python companion
([python/day11.py](../../python/day11.py)) mirrors the Racket almost
statement-for-statement — a resumable `VM` class instead of a mutable
struct, but the same step-and-block protocol:

```python
class VM:
    def __init__(self, program):
        self.mem = defaultdict(int, enumerate(program))
        self.ip = 0
        self.rb = 0
        self.inputs = []
        self.halted = False

    def step(self):
        if self.halted:
            return "halted"
        # ... decode op/modes, resolve val(n)/addr(n) with relative mode ...
        if op == 3:
            if not self.inputs:
                return "blocked"
            mem[addr(1)] = self.inputs.pop(0); self.ip += 2; return "ran"
        if op == 4:
            self.ip += 2
            return ("output", val(1))
        # ... opcodes 1/2/5/6/7/8/9 unchanged from Day 9 ...
        if op == 99:
            self.halted = True
            return "halted"

DELTAS = [(0, -1), (1, 0), (0, 1), (-1, 0)]   # up right down left, clockwise

def turn(facing, signal):
    return (facing + (3 if signal == 0 else 1)) % 4

def run_to_outputs(vm, camera):
    outs = []
    while True:
        result = vm.step()
        if result == "blocked":
            vm.inputs.append(camera)
        elif result == "halted":
            return outs
        elif isinstance(result, tuple):
            outs.append(result[1])
            if len(outs) == 2:
                return outs

def paint_hull(program):
    vm = VM(program)
    pos, facing, panels = (0, 0), 0, {}
    while True:
        outs = run_to_outputs(vm, panels.get(pos, 0))
        if len(outs) < 2:
            return panels
        panels[pos] = outs[0]
        facing = turn(facing, outs[1])
        dx, dy = DELTAS[facing]
        pos = (pos[0] + dx, pos[1] + dy)

def part1(program):
    return len(paint_hull(program))

def render(panels):
    whites = [pos for pos, color in panels.items() if color == 1]
    xs, ys = [p[0] for p in whites], [p[1] for p in whites]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    return "\n".join(
        "".join("#" if panels.get((x, y), 0) == 1 else "." for x in range(x0, x1 + 1))
        for y in range(y0, y1 + 1))

def part2(program):
    return render(paint_hull(program, start_color=1))
```

Running `python python/day11.py` against the real input independently
confirms **2129** for Part 1, and — the stronger check, since it exercises
the turn/move bookkeeping across ~250 decision cycles instead of one
diagnostic number — renders **the identical `#`/`.` grid, pixel for pixel**
for Part 2. Two independent implementations agreeing on a whole picture, not
just a checksum, is much harder to fake than agreeing on a single integer.

---

## The Day 11 code, form by form

### The `vm` struct and `vm-step!` — Day 9's operand resolution, stepped like Day 7

```racket
(struct vm (mem ip rb inputs halted?) #:mutable)

(define (make-vm program) (vm (d05:intcode-mem program) 0 0 '() #f))
```

Compare this to [Day 7](day07_function_guide.md)'s `vm` struct: same shape
(`mem ip inputs halted?`), plus one new field, `rb` — the relative base from
[Day 9](day09_function_guide.md). `vm-step!` is the union of the two days:
Day 7's `case`-per-opcode return protocol (`'blocked` / `'ran` /
`` `(output ,n)`` / `'halted`) wrapping Day 9's `val`/`addr` operand
resolution (position/immediate/relative modes, opcode 9 adjusting `rb`).
Nothing here is new *logic* — it's the union of two guides you've already
read, which is the point: adding a capability to the VM (relative mode) and
changing its *execution discipline* (batch → single-step) are orthogonal
changes, and this day needs both at once but they don't interact.

One detail worth naming: stepping an already-halted machine just returns
`'halted` again rather than erroring —

```racket
(define (vm-step! machine)
  (if (vm-halted? machine)
      'halted
      ...))
```

— which is what lets the driving loop below call `run-to-outputs!`
unconditionally on every cycle without a separate "are we done?" check: the
very next step after halting reports it, and the loop just notices it got
fewer than 2 outputs.

### `run-to-outputs!` — supply input lazily, on block

```racket
(define (run-to-outputs! machine camera)
  (let loop ([outs '()])
    (match (vm-step! machine)
      ['blocked (vm-enqueue! machine camera) (loop outs)]
      ['ran (loop outs)]
      [`(output ,n)
       (define outs* (cons n outs))
       (if (= 2 (length outs*)) (reverse outs*) (loop outs*))]
      ['halted (reverse outs)])))
```

This is the piece that makes the "input depends on prior output" cycle
work: `camera` is computed by the *caller* from the current hull state, but
it's only handed to the machine at the exact instant `vm-step!` reports
`'blocked` — not pushed ahead of time the way Day 7's phase settings were.
Day 7 could pre-populate the input queue because the amplifier's inputs
(phase, then one signal) were both known before the machine started; here
the second input (the *next* camera reading) doesn't exist yet — it depends
on where this cycle's still-unknown output moves the robot. Pull, not push.

`match` here is Racket's general pattern-matching form (first introduced on
[Day 4](day04_function_guide.md) for structural patterns); the
`` `(output ,n)`` clause is a quasiquote pattern that both recognizes the
two-element tagged list and binds `n` to its second element in one line —
the same destructuring style `vm-step!`'s own return value uses when a
caller consumes it.

### `dirs` / `turn` / `step-forward` — the compass, as a 4-cycle

```racket
(define dirs (vector (cons 0 -1) (cons 1 0) (cons 0 1) (cons -1 0)))

(define (turn dir signal) (modulo (+ dir (if (zero? signal) 3 1)) 4))

(define (step-forward pos dir)
  (define d (vector-ref dirs dir))
  (cons (+ (car pos) (car d)) (+ (cdr pos) (cdr d))))
```

Facing is an index `0..3` into `dirs`, ordered **clockwise**:
`0`=up, `1`=right, `2`=down, `3`=left — the identical convention
[Day 10](day10_function_guide.md)'s laser-angle sweep used, including the
same "y grows downward, so *up* is `(0 . -1)`" screen-coordinate choice.
Turning is addition mod 4: left (signal `0`) is `-1 mod 4`, written as `+3`
to stay in `0..3` without a negative intermediate; right (signal `1`) is
`+1`. `step-forward` reads as "look up the current facing's unit vector,
add it to the position" — no branching on which direction, because the
vector already encodes the answer.

- **Rust analogue:** the vector-of-deltas-plus-modular-index trick is
  identical to a `[(i32, i32); 4]` table with `(facing + delta) % 4` — the
  same "avoid a 4-armed match on direction" move, and it composes the same
  way with `wrapping` arithmetic if a real embedded/hot-loop version needed
  it (not needed at `usize`-friendly n=4 here).

### `paint-hull` — the grid, as a hash that only remembers what was painted

```racket
(define (paint-hull program [start-color 0])
  (define machine (make-vm program))
  (define start (cons 0 0))
  (let loop ([pos start] [dir 0] [panels (hash)])
    (define default (if (equal? pos start) start-color 0))
    (define outs (run-to-outputs! machine (hash-ref panels pos default)))
    (if (< (length outs) 2)
        panels
        (let* ([panels* (hash-set panels pos (car outs))]
               [dir*     (turn dir (cadr outs))])
          (loop (step-forward pos dir*) dir* panels*)))))
```

The subtlety the puzzle prose itself flags — *"it painted its starting panel
twice, but that panel is still only counted once; it also never painted the
panel it ended on"* — is handled by *not* pre-seeding the hash with the
starting position. `panels` starts as the **empty** hash; a position gets a
key only when the robot's program explicitly emits a paint color for it via
`hash-set`. Reading an unvisited panel's color falls back to a `default`
through `hash-ref`, which is `0` (black) everywhere *except* at `start`,
where it's `start-color` — Part 1's hull starts all black (the parameter's
default value, `0`), Part 2's starts with just that one panel white (`1`).
Two consequences fall out for free, matching the prose's own callouts (and
holding regardless of `start-color`, since it only ever affects the very
first read):

- **Revisiting a panel just overwrites its value under the same key** — so
  a twice-painted starting panel is one entry in the hash, not two.
- **The panel the robot is standing on when the program halts is never
  painted** (the loop only calls `hash-set` after a *complete* output
  pair), so it has no key unless an earlier cycle happened to paint it.

`part1` is then a one-liner:

```racket
(define (part1 program) (hash-count (paint-hull program)))
```

`hash-count` is exactly "how many distinct positions were ever painted" —
the puzzle's question, verbatim.

### `render` — bounding box over the lit cells, `part2` is a render of a repaint

```racket
(define (render panels)
  (define whites (for/list ([(pos color) (in-hash panels)] #:when (= color 1)) pos))
  (cond
    [(null? whites) ""]
    [else
     (define xs (map car whites))
     (define ys (map cdr whites))
     (define x0 (apply min xs)) (define x1 (apply max xs))
     (define y0 (apply min ys)) (define y1 (apply max ys))
     (string-join
      (for/list ([y (in-range y0 (add1 y1))])
        (list->string
         (for/list ([x (in-range x0 (add1 x1))])
           (if (= 1 (hash-ref panels (cons x y) 0)) #\# #\.))))
      "\n")]))

(define (part2 program) (render (paint-hull program 1)))
```

Same shape as [Day 10](day10_function_guide.md)'s `vaporization-order` in
spirit — a `for/list` over `in-hash` pulls out just the coordinates that
matter (here, `color = 1`) — but the rendering itself is closer to
[Day 8](day08_function_guide.md)'s pixel decode: walk a rectangle row by row,
column by column, and ask a lookup "what's here?" `min`/`max` over the white
coordinates give the *tightest* box that contains every lit pixel, so the
picture has no wasted blank border; black panels the robot painted outside
that box (if any) are simply never visited by the two `for/range` loops —
correct, because a black pixel outside the letters carries no information
the human reading the code needs.

This is the same **no-OCR** stance the 2018 Haskell repo's Day 10 ("The
Stars Align") took on its own render-letters-for-a-human sub-problem: decode
a `#`/`.` picture of capital letters into the letters themselves is a
different, self-contained puzzle (font-matching / template OCR), and it is
*not* what Day 11 is asking. `part2`'s contract returns `string?`, not the
inferred word — the picture *is* the answer, and a human (here, Matt,
cross-referencing the rendered grid against the standard 4×6 AoC letter
font) reads off `PECKRGZL`.

---

## Tests (what's pinned and why)

[test/day11-test.rkt](../../test/day11-test.rkt) deliberately does **not**
re-test `vm-step!`'s opcode semantics — that's Day 9's job, already pinned
by the quine and friends, and `vm-step!` here is a mechanical transplant of
that same `val`/`addr` logic into Day 7's stepper shape. Instead it isolates
the parts that are actually new this day:

**The turn/move/paint bookkeeping**, with a **scripted** Intcode program
that ignores its camera input and just emits the puzzle prose's own 7
example decision cycles: `(1,0) (0,0) (1,0) (1,0) (0,1) (1,0) (1,0)`.

1. `(hash-count panels)` is `6` — the prose's own headline number.
2. **The exact hash**, not just its size — pins the turn/move convention
   itself (a left/right or up/down sign flip would still often land on 6
   *distinct* panels by coincidence, but would almost certainly disagree on
   *which* ones).
3. **`(0 . -1)`, the panel the robot ends on, has no key** — the prose's
   second callout, and a direct check that painting truly happens
   *before* the move, not after.

**The `start-color` default**, with a *different* one-cycle program,
`3,100,4,100,104,0,99`, that (unlike the scripted walkthrough above) actually
*reads* its camera input and echoes it straight back out as the paint color.
Run with the default `start-color` it paints `(0 . 0)` black; run with
`start-color = 1` it paints the same panel white — the only way the two
calls can disagree is if the `default` expression inside `paint-hull` is
really reaching `start-color` on that first read.

**`render`**, standalone against a 3-cell synthetic hash — confirms the
bounding box tracks *only* the white cells (a stray black-painted cell
outside that box must not widen the picture), and that an empty hash (no
white panels) renders as `""` rather than erroring.

Then the real input: `part1 = 2129`, and `part2` pinned as the **exact**
rendered picture (all 6 rows), not just the inferred `PECKRGZL` — the
stronger-regression-test choice [Day 10 (2018)](../../../aoc2018_Haskell/Problem_Statements/days/day10_function_guide.md)
made for the identical situation: a `render` bug that drops or shifts one
cell could still produce a wrong-but-plausible-looking 8-letter code, but it
can't hide from a full-picture diff. Both are independently cross-checked by
the Python companion above.

`raco test test/day11-test.rkt` → 9 tests passed.

---

## Benchmarks

```
| Day | Parse (ms) | Part 1 (ms) | Part 2 (ms) | Total (ms) |
|-----|-----------|-------------|-------------|------------|
| 11  | 0.5500    | 24.0750     | 1.5750      | 26.2000    |
```

Mean over **200** iterations. **Parse** is the familiar comma-split into a
vector, in line with every other Intcode day. **Part 1 (24 ms)** is
`paint-hull` single-stepping the robot's program to completion on an
all-black hull — likely thousands of `vm-step!` calls (each a decode + a
mode-aware operand resolution) plus the hash bookkeeping, the same
ballpark as [Day 9](day09_function_guide.md)'s Part 1 test-mode run but
somewhat heavier for driving an actual spatial simulation rather than a
single diagnostic pass. **Part 2 (1.6 ms) is over 15× cheaper than Part 1**
despite doing strictly more work (`paint-hull` again, plus `render`) — the
tell is that starting on a white panel changes the robot's *decisions* from
the very first cycle onward, and on this input it evidently steers the
program down a much shorter path to a halt (a smaller registration-code
hull to paint) than the meandering, apparently-unbounded pattern the
all-black Part 1 run produces. `render` itself is noise next to either
simulation: one pass over a few hundred hash keys to find the bounding box,
then a `4×6`-ish grid of lookups.

---

## If I were writing this in Rust

```rust
use std::collections::HashMap;

#[derive(Default)]
struct Vm {
    mem: HashMap<i64, i64>,
    ip: i64,
    rb: i64,
    inputs: std::collections::VecDeque<i64>,
    halted: bool,
}

enum Step { Blocked, Ran, Output(i64), Halted }

impl Vm {
    fn step(&mut self) -> Step {
        if self.halted { return Step::Halted; }
        let instr = self.mem.get(&self.ip).copied().unwrap_or(0);
        let op = instr % 100;
        let modes = instr / 100;
        let mode = |n: i64| (modes / 10i64.pow(n as u32 - 1)) % 10;
        let val = |vm: &Self, n: i64| {
            let raw = vm.mem.get(&(vm.ip + n)).copied().unwrap_or(0);
            match mode(n) {
                1 => raw,
                2 => vm.mem.get(&(vm.rb + raw)).copied().unwrap_or(0),
                _ => vm.mem.get(&raw).copied().unwrap_or(0),
            }
        };
        let addr = |vm: &Self, n: i64| {
            let raw = vm.mem.get(&(vm.ip + n)).copied().unwrap_or(0);
            if mode(n) == 2 { vm.rb + raw } else { raw }
        };
        match op {
            3 => match self.inputs.pop_front() {
                None => Step::Blocked,
                Some(n) => { let a = addr(self, 1); self.mem.insert(a, n);
                             self.ip += 2; Step::Ran }
            },
            4 => { let n = val(self, 1); self.ip += 2; Step::Output(n) }
            9 => { self.rb += val(self, 1); self.ip += 2; Step::Ran }
            99 => { self.halted = true; Step::Halted }
            // 1/2/5/6/7/8 identical to Day 9's Rust sketch
            _ => unreachable!(),
        }
    }
}

fn paint_hull(program: &[i64]) -> HashMap<(i64, i64), i64> {
    let mut vm = Vm { mem: program.iter().enumerate()
        .map(|(i, &v)| (i as i64, v)).collect(), ..Default::default() };
    const DELTAS: [(i64, i64); 4] = [(0, -1), (1, 0), (0, 1), (-1, 0)];
    let (mut pos, mut facing) = ((0i64, 0i64), 0usize);
    let mut panels: HashMap<(i64, i64), i64> = HashMap::new();
    loop {
        let camera = *panels.get(&pos).unwrap_or(&0);
        let mut outs = Vec::with_capacity(2);
        loop {
            match vm.step() {
                Step::Blocked => vm.inputs.push_back(camera),
                Step::Ran => {}
                Step::Output(n) => { outs.push(n); if outs.len() == 2 { break; } }
                Step::Halted => return panels,
            }
        }
        panels.insert(pos, outs[0]);
        facing = (facing + if outs[1] == 0 { 3 } else { 1 }) % 4;
        let (dx, dy) = DELTAS[facing];
        pos = (pos.0 + dx, pos.1 + dy);
    }
}

fn render(panels: &HashMap<(i64, i64), i64>) -> String {
    let whites: Vec<(i64, i64)> = panels.iter()
        .filter(|&(_, &c)| c == 1).map(|(&p, _)| p).collect();
    let (x0, x1) = (whites.iter().map(|p| p.0).min().unwrap(),
                     whites.iter().map(|p| p.0).max().unwrap());
    let (y0, y1) = (whites.iter().map(|p| p.1).min().unwrap(),
                     whites.iter().map(|p| p.1).max().unwrap());
    (y0..=y1).map(|y| (x0..=x1).map(|x|
        if *panels.get(&(x, y)).unwrap_or(&0) == 1 { '#' } else { '.' })
        .collect::<String>())
        .collect::<Vec<_>>().join("\n")
}
```

The correspondences worth seeing:

- **`enum Step` ↔ the four symbols `vm-step!` returns.** Racket leans on
  runtime tags (`'blocked`, `` `(output ,n)``) that `match` destructures;
  Rust makes the same four-way protocol a real sum type the compiler
  exhaustiveness-checks — the `_ => unreachable!()` is where Rust would
  force you to actually write out opcodes 1/2/5/6/7/8, where Racket's
  `case` silently falls through to `else` if a case is missing.
- **`HashMap<i64, i64>` memory ↔ the boxed grow-on-write vector.** Rust's
  sparse map matches Python's `defaultdict(int)` more than Racket's
  doubling vector does — three different "infinite memory" encodings for
  the same requirement, chosen per language's comfortable idiom.
- **`VecDeque::pop_front` ↔ `(car inputs)` / `(cdr inputs)`.** Both are
  FIFO; Rust's is O(1) where Racket's cons-list pop is technically O(1) too
  (just `cdr`), so no asymptotic difference here — only ergonomics.
- **The borrow checker bites on the closures.** `val`/`addr` need to borrow
  `self` immutably while `step` holds `&mut self` — the sketch above
  threads `vm: &Self` explicitly through the closures to route around it;
  a real implementation would more likely inline the match or use methods
  taking `&self` directly. This is one of the days where Racket's mutable
  struct + nested closures reads *more* directly than the Rust translation,
  because Rust's aliasing rules charge rent that a single-threaded Racket
  program never pays.

---

## What's next

Day 11 closes out this Intcode arc's *robot* variant — the VM driving a
stateful world instead of a single diagnostic run. **Day 12** (The N-Body
Problem) leaves Intcode behind again for a physics simulation: gravity and
velocity updates on a handful of moons, with Part 2 almost certainly wanting
the same "find the repeat period" instinct as
[Day 10 (2018)](../../../aoc2018_Haskell/Problem_Statements/days/day10_function_guide.md)'s
convergence search, or a per-axis independence trick given how the sample
inputs are typically structured. See the
[summary table](summary_2019.md) for the running scoreboard.
