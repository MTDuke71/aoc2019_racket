# Day 1 — The Tyranny of the Rocket Equation (function guide)

> First real AoC 2019 Racket day. Besides solving the puzzle, this day
> sets up the **solving platform** every later day reuses, so this guide
> spends its first section on the project skeleton and the rest on the
> Day 1 code itself.

## The puzzle in one paragraph

Input is a list of module masses, one integer per line. **Part 1:** for
each module, `fuel = floor(mass / 3) - 2`; sum them. **Part 2:** fuel
has mass too, so it needs its own fuel, which needs its own fuel, …
Keep applying the same formula to each newly-added chunk of fuel until a
step yields nothing positive, and sum the whole chain per module.

---

## The platform (decided this day)

The four toolchain questions CLAUDE.md flagged for "Day 1" are settled
here, since the 12-day tutorial was skipped:

| Question | Decision | Why |
|----------|----------|-----|
| Project layout | one file per day, `src/dayNN.rkt` | mirrors the AoC 2018 Haskell repo; no per-day package ceremony |
| Type discipline | **contracts** (`contract-out`), not `typed/racket` | the tutorial scaffold already used contracts; runtime boundary checks read like signatures without a separate type layer |
| Tests | RackUnit, run via `raco test` | the Racket default; the `module+ test` submodule is what `raco test` executes |
| Benchmark | `time-apply` averaged over N iterations | Racket has no criterion; this is the honest mean-of-N substitute |

Layout that resulted:

```
src/aoc.rkt          -- shared input I/O (runtime-path resolution)
src/day01.rkt        -- parse-input / fuel / total-fuel / part1 / part2 / solve
test/day01-test.rkt  -- RackUnit: examples + pinned real answers
bench/main.rkt       -- mean-of-N timing harness, one row per day
python/day01.py      -- algorithm-flavored side-by-side
```

How to drive it:

```powershell
racket src/day01.rkt              # prints both parts
raco test test/day01-test.rkt     # runs the test submodule
racket bench/main.rkt             # prints the timing table
```

### The shared I/O module: `src/aoc.rkt`

Every day needs "read my input no matter the current directory." The key
form is `define-runtime-path`:

```racket
(define-runtime-path src-dir ".")
```

This pins `src-dir` to the **location of the source file**, resolved at
runtime, not to wherever you happened to launch `racket` from. So
`racket src/day01.rkt`, `raco test …`, and `racket bench/main.rkt` all
locate `inputs/day01.txt` identically.

- **Rust analogue:** `env!("CARGO_MANIFEST_DIR")` / `include_str!` — a
  build-anchored path into the project tree instead of a runtime cwd
  guess.

`day-input-path` then zero-pads the day number with `~a` from
`racket/format`:

```racket
(~a day #:min-width 2 #:pad-string "0" #:align 'right)  ; 1 -> "01"
```

and the public surface is fenced behind contracts:

```racket
(provide
 (contract-out
  [day-input-path (-> (integer-in 1 25) path?)]
  [read-day-input (-> (integer-in 1 25) string?)]))
```

`(integer-in 1 25)` is a contract that documents *and enforces* "a valid
AoC day." Pass `0` or `26` and you get a boundary error naming the
offending argument.

---

## Reading prefix notation

Racket (like all Lisps) writes operators **before** their operands —
*prefix*, a.k.a. *Polish notation*. The mirror image is **RPN** (Reverse
Polish / postfix), where the operator comes last. So if HP-calculator RPN
is your reference point, Racket is RPN flipped end-for-end:

| Notation | `fuel` expression | How you'd say it |
|----------|-------------------|------------------|
| Infix (Rust/C) | `mass / 3 - 2` | "mass over 3, minus 2" — needs precedence rules |
| Postfix (RPN) | `mass 3 / 2 -` | "push mass, push 3, divide, push 2, subtract" |
| Prefix (Racket) | `(- (quotient mass 3) 2)` | "subtract 2 from the quotient of mass and 3" |

**The one idea that makes it click:** there is no special syntax for
arithmetic. `+`, `-`, `quotient` are ordinary functions, and *every* call
has the identical shape — the first element inside the parens is "the
verb," the rest are its arguments:

```
(operator operand operand …)
   ^ always first = what to do
```

`(quotient mass 3)` is a function call in exactly the same way `(fuel m)`
and `(string-split s)` are. Two things that buys you:

1. **No precedence (PEMDAS).** The parens already say what groups with
   what; `(- (quotient mass 3) 2)` can only mean one thing.
2. **No RPN stack discipline.** The parens make each operand's extent
   explicit, so you read the form as a **tree**, not as a left-to-right
   stack trace.

Read it verb-first, descending into inner parens first:

```
(- (quotient mass 3) 2)
 │  └─────┬───────┘  └─ second arg to -: the literal 2
 │     first arg to -: "quotient of mass and 3"
 └─ verb: subtract
```

This generalizes past arithmetic — `if`, `define`, `let`, and `loop` all
sit in that same head position, so once "first element = what to do" is
automatic, the parens stop reading as noise and start reading as the
syntax tree drawn for you:

```
(if (<= f 0) acc (loop f (+ acc f)))
 └─ verb: if  then    else-branch
```

One bonus prefix gives you that RPN can't: operators are **n-ary**, not
just binary. `(+ 1 2 3 4)` is a single call — no two-at-a-time chaining.

---

## The Day 1 code, form by form

### `parse-input`

```racket
(define (parse-input s)
  (map string->number (string-split s)))
```

`string-split` with **no separator** splits on runs of whitespace and
drops empty pieces. That single choice handles trailing newlines, blank
lines, and CRLF (`\r\n`) endings with zero special-casing — worth
remembering, because Windows inputs routinely carry `\r`.

- **Rust analogue:** `s.split_whitespace().map(|t| t.parse().unwrap())`.
- **Haskell precedent (2018 Day 1):** there the parser was
  `map read . lines`; `lines` keeps empty lines, so the Haskell version
  needed care that the Racket whitespace-split sidesteps.

### `fuel` — the Part 1 kernel

```racket
(define (fuel mass)
  (- (quotient mass 3) 2))
```

