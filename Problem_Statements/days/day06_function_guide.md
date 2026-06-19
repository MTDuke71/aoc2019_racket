# Day 6 — Universal Orbit Map (function guide)

> The first **graph day** of 2019 — except it's not a general graph, and
> seeing why is the whole puzzle. Every object orbits *exactly one* other
> object, so the map is a **rooted tree** (root: `COM`), storable as
> nothing more than a child → parent hash. Part 1 ("count all direct and
> indirect orbits") is the **sum of every node's depth**; Part 2 ("minimum
> orbital transfers between YOU and SAN") is a **lowest common ancestor
> (LCA)** distance query. Along the way the day introduces `for/hash`
> (build a hash by iteration), `in-hash-keys`, parallel `for` clauses with
> `in-naturals` (Python's `enumerate`), and `for/first` (find-first with
> early exit).

## The puzzle in one paragraph

The input is one `A)B` fact per line, meaning "`B` is in orbit around
`A`". Except for the universal Center of Mass (`COM`), every object orbits
exactly one other object. **Part 1:** verify the map by computing its
*orbit count checksum* — the total number of direct orbits (`B` around
`A`) plus indirect orbits (if `A` orbits `B` and `B` orbits `C`, then `A`
indirectly orbits `C`, chains of any length). The 12-object worked example
checksums to `42`. **Part 2:** the map also contains `YOU` and `SAN`
(Santa). Count the minimum number of **orbital transfers** — moves from
the object you're orbiting to an adjacent one — required to get from *the
object `YOU` orbits* to *the object `SAN` orbits*. In the worked example
(`YOU` orbiting `K`, `SAN` orbiting `I`), the route `K → J → E → D → I`
takes `4` transfers.

---

## The algorithm in Python

Day 6 is *algorithm-flavored* — the lesson is recognizing the tree and
its two classic queries, not Racket syntax — so the Python companion
([python/day06.py](../../python/day06.py)) states the shape first:

```python
def parse_input(text):
    return {child: parent
            for parent, child in (line.split(")") for line in text.split())}

def ancestors(parents, obj):           # everything obj orbits, nearest first
    chain = []
    while obj in parents:
        obj = parents[obj]
        chain.append(obj)
    return chain                       # L -> [K, J, E, D, C, B, COM]

def part1(parents):                    # checksum = sum of all depths
    return sum(len(ancestors(parents, obj)) for obj in parents)

def part2(parents):                    # transfers = distance via the LCA
    you_dist = {obj: i for i, obj in enumerate(ancestors(parents, "YOU"))}
    for i, obj in enumerate(ancestors(parents, "SAN")):
        if obj in you_dist:
            return i + you_dist[obj]
```

Four short functions, one data structure. The dict maps each object to
the *one* object it orbits — that "exactly one" in the puzzle text is the
load-bearing word, because it means the map is a **tree**, not a general
graph, and no search algorithm (BFS, Dijkstra) is needed. `ancestors`
walks parent pointers to the root. Part 1 sums chain lengths. Part 2
indexes `YOU`'s chain by distance, then walks `SAN`'s chain outward; the
first object the chains share is their **lowest common ancestor**, and
the answer is the two distances added. Hold this picture — the Racket
version is the same four functions with `for/hash`, a named `let`, and
`for/first` standing in for the dict comprehension, `while`, and the
early-`return` loop.

---

## The parent-pointer tree pattern

The puzzle hands you edges ("B orbits A") and asks questions about paths
to the root. The right representation is the minimal one: a hash from
each node to its single parent. This is a **parent-pointer tree**
(occasionally "spaghetti stack") — each node knows only the way *up*, and
that's sufficient because both queries only ever travel up:

| Question | Tree formulation | In `src/day06.rkt` |
|----------|------------------|--------------------|
| how many orbits does one object have? | its **depth** (path length to root) | `(length (ancestors parents obj))` |
| total checksum (Part 1) | **sum of depths** over all nodes | `for/sum` over `in-hash-keys` |
| transfers between two orbits (Part 2) | distance via the **lowest common ancestor** | index one chain, scan the other |

Two canonical facts to bank:

- **Sum of depths.** Each node contributes one orbit per ancestor, so
  "count all direct + indirect orbits" is exactly `Σ depth(v)`. The naive
  evaluation re-walks each node's path — O(n·d) for n nodes of max depth
  d — and the memoized version (sidebar below) shares suffixes for O(n).
- **Tree distance via LCA.** In a tree there is exactly *one* simple path
  between any two nodes, and it goes up from `u` to the deepest ancestor
  `u` and `v` share — their lowest common ancestor — then down to `v`:

  ```
  d(u, v) = d(u, lca) + d(v, lca) = depth(u) + depth(v) - 2·depth(lca)
  ```

  No shortest-path *search* is needed because there is nothing to search
  — the path is forced. That's the difference between this day and a true
  graph day (Day 3 was a free-form grid; later Intcode days will need
  real BFS).

---

## The real input's shape: an anti-arborescence, mostly vine

Terminology first, then measurement. A directed tree has two
orientations, and they have different names in the literature: edges
pointing *away* from the root form an **arborescence** (out-tree); edges
pointing *toward* the root form an **anti-arborescence** (in-tree). The
parent-pointer hash stores the anti-arborescence orientation — each
entry is an edge child → parent, aimed at `COM`. That's not an
implementation accident: both of the day's queries (depth, LCA) only
ever travel *toward* the root, so the in-tree is the orientation that
makes every traversal a plain pointer-walk. Storing the out-tree
instead (parent → list of children, what you'd want for BFS from the
root) would force Part 2 into an actual search. Representation follows
query direction.

So much for the abstract shape — what does the *actual* input look
like? A few minutes with a script over `inputs/day06.txt`:

| Property | Measured |
|----------|----------|
| nodes | 896 |
| edges | 895 — exactly n − 1, the tree signature |
| roots (nodes with no parent) | 1 (`COM`) |
| nodes with two parents | 0 |
| max depth | **359** |
| leaves | 68 |
| internal nodes with 1 child | 761 |
| internal nodes with 2 children | 67 (none with three or more) |
| max width (nodes at any one depth) | 7 |
| sum of all depths | 140608 (= the Part 1 answer) |

The first four rows *verify* the tree claim — the puzzle's "exactly one"
promise, checked rather than trusted. The rest say the tree is a
**vine**: a balanced binary tree on 896 nodes would be ~10 deep, and
this one is 359 deep — 85% of the internal nodes have exactly one
child, so the map is a handful of long tendrils that fork (always
two-way) only occasionally and never get wider than 7 nodes at a depth.
Thematically that's exactly right for an orbit map: real orbital
hierarchies are chains (moon → planet → star), not bushy fans.

The shape feeds back into the analysis above in two places:

- **Part 1's O(n·d) is honest work here.** With average depth
  140608 / 895 ≈ **157**, the naive depth-sum really does ~140k
  pointer-hops — `d` is in the hundreds, nowhere near the log n of a
  balanced tree. That's the entire Part 1 benchmark line below, and
  it's why the memoized sidebar's O(n) would be a real (if
  unnecessary) ~150× hop reduction.
- **Part 2 stays trivially cheap.** `YOU` sits at depth 343, `SAN` at
  116, so the two chain walks touch a few hundred nodes total — the
  vine's depth costs Part 1 but not the single LCA query, and it's
  another reason binary lifting would be machinery without a customer.

---

## The Day 6 code, form by form

### `parse-input` — `for/hash` builds the parent map

```racket
(define (parse-input s)
  (for/hash ([line (in-list (string-split s))])
    (match (string-split line ")")
      [(list parent child) (values child parent)])))
```

**`for/hash` is new**: a `for` variant whose body must produce **two
values** — `(values key val)` — and which assembles one immutable hash
entry per iteration. It's the hash sibling of `for/sum` / `for/or` from
[Day 4](day04_function_guide.md), and the direct analogue of the Python
dict comprehension above.

Two deliberate choices:

- **The argument-free `(string-split s)`** splits on *whitespace runs*,
  so it cuts the file into lines while silently absorbing `\r\n` line
  endings and any trailing newline — three edge cases handled by leaving
  an argument out. (Days 1–3 split on `"\n"` and trimmed; whitespace
  splitting is the tidier idiom when tokens can't contain spaces.)
- **`(values child parent)` — note the flip.** The line `A)B` reads
  parent-first, but the lookup we need everywhere is "what does X
  orbit?", so the *child* is the key. The `match` against
  `(list parent child)` both destructures and asserts the two-field
  shape, the same loud-failure judgment as Day 4's range parser.
- **Rust analogue:** `text.split_whitespace().map(|l|
  l.split_once(')').unwrap()).map(|(p, c)| (c, p)).collect::<HashMap<_,_>>()`
  — `collect` into `HashMap` is Rust's `for/hash`.

### `ancestors` — walk the parent pointers to the root

```racket
(define (ancestors parents obj)
  (let loop ([obj obj] [acc '()])
    (match (hash-ref parents obj #f)
      [#f (reverse acc)]
      [parent (loop parent (cons parent acc))])))
```

`(ancestors parents "L")` is `'("K" "J" "E" "D" "C" "B" "COM")` — the
chain of everything `L` orbits, nearest first. The pieces:

- **`hash-ref` with a default.** The three-argument form returns `#f`
  instead of raising when the key is absent. `COM` is the only object
  that's never a key (it orbits nothing), so "lookup failed" *is* the
  loop's termination test — the `match` dispatches on `#f` vs. anything
  else. Same trick as [Day 3](day03_function_guide.md)'s occupancy-map
  lookups.
- **The named `let` loop** is Racket's idiomatic while-loop (seen since
  [Day 1](day01_function_guide.md)'s fuel fixed-point): tail calls to
  `loop` with updated bindings, no mutation.
- **`cons` builds backward, `reverse` flips once.** Identical bookkeeping
  to Day 4's `run-length-encode`: push-front is O(1), so accumulate
  reversed and pay one O(n) flip at the end.
- **Rust analogue:** the cleanest Rust shape is an iterator, not a loop —
  `std::iter::successors(Some(obj), |o| parents.get(*o).copied())`
  yields the chain lazily; `.skip(1)` drops `obj` itself.

### `part1` — sum of depths over `in-hash-keys`

```racket
(define (part1 parents)
  (for/sum ([obj (in-hash-keys parents)])
    (length (ancestors parents obj))))
```

Every object that orbits *anything* appears as a key (only `COM`
doesn't, and its depth is 0 anyway), so iterating the keys visits exactly
the nodes that contribute. **`in-hash-keys`** is the key-only sequence
over a hash — there are also `in-hash-values` and `in-hash` (both at
once); reaching for the narrowest one documents that the values aren't
needed here. Each object's orbit count is just the *length* of its
ancestor chain, and `for/sum` (from [Day 4](day04_function_guide.md))
adds them up.

This re-walks every node's full path — O(n·d). On this input (~900
objects) that's nothing; the O(n) memoized version is sidebar'd below
per the repo's idiomatic-first policy.

### `part2` — index one chain, scan the other

```racket
(define (part2 parents)
  (define you-dist
    (for/hash ([obj (in-list (ancestors parents "YOU"))]
               [i (in-naturals)])
      (values obj i)))
  (for/first ([obj (in-list (ancestors parents "SAN"))]
              [i (in-naturals)]
              #:when (hash-has-key? you-dist obj))
    (+ i (hash-ref you-dist obj))))
```

Two new `for`-machinery pieces, both load-bearing:

- **Parallel clauses + `in-naturals` = `enumerate`.** A `for` form with
  *two* clauses advances them **in lockstep** (it does not nest — nesting
  is `for*`, Day 3). `in-naturals` is the infinite sequence 0, 1, 2, …,
  and pairing it with a finite list stops when the list does. So
  `([obj (in-list …)] [i (in-naturals)])` is exactly Python's
  `for i, obj in enumerate(…)`. Here it tags each of `YOU`'s ancestors
  with its distance from `YOU`'s current orbit: nearest ancestor = 0
  transfers away.
- **`for/first` = find-first with early exit.** It returns the body's
  value for the *first* iteration that passes the `#:when` guard and
  stops iterating — Python's loop-with-`return`, or Rust's
  `.find_map(…)`. (It returns `#f` if nothing matches; here `COM` is a
  shared ancestor of everything, so a hit is guaranteed.)

Why the first hit is the *lowest* common ancestor: `SAN`'s chain is
scanned **nearest-first**, so the first element of it that also appears
in `YOU`'s chain is the closest meeting point — every later shared
element (`C`, `B`, `COM`…) is higher up and strictly farther. The answer
is then `d(YOU-orbit → lca) + d(SAN-orbit → lca)`, the two enumerated
distances added. On the worked example: `YOU`'s chain indexes
`K=0 J=1 E=2 D=3 …`; scanning `SAN`'s chain `I=0, D=1, …` first hits
`D` at `i = 1`, and `1 + 3 = 4`. ✓

One asymmetry worth noticing: the hash (`you-dist`) makes membership
tests O(1), so the whole part is O(depth) — build one chain's index,
scan the other. Intersecting two *lists* without the hash would be
O(d²); sorting them loses the order the "lowest" in LCA depends on.

---

## The problem within the problem: it's a lowest common ancestor query

Part 2 never says "tree", "ancestor", or "path" — it says *orbital
transfers*, and the example nudges you toward imagining a search. But
strip the costume: `YOU` and `SAN` hang off a tree, and "minimum
transfers between the objects we orbit" is the **distance between two
nodes of a tree**, which is forced — not searched — through their
**lowest common ancestor**:

```
d(u, v) = depth(u) + depth(v) - 2·depth(lca(u, v))
```

The chain-intersection trick in `part2` is the O(depth) two-pointer
answer, and it's the same algorithm you'd use on file-system paths
("deepest common directory of two files"), on Git commit graphs
(`git merge-base` is LCA generalized to DAGs), or on class hierarchies
(method resolution). Naming it buys the lookup: when a future puzzle
asks for *many* such queries on a big tree, the canonical heavy tools
are **binary lifting** (precompute 2^k-th ancestors; O(n log n) build,
O(log n) per query) and **Tarjan's offline LCA** (union-find; near-linear
for a batch). One query on a 900-node tree needs none of that — but the
name is the index into the literature when n grows.

The deeper lesson is the representational one: the puzzle hands you what
*looks* like a graph problem and the word "exactly one" quietly collapses
it to a tree, where paths are unique and BFS would be wasted machinery.
Reading the constraints **before** choosing the algorithm is the
transferable move — the 2018 repo's Day 19 ("the program *is* a sum of
divisors") made the same point from the other direction.

### Sidebar: memoized depths — Part 1 in O(n)

`part1` re-walks each node's chain, sharing nothing: `L` walks 7 steps,
its parent `K` separately walks 6, and the root-adjacent suffix
`B → COM` gets re-traversed by every node below it — O(n·d) total. But
depth satisfies a one-line recurrence,

```
depth(COM) = 0;   depth(v) = 1 + depth(parent(v))
```

so memoizing turns the sum into O(n) — classic **dynamic programming
over a tree**, with the parent pointers doing the topological ordering
for free. Untested pseudo-Racket:

```racket
(define (part1-memo parents)
  (define depths (make-hash '(("COM" . 0))))   ; mutable memo table
  (define (depth obj)
    (hash-ref! depths obj
               (lambda () (add1 (depth (hash-ref parents obj))))))
  (for/sum ([obj (in-hash-keys parents)]) (depth obj)))
```

`hash-ref!` is the memoize-in-one-call primitive: look up, and on a miss
run the thunk, **store** the result, and return it. Each object's depth
is then computed exactly once, no matter how many descendants ask. On
~900 nodes the measured win would be invisible (see Benchmarks); per the
repo's optimisation policy the shipping source keeps the transparent
re-walk and this sidebar documents the technique — it becomes real when
n hits the millions, and `hash-ref!` is worth banking for any future
memoization.

---

## Tests (what's pinned and why)

[test/day06-test.rkt](../../test/day06-test.rkt) pins four layers:

1. **Parser orientation** — `A)B` stores *B's* parent as *A* (the flip is
   the easiest thing to get backwards), one entry per line with `COM`
   absent from the keys, and CRLF tolerance.
