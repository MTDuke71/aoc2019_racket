# Day 9 — Sensor Boost (function guide)

> **Historical note.** This guide annotates the frozen Racket solution
> ([src/day09.rkt](../../src/day09.rkt)), written when this repo was the
> Racket leg of a language rotation. The repo is Python-only now and the
> Racket is frozen, not deleted -- see the [README](../../README.md). The
> guide is left as it was and remains accurate about the code it describes.

> The **Intcode finale**. [Day 2](day02_function_guide.md) was a three-opcode
> adder, [Day 5](day05_function_guide.md) grew it into a CPU with parameter
> modes and control flow, [Day 7](day07_function_guide.md) ran five copies in
> a feedback loop — and Day 9 adds the one feature that makes the machine
> *complete*: **relative mode**. A third addressing mode (`2`) plus a movable
> **relative base** (opcode `9`), and the BOOST program certifies the
> computer and emits its keycode. The lesson isn't the feature, it's *where
> the feature lands*: adding an addressing mode touches only the
> operand-resolution seam (`val` / `addr`) and leaves all eight opcode
> handlers byte-for-byte unchanged. That orthogonality is the payoff of the
> decode discipline Day 5 set up — and the heart of this guide.

## The puzzle in one paragraph

The BOOST program refuses to run until the machine proves it's a *complete*
Intcode computer, which means one missing capability: **relative mode**.
Parameter mode `2` behaves like position mode (the parameter names an
address) except the address is offset by a **relative base** that starts at
`0` and is moved by the new opcode **`9 p`** (adjust the relative base by
`p`). Relative mode works for both reads *and* writes. The machine also
needs **memory beyond the loaded program** (reads as `0`, freely writable)
and **arbitrary-precision integers** (some early BOOST checks overflow 32
bits). **Part 1** runs BOOST in test mode (input `1`); a correct machine
reports no faults and emits exactly one value, the BOOST keycode. **Part 2**
runs it in sensor-boost mode (input `2`) and emits the distress-signal
coordinates. Each part is a single output.

---

## The algorithm in Python

Day 9 is *interpreter-flavored* (like [Day 5](day05_function_guide.md)), so
the Python companion ([python/day09.py](../../python/day09.py)) is the
fastest way to see how small the change is. The entire delta from Day 5 is
in operand resolution plus one opcode:

```python
rb = 0                                  # relative base — the only new state

def val(n):                             # read operand n, mode-aware
    raw = mem[ip + n]
    m = mode(n)
    if m == 1: return raw               # immediate
    if m == 2: return mem[rb + raw]     # relative   <-- the one new line
    return mem[raw]                     # position

def addr(n):                            # write target: position OR relative
    raw = mem[ip + n]
    return rb + raw if mode(n) == 2 else raw    # <-- the mirror

# ... and in the dispatch:
elif op == 9:  rb += val(1); ip += 2    # adjust relative base
```

`mem` becomes a `defaultdict(int)` (read-past-program-as-0 for free) and
Python ints are already bignums (big numbers for free). The eight Day 5
handlers — add, multiply, input, output, two jumps, two comparisons — are
*untouched*. Hold that picture: the Racket version is the same, with `rb`
threaded as a loop accumulator beside `ip`.

---

## Operand resolution is the orthogonal axis

This is the conceptual centerpiece, and Day 9 is where it becomes provable.

Look at how the opcode handlers are written, in both Day 5 and Day 9: they
speak **only in values**. Opcode `1` is "store `(val 1) + (val 2)` at
`(addr 3)`." It never mentions position, immediate, or relative; it never
indexes memory directly. All the mode-awareness is funneled into two
helpers:

- **`val n`** — *read* operand `n`, consulting its mode digit.
- **`addr n`** — resolve operand `n` as a *write target*.

That funnel means the machine grows along **two independent axes**:

| Axis | What it is | Where it lives |
|------|-----------|----------------|
| **opcodes** | what operations exist (`+`, `*`, jump, …) | the `case` arms |
| **addressing modes** | how an operand names its data | `val` / `addr` |

