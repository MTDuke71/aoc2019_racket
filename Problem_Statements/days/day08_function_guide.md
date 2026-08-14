# Day 8 — Space Image Format (function guide)

> **Historical note.** This guide annotates the frozen Racket solution
> ([src/day08.rkt](../../src/day08.rkt)), written when this repo was the
> Racket leg of a language rotation. The repo is Python-only now and the
> Racket is frozen, not deleted -- see the [README](../../README.md). The
> guide is left as it was and remains accurate about the code it describes.

> A **mechanics day**, and the mechanic is *reshaping*: a flat string of
> 15 000 digits is secretly a 3-D array — 100 **layers** of a 25×6 image,
> filled row-major. Both parts are the same one-liner of index arithmetic
> read two ways. Part 1 ("layer with the fewest `0`s, then #1s × #2s") is a
> **per-layer histogram**. Part 2 ("stack the layers, keep the first
> non-transparent pixel, read the message") is the **painter's algorithm /
> z-buffer first-opaque-fragment** resolve — and the lit pixels spell
> `UBUFP`. New Racket this day: `for/vector`, `vector-count`, `argmin`, and
> a second outing for `for/first` ([Day 6](day06_function_guide.md)).

## The puzzle in one paragraph

The input is one long run of digits. It decodes as a stack of equal-sized
**layers**, each `width × height` pixels, filled left-to-right then
top-to-bottom; the first `width·height` digits are layer 1, the next batch
layer 2, and so on. The real image is **25 wide, 6 tall** — so each layer
is 150 pixels and the 15 000-digit input is exactly **100 layers**.
**Part 1** is a transmission-integrity check: find the layer with the
*fewest `0` digits*, and on that layer multiply the count of `1`s by the
count of `2`s. **Part 2** decodes the picture: the layers stack
front-to-back, each pixel is `0` (black), `1` (white), or `2`
(transparent), and the visible color at each position is the *first
non-transparent* value seen from the front. Render black/white to a 25×6
block and the white pixels form five capital letters — the BIOS password.

---

## The one idea: index arithmetic on a flattened 3-D array

Everything here is one fact about laying a 3-D array out in a 1-D buffer.
A pixel at **(layer `L`, row `r`, col `c`)** lives at flat offset

```
offset(L, r, c) = L·(W·H) + r·W + c
```

This is **row-major (C-order) striding**, the same layout `clox` uses for
a flattened 2-D table and the same one `ndarray`/NumPy calls C-contiguous.
Each axis has a *stride*: moving one layer jumps `W·H`, one row jumps `W`,
one column jumps `1`. The two parts are just two different slices of that
formula:

| Part | What it walks | Slice of the formula |
|------|---------------|----------------------|
| 1 | each **layer** as a block | chunk at `L·(W·H)`, ignore `r`, `c` |
| 2 | each **pixel column** down the layer axis | fix `r·W + c`, vary `L` |

Part 1 never needs the 2-D geometry — a layer is just a 150-long slice to
histogram. Part 2 never needs to know which row/col a pixel is until the
final render — it fixes a flat position `p = r·W + c` and scans `p`,
`p + 150`, `p + 300`, … down the stack. Get the offset formula right and
both parts fall out.

---

## The algorithm in Python

Day 8 is mechanics-flavored, so the guide is language-first below — but the
shape is small enough that the Python companion
([python/day08.py](../../python/day08.py)) is the fastest way to see the
whole thing at once:

```python
def image_layers(digits, w, h):       # 1-D -> list of W*H-pixel layers
    size = w * h
    return [digits[i:i+size] for i in range(0, len(digits), size)]

def part1(digits, w, h):              # fewest-zeros layer, #1s * #2s
    layer = min(image_layers(digits, w, h), key=lambda L: L.count(0))
    return layer.count(1) * layer.count(2)

def decode_image(digits, w, h):       # first opaque pixel, front to back
    layers = image_layers(digits, w, h)
    return [next(L[p] for L in layers if L[p] != 2) for p in range(w * h)]
```

`min(..., key=…)` is Part 1's whole engine — pick the layer minimizing its
zero-count, then two `.count()` calls. `next(… for … if L[p] != 2)` is
Part 2's — the first opaque value down the layer axis at position `p`. The
Racket version is the same three moves with `argmin`, `vector-count`, and
`for/first` standing in.

---

## The Day 8 code, form by form

### `parse-input` — `for/vector` builds a digit buffer

```racket
(define (parse-input s)
  (for/vector ([c (in-string (string-trim s))]
               #:when (char-numeric? c))
    (- (char->integer c) (char->integer #\0))))
```

- **`for/vector` is new** — the vector sibling of `for/list` / `for/hash`
  ([Day 6](day06_function_guide.md)): each iteration's body value becomes
  one element of a freshly built **vector**. A vector, not a list, because
  both parts index by *computed offset* (`vector-ref` is O(1);
  `list-ref` would be O(n)). Rust analogue: `s.chars().map(…).collect::<Vec<_>>()`.
- **`(- (char->integer c) (char->integer #\0))`** is the ASCII
  digit-to-value trick: digit characters `#\0`…`#\9` are contiguous in the
  code-point table, so subtracting `#\0`'s code turns the *character* `#\7`
  into the *number* `7`. Same idiom as C's `c - '0'` and Rust's
  `c.to_digit(10)`.
- **`string-trim` then `#:when char-numeric?`** is belt-and-suspenders
  against the trailing newline: `string-trim` drops leading/trailing
  whitespace, and the `#:when` guard skips any stray non-digit mid-stream
  so a value of 150·100 = 15 000 is guaranteed. (`#:when` inside a `for`
  filters iterations — first seen on [Day 6](day06_function_guide.md)'s
  `for/first`.)

### `image-layers` — stride the flat buffer into layers

```racket
(define (image-layers digits width height)
  (define size (* width height))
  (for/list ([start (in-range 0 (vector-length digits) size)])
    (vector-copy digits start (+ start size))))
```

This is the 1-D → list-of-layers reshape, and it leans on the
**three-argument `in-range`**: `(in-range 0 N size)` yields
`0, size, 2·size, …` up to (but not including) `N` — i.e. it *strides* by
a whole layer. At each stride start, `vector-copy` slices the half-open
range `[start, start+size)` into a fresh 150-element layer vector.
(`vector-copy` with two bounds is Racket's slice; Rust's `&digits[start..start+size]`,
except Racket copies where Rust borrows.) On the real input this produces
100 layers of 150 pixels each.

### `digit-count` — histogram one layer with `vector-count`

```racket
(define (digit-count layer d)
  (vector-count (lambda (x) (= x d)) layer))
```

**`vector-count` is new** (from `racket/vector`, pulled in by `#lang
racket`): it tallies how many elements satisfy the predicate — the vector
sibling of `count` from `racket/list`. So `(digit-count layer 0)` is "how
many `0`s in this layer", the quantity Part 1 minimizes. Rust analogue:
`layer.iter().filter(|&&x| x == d).count()`.

### `part1` — `argmin` picks the least-corrupted layer

```racket
(define (part1 digits width height)
  (define fewest-zeros
    (argmin (lambda (layer) (digit-count layer 0))
            (image-layers digits width height)))
  (* (digit-count fewest-zeros 1)
     (digit-count fewest-zeros 2)))
```

**`argmin` is new** (from `racket/list`): `(argmin key lst)` returns the
**element** of `lst` for which `(key element)` is smallest — *not* the
minimum key value, and *not* the index. The name comes straight from
mathematics' **arg min** (the argument that minimizes a function), and it's
exactly Python's `min(lst, key=…)`. Here the key is the layer's
zero-count, so `fewest-zeros` is the least-corrupted layer; the checksum is
then `#1s × #2s` on it. (Racket also has `argmax`; both pick the *first*
element on a tie.)

### `decode-image` — first opaque pixel down the stack

```racket
(define (decode-image digits width height)
  (define size (* width height))
  (define n-layers (quotient (vector-length digits) size))
  (for/vector ([p (in-range size)])
    (for/first ([l (in-range n-layers)]
                #:unless (= 2 (vector-ref digits (+ (* l size) p))))
      (vector-ref digits (+ (* l size) p)))))
```

The heart of Part 2, and a clean nest of two `for`s:

- **Outer `for/vector` over `p`** walks each of the 150 pixel *positions*
  (a flat `r·W + c`), building the resolved image one pixel at a time.
- **Inner `for/first` over `l`** walks the layer axis front-to-back and
  returns the value at the first layer where this pixel **isn't** `2`.
  `(+ (* l size) p)` is the offset formula `L·(W·H) + (r·W + c)` with
  `(r·W + c)` already collapsed into `p`. `#:unless` is `#:when`'s negation
  — "stop at the first layer that is *not* transparent". `for/first` short-circuits
  (the [Day 6](day06_function_guide.md) find-first), so the scan stops at
  the topmost opaque pixel; the puzzle guarantees one exists in every
  column, so it never falls through to `#f`.

Note the deliberate asymmetry with `image-layers`: Part 2 indexes the
*original flat buffer* directly rather than reusing the chunked layers,
because here we want to walk **down a column** (stride `size`), not across
a layer. Same buffer, orthogonal traversal — the two strides of the offset
formula.

### `render` — pixels to a readable glyph block

```racket
(define (render pixels width height)
  (string-join
   (for/list ([row (in-range height)])
     (list->string
      (for/list ([col (in-range width)])
        (if (= 1 (vector-ref pixels (+ (* row width) col))) #\# #\space))))
   "\n"))
```

The inverse reshape: flat pixel vector → `height` rows of `width`
characters. The nested `for/list`s rebuild the 2-D grid (`(+ (* row width)
col)` is the row-major offset again, now read forward), `list->string`
turns each row's character list into a string, and `string-join` stitches
the rows with newlines. Lit (`1`) → `#`, dark (`0`) → space, so the white
pixels stand out as letters. (Swap `#\#` for `#\█` — Unicode full block —
and the glyphs read even cleaner in a terminal; `#` keeps the output pure
ASCII and the tests easy to pin.)

### `solve` — parse once, print both parts

```racket
(define (solve contents)
  (define digits (parse-input contents))
  (printf "  part 1: ~a\n" (part1 digits WIDTH HEIGHT))
  (printf "  part 2:\n~a\n" (part2 digits WIDTH HEIGHT)))
```

The only structural difference from Days 1–7's `solve`: Part 2's answer is
a multi-line image, so it prints on its own lines under a header rather
than inline. `WIDTH`/`HEIGHT` are the module constants `25`/`6` — the only
place the code commits to the puzzle's dimensions; every shape function
takes them as arguments so the worked examples (3×2, 2×2) test the same
code.

---

## The problem within the problem: Part 2 is the painter's algorithm

Part 2's prose — "layers rendered first-in-front, keep the top visible
pixel, transparent lets the one behind show through" — is a verbatim
description of **alpha compositing under the painter's algorithm**. In
graphics you draw back-to-front and each fragment's `over` operator blends
it onto what's already there; here the alpha is *binary* (`2` = fully
transparent, `0`/`1` = fully opaque), so "blend" collapses to "the first
opaque fragment wins" and the whole thing is the **first-opaque-fragment**
query a z-buffer answers per pixel. Two canonical names worth banking:

- **Painter's algorithm** — composite ordered layers; nearer layers occlude
  farther ones. Our front-to-back scan with an early stop is the
  occlusion-test optimization (don't bother with layers behind the first
  opaque one).
- **Row-major / C-contiguous layout** — the offset formula `L·W·H + r·W +
  c`. The transferable skill is reading a flat buffer as an N-D array by
  its strides; it returns every time AoC flattens a grid (and it's how
  `clox` would store a 2-D table in one `ValueArray`).

The reframe is the lesson: the puzzle *looks* like fiddly string-chopping,
but naming it "binary-alpha painter's algorithm over a row-major 3-D array"
tells you the data structure (flat buffer + strides) and the kernel (first
opaque down the layer axis) before you write a line. That's the same
"read the structure, not the costume" move as
[Day 6](day06_function_guide.md)'s tree-in-disguise.

---

## Tests (what's pinned and why)

[test/day08-test.rkt](../../test/day08-test.rkt) pins five layers:

1. **Parser** — `"123456789012"` → the 12-digit vector, and `"120\n"`
   shows the trailing newline is trimmed, not parsed as a pixel.
2. **`image-layers` reshape** — the puzzle's own 3×2 example splits into
   `#(1 2 3 4 5 6)` and `#(7 8 9 0 1 2)`.
