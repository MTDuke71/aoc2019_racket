# Day 16 — Flawed Frequency Transmission (function guide)

> A signal-cleaning algorithm named FFT that is emphatically **not** the Fast
> Fourier Transform. One "phase" multiplies the digit vector by a fixed
> matrix and keeps the last digit of each result. The statement describes that
> matrix one row at a time, in prose, and if you transcribe the prose you get
> an O(n²)-per-phase loop that solves Part 1 in about 3 seconds and Part 2 in
> about **ten years**. The day is entirely about looking at the matrix instead
> of the prose. It has two properties — it is **upper triangular**, and every
> row is a handful of **constant-value runs** — and each property alone
> collapses one of the two parts. Part 1 becomes a **prefix-sum** sweep
> (**82× faster**, measured). Part 2 becomes a **suffix sum** over the last
> 8.1% of the signal, because triangularity says the other 91.9% cannot
> possibly reach the answer. Real input: **76795888** and **84024125**.

## The puzzle in one paragraph

The input is a string of digits. One *phase* replaces the list with a new one
of the same length: output element *k* (1-based) is Σ<sub>j</sub> input[j] ×
pattern<sub>k</sub>[j], where pattern<sub>k</sub> is `0,1,0,-1` with each value
repeated *k* times and the whole thing shifted left by one; only the ones digit
of |result| is kept. **Part 1:** the first eight digits after 100 phases.
**Part 2:** repeat the input 10000 times, run 100 phases on *that*, and read
eight digits starting at the offset given by the input's own first seven
digits. Real input: 650 digits, so Part 2's signal is 6,500,000 digits and the
offset is 5,972,877. Answers **76795888** and **84024125**.

Code: [python/day16.py](../../python/day16.py). Tests:
[python/tests/test_day16.py](../../python/tests/test_day16.py).

---

## The shape of the day: a phase is a matrix

Everything below follows from writing one phase as a matrix–vector product:

    out = M @ digits,   then   out[i] := abs(out[i]) mod 10

`M` does not depend on the data, only on `n`. Here it is for `n = 8`, printed
by the same rule the statement gives (`.` is zero):

```text
      j:  1  2  3  4  5  6  7  8
  k=1:    1  . -1  .  1  . -1  .
  k=2:    .  1  1  .  . -1 -1  .
  k=3:    .  .  1  1  1  .  .  .
  k=4:    .  .  .  1  1  1  1  .
  k=5:    .  .  .  .  1  1  1  1
  k=6:    .  .  .  .  .  1  1  1
  k=7:    .  .  .  .  .  .  1  1
  k=8:    .  .  .  .  .  .  .  1
```

Read the statement's own worked trace against that picture and every line
matches: row 1 is `1 . -1 . 1 . -1 .`, exactly the coefficients in
`1*1 + 2*0 + 3*-1 + 4*0 + …`.

Two properties jump out of the picture that do not jump out of the prose.

### 1. It is upper triangular

Row *k* is zero for every column *j < k*. That is what "skip the very first
value exactly once" *means* — the shift moves the leading run of zeros from
length *k* to length *k−1*, so the first nonzero entry of row *k* lands exactly
on the diagonal.

The consequence is a **causality rule**: after any number of phases, output
digit *i* depends only on input digits *i, i+1, …, n−1*. Nothing to the left
ever flows right. Part 2 is that sentence and nothing else.

This is pinned rather than asserted: `test_phase_is_triangular` bumps each
digit in turn and checks that no output digit to its right moves.

### 2. Every row is a few constant-value runs

Row *k* is not an arbitrary ±1 vector. It is:

- `k−1` zeros,
- `k` ones,
- `k` zeros,
- `k` minus-ones,
- and around again.

So the dot product for row *k* is not *n* multiplications; it is a small number
of **contiguous slice totals**, alternately added and subtracted. Runs start at
column *k*, *3k*, *5k*, … (1-based), so row *k* has about *n*/2*k* of them.

