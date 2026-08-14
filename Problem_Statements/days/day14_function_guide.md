# Day 14 — Space Stoichiometry (function guide)

> **Historical note.** This guide annotates the frozen Racket solution
> ([src/day14.rkt](../../src/day14.rkt)), written when this repo was the
> Racket leg of a language rotation. The repo is Python-only now and the
> Racket is frozen, not deleted -- see the [README](../../README.md). The
> guide is left as it was and remains accurate about the code it describes.

> A nanofactory recipe book. Every line is `3 A, 4 B => 1 AB`; exactly one
> reaction produces each chemical except `ORE`, the raw input. Part 1 asks
> the ORE cost of 1 FUEL; Part 2 asks how much FUEL a trillion ORE buys. The
> entire day hangs on one clause in the prose — **reactions cannot be
> partially run**. Strip that clause out and this is a linear-algebra
> one-liner: multiply the recipe matrix down to ORE and divide. Put it back
> and you get an *integer* problem with a rounding step that has to happen at
> exactly the right moment, and the moment is defined by a **topological
> sort**. Part 2 then falls out as a **binary search on the answer**, riding
> a monotonicity property that is worth proving rather than assuming. On the
> real input Part 1 is **628586** and Part 2 is **3209254** — and the ratio
> of those two numbers is the most interesting datum of the day: a trillion
> ORE at the *single-unit* rate would buy only 1,590,872 FUEL, so **producing
> at scale is 2.02× more efficient than producing one at a time**. All of
> that efficiency is recovered leftovers.

## The puzzle in one paragraph

Parse `N X, M Y => K Z` lines into a map from output chemical to (output
quantity, list of (quantity, input chemical)). A reaction can only be run a
whole number of times, so producing 3 units from a `=> 2 D` reaction takes
two runs and wastes one D — but leftovers persist and can be used later.
**Part 1:** minimum ORE for 1 FUEL. **Part 2:** maximum FUEL from
1,000,000,000,000 ORE. Real input: **628586** and **3209254**.

---

## Satisfactory players already know this problem

If you have played *Satisfactory* (or *Factorio*, or *Dyson Sphere Program*),
you have solved Day 14 by hand, at a whiteboard, with a calculator. The
recipe book is a production graph; the "reactions cannot be partially run"
clause is a constructor that produces in discrete batches; and the thing that
makes the puzzle interesting is exactly the thing that makes those games
interesting:

- **A naive chain overbuilds.** Ask each consumer independently "how much
  input do I need?" and round each answer up to whole batches, and you build
  four separate smelter lines each rounding up separately. That's the wrong
  answer to Part 1 — 41 ORE on the spec's first example instead of 31, and
  **929,471 instead of 628,586 on the real input: a 47.9% overbuild**.

- **Merging demand upstream is the whole optimisation.** One smelter line
  fed by the *summed* demand of all four consumers rounds up once. That is
  literally what the topological sort buys us.

- **Efficiency improves with scale, then plateaus.** In-game, a factory built
  for 1 item/min wastes a lot in partial batches; built for 1000/min the
  partials amortise away. Here is that curve on the real input:

  | FUEL built | ORE per FUEL |
  |-----------:|-------------:|
  | 1          | 628,586.00   |
  | 10         | 332,413.20   |
  | 100        | 312,990.53   |
  | 1,000      | 311,811.88   |
  | 10,000     | 311,620.33   |
  | 1,000,000  | 311,598.90   |
  | ∞ (exact ratio) | 311,598.6981 |

  It converges fast, and it converges to the *fractional* ratio — the answer
  the puzzle would have had if reactions were divisible. Part 2's answer sits
  on that plateau, which is why the naive per-unit estimate undershoots by a
  factor of ~2 and the fractional estimate overshoots by **2 units**. Both
  facts get used below.

The one place the analogy breaks: Satisfactory is a *steady-state throughput*
problem (items/minute, and you care about ratios and belt saturation). Day 14
is a *one-shot batch* problem (total units, and you care about integer
round-up waste). Same graph, different objective — and the batch version is
the one where the ceiling matters.

---

## The algorithm in Python

Day 14 is *algorithm-flavored*: the Racket mechanics are ordinary hash and
list work, and the interesting content is the two named algorithms. So the
guide leads with the algorithm stated in the most boring language available.
Full version with the spec's examples is at [python/day14.py](../../python/day14.py).

