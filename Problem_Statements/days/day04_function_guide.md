# Day 4 — Secure Container (function guide)

> A palate cleanser between grids ([Day 3](day03_function_guide.md)) and the
> Intcode thread ([Day 2](day02_function_guide.md)): a pure
> number-theory/combinatorics filter. Count six-digit numbers in a range
> whose digits **never decrease** and which contain an **adjacent repeated**
> digit. The day's one transferable idea is **run-length encoding** — once
> you collapse the digits into their runs, both parts are a one-line
> question about run *lengths*. Along the way it introduces the variadic
> `(apply <= ds)` monotonicity trick, `match` with a `#:when` guard on a
> fold accumulator, and the counting loops `for/or` / `for/sum`.

## The puzzle in one paragraph

You're given an inclusive numeric range (`172930-683082`). A valid password
is a six-digit number where, reading left to right, the digits are
**non-decreasing** (`111123`, `135679` — never a smaller digit after a
larger one) **and** at least two **adjacent** digits are equal (the `22` in
`122345`). **Part 1:** count the valid numbers in the range. **Part 2:**
tighten the double rule — the adjacent equal digits must form a group of
**exactly two**, not be swallowed by a longer run. So `123444` fails (the
`44` lives inside `444`), but `112233` passes (three clean doubles) and
`111122` passes (the `22` is a clean double even though `1111` is not).

---

## The algorithm in Python

Day 4 is *algorithm-flavored* — the lesson is a data transform
(run-length encoding), not a syntax tour — so the Python companion
([python/day04.py](../../python/day04.py)) states the shape in its most
legible form first:

```python
from itertools import groupby

def run_lengths(n):
    return [len(list(g)) for _, g in groupby(str(n))]   # 111122 -> [4, 2]

def non_decreasing(n):
    s = str(n)
    return list(s) == sorted(s)

def part1_ok(n):  return non_decreasing(n) and any(r >= 2 for r in run_lengths(n))
def part2_ok(n):  return non_decreasing(n) and any(r == 2 for r in run_lengths(n))
```

The entire puzzle is those four lines. `groupby` **is** run-length
encoding: it yields one group per maximal run of equal *adjacent* items, so
`str(111122)` becomes runs of lengths `[4, 2]`. Non-decreasing is "the
digits already equal their own sorted order." Then Part 1 asks for any run
≥ 2 and Part 2 for any run = 2 — the *only* difference between the parts is
`>=` versus `==`. Hold this picture; the Racket version is the same
algorithm, with a hand-rolled `for/fold` standing in for `groupby` and
`(apply <= ds)` standing in for the `sorted` comparison.

---

## The run-length-encoding pattern

The canonical name for collapsing `(1 1 2 3 3 3)` into
`((1 . 2) (2 . 1) (3 . 3))` is **run-length encoding** (RLE) — the same
primitive behind simple image compression and the `uniq -c` shell idiom. It
shows up in AoC whenever a puzzle cares about *consecutive sameness*: the
[2018 Day 4](../../../aoc2018_Haskell/Problem_Statements/days/) sleep-streak
counting, look-and-say sequences, any "longest run of X" question. Naming it
here means reaching for it on sight later instead of re-deriving an
ad-hoc counter.

| Question about the digits | RLE realization | In `src/day04.rkt` |
|---------------------------|-----------------|--------------------|
| do they ever decrease? | (handled separately) | `(apply <= ds)` |
| collapse into runs | run-length encode | `run-length-encode` |
| any adjacent double? (P1) | some run length ≥ 2 | `for/or … (>= (cdr run) 2)` |
| any *clean* double? (P2) | some run length = 2 | `for/or … (= (cdr run) 2)` |

The key realization: **the double-digit rule is not about digits at all,
it's about run lengths.** Part 1 wants the multiset of run lengths to
contain something ≥ 2; Part 2 wants it to contain a 2 exactly. Once the
digits are RLE'd, both questions are trivial — and identical except for one
comparison operator.

---

## The Day 4 code, form by form

### `parse-input` — split a range on the hyphen

```racket
(define (parse-input s)
  (match (map string->number (string-split (string-trim s) "-"))
    [(list lo hi) (cons lo hi)]))
```