Summed over all rows:

    Σ_{k=1..n} n/2k  =  (n/2)·H(n)  ≈  (n/2)(ln n + γ)

which for *n* = 650 predicts **2293** slice queries per phase. The actual
count is **2383** (`sum(len(range(k-1, n, 2*k)) for k in range(1, n+1))`) —
the difference is the ceiling on each row. Against *n*² = **422,500**
multiply-adds, that is a **177× reduction in operations**.

A contiguous slice total is one subtraction if you have a **prefix-sum array**
(a 1-D *summed-area table* — the same object [Day 3](day03_function_guide.md)'s
sidebar and every integral-image trick lean on). So:

---

## Part 1: runs are prefix-sum queries

```python
def phase(digits: list[int]) -> list[int]:
    n = len(digits)
    prefix = [0, *accumulate(digits)]

    out = []
    for k in range(1, n + 1):
        total = 0
        start, sign = k - 1, 1
        while start < n:
            total += sign * (prefix[min(start + k, n)] - prefix[start])
            start += 2 * k
            sign = -sign
        out.append(abs(total) % 10)
    return out
```

`prefix[j]` is the sum of the first *j* digits, so `prefix[b] - prefix[a]` is
the total of `digits[a:b]`. Three details carry the correctness:

- **`start = k - 1`** is the triangularity, in 0-based coordinates. Row *k*'s
  first run of ones covers `digits[k-1 : 2k-1]`.
- **`start += 2 * k`** skips a run of zeros and lands on the next signed run;
  `sign = -sign` alternates `+1, −1, +1, …`.
- **`min(start + k, n)`** clamps the last, truncated run of every row. This is
  the only place an off-by-one can hide, and it hides *by length* — a bug here
  is invisible on the puzzle's 8- and 32-digit examples and fatal on 650. Hence
  `test_prefix_sums_match_the_definition`, which runs `phase` against a literal
  transcription of the statement (`definition`, the O(n²) oracle) at **every**
  length from 1 to 40.

`abs` before `% 10` matters: Python's `%` already returns a non-negative
result, so `-17 % 10` is `3`, not `7`. The statement says `-17` becomes `7`.
Dropping the `abs` gives 10's-complement digits and a wrong answer on the very
first example.

### What it buys, measured

One phase of the real 650-digit input:

| phase implementation | ms/phase | ×100 phases |
|---|---:|---:|
| literal definition (O(n²)) | 32.16 | 3.22 s |
| prefix sums over runs | 0.39 | 0.04 s |

**82.1×.** (Measured wall-clock ratio, against a 177× reduction in arithmetic
operations — the gap is Python overhead per slice query, which is much heavier
per unit of work than per multiply-add inside a tight loop.)

Part 1 as benchmarked below is **38.2 ms** for all 100 phases, of which the
100 `accumulate` calls that build the prefix arrays are only **1.46 ms**
(3.8%) — the cost is in the 238,300 slice queries, not in the scans.

### The answer is a string

`part1` returns `"76795888"`, not `76795888`. The statement's own four-phase
trace lands on **`01029498`** — a leading zero — and as an `int` that would be
`1029498`, a different and rejected answer. `test_answer_is_a_string_because_of_leading_zeros`
pins the case the real input happens not to exercise.

---

## Part 2: the offset changes the problem, not the algorithm

Part 2 asks for 100 phases of a **6,500,000-digit** signal. Two facts about
that, both measured rather than estimated:

- With the **literal definition**, one phase is *n*² work. Scaling the 32.16 ms
  at *n* = 650 by (10000)² gives **37 days per phase** — about **10 years** for
  100 phases.
- With the **prefix-sum `phase` that ships**, one phase at *n* = 6,500,000
  measures **14.82 s**. That is 100 phases in **24.7 minutes**. Genuinely
  runnable, and still the wrong answer to the puzzle.

The way out is not a faster phase. It is noticing that most of the signal is
irrelevant.

### The lower half of the matrix degenerates