```python
def topo_order(reactions):
    """Chemicals ordered so every consumer precedes what it consumes.

    Kahn's algorithm on the DAG whose edges run output -> input.
    in-degree of X = how many distinct reactions consume X.
    """
    succs = {out: sorted({chem for _, chem in ins})
             for out, (_, ins) in reactions.items()}

    indeg = defaultdict(int)
    for out, ss in succs.items():
        indeg.setdefault(out, 0)
        for s in ss:
            indeg.setdefault(s, 0)
    for ss in succs.values():
        for s in ss:
            indeg[s] += 1

    ready = [c for c, d in indeg.items() if d == 0]
    order = []
    while ready:
        c = ready.pop()
        order.append(c)
        for s in succs.get(c, ()):
            indeg[s] -= 1
            if indeg[s] == 0:
                ready.append(s)
    return order


def ore_for(reactions, fuel):
    """ORE needed for `fuel` FUEL. One ceiling per chemical, at the right time."""
    need = defaultdict(int)
    need["FUEL"] = fuel
    for c in topo_order(reactions):
        n = need[c]
        if n <= 0 or c not in reactions:
            continue
        per, ins = reactions[c]
        runs = -(-n // per)                  # ceiling division
        for qty, chem in ins:
            need[chem] += runs * qty
    return need["ORE"]


def part2(reactions, budget=10**12):
    """Largest FUEL affordable, by bisection on a monotone predicate."""
    lo = budget // ore_for(reactions, 1)     # underestimate, provably
    hi = 2 * lo
    while ore_for(reactions, hi) <= budget:
        hi *= 2
    while hi - lo > 1:                       # invariant: lo affordable, hi not
        mid = (lo + hi) // 2
        if ore_for(reactions, mid) <= budget:
            lo = mid
        else:
            hi = mid
    return lo
```

That's the whole day. Everything below is why each of those lines is the line
it is.

---

## The key idea: *when* you round up

Take the spec's first example:

```text
10 ORE => 10 A
1 ORE  => 1 B
7 A, 1 B => 1 C
7 A, 1 C => 1 D
7 A, 1 D => 1 E
7 A, 1 E => 1 FUEL
```

`A` is consumed by four different reactions, 7 units at a time, and it is
produced 10 at a time. Total A demand for 1 FUEL is 7 + 7 + 7 + 7 = **28**.

**The wrong way — round per demand, depth-first:**

| step | demand | runs of `=> 10 A` | ORE |
|------|--------|-------------------|-----|
| FUEL needs 7 A | 7 | ⌈7/10⌉ = 1 | 10 |
| E needs 7 A    | 7 | ⌈7/10⌉ = 1 | 10 |
| D needs 7 A    | 7 | ⌈7/10⌉ = 1 | 10 |
| C needs 7 A    | 7 | ⌈7/10⌉ = 1 | 10 |
| C needs 1 B    | 1 | ⌈1/1⌉  = 1 | 1  |
|                |   | **total** | **41** |

**The right way — accumulate all demand, round once:**

| chemical | total demand | runs | ORE |
|----------|--------------|------|-----|
| A | 28 | ⌈28/10⌉ = 3 → 30 A produced, 2 wasted | 30 |
| B | 1  | 1 | 1 |
|   |    | **total** | **31** |

31 is the spec's answer. The difference is not a different formula — it is
the *same* formula applied at a different time. Four separate ⌈·⌉ calls
versus one.

So the question becomes: **when is it safe to round up chemical `c`?**
Answer: when no further demand for `c` can arrive — i.e. when every reaction
that consumes `c` has already been expanded. That is a precedence constraint
on the order in which we visit chemicals, and a precedence constraint on a
DAG has exactly one canonical name:

### Topological sort

Build a graph with an edge `X → Y` whenever the reaction producing `X`
consumes `Y`. It is a DAG (a cycle would mean a chemical is an ancestor of
itself, and the recipe book would be unproducible). A topological order of
that graph puts every chemical *after* everything that consumes it. Walk in
that order and each chemical's demand is complete when you reach it.

Concretely on the real input the order starts `FUEL, WFPNP, QKBQL, FRQH,
RNLTX, …` and ends `…, TZSDV, HTLSF, ORE`. FUEL is first because nothing
consumes it; ORE is last because everything reaches it and nothing produces
it. 64 chemicals, 63 reactions, longest FUEL→ORE chain 13 hops, at most 7
inputs to any one reaction, and only **5** chemicals are made directly from
ORE — the graph is a wide diamond, which is precisely why leftovers matter so
much (the same intermediate is reached down many paths).

**Kahn's algorithm** is the queue-based construction: initialise every node's
in-degree, start with the zero-in-degree frontier, emit a node and decrement
its successors, push any that hit zero. The alternative is a DFS post-order
reversal; Kahn's is used here because the in-degree count *is* the quantity
we care about ("how many consumers still owe me their demand"), so the
algorithm reads as the argument for its own correctness.

### The leftover pool, and why we don't need one

The other common correct solution keeps a `surplus` hash: recurse
depth-first, and before producing chemical `c` check whether leftovers from a
previous batch cover the demand. That works, and it is what most people write
first. But note what it is doing: it is *simulating* the merge that the
topological order gets for free. In the topological version there is no
surplus table at all, because by construction each chemical is produced
exactly once, in one batch, and nothing ever comes back to ask for more.

Two ways to see that the two agree:

1. The surplus version's final ORE total is a sum over chemicals of
   ⌈(total demand for c)/(per-run qty)⌉ × (inputs), and "total demand for c"
   is the same number in both. The surplus table's only job is to defer the
   round-up until all demand has landed — which the ordering does statically.
