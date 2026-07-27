#lang racket

;; AoC 2019 Day 12 — The N-Body Problem.
;;
;; Intcode steps aside again (last seen [Day 11](day11_function_guide.md))
;; for a discrete physics simulation: four moons, each with a 3-D position
;; and velocity. Every time step, gravity nudges each velocity component by
;; ±1 toward every other moon, then every position moves by its velocity.
;;
;; The whole day turns on one observation, and both parts fall out of it:
;;
;;   * **The three axes never interact.** Gravity on the x components is a
;;     function of the x components alone; likewise y and z. So this isn't
;;     one 6-D simulation of 4 moons — it's *three independent 2-D
;;     simulations* of 4 scalars each, and the only place the axes ever meet
;;     is the energy formula at the end.
;;
;;   * **Part 1** (total energy after 1000 steps) therefore runs the same
;;     one-dimensional kernel three times and zips the results back together.
;;
;;   * **Part 2** (first repeat of the *entire* state) would be hopeless as a
;;     6-D state-hash search — the answer is in the hundreds of billions —
;;     but per axis the period is only a few hundred thousand steps. The
;;     system repeats exactly when all three axes are simultaneously back at
;;     their start, so the answer is `lcm` of the three periods. This is the
;;     Chinese-Remainder-flavored "decompose, solve small, recombine" move.
;;
;; Two facts make the period search itself sound, both argued in the guide:
;; the step map is a **bijection** on (positions, velocities), so the orbit
;; is a pure cycle with no lead-in tail — the first repeated state must be
;; the *initial* one, so we can compare against the start instead of hashing
;; every state we've seen. And the periods are per-axis, so `lcm` composes
;; them without ever materializing the global cycle.
;;
;; New Racket this day: `regexp-match*` for parsing, multiple return values
;; (`values` / `define-values` / a two-accumulator `for/fold`), `for/lists`,
;; the `(apply map list ...)` transpose idiom, and `sgn`.

(require "aoc.rkt")

;; Contracts are ordinary values, so naming the two recurring shapes once
;; keeps the `contract-out` block readable. A `moon` is an (x y z) triple;
;; an `axis` is one scalar component collected across all the moons.
(define moons/c (listof (list/c exact-integer? exact-integer? exact-integer?)))
(define axis/c  (listof exact-integer?))

(provide
 (contract-out
  [parse-input  (-> string? moons/c)]
  [step-axis    (-> axis/c axis/c (values axis/c axis/c))]
  [simulate     (-> moons/c exact-nonnegative-integer? (values moons/c moons/c))]
  [total-energy (-> moons/c moons/c exact-nonnegative-integer?)]
  [axis-period  (-> axis/c exact-positive-integer?)]
  [part1        (->* (moons/c) (exact-nonnegative-integer?) exact-nonnegative-integer?)]
  [part2        (-> moons/c exact-positive-integer?)]
  [solve        (-> string? void?)]))

