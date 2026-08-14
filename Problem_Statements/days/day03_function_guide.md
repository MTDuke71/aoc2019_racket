# Day 3 — Crossed Wires (function guide)

> **Historical note.** This guide annotates the frozen Racket solution
> ([src/day03.rkt](../../src/day03.rkt)), written when this repo was the
> Racket leg of a language rotation. The repo is Python-only now and the
> Racket is frozen, not deleted -- see the [README](../../README.md). The
> guide is left as it was and remains accurate about the code it describes.

> Two wires snake across a grid from a shared origin; we want their
> crossings under two different cost functions. The day's real lesson is
> the **spatial hash** — rasterize each path into a `point -> step` map and
> let a hash intersection do the geometry. Along the way it introduces
> **immutable hash tables**, the `(cons x y)`-as-point idiom destructured
> with `match-define`, and a *nested* `for*/fold` that threads three
> accumulators. Two sidebars: points as **complex numbers**, and trading
> rasterization for **segment intersection**.

## The puzzle in one paragraph

Each of two wires is a comma-separated path like `R8,U5,L5,D3` — a
direction letter (`R`/`L`/`U`/`D`) and a distance — traced from a central
port on an integer grid. The wires cross at some cells. **Part 1:** find
the crossing with the smallest **Manhattan distance** (`|x| + |y|`) from
the origin. **Part 2:** find the crossing reachable in the fewest
**combined steps** — the number of steps wire 1 walks to first reach it,
plus the number wire 2 walks to first reach it. The origin itself doesn't
count, and a wire crossing *itself* doesn't count.

---

## The algorithm in Python

Day 3 is *algorithm-flavored* (it's a data-structure choice, not a syntax
tour), so the Python companion ([python/day03.py](../../python/day03.py))
states the shape in the most legible form first:

```python
def trace(wire):
    seen, x, y, steps = {}, 0, 0, 0
    for direction, dist in wire:
        dx, dy = DIRS[direction]
        for _ in range(dist):
            x, y = x + dx, y + dy
            steps += 1
            seen.setdefault((x, y), steps)   # keep FIRST arrival
    return seen

def crossings(wires):
    h1, h2 = trace(wires[0]), trace(wires[1])
    return [(p, h1[p] + h2[p]) for p in h1.keys() & h2.keys()]
```

That's the whole idea: **rasterize each wire into a `point -> step` dict,
then the crossings are the keys the two dicts share** (`h1.keys() &
h2.keys()` is a set intersection). Part 1 minimizes `|x| + |y|` over those
points; Part 2 minimizes `h1[p] + h2[p]`. Hold this picture — the Racket
version is the same algorithm with `for*/fold` standing in for the two
nested `for` loops and an immutable `hash` standing in for `dict`.

---

## The spatial-hash pattern

The canonical name for what `trace` builds is an **occupancy map** (or
*spatial hash*): a dictionary keyed by grid cell that answers "has this
path been here, and if so, when?" in O(1). It turns a geometry question —
*where do two polylines cross?* — into a **set-membership** question,
which is the single most reusable trick in grid-based AoC puzzles.

| Geometry question | Spatial-hash realization | In `src/day03.rkt` |
|-------------------|--------------------------|--------------------|
| trace a path's cells | walk unit steps, record each | `trace` |
| "have we been here?" | hash key lookup | `hash-has-key?` |
| where do paths cross? | keys present in both hashes | the `#:when` in `crossings` |
| cheapest arrival | store the first (smallest) step | the `if`-guarded `hash-set` |

The reason it's worth naming: the *same* pattern reappears whenever a
puzzle asks "do these traced things overlap" — flood fills, light beams,
robot trails. Recognizing it here means not re-deriving it later.

---

## The Day 3 code, form by form

### `dirs` — a letter-to-delta table

```racket
(define dirs
  (hash #\R (cons  1  0)
        #\L (cons -1  0)
        #\U (cons  0  1)
        #\D (cons  0 -1)))
```

`#\R` is Racket's **character literal** (the Rust `'R'`). `(hash k v ...)`
builds an **immutable** hash from alternating key/value arguments — the
table never changes after construction, so it's a constant lookup table,
not a mutable map. `hash-ref` later turns each direction letter into its
unit step `(cons dx dy)`.