2. Empirically: [python/day14.py](../../python/day14.py) and
   [src/day14.rkt](../../src/day14.rkt) agree on all five spec examples and
   the real input, and the tests pin both.

The topological framing is preferred here because it *names* the thing, and
because it makes the cost model obvious: one linear sweep, no recursion, no
memoisation, no repeated visits.

---

## The Day 14 code, form by form

### `struct reaction` — an immutable record

```racket
(struct reaction (qty inputs) #:transparent)
```

[Day 11](day11_function_guide.md) and [Day 7](day07_function_guide.md) used
`(struct vm (…) #:mutable)` — a mutable record threaded through a stepper.
This one is plain: two fields, never modified, constructed once at parse
time.

- `(reaction 1 '((7 . "A") (1 . "B")))` constructs; `reaction-qty` and
  `reaction-inputs` access; `reaction?` is the predicate.
- `#:transparent` makes it printable and `equal?`-comparable field by field.
  Without it, structs print as `#<reaction>` and compare by identity only —
  which would make the tests useless. Rust analogue:
  `#[derive(Debug, PartialEq)]`.
- The output *chemical* is deliberately **not** a field. It is the hash key
  that points at the struct. Storing it in both places invites them to
  disagree; this is the same "make illegal states unrepresentable" instinct
  as a Rust `HashMap<String, Reaction>` where `Reaction` has no `name`.

`(struct-out reaction)` in the `provide` exports the constructor, predicate,
and all accessors in one form — the analogue of `pub struct` with `pub`
fields.

### `parse-amount` — one shape for both sides of the arrow

```racket
(define (parse-amount s)
  (match (string-split (string-trim s))
    [(list n chem) (cons (string->number n) chem)]))
```

`string-split` with no separator argument splits on runs of whitespace *and*
drops empty pieces, so `" 44 XJWVT "` and `"44 XJWVT"` both give
`'("44" "XJWVT")`. That is why no explicit trimming of the pieces is needed
after splitting on `"=>"` and `","`.

The `match` on `(list n chem)` is doing double duty as a **validator**: an
input line with three tokens where two are expected raises a match error
rather than silently taking the first two. Rust analogue: destructuring a
slice pattern `[n, chem]` — which likewise fails rather than truncating.

Every quantity in this puzzle is a positive integer on both sides of the
arrow, so one function covers both, and the `(qty . chemical)` pair is the
one shape used everywhere downstream.

### `parse-input` — `for/hash` and `match-define`

```racket
(define (parse-input s)
  (for/hash ([line (in-list (string-split (string-trim s) "\n"))]
             #:unless (string=? (string-trim line) ""))
    (match-define (list lhs rhs) (string-split line "=>"))
    (define out (parse-amount rhs))
    (values (cdr out)
            (reaction (car out) (map parse-amount (string-split lhs ","))))))
```

Three things to re-read cold:

**`for/hash`** ([Day 6](day06_function_guide.md)) builds an *immutable* hash
from a comprehension whose body returns two values via `values` — key first,
then value. Contrast the `make-hash` / `hash-set!` pairs used inside
`topo-order` and `ore-for`, which are *mutable* hashes; the distinction is
Racket's, not a naming convention, and the two families have different
operation names (`hash-set` vs `hash-set!`).

**`match-define`** destructures in a *definition* position: the pattern's
variables are bound in the enclosing scope rather than in a `match` clause
body. `(match-define (list lhs rhs) …)` is exactly Rust's
`let [lhs, rhs] = …;` with an irrefutable-or-panic pattern. It is the form to
reach for whenever you'd otherwise write a `match` with a single clause whose
body is the rest of the function.

**`#:unless`** is a `for` clause guard — skip iterations where the expression
is true. (`#:when` is its complement; [Day 10](day10_function_guide.md) used
that one.) Here it drops blank lines, including the trailing newline's empty
tail on inputs that have one.

The choice of a hash keyed by *output chemical* is licensed by one sentence
of the puzzle: "almost every chemical is produced by exactly one reaction".
That guarantee is what makes the recipe book a **function** from chemical to
recipe. Without it we would need a multimap and the problem would become a
genuine optimisation (choose *which* recipe), which is a much harder puzzle.
Worth noticing how much load-bearing structure hides in that one clause.

### `topo-order` — Kahn's algorithm

```racket
(define (topo-order reactions)
  (define succs
    (for/hash ([(out r) (in-hash reactions)])
      (values out (remove-duplicates (map cdr (reaction-inputs r))))))
  (define indeg (make-hash))
  (for ([(out ss) (in-hash succs)])
    (hash-ref! indeg out 0)
    (for ([s (in-list ss)]) (hash-ref! indeg s 0)))
  (for* ([(_out ss) (in-hash succs)] [s (in-list ss)])
    (hash-update! indeg s add1))
  (let loop ([ready (for/list ([(c d) (in-hash indeg)] #:when (zero? d)) c)]
             [order '()])
    (cond
      [(null? ready) (reverse order)]
      [else
       (define c (car ready))
       (define ready*
         (for/fold ([acc (cdr ready)]) ([s (in-list (hash-ref succs c '()))])
           (hash-update! indeg s sub1)
           (if (zero? (hash-ref indeg s)) (cons s acc) acc)))
       (loop ready* (cons c order))])))
```