Row *k*'s first run of ones covers columns *k* through 2*k*−1. When
2*k*−1 ≥ *n* that run reaches the end of the signal — and every later run
(starting at 3*k*) is off the end entirely. So for *k* past the midpoint the
whole row is:

```text
n=12, lower half:
      j:  1  2  3  4  5  6  7  8  9 10 11 12
  k= 6:   .  .  .  .  .  1  1  1  1  1  1  .
  k= 7:   .  .  .  .  .  .  1  1  1  1  1  1
  k= 8:   .  .  .  .  .  .  .  1  1  1  1  1
  k= 9:   .  .  .  .  .  .  .  .  1  1  1  1
  k=10:   .  .  .  .  .  .  .  .  .  1  1  1
  k=11:   .  .  .  .  .  .  .  .  .  .  1  1
  k=12:   .  .  .  .  .  .  .  .  .  .  .  1
```

(*k* = 6 is shown to mark the boundary: at *n* = 12 it still has a zero in the
last column, so "all ones to the end" begins at *k* = 7. The condition is
2*k*−1 ≥ *n*, i.e. *k* > *n*/2.)

Restricted to that region the matrix is **unit upper triangular**, and a phase
collapses to

    out[i] = (sum of digits[i:]) mod 10

which is a **suffix sum**: one running total swept right to left. No prefix
array, no per-row loop, no sign alternation, and — because every digit is
non-negative — no `abs` either.

`test_suffix_transform_agrees_with_full_phases` checks exactly this: run the
general `phase` 100 times over a 101-digit signal, slice the tail off the
result, and compare against `suffix_transform` on the tail alone.

### Triangularity licenses throwing away the prefix

`out[i]` depends only on `digits[i:]`, at every phase, so nothing left of the
message offset can ever influence the message. That is what makes the puzzle
tractable: we never have to *build* the 6,500,000-digit signal at all.

| quantity | value |
|---|---:|
| signal length (650 × 10000) | 6,500,000 |
| message offset (first seven digits) | 5,972,877 |
| offset as a fraction of the signal | 91.89% in |
| tail actually processed | **527,123** digits (8.110%) |
| digit updates for 100 phases | 52,712,300 |

`test_prefix_cannot_reach_the_tail` demonstrates the licence directly:
scribble over every digit before the offset and the tail's 100-phase output is
byte-identical.

### The precondition nobody promises

**The shortcut is only valid because the offset lands past the midpoint.** The
statement never says it will. It is a property that every published input
happens to share — the three Part Two examples put their offsets at
303673/320000, 293510/320000 and 308177/320000, and the real input at
5972877/6500000, all comfortably in the top half.

So `part2` checks rather than assumes:

```python
offset = message_offset(digits)
total = len(digits) * REPEATS
if offset < total // 2:
    raise ValueError(f"offset {offset} is in the upper half of {total}; suffix sums do not apply")
```

An input with a small offset would need the real algorithm on the real signal
(the 24.7-minute route above, or the closed form in the sidebar), and silently
returning a suffix-sum answer for it would be wrong rather than slow.
`test_upper_half_offset_is_refused` feeds it exactly such a signal;
`test_offset_lands_in_the_lower_half` and `test_example_offsets_land_in_the_lower_half`
pin the precondition on the real input and on all three examples.

---

## The Day 16 code, form by form

### `parse_input` — digits, and the CRLF tax

```python
def parse_input(text: str) -> list[int]:
    return [int(ch) for ch in text.strip()]
```

`.strip()` is doing CRLF duty. Inputs downloaded on Windows end `\r\n`, and an
unstripped `\r` reaches `int('\r')` — a `ValueError`, so this one fails loudly
rather than silently, but it fails on a fresh input all the same. Note that
`test_crlf` constructs its CRLF case **as a string literal**: `Path.read_text()`
opens in universal-newline mode and rewrites `\r\n` to `\n`, so a CRLF test
that loads its fixture that way asserts nothing. (`conftest.py`'s `real_input`
opens with `newline=""` for precisely this reason; `test_crlf_real_input` uses
it to check the file on disk as it actually is.)