`string-split` on `"-"` cuts `"172930-683082"` into `("172930" "683082")`,
`map string->number` parses both, and the `match` against the literal
pattern `(list lo hi)` both **destructures** the two-element list and
**asserts its shape**: a malformed input (one number, or three) fails the
match loudly rather than silently mis-`cdr`-ing. The result `(cons lo hi)`
is the inclusive range.

- **Why `match` over `(values (first …) (second …))`?** The pattern is
  self-documenting — "I expect exactly a low and a high" — and it's the
  same judgment Day 3's `match-define` made: when there's one known shape,
  destructure it in the binding. Here we want the *list-length* assertion
  too, so full `match` over `match-define`.
- **Rust analogue:** `let (lo, hi) = s.trim().split_once('-').unwrap();`
  then `(lo.parse().unwrap(), hi.parse().unwrap())`. Rust's `split_once`
  returning an `Option<(&str,&str)>` is the moral twin of matching the
  two-element list.

### `digits` — a number to its digit list

```racket
(define (digits n)
  (map (lambda (c) (- (char->integer c) (char->integer #\0)))
       (string->list (number->string n))))
```

`123 -> '(1 2 3)`, most-significant digit first. We round-trip through the
string form because then `string->list` hands us the digit *characters* and
subtracting the code point of `#\0` converts each character to its integer
value (`#\7` is 7 past `#\0` in ASCII/Unicode).

- **Why not arithmetic?** Peeling digits with `quotient`/`remainder` by 10
  yields them **least-significant first** — the reverse of what the
  non-decreasing test needs. The string route gives MSB-first for free.
- **Rust analogue:**
  `n.to_string().bytes().map(|b| (b - b'0') as i64).collect()`. The
  `char->integer … #\0` subtraction is exactly Rust's `b - b'0'`.

### `run-length-encode` — the core trick, a fold over `match`

This is the heart of the day:

```racket
(define (run-length-encode xs)
  (for/fold ([runs '()] #:result (reverse runs))
            ([x (in-list xs)])
    (match runs
      [(cons (cons v n) rest)
       #:when (= v x)
       (cons (cons v (add1 n)) rest)]
      [_ (cons (cons x 1) runs)])))
```

Read it as "walk the list, maintaining a stack of completed-and-in-progress
runs; the run in progress is always the head."

**1. `for/fold` with one accumulator.** `([runs '()] …)` is a single
accumulator initialised to the empty list — the same `for/fold` from
[Day 1](day01_function_guide.md), here threading the growing run-list.
Each iteration returns the next value of `runs`.

**2. `match` on the accumulator decides extend-vs-start.** The first
pattern `(cons (cons v n) rest)` says "the run-list is non-empty and its
head is a `(value . count)` pair `(v . n)`"; the guard `#:when (= v x)` adds
"…and that run's value equals the current element." When both hold, we're
continuing the current run, so we replace the head with `(v . (add1 n))`.
Otherwise (`_` — list empty, or head value differs) the current element
starts a fresh run `(x . 1)` pushed on front.

**3. `#:result (reverse runs)` fixes the order.** Because each new run is
`cons`ed on the front, the accumulator ends up reversed (last run first);
`#:result` flips it back so the output reads left-to-right like the input.
This is the same projection role `#:result` played in
[Day 3](day03_function_guide.md)'s `trace`, just reversing instead of
selecting.

#### Token by token

| Token | What it is | What it does here |
|-------|-----------|-------------------|
| `for/fold` | fold-with-accumulators iterator | reduce the digit list into a run-list |
| `([runs '()]` | the one accumulator + initial value | the runs built so far, starting empty |
| `#:result (reverse runs))` | result projection | flip the front-built list back to input order |
| `([x (in-list xs)])` | the loop clause | bind `x` to each element in turn |
| `(match runs …)` | dispatch on accumulator shape | decide: extend the current run or open a new one |
| `(cons (cons v n) rest)` | pattern: non-empty list whose head is a pair | name the in-progress run `(v . n)` and the `rest` |
| `#:when (= v x)` | pattern guard | only take this branch if the run's value matches `x` |
| `(cons (cons v (add1 n)) rest)` | branch result | bump the head run's count, keep the rest |
| `[_ …]` | catch-all pattern | empty list, or head value ≠ `x` |
| `(cons (cons x 1) runs)` | branch result | push a brand-new `(x . 1)` run on the front |

The mental anchor: **the head of the accumulator is the run in progress**,
and the `#:when` guard is the entire "is this the same run?" decision.
Everything else is bookkeeping to keep the list in order.