- **Rust analogue:** a `match` on the byte (`b'R' => (1, 0)`, …) or a
  `HashMap<char, (i64, i64)>`. Racket's literal hash is the closest to the
  `match`-arm version but expressed as data rather than control flow.

### `parse-input` — splitting two lines without a separator

```racket
(define (parse-input s)
  (for/list ([line (in-list (string-split (string-trim s)))])
    (map parse-move (string-split line ","))))
```

The clever bit is the **outer `string-split` with no separator argument**.
With no separator, `string-split` cuts on *runs of whitespace* and drops
empty pieces — and because path tokens (`R1008`, `U5`) never contain
spaces, the only whitespace in the file is the line break between the two
wires. So one separator-less split cleanly yields the two lines and
swallows trailing newlines and CRLF for free. Each line is then split on
`","` into tokens, and `parse-move` turns each token into `(dir . dist)`.

- **Contrast with Day 2.** Day 2 used `(string-split (string-trim s) ",")`
  — *with* a comma separator and an explicit `string-trim` — because its
  whole file was one comma-separated line. Here we exploit the two-tier
  structure: whitespace splits records (lines), commas split fields
  (moves). Same function, two jobs.
- **Rust analogue:** `s.lines().map(|l| l.split(',').map(parse_move).collect())`.

### `parse-move` — destructure a token

```racket
(define (parse-move tok)
  (cons (string-ref tok 0)
        (string->number (substring tok 1))))
```

`(string-ref tok 0)` pulls the leading direction character; `(substring
tok 1)` is everything from index 1 onward (the digits), fed to
`string->number`. A token `"R1008"` becomes `(cons #\R 1008)`.

- **Rust analogue:** `(s.as_bytes()[0] as char, s[1..].parse().unwrap())`.

### `trace` — the nested `for*/fold`

This is the heart of the day and the densest form in it:

```racket
(define (trace wire)
  (for*/fold ([pos (cons 0 0)]
              [steps 0]
              [seen (hash)]
              #:result seen)
             ([mv (in-list wire)]
              [_  (in-range (cdr mv))])
    (match-define (cons dx dy) (hash-ref dirs (car mv)))
    (define next (cons (+ (car pos) dx) (+ (cdr pos) dy)))
    (define n    (add1 steps))
    (values next
            n
            (if (hash-has-key? seen next) seen (hash-set seen next n)))))
```

Four things are happening at once; take them one at a time.

**1. `for*/fold` is a fold with multiple accumulators.** The binding list
`([pos …] [steps …] [seen …])` declares three accumulators with their
initial values, and the body must return one `(values …)` tuple updating
all three. This is `for/fold` — the same form
[Day 1](day01_function_guide.md) used for a single running total — scaled
up to three carried values.

- **Haskell precedent:** this is `foldl'` over the unit steps with a
  triple `(pos, steps, seen)` as the accumulator — exactly the
  `for/fold`-vs-`foldl'` correspondence noted for
  [Day 1](day01_function_guide.md) and Day 5, just with a tuple
  accumulator instead of a scalar. Racket lets you name the three
  components; Haskell would pattern-match the tuple in the lambda.

**2. The `*` makes the iteration nested.** `for*/fold` (star) runs the
clauses as *stacked* loops: for each `mv` in the wire, the inner
`(in-range (cdr mv))` runs `dist` times. So the body executes once per
**unit cell**, not once per move — that's what rasterizes a `U5` move into
five separate single-cell steps. Crucially, **the accumulators thread
through the entire nested iteration**: `pos` and `steps` carry over from
the last cell of one move into the first cell of the next. (Plain `for`
would walk the two clauses in lockstep; the `*` is load-bearing.)

**3. `match-define` destructures in place.** `(match-define (cons dx dy)
(hash-ref dirs (car mv)))` binds `dx` and `dy` to the two halves of the
direction delta in one line — no `(car …)`/`(cdr …)` pair. `match-define`
is the statement-position cousin of `match`: it irrefutably destructures a
known shape and binds the pieces. We'll lean on full `match` when a day
branches on *several* shapes; here there's exactly one shape, so
`match-define` is the honest tool (the same judgment call Day 2 made
choosing `case` over `match`).

**4. `#:result seen` projects out the answer.** Without it, `for*/fold`
would return all three accumulators as `(values pos steps seen)`. The
`#:result` clause says "run the fold, then hand back just this" — so
`trace` returns the hash and discards the position/step bookkeeping.