2. **`ancestors`** — the full worked chain
   `L → (K J E D C B COM)` nearest-first, the root's empty chain, and
   `D`'s length-3 chain (the puzzle's own "D orbits 3 objects" example).
3. **Both worked examples** — the 12-object map checksums to `42`
   (Part 1), and with `K)YOU` / `I)SAN` appended the transfer count is
   `4` (Part 2, the `K → J → E → D → I` route).
4. **The real answers** — `part1 = 140608`, `part2 = 337`.

`raco test` runs the `module+ test` submodule; 11 checks, all green.

---

## Benchmarks

```
| Day | Parse (ms) | Part 1 (ms) | Part 2 (ms) | Total (ms) |
|-----|-----------|-------------|-------------|------------|
| 06  | 0.4620    | 5.7040      | 0.0380      | 6.2040     |
```

The mean is over **500** iterations. What the row says:

- **Parse** builds a ~900-entry immutable hash from ~900 line splits —
  comfortably sub-millisecond.
- **Part 1** dominates the day: ~900 ancestor walks of average depth
  ~157 (the vine shape measured above — max depth 359), each consing
  and reversing a fresh chain list. This is the O(n·d) cost made
  visible — and exactly the line the memoized sidebar would erase.
- **Part 2** walks just *two* chains and builds one small hash —
  microseconds. The asymmetry between the parts is the depth-sum vs.
  single-query asymmetry, on display in the timings.