### `part1-ok?` / `part2-ok?` — `apply` and `for/or`

```racket
(define (part1-ok? n)
  (define ds (digits n))
  (and (apply <= ds)
       (for/or ([run (in-list (run-length-encode ds))])
         (>= (cdr run) 2))))

(define (part2-ok? n)
  (define ds (digits n))
  (and (apply <= ds)
       (for/or ([run (in-list (run-length-encode ds))])
         (= (cdr run) 2))))
```

Two new idioms:

- **`(apply <= ds)` is the non-decreasing test.** Racket's comparison
  operators are **variadic** — `(<= a b c d)` is true iff
  `a ≤ b ≤ c ≤ d`. `apply` splices the digit list in as those arguments, so
  one call checks the whole chain `d0 ≤ d1 ≤ … ≤ d5`. This is the Racket
  counterpart of Python's `list(s) == sorted(s)`, but cheaper — no sort,
  one linear pass. (Rust has no variadic `<=`; you'd write
  `ds.windows(2).all(|w| w[0] <= w[1])`.)
- **`for/or` is "does any iteration satisfy the body?"** It short-circuits
  on the first truthy body value and returns `#f` if none match — exactly
  Python's `any(...)`. Here the body is a comparison on `(cdr run)` (the run
  *length*), so the whole expression is a clean boolean.

The `and` short-circuits, so the (cheap) monotonicity check gates the
(slightly less cheap) RLE — we never encode a number that already failed.
And the *only* textual difference between the two predicates is `>=` vs `=`:
Part 1 accepts any run that reaches a pair; Part 2 demands a run that *stops
at* a pair.

### `count-in-range`, `part1`, `part2`, `solve`

```racket
(define (count-in-range lohi ok?)
  (match-define (cons lo hi) lohi)
  (for/sum ([n (in-range lo (add1 hi))] #:when (ok? n)) 1))

(define (part1 lohi) (count-in-range lohi part1-ok?))
(define (part2 lohi) (count-in-range lohi part2-ok?))
```

`count-in-range` takes the predicate as a **function argument** (`ok?`), so
both parts share one counting loop and differ only in which predicate they
pass — the higher-order-function move that keeps the two parts one line
each. `for/sum` with a `#:when` guard adds `1` per matching number: a
counting loop with no explicit accumulator (Rust:
`(lo..=hi).filter(|&n| ok(n)).count()`). `(add1 hi)` turns the half-open
`in-range` into an inclusive scan so `hi` itself is tested.

---

## The problem within the problem: it's combinations-with-repetition

The brute force scans ~510k numbers, which is fast enough that nobody needs
more. But the *structure* underneath is worth naming, because it's the kind
of reframing that turns an astronomically large range into an O(1) answer.

A **non-decreasing** d-digit number is exactly a **multiset** of d digits
drawn from `{1..9}` (a leading zero would shorten the number, so the usable
alphabet is the nine non-zero digits): the digit string is fully determined
by *how many* of each value it contains, and there's exactly one sorted
arrangement of any multiset. Counting multisets of size d from k symbols is
the textbook **stars and bars** / **combinations with repetition** formula:

```
   number of non-decreasing d-digit strings  =  C(d + k - 1, d)
```

with `d = 6`, `k = 9`. The "contains an adjacent double" constraint (Part 1)
and the "contains a *clean* double" constraint (Part 2) can then be layered
on by **inclusion-exclusion** over which digit forms the run — counting the
strictly-increasing strings (no repeats at all) and subtracting, etc. The
upshot: you can count valid passwords for a range *millions of digits wide*
without ever enumerating one, because the count depends only on the digit
*length* and the range endpoints, not on visiting each candidate.

Per the repo's optimisation policy, the shipping
[src/day04.rkt](../../src/day04.rkt) stays the readable brute force; the
closed form lives here as the transferable idea. The lesson is the
reframing — *"non-decreasing string" = "multiset" = stars and bars* — which
recurs any time a puzzle counts monotonic sequences.

### Sidebar: `group-by` on a sorted list

