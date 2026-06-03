# Day 2 — 1202 Program Alarm (function guide)

> The first **Intcode** day, and the start of AoC 2019's defining
> meta-problem: a tiny virtual machine that Days 2, 5, 7, and 9 grow into
> a full computer. This guide spends real time on the *interpreter
> pattern* and the project's first **mutable `vector`**, then closes with
> the affine trick that collapses Part 2's brute force.

## The puzzle in one paragraph

The input is a flat list of integers — an *Intcode program* — where the
same array holds both code and data (von-Neumann style). Execution is a
**fetch/decode/execute** loop over three opcodes: `1` adds, `2`
multiplies, `99` halts. Each arithmetic op is four cells wide
(`opcode a b dst`) and the three operand cells are **positions**, not
values — you read `mem[a]` and `mem[b]`, combine them, and write to
`mem[dst]`. **Part 1:** set `mem[1]=12`, `mem[2]=2` (the "1202" alarm
state), run, read `mem[0]`. **Part 2:** find the `(noun, verb)` pair in
`[0,99]²` that makes `mem[0]` equal `19690720`, and report
`100·noun + verb`.

---

## The algorithm in Python

Day 2 is *interpreter-flavored*, not number-crunching, so the Python
companion ([python/day02.py](../../python/day02.py)) is there to make the
fetch/decode/execute loop legible before we read it in Racket:

```python
def run(program):
    mem = program[:]          # execute a copy
    ip = 0
    while True:
        op = mem[ip]
        if op == 99:
            return mem
        a, b, dst = mem[ip + 1], mem[ip + 2], mem[ip + 3]
        if op == 1:   mem[dst] = mem[a] + mem[b]
        elif op == 2: mem[dst] = mem[a] * mem[b]
        else:         raise ValueError(f"bad opcode {op}")
        ip += 4
```

That `while True` with a manual instruction pointer `ip` that steps by 4
is the canonical **bytecode interpreter** skeleton — the same loop at the
heart of `clox`'s VM, just with three opcodes instead of thirty. Hold
that picture; the Racket version is the same machine.

---

## The interpreter pattern

A bytecode VM has three moving parts, and they map one-to-one onto the
Racket code:

| VM concept | Day 2 realization | In `src/day02.rkt` |
|------------|-------------------|--------------------|
| **Memory** (code = data) | one mutable integer array | `mem`, a Racket `vector` |
| **Instruction pointer** | index of the current opcode | `ip`, the `let loop` variable |
| **Fetch / decode / execute** | read `mem[ip]`, branch on it, mutate, advance | the `case` in `run!` |

