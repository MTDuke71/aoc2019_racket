# Day 7 — Amplification Circuit (function guide)

> **Historical note.** This guide annotates the frozen Racket solution
> ([src/day07.rkt](../../src/day07.rkt)), written when this repo was the
> Racket leg of a language rotation. The repo is Python-only now and the
> Racket is frozen, not deleted -- see the [README](../../README.md). The
> guide is left as it was and remains accurate about the code it describes.

> Five copies of the [Day 5](day05_function_guide.md) Intcode program run
> as amplifiers. Each copy reads its phase setting (0–4 or 5–9) and then
> input signals; outputs chain A→E (Part 1) or loop E→A (Part 2). The
> puzzle input is a **phase-indexed jump table** routing to ten modules —
> see [day07_disassembly.md](day07_disassembly.md) for the full take-apart.

## The puzzle in one paragraph

The input is the same Intcode program from Day 5. Five amplifiers each run
an independent copy (fresh memory). On startup each amp reads its **phase
setting** at the first `opcode 3`, then reads **input signals** at later
`opcode 3`s, and emits signals via `opcode 4`. **Part 1:** amps are wired
A→B→C→D→E in series; the first amp's signal input is `0`; try every
permutation of phases `0`–`4` (each used once) and take the maximum output
from E. **Part 2:** E's output loops back to A; phases are now `5`–`9`; all
five programs keep running (mutating their own memory) until all halt; the
answer is E's **last** output before halt. Brute force: `5! = 120`
permutations per part.

---

## The algorithm in Python

Day 7 is *algorithm-flavored* — the puzzle is really "how do you wire I/O
between Intcode instances?" — so the Python companion
([python/day07.py](../../python/day07.py)) states both shapes first:

```python
def thruster_series(program, phases):
    signal = 0
    for phase in phases:
        signal = run_inputs(program[:], [phase, signal])[-1]
    return signal

def part1(program):
    return max(thruster_series(program, list(p)) for p in permutations(range(5)))

def part2(program):
    return max(thruster_feedback(program, list(p)) for p in permutations(range(5, 10)))
```

Part 1 is a **fold over the permutation**: seed `0`, each amp consumes
`[phase, incoming_signal]` and returns its final output. Part 2 is a
**round-robin scheduler** over five VMs that each `step` until they block
(need input), halt, or produce output — canonical name:
**cooperative multitasking** with blocking channels.

---

## Part 1: the series chain

```
  0 ──> [Amp A] ──> [Amp B] ──> [Amp C] ──> [Amp D] ──> [Amp E] ──> answer
         phase p0    phase p1    phase p2    phase p3    phase p4
```

For one permutation `[p0, p1, p2, p3, p4]`:

1. Copy the program; run amp A with inputs `[p0, 0]`; collect A's output.
2. Fresh copy; run amp B with `[p1, A_out]`; collect B's output.
3. … through E.

The Racket code is a `for/fold`:

```racket
(define (thruster-series program phases)
  (for/fold ([signal 0]) ([phase (in-list phases)])
    (amp-output program phase signal)))

(define (amp-output program phase signal)
  (last (d05:run/inputs program (list phase signal))))
```

`last` of the output list is E's thruster signal for that chain (each amp
emits once before halting on these inputs).

### `run/inputs` — the Day 5 upgrade

[Day 5](day05_function_guide.md)'s `run` took a single integer. Day 7's
amps read **twice** before doing work (phase, then signal), and Part 2 reads
many more times. `run/inputs` threads a `(listof exact-integer?)` through the
loop; each `opcode 3` pops the head:

```racket
[(3) (unless (pair? pending) (error ...))
     (intcode-set! mem (addr 1) (car pending))
     (loop (+ ip 2) outs (cdr pending))]
```

`run` is now `(run/inputs program (list input))` — Day 5's tests unchanged.

### Growable memory (`intcode-ref` / `intcode-set!`)

Several example programs (and your real input) write to addresses beyond the
initial program image — scratch cells like `mem[52]`, `mem[99999]`. The spec
says unread cells are `0` and the address space expands as needed. Day 5's
original fixed `vector` was fine for the diagnostic program; Day 7 adds:

```racket
(define (intcode-ref mem-box addr)
  ...)   ; out-of-range read → 0

(define (intcode-set! mem-box addr val)
  ...)   ; grow vector with zeros, then write
```

Memory lives in a `box` so the grow-and-replace step can update the
reference in place. Part 2's `vm` struct holds the same box across many
`vm-step!` calls.

---

## Part 2: the feedback loop

```
        ┌──────────────────────────────────────────┐
        v                                          │
  0 ──> [A] ──> [B] ──> [C] ──> [D] ──> [E] ───────┘
        p0      p1      p2      p3      p4
```

All five VMs start together. Amp A's input queue is seeded `[phase₀, 0]`; the
others get `[phaseᵢ]` only. The scheduler sweeps A→E each round; each amp
runs instructions until it **blocks** (empty queue at `opcode 3`), **halts**
(`opcode 99`), or **outputs** (`opcode 4` — route to the next amp, or from E
back to A and record the thruster value).