Racket's [`group-by`](https://docs.racket-lang.org/reference/pairs.html)
(from `racket/list`) groups *equal* elements regardless of position, so in
general it is **not** run-length encoding: `(group-by values '(1 2 1))`
gives `'((1 1) (2))`, merging the two non-adjacent `1`s. But on an
*already-sorted* list, equal elements are adjacent, so each group is a
maximal run and `(map length (group-by values ds))` equals the run lengths.
Since `part*-ok?` only inspects runs *after* the `(apply <= ds)` gate has
confirmed the digits are sorted, the one-liner

```racket
(map length (group-by values ds))   ; == run lengths, BUT ONLY when ds is sorted
```

would be a correct (and shorter) substitute for `run-length-encode` here.
The shipping source uses the explicit fold anyway, because the helper is
then honestly order-independent and the `match`-on-accumulator pattern is
the reusable teaching artifact. Knowing the `group-by`-on-sorted shortcut is
worth it: it's the idiomatic Racket move whenever you've *already* sorted.

### Sidebar: flip the predicate, skip the reverse

`digits` round-trips through a string specifically to get the digits
**most-significant-first**, so that `(apply <= ds)` reads as the natural
"never decreases." The cheaper route is to peel the digits *arithmetically*
— but `quotient`/`remainder` hand them back **least**-significant-first:

```racket
;; LSB-first: 122345 -> '(5 4 3 2 2 1). No string, no reverse.
(define (digits-lsb n)
  (if (< n 10)
      (list n)
      (cons (remainder n 10) (digits-lsb (quotient n 10)))))
```

The naïve fix would be to `reverse` that list back to MSB-first so `<=`
still applies. But a left-to-right *non-decreasing* number is, read
low-digit-to-high, a *non-increasing* list — so you don't reverse, you
**flip the comparison**: `(apply >= (digits-lsb n))`. `122345` peels to
`(5 4 3 2 2 1)`, and `(>= 5 4 3 2 2 1)` is the same verdict as
`(<= 1 2 2 3 4 5)`. The run-length encoder rides along untouched, because
run *lengths* are direction-blind — reversing the digit order can't change
the multiset of run lengths. (Verified end-to-end: the LSB-first/`>=`
variant returns the identical `1675 / 1142`.)

This is the canonical **"reverse a sequence vs. invert the predicate"**
trade: whenever the *only* reason you'd reverse a list is to make a
comparison read the conventional direction, flip the comparison instead and
delete the reverse. It generalizes far past this puzzle — ascending vs.
descending sorts (`(sort xs <)` vs `(sort xs >)`), `foldl` vs `foldr`
accumulation order, reading a stack top-down vs. bottom-up. The shipping
source keeps the MSB-first string route because at brute-force scale the
string allocation is in the noise and the `<=` reads the way the puzzle is
phrased; the point of the sidebar is the *technique*, which is worth more
than the microseconds it saves here.

One thing the trade does **not** buy you: the `(reverse runs)` inside
`run-length-encode` itself. There's no comparison on that path to flip — the
run list is consumed order-blind (only `(cdr run)` is ever read) — so that
reverse is already a no-op for *correctness*. It stays purely so the helper
returns runs in input order like a well-behaved general RLE (which
[the test](../../test/day04-test.rkt) pins); drop it and the puzzle answers
are unchanged, only the helper's general contract weakens.

---

## Tests (what's pinned and why)

[test/day04-test.rkt](../../test/day04-test.rkt) pins five layers:

1. **Parser** — `lo-hi` into an inclusive pair, with CRLF/trailing-newline
   tolerance.
2. **`digits`** — MSB-first order, repeated digits, the single-digit edge
   case.
3. **`run-length-encode`** — the consecutive-run contract on hand-checkable
   lists, including the `(1 2 1)` case that proves it's *positional* RLE
   (three runs), not a frequency count (which would say "two 1s").
4. **All six worked examples** — the puzzle's three Part 1 cases
   (`111111` ✓, `223450` ✗ decreasing, `123789` ✗ no double) and three
   Part 2 cases (`112233` ✓, `123444` ✗ buried, `111122` ✓), plus the
   instructive `111111` which passes Part 1 but **fails** Part 2 (its only
   run has length 6, never exactly 2) — a direct check that Part 2 is
   strictly stronger.
5. **The real answers** — `part1 = 1675`, `part2 = 1142`.

`raco test` runs the `module+ test` submodule; 19 checks, all green.

---

## Benchmarks