Day 5 had two modes (position, immediate) and eight opcodes. Day 9 adds a
*mode* without touching a single *opcode*. Here is the complete diff in
`val`, Day 5 → Day 9:

```racket
;; Day 5 — two modes, a binary choice
(define (val n)
  (define raw (intcode-ref mem (+ ip n)))
  (if (= 1 (modulo (quotient modes (expt 10 (sub1 n))) 10))
      raw                           ; immediate
      (intcode-ref mem raw)))       ; position

;; Day 9 — three modes, one new clause
(define (val n)
  (define raw (intcode-ref mem (+ ip n)))
  (case (mode n)
    [(0) (intcode-ref mem raw)]          ; position
    [(1) raw]                            ; immediate
    [(2) (intcode-ref mem (+ rb raw))])) ; relative  <-- added
```

The binary `if` becomes a three-way `case`, and the genuinely *new* code is
the single `[(2) …]` clause. The mirror in `addr` is one conditional:

```racket
;; Day 5: writes are always position — return the raw cell
(define (addr n) (intcode-ref mem (+ ip n)))

;; Day 9: writes are position OR relative (never immediate)
(define (addr n)
  (define raw (intcode-ref mem (+ ip n)))
  (if (= 2 (mode n)) (+ rb raw) raw))    ; <-- relative write target
```

And opcode `9` is one new `case` arm. **That is the entire feature.** Eight
handlers, zero edits.

Two structural facts fall out of this seam, worth banking:

- **"Writes are never immediate" is encoded by construction.** A write
  target is resolved by `addr`, which has no immediate branch — there is no
  place to put one, because an immediate write is meaningless (you can't
  store into a literal). The spec rule isn't checked at runtime; it's
  *unrepresentable* because write targets never pass through `val`. This is
  the kind of "make illegal states unrepresentable" move Rust's type system
  is prized for, achieved here just by routing reads and writes through
  different helpers.
- **The relative base is CPU state, threaded like the program counter.**
  `rb` rides in the loop next to `ip` — both are accumulators updated by
  tail call, never mutated. Opcode `9` is the *only* writer of `rb` (it
  recurs with `(+ rb (val 1))`); every other arm just passes `rb` through
  unchanged, exactly as they pass `ip` through when they don't jump.