3. **Part 1 example** — on that 3×2 image layer 1 has zero `0`s (vs. layer
   2's one), so it wins; `#1s × #2s = 1 × 1 = 1`.
4. **Part 2 example** — the 2×2 `"0222112222120000"` decodes to
   `#(0 1 1 0)` (each pixel's first opaque value) and renders to the
   ` #` / `# ` checkerboard.
5. **Real answers** — 15 000 pixels (the 100-layer sanity check),
   `part1 = 1677`, and the full `part2` glyph block spelling **`UBUFP`**.

`raco test` runs the `module+ test` submodule; 9 checks, all green. Pinning
the rendered string (trailing spaces and all) is the only fiddly part — the
glyph block is fixed-width 25 columns per row, so the dark pixels on the
right edge are real spaces the test must include.

---

## Benchmarks

```
| Day | Parse (ms) | Part 1 (ms) | Part 2 (ms) | Total (ms) |
|-----|-----------|-------------|-------------|------------|
| 08  | 0.2815    | 0.4950      | 0.2480      | 1.0245     |
```

The mean is over **2000** iterations. What the row says:

- **Parse** scans 15 000 characters into a vector — a single linear pass,
  sub-millisecond.
- **Part 1** chunks 100 layers (100 `vector-copy`s of 150 elements) and
  histograms each twice over for zeros, then twice more on the winner —
  ~30 k element visits, the day's most expensive part but still under half
  a millisecond.
- **Part 2** resolves 150 pixels, each scanning down at most 100 layers
  until the first opaque value (usually far sooner), then renders 150
  characters. Cheaper than Part 1 because the early stop means most pixels
  resolve in the first layer or two.

All three are dominated by the 15 000-element linear scans; there's no
algorithmic depth to mine here — the whole day is **O(W·H·layers)**, which
is just "touch every pixel a constant number of times". That linearity is
itself the calibration note: a day whose total is ~1 ms is pure mechanics.

---

## If I were writing this in Rust

```rust
fn parse_input(s: &str) -> Vec<u8> {
    s.trim().bytes().map(|b| b - b'0').collect()
}

fn image_layers(digits: &[u8], w: usize, h: usize) -> impl Iterator<Item = &[u8]> {
    digits.chunks(w * h)
}

fn part1(digits: &[u8], w: usize, h: usize) -> usize {
    let count = |layer: &[u8], d: u8| layer.iter().filter(|&&x| x == d).count();
    let layer = image_layers(digits, w, h)
        .min_by_key(|l| count(l, 0))
        .unwrap();
    count(layer, 1) * count(layer, 2)
}

fn decode_image(digits: &[u8], w: usize, h: usize) -> Vec<u8> {
    let size = w * h;
    (0..size)
        .map(|p| digits[p..].iter().step_by(size).copied()
                            .find(|&x| x != 2).unwrap())
        .collect()
}
```

The correspondences worth seeing:

- **`slice::chunks` ↔ `image-layers`.** Rust hands you exactly this reshape
  as a standard-library iterator — `chunks(w*h)` *borrows* non-overlapping
  windows where the Racket `vector-copy` *allocates* fresh layers. The GC
  makes Racket's copies free to reason about; Rust's borrow makes them free
  to run.
- **`min_by_key` ↔ `argmin`.** Same "element minimizing a key" primitive,
  same first-on-tie rule.
- **`iter().step_by(size).find(…)` ↔ the inner `for/first`.** This is the
  prettiest correspondence: `digits[p..].step_by(size)` *is* "walk down the
  layer axis at pixel `p`" — the stride made literal — and `.find(|&x| x !=
  2)` is the first-opaque stop. Racket spells the stride as the explicit
  offset `(+ (* l size) p)`; Rust folds it into the iterator. Same
  row-major arithmetic, two notations.

The shape of the day is identical in both languages because it's all index
arithmetic and linear scans — no ownership puzzle, no lifetime friction,
the case where Rust and Racket read almost the same.

---

## What's next

**Day 9** completes the **Intcode trilogy**
([Day 5](day05_function_guide.md), [Day 7](day07_function_guide.md)):
the VM grows a **relative base** addressing mode and arbitrarily large
memory, finishing the machine that every later 2019 puzzle embeds. The
reshape skills banked today — flat-buffer-as-N-D-array, row-major strides —
return whenever AoC hands you a grid as a one-dimensional string. See the
[summary table](summary_2019.md) for the running scoreboard.
