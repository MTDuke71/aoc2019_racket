#lang racket/base

;; Tests for Day 04 — Secure Container.
;;
;; Pins:
;;   1. the range parser ("lo-hi" -> (lo . hi), CRLF/trailing-newline),
;;   2. `digits` (number -> most-significant-first digit list),
;;   3. `run-length-encode` on hand-checkable lists (the day's core trick),
;;   4. every worked example from the puzzle text — Part 1's three and
;;      Part 2's three — directly against `part1-ok?` / `part2-ok?`,
;;   5. the actual answers for inputs/day04.txt.
;;
;; Run with:  raco test test/day04-test.rkt

(require rackunit
         "../src/aoc.rkt"
         "../src/day04.rkt")

(module+ test

  ;; --- parser ---
  (check-equal? (parse-input "172930-683082") (cons 172930 683082)
                "splits lo-hi into an inclusive pair")
  (check-equal? (parse-input "1-9\r\n") (cons 1 9)
                "tolerates CRLF and a trailing newline")

  ;; --- digits: most-significant-first ---
  (check-equal? (digits 123789) (list 1 2 3 7 8 9) "decimal digits, MSB first")
  (check-equal? (digits 111111) (list 1 1 1 1 1 1) "repeated digits")
  (check-equal? (digits 0) (list 0) "zero is a single digit")

  ;; --- run-length-encode: maximal CONSECUTIVE runs ---
  (check-equal? (run-length-encode '(1 1 2 3 3 3))
                '((1 . 2) (2 . 1) (3 . 3))
                "collapses consecutive equal elements into (value . count)")
  (check-equal? (run-length-encode '()) '() "empty list -> no runs")
  (check-equal? (run-length-encode '(5)) '((5 . 1)) "singleton -> one run")
  ;; Equal-but-NON-adjacent elements are distinct runs (the encoding is
  ;; positional, not a frequency count) — 1 2 1 is three runs, not "two 1s".
  (check-equal? (run-length-encode '(1 2 1))
                '((1 . 1) (2 . 1) (1 . 1))
                "non-adjacent equals are separate runs")

  ;; --- Part 1: the three worked examples ---
  (check-true  (part1-ok? 111111) "111111: double 11, never decreases")
  (check-false (part1-ok? 223450) "223450: decreasing pair 50")
  (check-false (part1-ok? 123789) "123789: no adjacent double")

  ;; --- Part 2: the three worked examples ---
  (check-true  (part2-ok? 112233) "112233: all repeats are exactly doubles")
  (check-false (part2-ok? 123444) "123444: the 44 is inside a run of three")
  (check-true  (part2-ok? 111122) "111122: 22 is a clean double despite 1111")
  ;; Part 2 is strictly stronger than Part 1: 111111 passes Part 1 but not
  ;; Part 2 (its only run has length 6, never exactly 2).
  (check-true  (part1-ok? 111111) "111111 still passes part 1")
  (check-false (part2-ok? 111111) "111111 fails part 2: no length-2 run")

  ;; --- actual puzzle input ---
  (define lohi (parse-input (read-day-input 4)))
  (check-equal? (part1 lohi) 1675 "part 1")
  (check-equal? (part2 lohi) 1142 "part 2"))