The **first-arrival rule** lives in the last line: `(if (hash-has-key?
seen next) seen (hash-set seen next n))`. Steps only ever increase, so the
first time a cell is recorded is also the cheapest arrival. If the cell is
already a key we leave the hash untouched; otherwise we add it at step
`n`. `hash-set` on an **immutable** hash returns a *new* hash sharing
structure with the old one — it doesn't mutate in place, which is why the
new value has to be threaded back through the accumulator.

#### Token by token

`for*/fold` packs a lot into one form; here is every piece of it spelled
out left to right.

| Token | What it is | What it does here |
|-------|-----------|-------------------|
| `for*/fold` | the fold-with-accumulators iterator, `*` = nested clauses | run a fold whose loop clauses stack like nested `for`s |
| `([pos (cons 0 0)]` | accumulator 1 + initial value | current position, starting at the origin |
| `[steps 0]` | accumulator 2 + initial value | total unit steps walked so far |
| `[seen (hash)]` | accumulator 3 + initial value | the point→step hash, starting empty (immutable) |
| `#:result seen)` | result projection | when the fold ends, return *just* `seen`, dropping `pos`/`steps` |
| `([mv (in-list wire)]` | outer loop clause | bind `mv` to each move `(dir . dist)` in turn |
| `[_ (in-range (cdr mv))])` | inner loop clause | run the body `dist` times; `_` = "I don't need the index" |
| `(match-define (cons dx dy) (hash-ref dirs (car mv)))` | destructuring bind | look up this move's unit delta, name its halves `dx`/`dy` |
| `(define next (cons (+ (car pos) dx) (+ (cdr pos) dy)))` | local | the cell one step along, `(x+dx, y+dy)` |
| `(define n (add1 steps))` | local | the step count *at* `next` (one more than before) |
| `(values next n …)` | the three updated accumulators | hand back new `pos`, new `steps`, new `seen` for the next iteration |
| `(if (hash-has-key? seen next) seen (hash-set seen next n))` | the `seen` update | first-arrival rule: keep the old hash if `next` is already recorded, else add `next ↦ n` |

The two mental anchors: **`#:result` is a projection** (the fold computes
three things, you keep one), and **the `*` is what makes one iteration =
one unit cell** rather than one move. Strip the `*` and the two clauses
would run in lockstep — you'd visit only `min(#moves, max-dist)` cells and
get nonsense. Everything else is ordinary `define`/`if` inside a loop body.

### `crossings`, `part1`, `part2`

```racket
(define (crossings wires)
  (define h1 (trace (first wires)))
  (define h2 (trace (second wires)))
  (for/list ([(p s1) (in-hash h1)]
             #:when (hash-has-key? h2 p))
    (cons p (+ s1 (hash-ref h2 p)))))

(define (part1 wires)
  (apply min (map (lambda (c) (manhattan (car c))) (crossings wires))))

(define (part2 wires)
  (apply min (map cdr (crossings wires))))
```

`crossings` traces both wires and keeps one `(point . combined-steps)`
entry per shared cell. `(in-hash h1)` iterates **key and value together**
— `p` is the point, `s1` is wire 1's step count — and `#:when
(hash-has-key? h2 p)` keeps only the cells wire 2 also visited. That
`#:when` *is* the set intersection from the Python (`h1.keys() &
h2.keys()`), spelled as a filtered comprehension.

#### Token by token

The same left-to-right treatment as `trace`, for the comprehension that
does the intersection:

| Token | What it is | What it does here |
|-------|-----------|-------------------|
| `for/list` | the list **comprehension** iterator | run the loop and *collect* each body value into a list |
| `([(p s1) (in-hash h1)]` | a 2-value binding clause over a hash | bind `p` and `s1` to each **key and value** of `h1` — point and its wire-1 step count |
| `#:when (hash-has-key? h2 p))` | a filter guard | keep only iterations where `p` is also in `h2` — i.e. cells **both** wires visited |
| `(cons p (+ s1 (hash-ref h2 p)))` | the body / collected value | pair the point with the **combined** steps: wire-1's `s1` plus wire-2's `(hash-ref h2 p)` |

Three things worth pinning:

- **`for/list` vs `for*/fold`.** `trace` used `for*/fold` because it was
  *accumulating* one growing value (the hash). `crossings` is *mapping +
  filtering* a sequence into a fresh list, which is exactly `for/list`'s
  job — no accumulator to thread, the result is just "the body, collected."
  Same `for` family, two different shapes: fold when you reduce, `/list`
  when you transform.
- **The two-identifier binding `[(p s1) …]`** is the destructuring form of
  a `for` clause: when the sequence yields *two* values per step (as
  `in-hash` does — key and value), you name both in parentheses. Compare
  Python's `for p, s1 in h1.items()`.
- **`#:when` is the filter, the body is the map.** Reading the clause as
  "the set intersection" is right, but mechanically it's a guard that skips
  non-matching iterations *and* a body that transforms the survivors —
  filter and map fused into one pass. Rust: `h1.iter().filter(|(p,_)|
  h2.contains_key(p)).map(|(p,s1)| (p, s1 + h2[p])).collect()`.

Then both parts are one-liners over the same `crossings` list: Part 1
minimizes `manhattan` of the point, Part 2 minimizes the combined step
count. `(apply min lst)` is "min of a list" — `apply` splices the list in
as min's arguments (Rust's `iter().min().unwrap()`).