**`(in-hash h)`** in a `for` clause with *two* binding names iterates
key/value pairs. (`in-hash-keys` and `in-hash-values` give one each.) Note
this is the first day to iterate a hash's entries rather than just look
things up.

**`hash-ref!`** — "read, inserting the default if absent". `(hash-ref! indeg
s 0)` returns the current in-degree or stores 0 and returns that. It is the
mutable cousin of `hash-ref` with a default, and it exists so you can
initialise a key without a `hash-has-key?` test. Rust analogue:
`*map.entry(k).or_insert(0)`.

**`hash-update!`** — "apply a function to the value at a key". `(hash-update!
indeg s add1)` is `indeg[s] += 1`; the three-argument form with a trailing
default (used in `ore-for`) handles the absent case. This is Racket's answer
to the read-modify-write dance, and it is worth internalising because the
alternative — `(hash-set! h k (f (hash-ref h k d)))` — hashes the key twice
and reads worse.

**`remove-duplicates` is correctness, not tidiness.** The in-degree counting
loop and the decrementing loop both walk `succs`. If a reaction listed the
same input chemical twice, and we counted two edges but decremented once (or
vice versa), a node would never reach zero and the sort would silently drop
chemicals off the end. Deduplicating once, at construction, makes both loops
agree by construction. The real input has no such reaction — but the property
that makes the code correct shouldn't depend on the input being nice.