Note also that this is the *full* parse: the day reasons about a list of
integers, and nothing downstream re-splits or re-`int`s anything.

### `phase` — one phase, general

Covered above. This is the only function that implements the puzzle's actual
definition, and it is the oracle everything else is checked against.

### `transform` — repeat `phase`

```python
def transform(digits: list[int], phases: int = PHASES) -> list[int]:
    for _ in range(phases):
        digits = phase(digits)
    return digits
```

Rebinding rather than mutating: `phase` returns a fresh list, and the caller's
input is untouched. That is what lets `check_locked` hand the same parse to
both parts without the Intcode days' aliasing hazard.

### `message_offset` — the first seven digits

```python
def message_offset(digits: list[int]) -> int:
    return int(digits_to_str(digits[:7]))
```

Seven digits, always — the statement says so, and it is what makes the offset
land at 5,972,877 rather than somewhere convenient. The leading zeros in the
examples (`0303673`) are why this goes through the string rather than
positional arithmetic on the list.

### `real_tail` — the suffix, without building the signal

```python
def real_tail(digits: list[int], offset: int, repeats: int = REPEATS) -> list[int]:
    q, r = divmod(offset, len(digits))
    return digits[r:] + digits * (repeats - q - 1)
```

`digits * repeats` then slicing would allocate a 6,500,000-element list to keep
527,123 of it. Instead: the offset falls `r` digits into copy number `q`, so
the tail is *the remainder of that copy* followed by *every whole copy after
it*. The length works out exactly:

    (n − r) + (repeats − q − 1)·n = n·repeats − (q·n + r) = n·repeats − offset

`test_real_tail_matches_the_honest_construction` checks it against the naive
`(digits * REPEATS)[offset:]` on a 32-digit example, where materialising the
whole thing is affordable.

### `suffix_transform` — 100 running totals

```python
def suffix_transform(tail: list[int], phases: int = PHASES) -> list[int]:
    reversed_tail = tail[::-1]
    for _ in range(phases):
        reversed_tail = [value % 10 for value in accumulate(reversed_tail)]
    return reversed_tail[::-1]
```

Reverse once, accumulate `phases` times, reverse back. `accumulate` does the
running total in C; the `% 10` comprehension is the only per-digit Python in
the hot loop, which is why it beats the obvious explicit
`for i in range(len(t)-1, -1, -1)` loop that mutates in place: measured
**2.19 s versus 3.24 s** on the real tail, a 1.48× gap that is pure
interpreter overhead — same algorithm, same operation count.

Reducing mod 10 every phase is not just cosmetic: it keeps partial sums bounded
by 9 × 527,123 ≈ 4.7 million, comfortably inside a machine word, so CPython
never reaches for multi-digit integer arithmetic.

### `part1`, `part2`, `solve`, `main`

`solve` returns both answers. Unlike [Day 15](day15_function_guide.md), where
`solve` existed to *share* an expensive exploration between the parts, here the
parts genuinely share nothing — Part 1 works on 650 digits and Part 2 on a
different 527,123 — so `solve` is a plain tuple of the two calls, and
`test_solve_agrees_with_the_parts` says so.

---

## Why any of this is legal: carry-free digits

Everything above quietly assumes something worth making explicit, because it is
the foundation the whole day stands on: **there is no carry from one digit to
the next.**

A phase computes each output digit as `abs(one dot product) mod 10`, applied
**coordinate-wise and independently**. Position *i* depends on the *digits* at
positions ≥ *i*, never on their magnitudes. So reducing mod 10 is a ring
homomorphism applied per coordinate, and it **commutes with the operator** —
you may discard everything above the ones digit after every phase and the
answer is unchanged.

What that discards is not small. The exact 100-phase coefficient at maximum gap
is

    C(527122 + 99, 99)  ->  411 decimal digits

