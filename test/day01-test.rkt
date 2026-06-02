#lang racket/base

;; Tests for Day 01 — The Tyranny of the Rocket Equation.
;;
;; Pins three things so no future refactor can drift silently:
;;   1. the parser,
;;   2. every worked example from the puzzle text (both parts),
;;   3. the actual answers for inputs/day01.txt.
;;
;; Run with:  raco test test/day01-test.rkt
;; (`raco test` executes the `test` submodule below.)

(require rackunit
         "../src/aoc.rkt"
         "../src/day01.rkt")

(module+ test

  ;; --- parser ---
  (check-equal? (parse-input "12\n14\n1969\n") '(12 14 1969)
                "splits lines into integers, ignoring trailing newline")
  (check-equal? (parse-input "100756") '(100756)
                "single line, no trailing newline")
  (check-equal? (parse-input "12\r\n14\r\n") '(12 14)
                "tolerates CRLF line endings")

  ;; --- Part 1: per-module fuel from the puzzle examples ---
  (check-equal? (fuel 12) 2)
  (check-equal? (fuel 14) 2)
  (check-equal? (fuel 1969) 654)
  (check-equal? (fuel 100756) 33583)
  (check-equal? (part1 '(12 14 1969 100756)) (+ 2 2 654 33583))

  ;; --- Part 2: fixed-point fuel from the puzzle examples ---
  (check-equal? (total-fuel 14) 2     "fuel(14)=2, fuel(2)<=0 -> stop")
  (check-equal? (total-fuel 1969) 966 "654 + 216 + 70 + 21 + 5")
  (check-equal? (total-fuel 100756) 50346)

  ;; --- actual puzzle input ---
  (define raw (read-day-input 1))
  (check-equal? (part1 (parse-input raw)) 3481005 "part 1")
  (check-equal? (part2 (parse-input raw)) 5218616 "part 2"))