---

## If I were writing this in Rust

```rust
use std::collections::HashMap;

fn parse_input(text: &str) -> HashMap<&str, &str> {
    text.split_whitespace()
        .map(|line| line.split_once(')').expect("A)B"))
        .map(|(parent, child)| (child, parent))
        .collect()
}

fn ancestors<'a>(parents: &'a HashMap<&str, &str>, obj: &'a str)
                 -> impl Iterator<Item = &'a str> {
    std::iter::successors(Some(obj), |o| parents.get(*o).copied()).skip(1)
}

fn part1(parents: &HashMap<&str, &str>) -> usize {
    parents.keys().map(|o| ancestors(parents, o).count()).sum()
}

fn part2(parents: &HashMap<&str, &str>) -> usize {
    let you_dist: HashMap<&str, usize> =
        ancestors(parents, "YOU").enumerate().map(|(i, o)| (o, i)).collect();
    ancestors(parents, "SAN")
        .enumerate()
        .find_map(|(i, o)| you_dist.get(o).map(|d| i + d))
        .expect("YOU and SAN share COM")
}
```

The correspondences worth seeing:

- **Zero-copy parse.** The Rust `HashMap<&str, &str>` borrows slices of
  the input string — no allocation per name, lifetimes tying the map to
  the text it came from. Racket's `string-split` allocates fresh strings
  and the hash holds them; the GC makes the ownership question vanish,
  at the cost of Rust's guarantee that it *couldn't* dangle.
