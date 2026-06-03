#lang racket/base

;; Tests for Day 02 — 1202 Program Alarm.
;;
;; Pins:
;;   1. the comma parser (incl. trailing-newline tolerance),
;;   2. every worked example from the puzzle text — both the step-by-step
;;      program and the four small "initial -> final state" programs —
;;      checked against the *full* final memory, not just position 0,
;;   3. the actual answers for inputs/day02.txt.
;;
;; Run with:  raco test test/day02-test.rkt

(require rackunit
         "../src/aoc.rkt"
         "../src/day02.rkt")

(module+ test

  ;; --- parser ---
  (check-equal? (parse-input "1,0,0,3,99") (vector 1 0 0 3 99)
                "splits on commas into a vector")
  (check-equal? (parse-input "1,0,0,3,99\n") (vector 1 0 0 3 99)
                "tolerates a trailing newline")
  (check-equal? (parse-input "1,0,0,3,99\r\n") (vector 1 0 0 3 99)
                "tolerates CRLF line endings")

  ;; --- the worked example, checked against the full final state ---
  (check-equal? (run (parse-input "1,9,10,3,2,3,11,0,99,30,40,50"))
                (vector 3500 9 10 70 2 3 11 0 99 30 40 50)
                "the step-by-step example from the puzzle text")

  ;; --- the four small initial -> final programs ---
  (check-equal? (run (vector 1 0 0 0 99)) (vector 2 0 0 0 99)
                "1+1=2 at position 0")
  (check-equal? (run (vector 2 3 0 3 99)) (vector 2 3 0 6 99)
                "3*2=6 at position 3")
  (check-equal? (run (vector 2 4 4 5 99 0)) (vector 2 4 4 5 99 9801)
                "99*99=9801 stored past the halt")
  (check-equal? (run (vector 1 1 1 4 99 5 6 0 99))
                (vector 30 1 1 4 2 5 6 0 99)
                "two ops, the first rewriting the halt cell")

  ;; --- run does not clobber its argument ---
  (let ([prog (vector 1 0 0 0 99)])
    (run prog)
    (check-equal? prog (vector 1 0 0 0 99)
                  "run executes a copy; the caller's program is untouched"))

  ;; --- actual puzzle input ---
  (define program (parse-input (read-day-input 2)))
  (check-equal? (part1 program) 4945026 "part 1")
  (check-equal? (part2 program) 5296    "part 2"))
