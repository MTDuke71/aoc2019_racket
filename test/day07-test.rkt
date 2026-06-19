#lang racket/base

;; Tests for Day 07 — Amplification Circuit.
;;
;; Pins:
;;   1. Part 1's three worked examples (series chain, known phase + signal),
;;   2. Part 2's two worked examples (feedback loop),
;;   3. the actual answers for inputs/day07.txt.
;;
;; Run with:  raco test test/day07-test.rkt

(require rackunit
         racket/list
         "../src/aoc.rkt"
         "../src/day07.rkt")

(module+ test

  (define (prog s) (parse-input s))

  ;; --- Part 1 worked examples ---
  (check-equal? (thruster-series
                 (prog "3,15,3,16,1002,16,10,16,1,16,15,15,4,15,99,0,0")
                 '(4 3 2 1 0))
                43210
                "example 1: phases 4,3,2,1,0 -> 43210")
  (check-equal? (thruster-series
                 (prog "3,23,3,24,1002,24,10,24,1002,23,-1,23,101,5,23,23,1,24,23,23,4,23,99,0,0")
                 '(0 1 2 3 4))
                54321
                "example 2: phases 0,1,2,3,4 -> 54321")
  (check-equal? (thruster-series
                 (prog "3,31,3,32,1002,32,10,32,1001,31,-2,31,1007,31,0,33,1002,33,7,33,1,33,31,31,1,32,31,31,4,31,99,0,0,0")
                 '(1 0 4 3 2))
                65210
                "example 3: phases 1,0,4,3,2 -> 65210")

  ;; --- Part 2 worked examples (feedback loop, phases 5–9) ---
  (check-equal? (thruster-feedback
                 (prog "3,26,1001,26,-4,26,3,27,1002,27,2,27,1,27,26,27,4,27,1001,28,-1,28,1005,28,6,99,0,0,5")
                 '(9 8 7 6 5))
                139629729
                "feedback example 1: phases 9,8,7,6,5 -> 139629729")
  (check-equal? (thruster-feedback
                 (prog "3,52,1001,52,-5,52,3,53,1,52,56,54,1007,54,5,55,1005,55,26,1001,54,-5,54,1105,1,12,1,53,54,53,1008,54,0,55,1001,55,1,55,2,53,55,53,4,53,1001,56,-1,56,1005,56,6,99,0,0,0,0,10")
                 '(9 7 8 5 6))
                18216
                "feedback example 2: phases 9,7,8,5,6 -> 18216")

  ;; --- actual puzzle input ---
  (define program (parse-input (read-day-input 7)))
  (check-equal? (part1 program) 46014 "part 1")
  (check-equal? (part2 program) 19581200 "part 2"))