- **Note the redundancy:** `part1` and `part2` each call `crossings`,
  which traces both wires — so `solve` rasterizes all four wire-traces
  twice over. That's deliberate (the parts stay independent pure functions
  of the parsed input, matching Day 1/Day 2's shape), and it's the single
  biggest line item in the benchmark. The "Optimization, measured" section
  below shows the trace-once variant ([src/day03a.rkt](../../src/day03a.rkt))
  that halves it.

---

## The problem within the problem: it's a set intersection in disguise

The puzzle's prose is geometric ("wires twist and turn and cross"), but
the moment you rasterize, **all of the geometry collapses into a hash-set
intersection**. That reframing is the transferable insight: a surprising
number of grid puzzles that *sound* like computational geometry are really
"build two membership sets and intersect them." Naming it — *occupancy map
+ set intersection* — is what lets you reach for it on sight next time
instead of re-deriving a coordinate sweep.

### Sidebar: points as complex numbers

Racket has first-class **exact complex numbers**, and they make a 2D point
representation that most languages can't match. A point is `x+yi`,
translation is *addition*, and the four directions are the four unit
complex values:

```racket
(define dirs (hash #\R 1 #\L -1 #\U 0+i #\D 0-i))   ; i = (sqrt -1)

(define (step pos dir) (+ pos (hash-ref dirs dir)))  ; move = complex add
(define (manhattan p)  (+ (abs (real-part p)) (abs (imag-part p))))
```

Stepping a cell is just `(+ pos dir)`; the hash key is the complex number
itself (`equal?` compares them component-wise). The deep payoff isn't
here, though — it's that **rotation is multiplication by `i`**: turning
left 90° is `(* dir 0+i)`, turning right is `(* dir 0-i)`. Day 3 only
translates, so it doesn't need the rotation, but [Day 11](day11_function_guide.md)'s
painting robot turns constantly, and there the complex-number model turns
a four-way `cond` on heading into one multiply. (One wart to know: `(make-rectangular
5 0)` collapses to the *real* `5`, so x-axis points are reals — harmless
for hashing since the collapse is consistent, but surprising the first
time you see a real number as a "point.") The shipping source uses `(cons
x y)` because it's the most transparent for a translation-only day; the
complex model earns its keep when turning enters.

- **Rust contrast:** Rust has no built-in complex type for this; you'd
  reach for a `Point { x, y }` struct or `num::Complex<i64>`. The "turn =
  multiply by i" trick is genuinely cleaner in Racket — a rare case where
  the dynamic Lisp out-ergonomics the systems language.

### Sidebar: segment intersection (the O(n²) alternative)

Rasterizing is O(total path length) — ~150k cells per wire here. The
classic alternative keeps each move as an **axis-aligned segment** and
intersects the ~300 segments of one wire against the other's: O(n²) in
*segment* count (~90k cheap interval overlap tests), independent of how
long each segment is. For a wire made of a few very long runs, segment
intersection wins decisively; for AoC's many-short-moves inputs the two
are comparable and the raster is far simpler to get right (Part 2's
step-accounting and collinear-overlap handling are fiddly in the segment
version). The raster ships in both languages for that reason; the segment
method is the thing to remember when path lengths dwarf segment counts.