**The clox anchor.** This is the same factoring as Crafting Interpreters'
bytecode VM, where `READ_BYTE()` and `READ_CONSTANT()` are macros pulled
*out* of the big `run()` switch. The opcode cases call `READ_CONSTANT()`
without caring how a constant is decoded; change the constant encoding (e.g.
`OP_CONSTANT_LONG`'s 24-bit operand) and only the macro changes, not the
arithmetic opcodes. `val`/`addr` are this VM's `READ_*` macros, and relative
mode is its `OP_CONSTANT_LONG`: a decode change, quarantined.

**The Rust framing.** In Rust you'd make the axes explicit in the types:

```rust
enum Mode { Position, Immediate, Relative }

impl Cpu {
    fn val(&self, n: i64) -> i64 {
        let raw = self.mem[self.ip + n];
        match self.mode(n) {
            Mode::Immediate => raw,
            Mode::Position  => self.mem[raw],
            Mode::Relative  => self.mem[self.rb + raw],
        }
    }
    fn addr(&self, n: i64) -> i64 {           // no Immediate arm exists
        let raw = self.mem[self.ip + n];
        match self.mode(n) {
            Mode::Relative => self.rb + raw,
            _              => raw,
        }
    }
}
```

Adding `Relative` to the `enum` makes the compiler point at exactly the two
`match`es that must grow — `val` and `addr` — and *nowhere else*. The
exhaustiveness check turns "the seam is the only thing that changes" from a
claim into a compile error if you forget. That's the orthogonality made
mechanical.

---

## The Day 9 code, form by form

### `run/inputs` — the same loop, one more accumulator

```racket
(define (run/inputs program inputs)
  (define mem (d05:intcode-mem program))
  (let loop ([ip 0] [rb 0] [outs '()] [pending inputs])
    (define instr (d05:intcode-ref mem ip))
    (define op    (modulo instr 100))
    (define modes (quotient instr 100))
    (define (mode n) (modulo (quotient modes (expt 10 (sub1 n))) 10))
    (define (val n) ...)   ; mode-aware read (shown above)
    (define (addr n) ...)  ; position-or-relative write target (shown above)
    (case op
      [(1)  (d05:intcode-set! mem (addr 3) (+ (val 1) (val 2))) (loop (+ ip 4) rb outs pending)]
      ;; ... opcodes 2–8 exactly as Day 5, each threading rb unchanged ...
      [(9)  (loop (+ ip 2) (+ rb (val 1)) outs pending)]   ; adjust relative base
      [(99) (reverse outs)]
      [else (error 'run/inputs "unknown opcode ~a at position ~a" op ip)])))
```

- **`rb` as a loop variable.** This is the [Day 1](day01_function_guide.md)
  named-`let` pattern doing CPU state: `ip` and `rb` are both bindings the
  loop carries forward. Functional, no mutable register — the same reason
  Day 5 threads `ip` instead of a `set!`.
- **`mode` extracted.** Day 5 inlined the mode arithmetic inside `val`; with
  three modes it's worth a name. `(modulo (quotient modes (expt 10 (sub1 n))) 10)`
  is "the n-th digit of `modes`" — parameter 1 is the ones digit, parameter
  2 the tens, parameter 3 the hundreds. (Decode reminder from
  [Day 5](day05_function_guide.md): the instruction is `modes·100 + op`.)
- **Opcode 9** recurs with `rb` updated and `ip` advanced by 2 (one opcode +
  one operand). Every other arm passes `rb` straight through.

### Big memory and big numbers — already handled by Day 5's primitives

Day 9 requires "memory much larger than the program, zero-filled, freely
writable" and "large numbers." Both were already paid for:

- **`d05:intcode-mem` / `intcode-ref` / `intcode-set!`** (introduced for
  [Day 7](day07_function_guide.md)) box a growable vector: reads out of
  bounds return `0`, writes past the end grow the vector (doubling, so
  amortized O(1)), and negative addresses error. Relative mode is the first
  day that *needs* this — BOOST uses high addresses as scratch via the
  relative base — but the machinery predates it. Day 9 reuses it verbatim;
  the only new memory behavior is *which* addresses get touched, computed by
  the new `addr`.
- **Bignums for free.** Racket integers are arbitrary precision, so
  `1125899906842624` and 16-digit products need no special handling — the
  `(vectorof exact-integer?)` contract already admits them. (In a fixed-width
  language this is the day you'd reach for `i64`/`int64_t` and hope it fits;
  the spec's "support for large numbers" check exists precisely to catch
  machines that used 32-bit cells.)

### `part1` / `part2` — single-output diagnostic

```racket
(define (boost program input) (last (run program input)))
(define (part1 program) (boost program 1))   ; test mode
(define (part2 program) (boost program 2))   ; sensor-boost mode
```

Same shape as Day 5's `diagnostic`: a correct machine emits exactly one
value, and `last` reads it (defensive against a faulty machine that would
emit fault codes first). Part 1's input `1` is "run the self-test"; Part 2's
input `2` is "do the real sensor boost." The program branches on that single
input internally — the same self-selecting-input pattern Day 5's diagnostic
used (see [day05_disassembly.md](day05_disassembly.md)).

---

## The quine as a test oracle

The spec hands us a gift: `109,1,204,-1,1001,100,1,100,1008,100,16,101,1006,101,0,99`
is a **quine** — it outputs an exact copy of its own source. That single
example is the strongest correctness test the day has, because reproducing
itself exercises nearly the whole machine at once:

- **relative reads** (`204,-1` outputs `mem[rb-1]`),
- **relative-base motion** (`109,1` and the loop's `1006,101,0`),
- **arithmetic into memory** (`1001,100,1,100` increments a pointer),
- **a comparison + conditional jump** (`1008`/`1006` form the loop test),
- **grow-on-write memory** (address `100`+ is past the 16-cell program),

and it only terminates with the right output if *all* of them agree. A quine
is to an interpreter what a round-trip (`decode(encode(x)) == x`) is to a
codec: a single assertion that pins the whole pipeline. The test suite leans
on it as check #1, with the 16-digit multiply and the large-immediate
passthrough covering the "big numbers" axis the quine doesn't stress.

> **Aside — why quines exist.** A program that prints itself sounds
> paradoxical but is a standard consequence of Kleene's recursion theorem:
> any Turing-complete system admits a self-reproducing program. AoC's quine
> is hand-built to also be a *compact regression test* — it's the smallest
> program that uses relative mode non-trivially, which is why the puzzle
> leads with it.

---

## Tests (what's pinned and why)

[test/day09-test.rkt](../../test/day09-test.rkt) pins four layers:

1. **The three spec examples** — the quine reproduces itself; the
   `1102,…` program outputs a verified-16-digit number; the
   `104,1125899906842624,99` passthrough emits the large immediate.
2. **Opcode 9 / relative base in isolation** — `109,1,204,-1,99` moves the
   base then outputs a relative cell (`109`), and a hand-built
   `109,5,21101,7,8,0,204,0,99` confirms a *relative write target* resolves
   through `rb`.
3. **Backward compatibility** — a Day 5 position/immediate program
   (`3,9,8,9,10,9,4,9,99,-1,8`, "input == 8?") still returns `1`/`0` through
   the extended VM, proving the new mode didn't perturb the old ones.
4. **The real answers** — `part1 = 4080871669`, `part2 = 75202`.

`raco test` runs the `module+ test` submodule; 10 checks, all green.

---

## Benchmarks

```
| Day | Parse (ms) | Part 1 (ms) | Part 2 (ms) | Total (ms) |
|-----|-----------|-------------|-------------|------------|
| 09  | 0.8240    | 0.1000      | 53.3680     | 54.2920    |
```

The mean is over **500** iterations, and the row tells a striking story —
**Part 2 is ~530× Part 1**:

- **Parse** splits ~1000 comma-separated integers into a vector —
  sub-millisecond, same kernel as Days 2/5/7.
- **Part 1** runs BOOST's *self-test* (input `1`): it walks its opcode
  checks, finds the machine complete, and emits the keycode in ~0.1 ms — a
  few thousand instructions, each a fetch / decode / one or two `val` calls.
  The grow-on-write memory doubles a handful of times early, then stays put.
- **Part 2** runs the actual *sensor boost* (input `2`), and that 53 ms says
  the program does real algorithmic work behind the single input branch — the
  self-test was just the warm-up. Same machine, same memory; the only
  difference is which code path that one input selects, and the boost path is
  a genuinely heavy computation (the "problem within the problem" — BOOST is
  hiding a real algorithm we never have to understand, only execute).
  [day09_disassembly.md](day09_disassembly.md) takes the program apart and
  identifies that algorithm: a naive tree recursion `T(n)=T(n-1)+T(n-3)` at
  `n=27`, run on a **stack frame addressed through the relative base** — the
  relative mode this day adds turns out to be a *calling convention*, and
  Part 2's cost is 37,119 unmemoized recursive calls.

There's no interpreter change that helps here — the cost is "interpret N
instructions," linear in the trace length, and Part 2's trace is simply huge.
The one real lever would be a faster *dispatch* (a jump table or a
precompiled instruction stream instead of re-decoding a linear `case` every
step); at this scale the idiomatic `case` is fine, and a precompile pass is
the kind of thing this guide sidebars rather than ships.

---

## If I were writing this in Rust

```rust
use std::collections::HashMap;

struct Cpu { mem: HashMap<i64, i64>, ip: i64, rb: i64 }

impl Cpu {
    fn new(program: &[i64]) -> Self {
        let mem = program.iter().enumerate()
            .map(|(i, &v)| (i as i64, v)).collect();
        Cpu { mem, ip: 0, rb: 0 }
    }
    fn get(&self, a: i64) -> i64 { *self.mem.get(&a).unwrap_or(&0) }
    fn mode(&self, n: i64) -> i64 { self.get(self.ip) / 10i64.pow(n as u32 + 1) % 10 }

    fn val(&self, n: i64) -> i64 {
        let raw = self.get(self.ip + n);
        match self.mode(n) { 1 => raw, 2 => self.get(self.rb + raw), _ => self.get(raw) }
    }
    fn addr(&self, n: i64) -> i64 {
        let raw = self.get(self.ip + n);
        if self.mode(n) == 2 { self.rb + raw } else { raw }
    }

    fn run(&mut self, inputs: &[i64]) -> Vec<i64> {
        let mut input = inputs.iter().copied();
        let mut out = Vec::new();
        loop {
            match self.get(self.ip) % 100 {
                1 => { let a = self.addr(3); self.mem.insert(a, self.val(1) + self.val(2)); self.ip += 4 }
                2 => { let a = self.addr(3); self.mem.insert(a, self.val(1) * self.val(2)); self.ip += 4 }
                3 => { let a = self.addr(1); self.mem.insert(a, input.next().unwrap()); self.ip += 2 }
                4 => { out.push(self.val(1)); self.ip += 2 }
                5 => self.ip = if self.val(1) != 0 { self.val(2) } else { self.ip + 3 },
                6 => self.ip = if self.val(1) == 0 { self.val(2) } else { self.ip + 3 },
                7 => { let a = self.addr(3); self.mem.insert(a, (self.val(1) <  self.val(2)) as i64); self.ip += 4 }
                8 => { let a = self.addr(3); self.mem.insert(a, (self.val(1) == self.val(2)) as i64); self.ip += 4 }
                9 => { self.rb += self.val(1); self.ip += 2 }
                99 => return out,
                op => panic!("unknown opcode {op} at {}", self.ip),
            }
        }
    }
}
```

The correspondences worth seeing:

- **`HashMap<i64,i64>` ↔ the boxed growable vector.** Both give
  read-as-0-past-the-end and writable-anywhere; the `HashMap` trades the
  vector's contiguity (and cache locality) for never having to resize or
  reason about bounds. On a sparse-high-address program either is fine; a
  dense one would favor the vector. (`i64` suffices for this input — but it's
  the spot where Racket's automatic bignums quietly insure you and Rust makes
  you choose.)
- **`&mut self` ↔ the threaded accumulators.** Rust mutates `ip`/`rb`
  in-place behind `&mut`; Racket threads them as loop arguments. Same state,
  opposite default — and the Racket version's "no mutation" is what lets
  [Day 7](day07_function_guide.md) snapshot a paused VM trivially.
- **`enum Mode` is the upgrade.** The `match self.mode(n)` above uses bare
  integers to stay close to the Racket; the *better* Rust (shown in the
  orthogonality section) names the modes in an `enum` so the compiler
  enforces that only `val`/`addr` know about them.

---

## What's next

Intcode rests for two days. **Day 10** (Monitoring Station) is pure
geometry — line-of-sight among asteroids, reduced fractions as direction
keys, and an angular sweep — no VM in sight. The complete machine built
today returns on **Day 11** (the hull-painting robot), where this exact
`run/inputs` drives a robot over a grid, and again on Days 13, 15, 17, 19,
21, 23, and 25 — every remaining Intcode puzzle embeds the computer finished
here. Banking the **operand-resolution seam** is the transferable win: when a
future machine grows an addressing mode or an opcode, you now know it lands
in exactly one place. See the [summary table](summary_2019.md) for the
running scoreboard.
