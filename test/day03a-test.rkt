#lang racket/base

;; Tests for Day 03a — the trace-once Crossed Wires variant.
;;
;; The variant's whole contract is "faster, but observably identical to
;; src/day03.rkt." So these tests pin parity: day03a's `both-parts` must
;; agree with day03's independent `part1`/`part2` on every worked example
;; AND the real input.
;;
;; Run with:  raco test test/day03a-test.rkt

(require rackunit
         "../src/aoc.rkt"
         (prefix-in a:  "../src/day03a.rkt")
         (prefix-in d3: "../src/day03.rkt"))

(module+ test

  (define examples
    (list (cons "R8,U5,L5,D3" "U7,R6,D4,L4")
          (cons "R75,D30,R83,U83,L12,D49,R71,U7,L72"
                "U62,R66,U55,R34,D71,R55,D58,R83")
          (cons "R98,U47,R26,D63,R33,U87,L62,D20,R33,U53"
                "U98,R91,D20,R16,D67,R40,U7,R15,U6,R7")))

  ;; day03a reuses day03's parser; parse via day03 and feed both.
  (for ([ex (in-list examples)])
    (define w (d3:parse-input (string-append (car ex) "\n" (cdr ex))))
    (define-values (p1 p2) (a:both-parts w))
    (check-equal? p1 (d3:part1 w) "both-parts part1 matches idiomatic part1")
    (check-equal? p2 (d3:part2 w) "both-parts part2 matches idiomatic part2"))

  ;; --- parity on the real input, and the known answers ---
  (define input (d3:parse-input (read-day-input 3)))
  (define-values (rp1 rp2) (a:both-parts input))
  (check-equal? rp1 (d3:part1 input) "real input part1 parity")
  (check-equal? rp2 (d3:part2 input) "real input part2 parity")
  (check-equal? rp1 2180   "part 1")
  (check-equal? rp2 112316 "part 2"))
