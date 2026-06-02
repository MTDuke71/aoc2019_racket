# Day 2 - Values, Bindings, and Functions

Goal: know Racket's basic value types by name, write pure functions with `define`, read prefix notation fluently, and understand the one numeric distinction Racket actually makes you track (exact vs inexact).

Source files: src/values.rkt, src/numbers.rkt

---

## 1. The basic value types

Racket gives you these primitive value kinds. You will read them in every puzzle from here on. Unlike Haskell, you rarely *write* the type down — but you still need to recognize each literal on sight.

| Kind | What it is | Literal example | Rust analogue |
|------|------------|-----------------|---------------|
| exact integer | Arbitrary-precision signed integer. Never overflows. | `42`, `(expt 2 100)` | `num_bigint::BigInt` (but it's the *default*) |
| exact rational | Ratio of two integers, kept exact. | `1/3` | no direct analogue |
| inexact (flonum) | 64-bit IEEE 754 float. | `3.14`, `1.0` | `f64` |
| boolean | `#t` or `#f`. | `#t` | `bool` |
| character | One Unicode codepoint. | `#\A` | `char` |
| string | Immutable sequence of characters. | `"hello"` | `String` / `&str` |
| symbol | Interned name, compared by identity. (You'll just *recognize* these today — Day 4 uses them in earnest.) | `'foo` | no clean analogue (think interned `&'static str` / enum tag) |

Things to internalize up front:

- **There is no `Int` vs `Integer` choice.** Integer math is exact and arbitrary-precision by default. `(expt 2 100)` just *works* and stays an integer. The distinction Racket makes you track instead is **exact vs inexact** — see section 7.
- **`#t` / `#f`, and only `#f` is false.** This is the big one coming from Rust or C. In a conditional, *every* value except `#f` is true — `0` is true, `""` is true, `'()` (the empty list) is true. There is no "falsy zero."
- **Strings are not lists of chars.** Unlike Haskell's `String = [Char]`, a Racket string is its own type. List operations do not work on it directly; you convert with `string->list` when you need to (Day 3).
- **Symbols are new.** `'foo` is an interned name. Two `'foo`s are `eq?` (pointer-equal). They're the cheap, allocation-free tags you'll reach for as enum-like markers — closer to a Rust unit enum variant than to a string.

---

## 2. Declaring a value

A top-level **binding** is one form:

```racket
(define answer 42)
```

Read it as: "*define* `answer` to be `42`." That's it. Compare the Haskell, which is two lines (a signature then a body):

```haskell
answer :: Int
answer = 42
```

Racket has no separate signature line. The same `define` binds values of any kind:

```racket
(define ready    #t)
(define letter-a #\A)
(define motto    "Values first, parens always.")
```

What is *not* happening here:

- **One keyword for everything.** No `let` / `var` / `const` distinction at top level — just `define`. (`let` exists, but it's for *local* bindings inside a body; Day 6.)
- **No reassignment by default.** You don't write `(define answer 43)` later. Racket *does* have `set!` for mutation — unlike Haskell, it's right there — but idiomatic Racket avoids it, and these tutorials stay functional until a puzzle earns the mutation (the 2018 Haskell repo waited until Day 9 for `STUArray`; we'll do the same with Racket `vector`s).
- **Hyphens in names are normal.** `pi-approx`, `letter-a` — `kebab-case` is the Racket convention, not `snake_case` or `camelCase`. The hyphen is a legal identifier character because there are no infix operators to confuse it with (see section 4).

---

## 3. Defining a function

A function is a `define` whose head is a parenthesized *(name . parameters)* list:

```racket
(define (square x) (* x x))
```

Read it: "*define* `square` of `x` to be `(* x x)`." No `return`, no braces — the body is a single expression and its value is what the function returns.

One function can call another exactly the way you'd expect:

```racket
(define (cube x) (* x (square x)))
```

`(square x)` evaluates first and its result is multiplied by `x`. There's no precedence question to worry about here — and that's the whole point of section 4.

This is also where Day 1's contracts come back. The source file exports each function with a contract, the runtime-checked analogue of a Haskell signature:

```racket
(provide
 (contract-out
  [square   (-> exact-integer? exact-integer?)]
  [hypot    (-> real? real? real?)]
  [shout    (-> string? string?)]))
```

`(-> exact-integer? exact-integer?)` reads "takes one exact integer, returns one exact integer" — the same shape as Haskell's `square :: Int -> Int`, but enforced when the value crosses the module boundary at *run time* rather than proven at compile time. (Day 1, section 4 has the boundary-behavior detail.)

---

## 4. Prefix notation: the thing that feels alien first

Every operation is a parenthesized list with the operator in **front**:

```racket
(+ 1 2)            ; 3
(* 3 4 5)          ; 60   -- + and * take any number of arguments
(< 1 2 3)          ; #t   -- so does <: "is this strictly increasing?"
(sqrt (+ (* a a) (* b b)))
```

There are no infix operators and **no precedence rules to memorize**, because the parentheses already say exactly what groups with what. This is the mirror image of Day 1 of the Haskell tutorial, where the surprise was the *absence* of parentheses (`f x`, currying, `->` associating right). Racket goes the other way: parentheses everywhere, applied uniformly.

Consequences worth noting:

- **`+`, `*`, `<`, `=` are just functions.** `(+ 1 2 3)` works because `+` is variadic. `(< 1 2 3)` is a chained comparison. There's nothing special about them syntactically — they're names in the function position.
- **No currying, no partial application by writing fewer arguments.** In Haskell `hypot 3` is a valid partially-applied function. In Racket `(hypot 3)` is an *error* — wrong number of arguments. When you want the "fill in some arguments" behavior, you ask for it explicitly with `curry` or a `lambda` (Day 6); it isn't the default.
- **Equality has a family.** `=` is for numbers. `eq?` is pointer identity (use for symbols). `equal?` is structural/deep equality (use for strings, lists). `(= 2 2.0)` is `#t`; `(equal? 2 2.0)` is `#f`. Reach for `equal?` when in doubt about non-numbers.

The "any function used infix" trick from Haskell (backticks: `` n `mod` 2 ``) has no Racket equivalent and needs none — you just write `(modulo n 2)` and the prefix form *is* the normal form.

```racket
(define (my-even? n) (= (remainder n 2) 0))
```

Read left to right by nesting: take `(remainder n 2)`, then ask `(= … 0)`. (`even?` is built in; this is the manual version so you can see the shape. Predicate names conventionally end in `?`.)

---

## 5. Reading definitions, revisited

You now have enough to read everything in the source file out loud:

```racket
(define (square x) (* x x))
;; square of x is x times x.

(define (hypot a b) (sqrt (+ (* a a) (* b b))))
;; hypot of a and b is the square root of (a*a + b*b).

(define (my-even? n) (= (remainder n 2) 0))
;; my-even? of n is: does n remainder 2 equal 0?

(define (shout s) (string-append s "!!!"))
;; shout of s is s with "!!!" appended.
```

`string-append` is the string concatenator — the counterpart to Haskell's `++` on `String`, except it's a named function (strings aren't lists here, so list `++` wouldn't apply).

---

## 6. Walkthrough of `values.rkt`

The file defines six values and five functions, then a `main` submodule that prints them. The pieces worth calling out:

```racket
(define bignum (expt 2 100))
```

`expt` is exponentiation. The result is `1267650600228229401496703205376` — a full bignum, with **no type change and no overflow**. Where Haskell forced `bignum :: Integer` to avoid `Int` wraparound, Racket just gives you the exact answer. This is the single most freeing difference for AoC arithmetic puzzles.

```racket
(define (hypot a b) (sqrt (+ (* a a) (* b b))))
```

Note the result of `(hypot 3 4)` in the output below: it prints `5`, not `5.0`. `(sqrt 25)` is `5` exactly because `25` is an exact perfect square — `sqrt` returns an exact result when it can. `(sqrt 2)` would give an inexact `1.4142135623730951`. That's the exact/inexact tower at work; section 7.

```racket
(module+ main
  (printf "answer     = ~a\n" answer)
  ...)
```

`printf` with `~a` is the display-style placeholder you met on Day 1 (`format`'s sibling). One thing to notice in the output: `letter-a` prints as `A`, not `#\A`, because `~a` shows the *display* form. Use `~v` (or `~s`) if you want the literal `#\A` representation back.

Run it:

```powershell
cd tutorial/day2
racket src/values.rkt
```

Expected output:

```
answer     = 42
bignum     = 1267650600228229401496703205376
pi-approx  = 3.141592653589793
ready      = #t
letter-a   = A
motto      = Values first, parens always.
square 7   = 49
cube 3     = 27
hypot 3 4  = 5
my-even? 10 = #t
Day 2 complete!!!
```

Or load it in the REPL and poke at individual bindings (this is the GHCi analogue):

```powershell
cd tutorial/day2
racket
```

```racket
(require "src/values.rkt")
(square 12)        ; 144
(hypot 5 12)       ; 13
(my-even? 7)       ; #f
(exit)
```

(Only the contracted exports — `square`, `cube`, `hypot`, `my-even?`, `shout` — are visible after `require`. The bare `define`d values aren't `provide`d, so they stay private to the module.)

---

## 7. The exact/inexact tower (src/numbers.rkt)

This is the Racket-specific concept that replaces Haskell's `Int` vs `Integer`. It deserves its own runnable file. Run it:

```powershell
cd tutorial/day2
racket src/numbers.rkt
```

Verified output:

```
exactness
  (expt 2 100)         => 1267650600228229401496703205376
  (/ 1 3)              => 1/3
  (/ 1.0 3)            => 0.3333333333333333
  (+ 1/3 1/6)          => 1/2
  (exact? (/ 1 3))     => #t
  (exact? 1.0)         => #f

crossing the line
  (exact->inexact 1/3) => 0.3333333333333333
  (inexact->exact 0.5) => 1/2
  (sqrt 25)            => 5
  (sqrt 2)             => 1.4142135623730951
  (* 2 3.0)            => 6.0

truthiness
  (if 0 'yes 'no)      => yes
  (if "" 'yes 'no)     => yes
  (if '() 'yes 'no)    => yes
  (if #f 'yes 'no)     => no
```

The takeaways, in order:

1. **Integer division of exacts stays exact and rational.** `(/ 1 3)` is `1/3`, a real value you can keep computing with — `(+ 1/3 1/6)` is `1/2`, no rounding. This is unlike almost every other language you've touched, where `1/3` either truncates to `0` (C/Rust integer division) or floats to `0.333…`.
2. **A literal with a decimal point is inexact, and inexactness is contagious.** `(/ 1.0 3)` floats. `(* 2 3.0)` is `6.0` — one inexact argument drags the whole result inexact. Mixing `1.0` into an otherwise-exact computation silently converts it.
3. **`exact?` / `inexact?` are the predicates; `exact->inexact` / `inexact->exact` are the bridges.** `(inexact->exact 0.5)` recovers `1/2` exactly (0.5 is representable); most floats won't round-trip so cleanly.
4. **`sqrt` returns exact when it can** (`(sqrt 25)` → `5`) and inexact otherwise (`(sqrt 2)`). Same for many numeric ops.
5. **Truthiness: `#f` is the lone false value.** `(if 0 …)`, `(if "" …)`, `(if '() …)` all take the *true* branch. Coming from Rust/C this is the one that bites — there is no "zero is false." Test for emptiness or zero *explicitly* (`(= n 0)`, `(empty? xs)`), never by leaning on truthiness.

**Practical AoC rule:** stay in exact integers/rationals for puzzle math (you get bignums and exact ratios for free), and only convert to inexact at the edges when a problem genuinely wants floating point. Most 2019 puzzles never need a flonum.

---

## 8. Try it

In the REPL with `src/values.rkt` loaded (`(require "src/values.rkt")`), or by editing the file and re-running:

1. Evaluate `(expt 2 1000)`. Confirm you get a 300-ish-digit integer with no overflow and no type annotation needed. (This is the `Int`/`Integer` lesson — except there's nothing to learn, it just works.)
2. Evaluate `(/ 10 4)`, then `(/ 10.0 4)`, then `(exact->inexact (/ 10 4))`. Read each result and say whether it's exact or inexact before you check with `(exact? …)`.
3. Predict the output of `(if "" 'yes 'no)` and `(if 0 'yes 'no)` before running them. If you guessed `'no` for either, reread section 7 point 5.
4. Add a function `average` that returns the arithmetic mean of two numbers, with contract `(-> real? real? real?)`. Test `(average 3 4)` — note whether you get `7/2` or `3.5`, and why.
5. Add `my-odd?` *without* repeating the `remainder` trick — define it in terms of `my-even?` and `not`.
6. Try to call `(hypot 3)` with one argument. Read the error. (This is the no-currying lesson: Racket wants all the arguments, every time.)

---

## 9. What to remember

- **Seven value kinds**: exact integer, exact rational, inexact float, boolean, char, string, symbol. You read the literals; you rarely write a type.
- **No `Int` vs `Integer`** — integers are exact and arbitrary-precision by default. The distinction you track is **exact vs inexact**, and inexactness is contagious.
- **One binding keyword**: `define`, for both values and functions. No reassignment in idiomatic code (though `set!` exists).
- **Prefix, uniform, no precedence**: `(f a b)`. Operators are just variadic functions. No currying — pass every argument.
- **`#f` is the only false value.** `0`, `""`, `'()` are all true. Test emptiness/zero explicitly.
- **Equality family**: `=` (numbers), `eq?` (identity/symbols), `equal?` (structural/strings/lists).
- **Contracts continue from Day 1** as the signature-shaped guardrail: `(-> dom? rng?)`, checked at the module boundary.

---

Next: Day 3 — lists, strings, and the map/filter/fold sequence toolkit.