```
| Day | Parse (ms) | Part 1 (ms) | Part 2 (ms) | Total (ms) |
|-----|-----------|-------------|-------------|------------|
| 01  | 0.0144    | 0.0006      | 0.0026      | 0.0176     |
| 02  | 0.1000    | 0.0050      | 28.2450     | 28.3500    |
| 03  | 0.5200    | 92.5700     | 92.3800     | 185.4700   |
| 04  | 0.0000    | 38.5000     | 38.1000     | 76.6000    |
```

The mean is over **50** iterations (each part scans ~510k numbers, so a
single part call is tens of milliseconds — 50 is plenty for a stable mean).
What the row says:

- **Parse ≈ 0 ms**: splitting one short string on a hyphen rounds to zero.
- **Part 1 ≈ Part 2 ≈ 38 ms**: nearly identical, because both do the *same*
  work — scan every number in the range, `digits` + `run-length-encode`
  each, and test the run lengths. The cost is the per-candidate digit work
  times ~510k candidates; the `>=`-vs-`=` difference is free.
- **Total 76.6 ms**: the second-slowest day so far (behind Day 3's raster),
  and slow for the obvious reason — it's a half-million-iteration brute
  force. The combinatorial count in the "problem within the problem"
  section would drop this to microseconds, but per policy the readable scan
  ships and the closed form stays a documented idea.

---

## If I were writing this in Rust

```rust
fn digits(mut n: u32) -> Vec<u8> {
    let mut ds = Vec::new();
    if n == 0 { return vec![0]; }
    while n > 0 { ds.push((n % 10) as u8); n /= 10; }
    ds.reverse();                       // peeled LSB-first; flip to MSB-first
    ds
}

fn run_lengths(ds: &[u8]) -> Vec<usize> {
    let mut runs = Vec::new();
    for &d in ds {
        match runs.last_mut() {
            Some((v, n)) if *v == d => *n += 1,   // extend current run
            _ => runs.push((d, 1usize)),          // start a new run
        }
    }
    runs.into_iter().map(|(_, n)| n).collect()
}

fn part1_ok(n: u32) -> bool {
    let ds = digits(n);
    ds.windows(2).all(|w| w[0] <= w[1]) && run_lengths(&ds).iter().any(|&r| r >= 2)
}

fn part2_ok(n: u32) -> bool {
    let ds = digits(n);
    ds.windows(2).all(|w| w[0] <= w[1]) && run_lengths(&ds).iter().any(|&r| r == 2)
}

fn part1(lo: u32, hi: u32) -> usize { (lo..=hi).filter(|&n| part1_ok(n)).count() }
```

The correspondences worth seeing:

- **`run-length-encode`'s `for/fold` + `match` ↔ Rust's loop +
  `match runs.last_mut()`.** This is an unusually tight match: Racket
  inspects the *head* of a front-built list, Rust inspects the *tail* (last)
  of a back-pushed `Vec`, but the logic — `Some(run) if run.value == x =>
  bump`, `_ => push new` — is line-for-line the same guarded dispatch.
  Racket reverses at the end (`#:result reverse`); Rust pushes onto the back
  and never needs to.
- **`(apply <= ds)` ↔ `ds.windows(2).all(|w| w[0] <= w[1])`.** Racket's
  variadic comparison has no Rust equivalent, so the pairwise-window
  formulation is the idiomatic stand-in — and it's what the closed-form
  "compare adjacent" actually means.
- **`for/sum` + `#:when` ↔ `.filter(…).count()`.** Both are "count the
  matches" with no manual accumulator.
- **The string-route `digits` ↔ arithmetic `digits`.** Here the Rust
  version peels with `% 10` and reverses, because allocating a `String` just
  to split it would be wasteful in Rust; Racket pays the string round-trip
  for clarity since the brute force already dominates. A representation
  choice driven by which cost the language makes cheap.

---

## What's next

Day 4 is the last "standalone" warm-up before the Intcode thread resumes in
force. **Day 5** returns to the [Day 2](day02_function_guide.md) virtual
machine and grows it real teeth: **parameter modes** (immediate vs
position), **I/O opcodes** (`3` read, `4` write), and **conditional jumps**
(`5`–`8`) — the machinery every later VM day (7, 9) builds on. The
run-length-encoding banked here returns whenever a puzzle counts
consecutive sameness. See the [summary table](summary_2019.md) for the
running scoreboard, and [Day 2](day02_function_guide.md) for the Intcode
thread Day 5 picks back up.
