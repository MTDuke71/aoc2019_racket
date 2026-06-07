# Day 5 — Sunny with a Chance of Asteroids (function guide)

> The Intcode thread resumes. [Day 2](day02_function_guide.md) built a
> three-opcode adder; Day 5 grows it into a real little CPU with
> **parameter modes**, **I/O**, and **conditional control flow**. The
> durable lesson is the *decode*: an instruction is no longer a fixed
> 4-wide shape but a packed `modes·opcode` integer you take apart with digit
> arithmetic. Once the decode is right, the eight opcodes are a flat `case`.
> Everything here is reused verbatim by [Day 7](day07_function_guide.md)
> (amplifiers) and [Day 9](day09_function_guide.md) (relative mode).

## The puzzle in one paragraph

The input is an Intcode program (the "TEST" diagnostic). Three upgrades
over Day 2: **(1) parameter modes** — the opcode is just the rightmost two
digits of the instruction, and the digits above it are per-parameter modes
read right-to-left, where `0` means *position* (treat the parameter as an
address and dereference) and `1` means *immediate* (treat it as a literal);
**(2) I/O** — opcode `3` reads one input value and stores it, opcode `4`
emits a value; **(3) control flow** — `5`/`6` are jump-if-true /
jump-if-false (they *set* the instruction pointer), and `7`/`8` are
less-than / equals (they store a `0`/`1` flag). **Part 1** feeds input `1`
and reads the final output (the diagnostic code; every earlier output is a
`0` "test passed"). **Part 2** feeds input `5` and reads its single output.

---

## The algorithm in Python

Day 5 is *interpreter-flavored* (like [Day 2](day02_function_guide.md)), so
the Python companion ([python/day05.py](../../python/day05.py)) exists to
make the fetch/decode/execute loop legible before we read it in Racket. The
two new helpers are the whole story:

```python
def val(n):                              # nth parameter, mode-aware
    raw = mem[ip + n]
    mode = (mem[ip] // 10 ** (n + 1)) % 10
    return raw if mode == 1 else mem[raw]

def addr(n):                             # write target: ALWAYS position
    return mem[ip + n]
```

`mem[ip] % 100` is the opcode; `mem[ip] // 100` is the stack of mode digits.
`val(n)` picks the mode digit sitting above the opcode at position `n` (the
ones-digit-of-`//100` for parameter 1, the tens for parameter 2, …) and
either returns the cell literally (immediate) or dereferences it (position).
Write targets skip all of that — by spec a parameter an instruction *writes*
to is never immediate — so `addr(n)` just returns the raw cell. Hold these
two functions in mind; the Racket version is identical, with the dispatch as
a `case` instead of an `if/elif` ladder.

---

## Parameter modes: the decode is the day

In [Day 2](day02_function_guide.md), every instruction was opcode + three
operand *positions*, four cells wide, and decoding was "read the opcode,
read three addresses." Day 5 packs the addressing *modes* into the
instruction word itself, so the same operand can mean an address or a
literal depending on a digit you have to extract:

```
 instruction = 1002
   1002 % 100  = 2     -> opcode (multiply)
   1002 // 100 = 10    -> mode digits, read right-to-left:
       digit 0 (ones)     = 0  -> parameter 1 is POSITION
       digit 1 (tens)     = 1  -> parameter 2 is IMMEDIATE
       digit 2 (hundreds) = 0  -> parameter 3 is POSITION (the write target)
```

The canonical name for this is an **addressing mode** — the same concept a
real ISA uses when it distinguishes `LOAD R1, [R2]` (indirect) from
`LOAD R1, #5` (immediate). Day 5's modes are encoded *unary-positionally* in
the opcode word, which is why the extraction is pure base-10 digit
arithmetic.

### The `val` helper, token by token

```racket
(define (val n)
  (define raw (vector-ref mem (+ ip n)))
  (if (= 1 (modulo (quotient modes (expt 10 (sub1 n))) 10))
      raw
      (vector-ref mem raw)))
```