so `out[0]`, computed honestly without ever reducing, is a ~411-digit integer
*per output position*. Under a carry chain none of it could be thrown away: a
carry out of position *i*+1 means position *i* is not final until *i*+1 is
known **exactly**, so no truncation is legal anywhere, at any step.

Three things follow, and each is load-bearing somewhere in the code:

- **The transform is iterable.** *n* digits in, *n* digits out, same type. With
  carries the output could be longer than the input and `transform`'s loop
  would not close.
- **State stays bounded.** Digits are 0–9, so the running total in
  `suffix_transform` never exceeds 9 × 527,123 ≈ 4.7 M — one machine word, no
  bignums, no reallocation.
- **The operator is linear over ℤ/10ℤ.** Which is what lets 100 phases collapse
  into the single binomial dot product in the next section.

### Hardware analogy

This is exactly why a **carry-save adder** is fast. A ripple-carry adder's
critical path *is* the carry chain; carry-save and other redundant number
systems exist to break it so every digit position becomes independent and the
array parallelises. Day 16's transform arrives already in that form.

The next section's Kummer-plus-Lucas trick is the same idea one level up: it is
a **residue number system** — work mod 2 and mod 5 independently, recombine by
CRT — chosen for exactly the reason RNS is ever chosen, that the residues do
not talk to each other.

### The one nonlinearity that survives: `abs`

`mod 10` is coordinate-wise, so it is harmless. **`abs` is not.** It is applied
per coordinate too, but it is not compatible with ℤ/10ℤ, and it is what
confines every algebraic claim above to the lower half of the matrix.

On the statement's own `12345678`:

```text
raw totals    = [-4, -8, 12, 22, 26, 21, 15, 8]
abs(t) % 10   = [ 4,  8,  2,  2,  6,  1,  5, 8]   <- what the puzzle wants
t % 10        = [ 6,  2,  2,  2,  6,  1,  5, 8]   <- what a linear map gives
                   ^   ^
                   differ at exactly the rows whose total went negative
```

Below the midpoint every coefficient is `+1` and every digit is non-negative,
so a total **cannot** be negative and `abs` is a no-op. That is why
`suffix_transform` omits it. Above the midpoint the `−1` runs are live, totals
go negative, and the map is not even additive:
`phase([1,0,1,0]) ≠ phase([0,0,1,0]) + phase([1,0,0,0]) (mod 10)`.

So the midpoint is two boundaries at once, and the second is the sharper one:
it is where the matrix degenerates into a suffix of ones, **and** it is where
the phase becomes a genuine linear map over a ring. Measured at *n* = 20,
100 real phases against the honest matrix power `M¹⁰⁰ mod 10`:

```text
real transform (with abs) : [7,3,5,3,6,2,6,0,3,5, 1,1,0,8,0,6,1,5,3,5]
(M^100 mod 10) @ x        : [1,1,5,3,0,6,6,0,3,5, 1,1,0,8,0,6,1,5,3,5]
                                                  ^--- tail: identical
   agree on the tail (i >= 10) : True
   agree on the head (i <  10) : False
```

**This is why Part 2 has a closed form and Part 1 does not — and the reason is
`abs`, not size.** Part 1 wants the first eight digits, which sit as deep in the
nonlinear region as it is possible to get. No amount of linear algebra reaches
them; the phases have to actually run.

Both halves are pinned: `test_abs_is_a_no_op_below_the_midpoint` (universal for
the tail at every length 2..40; the head is demonstrated on `12345678`, since
whether a head total *actually* goes negative is data-dependent) and
`test_phases_equal_the_matrix_power_only_on_the_tail`.

---

## The problem within the problem: 100 suffix sums are Pascal's triangle

The shipped Part 2 applies the same linear operator 100 times. Applying a
linear operator 100 times is *one* linear operator, and it is worth asking
which one.

Let `S` be the suffix-sum operator, `(S x)[i] = Σ_{j≥i} x[j]`. Then:

- `S¹`: coefficient of `x[j]` in `out[i]` is 1 for every `j ≥ i`.
- `S²`: `x[j]` is counted once for each way to reach it in two steps — that is
  `j − i + 1` ways.
- `S^k`: the coefficient is the number of weakly increasing length-*k* chains
  from *i* to *j*, i.e.

      out[i] = Σ_{j ≥ i} C(j − i + k − 1, k − 1) · x[j]     (mod 10)

So **100 phases of the tail is a single dot product against row 99 of Pascal's
triangle**, `C(d + 99, 99)` for gap `d = j − i`. Verified numerically for
*k* = 1, 2, 3, 7 and 100 against `math.comb` — the identity holds exactly, mod 10.

That is interesting on its own, and it also makes Part 2 *cheap*, because the
puzzle asks for **eight** output digits, not half a million. Eight dot products
of length 527,123 is 4.2 M multiply-adds against the shipped solution's
52.7 M digit updates.

### Getting `C(d + 99, 99) mod 10` without computing `C(d + 99, 99)`

`math.comb(527222, 99)` is a 500-digit integer; doing that half a million times
defeats the point. Two classical results avoid it, and they compose through the
Chinese Remainder Theorem because 10 = 2 × 5.

- **Kummer's theorem** (p = 2): `C(a+b, a)` is odd exactly when adding *a* and
  *b* in base 2 produces no carries — equivalently `a & b == 0`. Here
  *a* = 99, *b* = *d*, so the whole mod-2 computation is **`(d & 99) == 0`**.
  One instruction.
- **Lucas' theorem** (p = 5): `C(n, r) ≡ Π C(n_i, r_i) (mod 5)`, digitwise in
  base 5, with 99 = `344`₅. Nine digit steps at most, and it short-circuits the
  moment any factor is zero — which is most of the time.

CRT recombines: `x ≡ (5·m₂ + 6·m₅) mod 10`. Checked against `math.comb(m, 99) % 10`
for 3000 consecutive *m* — exact agreement.

### What it measures

| Part 2 route | time | vs shipped |
|---|---:|---:|
| shipped — 100 suffix-sum sweeps over 527,123 digits | 1987.7 ms | 1.0× |
| binomial coefficients + 8 dense dot products | 268.9 ms | **7.4×** |
| …exploiting sparsity (see below), dot products only | 38.6 ms | 51.5× |
| …sparse, including coefficient construction | ~169 ms | **11.8×** |

All three produce `84024125`.

The sparsity is the pretty part. `C(d+99, 99) mod 10` is zero unless it is
nonzero mod 2 *or* mod 5. Mod 2 it is nonzero only when `d & 99 == 0` — and
99 = `0b1100011` has four set bits, so only about 1 in 16 values of *d* qualify.
Mod 5 the Lucas product zeroes out even more aggressively. Measured on the real
tail: **40,857 of 527,123 coefficients are nonzero — 7.75%**. The dot product
only has to visit those.

This is a sidebar, not the shipping solution, per the repo's
[optimisation policy](../../CLAUDE.md): the shipped `python/day16.py` says
"a phase over the tail is a suffix sum", which is the insight the puzzle is
actually about. "…and 100 suffix sums are a binomial convolution whose
coefficients you can get from Kummer and Lucas" is a *second* insight, worth
writing down and not worth hiding the first one behind.

### Possible optimization: sub-linear via periodicity

Not implemented, not measured — recorded because it is the obvious next step.
`C(d+99, 99) mod 2` depends only on `d & 99`, so it is periodic in *d* with
period 128. `mod 5` is *not* periodic, but by Lucas it depends only on the
base-5 digits of *d* + 99 aligned against `344`₅, which is a 3-digit window
plus a carry chain — a digit-DP could enumerate the nonzero positions directly
in *O*(number of nonzeros) rather than filtering 527,123 candidates. That would
turn the 130 ms coefficient build into something proportional to the 40,857
answers, and Part 2 into a ~50 ms problem. Diminishing returns on a 2-second
day; the technique is the point.

