# Day 10 — Monitoring Station (function guide)

> **Historical note.** This guide annotates the frozen Racket solution
> ([src/day10.rkt](../../src/day10.rkt)), written when this repo was the
> Racket leg of a language rotation. The repo is Python-only now and the
> Racket is frozen, not deleted -- see the [README](../../README.md). The
> guide is left as it was and remains accurate about the code it describes.

> The first **lattice-geometry day** of 2019 — and the Intcode VM
> ([Day 9](day09_function_guide.md)) sits this one out entirely. Both
> parts hinge on a single number-theory fact: the direction from one grid
> point to another, reduced by its **gcd**, is a *canonical name for a
> line of sight*. Part 1 ("most asteroids visible") is "count the distinct
> reduced directions" — collinear asteroids share a name and collapse.
> Part 2 ("200th vaporized by a clockwise laser") sorts those directions
> by **`atan2` angle** and **round-robins** the rays. New Racket along the
> way: `in-indexed` (enumerate), nested `for*/list`, `argmax`,
> `hash-update!`, the two-argument `atan` (atan2), and `pi`.

## The puzzle in one paragraph

The input is an ASCII grid of `.` (empty) and `#` (asteroid). A station on
an asteroid can *detect* another asteroid iff no third asteroid sits
*exactly* on the segment between them. **Part 1:** place the station on the
asteroid that detects the most others; report that count. **Part 2:** from
that station, a laser starts pointing straight up and rotates **clockwise**,
vaporizing the nearest asteroid on each bearing as it sweeps past — one per
bearing per full rotation. Report the **200th** asteroid vaporized, encoded
as `x*100 + y`. On the real input the best station is at `19,11` detecting
`230`, and the 200th vaporized is `12,5` → `1205`.

---

## The algorithm in Python

Day 10 is *algorithm-flavored* — the lesson is the gcd-reduced direction
vector and the angular sweep, not Racket syntax — so the Python companion
([python/day10.py](../../python/day10.py)) states the shape first:

```python
import math
from collections import defaultdict

def parse_input(text):
    return [(x, y)
            for y, row in enumerate(text.split())
            for x, ch in enumerate(row) if ch == "#"]

def direction(dx, dy):                 # primitive direction = delta / gcd
    g = math.gcd(abs(dx), abs(dy))
    return (dx // g, dy // g)

def count_visible(station, asteroids):
    sx, sy = station
    return len({direction(x - sx, y - sy) for (x, y) in asteroids if (x, y) != station})

def best(asteroids):                   # (station, count); Part 1 = count
    return max(((a, count_visible(a, asteroids)) for a in asteroids), key=lambda p: p[1])

def vaporization_order(station, asteroids):
    sx, sy = station
    dist2 = lambda a: (a[0]-sx)**2 + (a[1]-sy)**2
    angle = lambda a: math.atan2(a[0]-sx, -(a[1]-sy)) % (2*math.pi)  # cw from up
    groups = defaultdict(list)
    for a in asteroids:
        if a != station:
            groups[direction(a[0]-sx, a[1]-sy)].append(a)
    rays = [sorted(m, key=dist2)                       # each ray near->far
            for _, m in sorted(groups.items(), key=lambda kv: angle(kv[1][0]))]
    order = []
    while any(rays):                                   # one pass = one rotation
        for ray in rays:
            if ray: order.append(ray.pop(0))
    return order

def part2(asteroids):
    station, _ = best(asteroids)
    x, y = vaporization_order(station, asteroids)[199]  # the 200th
    return 100 * x + y
```

Hold this picture: the Racket version is the same five functions with
`for*/list` for the comprehension, a `set` for the distinct-direction count,
`argmax` for the `max(..., key=...)`, `hash-update!` for the `defaultdict`,
and a tail-recursive `rotate` loop for the `while any(rays)`.

---

## The key idea: a gcd-reduced delta *is* a line of sight

Everything in this puzzle is the same observation viewed twice. Take the
station at `S` and another asteroid at `A`; the vector `A − S = (dx, dy)`
points along the ray from `S` through `A`. Now factor out the greatest
common divisor `g = gcd(|dx|, |dy|)`:

```
(dx, dy) = g · (dx/g, dy/g)
```

The reduced pair `(dx/g, dy/g)` is the **primitive direction vector** — the
shortest integer step in that exact direction. Two facts fall out, and they
*are* the two parts of the puzzle:

1. **Two asteroids share a line of sight from `S` iff their primitive
   directions are equal.** If `A` and `B` both reduce to `(1, 2)`, they lie
   on the one ray `S + t·(1,2)`, so the nearer one blocks the farther.
   Distinct primitive directions ⟺ distinct sightlines ⟺ separately
   visible asteroids. (Part 1.)

2. **The number of asteroids the laser must pass on a bearing before the
   next bearing is exactly how many share that primitive direction** — and
   they die nearest-first, one per rotation. (Part 2.)

There's a third, classic form of the same fact worth banking, because it's
the one that shows up in number-theory problems: *the count of integer
lattice points strictly between two grid points `P` and `Q` is
`gcd(|dx|, |dy|) − 1`*. The `g` we divide out is literally counting the
asteroids-that-could-block positions on the segment. Same `g`, three faces.

> **Why integer gcd and not floating-point slope?** Slope `dy/dx` loses the
> *sign pair* (it can't tell `(1,2)` from `(−1,−2)`, opposite rays) and
> introduces rounding — two truly-collinear points might disagree in the
> 15th decimal and fail to collapse. The reduced integer pair is *exact*
> and keeps the quadrant, which is why `(dx/g, dy/g)` and not a `double` is
> the right hash key. This is the same "exact rational over float" judgment
> as Day 3's grid intersections.

---

## The Day 10 code, form by form

### `parse-input` — `for*/list` + `in-indexed` collects coordinates

```racket
(define (parse-input s)
  (for*/list ([(row y) (in-indexed (in-list (string-split s)))]
              [(ch  x) (in-indexed (in-string row))]
              #:when (char=? ch #\#))
    (cons x y)))
```

We never need the grid as a grid — only the asteroid coordinates — so the
parser flattens straight to a list of `(x . y)` pairs. Three pieces, two of
them new:

- **`in-indexed`** wraps any sequence so each step yields *two* values:
  the element and its 0-based index. `[(row y) (in-indexed …)]` binds
  `row` to the line and `y` to its row number — Racket's `enumerate`. We
  saw the equivalent built by hand on [Day 6](day06_function_guide.md) with
  a parallel `in-naturals` clause; `in-indexed` is the packaged form.
- **`for*/list` nests.** The `*` is load-bearing: a plain `for/list` with
  two clauses advances them in *lockstep* (Day 6's `enumerate` trick),
  whereas `for*/list` makes the second clause an *inner loop* over the
  first — rows on the outside, columns on the inside, exactly the double
  comprehension in the Python. (`for*` ↔ `for` is the same nest-vs-lockstep
  distinction first drawn on [Day 3](day03_function_guide.md).)
- **`#:when (char=? ch #\#)`** filters to asteroid cells before the body
  runs, so the body only ever produces real coordinates.

The result for the 5×5 example is
`'((1 . 0) (4 . 0) (0 . 2) (1 . 2) … (3 . 4) (4 . 4))` — row-major, which is
just the order the nested loop visits.

- **Rust analogue:** `text.lines().enumerate().flat_map(|(y, row)|
  row.char_indices().filter(|(_, c)| *c == '#').map(move |(x, _)| (x as
  i64, y as i64))).collect()` — `flat_map` is the `for*` nest, `enumerate`
  / `char_indices` are the two `in-indexed`s.

### `direction` — the gcd reduction

```racket
(define (direction dx dy)
  (define g (gcd (abs dx) (abs dy)))
  (cons (quotient dx g) (quotient dy g)))
```

`gcd` is in `racket/base`; it takes absolute values implicitly for the
*magnitude* but we feed `(abs …)` to be explicit, then divide the *signed*
deltas so the quadrant survives: `(direction -3 6)` is `(-1 . 2)`,
distinct from `(direction 3 -6)` = `(1 . -2)` (the opposite ray).
`quotient` is integer division (truncating toward zero), and because `g`
exactly divides both components there's no remainder to worry about. `g` is
never `0` because every caller excludes the station itself (the only
zero-delta).

#### Worked numbers: the 5×5 map, from the station at `3,4`

The smallest spec map is the cleanest place to watch the reduction do its
job, because the puzzle prose *tells us the answer*: the station at `3,4`
detects 8, and *"the only asteroid it cannot detect is the one at `1,0`; its
view is blocked by the asteroid at `2,2`."* Run `direction` on the delta to
every other asteroid (`dx = ax − 3`, `dy = ay − 4`):

| asteroid | `dx` | `dy` | `g = gcd(\|dx\|,\|dy\|)` | `(dx/g, dy/g)` |
|----------|------|------|------------------------|----------------|
| (1,0) | −2 | −4 | gcd(2,4)=**2** | **(−1, −2)** |
| (4,0) |  1 | −4 | gcd(1,4)=1 | (1, −4) |
| (0,2) | −3 | −2 | gcd(3,2)=1 | (−3, −2) |
| (1,2) | −2 | −2 | gcd(2,2)=2 | (−1, −1) |
| (2,2) | −1 | −2 | gcd(1,2)=1 | **(−1, −2)** |
| (3,2) |  0 | −2 | gcd(0,2)=2 | (0, −1) |
| (4,2) |  1 | −2 | gcd(1,2)=1 | (1, −2) |
| (4,3) |  1 | −1 | gcd(1,1)=1 | (1, −1) |
| (4,4) |  1 |  0 | gcd(1,0)=1 | (1, 0) |

Nine deltas, but **`(1,0)` and `(2,2)` both reduce to `(−1, −2)`** — every
other row is unique. So the `set` in `count-visible` holds 8 elements, the 8
detected, and the lone collision is the blocked pair. The geometry behind
the collision: the raw delta to `(1,0)` is `(−2,−4) = 2·(−1,−2)`, *exactly
twice* the delta to `(2,2)`, so the two sit on one ray with `(2,2)` (distance
√5) in front of `(1,0)` (distance 2√5). The gcd *names that ray* `(−1,−2)`
and the set collapses the two asteroids on it to one detectable — Part 1's
entire trick, recovered from one `gcd`.

Three details the table makes concrete:

- **Sign is load-bearing.** `(1,0)` reduces to `(−1,−2)`, **not** `(1,2)`.
  A hypothetical asteroid down-right at `(4,6)` would give delta `(1,2)` →
  the *opposite* ray, vaporized half a rotation later. A float slope
  `dy/dx` computes `2` for *both* `(−1,−2)` and `(1,2)` and wrongly merges
  them; the signed integer pair keeps the quadrant.
- **`g` divides exactly.** `−4/2 = −2` with no remainder — `g` is by
  definition a common divisor, which is why `quotient` is safe.
- **Zero components reduce cleanly.** `(3,2)` → `(0,−1)` (straight up),
  `(4,4)` → `(1,0)` (straight right): `gcd(0,k)=k`, so axis-aligned deltas
  collapse to unit steps. The only fatal delta is `(0,0)` — station to
  itself — excluded by `count-visible`'s `#:unless`.

### `count-visible` — distinct directions via a `set`

```racket
(define (count-visible station asteroids)
  (define sx (car station))
  (define sy (cdr station))
  (for/fold ([dirs (set)] #:result (set-count dirs))
            ([a (in-list asteroids)] #:unless (equal? a station))
    (set-add dirs (direction (- (car a) sx) (- (cdr a) sy)))))
```

This is Part 1's whole engine. `for/fold` threads an accumulator `dirs`
(starting at the empty `set`) across the asteroid list, `set-add`ing each
one's primitive direction. Because a set *dedups*, every collinear cluster
contributes a single element automatically — the "blocked by a nearer
asteroid" rule needs no explicit distance check, it's a side effect of the
data structure. Two idioms worth naming:

- **`#:result (set-count dirs)`** post-processes the final accumulator: the
  fold builds the set, then `#:result` projects out just its cardinality.
  (Same `#:result` keyword used to project the answer on
  [Day 9](day09_function_guide.md)'s VM fold.)
- **`#:unless (equal? a station)`** skips the station itself — the one
  asteroid whose delta is `(0,0)` and would crash `direction`'s `gcd`.

`set`, `set-add`, `set-count` come from `racket/set` (bundled into
`#lang racket`); the default `set` is a hash set with `equal?` semantics,
so `(cons 1 2)` keys compare by value — exactly what we need.

### `best` — `argmax` over tagged asteroids

```racket
(define (best asteroids)
  (argmax cdr
          (for/list ([a (in-list asteroids)])
            (cons a (count-visible a asteroids)))))
```

We tag each asteroid with its visible count — a list of
`((x . y) . count)` — and let **`argmax`** return the *element* that
maximizes the key function. The subtlety, and the reason `argmax` (not
`max`) is the right tool: we want the *winning asteroid*, not the winning
*count*. `argmax cdr` says "score each element by its `cdr`, return the
whole element with the top score." `part1` then reads off the `cdr`:

```racket
(define (part1 asteroids) (cdr (best asteroids)))
```

This is the day's **O(n²)** core: `best` calls `count-visible` once per
asteroid (n of them), and each `count-visible` scans all n others. With
n ≈ 310 that's ~96k direction reductions — the 13.8 ms Part 1 line below.

- **Rust analogue:** `asteroids.iter().map(|&a| (a, count_visible(a,
  asteroids))).max_by_key(|&(_, c)| c).unwrap()` — `max_by_key` is `argmax`.

### `vaporization-order` — group, sort each ray, round-robin

This is Part 2, in three movements. First the geometry helpers:

```racket
  (define (dist2 a) (+ (sqr (- (car a) sx)) (sqr (- (cdr a) sy))))
  (define (angle a)
    (define θ (atan (- (car a) sx) (- sy (cdr a))))
    (if (negative? θ) (+ θ (* 2 pi)) θ))
```

- **`dist2` skips the square root.** We only ever *compare* distances along
  one bearing, and `x ↦ x²` is monotonic on non-negative reals, so squared
  distance sorts identically to true distance for a fraction of the cost.
  (Same "compare in the cheaper monotone space" move as avoiding `sqrt` in
  nearest-neighbor code generally.)
- **`angle` is the clockwise-from-up bearing**, and the argument order is
  the whole trick — see the dedicated section below. `atan` with *two*
  arguments is Racket's `atan2`; `pi` comes from `racket/math` (bundled
  into `#lang racket`).

Second, group asteroids by bearing with `hash-update!`:

```racket
  (define groups (make-hash))
  (for ([a (in-list asteroids)] #:unless (equal? a station))
    (hash-update! groups (direction (- (car a) sx) (- (cdr a) sy))
                  (λ (members) (cons a members)) '()))
```

**`hash-update!`** is the mutable-hash "modify the value at a key" call: it
looks up the key, applies the function to the current value, and stores the
result. The third argument is the **default** used when the key is absent —
here `'()`, so the first asteroid on a new bearing starts a fresh list.
This is precisely Python's `defaultdict(list)` + `.append`, fused into one
call. (Contrast [Day 6](day06_function_guide.md)'s *immutable* `for/hash`,
which builds a hash all at once; here we accumulate into a mutable one
because each key's value grows across iterations.)

Third — and this is the heart — sort the rays and round-robin them:

```racket
  (define rays
    (sort (for/list ([members (in-hash-values groups)])
            (sort members < #:key dist2))
          < #:key (λ (ray) (angle (car ray)))))
  (let rotate ([rays rays] [order '()])
    (if (andmap null? rays)
        (reverse order)
        (rotate (map (λ (ray) (if (null? ray) ray (cdr ray))) rays)
                (for/fold ([order order]) ([ray (in-list rays)] #:when (pair? ray))
                  (cons (car ray) order)))))
```

Two nested sorts build `rays`:

1. **Inner** `(sort members < #:key dist2)` orders each bearing's asteroids
   **near→far** — the order the laser hits them.
2. **Outer** `(sort … #:key (λ (ray) (angle (car ray))))` orders the rays
   themselves by **clockwise angle**. Every member of a ray shares the
   bearing, so the nearest member (`car ray`) is a fine representative for
   the angle.

Then `rotate` is the laser:

- **Each pass = one full rotation.** The `for/fold` walks the angle-sorted
  rays once and `cons`es the *head* of every nonempty ray onto `order` — that
  pass vaporizes the nearest survivor on every bearing, in clockwise order.
- **`(map cdr …)` advances all rays** by dropping those heads, then
  `rotate` recurs. When `(andmap null? rays)` — every ray drained — we
  `reverse` the accumulated `order` once (it was built head-first, like
  every cons-accumulator since [Day 4](day04_function_guide.md)).

Most inputs (including this one: 230 ≥ 200) settle the 200th in the *first*
rotation, but `rotate` is fully general — it keeps sweeping until the last
straggler behind a triple-stack falls, matching the spec's "9 partway
through its third rotation" example.

`part2` reads off the 200th (index 199) and encodes it:

```racket
(define (part2 asteroids)
  (define station (car (best asteroids)))
  (define target (list-ref (vaporization-order station asteroids) 199))
  (+ (* 100 (car target)) (cdr target)))
```

---

## The angle convention, nailed down

Getting the laser to start *up* and turn *clockwise* is the one place this
puzzle bites, so here is the derivation rather than a magic incantation.

Two coordinate facts collide:

- **The grid's y grows *downward*** (row 0 is the top). So "up" — the
  laser's start — is the **−y** direction.
- **`atan2` is defined math-style**: `(atan y x)` returns the angle of the
  point `(x, y)` measured **counter-clockwise from the +x axis**, in
  `(−π, π]`.

We want a function that returns `0` for up, increasing **clockwise**:
up → right → down → left. The substitution that does it is
`(atan dx (- dy))` — i.e. feed `dx` as atan2's "y" and `-dy` as its "x":

| Direction | `(dx, dy)` | `(atan dx (- dy))` | after wrap |
|-----------|-----------|--------------------|-----------|
| up        | `(0, -1)` | `atan(0, 1) = 0`     | `0`        |
| right     | `(1, 0)`  | `atan(1, 0) = π/2`   | `π/2`      |
| down      | `(0, 1)`  | `atan(0, -1) = π`    | `π`        |
| left      | `(-1, 0)` | `atan(-1, 0) = -π/2` | `3π/2`     |

In the code the deltas are written `(- (car a) sx)` for `dx` and the *x*
argument as `(- sy (cdr a))` — which is `-(dy)` since `dy = (cdr a) - sy`.
The `(if (negative? θ) (+ θ (* 2 pi)) θ)` wrap lifts the bottom-left
quadrant (left side, which `atan` reports as negative) up into `[π, 2π)`,
giving one monotonic clockwise sweep over `[0, 2π)`. Sort ascending and you
have the firing order.

> **Mental model:** swapping atan2's arguments reflects the plane across the
> line `y = x`, which converts "counter-clockwise from +x" into "clockwise
> from +y"; negating the second argument then flips +y to point *up* in
> screen space. You can rederive it any time from the four cardinal
> directions in the table — that's faster than memorizing the formula.

### Same direction ⟺ same angle — and why grouping is exact but ordering is float

The angle is a **pure function of the primitive direction**, and that fact
runs in both directions:

- **Same direction → same angle.** `atan2` depends only on the *ratio*
  `dx : −dy` and the *quadrant*, both invariant along a ray. The two
  collinear asteroids from the worked example — `(2,2)` with delta `(−1,−2)`
  and `(1,0)` with delta `(−2,−4) = 2·(−1,−2)` — give
  `atan(−1, 2) = atan(−2, 4) ≈ 5.820 rad ≈ 333.4°`. Positive scaling can't
  change the bearing.
- **Different direction → different angle.** The map *direction → angle* is
  **injective** over primitive vectors: two integer vectors share an
  `atan2` only when one is a *positive* multiple of the other, and two
  *primitive* vectors that are positive multiples are equal. So distinct
  rays never tie in angle — which is exactly why `(sort rays … #:key angle)`
  is a strict total order and the clockwise firing sequence is unambiguous.

There's a floating-point subtlety the code quietly sidesteps. `atan2` runs
on `double`s, so `atan(−1, 2)` and `atan(−2, 4)` aren't *guaranteed*
bit-identical (last-ULP wobble on scaled arguments). But notice `angle` is
applied **once per ray, to `(car ray)`** — the nearest representative — never
to two collinear members for comparison. Each ray carries a single angle
value, so:

- the **equivalence** ("same bearing?") is decided by *exact integer*
  `direction` equality in the `hash-update!` grouping — no float compares;
- the float `atan2` is used *only* to **order** the already-formed rays.

Exact where it must be exact, float only as a sort key. That split is
deliberate, and it's the reason the collinear-points float-equality question
— which would be a real bug if we'd grouped asteroids *by angle* instead of
by reduced direction — never arises.

---

## The problem within the problem: visibility is an equivalence relation

Strip the asteroid costume and Part 1 is a statement about **equivalence
classes**. Fix the station as origin; define `A ∼ B` iff `A` and `B` lie on
the same ray (same primitive direction). This `∼` is an equivalence relation
(reflexive, symmetric, transitive), it partitions the other asteroids into
classes, and **the number visible is the number of classes** — one
representative (the nearest) is detectable per class. The gcd reduction is
just the *canonical-form* function that labels each class; hashing on the
label is how you count classes without comparing every pair.

That reframing is the transferable part. "Count distinct directions /
slopes through a fixed point" recurs all over computational geometry —
counting lines through point sets, the "visible points from the origin"
classic (which is *exactly* this, and whose density is `6/π²`, the
probability two random integers are coprime), maximum-points-on-a-line
problems in interview canon. The canonical-form-by-gcd trick is the same
one that powers hashing rational slopes without floating point.

Part 2 then adds a **total order** on top of the partition: sort the classes
by angle (a *cyclic* order made linear by fixing the up-bearing as 0), sort
within each class by distance, and the laser's firing sequence is the
lexicographic *(rotation index, angle)* enumeration — which the round-robin
produces directly. Recognizing "partition, then order each axis" is what
turns a fiddly simulation into three library calls (`group`, `sort`,
`sort`).

### Sidebar: the round-robin vs. a (rotation, angle) sort

The `rotate` loop is an explicit round-robin, O(n) after the sort. An
equivalent one-liner tags each asteroid with how many rivals are *nearer*
on its bearing (its rotation index `k`, = position in the near→far list)
and does a single lexicographic sort:

```racket
;; untested sketch — same result as `rotate`
(define tagged
  (for*/list ([ray (in-list rays)]
              [(a k) (in-indexed (in-list ray))])
    (list k (angle (car ray)) a)))           ; (rotation angle asteroid)
(map caddr (sort tagged (λ (p q) (or (< (car p) (car q))
                                     (and (= (car p) (car q))
                                          (< (cadr p) (cadr q)))))))
```

The insight it makes explicit: **the laser fires in (rotation, then angle)
lexicographic order.** All the rotation-0 asteroids (nearest on each
bearing) die first in angle order, then all the rotation-1 asteroids, and so
on. The shipping source keeps the round-robin because it reads like the
prose ("sweep, advance, repeat") and avoids re-deriving the rotation index;
this sort is the same fact stated declaratively. Per the repo's
idiomatic-first policy, the loop ships and the sort documents.

---

## Tests (what's pinned and why)

[test/day10-test.rkt](../../test/day10-test.rkt) pins four layers (20
checks):

1. **`parse-input`** on the 5×5 map — exact coordinate list, row-major,
   confirming the `(x . y)` orientation (the easiest thing to flip).
2. **Part 1 on all five spec maps** — the 8-detector 5×5 (`3,4`) plus the
   four larger examples (`5,8`/33, `1,2`/35, `6,3`/41, `11,13`/210). The
   answer is checked as the full `(coord . count)` pair, so a wrong
   *location* with a right *count* still fails.
3. **Part 2 on the 20×20 / 210 map** — every position the spec enumerates
   (1st, 2nd, 3rd, 10th, 20th, 50th, 100th, 199th, **200th**, 201st, and
   299th-and-final), plus `(length order) = 299` to confirm every non-station
   asteroid is vaporized exactly once. The 201st and 299th specifically
   exercise the multi-rotation tail.
4. **The real answers** — `part1 = 230`, `part2 = 1205`.

`raco test test/day10-test.rkt` → 20 tests passed.

---

## Benchmarks

```
| Day | Parse (ms) | Part 1 (ms) | Part 2 (ms) | Total (ms) |
|-----|-----------|-------------|-------------|------------|
| 10  | 0.0000    | 13.8000     | 14.1400     | 27.9400    |
```

Mean over **100** iterations. What the row says:

- **Parse** builds a ~310-element coordinate list from the 23×22 grid —
  fast enough that at 100 iterations it falls *below the harness's
  millisecond timer resolution* and rounds to `0.0000`. (The cheaper-parse
  days that show a real number — 08, 09 — run at 2000 iterations, where the
  totals clear the timer's granularity. The parse here is genuinely
  sub-100 µs, not free.)
- **Part 1 (13.8 ms)** is the O(n²) visibility scan: `best` runs ~310
  `count-visible` calls, each reducing ~310 deltas and hashing them into a
  set. ~96k gcd reductions + set operations.
- **Part 2 (14.1 ms)** *redoes* that same `best` scan (it needs the station)
  and then adds the grouping, two sorts, and the round-robin — the sweep
  itself is cheap (O(n log n) dominated by the angle sort), so the part is
  essentially "Part 1's cost again, plus a little." Caching `best` across
  the two parts in a combined `solve` would roughly halve the pair, the same
  trace-once win [Day 3a](../../src/day03a.rkt) banked — filed as a sidebar,
  not shipped, per policy.

The two parts being near-equal in cost is the tell that **`best` dominates
both** — the geometry of Part 2 (sorts, sweep) is noise next to re-running
the O(n²) scan.

---

## If I were writing this in Rust

```rust
use std::collections::{HashMap, HashSet};

type P = (i64, i64);

fn parse_input(text: &str) -> Vec<P> {
    text.lines().enumerate()
        .flat_map(|(y, row)| row.char_indices()
            .filter(|(_, c)| *c == '#')
            .map(move |(x, _)| (x as i64, y as i64)))
        .collect()
}

fn direction(dx: i64, dy: i64) -> P {
    let g = num_integer::gcd(dx.abs(), dy.abs());
    (dx / g, dy / g)
}

fn count_visible(s: P, asteroids: &[P]) -> usize {
    asteroids.iter().filter(|&&a| a != s)
        .map(|&(x, y)| direction(x - s.0, y - s.1))
        .collect::<HashSet<_>>().len()
}

fn best(asteroids: &[P]) -> (P, usize) {
    asteroids.iter()
        .map(|&a| (a, count_visible(a, asteroids)))
        .max_by_key(|&(_, c)| c).unwrap()
}

fn vaporization_order(s: P, asteroids: &[P]) -> Vec<P> {
    let dist2 = |a: P| (a.0 - s.0).pow(2) + (a.1 - s.1).pow(2);
    let angle = |a: P| {
        let t = ((a.0 - s.0) as f64).atan2(-((a.1 - s.1) as f64));
        if t < 0.0 { t + std::f64::consts::TAU } else { t }
    };
    let mut groups: HashMap<P, Vec<P>> = HashMap::new();
    for &a in asteroids.iter().filter(|&&a| a != s) {
        groups.entry(direction(a.0 - s.0, a.1 - s.1)).or_default().push(a);
    }
    let mut rays: Vec<Vec<P>> = groups.into_values().collect();
    for ray in &mut rays { ray.sort_by_key(|&a| dist2(a)); }
    rays.sort_by(|a, b| angle(a[0]).partial_cmp(&angle(b[0])).unwrap());

    let mut order = Vec::new();
    let mut i = 0;
    while rays.iter().any(|r| i < r.len()) {     // pass = rotation
        for ray in &rays { if i < ray.len() { order.push(ray[i]); } }
        i += 1;
    }
    order
}
```

The correspondences worth seeing:

- **`HashSet::len()` ↔ the `for/fold` over a `set`.** Both count distinct
  directions by letting the set dedup; Rust's `.collect::<HashSet<_>>()`
  is the one-shot form of Racket's accumulating fold.
- **`max_by_key` ↔ `argmax`.** Identical "return the element, not the
  score" semantics — the trap `max` would fall into in both languages.
- **`entry(k).or_default().push(a)` ↔ `hash-update!` with `'()`.** Rust's
  entry API *is* `hash-update!`: get-or-insert-default, then mutate.
- **The round-robin by index `i`** replaces Racket's "drop all heads each
  pass" with "read column `i` of every ray each pass" — same rotation
  semantics, no list-rebuilding, because Rust indexes `Vec`s in O(1) where
  Racket walks `cons` cells. (The Racket `rotate` could do the same with
  vectors; the list version reads cleaner and n is tiny.)
- **`f64::atan2` ↔ two-arg `atan`.** Same function, same argument-swap
  trick for clockwise-from-up; `TAU` is `2π`.

The borrow checker is quiet here — everything is `Copy` `(i64, i64)` pairs
and the asteroid slice outlives every closure — so this is one of the days
where the Rust and Racket shapes line up almost statement for statement.

---

## What's next

**Day 11** brings the Intcode VM ([Day 9](day09_function_guide.md)) back as
a *painting robot*: the program drives a turtle over an infinite grid,
reading the current panel's color as input and emitting paint-and-turn
commands as output — the first time an Intcode program is wired to a
*stateful external world* that feeds back into its own input stream. The
`run/inputs` machinery and the cooperative-pause discipline from
[Day 7](day07_function_guide.md) are the tools; today's grid-of-coordinates
bookkeeping (hash keyed by `(x . y)`) is the warm-up for the robot's canvas.
See the [summary table](summary_2019.md) for the running scoreboard.