### Optimization, measured: [src/day03a.rkt](../../src/day03a.rkt)

The benchmark's cost is dominated by tracing each wire **four times** per
`solve` (twice in `part1`, twice in `part2`). Two candidate speedups
suggest themselves; the interesting part is that **only one of them
survives a benchmark**, and it isn't the one a systems programmer reaches
for first. Both were measured on the real input, double-`collect-garbage`
isolated, mean of 200–300 iterations.

**(a) Trace once — the real win, 2.0×.** `part1` and `part2` are
independent pure functions, which is clean but means a `solve` calls
`crossings` (hence traces the wire pair) twice. [src/day03a.rkt](../../src/day03a.rkt)
adds a `both-parts` that traces once and reads both answers off the single
crossings list:

```racket
(define (both-parts wires)
  (define cs (crossings wires))                      ; trace the pair ONCE
  (values (apply min (map (lambda (c) (manhattan (car c))) cs))
          (apply min (map cdr cs))))
```

```
day03  part1 then part2 (crossings ×2, 4 traces): 183.97 ms
day03a both-parts       (crossings ×1, 2 traces):  91.91 ms   ← 2.0×
```

Exactly the halving you'd predict from cutting four traces to two. Pure
algorithmic structure, no representation change. (test/day03a-test.rkt
pins that it gives the identical answers.)

**(b) Mutable hash — the dead-end that looks like a win.** The obvious
systems-programmer move is to replace ~150k allocating `hash-set` calls
with one `make-hash` mutated in place via `hash-ref!`:

```racket
(define (trace-mut wire)
  (define seen (make-hash))                          ; mutable, equal?-keyed
  (for*/fold ([pos (cons 0 0)] [steps 0] #:result seen)
             ([mv (in-list wire)] [_ (in-range (cdr mv))])
    (match-define (cons dx dy) (hash-ref dirs (car mv)))
    (define next (cons (+ (car pos) dx) (+ (cdr pos) dy)))
    (define n (add1 steps))
    (hash-ref! seen next n)                           ; insert iff absent
    (values next n)))
```

`hash-ref!` even gives the first-arrival rule for free (insert iff absent).
And benched *in isolation*, building a mutable hash looks ~2× faster than
building the immutable one. But that isolated number is a **GC-accounting
artifact** — the immutable build's allocation triggers a collection
*inside* its own measurement loop. Benched end-to-end (build *and* the
crossing scan that follows), the mutable version is consistently **~8%
slower**:

```
immutable trace-once (crossings ×1):  95.30 ms
mutable   trace-once (crossings ×1): 102.80 ms   ← slower
```

Two reasons. First, the crossing scan does ~150k `hash-has-key?`/`hash-ref`
probes, and mutable `equal?`-keyed hashes don't recover enough on lookup to
pay back the build. Second, **Racket CS's immutable hashes are HAMTs**
(hash array-mapped tries) — structural sharing makes `hash-set` far cheaper
than "copy the whole table," so the allocation it does pay isn't the cliff
C intuition expects. The lesson is the transferable one: *measure the whole
pipeline, not the phase you assumed was hot* — and don't assume mutable
beats persistent on a managed runtime with a good immutable map.

Per the repo's optimization policy, the shipping [src/day03.rkt](../../src/day03.rkt)
stays idiomatic and immutable; [src/day03a.rkt](../../src/day03a.rkt) is the
tested trace-once variant, and the mutable-hash route is documented here as
the measured dead-end it turned out to be.

---

## Tests (what's pinned and why)

[test/day03-test.rkt](../../test/day03-test.rkt) pins four layers:

1. **Parser** — two-line split, multi-digit distances, and CRLF/trailing-
   newline tolerance.
2. **`trace` bookkeeping** on hand-checkable wires: a straight `R2,U1`
   gives the exact step count at each cell and excludes the origin as a
   *start*; a doubling-back `R2,L2` proves the **first-arrival rule**
   (the revisited cell keeps step 1, not 3) and that stepping *back onto*
   the origin later does get recorded.
3. **All three worked examples, both parts** — Part 1 and Part 2 have
   different published answers per example (`6/30`, `159/610`, `135/410`),
   so each example pins both cost functions.
4. **The real answers** — `part1 = 2180`, `part2 = 112316`.

`raco test` runs the `module+ test` submodule; 18 checks, all green.