---

## Tests (what is pinned and why)

`python/tests/test_day16.py` — **67 tests**, one skip (Part 2 unverified).

| test | claim |
|---|---|
| `test_worked_trace` | `12345678` after 1/2/3/4 phases matches the statement, digit for digit |
| `test_trace_is_a_chain` | each trace line is one `phase` of the line above — the trace is a chain, not four independent facts |
| `test_answer_is_a_string_because_of_leading_zeros` | `01029498` ≠ `1029498`; the answer type is `str` on purpose |
| `test_part1_examples` | all three 100-phase Part One signals |
| `test_prefix_sums_match_the_definition` (×40) | **the prefix-sum phase equals the statement's literal O(n²) definition at every length 1..40** — the run-truncation `min` is checked at lengths the puzzle never shows |
| `test_phase_is_triangular` | row *k* is zero left of column *k*: bumping digit *j* moves no output digit right of *j* |
| `test_part2_examples` | all three Part Two signals |
| `test_example_offsets_land_in_the_lower_half` | every published example satisfies the precondition the real input relies on |
| `test_upper_half_offset_is_refused` | an offset in the *upper* half raises rather than returning a plausible wrong answer |
| `test_real_tail_matches_the_honest_construction` | the cheap tail construction equals `(digits * 10000)[offset:]` |
| `test_suffix_transform_agrees_with_full_phases` | **below the midpoint a phase IS a suffix sum** — checked against the general `phase`, not asserted |
| `test_prefix_cannot_reach_the_tail` | **digits left of the offset cannot influence the answer** — scribble the prefix, the tail is unchanged |
| `test_crlf`, `test_crlf_real_input` | a `\r` in the input does not reach `int()` |
| `test_real_signal_shape` | 650 digits, all 0–9 |
| `test_offset_lands_in_the_lower_half` | 5,972,877 of 6,500,000 — inside the signal, past the midpoint |
| `test_abs_is_a_no_op_below_the_midpoint` | **totals below the midpoint are never negative, so `abs` does nothing there** — universal at every length 2..40; the head case is data-dependent and shown on `12345678` |
| `test_phases_equal_the_matrix_power_only_on_the_tail` | **100 phases *is* `M¹⁰⁰ mod 10` on the tail and is not on the head** — locating the `abs` nonlinearity exactly |
| `test_solve_agrees_with_the_parts` | `solve` is not a third implementation |
| `test_real_input` | `check_locked(16, LOCKED)` |

The three bolded rows are the [standing rule](../../CLAUDE.md) in action: the
prefix-sum identity, the suffix-sum degeneration, and the causality rule are
each a *claim*, and each is now a claim a test checks rather than a claim the
prose asserts. Two of the three are invisible in the puzzle's own examples.

`definition()` inside the test module deserves a note. It transcribes the
statement literally, including the slot arithmetic `((j + 1) // k) % 4`, which
is where the "skip the very first value" shift lives: index 0 of the shifted
pattern sees repeated-pattern index 1. Having a slow, obviously-correct oracle
next to a fast, cleverly-correct implementation is the cheapest correctness
insurance available, and it is what made the length sweep possible.

---

## Benchmarks

`.venv\Scripts\python.exe python\bench.py 16` — best / median ms over 7 reps:

| day | parse | part 1 | part 2 | total |
|---|---:|---:|---:|---:|
| 16 | 0.037 / 0.038 | 38.169 / 38.591 | 1989.436 / 2004.181 | 2027.642 |

Part 2 is **52×** Part 1 and 98% of the day. That ratio is worth reading
carefully, because the *inputs* are 811× apart in size (650 digits versus
527,123) while the *times* are only 52× apart — the suffix-sum inner loop is
much cheaper per digit than the prefix-sum one, and almost all of it is running
in C inside `accumulate`.

Where Day 16 sits in the year:

