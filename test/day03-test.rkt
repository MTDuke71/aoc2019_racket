#lang racket/base

;; Tests for Day 03 — Crossed Wires.
;;
;; Pins:
;;   1. the path parser (token -> (dir . dist), two-line split, CRLF),
;;   2. `trace`'s first-arrival bookkeeping on a hand-checkable wire,
;;   3. all three worked examples from the puzzle text — for BOTH parts,
;;      since Part 1 (Manhattan) and Part 2 (combined steps) have
;;      different published answers per example,
;;   4. the actual answers for inputs/day03.txt.
;;
;; Run with:  raco test test/day03-test.rkt

(require rackunit
         "../src/aoc.rkt"
         "../src/day03.rkt")

(module+ test

  ;; --- parser ---
  (check-equal? (parse-input "R8,U5\nL5,D3")
                (list (list (cons #\R 8) (cons #\U 5))
                      (list (cons #\L 5) (cons #\D 3)))
                "splits two lines, each into (dir . dist) moves")
  (check-equal? (parse-input "R8,U5\r\nL5,D3\r\n")
                (list (list (cons #\R 8) (cons #\U 5))
                      (list (cons #\L 5) (cons #\D 3)))
                "tolerates CRLF line endings and a trailing newline")
  (check-equal? (parse-input "R1008,D546\nL19")
                (list (list (cons #\R 1008) (cons #\D 546))
                      (list (cons #\L 19)))
                "multi-digit distances parse")

  ;; --- trace: first-arrival step counts on a tiny wire ---
  ;; R2,U1 visits (1,0)@1 (2,0)@2 (2,1)@3; origin is never recorded.
  (let ([h (trace (list (cons #\R 2) (cons #\U 1)))])
    (check-equal? (hash-ref h (cons 1 0)) 1 "first cell, 1 step")
    (check-equal? (hash-ref h (cons 2 0)) 2 "second cell, 2 steps")
    (check-equal? (hash-ref h (cons 2 1)) 3 "third cell, 3 steps")
    (check-false  (hash-has-key? h (cons 0 0)) "origin is not recorded")
    (check-equal? (hash-count h) 3 "exactly three cells visited"))

  ;; A wire that doubles back keeps the EARLIER arrival, not the later.
  ;; R2,L2 visits (1,0)@1 (2,0)@2, then on the way back revisits (1,0)@3
  ;; (kept at 1) and lands on the origin (0,0)@4.
  (let ([h (trace (list (cons #\R 2) (cons #\L 2)))])
    (check-equal? (hash-ref h (cons 1 0)) 1
                  "self-crossing keeps the first (cheaper) arrival")
    (check-equal? (hash-ref h (cons 0 0)) 4
                  "origin excluded only as a START; stepping back onto it counts"))

  ;; --- the three worked examples, both parts ---
  (define (wires a b) (parse-input (string-append a "\n" b)))

  (let ([w (wires "R8,U5,L5,D3" "U7,R6,D4,L4")])
    (check-equal? (part1 w) 6  "example 1 part 1")
    (check-equal? (part2 w) 30 "example 1 part 2"))

  (let ([w (wires "R75,D30,R83,U83,L12,D49,R71,U7,L72"
                  "U62,R66,U55,R34,D71,R55,D58,R83")])
    (check-equal? (part1 w) 159 "example 2 part 1")
    (check-equal? (part2 w) 610 "example 2 part 2"))

  (let ([w (wires "R98,U47,R26,D63,R33,U87,L62,D20,R33,U53"
                  "U98,R91,D20,R16,D67,R40,U7,R15,U6,R7")])
    (check-equal? (part1 w) 135 "example 3 part 1")
    (check-equal? (part2 w) 410 "example 3 part 2"))

  ;; --- actual puzzle input ---
  (define input (parse-input (read-day-input 3)))
  (check-equal? (part1 input) 2180   "part 1")
  (check-equal? (part2 input) 112316 "part 2"))