```racket
(struct vm (mem ip inputs halted?) #:mutable)

(define (vm-step! machine) ...)
```

`vm-step!` returns one of `'blocked`, `'ran`, `'halted`, or `` `(output ,n) ``.
The outer `thruster-feedback` loops until every `vm-halted?` is true.

**Load-bearing detail:** on output, stop stepping that amp for this sweep
(the inner `loop-amp` breaks). The next amp may now have data in its queue.
If a full sweep makes no progress and not everyone has halted → deadlock
(error).

Phases for Part 2: `(permutations '(5 6 7 8 9))` — not `0`–`4`.

### Token by token: `vm-step!`

Part 1's `run/inputs` is a tail-recursive loop that owns the whole machine
until halt. Part 2's `vm-step!` executes **one instruction** and returns a
tag telling the scheduler what happened — cooperative multitasking in
disguise. The decode (`op`, `modes`, `val`, `addr`) is identical to
[Day 5](day05_function_guide.md); only the **I/O model** and **stop
condition** change.

#### The `vm` struct — persistent process state

```racket
(struct vm (mem ip inputs halted?) #:mutable)
```

| Field | Role |
|-------|------|
| `mem` | `box?` of growable Intcode RAM — same `intcode-ref` / `intcode-set!` as Day 5; **persists** across steps |
| `ip` | Instruction pointer — survives between `vm-step!` calls (in `run/inputs` it was a `loop` argument) |
| `inputs` | **Queue** of pending values for `opcode 3` — e.g. `(list phase)` or `(list phase 0)` on amp A |
| `halted?` | Set on `opcode 99`; top-of-function guard prevents re-executing halt |

`#:mutable` generates `set-vm-ip!`, `set-vm-inputs!`, `set-vm-halted?!`, etc.
The struct is the process; `vm-step!` mutates it in place. The `!` suffix
follows Racket's mutation naming (`vector-set!`, `set-box!`).

**Rust analogue:** `struct Vm { mem: Vec<i64>, ip: usize, inputs: VecDeque<i64>, halted: bool }`.

#### Return protocol — four outcomes

| Return | Meaning | Scheduler (`loop-amp`) |
|--------|---------|------------------------|
| `'blocked` | `opcode 3`, input queue empty | Stop this amp; try others — **yield**, not error |
| `'ran` | Any insn that advanced `ip` without outputting | Tail-call `loop-amp` — amp keeps its time slice |
| `` `(output ,n) `` | `opcode 4` emitted `n` | Enqueue `n` on neighbour; **stop** this amp this sweep |
| `'halted` | Already halted, or just executed `99` | Stop this amp; mark sweep as progressed |

Think of this as a hand-rolled `enum Step { Blocked, Ran, Output(i64), Halted }`.

#### Setup — destructure, guard, decode

```racket
(define (vm-step! machine)
  (match-define (vm mem ip inputs halted?) machine)
  (if halted?
      'halted
      (let ()
        (define instr (d05:intcode-ref mem ip))
        (define op    (modulo instr 100))
        (define modes (quotient instr 100))
        (define (val n) ...)
        (define (addr n) (d05:intcode-ref mem (+ ip n)))
        (case op ...))))
```

| Token | What it does |
|-------|--------------|
| `(match-define (vm mem ip inputs halted?) machine)` | Destructure the struct. `mem` is the **box**, passed straight to `intcode-ref` / `intcode-set!` |
| `(if halted? 'halted …)` | Idempotent: a halted VM always returns `'halted` |
| `(let () …)` | One-instruction scope for `instr`, `op`, `val`, `addr` |
| `intcode-ref mem ip` | Fetch through the box; out-of-range read → `0` |
| `val` / `addr` | Same digit arithmetic as Day 5 — see that guide's token table |

#### The `case` arms — what differs from `run/inputs`

Opcodes `1`, `2`, `5`, `6`, `7`, `8` — compute or jump, bump `ip`, return
`'ran`. Unchanged from Day 5.

**Opcode 3 — the whole point of Part 2:**

```racket
[(3) (if (null? inputs)
         'blocked
         (begin
           (d05:intcode-set! mem (addr 1) (car inputs))
           (set-vm-inputs! machine (cdr inputs))
           (set-vm-ip! machine (+ ip 2))
           'ran))]
```

| Branch | Behaviour |
|--------|-----------|
| `(null? inputs)` | Return `'blocked` — scheduler runs other amps; resume when a neighbour enqueues |
| else | Pop queue head into `mem[addr(1)]`, `ip += 2`, return `'ran` |

In `run/inputs`, an exhausted input list is an **error**. Here it means
**wait for input** — the coroutine yield.

**Opcode 4 — yield with a value:**

```racket
[(4) (set-vm-ip! machine (+ ip 2))
     `(output ,(val 1))]