| day | total | note |
|---|---:|---|
| 03 | 185.0 ms | previous heaviest non-Intcode day |
| 13 | 134.4 ms | |
| 15 | 133.2 ms | |
| 12 | 82.0 ms | |
| **16** | **2027.6 ms** | **the slowest day of the year so far, by 11×** |

And what it would have been without either insight:

| route | Part 1 | Part 2 |
|---|---:|---:|
| literal definition | 3.22 s | ~10 years (extrapolated from 32.16 ms at *n*=650, scaled by 10⁸) |
| prefix sums, whole signal | 38.2 ms | 24.7 min (measured: 14.82 s for one phase at *n* = 6,500,000) |
| prefix sums + suffix shortcut (**shipped**) | 38.2 ms | 1.99 s |
| + binomial closed form (sidebar) | — | 0.27 s |

The 24.7-minute row is the interesting one. It is the trap the day sets: the
prefix-sum optimisation is *real*, it is a genuine 82× win, and it is nowhere
near enough. Optimising the phase is the wrong axis entirely; the win comes
from not looking at 91.89% of the data.

---

## If I were writing this in Rust

Two things change, and one does not.

**Part 1's inner loop becomes free.** `phase` in Rust is a `Vec<i32>` prefix
scan and a slice-indexed loop, all of it monomorphised and bounds-check-elided
in the obvious places. The 82× Python win over the literal definition would
shrink dramatically, because in Rust the *literal* definition is also fast —
650² = 422,500 multiply-adds per phase is well under a millisecond of real
work on any modern core. (Estimate, not a measurement — there is no Rust in
this repo to run.) Both routes would finish Part 1 fast enough that the
choice would not matter. In Python, the constant factor on interpreted loop iterations is what
makes the asymptotic improvement feel like the whole day.

**Part 2's inner loop is the one place Rust would really show.** The shipped
Python does 52.7 M `value % 10` operations through the interpreter even with
`accumulate` carrying the addition. In Rust:

```rust
fn suffix_transform(tail: &mut [u8], phases: usize) {
    for _ in 0..phases {
        let mut total: u32 = 0;
        for d in tail.iter_mut().rev() {
            total += *d as u32;
            *d = (total % 10) as u8;
        }
    }
}
```

`u8` digits — the whole 527 KB tail fits in a modern L2, versus Python's list of
527,123 pointers to boxed integers at ~4 MB of pointers plus indirection. This
is the same "one byte per cell versus one pointer per cell" argument that
makes bitboard-style representations win in chess engines: the algorithm is
identical, the memory traffic is not. Expect low tens of milliseconds — the
same ballpark as the *sparse binomial* sidebar in Python, which is a nice
illustration of the tradeoff between a better algorithm and a better constant
factor.

**What does not change:** `real_tail`. Rust would write it as
`digits[r..].iter().chain(digits.iter().cycle().take((repeats - q - 1) * n)).copied().collect()`,
which is prettier than the Python but does exactly the same thing — and, more
to the point, the *reason* it can skip the first 91.89% of the signal is
triangularity, which is a property of the matrix, not of the language. No
amount of Rust rescues someone who materialises 6,500,000 digits and runs 100
honest phases over them. That is the day.

---

## What's next

Day 17 is Intcode again — the VM froze at [Day 9](day09_function_guide.md) and
lives in [python/intcode.py](../../python/intcode.py), so the interesting part
will be, as with [Day 13](day13_function_guide.md) and
[Day 15](day15_function_guide.md), what shape of interface the program presents
rather than the interpreter itself.

Day 16 is the year's first day with **no** VM in it at all since
[Day 14](day14_function_guide.md), and the second (after
[Day 12](day12_function_guide.md)) whose whole content is *noticing that a
big computation decomposes*. Day 12 decomposed a 6-D simulation into three
independent 1-D ones and recombined with `lcm`. Day 16 decomposes a
6,500,000-element linear map into a triangular one and throws away the part
that cannot reach the answer. Different structures, same instinct: look at the
operator, not at the loop.
