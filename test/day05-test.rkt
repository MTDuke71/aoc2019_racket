#lang racket/base

;; Tests for Day 05 — Sunny with a Chance of Asteroids.
;;
;; Pins:
;;   1. the parser (comma-separated ints -> vector, shared with Day 2),
;;   2. I/O + immediate-vs-position modes via the echo program,
;;   3. every new control-flow opcode (equals 8, less-than 7, jump 5/6) in
;;      BOTH parameter modes, using the puzzle's canonical small programs —
;;      these collectively cover what the large 999/1000/1001 example does,
;;   4. the actual answers for inputs/day05.txt.
;;
;; Run with:  raco test test/day05-test.rkt

(require rackunit
         racket/list
         "../src/aoc.rkt"
         "../src/day05.rkt")

(module+ test

  (define (prog . xs) (list->vector xs))

  ;; --- parser ---
  (check-equal? (parse-input "1002,4,3,4,33") (vector 1002 4 3 4 33)
                "comma-separated ints into a vector")
  (check-equal? (parse-input "3,0,4,0,99\r\n") (vector 3 0 4 0 99)
                "tolerates CRLF / trailing newline")

  ;; --- I/O echo: read input, emit it, halt. Exercises opcodes 3 and 4. ---
  (check-equal? (run (prog 3 0 4 0 99) 42) (list 42)
                "3,0,4,0,99 echoes its input")

  ;; --- equals 8 (opcode 8), position then immediate mode ---
  (let ([p (prog 3 9 8 9 10 9 4 9 99 -1 8)])     ; position
    (check-equal? (run p 8) (list 1) "pos equals: input 8 -> 1")
    (check-equal? (run p 7) (list 0) "pos equals: input 7 -> 0"))
  (let ([p (prog 3 3 1108 -1 8 3 4 3 99)])       ; immediate
    (check-equal? (run p 8) (list 1) "imm equals: input 8 -> 1")
    (check-equal? (run p 9) (list 0) "imm equals: input 9 -> 0"))

  ;; --- less-than 8 (opcode 7), position then immediate mode ---
  (let ([p (prog 3 9 7 9 10 9 4 9 99 -1 8)])     ; position
    (check-equal? (run p 7) (list 1) "pos less-than: input 7 -> 1")
    (check-equal? (run p 8) (list 0) "pos less-than: input 8 -> 0"))
  (let ([p (prog 3 3 1107 -1 8 3 4 3 99)])       ; immediate
    (check-equal? (run p 7) (list 1) "imm less-than: input 7 -> 1")
    (check-equal? (run p 8) (list 0) "imm less-than: input 8 -> 0"))

  ;; --- jumps (opcodes 5/6): output 0 for input 0, else 1 ---
  (let ([p (prog 3 12 6 12 15 1 13 14 13 4 13 99 -1 0 1 9)])  ; position
    (check-equal? (run p 0) (list 0) "pos jump: input 0 -> 0")
    (check-equal? (run p 5) (list 1) "pos jump: nonzero -> 1"))
  (let ([p (prog 3 3 1105 -1 9 1101 0 0 12 4 12 99 1)])       ; immediate
    (check-equal? (run p 0) (list 0) "imm jump: input 0 -> 0")
    (check-equal? (run p 5) (list 1) "imm jump: nonzero -> 1"))

  ;; --- actual puzzle input ---
  (define program (parse-input (read-day-input 5)))
  ;; Part 1's diagnostic run: every test output is 0 except the final code.
  (let ([outs (run program 1)])
    (check-true (andmap zero? (drop-right outs 1))
                "part 1: all but the last output are 0 (tests pass)")
    (check-equal? (last outs) 6731945 "part 1 diagnostic code"))
  (check-equal? (part1 program) 6731945 "part 1")
  (check-equal? (part2 program) 9571668 "part 2"))
