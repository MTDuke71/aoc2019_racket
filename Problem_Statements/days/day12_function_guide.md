# Day 12 — The N-Body Problem (function guide)

> Four moons, each with a 3-D position and velocity. Every time step,
> gravity nudges each velocity component by ±1 toward every other moon, then
> every position moves by its velocity. Part 1 asks for the total energy
> after 1000 steps — a straight simulation. Part 2 asks for the first time
> the *entire* state repeats, and the answer on the real input is
> **380,635,029,877,596**, so simulating until it happens is out of the
> question. The whole day turns on one structural observation: **the three
> axes never interact**. Gravity on the x components is a function of the x
> components alone, so this is not one 6-D simulation of four moons — it is
> *three independent 2-D simulations of four scalars each*, and the only
> place the axes ever meet is the energy formula. Each axis repeats within a
> few hundred thousand steps; the system repeats when all three coincide; so
> Part 2 is `lcm` of three cheap searches. Underneath that is a second
> observation worth the whole day: the puzzle's oddly specific "update *all*
> velocities first, *then* all positions" is **semi-implicit (symplectic)
> Euler** integration of a piecewise-linear potential — and its symplecticity
> is exactly why the state map is a bijection, why the orbit is a pure cycle
> with no lead-in tail, and why comparing against the *initial* state is a
> legal substitute for remembering every state you've seen.

## The puzzle in one paragraph

Parse four `<x=…, y=…, z=…>` lines into positions; all velocities start at
zero. One time step is two phases, in this order: (1) for every ordered pair
of moons and every axis, if the other moon's coordinate is greater, add 1 to
this moon's velocity on that axis; if less, subtract 1; if equal, nothing.
(2) Add each moon's (new) velocity to its own position. **Part 1:** after
1000 steps, the total energy is Σ over moons of *potential* (sum of |position
coordinates|) × *kinetic* (sum of |velocity coordinates|). **Part 2:** find
the number of steps before the full (positions, velocities) state exactly
matches one seen before. On the real input, Part 1 is **12351** and Part 2 is
**380635029877596**.

---

## The algorithm in Python

Day 12 is *algorithm-flavored* (the Racket mechanics are unremarkable; the
axis decomposition is the day), so the Python companion
([python/day12.py](../../python/day12.py)) leads. The entire simulation is
five lines:

```python
def sgn(n):
    return (n > 0) - (n < 0)

def step_axis(ps, vs):
    vs = [v + sum(sgn(q - p) for q in ps) for p, v in zip(ps, vs)]
    ps = [p + v for p, v in zip(ps, vs)]
    return ps, vs

def axis_period(ps0):
    vs0 = [0] * len(ps0)
    ps, vs, n = ps0, vs0, 0
    while True:
        ps, vs = step_axis(ps, vs)
        n += 1
        if ps == ps0 and vs == vs0:
            return n

def part2(moons):
    return lcm(*(axis_period(list(a)) for a in zip(*moons)))
```

`zip(*moons)` is the transpose that performs the decomposition: it turns
four `(x, y, z)` triples into three four-element axis lists. `part1` runs
the same `step_axis` 1000 times per axis and zips the results back before
computing energy. Note what is *absent*: no `seen` set, no cycle-detection
algorithm, no 6-D state hashing. Both omissions are justified below.

---

## The key idea: the three axes never touch

Write the gravity rule out for one moon *i*:

```
Δv_i = ( Σ_j sgn(x_j − x_i),  Σ_j sgn(y_j − y_i),  Σ_j sgn(z_j − z_i) )
```

The x component of the velocity change depends on **x coordinates only**.
The y component depends on y only. There is no cross term anywhere — not in
gravity, not in the position update (`p += v` is componentwise). So the
6-dimensional system

```
(x, y, z, vx, vy, vz) × 4 moons     — 24 integers, one coupled system
```

is really three *disjoint* systems

```
(x, vx) × 4 moons  ⊥  (y, vy) × 4 moons  ⊥  (z, vz) × 4 moons
```

that happen to be printed on the same lines of the input file. This is the
whole day. Part 1 doesn't need it (1000 steps is 1000 steps either way), but
Part 1 is written in terms of it anyway so that Part 2 gets it for free.