| Token | What it is | What it does here |
|-------|-----------|-------------------|
| `(vector-ref mem (+ ip n))` | the raw parameter cell | the `n`th cell after the opcode |
| `modes` | `(quotient instr 100)` | the instruction word with the 2-digit opcode stripped off |
| `(expt 10 (sub1 n))` | a power of ten | `1` for param 1, `10` for param 2, `100` for param 3 |
| `(quotient modes …)` | shift right by digits | drop the mode digits *below* parameter `n` |
| `(modulo … 10)` | take the ones digit | parameter `n`'s mode digit, isolated |
| `(if (= 1 …) raw (vector-ref mem raw))` | the mode switch | `1` → use the literal; `0` → dereference as an address |

The pair `(modulo (quotient x p) 10)` is the **"extract one base-10 digit"**
idiom — `quotient` shifts the digit you want into the ones place, `modulo`
chops everything above it. You'll see the same two-step in any code that
unpacks a packed integer (and again on [Day 9](day09_function_guide.md),
where mode `2` joins the switch).

- **Rust analogue:** `let mode = (instr / 10i64.pow(n as u32 + 1)) % 10;`
  then `if mode == 1 { raw } else { mem[raw as usize] }`. Identical digit
  arithmetic; Rust just makes the `i64`/`usize` cast explicit.

### Why `addr` doesn't consult the mode

```racket
(define (addr n) (vector-ref mem (+ ip n)))
```

A write target is *always* a position by the puzzle's rule ("parameters an
instruction writes to will never be in immediate mode"), so `addr` returns
the raw cell unconditionally — it's the address to store *into*, never a
value. Keeping `val` and `addr` as separate helpers makes each opcode line
read as "values in, address out," and quietly encodes that rule in the type
of access rather than a runtime check.

---

## The dispatch: a variable-width `case`

```racket
(case op
  [(1)  (vector-set! mem (addr 3) (+ (val 1) (val 2))) (loop (+ ip 4) outs)]
  [(2)  (vector-set! mem (addr 3) (* (val 1) (val 2))) (loop (+ ip 4) outs)]
  [(3)  (vector-set! mem (addr 1) input)               (loop (+ ip 2) outs)]
  [(4)  (loop (+ ip 2) (cons (val 1) outs))]
  [(5)  (loop (if (not (zero? (val 1))) (val 2) (+ ip 3)) outs)]
  [(6)  (loop (if (zero? (val 1))       (val 2) (+ ip 3)) outs)]
  [(7)  (vector-set! mem (addr 3) (if (< (val 1) (val 2)) 1 0)) (loop (+ ip 4) outs)]
  [(8)  (vector-set! mem (addr 3) (if (= (val 1) (val 2)) 1 0)) (loop (+ ip 4) outs)]
  [(99) (reverse outs)]
  [else (error 'run "unknown opcode ~a at position ~a" op ip)])
```

Three things changed shape from Day 2's loop:

1. **Instruction width is per-opcode.** Arithmetic and compare ops are
   4-wide (`ip+4`), I/O ops are 2-wide (`ip+2`), and jumps don't advance by
   a fixed amount *at all* — they either set `ip` to a computed target or
   fall through to `ip+3`. Day 2 could hard-code `+4`; here each `case` arm
   owns its own pointer math. This is the "the instruction pointer should
   increase by the number of values in the instruction" rule made literal.

2. **Jumps are just a different next-`ip`.** Because the loop is
   tail-recursive on `ip`, a jump is not a special control construct — it's
   an ordinary `(loop target outs)` where `target` is computed by an `if`.
   "Set the instruction pointer" and "advance the instruction pointer" are
   the same operation (`loop`) with different arguments. That's the payoff
   of modelling the PC as a loop variable rather than mutating a register.