- **`ancestors` as `iter::successors`.** Where the Racket named `let`
  *builds the list*, the Rust version returns a **lazy iterator** —
  `successors` is precisely "keep applying the step until it yields
  `None`", i.e. the named-let pattern reified as a value. `part1` then
  never materializes a chain at all: `.count()` consumes it as it's
  produced.
- **`for/first` + `#:when` ↔ `.find_map(…)`.** Both are find-first with
  early exit; `find_map`'s `Option`-returning closure fuses Racket's
  `#:when` test and body into one step, with `you_dist.get(o)` supplying
  the `Some`/`None`.
- **Parallel `in-naturals` ↔ `.enumerate()`.** Same lockstep pairing,
  same role — distance labels on the ancestor chains.

---

## What's next

The standalone interlude is over: **Day 7** returns to the Intcode
machine ([Day 5](day05_function_guide.md)) and runs *five copies of it
in series* — amplifiers feeding each other's output, with a permutation
search over phase settings, and (in Part 2) a **feedback loop** that
forces the VM to *pause on input* instead of running to completion.
That pause is the first real architectural pressure on the VM's shape.
The tree machinery banked today — parent maps, depth sums, LCA — returns
whenever AoC dresses a hierarchy in prose. See the
[summary table](summary_2019.md) for the running scoreboard.