The thing that makes Intcode *Intcode* (and not just "evaluate an
expression tree") is that **code and data share one address space**. The
worked example literally overwrites the cell holding `99` mid-run:
`1,1,1,4,99,...` rewrites position 4 from `99` to `2` before the pointer
ever reaches it. Self-modifying code is the norm here, not a trick —
which is exactly why the program lives in a *mutable* array.

- **Crafting Interpreters anchor:** this is `clox`'s `run()` — the
  `for (;;)` loop that reads an opcode, `switch`es on it, and bumps `ip`.
  Day 2 is that VM stripped to three instructions. When Day 5 adds
  parameter modes and I/O, and Day 9 adds a relative base, you're
  watching `clox` grow opcode by opcode.

---

## The Day 2 code, form by form

### `parse-input`

```racket
(define (parse-input s)
  (list->vector (map string->number (string-split (string-trim s) ","))))
```

Two deliberate choices versus Day 1:

1. **`string-trim` first, then split on `","`.** Day 1 used
   `(string-split s)` with no separator, which drops whitespace tokens for
   free. Here the separator is a comma, so a trailing `\n` would otherwise
   ride along on the last token (`"...0\n"`) and make `string->number`
   return `#f`. `string-trim` strips the leading/trailing newline (and
   CRLF) up front.
2. **`list->vector`, not a bare list.** Intcode is random-access by
   position and mutates in place. A list is O(n) to index and immutable;
   a `vector` is O(1) `vector-ref` / `vector-set!`. This is the project's
   first use of a **mutable vector** — see the next section.

- **Rust analogue:** `s.trim().split(',').map(|t| t.parse().unwrap()).collect::<Vec<i64>>()`.

### The mutable `vector` — Racket's `STUArray`

Day 1 only ever read its data. Day 2 needs an array it can *clobber in
place* thousands of times, and Racket's `vector` is exactly that:

```racket
(vector-ref  mem i)      ; read   — O(1)
(vector-set! mem i v)    ; write  — O(1), in place
(vector-copy v)          ; fresh independent copy
```

- **Haskell precedent (AoC 2018 Day 9):** this is the `STUArray` /
  `Data.Vector.Mutable` story. In Haskell, in-place mutation has to be
  fenced inside the `ST` monad so the compiler can prove the mutation
  doesn't escape; `readArray` / `writeArray` are the `vector-ref` /
  `vector-set!` equivalents. Racket has no such ceremony — `vector-set!`
  is just a function — but the *discipline* is the same: one array, many
  destructive updates, and you must copy when you want an independent run.
- **Rust analogue:** `Vec<i64>` with `v[i]` and `v[i] = x`. The
  `vector-copy`-before-run pattern is `program.clone()` — the same
  "borrow the original immutably, mutate a clone" move.

### `binop!` — indirect addressing

```racket
(define (binop! mem ip op)
  (define a   (vector-ref mem (vector-ref mem (+ ip 1))))
  (define b   (vector-ref mem (vector-ref mem (+ ip 2))))
  (define dst (vector-ref mem (+ ip 3)))
  (vector-set! mem dst (op a b)))
```

The **double `vector-ref`** is the whole subtlety of the puzzle. Cell
`ip+1` doesn't hold operand *a*; it holds the *position* of operand *a*.
So you dereference twice: once to get the address, once to get the value
there. The destination is dereferenced **once** — `mem[ip+3]` is the
address to write, and you write the value directly (you don't deref the
destination).

```
 mem[ip+1] = 9   ──first ref──▶  the address 9
 mem[9]    = 30  ──second ref─▶  the value 30   = a
```

The `!` suffix is a Racket naming convention: a procedure that **mutates**
ends in `!` (like `vector-set!`, `set!`). It's the cultural cue Rust
spells with `&mut` and Scheme/Racket spells with a bang.

- **Passing `op` as an argument** is first-class functions at work: `+`
  and `*` are ordinary values, so add and multiply share one body and
  differ only in which function gets threaded in. Rust: `fn(i64,i64)->i64`
  function pointers, or a closure.

### `run!` — fetch/decode/execute

```racket
(define (run! mem)
  (let loop ([ip 0])
    (case (vector-ref mem ip)
      [(99) mem]
      [(1)  (binop! mem ip +) (loop (+ ip 4))]
      [(2)  (binop! mem ip *) (loop (+ ip 4))]
      [else (error 'run "unknown opcode ~a at position ~a"
                   (vector-ref mem ip) ip)])))
```

`case` is Racket's **multi-way dispatch on a value** — it compares the
fetched opcode against each literal datum list (`(99)`, `(1)`, `(2)`) and
runs the first match, with `else` as the fallthrough. It's the `switch`
the interpreter pattern calls for, and it reads more directly than a
`cond` chain of `(= op 1)` tests.

- **Why `case` and not `match`?** `match` (which later days will lean on
  hard) destructures *structure* — shapes, lists, records. Here we're
  branching on a single scalar against constant tags, which is precisely
  `case`'s job. Reaching for `match` would be using a pattern matcher
  where an integer `switch` is the honest tool. Naming the right tool
  matters: this is *tagged dispatch*, the same idea as a Rust `match op {
  1 => …, 2 => …, 99 => …, _ => panic! }` on a `u8`.
- The recursive `(loop (+ ip 4))` is in **tail position**, so Racket runs
  it as a constant-stack loop — no growing call frames even though the
  program executes hundreds of instructions. This is the same
  tail-recursion guarantee Day 1's `total-fuel` relied on.
- **Halt returns `mem`.** The machine's whole observable result is its
  final memory, so `run!` hands it back; callers read whatever cell they
  care about.

### `run` and `run-with` — copy-on-execute

```racket
(define (run program)
  (run! (vector-copy program)))

(define (run-with program noun verb)
  (define mem (vector-copy program))
  (vector-set! mem 1 noun)
  (vector-set! mem 2 verb)
  (run! mem)
  (vector-ref mem 0))
```

`run!` is **private** and mutates; `run` is the **public** wrapper that
copies first. That split is the key design decision of the day: because
Part 2 runs the same program up to 10,000 times, the original program
vector must survive each run untouched. Copy-then-mutate gives every run a
clean slate. (The test `"run executes a copy; the caller's program is
untouched"` pins exactly this.)

`run-with` is the "load two inputs, read one output" harness: pour `noun`
and `verb` into positions 1 and 2, run, read position 0. Part 1 is then
just the 1202 alarm: `(run-with program 12 2)`.

- **Rust analogue:** `run` is `fn run(program: &[i64]) -> Vec<i64>` that
  starts with `let mut mem = program.to_vec();` — borrow immutably, clone,
  mutate the clone.

### `part2` — `for*/first`

```racket
(define (part2 program)
  (for*/first ([noun (in-range 100)]
               [verb (in-range 100)]
               #:when (= (run-with program noun verb) target))
    (+ (* 100 noun) verb)))
```

`for*/first` packs three ideas into one form:

- **`for*`** (star) is **nested** iteration — `verb` runs its full inner
  loop for each `noun`, exactly like two stacked `for` loops. (Plain
  `for` would walk the two sequences *in lockstep*, only visiting the 100
  diagonal pairs — a real bug if you reached for it here.)
- **`/first`** short-circuits: it returns the body of the **first**
  iteration that runs, and stops. No manual `break`, no found-flag.
- **`#:when`** guards which iterations count — only `(noun, verb)` pairs
  that hit the target reach the body, so `/first` returns the first
  *matching* pair's answer.

- **Rust analogue:**
  `(0..100).cartesian_product(0..100).find(|&(n,v)| run_with(p,n,v)==target).map(|(n,v)| 100*n+v)` —
  `for*` is `cartesian_product`, `/first` + `#:when` is `find`.

---

## The problem within the problem: Part 2 is affine

Part 2's brute force is honest and ships in the source, but the puzzle
hides a much smaller structure. **The program's output is an affine
(linear-plus-constant) function of its two inputs:**

```
output(noun, verb) = base + A·noun + B·verb
```

Why this holds *for this input*: the program only ever adds and
multiplies, and along the path the alarm setup takes, `noun` and `verb`
are never multiplied **by each other** — each contributes linearly. So
the entire 100×100 grid lies on a single plane, and three runs nail it
down:

```racket
(define base (run-with prog 0 0))           ; the constant term
(define A    (- (run-with prog 1 0) base))  ; ∂output/∂noun
(define B    (- (run-with prog 0 1) base))  ; ∂output/∂verb
```

On this puzzle's input those come out to `base = 521344`, `A = 368640`,
`B = 1`. Because the map is affine and `B = 1`, the target equation
`base + A·noun + B·verb = 19690720` solves directly:

```racket
(define noun (quotient (- target base) A))   ; 52
(define verb (- target base (* A noun)))     ; 96  → answer 5296
```

That's **3 program runs instead of ~5,300** — the 27 ms Part 2 in the
bench table would drop to a handful of microseconds. The empirical
verification (the plane holds on every sampled pair, and the closed form
reproduces `5296`) is in [python/day02.py](../../python/day02.py)'s
`part2_affine`. For the *proof* — a full disassembly of the puzzle program
and a symbolic decompilation that recovers `521344 + 368640·noun + verb`
by abstract interpretation — see the
[Day 2 disassembly](day02_disassembly.md).

**Why the source still ships the brute force** — per the repo's
optimization policy, the idiomatic, obviously-correct version is what
goes in `src/dayNN.rkt`; the faster algorithm lives here as a sidebar.
And there's a real caveat that makes the brute force the *safe* default:
affinity is a property of **this input**, not of the Intcode opcode set.
A program that multiplied two noun-dependent cells would be quadratic and
break the closed form. The brute force is correct for any input; the
affine solve is correct for the ones AoC actually ships. Naming the
technique: this is **solving a linear system by sampling basis vectors** —
evaluate at `(0,0)`, `(1,0)`, `(0,1)` to recover the coefficients of an
affine map, the same move as reading off a Jacobian by finite
differences.

### Possible optimization (sidebar, untested)

A drop-in `part2` using the closed form, kept out of the shipping source:

```racket
;; Affine closed form. Assumes output is linear in (noun, verb), which is
;; an empirical property of AoC inputs, not a guarantee — falls back to a
;; grid scan if the recovered plane doesn't actually hit the target.
(define (part2-fast program)
  (define base (run-with program 0 0))
  (define A    (- (run-with program 1 0) base))
  (define B    (- (run-with program 0 1) base))
  (define noun (quotient (- target base) A))
  (define verb (quotient (- target base (* A noun)) B))
  (if (and (<= 0 noun 99) (<= 0 verb 99)
           (= (run-with program noun verb) target))
      (+ (* 100 noun) verb)
      (part2 program)))   ; safety net: fall back to the brute force
```

The `if` guard is the honest part: it *checks* the recovered pair before
trusting it and falls back to the brute force if the affine assumption
ever fails. Cheap insurance for a 1000×speedup.

---

## Tests (what's pinned and why)

[test/day02-test.rkt](../../test/day02-test.rkt) pins four layers:

1. **Parser** — comma split plus trailing-newline and CRLF tolerance.
2. **Every worked example**, checked against the **full final memory
   vector**, not just position 0 — the step-by-step
   `1,9,10,3,...,40,50 → 3500,9,10,70,...` program and all four small
   `initial → final` programs (including `2,4,4,5,99,0 → ...9801`, which
   writes *past* the halt cell).
3. **The copy invariant** — running a program leaves the caller's vector
   untouched, which is the contract Part 2's 10,000 reruns depend on.
4. **The real answers** — `part1 = 4945026`, `part2 = 5296`.

`raco test` runs the `module+ test` submodule; 11 checks, all green.

---

## Benchmarks

```
| Day | Parse (ms) | Part 1 (ms) | Part 2 (ms) | Total (ms) |
|-----|-----------|-------------|-------------|------------|
| 01  | 0.0141    | 0.0006      | 0.0028      | 0.0174     |
| 02  | 0.1050    | 0.0050      | 27.0500     | 27.1600    |
```

Day 2's mean is over **200** iterations, not Day 1's 100,000 — Part 2
runs the full 100×100 search *every* call, so a single Part 2 measure is
already ~5,300 program executions. The story the row tells:

- **Part 1 ≈ 5 µs**: one program run. The Intcode loop itself is cheap.
- **Part 2 ≈ 27 ms**: ~5,300× Part 1. *All* of Day 2's cost is the brute
  force — this is the row that motivates the affine sidebar, which would
  drop Part 2 back to ~15 µs (3 runs).
- **Parse ≈ 0.1 ms**, ~7× Day 1's, because `list->vector` allocates a
  vector on top of the list `string->number` already builds.

This is the first day where an algorithmic choice (brute force vs. closed
form) shows up as four orders of magnitude in the table — calibration for
the cold reader on what "doing real work" costs.

---

## If I were writing this in Rust

```rust
fn run(program: &[i64]) -> Vec<i64> {
    let mut mem = program.to_vec();   // execute a clone
    let mut ip = 0;
    loop {
        match mem[ip] {
            99 => return mem,
            op @ (1 | 2) => {
                let (a, b, dst) = (mem[ip + 1] as usize,
                                   mem[ip + 2] as usize,
                                   mem[ip + 3] as usize);
                mem[dst] = if op == 1 { mem[a] + mem[b] } else { mem[a] * mem[b] };
                ip += 4;
            }
            bad => panic!("unknown opcode {bad} at {ip}"),
        }
    }
}

fn run_with(program: &[i64], noun: i64, verb: i64) -> i64 {
    let mut mem = program.to_vec();
    mem[1] = noun;
    mem[2] = verb;
    run(&mem)[0]
}

fn part2(program: &[i64]) -> i64 {
    (0..100)
        .flat_map(|noun| (0..100).map(move |verb| (noun, verb)))
        .find(|&(n, v)| run_with(program, n, v) == 19_690_720)
        .map(|(n, v)| 100 * n + v)
        .unwrap()
}
```

The correspondences worth seeing:

- Racket's `case` on the opcode ↔ Rust's `match mem[ip]`, with the
  `1 | 2` or-pattern doing what the two `case` clauses do (and `op @`
  binding the matched value the way the shared `binop!` reads it back).
- `vector-copy` ↔ `program.to_vec()` — the copy-on-execute discipline is
  identical; the original is borrowed `&[i64]`, the run owns a `Vec`.
- `for*/first` + `#:when` ↔ `flat_map`-to-cartesian-product + `find`.
  Racket folds the nested loop, the guard, and the short-circuit into one
  `for*/first`; Rust spells the three as separate iterator adapters.
- The `as usize` casts are the one place Rust is noisier: Intcode
  positions are stored as `i64` but index a `Vec`, so each deref needs a
  cast. Racket's `vector-ref` takes any exact integer, so the double
  dereference reads without the ceremony.

---

## What's next

Day 2 stands up the Intcode VM in its smallest form. **Day 5** is where it
grows teeth: *parameter modes* (immediate vs. position), new opcodes for
input/output and conditional jumps, and instruction widths that vary by
opcode. That's the day the single shared `run!` here gets refactored into
something worth extracting into a reusable `src/intcode.rkt` — the way
AoC 2018 introduced `ST` on Day 9 rather than Day 1, the VM earns its own
module when a second day actually needs it, not before. See the
[summary table](summary_2019.md) for the running scoreboard, and
[Day 1](day01_function_guide.md) for the platform this builds on.