`quotient` is truncating integer division. For non-negative masses
"truncate" and "round down" coincide, which is exactly the puzzle's
"divide by three and round down." (For negatives they differ — `quotient`
truncates toward zero — but module masses are positive, so it's moot.)

### `part1` — `for/sum`

```racket
(define (part1 masses)
  (for/sum ([m (in-list masses)]) (fuel m)))
```

`for/sum` is a **comprehension that folds with `+`**. `in-list` is the
sequence driver that says "iterate a list specifically," which lets the
compiler specialize the loop instead of going through the generic
sequence protocol.

- **Rust analogue:** `masses.iter().map(|&m| fuel(m)).sum()`.
- **Haskell precedent:** `foldl' (+) 0 . map fuel`. `for/sum` is the
  same fold with the accumulator and operator implied.

### `total-fuel` — the Part 2 fixed-point iteration

```racket
(define (total-fuel mass)
  (let loop ([m mass] [acc 0])
    (define f (fuel m))
    (if (<= f 0)
        acc
        (loop f (+ acc f)))))
```

This is the **algorithm hiding inside Day 1**: a *fixed-point
iteration*. You repeatedly apply `fuel` to its own output and accumulate
each positive result, stopping when the map's output leaves the positive
region. The sequence `mass → fuel → fuel(fuel) → …` strictly decreases
(each step is roughly `m/3`), so it always terminates — it's a geometric
decay with ratio ≈ 1/3, which is also why Part 2's answer is only ~1.5×
Part 1's rather than unbounded.

The `let loop` form is a **named let**: it defines a local recursive
function `loop` and immediately calls it with the initial bindings. The
recursive call is in tail position, so Racket runs it as a loop in
constant stack — no accumulating frames.

- **Rust analogue:** a `while f > 0 { total += f; f = fuel(f); }` loop —
  see [python/day01.py](../../python/day01.py), whose `total_fuel` is
  written in exactly that imperative shape for comparison.
- **Naming it matters:** "fixed-point iteration" / "iterate to
  convergence" is the transferable vocabulary. The same shape shows up
  whenever you apply a step function until it stabilizes (think
  Newton's method, or the stabilization passes in later AoC grid
  puzzles).

### `solve` and `module+ main`

```racket
(define (solve contents)
  (define puzzle (parse-input contents))
  (printf "  part 1: ~a\n" (part1 puzzle))
  (printf "  part 2: ~a\n" (part2 puzzle)))

(module+ main
  (solve (read-day-input 1)))
```

`solve` mirrors the Haskell repo's `solve :: String -> IO ()`: parse
once, print both parts. `module+ main` is code that runs **only when the
file is executed directly** (`racket src/day01.rkt`); `require`-ing the
module from a test or the bench harness does *not* trigger it. That
separation is why the same file is both a runnable script and a clean
library.

- **Rust analogue:** `module+ main` ≈ a `fn main()` that's compiled out
  when the crate is used as a library; `~a` in `printf` is `{}` in
  `format!` (display style). `~s` would be `{:?}` (write/debug style).

### Why these are behind `contract-out`

```racket
(provide
 (contract-out
  [parse-input (-> string? (listof exact-integer?))]
  [fuel        (-> exact-integer? exact-integer?)]
  [total-fuel  (-> exact-integer? exact-integer?)]
  [part1       (-> (listof exact-integer?) exact-integer?)]
  [part2       (-> (listof exact-integer?) exact-integer?)]
  [solve       (-> string? void?)]))
```

Contracts check values **as they cross the module boundary**. The test
file calls `(fuel 12)` from *outside* `day01.rkt`, so a regression that
made `fuel` return a string would trip the contract before the
`check-equal?` even ran. Internal calls (`part1` calling `fuel`) are not
checked, so there's no per-iteration cost in the hot loop. This is the
"signature-like guardrails in untyped Racket" idea from tutorial Day 1,
applied to a real solution surface.

---

## Tests (what's pinned and why)

[test/day01-test.rkt](../../test/day01-test.rkt) pins three layers:

1. **Parser** — including a CRLF case, to lock in the whitespace-split
   robustness.
2. **Every worked example** from the puzzle text, for both parts
   (`fuel 1969 = 654`, `total-fuel 1969 = 966`, …).
3. **The real answers** — `part1 = 3481005`, `part2 = 5218616` — read
   from `inputs/day01.txt`. Pinning the actual answer means any future
   refactor that changes the result fails loudly instead of silently.

`raco test` runs the `module+ test` submodule; 13 checks, all green.

---

## Benchmarks

```
| Day | Parse (ms) | Part 1 (ms) | Part 2 (ms) | Total (ms) |
|-----|-----------|-------------|-------------|------------|
| 01  | 0.0141    | 0.0006      | 0.0029      | 0.0175     |
```

Mean of 100,000 iterations each (`collect-garbage` before each measure).
Reading is dominated by **parsing** — `string->number` over 100 lines
costs ~20× the arithmetic of either part. Part 2 is ~5× Part 1 because of
the per-module fixed-point loop, but in absolute terms the whole day is
~17 microseconds. These numbers are calibration for the cold reader:
Day 1 is the cheapest possible baseline; anything in later days that's
*not* sub-millisecond is doing real algorithmic work.

---

## If I were writing this in Rust

```rust
fn fuel(mass: i64) -> i64 { mass / 3 - 2 }

fn total_fuel(mass: i64) -> i64 {
    std::iter::successors(Some(mass), |&m| Some(fuel(m)))
        .skip(1)                 // drop the original mass
        .take_while(|&f| f > 0)  // stop at the first non-positive step
        .sum()
}

fn main() {
    let masses: Vec<i64> = include_str!("../inputs/day01.txt")
        .split_whitespace()
        .map(|t| t.parse().unwrap())
        .collect();
    let part1: i64 = masses.iter().map(|&m| fuel(m)).sum();
    let part2: i64 = masses.iter().map(|&m| total_fuel(m)).sum();
    println!("part 1: {part1}\npart 2: {part2}");
}
```

The interesting correspondence is `total_fuel`. Racket expresses the
fixed-point iteration as an explicit tail-recursive `let loop`; Rust can
say the same thing declaratively with `std::iter::successors` —
`successors(seed, step)` *is* "iterate this function," and
`take_while(|&f| f > 0)` *is* the loop's `(<= f 0)` stop condition. Two
spellings of one idea: "generate the orbit of a function from a seed,
consume the prefix you care about." Racket's `for/sum` ↔ Rust's `.sum()`
is the other one-to-one mapping.

---

## What's next

Day 1 establishes the template. The next day to actually exercise the
platform's harder muscles is **Day 2 (1202 Program Alarm)** — the first
**Intcode** day, which kicks off AoC 2019's VM trilogy. That's where
mutable `vector` (the `STUArray` analogue from Haskell Day 9) and a
fetch/decode/execute loop enter the project. See the
[summary table](summary_2019.md) for the running scoreboard.
