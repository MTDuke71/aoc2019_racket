# Day 3 - Lists, Strings, and the Sequence Toolkit

Goal: read and use Racket's list type fluently, reach for `map` / `filter` / `foldl` instead of hand-rolled recursion, drive the `for/…` comprehension family over sequences, and convert between strings and lists — the exact moves every AoC input parser is built from.

Source files: src/lists.rkt, src/sequences.rkt

---

## 1. The list, and what it is *not*

A Racket list is a singly-linked chain of **cons cells** ending in the empty list `'()`. `'(3 1 4)` is `(cons 3 (cons 1 (cons 4 '())))`. This is the **Haskell `[a]` model**, not a Rust `Vec<T>`.

| Operation | List (`'(…)`) | Cost | Rust analogue |
|-----------|---------------|------|---------------|
| prepend | `(cons x xs)` | **O(1)** | `VecDeque::push_front` |
| head / tail | `(first xs)` / `(rest xs)` | O(1) | `slice::split_first` |
| index | `(list-ref xs i)` | **O(n)** | (so *don't* — use a vector) |
| length | `(length xs)` | O(n) | — |
| append | `(append xs ys)` | O(len xs) | — |

The single most important consequence: **a list streams cheaply front-to-back and prepends cheaply, but random indexing is linear.** When a puzzle indexes by position (Intcode memory, grids), you'll switch to a `vector` (Day 7). Until then, lists are the default container and `cons`/`first`/`rest` are your `car`/`cdr` vocabulary.

- `'()` is the empty list. Recall from Day 2 that it is **truthy** — `(if '() 'yes 'no)` is `'yes`. Test emptiness with `(empty? xs)` or `(null? xs)`, never by leaning on truthiness.
- The leading quote in `'(3 1 4)` means "don't evaluate this as a function call — it's literal data." Without it, `(3 1 4)` would try to call `3` as a function. (Day 4 leans on `quote` harder; here just read it as "list literal.")

---

## 2. The toolkit: map, filter, foldl

These three replace almost every explicit recursion you'd write by hand. They are the heart of `src/lists.rkt`.

```racket
(define (doubled xs)  (map (lambda (x) (* 2 x)) xs))   ; transform each
(define (evens xs)    (filter even? xs))               ; keep some
(define (sum-list xs) (foldl + 0 xs))                  ; reduce to one
```

| Racket | Rust iterator | Haskell |
|--------|---------------|---------|
| `(map f xs)` | `xs.iter().map(f).collect()` | `map f xs` |
| `(filter p xs)` | `xs.iter().filter(p).collect()` | `filter p xs` |
| `(foldl f init xs)` | `xs.iter().fold(init, f)` | `foldl' f init xs` ⚠ arg order |

`lambda` is the anonymous-function form (full treatment Day 6); here read `(lambda (x) (* 2 x))` as Rust's `|x| 2 * x`. Predicate names like `even?` end in `?` by convention.

### The one trap: `foldl`'s argument order

Racket's combining function takes **`(element accumulator)` — accumulator LAST**. Haskell's `foldl` takes the accumulator **first**. So the direct translation of a Haskell fold has its two arguments swapped:

```racket
(foldl + 0 '(3 1 4))        ; 8   -- + is symmetric, so order doesn't bite here
(foldl cons '() '(1 2 3))   ; '(3 2 1)  -- REVERSES: acc threads through cons
```

That second line is the canonical "gotcha" demo: `foldl cons '()` reverses the list, because each step does `(cons element acc)` and the accumulator grows on the front. If you came from Haskell expecting `foldl (flip (:)) []` to reverse, note Racket already put the accumulator where `flip` would: no `flip` needed.

> `foldr` exists too and folds right-to-left, with the *same* `(element accumulator)` order. `foldl` is tail-recursive and the one to default to; reach for `foldr` only when the operation is genuinely right-associative.

---

## 3. Walkthrough of `src/lists.rkt`

Run it:

```powershell
cd tutorial/day3
racket src/lists.rkt
```

Verified output:

```
xs                  = (3 1 4 1 5 9 2 6)
(first xs)          = 3
(rest xs)           = (1 4 1 5 9 2 6)
(length xs)         = 8
(list-ref xs 2)     = 4
(cons 0 xs)         = (0 3 1 4 1 5 9 2 6)
(append xs '(0 0))  = (3 1 4 1 5 9 2 6 0 0)
(reverse xs)        = (6 2 9 5 1 4 1 3)
(member 4 xs)       = (4 1 5 9 2 6)
(sum-list xs)       = 31
(evens xs)          = (4 2 6)
(doubled xs)        = (6 2 8 2 10 18 4 12)
(parse-and-sum ...) = 46
```

Two lines worth pausing on:

- **`(member 4 xs)` returns `(4 1 5 9 2 6)`, not `#t`.** `member` returns the *tail of the list starting at the match*, or `#f` if absent. Because every non-`#f` value is truthy (Day 2), this still works perfectly in a conditional — `(if (member 4 xs) …)` does the right thing — but the *value* is the matched suffix, which is occasionally useful in its own right. This is a recurring Racket idiom: "find" operations return the found thing (or `#f`), not a bare boolean.
- **`parse-and-sum` is a parser in miniature.** It's the shape of every AoC day's front end:

```racket
(define (parse-and-sum line)
  (sum-list (map string->number (string-split line))))
```

Read inside-out: `(string-split line)` cuts `"1 2 3 40"` on whitespace into `'("1" "2" "3" "40")`; `(map string->number …)` parses each token to `'(1 2 3 40)`; `sum-list` folds them to `46`. Raw text → list of strings → list of numbers → answer. Hold onto this pipeline; Day 8 ("parsing puzzle text") is this idea scaled up.

---

## 4. The `for` sequence toolkit (src/sequences.rkt)

`map`/`filter`/`foldl` are great for one transform over one list. But AoC code constantly needs *ranges*, *parallel iteration*, *guards*, and *multiple accumulators at once* — and that's where Racket's `for/…` family earns its keep. The mental model that matters:

> A `for/…` form is **not a C loop**. It is an **expression that builds a value** by walking one or more **sequences**. The suffix picks what it builds.

| Form | Builds | Rust finisher | Haskell |
|------|--------|---------------|---------|
| `for/list` | a list | `.collect::<Vec<_>>()` | list comprehension |
| `for/sum` | the sum | `.sum()` | `sum [ … ]` |
| `for/fold` | whatever you accumulate | `.fold(init, …)` | `foldl'` |
| `for` | nothing (`void`) — side effects only | a plain `for` loop | `mapM_` |

A **sequence** is the thing being walked. The common generators:

- `(in-range 5)` → `0 1 2 3 4`; `(in-range 1 6)` → `1 2 3 4 5`.
- `(in-list xs)` / `(in-string s)` — walk a list's elements / a string's chars.
- `(in-naturals)` — the infinite `0 1 2 …` stream (safe to zip against a finite sequence).

> A bare list also works as a sequence — `([x '(1 2 3)])` iterates it directly. The explicit `(in-list xs)` / `(in-range …)` wrappers are faster (the compiler specializes them) and clearer about intent, so the guides prefer them. The bare-list form shows up below only to keep the demos short.

Run the demos:

```powershell
cd tutorial/day3
racket src/sequences.rkt
```

Verified output:

```
for/list and ranges
  (for/list ([i (in-range 5)]) (* i i)) => (0 1 4 9 16)
  (for/list ([i (in-range 1 6)] #:when (odd? i)) i) => (1 3 5)
  (for/sum ([i (in-range 1 101)]) i) => 5050

for/fold
  (for/fold ([acc 0]) ([x '(3 1 4 1 5)]) (+ acc x)) => 14
  (for/fold ([acc '()]) ([x '(1 2 3)]) (cons x acc)) => (3 2 1)

strings as data
  (string->list "abc") => (a b c)
  (list->string (list #\h #\i)) => hi
  (string-split "1 2 3") => (1 2 3)
  (map string->number (string-split "1 2 3")) => (1 2 3)
  (for/sum ([c (in-string "12345")]) (- (char->integer c) 48)) => 15

parallel sequences
  (for/list ([x '(1 2 3)] [y '(10 20 30)]) (+ x y)) => (11 22 33)
  (for/list ([i (in-naturals)] [c (in-string "abc")]) (list i c)) => ((0 a) (1 b) (2 c))
```

### 4a. Comprehensions and `#:when`

```racket
(for/list ([i (in-range 5)]) (* i i))                ; => (0 1 4 9 16)
(for/list ([i (in-range 1 6)] #:when (odd? i)) i)    ; => (1 3 5)
(for/sum  ([i (in-range 1 101)]) i)                  ; => 5050
```

`#:when p` is the comprehension **guard** — Haskell's `| p` in `[ … | x <- xs, p x ]`, Rust's `.filter()` mid-chain. The Gauss sum `1..=100 = 5050` is `for/sum` finishing the same walk `for/list` would.

### 4b. `for/fold` — the general reducer

`for/fold` is the one that generalizes all the others. You name the accumulator(s) and their seed(s); the body's value becomes the next accumulator:

```racket
(for/fold ([acc 0]) ([x '(3 1 4 1 5)]) (+ acc x))    ; => 14  (a sum, by hand)
(for/fold ([acc '()]) ([x '(1 2 3)]) (cons x acc))   ; => (3 2 1)  (reverse, again)
```

Note the accumulator order is the *natural* one here — `(+ acc x)`, `(cons x acc)` — because **you** write the body, unlike `foldl` where the *function's* parameter order is fixed. When a fold needs two running values (a min and a max, a count and a sum), `for/fold` takes two accumulator clauses and returns two values — the place `foldl` gets awkward and `for/fold` stays clean. Day 6 goes deep on this.

### 4c. Strings ↔ lists ↔ numbers

This block is the parsing vocabulary, and it's load-bearing for every day after this:

```racket
(string->list "abc")                                 ; => '(#\a #\b #\c)
(list->string (list #\h #\i))                        ; => "hi"
(string-split "1 2 3")                               ; => '("1" "2" "3")
(map string->number (string-split "1 2 3"))          ; => '(1 2 3)
(for/sum ([c (in-string "12345")]) (- (char->integer c) 48))  ; => 15
```

- **`string->list` / `list->string`** are the bridge Day 2 promised: a string is *not* a list of chars (unlike Haskell's `String = [Char]`), so you cross explicitly.
- **`string-split`** with no separator splits on runs of whitespace — the everyday line tokenizer. (It takes an optional separator: `(string-split "1,2,3" ",")`.)
- **`string->number`** parses; it returns `#f`, not an error, on a non-number — so on dirty input you'd guard or `filter` before summing.
- **The last line is the digit-sum kernel.** `(char->integer c)` gives a char's codepoint; subtracting `48` (the codepoint of `#\0`) maps `#\0…#\9` to `0…9`. Summing those over `"12345"` gives `15`. That `char - '0'` trick is identical in Rust and C, and it's the exact move the **Day 12 capstone** (Inverse Captcha / digit work) is built on. (`(char->integer #\0)` is `48`; using the literal keeps the demo self-contained, but `(- (char->integer c) (char->integer #\0))` is the self-documenting form.)

> **Why does `string->list "abc"` print as `(a b c)` and not `(#\a #\b #\c)`?** Same reason as Day 2: the demo uses `~a` (display style), which shows a char as just its glyph. The *value* really is a list of three char objects; `~v`/`~s` (write style) would print `(#\a #\b #\c)`. Same goes for `string-split` printing `(1 2 3)` — those are still strings, not numbers; the next line actually converts them.

### 4d. Parallel sequences — the `zip`

A `for` clause list can name **more than one sequence**. They advance in lockstep and **stop at the shortest** — this is Rust's `.zip()` / Haskell's `zipWith`:

```racket
(for/list ([x '(1 2 3)] [y '(10 20 30)]) (+ x y))            ; => (11 22 33)
(for/list ([i (in-naturals)] [c (in-string "abc")]) (list i c))  ; => ((0 a) (1 b) (2 c))
```

The second line is the idiomatic **"enumerate"**: zip `(in-naturals)` against any finite sequence to get `(index, element)` pairs without an index variable you mutate. The infinite stream is safe precisely because the finite `"abc"` ends the walk — Rust's `.enumerate()`, spelled out.

---

## 5. Try it

In the REPL (`racket`, then `(require "src/lists.rkt")`), or by editing and re-running:

1. Predict, then check: `(foldl - 0 '(1 2 3))`. Does it compute `0-1-2-3` or `3-2-1-0` or something else? Trace the `(element accumulator)` order by hand before running. (This is the arg-order lesson with a *non-symmetric* operator, where it actually bites.)
2. Write `(count-evens xs)` two ways: once as `(length (filter even? xs))`, once as a single `for/sum` with `#:when`. Confirm they agree on `'(3 1 4 1 5 9 2 6)`.
3. Rewrite `parse-and-sum` to find the **maximum** token instead of the sum. (`apply max` over the parsed list, or a `for/fold` with one accumulator — try both.)
4. Evaluate `(for/list ([i (in-range 1 4)] [j '(a b c d e)]) (list i j))`. How many pairs come out, and why? (The shortest-sequence rule.)
5. Build the digit list of `12345` as exact integers — `(for/list ([c (in-string "12345")]) (- (char->integer c) (char->integer #\0)))`. Confirm you get `'(1 2 3 4 5)`, then sum it to re-derive `15`.
6. Call `(string->number "12x")` and `(string->number "")`. Note that both give `#f`, not an error — and reason about what `(map string->number (string-split "1 x 3"))` would then hand to `sum-list`. (Foreshadows defensive parsing on Day 8.)

---

## 6. What to remember

- **List = singly-linked cons cells**, Haskell `[a]` not Rust `Vec`. `cons`/`first`/`rest` are O(1); `list-ref`/`length` are O(n). Switch to a `vector` (Day 7) when you index by position.
- **`map` / `filter` / `foldl`** replace hand-written recursion. `foldl`'s combiner is **`(element accumulator)` — accumulator LAST**, the opposite of Haskell; `(foldl cons '() xs)` reverses.
- **`for/…` forms are value-building expressions over sequences**, not C loops. `for/list` collects, `for/sum` sums, `for/fold` reduces with named accumulators, bare `for` is side-effects-only.
- **`in-range` / `in-list` / `in-string` / `in-naturals`** are the sequence generators; `#:when` is the comprehension guard; multiple clauses **zip** and stop at the shortest.
- **`string-split` → `map string->number`** is the canonical token-parse pipeline; `string->list`/`list->string` bridge the string/char-list gap; `string->number` returns `#f` (not an error) on junk.
- **`(- (char->integer c) (char->integer #\0))`** is the digit-extraction kernel — the same `char - '0'` you know from Rust/C — and it's exactly what the Day 12 capstone needs.

---

Next: Day 4 — conditionals and `match`, dispatching on structure instead of nesting `if`/`cond`.