**The `for/fold` inside the loop** carries the frontier as an accumulator
while performing side effects on `indeg`. Reading it: start from `(cdr ready)`
(the frontier minus the node we just emitted), and for each successor,
decrement and conditionally push. It is a fold used for its accumulator, not
for purity — the `hash-update!` in the body is deliberate mutation. That mix
is idiomatic Racket in a way it would not be in Haskell, where the same code
would need `ST` ([the 2018 repo's Day 9](../../../aoc2018_Haskell/Problem_Statements/days/day09_function_guide.md)).

**`ready` as a list-as-stack** makes this a DFS-flavoured linearisation
rather than a BFS one. Either is a valid topological order; with 64 nodes the
constant factors are irrelevant. Using `(car …)`/`(cons …)` on a list is
O(1) at the head, so it is a genuine stack.

**The order is not unique**, and that matters for the tests: any
linearisation respecting the edges is correct, and the initial frontier is
read out of a hash whose iteration order is unspecified. The test therefore
pins the *property* (every consumer precedes its inputs; FUEL first, ORE
last; no duplicates) rather than a literal list. This is a good habit to
carry forward — pinning an arbitrary-but-valid output makes a test that
breaks on an innocent refactor.

### `ceil-div` — the integer ceiling idiom

```racket
(define (ceil-div n per) (quotient (+ n per -1) per))
```

Racket has `ceiling`, but `(ceiling (/ n per))` constructs an exact rational
and then rounds it — correct, but it allocates and leaves the fixnum world.
`(quotient (+ n per -1) per)` stays in integers. Identical to Rust's
`n.div_ceil(per)` (and to the pre-`div_ceil` idiom `(n + per - 1) / per`), and
to the C one-liner everybody has written.

Guard rail for the cold reader: this identity holds for **non-negative**
`n` and **positive** `per`. Both hold here — quantities are positive by the
puzzle's construction and demands are non-negative — but the version with
negatives is a different formula, and Racket's `quotient` truncates toward
zero rather than flooring, so don't reuse this blindly.

### `ore-for` — one sweep, one ceiling per chemical

```racket
(define (ore-for reactions fuel)
  (define need (make-hash))
  (hash-set! need "FUEL" fuel)
  (for ([c (in-list (topo-order reactions))])
    (define n (hash-ref need c 0))
    (when (and (positive? n) (hash-has-key? reactions c))
      (define r (hash-ref reactions c))
      (define runs (ceil-div n (reaction-qty r)))
      (for ([in (in-list (reaction-inputs r))])
        (hash-update! need (cdr in) (λ (v) (+ v (* runs (car in)))) 0))))
  (hash-ref need "ORE" 0))
```

The whole solver, and it is nine lines. Reading the guards:

- **`(positive? n)`** skips chemicals nothing asked for. On these inputs
  every chemical is reachable from FUEL, so this is defensive; it also makes
  `(ore-for rs 0)` return 0 rather than doing 63 units of pointless work.
- **`(hash-has-key? reactions c)`** is the ORE test, stated structurally
  rather than as `(string=? c "ORE")`. ORE is the unique chemical with no
  producing reaction, so "has no recipe" *is* "is a raw material". If a
  future variant of this puzzle had two raw inputs, this code would already
  handle it; a literal `"ORE"` test would not.
- **The trailing `0` on `hash-update!`** is the default for an absent key —
  the first time anything demands a chemical, its running total starts at 0
  and then gets the increment.
- **`(hash-ref need "ORE" 0)`** with a default, because a degenerate recipe
  book that reaches no ORE at all shouldn't crash.

The subtle line is the one that *isn't there*: no surplus bookkeeping. The
`runs × qty − n` units of waste are computed implicitly (we pay for `runs`
whole runs of inputs) and then never mentioned again, because the topological
order guarantees nothing will ask for `c` a second time.

**Cost:** one `topo-order` (O(V + E)) plus one sweep (O(V + E)). With V = 64
and E ≈ 200 that is a few thousand hash operations. Measured at **0.10 ms**
per call.

### `part1` / `part2`

```racket
(define (part1 reactions) (ore-for reactions 1))

(define (part2 reactions [budget 1000000000000])
  (define (affordable? f) (<= (ore-for reactions f) budget))
  (define lo0 (quotient budget (part1 reactions)))
  (let grow ([hi (max 1 (* 2 lo0))])
    (if (affordable? hi)
        (grow (* 2 hi))
        (let bisect ([lo lo0] [hi hi])
          (if (<= (- hi lo) 1)
              lo
              (let ([mid (quotient (+ lo hi) 2)])
                (if (affordable? mid) (bisect mid hi) (bisect lo mid))))))))
```

`part2` takes the budget as an **optional argument** with a default (the
`->*` contract's second bracket, first seen on
[Day 13](day13_function_guide.md)). That is not decoration: it is what makes
the boundary tests possible — `(part2 rs1 31)` and `(part2 rs1 30)` exercise
the bracket logic at scales the trillion-ORE case never reaches.

Two named loops via `let`-with-a-name (Racket's labelled tail recursion, the
same form as [Day 12](day12_function_guide.md)'s `axis-period`): `grow`
doubles until the upper bracket is unaffordable, then `bisect` halves.
Both are properly tail-recursive, so neither grows the stack.

The correctness argument has three parts, and all three are worth spelling
out because "binary search on the answer" is a technique that goes wrong
quietly.

---

## The problem within the problem: why bisection is legal

### 1. `ore-for` is monotone non-decreasing in `fuel`

**Claim.** If `f ≤ f'` then `ore-for(f) ≤ ore-for(f')`.

**Proof.** Walk the topological order and induct. The claim is that for every
chemical `c`, `need_f[c] ≤ need_f'[c]`. Base case: `need[FUEL]` is `f` and
`f'`. Inductive step: if `need_f[c] ≤ need_f'[c]`, then
`⌈need_f[c]/q⌉ ≤ ⌈need_f'[c]/q⌉` (ceiling is non-decreasing), so every
contribution `runs × qty` pushed onto each input is non-decreasing, and each
input's total is a sum of non-decreasing terms. Since chemicals are visited
in an order where all contributions to `c` are made before `c` is read, the
induction is well-founded. ORE is a chemical, so `ore-for(f) ≤ ore-for(f')`.
∎

That is what licenses `affordable?` being a *prefix* predicate — true up to
some threshold, false thereafter — which is exactly the shape binary search
requires. Without monotonicity, bisection would find *a* boundary, not *the*
boundary.

Note that it is monotone but **not** strictly increasing: leftovers mean
`ore-for(f) = ore-for(f+1)` is possible for some f. Bisection handles that
fine (it converges on the last `f` where the predicate holds); a search that
assumed strictness would not.

### 2. `ore-for` is subadditive — so the naive rate is a *lower* bound

**Claim.** `ore-for(k·f) ≤ k · ore-for(f)`.

**Proof sketch.** Building `k·f` FUEL in one batch and building it as `k`
separate batches of `f` produce the same *demand* for every chemical. The
separate-batch version applies `⌈·⌉` once per batch per chemical; the single
batch applies it once, to the sum. And `⌈a/q⌉ + ⌈b/q⌉ ≥ ⌈(a+b)/q⌉` for all
non-negative `a, b` and positive `q`. Induct up the topological order as
before. ∎

Therefore `ore-for(⌊B/ore-for(1)⌋) ≤ ⌊B/ore-for(1)⌋ · ore-for(1) ≤ B`, so the
naive rate estimate is **affordable** — a valid `lo`. On the real input that
is 10¹² / 628586 = **1,590,872**, and the true answer 3,209,254 is **2.017×**
larger. The doubling phase then only has to run twice to find an unaffordable
`hi`.

This is the "economy of scale" from the Satisfactory section, restated as the
inequality that makes the code correct.

### 3. The off-by-one

The bisection maintains **`lo` is affordable, `hi` is not**, and terminates
when `hi − lo ≤ 1`, returning `lo`. That is the half-open-interval
formulation, and it is the one to memorise because it never needs an
`if (found) return mid` special case: `mid` is always strictly between `lo`
and `hi` when `hi − lo ≥ 2`, so the interval always shrinks and the loop
always terminates.

The invariant must hold *on entry*, which is why `lo0` is **not** floored at
1. An earlier draft had `(max 1 (quotient budget (part1 reactions)))`, and it
was wrong: with a budget smaller than the cost of a single FUEL, `lo0` would
be 1 — unaffordable — and the search would confidently report 1 FUEL you
cannot build. `(part2 rs1 30)` on the spec's first example (which needs 31)
is now a test, and it returns 0. `ore-for(0) = 0 ≤ budget` always, so 0 is
always a safe `lo`.

That bug is the archetype of how binary-search-on-the-answer fails: not in
the loop, in the *bracket*. Verify the invariant at the entry point, not just
inside the body.

---

## Possible optimization: the LP relaxation as a tight upper bound

The shipping code does 26 `ore-for` evaluations (one for `part1` inside
`part2`, one for `grow`'s overshoot, ~23 for the bisection, plus the initial).
Here is how to get it to about **three**.

Drop the ceilings entirely and run the same topological sweep over exact
rationals. That is the **linear-programming relaxation** of the integer
problem: reactions become infinitely divisible, and the answer is a single
exact ratio. On the real input:

```
exact fractional ORE per FUEL = 3324344305754201 / 10668672000
                              ≈ 311598.6981092118
```

Since removing a ceiling can only *decrease* the ORE required,
`ore_frac(f) ≤ ore_for(f)` for every f. So `ore_for(f) ≤ B` implies
`ore_frac(f) ≤ B` implies `f ≤ B / rate`. That makes

```
⌊10¹² / rate⌋ = 3,209,256
```

a rigorous **upper** bound. The true answer is **3,209,254** — an integrality
gap of **2**. On all three of the spec's large examples the gap is **0**: the
relaxation nails 82892753, 5586022, and 460664 exactly.

So a faster Part 2 is: compute the fractional bound, then walk *down* from it
one unit at a time until `ore-for` fits the budget. Untested pseudo-Racket:

```racket
;; Exact rational sweep — identical to `ore-for` with `ceil-div` deleted.
(define (ore-for/exact reactions fuel)
  (define need (make-hash))
  (hash-set! need "FUEL" fuel)
  (for ([c (in-list (topo-order reactions))])
    (define n (hash-ref need c 0))
    (when (and (positive? n) (hash-has-key? reactions c))
      (define r (hash-ref reactions c))
      (define runs (/ n (reaction-qty r)))          ; exact rational, no ⌈⌉
      (for ([in (in-list (reaction-inputs r))])
        (hash-update! need (cdr in) (λ (v) (+ v (* runs (car in)))) 0))))
  (hash-ref need "ORE" 0))

(define (part2/lp reactions [budget 1000000000000])
  (let down ([f (floor (/ budget (ore-for/exact reactions 1)))])
    (if (<= (ore-for reactions f) budget) f (down (sub1 f)))))
```

Expected cost: one exact sweep (rationals are slower per operation than
fixnums, but it is still one sweep) plus 1–3 integer sweeps. Call it **8×
faster** than the bisection, at 2.66 ms → ~0.3 ms.

Why it is a sidebar and not the shipping code: **the gap is not provably
bounded.** Nothing in the puzzle guarantees the integrality gap stays in the
single digits — a pathological recipe book with a deep chain of small-batch
reactions could push it wide, and the downward walk would degrade to a linear
scan. Bisection's ~23 steps are a *worst-case* guarantee over a bracket of
any width; the LP walk is a heuristic that happens to be excellent on these
inputs. The repo's policy ([Day 2](day02_function_guide.md)'s affine closed
form, [Day 12](day12_function_guide.md)'s half-period) is that the source
ships the honest algorithm and the guide documents the sharp one.

The hybrid — bisect on `[⌊B/ore-for(1)⌋, ⌊B/rate⌋]` instead of on
`[lo, 2·lo, 4·lo, …]` — gets the best of both: still a worst-case log bound,
but over a bracket of width 1,618,384 instead of one found by doubling, and
with no `grow` phase at all. That saves about 3 evaluations. Modest, and it
costs an exact-rational sweep, so it is roughly a wash.

### Other optimizations not taken

- **Hoist `topo-order` out of `ore-for`.** Part 2 recomputes the topological
  sort on all 26 calls. Sorting 64 nodes is genuinely cheap, but it is
  strictly redundant work — the graph doesn't change. Threading a
  precomputed order through `ore-for` would cut Part 2 by roughly the
  `topo-order` share of each call. It was left out because it complicates
  `ore-for`'s signature (or requires a mutable cache) for a constant factor,
  and the shipping code prefers the self-contained function. This is the
  cheapest real win available if the day ever needs to be faster.
- **Intern chemical names to integers** and use vectors instead of hashes.
  With 64 chemicals this would turn every hash lookup into a vector index.
  Probably a 2–4× win on Part 2, at the cost of an interning pass and losing
  the readability of `need["ORE"]`. Standard move, wrong trade at this scale.
- **Memoise `ore-for`.** Useless — the bisection never asks the same `f`
  twice.

---

## Tests (what's pinned and why)

[test/day14-test.rkt](../../test/day14-test.rkt), 105 checks.

- **Parsing**: `parse-amount` on a clean and a whitespace-padded token; the
  `10 ORE => 10 A` batch size (the source of all waste in example 1); a
  multi-input left-hand side keeping its order; and `(check-false (hash-has-key?
  rs1 "ORE"))` — pinning the *structural* fact that `ore-for`'s ORE test
  relies on.
- **`topo-order` as a property, not a value.** A helper `check-topo` asserts
  no duplicates, FUEL first, ORE last, and — the one that matters — for every
  reaction and every input, `pos[output] < pos[input]`. Run on three
  different recipe books. Pinning a literal order would break on any change
  to hash iteration and would assert something the algorithm never promised.
- **Part 1 on all five spec examples.** Example 1 is the regression test for
  the entire idea: naive per-demand rounding returns 41 there, not 31.
- **`ore-for` at 0** (returns 0, exercising the `positive?` guard) and a
  **subadditivity witness**: `ore-for(10) ≤ 10 · ore-for(1)`, plus the
  concrete numbers 290 vs 310 so a future reader sees *why* the inequality is
  strict. This is the property Part 2's lower bracket leans on, so it is
  pinned rather than merely argued in a comment.
- **Part 2 on the three large examples**, and separately a **boundary
  check**: for each, `ore-for(answer) ≤ 10¹²` and `ore-for(answer+1) > 10¹²`.
  That second half is what catches an off-by-one; pinning only the value
  would let a search that lands one short pass on a lucky bracket.
- **Small-budget cases** `(part2 rs1 31) = 1` and `(part2 rs1 30) = 0` — the
  tests that caught the `(max 1 …)` bracket bug described above.
- **The real input**: 628586 and 3209254, cross-checked against the
  independent Python implementation in [python/day14.py](../../python/day14.py).

---

## Benchmarks

```
| Day | Parse (ms) | Part 1 (ms) | Part 2 (ms) | Total (ms) |
|-----|-----------|-------------|-------------|------------|
| 14  | 0.2990    | 0.1005      | 2.6575      | 3.0570     |
```

Mean over **2000** iterations.

**Parse (0.30 ms)** is 63 lines through `string-split` three times each plus
63 struct allocations and an immutable-hash build. Comparable to
[Day 13](day13_function_guide.md)'s 2.15 ms Intcode parse only in kind — this
one is string-splitting rather than number-parsing 2640 comma-separated
integers.

**Part 1 (0.10 ms)** is one `topo-order` plus one demand sweep over 64
chemicals and ~200 edges. About 1.6 µs per chemical, essentially all hash
operations. This is the cheapest Part 1 since
[Day 8](day08_function_guide.md).

**Part 2 (2.66 ms)** is **26.4× Part 1**, and that number is the whole story:
Part 2 makes exactly 26 `ore-for` calls (1 inside `part1` for the bracket, 2
in `grow`, 23 in the bisection). The measured ratio of 26.44 against a
predicted 26 is as clean a confirmation of a cost model as this year has
produced — there is *nothing* in Part 2 but repeated Part 1s, and the count
is `log₂` of the bracket width.

Worth putting next to the alternative: a linear scan upward from the naive
estimate would need 3,209,254 − 1,590,872 = **1,618,382** evaluations at
0.10 ms each ≈ **2.7 minutes**. Bisection turns that into 2.7 milliseconds —
a 60,000× gap, and unlike [Day 12](day12_function_guide.md)'s
million-years-vs-82ms it comes from the *search strategy* rather than from a
structural insight about the problem. Both are worth having in the toolkit;
this is the cheaper one to reach for, because "the predicate is monotone" is
a much more common situation than "the state space factors".

---

## If I were writing this in Rust

```rust
use std::collections::HashMap;

#[derive(Debug)]
struct Reaction {
    qty: u64,
    inputs: Vec<(u64, String)>,
}

fn parse_input(text: &str) -> HashMap<String, Reaction> {
    text.lines()
        .filter(|l| !l.trim().is_empty())
        .map(|line| {
            let amount = |s: &str| {
                let mut it = s.split_whitespace();
                let n: u64 = it.next().unwrap().parse().unwrap();
                (n, it.next().unwrap().to_string())
            };
            let (lhs, rhs) = line.split_once("=>").unwrap();
            let (qty, out) = amount(rhs);
            (out, Reaction { qty, inputs: lhs.split(',').map(amount).collect() })
        })
        .collect()
}

/// Kahn's algorithm. Edges run output -> input, so a chemical is emitted
/// only after every reaction that consumes it has been emitted.
fn topo_order(reactions: &HashMap<String, Reaction>) -> Vec<&str> {
    let mut succs: HashMap<&str, Vec<&str>> = HashMap::new();
    let mut indeg: HashMap<&str, usize> = HashMap::new();

    for (out, r) in reactions {
        let mut ss: Vec<&str> = r.inputs.iter().map(|(_, c)| c.as_str()).collect();
        ss.sort_unstable();
        ss.dedup();                       // one edge per distinct input
        indeg.entry(out.as_str()).or_insert(0);
        for s in &ss {
            *indeg.entry(s).or_insert(0) += 1;
        }
        succs.insert(out.as_str(), ss);
    }

    let mut ready: Vec<&str> =
        indeg.iter().filter(|(_, &d)| d == 0).map(|(&c, _)| c).collect();
    let mut order = Vec::with_capacity(indeg.len());
    while let Some(c) = ready.pop() {
        order.push(c);
        for s in succs.get(c).map(|v| v.as_slice()).unwrap_or(&[]) {
            let d = indeg.get_mut(s).unwrap();
            *d -= 1;
            if *d == 0 {
                ready.push(s);
            }
        }
    }
    order
}

fn ore_for(reactions: &HashMap<String, Reaction>, order: &[&str], fuel: u64) -> u64 {
    let mut need: HashMap<&str, u64> = HashMap::new();
    need.insert("FUEL", fuel);
    for &c in order {
        let n = need.get(c).copied().unwrap_or(0);
        if n == 0 {
            continue;
        }
        let Some(r) = reactions.get(c) else { continue };   // no recipe => ORE
        let runs = n.div_ceil(r.qty);
        for (qty, chem) in &r.inputs {
            *need.entry(chem.as_str()).or_insert(0) += runs * qty;
        }
    }
    need.get("ORE").copied().unwrap_or(0)
}

fn part2(reactions: &HashMap<String, Reaction>, budget: u64) -> u64 {
    let order = topo_order(reactions);           // hoisted, unlike the Racket
    let affordable = |f| ore_for(reactions, &order, f) <= budget;

    let mut lo = budget / ore_for(reactions, &order, 1);   // provably affordable
    let mut hi = (2 * lo).max(1);
    while affordable(hi) {
        hi *= 2;
    }
    while hi - lo > 1 {                          // invariant: lo yes, hi no
        let mid = lo + (hi - lo) / 2;
        if affordable(mid) { lo = mid } else { hi = mid }
    }
    lo
}
```

The differences worth noticing on a cold reread:

- **The borrow checker forces the optimisation the Racket declined.** In
  Rust, `topo_order` returns `Vec<&str>` borrowed from the reaction map, and
  keeping that alive across the bisection is natural — so hoisting the sort
  out of `ore_for` is the *path of least resistance*, not an optimisation you
  have to think of. Racket's version recomputes it 26 times because nothing
  pushed back. Lifetimes as a performance nudge is a real and underrated
  effect.
- **`n.div_ceil(r.qty)`** is in std since 1.73, so the `(n + q - 1) / q`
  idiom is finally retired. It also panics on `q == 0` rather than silently
  misbehaving.
- **`let Some(r) = reactions.get(c) else { continue }`** — let-else, which
  reads almost exactly like the Racket `(when (hash-has-key? …) …)` but
  binds and early-exits in one form. This is the closest Rust has to Racket's
  `when`-guard-plus-`define` shape.
- **`u64` overflow is a live concern** in a way Racket's bignums make
  impossible. `ore_for` at the trillion scale multiplies `runs × qty` where
  `runs` can be ~10⁷ and `qty` ~100 — fine in u64, but the doubling in
  `while affordable(hi) { hi *= 2 }` is one careless input away from
  wrapping. In release mode that wraps silently. Racket's exact integers
  simply grow; this is the recurring tax of the Rust version across
  [Day 9](day09_function_guide.md), [Day 12](day12_function_guide.md), and
  now here.
- **`indeg` keyed by `&str`** avoids cloning the chemical names entirely.
  The Racket version shares the same immutable strings by reference too — it
  just doesn't have to say so.
- **`.max(1)` on the initial `hi`** encodes the same bracket-safety fix as
  the Racket. Worth noting it survives translation: this is a property of the
  *algorithm*, not the language.

---

## What's next

Day 14 is the year's cleanest **"round up at the right moment"** puzzle, and
both of its algorithms are load-bearing well beyond AoC: a topological sort
whenever a computation has precedence constraints (build systems, spreadsheet
recalculation, [Day 6](day06_function_guide.md)'s orbit tree in a more
general form), and binary search on the answer whenever a monotone predicate
separates feasible from infeasible (which is most resource-budget questions
you will ever be asked). Store them under those names.

**Day 15** (Oxygen System) brings Intcode back for the fourth robot
application — a repair droid exploring an unknown maze, where the VM's
block-and-resume protocol from [Day 11](day11_function_guide.md) drives a
search that has to *discover* its own graph before it can traverse it. That
makes it the year's first genuine BFS-with-unknown-frontier day, and the
first where the map is built by the same loop that walks it.

See the [summary table](summary_2019.md) for the running scoreboard.