The canonical name for the move is **decomposition into independent
subsystems, recombined by the lcm** — the same instinct as the Chinese
Remainder Theorem, which reconstructs a value on a product space from its
behaviour on each coprime factor. Once you see that the state space *factors*,
you stop searching the product and start searching the factors. AoC 2019 Day
12 is the canonical example of the pattern; AoC 2023 Day 8 ("sync the ghosts'
cycle lengths") reuses it almost verbatim.

---

## The Day 12 code, form by form

### `parse-input` — `regexp-match*` and "just grab the integers"

```racket
(define (parse-input s)
  (for/list ([line (in-list (string-split (string-trim s) "\n"))])
    (map string->number (regexp-match* #px"-?[0-9]+" line))))
```

`<x=3, y=3, z=0>` has real structure, but none of it carries information the
positional order doesn't already give you — so don't parse the format, mine
it. **`regexp-match*`** (note the star) returns *every* match in the string
as a list of strings, where plain `regexp-match` returns only the first
match plus its capture groups. `#px` selects Perl-compatible regexp syntax
(`#rx` would be POSIX, where `\d` and friends don't work); `-?[0-9]+` is
"optional minus, then one or more digits".

| Form | What it does |
|---|---|
| `#px"…"` | a *regexp value*, compiled at read time — not a string |
| `regexp-match` | first match → `(list whole group1 …)` or `#f` |
| `regexp-match*` | all matches → `(list str str …)`, `'()` if none |
| `string-trim` | strips leading/trailing whitespace (so a trailing newline doesn't yield an empty line) |
| `string-split s "\n"` | splits on an explicit separator; the default (no separator) splits on *any* whitespace run, which would shred `y= 3` |

Rust analogue: `Regex::find_iter(line).map(|m| m.as_str().parse().unwrap())`,
or the no-dependency `line.split(|c: char| !c.is_ascii_digit() && c != '-')
.filter(|s| !s.is_empty())`. Haskell analogue from
[2018](../../../aoc2018_Haskell/Problem_Statements/days/): the same
"`readMaybe` over everything that looks like a number" trick used for the
coordinate-parsing days.

A note on Windows line endings: the input file is CRLF, and splitting on
`"\n"` leaves a trailing `\r` on each line — which `regexp-match*` simply
doesn't match, so it costs nothing. Parsing by *extraction* rather than by
*shape* is robust to exactly this class of nuisance.

### `transpose` — `(apply map list …)`, the decomposition seam

```racket
(define (transpose xss) (apply map list xss))
```

This tiny function is where the axis decomposition physically happens.
`apply` splices the list of rows into `map`'s argument positions, so

```racket
(transpose '((-1 0 2) (2 -10 -7) (4 -8 8) (3 5 -1)))
;; = (map list '(-1 0 2) '(2 -10 -7) '(4 -8 8) '(3 5 -1))
;; = '((-1 2 4 3) (0 -10 -8 5) (2 -7 8 -1))
;;      x axis       y axis       z axis
```

`map` with n lists walks all of them in lockstep and calls the function with
n arguments; with `list` as the function, each call collects one column.
That's `zip*` — Racket's variadic `map` gives you an n-ary zip for free
where Rust needs `itertools::multizip` or nested `zip`s.

It runs in **both directions**, which is why it's worth naming: applied to
the moons it splits them into axes; applied to the three axis results it
zips them back into per-moon triples. Transpose is its own inverse on
rectangular data.

> One caveat worth knowing: `(apply map list '())` errors — `map` needs at
> least one list. An empty moon list would be an empty input file, so it
> never arises here, but a general-purpose `transpose` would guard it.

### `gravity` — a sum of signs, and a self-term that vanishes

```racket
(define (gravity ps p)
  (for/sum ([q (in-list ps)]) (sgn (- q p))))
```

The puzzle says "consider every *pair*", which invites an `#:unless (eq? q
p)` guard or an index-excluding loop. It isn't needed: **`(sgn 0)` is `0`**,
so the moon's own term contributes nothing and summing over *all* moons —
including itself — gives exactly the right answer. Small thing, but it's the
difference between a loop with an index-comparison guard (and the off-by-one
bugs that come with it) and a fold over a list.

`sgn` comes from `racket/math` (re-exported by `#lang racket`, the same way
[Day 10](day10_function_guide.md) got `pi` and `sqr`). On exact integers it
returns exact `-1`, `0`, `1`. Rust spells it `i64::signum`; Haskell spells
it `signum`; C makes you write it yourself.

### `step-axis` — two return values, and phase ordering as data flow

```racket
(define (step-axis ps vs)
  (define vs* (for/list ([p (in-list ps)] [v (in-list vs)]) (+ v (gravity ps p))))
  (define ps* (for/list ([p (in-list ps)] [v (in-list vs*)]) (+ p v)))
  (values ps* vs*))
```

The puzzle is emphatic that *all* velocities update before *any* position
does. In an in-place, mutation-based implementation that's a real hazard —
you need two passes over the array and a discipline not to read a position
you've already advanced. Here it's enforced **structurally**: `vs*` is
computed from the old `ps` (which is immutable and cannot have been touched),
and `ps*` is computed from the new `vs*`. Get the ordering wrong and the code
doesn't compile-then-misbehave, it fails to name a binding.

**`values`** returns multiple results at once. It is *not* a tuple: nothing
is allocated, and the results can only be consumed by a form that expects
multiple values (`define-values`, `let-values`, a matching `for/fold`, or a
call in tail position of another multiple-value context).

| Racket | Rust | Haskell |
|---|---|---|
| `(values a b)` | `(a, b)` | `(a, b)` |
| `(define-values (x y) e)` | `let (x, y) = e;` | `let (x, y) = e` |
| `(let-values ([(x y) e]) …)` | `let (x, y) = e; …` | `case e of (x, y) -> …` |
| — no first-class value — | tuples are values | tuples are values |

That last row is the one that bites. Rust and Haskell tuples are ordinary
values you can put in a `Vec`/list, return through a `Box`, or pattern-match
anywhere. Racket's multiple values are a *calling convention*, not a data
structure: `(list (values 1 2))` is an arity error, not a one-element list.
The upside is zero allocation on the fast path; the cost is that you must
plan where they're consumed. If you need to store them, cons them yourself.

### `simulate-axis` — `for/fold` with two accumulators

```racket
(define (simulate-axis ps vs steps)
  (for/fold ([ps ps] [vs vs]) ([_ (in-range steps)])
    (step-axis ps vs)))
```

`for/fold` with two accumulator bindings expects its body to produce two
values — and `step-axis` already does, so the entire loop body is a single
call with no unpacking and no repacking. This is the payoff for choosing
`values` over a cons pair as `step-axis`'s return type: the shapes line up
and the fold body is one expression.

Cross-reference: [Day 3](day03_function_guide.md) named `for/fold` and drew
the `foldl'` correspondence; [Day 4](day04_function_guide.md) and
[Day 10](day10_function_guide.md) used the single-accumulator `#:result`
variant (reverse an accumulated list, project a set down to its count). This
is the multi-accumulator form — Haskell's `foldl'` over a tuple state,
without the tuple.

### `simulate` — `for/lists`, and both directions of `transpose`

```racket
(define (simulate moons steps)
  (define vs0 (map (λ (_) 0) moons))
  (define-values (pss vss)
    (for/lists (pss vss) ([ps (in-list (transpose moons))])
      (simulate-axis ps vs0 steps)))
  (values (transpose pss) (transpose vss)))
```

Read it as three lines of pipeline: **split** (`transpose moons` → three axis
lists), **run each independently** (`simulate-axis`), **recombine**
(`transpose` back to per-moon triples).

**`for/lists`** is `for/list`'s multiple-accumulator sibling: with two names
bound, the body must return two values per iteration, and it collects two
parallel lists. Here that's "the final positions of each axis" and "the final
velocities of each axis" — three-element lists of four-element lists, which
the two `transpose` calls turn back into four-element lists of three-element
triples.

`vs0` is `(0 0 0 0)` built via `map` over the moons rather than
`(make-list 4 0)`, so nothing hardcodes "four moons" — the code works for any
number of bodies, which is what makes the tests able to exercise a two-moon
tie case.

### `norm1` and `total-energy` — the only place the axes meet

```racket
(define (norm1 xs) (for/sum ([x (in-list xs)]) (abs x)))

(define (total-energy positions velocities)
  (for/sum ([p (in-list positions)] [v (in-list velocities)])
    (* (norm1 p) (norm1 v))))
```

The puzzle calls it "potential energy" for a position and "kinetic energy"
for a velocity, but it is the same function twice: the **ℓ¹ norm** (a.k.a.
Manhattan/taxicab norm), which [Day 3](day03_function_guide.md) already used
under its distance name. Naming it once and applying it twice is what makes
the "these are the same thing" visible.

Note the physics is nonsense — real kinetic energy is ½mv², not Σ|v| — but
that's the puzzle's definition, and the only consequence is that this is the
sole point in the program where x, y and z are combined. Everything upstream
of it is three separate universes.

### `axis-period` — comparing against the *start*

```racket
(define (axis-period ps0)
  (define vs0 (map (λ (_) 0) ps0))
  (let loop ([ps ps0] [vs vs0] [n 1])
    (define-values (ps* vs*) (step-axis ps vs))
    (if (and (equal? ps* ps0) (equal? vs* vs0))
        n
        (loop ps* vs* (add1 n)))))
```

The puzzle asks for "the first state that exactly matches *a previous*
state", which reads like an instruction to keep a `seen` set. This loop
keeps nothing — it compares each new state against the *initial* one and
counts. That is not a shortcut or a guess about the input; it's licensed by
the structure of the step map, argued next. The practical difference is
O(1) memory instead of O(period) — a `seen` set here would hold ~540,000
entries across the three axes for no benefit.

`let loop` is Racket's named let: a tail-recursive local loop, compiled to a
jump. `n` starts at 1 because it's counting the step that's about to be
taken.

### `part1` / `part2`

```racket
(define (part1 moons [steps 1000])
  (define-values (positions velocities) (simulate moons steps))
  (total-energy positions velocities))

(define (part2 moons)
  (apply lcm (map axis-period (transpose moons))))
```

`part1`'s `steps` is an **optional argument** defaulting to the puzzle's
1000, which is what lets the tests check the spec's 10-step and 100-step
tables against the same code path the real answer uses. Its contract is
`->*` (mandatory args, then optional args, then range) — the same shape
[Day 11](day11_function_guide.md)'s `paint-hull` used for `start-color`.
([Day 8](day08_function_guide.md) faced the same "the puzzle fixes a
constant the tests want to vary" situation for image width/height and made
them *required* parameters instead, which is why its bench harness has to
wrap the parts in lambdas — the optional-argument version avoids that.)

`part2` is a one-liner because all the work is in the two ideas: `transpose`
does the decomposition, `lcm` does the recombination. `lcm` is variadic and
exact in Racket, so the ~3.8×10¹⁴ answer is an ordinary fixnum-or-bignum
result with no overflow consideration at all — a real difference from the
Rust version, where `u64` is fine here but `i32` would silently wrap.

---

## The problem within the problem: the step map is a bijection

Both of Part 2's shortcuts — "compare against the start" and "lcm the
per-axis periods" — rest on the same fact, and it's worth proving rather
than assuming.

### The update rule is symplectic Euler

Fix one axis. Let `p, v ∈ ℤⁿ` and define the **potential**

```
U(p) = Σ_{i<j} |p_i − p_j|          (sum of pairwise separations)
```

Then for each i,

```
−∂U/∂p_i = −Σ_{j≠i} sgn(p_i − p_j) = Σ_{j≠i} sgn(p_j − p_i) = gravity_i(p)
```

so the puzzle's gravity is exactly `−∇U`: moons are pulled *down* the
separation potential, toward each other, with unit force regardless of
distance. (Not an inverse-square law — a constant-force law. The "N-body" in
the title is thematic.)

With `g = −∇U`, the puzzle's two-phase update is

```
v' = v + g(p)      ← kick, using the OLD positions
p' = p + v'        ← drift, using the NEW velocities
```

which is textbook **semi-implicit (symplectic) Euler**, the same integrator
family as leapfrog/Störmer–Verlet. Naming this is the transferable part —
"update velocities from old positions, then positions from new velocities"
is a scheme with a literature, not an arbitrary rule. What the phase
ordering actually buys is worked out in
[the ordering experiment](#what-if-you-updated-positions-before-velocities)
below.

### Therefore the map is invertible, and the orbit has no tail

Write the step as `S(p, v) = (p + v + g(p), v + g(p))`. Given the *output*
`(p′, v′)`, recover the input mechanically:

```
v  = v′ − g(p′ − v′)
p  = p′ − v′
```

Both steps are total and deterministic, so **S is a bijection on the whole
state space** ℤⁿ × ℤⁿ (symplectic maps are volume-preserving; over the
integers that lands as "invertible"). Now suppose the orbit
`s₀, s₁, s₂, …` first repeats with `s_a = s_b`, `a < b`. Apply `S⁻¹`
exactly `a` times to both sides:

```
s₀ = s_{b−a}
```

So the *initial* state recurs — at a time no later than the first repeat.
Hence **the first repeated state is necessarily `s₀`**, the trajectory is a
pure cycle, and there is no ρ-shaped lead-in tail. Comparing against `s₀`
alone is not an optimization that happens to work on this input; it is
equivalent to the general check.

This is the same reasoning that makes Floyd's tortoise-and-hare *unnecessary*
here, where [Day 1 (2018)](../../../aoc2018_Haskell/Problem_Statements/days/day01_function_guide.md)'s
frequency-repeat and other ρ-shaped searches genuinely need a `seen` set:
those iterate a function that is *not* injective, so the first repeat can sit
anywhere in the tail. Injectivity is exactly what buys the O(1)-memory check.
The formal name for the picture: a functional graph of an injective map on a
finite reachable set is a **disjoint union of cycles** — no trees hanging off
them.

> **What this argument does *not* prove:** that a repeat exists at all. The
> state space ℤⁿ × ℤⁿ is infinite, so termination needs boundedness. Two
> partial answers: (1) total momentum `Σv` is exactly conserved — the
> gravity terms cancel pairwise because `sgn(p_j − p_i) + sgn(p_i − p_j) =
> 0` — and it starts at 0, so the system can never drift off as a whole.
> (2) A symplectic integrator conserves a nearby "shadow" Hamiltonian to
> bounded error rather than letting energy drift secularly, which is the
> standard reason these schemes give bounded orbits where explicit Euler
> spirals outward. For a piecewise-linear potential that's a heuristic
> rather than a theorem, but the puzzle guarantees a repeat exists and every
> real input has one. Boundedness makes it *terminate*; bijectivity makes
> the *search cheap*.

### Why `lcm` is the right recombination

The full state is the triple `(sˣ_t, sʸ_t, sᶻ_t)` and each component evolves
independently, so the full state returns to its start at time `t` **iff every
axis does**:

```
s_t = s₀  ⟺  T_x | t  and  T_y | t  and  T_z | t
```

(each direction uses the per-axis version of the bijection argument: an axis
is back at its start exactly at multiples of its own period). The set of
common multiples of three integers is the set of multiples of their least
common multiple, so the smallest such `t` is `lcm(T_x, T_y, T_z)`. ∎

#### Worked numbers

Example 1 decomposes into x = `(-1 2 4 3)`, y = `(0 -10 -8 5)`, z =
`(2 -7 8 -1)` with periods **18, 28, 44**:

```
lcm(18, 28)      = 252
lcm(252, 44)     = 252·44 / gcd(252,44) = 11088 / 4 = 2772   ✓ the spec's answer
```

The real input:

| Axis | Start | Period | Factorization |
|---|---|---:|---|
| x | `(3 4 -10 -3)` | 22958 | 2 · 13 · 883 |
| y | `(3 -16 -6 0)` | 286332 | 2² · 3 · 107 · 223 |
| z | `(0 2 5 -13)` | 231614 | 2 · 115807 |

Every pairwise gcd is exactly 2, so the lcm is the product divided by 4:
`1,522,540,119,510,384 / 4 = 380,635,029,877,596`. Two things fall out of
that table. First, **the periods are near-coprime**, which is why the answer
is astronomically larger than any individual search — the decomposition buys
a factor of ~700 million here, not a constant factor. Second, **every period
is even**, which is not a coincidence — see the sidebar below.

### What if you updated positions before velocities?

The puzzle is loud about the phase ordering, which invites the question:
what actually breaks if you swap it? There are **two different swaps**, and
they fail in completely different ways.

**Swap 1 — drift then kick** (the natural in-place reading: advance
positions, then compute gravity from where the moons *now* are):

```
p' = p + v          ← drift first
v' = v + g(p')      ← kick from the NEW positions
```

This is still a composition of the same two shear maps, just in the other
order — `S′ = A∘B` where the puzzle's is `S = B∘A`. So it is **still
symplectic, still a bijection, still tail-free**. And the two are conjugate:
`S′ = A ∘ S ∘ A⁻¹`. Conjugate maps have identical cycle structure, and here
`A⁻¹s₀` happens to be `S⁻¹s₀` — the *same orbit* — so the periods come out
bit-for-bit identical:

| | ex1 x/y/z | real x/y/z |
|---|---|---|
| kick → drift (puzzle) | 18 / 28 / 44 | 22958 / 286332 / 231614 |
| drift → kick (swapped) | 18 / 28 / 44 | 22958 / 286332 / 231614 |

So **Part 2 is completely insensitive to this swap** — same answer, provably,
on any input. **Part 1 is not**: the states at any finite time are shifted by
one half-step, so example 1's energy after 10 steps comes out **259** instead
of 179. A tidy trap: the swap breaks the easy part and leaves the hard part
untouched.

**Swap 2 — explicit (forward) Euler** (the "simultaneous update" reading,
where *both* lines read the old state):

```
p' = p + v          ← both from the OLD state
v' = v + g(p)
```

This is a genuinely different beast. Its Jacobian determinant isn't 1, so it
is **not symplectic and not volume-preserving**, and the classic consequence
follows immediately — energy drifts secularly and the system flies apart:

| Step | max &#124;p&#124; | max &#124;v&#124; | Σv |
|---:|---:|---:|---:|
| 10 | 23 | 9 | 0 |
| 100 | 231 | 30 | 0 |
| 1 000 | 2 334 | 80 | 0 |
| 10 000 | 24 523 | 241 | 0 |
| 40 000 | 84 024 | 480 | 0 |

(example 1's x axis; the puzzle's own integrator never leaves `max |p| = 5`
on the same axis, forever.)

Note that **momentum is still exactly conserved** — `Σv = 0` in every row,
because `Σg = 0` is an antisymmetry fact about gravity that no integrator
can break. The moons separate *symmetrically* and sail off in opposite
directions. Conservation of momentum is not enough to keep a system bounded;
that's what the symplectic structure was doing.

So under swap 2, **Part 1 returns garbage (2228 instead of 179) and Part 2
never terminates** — there is no cycle to find, because the orbit is
unbounded. This is the concrete answer to "why does the puzzle care so much
about the ordering": one swap is harmless-then-subtly-wrong, the other
destroys the existence of the answer.

### The general cycle-detection landscape

Day 12 makes `lcm` look like *the* answer to "find the cycle length". It
isn't — `lcm` is not a cycle-detection algorithm at all. It is a
**recombination** step that runs after cycles have been found by other
means, and it is only licensed when the state space **factors**. Three
separate questions hide inside any repeat-finding puzzle:

| Question | Tool |
|---|---|
| Does this iteration cycle, and how long is the loop (λ)? | Floyd / Brent / a `seen` hash |
| Does the loop start at t = 0, or after a tail of length μ? | an injectivity argument, or μ from the above |
| N independent components each cycle — when do they align? | `lcm`, or CRT if the components have offsets |

Day 12 gets to skip straight to the third row only because it clears the
first two: the axes are genuinely independent, and the bijection proof above
gives μ = 0 on every one of them.

**Finding a single cycle.** The general orbit shape of an iterated function
is a **ρ**: a tail of length μ running into a loop of length λ.

- **A `seen` hash set** — O(λ + μ) memory, yields both μ and λ, trivial to
  write. This is the correct default, and it's what
  [Day 1 (2018)](../../../aoc2018_Haskell/Problem_Statements/days/day01_function_guide.md)
  (first repeated running frequency) and AoC 2017 Day 6 (memory
  reallocation) both need.
- **Floyd's tortoise and hare** — O(1) memory, two pointers at 1× and 2×
  speed. The canonical name; worth knowing even when a hash set is simpler.
- **Brent's algorithm** — the same guarantees with ~25% fewer function
  evaluations, and it recovers λ before μ.
- **Structure-specific** methods when the map is more than a black box: the
  multiplicative order of a matrix for a linear map, baby-step giant-step or
  Pollard's rho for a discrete-log-flavored one.

The μ = 0 property — the licence to compare against the start rather than
hash every state — comes from **injectivity**, exactly the argument made
above. A map that forgets information *always* risks a tail: AoC 2018 Day 1
accumulates a running sum, which is not injective on its state, so a `seen`
set there is mandatory rather than lazy.

**When `lcm` is the wrong recombination.** `lcm` answers "when are all
components simultaneously back at **offset 0**". If component *i* is instead
in the wanted state at times ≡ rᵢ (mod Tᵢ) with rᵢ ≠ 0, the question is a
system of simultaneous congruences and the tool is the **Chinese Remainder
Theorem** — with a solution only when the residues are pairwise consistent
modulo the gcds. AoC 2020 Day 13 (bus departure offsets) is the canonical
CRT puzzle, and `lcm` alone cannot touch it.

The cautionary example is **AoC 2023 Day 8**, which the whole world solves
with `lcm` and where the puzzle text does *not* justify it: nothing in the
statement guarantees the ghost cycles have zero tail or that the exit node
sits at offset 0 within each cycle. It works because the inputs were
constructed that way. A generally correct solution is CRT over (μ, λ, offset)
triples. Worth filing away as the contrast: on AoC 2023 Day 8 you get away
with it; here you don't have to, because the bijection makes it a theorem.

The transferable instinct, in one line: **ask whether the state space
factors.** If it does, search the factors and recombine (`lcm`, or CRT with
offsets). If it doesn't, you are back to Floyd, Brent, or a `seen` set on the
full state.

---

## Possible optimization: the half-period, by time reversal

*(Sidebar, per this repo's optimisation policy: the shipping
[src/day12.rkt](../../src/day12.rkt) keeps the straightforward full-period
search; this is the technique, documented but not shipped.)*

Every one of the six axis periods measured for this write-up — the three
real ones and example 1's 18/28/44 — is exactly **twice** the first time at
which all velocities on that axis return to zero:

| Axis | First `v = 0` | Period |
|---|---:|---:|
| example 1, x | 9 | 18 |
| example 1, y | 14 | 28 |
| example 1, z | 22 | 44 |
| real, x | 11479 | 22958 |
| real, y | 143166 | 286332 |
| real, z | 115807 | 231614 |

That's not luck. The system is **time-reversible**: define

```
J(p, v) = (p − v, −v)          (undo the drift, then flip the velocity)
```

`J` is an involution (`J(J(p,v)) = (p − v + v, v) = (p, v)`), and it
conjugates the step map to its own inverse:

```
J ∘ S ∘ J = S⁻¹
```

(Write `S = B ∘ A` with kick `A(p,v) = (p, v+g(p))` and drift
`B(p,v) = (p+v, v)`; then `J = R ∘ B⁻¹` with `R(p,v) = (p,−v)`, and both
`R A R = A⁻¹` and `R B R = B⁻¹` hold because `g` is odd under position
differences and drift is linear in `v`. Composing gives
`J S J = R B⁻¹ B A R B⁻¹ = R A R B⁻¹ = A⁻¹B⁻¹ = (BA)⁻¹ = S⁻¹`.)

From `J S J = S⁻¹` and `J s₀ = s₀` (true because `v₀ = 0` and
`p₀ − 0 = p₀`), induction gives

```
J s_t = s_{−t}
```

so the orbit is a **palindrome about t = 0**. If `v_m = 0` for some m > 0
then `s_m` is also J-fixed, so `s_m = s_{−m}`, hence `S^{2m} s₀ = s₀` and
**T divides 2m**. With m the first such time, T is m or 2m — and 2m in every
case measured.

Two consequences, one practical and one for reading the puzzle text:

- **The search can stop at the first all-zero-velocity state and double**,
  halving Part 2's work (~90 ms → ~45 ms), and it can test only the
  velocities, which is a cheaper comparison than positions-and-velocities:

  ```racket
  ;; untested sketch — the technique, not the shipping code
  (define (axis-half-period ps0)
    (define zeros (map (λ (_) 0) ps0))
    (let loop ([ps ps0] [vs zeros] [n 1])
      (define-values (ps* vs*) (step-axis ps vs))
      (if (equal? vs* zeros) n (loop ps* vs* (add1 n)))))
  ;; period = (* 2 (axis-half-period ps0))   [assuming T = 2m, verified above]
  ```

  It's a sidebar rather than the shipping code precisely because that last
  bracket is an *assumption* about the input class, not a theorem: `T | 2m`
  is proved, `T = 2m` is observed. The shipping version answers the question
  the puzzle actually asked.

- **It explains the spec's own printout.** The Part Two example shows that
  after 2771 steps (one before the period) example 1 is back at its starting
  *positions* with nonzero velocities. That's `s_{T−1} = s_{−1} = J s₁`
  exactly: `s₁` is `pos=(2,3,1,2)`/`vel=(3,1,−3,−1)` on the x axis, and
  `J s₁ = (p₁ − v₁, −v₁) = ((−1,2,4,3), (−3,−1,3,1))` — which is precisely
  the row the puzzle prints.

### Other optimizations not taken

- **Mutable fixnum vectors instead of fresh lists.** `step-axis` allocates
  two four-element lists per step, ~1.1 M allocations for Part 2. Two
  `(vector 4)` buffers updated in place would remove essentially all of it
  and is probably a 3–5× win. It costs the structural guarantee that the two
  phases can't interleave, which is exactly the property the idiomatic
  version is buying — a fair trade to document and decline.
- **Rank-based gravity.** `gravity` is O(n²) per step. Sorted positions turn
  it into "(number of moons strictly below) − (number strictly above)", an
  O(n log n) per step computation. At n = 4 this is strictly worse; it is
  the right answer at n = 1000, and it's the reason to know the trick exists.

---

## Tests (what's pinned and why)

[test/day12-test.rkt](../../test/day12-test.rkt), 16 checks:

1. **`parse-input`** on example 1 — that the three integers come out of each
   `<x=…>` line in order.
2. **`step-axis` in isolation**, one step of example 1's x axis against the
   prose's own "After 1 step" table: velocities `(3 1 -3 -1)`, positions
   `(2 3 1 2)`. Testing one axis directly is the point — it's the level at
   which the decomposition claim is checkable.
3. **The tie case**, `step-axis '(1 1) '(0 0)` → unchanged. Equal coordinates
   exert no pull, which the `sgn`-sum formulation gets right silently and a
   hand-rolled `if (> q p) … else …` comparison chain typically gets wrong by
   assigning ties to one branch. Two moons rather than four, which also
   proves nothing in the code hardcodes a moon count.
4. **`simulate` after 10 steps** on example 1 — the exact positions *and*
   velocities, not just the energy. Energy is a lossy digest (a product of
   two sums of absolute values); many wrong states share a total. The prose
   prints the full state table, so pin the full state table.
5. **Part 1 on both spec examples**: 179 after 10 steps, 1940 after 100.
6. **`axis-period` per axis on example 1** (18 / 28 / 44) **and** their lcm
   (2772), pinned separately. If the decomposition and the recombination are
   only tested jointly, a transposition bug and an lcm bug can cancel; pinned
   apart, they can't.
7. **Part 2 on example 2**, 4686774924 — the case that makes the
   decomposition *necessary* rather than merely tidy. A simulate-and-hash
   search over the 6-D state would need 4.7 billion steps and hundreds of
   gigabytes; the per-axis search finishes in microseconds.
8. **The real input**: `part1 = 12351`, `part2 = 380635029877596`.

Both answers are independently cross-checked against
[python/day12.py](../../python/day12.py), which is a separate implementation
in a language with different integer semantics (arbitrary-precision by
default, so the bignum path is exercised the same way).

`raco test test/day12-test.rkt` → **16 tests passed** in ~1.3 s.

---

## Benchmarks

```
| Day | Parse (ms) | Part 1 (ms) | Part 2 (ms) | Total (ms) |
|-----|-----------|-------------|-------------|------------|
| 12  | 0.0000    | 0.4000      | 81.7200     | 81.9600    |
```

Mean over **50** iterations.

**Parse** reads as `0.0000` because it's below the harness's resolution at 50
iterations — a four-line regexp scan. Measured separately over 20,000
iterations it's **0.00915 ms**, i.e. ~9 µs, the same "invisible" band as
[Day 10](day10_function_guide.md)'s asteroid parse.

**Part 1 (0.4 ms)** is 3 axes × 1000 steps = 3000 calls to `step-axis`, each
doing 16 `sgn` evaluations and allocating two four-element lists. About 130 ns
per step — which is the honest cost of the idiomatic representation, and
almost entirely allocation.

**Part 2 (82 ms)** is the same kernel run 22958 + 286332 + 231614 = **540,904**
times, plus one `equal?` pair per step. 82 ms / 540,904 ≈ **152 ns per step**,
so Part 2 is Part 1's cost model almost exactly, scaled by 180× more steps —
the extra ~20 ns is the two `equal?` list comparisons. The clean linearity is
the useful calibration datum here: nothing in Part 2 is algorithmically
different from Part 1, it just runs longer.

The number worth internalizing is the one that *isn't* in the table: the
naïve Part 2 — simulate the 6-D system, hash each state, stop on a repeat —
would need 3.8 × 10¹⁴ steps. At 152 ns/step that's **1.8 million years**,
and it would exhaust memory in the first minute. This is the largest
algorithmic gap of the year so far; [Day 2](day02_function_guide.md)'s
brute-force grid and [Day 4](day04_function_guide.md)'s range scan were
merely slow, not impossible.

---

## If I were writing this in Rust

```rust
fn parse_input(text: &str) -> Vec<[i64; 3]> {
    text.lines()
        .map(|line| {
            let mut it = line
                .split(|c: char| !c.is_ascii_digit() && c != '-')
                .filter(|s| !s.is_empty())
                .map(|s| s.parse::<i64>().unwrap());
            [it.next().unwrap(), it.next().unwrap(), it.next().unwrap()]
        })
        .collect()
}

/// One time step of ONE axis, in place. Kick from the old positions,
/// then drift with the new velocities.
fn step_axis(ps: &mut [i64; 4], vs: &mut [i64; 4]) {
    for i in 0..4 {
        let pi = ps[i];                       // copy out: ps is borrowed below
        vs[i] += ps.iter().map(|&q| (q - pi).signum()).sum::<i64>();
    }
    for i in 0..4 {
        ps[i] += vs[i];
    }
}

fn axis_period(ps0: [i64; 4]) -> u64 {
    let (mut ps, mut vs) = (ps0, [0i64; 4]);
    for n in 1.. {
        step_axis(&mut ps, &mut vs);
        if ps == ps0 && vs == [0; 4] {
            return n;
        }
    }
    unreachable!()
}

fn gcd(a: u64, b: u64) -> u64 { if b == 0 { a } else { gcd(b, a % b) } }
fn lcm(a: u64, b: u64) -> u64 { a / gcd(a, b) * b }

fn part2(moons: &[[i64; 3]]) -> u64 {
    (0..3)
        .map(|k| axis_period(std::array::from_fn(|i| moons[i][k])))
        .fold(1, lcm)
}

fn part1(moons: &[[i64; 3]], steps: usize) -> i64 {
    let mut axes: [([i64; 4], [i64; 4]); 3] =
        std::array::from_fn(|k| (std::array::from_fn(|i| moons[i][k]), [0; 4]));
    for (ps, vs) in axes.iter_mut() {
        for _ in 0..steps {
            step_axis(ps, vs);
        }
    }
    (0..4)
        .map(|i| {
            let pot: i64 = (0..3).map(|k| axes[k].0[i].abs()).sum();
            let kin: i64 = (0..3).map(|k| axes[k].1[i].abs()).sum();
            pot * kin
        })
        .sum()
}
```

The correspondences worth seeing:

- **`[i64; 4]` ↔ the four-element list — and this is the day Rust wins on
  performance.** A fixed-size array is `Copy`, lives on the stack, compares
  with `==` field-by-field, and `step_axis` mutates it with zero allocation.
  Racket's version conses two fresh four-element lists 540,904 times.
  Expect the Rust Part 2 in the **5–15 ms** range against Racket's 82 ms,
  and the gap is essentially all allocator and GC. Note what the array
  representation *loses*: `&mut` in-place update is exactly what makes the
  "all velocities before any position" ordering a discipline again rather
  than a data-flow fact — hence the two separate `for i in 0..4` loops, which
  a reviewer must check are in the right order. The Racket version can't get
  that wrong.
- **`std::array::from_fn` ↔ `transpose`.** Rust has no `zip*` for a runtime
  number of iterators, so the transpose becomes explicit indexing
  `moons[i][k]`. Racket's variadic `map` gives an n-ary zip for free; Rust
  gives compile-time-checked lengths for free. Different currencies.
- **`i64::signum` ↔ `sgn`, and the borrow that isn't obvious.**
  `vs[i] += ps.iter()…` needs `ps` immutably borrowed while `vs` is mutably
  borrowed — fine, they're separate bindings — but `ps[i]` *inside* the
  closure would alias `ps.iter()`, so the `let pi = ps[i];` copy is
  mandatory. This is the third day running
  ([Day 11](day11_function_guide.md)'s VM closures, [Day 9](day09_function_guide.md)'s
  memory) where the borrow checker charges rent that a single-threaded
  Racket program never pays.
- **No `lcm` in std.** Rust's standard library has neither `gcd` nor `lcm`
  (they live in the `num-integer` crate); Racket has both as variadic
  builtins. Note `a / gcd(a,b) * b` rather than `a * b / gcd(a,b)`: the
  divide-first ordering avoids overflowing `u64` on the intermediate
  product, which is a real hazard here — `22958 * 286332 * 231614` is
  1.5 × 10¹⁵, still inside `u64` but only by four orders of magnitude, and
  a `u32` version would wrap silently. Racket's exact integers make the
  question disappear.
- **`for n in 1..` ↔ `let loop`.** Rust's unbounded range with an early
  `return` is the closest thing to a named let; the `unreachable!()` is dead
  code the compiler can't prove dead, which is the price of expressing "loop
  forever until a condition" as an iterator.

---

## What's next

Day 12 is the year's cleanest **decompose-and-recombine** puzzle, and worth
remembering under that name — the moment a state space factors into
independent components with small periods, `lcm` turns an impossible search
into three easy ones. **Day 13** (Care Package) brings Intcode back for the
third robot-style application: the VM as a *video game*, emitting
`(x, y, tile)` triples to draw a Breakout screen, with Part 2 turning the
program into an interactive session that has to be played to completion —
the same block-and-resume `vm-step!` protocol
[Day 11](day11_function_guide.md) built, now with the caller acting as a
joystick rather than a hull. See the [summary table](summary_2019.md) for
the running scoreboard.