;; Input lines look like `<x=3, y=3, z=0>`. Rather than pick the format
;; apart, pull every integer literal out of the line and trust their order:
;; `regexp-match*` returns *all* matches as a list of strings (where
;; `regexp-match` returns just the first, with its capture groups). The
;; `#px` prefix selects perl-compatible syntax; `-?[0-9]+` is "optional
;; minus sign, then digits". Rust analogue: `Regex::find_iter`, or the
;; `split(|c: char| !c.is_ascii_digit() && c != '-')` hack.
(define (parse-input s)
  (for/list ([line (in-list (string-split (string-trim s) "\n"))])
    (map string->number (regexp-match* #px"-?[0-9]+" line))))

;; Transpose a list of rows into a list of columns. `(apply map list xss)`
;; hands each row to `map` as a separate argument, and `map` walks all of
;; them in lockstep collecting one `list` per column — Racket's `zip*`.
;;
;; This is the axis-decomposition seam, and it runs *both* ways: applied to
;; the moons `((x1 y1 z1) (x2 y2 z2) ...)` it yields the three per-axis
;; lists `((x1 x2 ...) (y1 y2 ...) (z1 z2 ...))`; applied to those results
;; it zips them back into per-moon triples.
(define (transpose xss) (apply map list xss))

;; Gravity on one moon along one axis: every moon at a greater coordinate
;; pulls +1, every lesser one −1, ties contribute 0. That is exactly the sum
;; of `sgn` over the differences — and because `(sgn 0)` is `0`, the moon's
;; own term vanishes and there's no need to exclude it from the sum.
(define (gravity ps p)
  (for/sum ([q (in-list ps)]) (sgn (- q p))))

;; One time step of one axis, returning the new positions and velocities as
;; two values. The puzzle's "update ALL velocities first, THEN all
;; positions" ordering is enforced structurally rather than by discipline:
;; `vs*` is computed from the *old* `ps`, and `ps*` from the *new* `vs*`.
;;
;; `values` returns multiple results at once (Rust's tuple return, without
;; the tuple allocation); callers unpack with `define-values`/`let-values`.
(define (step-axis ps vs)
  (define vs* (for/list ([p (in-list ps)] [v (in-list vs)]) (+ v (gravity ps p))))
  (define ps* (for/list ([p (in-list ps)] [v (in-list vs*)]) (+ p v)))
  (values ps* vs*))

;; `steps` time steps of one axis. `for/fold` with two accumulators expects
;; its body to produce two values — `step-axis` already does, so the fold
;; body is a single call and the loop carries (ps, vs) forward with no
;; intermediate unpacking.
(define (simulate-axis ps vs steps)
  (for/fold ([ps ps] [vs vs]) ([_ (in-range steps)])
    (step-axis ps vs)))

;; `steps` time steps of the whole system, returned as per-moon (x y z)
;; position and velocity triples. Decompose into axes, run each one
;; independently, recompose.
;;
;; `for/lists` is `for/list`'s multiple-accumulator sibling: the body
;; returns two values per iteration and it collects two parallel lists —
;; here the final positions and velocities of each of the three axes.
(define (simulate moons steps)
  (define vs0 (map (λ (_) 0) moons))
  (define-values (pss vss)
    (for/lists (pss vss) ([ps (in-list (transpose moons))])
      (simulate-axis ps vs0 steps)))
  (values (transpose pss) (transpose vss)))

;; ℓ¹ norm — the sum of absolute values. The puzzle calls it potential
;; energy for a position and kinetic energy for a velocity; it is the same
;; function both times.
(define (norm1 xs) (for/sum ([x (in-list xs)]) (abs x)))

;; Total energy: per moon, potential × kinetic, summed. This is the ONLY
;; place the three axes are ever combined — the simulation itself never
;; needs them together.
(define (total-energy positions velocities)
  (for/sum ([p (in-list positions)] [v (in-list velocities)])
    (* (norm1 p) (norm1 v))))

(define (part1 moons [steps 1000])
  (define-values (positions velocities) (simulate moons steps))
  (total-energy positions velocities))

;; The number of steps before one axis returns to its starting state.
;;
;; Why comparing against the *start* is enough (rather than remembering
;; every state seen, Floyd-style): the step map is invertible — from
;; (ps*, vs*) you recover `vs*` directly, `ps = ps* − vs*`, and then
;; `vs = vs* − gravity(ps)`. An injective map on a reachable orbit cannot
;; have two states feeding into one, so the orbit is a pure cycle with no
;; ρ-shaped tail, and the first repeated state is necessarily the initial
;; one. See the function guide for the full argument.
(define (axis-period ps0)
  (define vs0 (map (λ (_) 0) ps0))
  (let loop ([ps ps0] [vs vs0] [n 1])
    (define-values (ps* vs*) (step-axis ps vs))
    (if (and (equal? ps* ps0) (equal? vs* vs0))
        n
        (loop ps* vs* (add1 n)))))

;; The whole system repeats exactly when all three axes are simultaneously
;; back at their start — the multiples common to all three periods — so the
;; first such time is their least common multiple. `lcm` is variadic and
;; exact, so bignum answers (this one is ~3×10¹¹) cost nothing extra.
(define (part2 moons)
  (apply lcm (map axis-period (transpose moons))))

;; Dispatcher: parse once, print both parts. Mirrors Days 1–11.
(define (solve contents)
  (define moons (parse-input contents))
  (printf "  part 1: ~a\n" (part1 moons))
  (printf "  part 2: ~a\n" (part2 moons)))

(module+ main
  (solve (read-day-input 12)))