---

## Benchmarks

```
| Day | Parse (ms) | Part 1 (ms) | Part 2 (ms) | Total (ms) |
|-----|-----------|-------------|-------------|------------|
| 01  | 0.0143    | 0.0006      | 0.0026      | 0.0175     |
| 02  | 0.1050    | 0.0050      | 25.7050     | 25.8150    |
| 03  | 0.5200    | 92.2400     | 92.2750     | 185.0350   |
```

The mean is over **200** iterations (like Day 2 — a single part call is
real work, not a microsecond kernel). What the row says:

- **Parse ≈ 0.5 ms**: the most expensive parse yet — two lines, ~600 total
  tokens, each `substring` + `string->number`.
- **Part 1 ≈ Part 2 ≈ 92 ms**: nearly identical, because *each* part does
  the same thing — trace both wires (~300k total unit-cell `hash-set`s
  into persistent hashes) and scan the crossings. The cost is the
  rasterization, not the min.
- **Total 185 ms**: the slowest day so far, and it's slow for a
  *structural* reason — `solve` traces the wire pair four times. The
  measured trace-once variant ([src/day03a.rkt](../../src/day03a.rkt))
  cuts this in half — `184 → 92 ms`, a clean 2.0× — and the
  optimization section above has the full writeup, including why the
  "obvious" mutable-hash speedup actually loses on Racket CS. Per policy
  the readable version ships and the fast one lives alongside.

---

## If I were writing this in Rust

```rust
use std::collections::HashMap;

const DIRS: &[(u8, (i64, i64))] = &[(b'R', (1, 0)), (b'L', (-1, 0)),
                                    (b'U', (0, 1)), (b'D', (0, -1))];

fn delta(d: u8) -> (i64, i64) { DIRS.iter().find(|x| x.0 == d).unwrap().1 }

fn trace(wire: &[(u8, i64)]) -> HashMap<(i64, i64), i64> {
    let mut seen = HashMap::new();
    let (mut x, mut y, mut steps) = (0i64, 0i64, 0i64);
    for &(dir, dist) in wire {
        let (dx, dy) = delta(dir);
        for _ in 0..dist {
            x += dx; y += dy; steps += 1;
            seen.entry((x, y)).or_insert(steps);   // first-arrival rule
        }
    }
    seen
}

fn part1(wires: &[Vec<(u8, i64)>]) -> i64 {
    let (h1, h2) = (trace(&wires[0]), trace(&wires[1]));
    h1.keys().filter(|p| h2.contains_key(*p))
        .map(|&(x, y)| x.abs() + y.abs()).min().unwrap()
}
```

The correspondences worth seeing:

- Racket's immutable `hash` + threaded `hash-set` ↔ Rust's mutable
  `HashMap` with `.entry((x,y)).or_insert(steps)`. The Rust `or_insert`
  *is* the first-arrival rule in one method call — the same idea as the
  `if (hash-has-key? …)` guard and `hash-ref!`. Rust mutates in place by
  default, so it skips the persistent-hash allocation Racket's idiomatic
  version pays for (and which the sidebar reclaims with `make-hash`).
- `for*/fold` with threaded `(pos steps seen)` ↔ the two nested `for`
  loops with `mut x, y, steps`. Racket folds the carried state into named
  accumulators; Rust uses ordinary mutable locals. Same data flow, two
  spellings of "carry state across a nested loop."
- `(in-hash h1)` key/value iteration + `#:when` ↔ `h1.keys().filter(…)`.
  The set intersection is a filtered iterator in both.
- The `(cons x y)` point ↔ a `(i64, i64)` tuple, both used directly as a
  hash key. The complex-number representation has no clean Rust analogue —
  see that sidebar.

---

## What's next

Day 3 is the last "pure data structures" warm-up before the puzzles start
varying in flavor. **Day 4** is a small number-theory/combinatorics day
(password rules over a digit range) — a change of pace from grids and
VMs — and then **Day 5** returns to Intcode and grows the
[Day 2](day02_function_guide.md) machine its first teeth: parameter modes,
I/O opcodes, and conditional jumps. The spatial-hash pattern banked here
comes back the moment a later day traces something on a grid. See the
[summary table](summary_2019.md) for the running scoreboard, and
[Day 2](day02_function_guide.md) for the Intcode thread this day takes a
break from.