```

Returns the emitted value immediately (not `'ran`). The scheduler routes it
and breaks the inner loop — **one output per amp per sweep**.

**Opcode 99:**

```racket
[(99) (set-vm-halted?! machine #t)
      'halted]
```

#### How `thruster-feedback` consumes the return

```racket
(match (vm-step! machine)
  ['blocked (values progressed? thruster)]
  ['ran (loop-amp #t thruster)]
  ['halted (values #t thruster)]
  [`(output ,n)
   (if (= i 4)
       (begin (vm-enqueue! (list-ref vms 0) n) (values #t n))
       (begin (vm-enqueue! (list-ref vms (+ i 1)) n) (values #t thruster)))])
```

```
                 ┌─────────────┐
                 │  vm-step!   │
                 └──────┬──────┘
    ┌──────────────────┼──────────────────┐
    v                  v                  v
'blocked            'ran            `(output ,n)
(stop amp)      (loop-amp)      (enqueue, stop amp)
    │                  │                  │
    └──────────────────┴──────────────────┘
                  'halted → stop amp
```

- `'ran` → keep stepping this amp until block / output / halt
- `'blocked` → yield; another amp may unblock this one later in the sweep
- `` `(output ,n) `` → `vm-enqueue!` appends to neighbour's `inputs` (FIFO via `car`/`cdr` on next `opcode 3`); E's output also enqueues on amp A and updates the thruster candidate
- Outer loop repeats A→E until all `halted?` or deadlock (full sweep, zero progress)

#### `run/inputs` vs `vm-step!`

| | `run/inputs` (Part 1) | `vm-step!` (Part 2) |
|--|----------------------|---------------------|
| Granularity | Whole program to halt | One instruction |
| Input | Fixed list at start | Queue, grows mid-run via `vm-enqueue!` |
| Empty input | `error` | `'blocked` |
| Output | Collected in a list | Returned to scheduler immediately |
| `ip` / memory | Loop-local; fresh copy per amp | Persist in `vm` struct across the feedback loop |

---

## Brute-force permutations

```racket
(require racket/list)

(for/list ([phases (in-list (permutations '(0 1 2 3 4)))])
  (thruster-series program phases))
```

`permutations` generates all `5!` orderings lazily. `apply max` picks the
best thruster signal. No pruning — 120 runs is trivial at ~1 ms each.

**Rust analogue:** `itertools::permutations([0,1,2,3,4])` or nested loops;
same O(5! · program cost) brute force everyone uses.

---

## Benchmarks

| Phase | Mean (ms) |
|-------|-----------|
| Parse | 0.4400 |
| Part 1 | 21.0650 |
| Part 2 | 25.3400 |
| **Total** | **46.8450** |

Part 1: 120 series chains × one Intcode run each (~5 ms total). Part 2: 120
feedback simulations × five cooperative VMs (~25 ms). Parse is sub-millisecond.

Answers (your input): **Part 1 = 46014**, **Part 2 = 19581200**.

---

## If I were writing this in Rust

```rust
fn thruster_series(program: &[i64], phases: &[i64]) -> i64 {
    let mut signal = 0;
    for &phase in phases {
        signal = *run_inputs(program, &[phase, signal]).last().unwrap();
    }
    signal
}

fn part1(program: &[i64]) -> i64 {
    let mut best = 0;
    for perm in permutations(0..5) {
        best = best.max(thruster_series(program, &perm));
    }
    best
}
```

Part 2 in Rust usually becomes five `Intcode` structs in a `Vec`, each with
`ip`, `mem`, `input_queue: VecDeque<i64>`, and a `step(&mut self) -> Step`
enum (`Blocked | Output(i64) | Halted`). The scheduler is a `loop` over
`0..5` calling `step` until all `Halted`. The `box` for growable memory maps
to `Vec<i64>` with `resize` on write — same pattern as [Day 5's guide](day05_function_guide.md)
but you finally need it here.

**vs Haskell 2018:** no direct analogue — this is the Intcode trilogy, not a
graph day. Closest pattern from the 2018 repo is "simulator with explicit
state threaded through recursion" ([Day 15](day15_function_guide.md) style),
but the blocking I/O queues are the new idea.

---

## Possible optimization (sidebar)

The shipping source brute-forces all 120 permutations. For this input size
that is already fast (~46 ms total). If it ever mattered: **Johnson–Trotter**
doesn't help (you need every ordering's exact signal). Pruning only applies
if you can prove a partial chain cannot beat the current max — not obvious
for arbitrary Intcode programs. Leave brute force.

---

## What's next

Day 7 is Intcode's third growth spurt (chained I/O). **[Day 8](day08.md)**
is a break — image rendering, layers, and pixels. **[Day 9](day09_function_guide.md)**
returns to the VM with **relative mode** and a **relative base** register —
the last opcode/mode extension before the BOOST program. See the
[summary table](summary_2019.md) for the running scoreboard and
[Day 5](day05_function_guide.md) for the decode this day reuses unchanged.
