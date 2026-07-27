#lang racket/base

;; Tests for Day 12 — The N-Body Problem.
;;
;; Pins:
;;   1. parse-input on the spec's first example scan,
;;   2. `step-axis` in isolation — one step of the x axis against the prose's
;;      own "After 1 step" table, plus the tie case (equal coordinates exert
;;      no pull) which the `sgn`-sum formulation handles silently and a
;;      hand-rolled comparison chain typically gets wrong,
;;   3. `simulate` after 10 steps on example 1 — the *exact* positions AND
;;      velocities, not just the energy they roll up to (energy is a lossy
;;      digest: two different states can share a total),
;;   4. Part 1's energy on both spec examples (179 after 10 steps, 1940
;;      after 100),
;;   5. `axis-period` per axis on example 1 (18 / 28 / 44) and the `lcm` that
;;      composes them into Part 2's 2772 — the per-axis periods are pinned
;;      separately from their lcm so a decomposition bug and a recombination
;;      bug can't cancel out,
;;   6. Part 2 on the second example, 4686774924 — the case that only a
;;      per-axis search can reach at all (a 6-D state-hash search would run
;;      for hours),
;;   7. the actual answers for inputs/day12.txt.
;;
;; Run with:  raco test test/day12-test.rkt

(require rackunit
         "../src/aoc.rkt"
         "../src/day12.rkt")

(module+ test

  ;; --- the spec's two example scans ---

  (define example1 "<x=-1, y=0, z=2>
<x=2, y=-10, z=-7>
<x=4, y=-8, z=8>
<x=3, y=5, z=-1>")

  (define example2 "<x=-8, y=-10, z=0>
<x=5, y=5, z=10>
<x=2, y=-7, z=3>
<x=9, y=-8, z=-3>")

  (define moons1 (parse-input example1))
  (define moons2 (parse-input example2))

  ;; --- parse-input ---

  (check-equal? moons1
                '((-1 0 2) (2 -10 -7) (4 -8 8) (3 5 -1))
                "pulls the three integers out of each <x=..,y=..,z=..> line")

  ;; --- step-axis: one axis, one step ---
  ;;
  ;; The x components of example 1 are (-1 2 4 3). The prose's "After 1
  ;; step" table gives x positions (2 3 1 2) and x velocities (3 1 -3 -1):
  ;; the moon at -1 is pulled +1 by each of the three moons above it, the
  ;; moon at 4 is pulled -1 by each of the three below it, and so on.
  (let-values ([(ps vs) (step-axis '(-1 2 4 3) '(0 0 0 0))])
    (check-equal? vs '(3 1 -3 -1) "gravity is the sum of the signed deltas")
    (check-equal? ps '(2 3 1 2) "positions then move by the NEW velocities"))

  ;; Ties exert no pull: two moons sharing a coordinate contribute 0 to each
  ;; other's velocity, so a pair that starts together and at rest never moves.
  (let-values ([(ps vs) (step-axis '(1 1) '(0 0))])
    (check-equal? vs '(0 0) "equal coordinates exert no gravity")
    (check-equal? ps '(1 1) "…so a resting tied pair is a fixed point"))

  ;; --- simulate: the full 3-D state after 10 steps of example 1 ---
  ;;
  ;; These are the four `pos=`/`vel=` rows the prose prints under "After 10
  ;; steps", and the same numbers its energy table breaks down
  ;; (pot 2+1+3=6, kin 3+2+1=6; pot 1+8+0=9, kin 1+1+3=5; …).
  (let-values ([(positions velocities) (simulate moons1 10)])
    (check-equal? positions
                  '((2 1 -3) (1 -8 0) (3 -6 1) (2 0 4))
                  "positions after 10 steps")
    (check-equal? velocities
                  '((-3 -2 1) (-1 1 3) (3 2 -3) (1 -1 -1))
                  "velocities after 10 steps"))

  ;; --- Part 1: total energy ---

  (check-equal? (part1 moons1 10) 179  "example 1: 179 after 10 steps")
  (check-equal? (part1 moons2 100) 1940 "example 2: 1940 after 100 steps")

  ;; --- Part 2: per-axis periods, then their lcm ---
  ;;
  ;; Pinned separately so a bug in the decomposition and a bug in the
  ;; recombination can't hide each other: lcm(18, 28, 44) = 2772.
  (check-equal? (axis-period '(-1 2 4 3))   18 "example 1, x axis")
  (check-equal? (axis-period '(0 -10 -8 5)) 28 "example 1, y axis")
  (check-equal? (axis-period '(2 -7 8 -1))  44 "example 1, z axis")
  (check-equal? (part2 moons1) 2772 "example 1 repeats after 2772 steps")

  ;; The second example is the one that makes the decomposition necessary
  ;; rather than merely tidy — 4.7 billion steps is out of reach for any
  ;; simulate-and-hash-the-6-D-state search, but its three axes repeat after
  ;; only a few thousand steps each.
  (check-equal? (part2 moons2) 4686774924 "example 2 repeats after 4686774924")

  ;; --- actual puzzle input ---
  (define moons (parse-input (read-day-input 12)))
  (check-equal? (part1 moons) 12351 "part 1 (total energy after 1000 steps)")
  (check-equal? (part2 moons) 380635029877596 "part 2 (first repeated state)"))