3. **Output threads through the accumulator.** `outs` is the second loop
   variable, and opcode `4` is the only arm that grows it — `(cons (val 1)
   outs)`. We cons onto the front (cheap) and `reverse` once at halt, the
   same front-build-then-reverse pattern as
   [Day 4](day04_function_guide.md)'s run-length encoder. Input, by
   contrast, is a single fixed value `input` that opcode `3` stores
   wherever it's told — sufficient because the TEST program reads input
   exactly once (see *What's next* for when this has to become a queue).

- **Haskell precedent:** Day 2's note about `case`-over-`match` applies
  here too — we're dispatching on a small set of integer tags, which is
  exactly `case`'s job. The Haskell Intcode in the 2018-style repos would
  pattern-match the opcode in a `case op of` with guards; same structure.

---

## The problem within the problem: the input is a unit-test suite

It's worth pausing on *what the diagnostic program actually is*. Part 1's
prose ("for each test it outputs how far the result was from expected, where
`0` means success") is describing a **self-test harness written in
Intcode**: the program runs a battery of checks of the very features you
just implemented — position vs immediate decoding, each new opcode — and
emits `0` per passing check, then the diagnostic code. A non-zero output
*before* the final one is the program telling you *which feature you decoded
wrong*.

That's why the test file asserts `(andmap zero? (drop-right outs 1))`
separately from the final code: it's not redundant with checking the answer,
it's reproducing the diagnostic's own contract — *if any intermediate output
is non-zero, your interpreter has a bug*, and the position of the first
non-zero output points at the failing opcode. Recognizing the input as a
test suite reframes debugging: you don't stare at your code, you read which
test number failed and look at the opcode it exercises. (This "the puzzle
input is itself a program that diagnoses your VM" pattern recurs across the
Intcode trilogy — it's the most AoC-2019 thing about AoC 2019.)

**This is not just an assertion — it's provable by disassembly, and the
proof is better than the claim.** [day05_disassembly.md](day05_disassembly.md)
takes the input apart and finds that (a) it is **self-modifying** —
`mem[6] = input + 1100` turns your system-ID input *into an opcode*, so a
single cell is `add` for input 1 and `jump-if-true` for input 5 — and (b)
the two inputs therefore run **disjoint** instruction histograms: input 1
executes 61 instructions with *zero* comparisons or jumps (the arithmetic /
parameter-mode tests), while input 5 executes 101 instructions including
12 `less-than` + 12 `equals` + 37 jumps (the comparison / control-flow tests
— exactly the opcodes Part 2 had you add). The diagnostic is literally a
**per-subsystem test selector**, with the input as the test key. That file
also shows *why* the disassembly had to be dynamic: self-modifying code
defeats static analysis, so the only faithful disassembly is to execute and
log — the classic linear-sweep → recursive-descent → dynamic-trace
progression, one per Intcode era.

---

## Tests (what's pinned and why)

[test/day05-test.rkt](../../test/day05-test.rkt) pins four layers:

1. **Parser** — comma-separated ints to a vector (shared with Day 2),
   CRLF-tolerant.
2. **I/O + modes** — the echo program `3,0,4,0,99` exercises opcodes `3`
   and `4`.
3. **Every new control-flow opcode in both modes** — equals (`8`) and
   less-than (`7`) in position *and* immediate form, plus both jump
   programs (`5`/`6`), using the puzzle's canonical small programs. These
   collectively cover everything the large 999/1000/1001 example does, so
   that larger literal is left out rather than transcribed (and risk a typo
   in a 60-int constant).
4. **The real input** — the diagnostic contract (`all but the last output
   are 0`) *and* both answers: `part1 = 6731945`, `part2 = 9571668`.

`raco test` runs the `module+ test` submodule; 19 checks, all green.

---

## Benchmarks

```
| Day | Parse (ms) | Part 1 (ms) | Part 2 (ms) | Total (ms) |
|-----|-----------|-------------|-------------|------------|
| 02  | 0.1050    | 0.0050      | 27.4200     | 27.5300    |
| 05  | 0.5740    | 0.0255      | 0.0270      | 0.6265     |
```

The mean is over **2000** iterations. What the row says:

- **Parse ≈ 0.57 ms** *dominates* — it's the whole cost of the day. Parsing
  ~680 integers (split + `string->number` each) is far more work than
  *running* them, because each part executes only a few hundred
  instructions.
- **Part 1 ≈ Part 2 ≈ 0.026 ms**: a single pass through the diagnostic
  program. Unlike Day 2 (whose Part 2 brute-forced 10 000 runs) or Day 3
  (which rasterized 150k cells), Day 5 runs the program *once* per part, so
  it's the fastest day since Day 1.
- **Total 0.63 ms**: the decode upgrade costs essentially nothing at
  runtime — the digit arithmetic in `val` is a couple of integer ops per
  parameter, dwarfed by the parse.

---

## If I were writing this in Rust

```rust
fn run(program: &[i64], input: i64) -> Vec<i64> {
    let mut mem = program.to_vec();
    let (mut ip, mut outs) = (0usize, Vec::new());
    loop {
        let instr = mem[ip];
        let val = |n: usize| {                       // mode-aware read
            let raw = mem[ip + n];
            let mode = (instr / 10i64.pow(n as u32 + 1)) % 10;
            if mode == 1 { raw } else { mem[raw as usize] }
        };
        let addr = |n: usize| mem[ip + n] as usize;  // write target
        match instr % 100 {
            1 => { mem[addr(3)] = val(1) + val(2); ip += 4; }
            2 => { mem[addr(3)] = val(1) * val(2); ip += 4; }
            3 => { mem[addr(1)] = input;           ip += 2; }
            4 => { outs.push(val(1));              ip += 2; }
            5 => ip = if val(1) != 0 { val(2) as usize } else { ip + 3 },
            6 => ip = if val(1) == 0 { val(2) as usize } else { ip + 3 },
            7 => { mem[addr(3)] = (val(1) < val(2)) as i64; ip += 4; }
            8 => { mem[addr(3)] = (val(1) == val(2)) as i64; ip += 4; }
            99 => return outs,
            op => panic!("unknown opcode {op} at {ip}"),
        }
    }
}
```

The correspondences worth seeing:

- **Racket's `val`/`addr` local functions ↔ Rust closures over `mem`/`ip`.**
  Both capture the current pointer so each opcode arm reads "values in,
  address out." (Rust's borrow checker actually fights this — the closures
  borrow `mem` immutably while the arms need it mutably; in real Rust you'd
  inline `val`/`addr` or pass `&mem` explicitly. Racket's lack of a borrow
  checker makes the closure version frictionless, a rare ergonomic win for
  the dynamic language.)
- **`case` on `(modulo instr 100)` ↔ `match instr % 100`.** Same dispatch
  on the two-digit opcode.
- **The tail-recursive `(loop ip outs)` ↔ Rust's `loop { … }` with `mut
  ip`.** Racket threads the pointer as an argument; Rust mutates a local.
  The jump opcodes are "assign `ip`" in both — the PC-as-variable model is
  identical, just immutable-rebind vs. mutable-assign.
- **`(if (< (val 1) (val 2)) 1 0)` ↔ `(val(1) < val(2)) as i64`.** Rust can
  cast a `bool` straight to `0`/`1`; Racket spells the `if` out (it has no
  bool→int coercion, by design).

---

## What's next

Day 5 is the VM's second of four growth spurts. **[Day 6](day06_function_guide.md)**
takes a break from Intcode for a tree/graph day (orbital transfers — a
lowest-common-ancestor problem). Then **[Day 7](day07_function_guide.md)**
chains *five copies* of this exact machine into an amplifier circuit, and
that's where the single `input` value here must become an **input queue** (a
port the machine reads from and another machine writes to) and `run` must be
able to **pause** mid-program waiting for input rather than running to halt.
The decode and the eight opcodes carry over unchanged; only the I/O model
grows. **[Day 9](day09_function_guide.md)** adds the final piece — a third
parameter mode (relative) and a relative base — completing the Intcode
computer. See the [summary table](summary_2019.md) for the running
scoreboard and [Day 2](day02_function_guide.md) for where this machine
began.
