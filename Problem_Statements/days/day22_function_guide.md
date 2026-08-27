# Day 22 — Slam Shuffle (function guide)

> Code: [python/day22.py](../../python/day22.py). Tests:
> [python/tests/test_day22.py](../../python/tests/test_day22.py) (15 test
> functions, 332 parametrized cases). Statement: [day22.md](day22.md).
>
> **Answers: Part 1 = 6850, Part 2 = 13224103523662** (both verified on
> adventofcode.com; `LOCKED = (6850, 13224103523662)`).

## The puzzle in one paragraph

No Intcode. The input is a hundred lines of card-shuffling "techniques" —
`deal into new stack`, `cut N`, `deal with increment N` — applied in order to
a factory-order deck. Part 1 shuffles 10,007 cards once and asks where card
2019 ends up. Part 2 shuffles **119,315,717,514,047** cards
**101,741,582,076,661** times and asks which card ends up at position 2020.
The deck sizes are the message: one big deck alone is a petabyte
(8 × 119 T ≈ **1 PiB** at 8 bytes/card), so nothing that touches cards can
survive contact with part 2. The day is a disguised algebra exam, and the
exam has one question: *what is a shuffle, really?*

## The shape of the day: every technique is an affine map

Track a single card's **position** x in a deck of m cards. Each technique
moves it by a rule that is linear-plus-constant:

| technique | where position x goes | (a, b) |
|---|---|---|
| `deal into new stack` | m − 1 − x  ≡  −x − 1 | (−1, −1) |
| `cut n` | x − n (mod m) | (1, −n) |
| `deal with increment n` | n·x (mod m) | (n, 0) |

The first reverses the deck (top card to the bottom), the second is a
rotation (Python's `%` handles the statement's negative cuts with no special
case — pinned by the `cut -4` walkthrough), and the third lays card number
x down at table position n·x mod m, which is the definition read literally.

Affine maps **compose into affine maps**: doing (a, b) then (c, d) gives
x → c·(a·x + b) + d = (ca)·x + (cb + d). So the hundred-line input collapses
to a *single* pair — `parse_input` does that fold and nothing downstream
ever looks at a technique again. Two design points in the fold:

* **No modulus at parse time.** The input file never states a deck size, so
  `parse_input` composes over exact integers and stays deck-size-agnostic:
  one parse serves the 10-card examples, the 10,007 deck and the
  119-trillion deck (`test_parse_is_deck_size_agnostic` runs one parse
  against two different moduli). Python's transparent big integers make
  this free — the real input's exact coefficients are only 217 and 225 bits
  (a is a signed product of 44 increments; see
  [the census below](#the-real-input-measured)).
* **Composition order is application order.** `Affine.then(other)` is "self
  first, then other", so the parse is a left fold with `then` and the code
  never writes the reversed ∘ notation.

This is [Day 16](day16_function_guide.md)'s lesson wearing a new costume:
*compose the operator, not the applications*. There the operator was an
upper-triangular matrix and 100 applications collapsed into binomial
coefficients; here it is a 1-D affine map and 10¹⁴ applications will
collapse into one exponentiation.

## Part 1: apply the map forward

`position(shuffle, 10007, 2019)` = a·2019 + b mod 10007. That is the whole
part — one multiply-add, measured below the benchmark harness's display
resolution. The literal simulation (an actual 10,007-card list pushed
through all 100 techniques) takes **42.0 ms** and agrees; it exists only in
the guide's scratch measurements, not in the shipping code.

## Part 2: reverse the question, then exponentiate

Two independent escalations, and a trap between them.

**The trap: part 2 inverts the question.** Part 1 asks where card 2019
*goes* (forward map). Part 2 asks which card *lands on* position 2020 —
that is the **inverse** map. Applying the forward power to 2020 produces
115664723149851, a plausible-looking wrong answer; the right one is the x
solving A·x + B ≡ 2020. Inverting an affine map mod a prime is Fermat's
little theorem: x = (2020 − B) · A⁻¹, with A⁻¹ = `pow(A, -1, m)` (Python
≥ 3.8 accepts negative exponents and runs extended Euclid underneath). The
inverse exists because m is prime and A ≢ 0 — both pinned
(`test_part2_constants_are_prime`, `test_real_shuffle_shape`).

**The exponentiation: LCG jump-ahead.** One application of the shuffle is
x → a·x + b mod m — which is *exactly one step of a linear congruential
generator*. "Advance an LCG by k steps in O(log k)" is a classic trick
(it is how PCG and friends implement `jump`), and it is nothing more than
**square-and-multiply over affine composition**: `repeat` keeps a running
result and a running square, multiplying the result in on each set bit of
k. 101,741,582,076,661 is a 47-bit exponent, so the whole tower is ~94
compositions of three multiplications each — **39 µs** measured, against
0.8 *years* extrapolated for iterating the composed map once per shuffle
(254 ns/application, measured over 10⁵). Equivalently: the affine map is
the 2×2 matrix [[a, b], [0, 1]] acting on (x, 1), and `repeat` is matrix
exponentiation with the bottom row optimized away.

The one non-optional detail: reduce mod m at *every* composition step —
after the first few squarings the exact integers would double in size each
round. This is the only place a modulus enters before the final answer.

## The problem within the problem: the affine group mod p

Because both deck sizes are prime and every `deal with increment` argument
is nonzero mod them, every shuffle lives in the **affine group**
Aff(ℤ/mℤ) = { x → a·x + b : a ≠ 0 } — a group of order m·(m−1) under
composition. That one sentence *is* the puzzle: group elements compose
(`parse_input`), invert (`card_at`), and exponentiate (`repeat`), and all
three of the day's operations are the group operations. Three consequences,
each pinned as a test:

* **Lagrange's theorem** says every shuffle's order divides m·(m−1).
  `test_shuffle_order_divides_the_affine_group_order` runs the real shuffle
  10007 × 10006 ≈ 10⁸ times — in 54 doublings — and gets the identity back;
  the 10-card examples do the same at group order 10·φ(10) = 40.
* **The element order is exactly ord(a)**, the multiplicative order of a
  mod m: at k = ord(a) the geometric b-term b·(aᵏ−1)/(a−1) vanishes with
  aᵏ − 1. For this input mod 10,007 that order is **5003 = (m−1)/2**:
  five thousand and three shuffles restore factory order. Mod the big deck
  the order is **m − 1, the theoretical maximum — a is a primitive root**.
  Both m−1 factor as 2·q with q prime (10006 = 2 × 5003;
  119315717514046 = 2 × 59657858757023), which is what lets
  `test_real_shuffle_order` pin the orders *exactly* rather than as
  divisors: the only candidate divisors are 1, 2, q, 2q, and
  a^((m−1)/2) ≠ 1 plus a ≠ ±1 eliminates everything short of the top.
* **The geometric-series closed form.** Summing the b-contributions of k
  compositions: (a, b)ᵏ = (aᵏ, b·(aᵏ−1)·(a−1)⁻¹), one `pow` and two
  inversions instead of a composition ladder.
  `test_closed_form_agrees_with_repeat` holds it against `repeat` on both
  real moduli at part 2's real exponent (and `test_closed_form_a_equals_1_branch`
  exercises the a = 1 degenerate case with a cut-only shuffle, where the
  sum collapses to k·b). The shipping code stays on `repeat` — the closed
  form saves nothing measurable at 39 µs and costs a branch.

Since part 2's exponent (47 bits) is *smaller* than the shuffle's order
mod the big deck (m − 1, also 47 bits but larger), no order-reduction
shortcut applies — the ladder is the honest route.

## The Day 22 code, form by form

### `Affine` / `IDENTITY`

A frozen dataclass holding exact integer coefficients; `then(other, m=None)`
is composition in application order, reducing mod m only when a modulus is
supplied. Frozen because a shuffle is a *value* — every operation returns a
new map, and the parsed shuffle is safely shareable between parts (the
Intcode days' parse-mutation hazard does not exist here).

### `parse_input(text) -> Affine`

Strips each line (the CRLF guard), matches the technique by name — the
name is the line with trailing `-0123456789 ` stripped, so the argument
parse falls out of the same split — and left-folds the three primitive maps
with `then`. Unknown techniques raise. Returns the one composed map; no
other function reads the input.

### `position(shuffle, m, card)` / `card_at(shuffle, m, pos)`

The forward map and its Fermat inverse — part 1 and part 2's final step
respectively, and `test_card_at_inverts_position_everywhere` round-trips
them at every position of every example deck.

### `repeat(shuffle, times, m)`

Square-and-multiply over `then`, reducing mod m throughout.
`test_repeat_agrees_with_literal_composition` holds it against the O(k)
literal fold for every k below 300 and a handful of larger ones.

### `deck(shuffle, m)`

The whole shuffled deck, top first — `out[position(c)] = c` for each card.
Exists for the statement's examples, whose ground truth is full 10-card
decks; the real parts never materialize a deck.

### `part1` / `part2` / `solve`

`part1` = forward at (10007, card 2019). `part2` = `repeat` to the 10¹⁴th
power mod the big deck, then `card_at` position 2020. Constants at module
top; `solve` returns both off one parse.

## The real input, measured

* **Technique census:** 100 lines = 44 `deal with increment` (arguments
  5..75, 34 distinct), 44 `cut` (arguments −9660..9781), 12
  `deal into new stack`.
* **Exact composed coefficients:** a is positive, 217 bits (66 decimal
  digits); b is negative, 225 bits (68 digits). Reduced: mod 10,007 the
  shuffle is x → 2604·x + 3049; mod the big deck it is
  x → 93922407988235·x + 117473918147102.
* **Orders:** 5003 shuffles restore the 10,007-card deck to factory order;
  on the big deck the order is the maximal 119315717514046 (primitive
  root), so no cycle shorter than the whole group's a-cycle exists to
  exploit.
* **Scale of the refused routes**, measured then extrapolated: the literal
  10,007-card simulation costs 42.0 ms for one shuffle; iterating the
  *composed* map once per application runs at 254 ns/step, or **0.8 years**
  for part 2's 101 trillion applications; and one big deck as a Python-free
  8-byte-per-card array would need 1 PiB. `repeat` does the whole thing in
  39 µs.

## Possible optimization

None worth shipping — the day totals **0.134 ms**, and 72% of that is
`parse_input` (string handling over 100 lines). The closed form above is
the classical alternative to the ladder and is pinned as correct, but at
this scale it is a wash. The only real lever left is aesthetic: folding
the parse mod each deck size would shrink the exact integers, and would
also destroy the one-parse-serves-all-decks property the tests lean on.

## Tests (what is pinned and why)

* **All seven statement walkthroughs** (three single-technique, four
  combined) as whole 10-card decks via `deck` — the forward map checked at
  every position at once — plus the hand-composed `Affine(63, 2)` for the
  increment-7/increment-9/cut−2 example.
* **`repeat` vs the literal k-fold composition** for k ∈ 0..299 and
  {1000, 4096, 12345}: the O(log k) ladder against the O(k) truth.
* **The geometric closed form vs `repeat`** on both real moduli at the real
  exponent, plus the a = 1 branch — the guide's sidebar identity is a test,
  not a sentence.
* **Inversion**: `card_at ∘ position` is the identity at every position of
  every example deck, and on both real moduli for card 2019.
* **Group theory**: order divides m·(m−1) (Lagrange, at 40 and at 10⁸);
  the real shuffle's exact orders (5003, and primitive-root maximal), with
  the divisor-elimination argument spelled out in the test body.
* **Primality of both deck sizes** by trial division to the square root —
  everything `pow(a, -1, m)` stands on.
* **CRLF** twice: a constructed `\r\n` example and the real file against
  its own LF-normalized text.
* **Input shape**: exactly 100 techniques, the composed a coprime to both
  moduli.
* **`check_locked`** against `LOCKED = (6850, 13224103523662)`, locked
  only after adventofcode.com accepted both.

## Benchmarks

`python python/bench.py 22 -n 25`, best/median ms:

| phase | best | median |
|---|---|---|
| parse | 0.096 | 0.100 |
| part 1 | 0.000 | 0.000 |
| part 2 | 0.039 | 0.039 |
| **total** | **0.134** | |

Part 1 is one multiply-add mod 10,007 — below the harness's display
resolution. Part 2 — a 101-trillion-fold shuffle of a 119-trillion-card
deck — costs 39 µs, four orders of magnitude less than [Day
21](day21_function_guide.md)'s part 2 spent interpreting Intcode. The
parse, at 0.096 ms, is 72% of the day.

## If I were writing this in Rust

Part Two's text warns "one wrong move with this many cards and you might
*overflow* your entire ship" — in Rust that is a literal compiler-visible
hazard, not a flavor line. The algorithm ports line for line; the trap is
arithmetic width. The big
deck is a **47-bit modulus**, so a product of two reduced residues needs
**94 bits** — `u64 * u64` silently overflows in release mode (and panics in
debug), which is precisely the class of bug Python's transparent big
integers make unrepresentable. The idiomatic fix is widening multiplication:

```rust
fn mul_mod(x: u64, y: u64, m: u64) -> u64 {
    ((x as u128 * y as u128) % m as u128) as u64
}
```

with `then`, `repeat` and a Fermat `pow_mod` built on it (`pow_mod(a, m -
2, m)` for the inverse, m being prime — or `i128` extended Euclid). The
*exact-integer* parse fold does not port: the real coefficients are 217
and 225 bits, past `i128`, so a Rust version would either fold modulo each
deck size from the start (parse twice or parameterize) or pull in a bigint
crate for a property Python gives for free. The signed intermediate values
(`cut -9660`, b negative throughout) also want care: either fold in
`i128` and reduce with `rem_euclid`, or normalize each primitive's b to
`m - n` at construction. This day is the standard-library pitch for
`pow(a, -1, m)` — the Rust ecosystem reaches for `num-modular` or five
lines of extended Euclid, and both are fine, but neither is *built in*.

## What's next

[Day 23](day23_function_guide.md) — when it lands. The year's remaining
Intcode days (23, 25) wire the frozen VM to a network and to a text
adventure, so [Day 7](day07_function_guide.md)'s cooperative multi-VM
scheduling is about to come back at scale. Today was the year's one pure
number-theory day — the counterpart to [Day 12](day12_function_guide.md)'s
lcm and [Day 16](day16_function_guide.md)'s operator algebra, completing
the trilogy of "the answer is a structure, not a simulation".
