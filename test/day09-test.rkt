#lang racket/base

;; Tests for Day 09 — Sensor Boost (the complete Intcode computer).
;;
;; Pins:
;;   1. the three spec examples that exercise relative mode + big numbers:
;;        - the quine (relative reads/writes; outputs a copy of itself),
;;        - the 16-digit multiply (large-number support),
;;        - the large-value immediate passthrough,
;;   2. opcode 9 / relative-base behavior on the spec's tiny snippets,
;;   3. backward compatibility: a position/immediate program from Day 5
;;      still runs identically through the extended VM,
;;   4. the actual answers for inputs/day09.txt.
;;
;; Run with:  raco test test/day09-test.rkt

(require rackunit
         "../src/aoc.rkt"
         "../src/day09.rkt")

(module+ test

  (define (prog s) (parse-input s))

  ;; --- relative mode + big numbers: the three spec examples ---

  ;; The quine: takes no input and outputs a copy of itself. This is the
  ;; strongest single test — it only reproduces if relative-mode reads AND
  ;; writes, opcode 9, and grow-on-write memory all behave.
  (define quine
    '(109 1 204 -1 1001 100 1 100 1008 100 16 101 1006 101 0 99))
  (check-equal? (run/inputs (list->vector quine) '()) quine
                "quine outputs a copy of itself")

  ;; 1102,34915192,34915192,7,4,7,99,0 multiplies a big number by itself and
  ;; outputs the 16-digit result.
  (define out16 (run/inputs (prog "1102,34915192,34915192,7,4,7,99,0") '()))
  (check-equal? out16 '(1219070632396864) "outputs a 16-digit number")
  (check-equal? (string-length (number->string (car out16))) 16
                "result really is 16 digits")

  ;; 104,1125899906842624,99 emits the large immediate in the middle.
  (check-equal? (run/inputs (prog "104,1125899906842624,99") '())
                '(1125899906842624) "large immediate passthrough")

  ;; --- opcode 9 / relative base, from the prose examples ---

  ;; 109,1 sets rb to 1 (from 0); then 204,-1 outputs mem[rb-1] = mem[0] =
  ;; 109. (Same mechanic as the spec's rb 2000 -> 2019 then 204,-34 ->
  ;; addr 1985 = 2019-34; here rb 0 -> 1, addr 0 = 1-1.)
  (check-equal? (run/inputs (prog "109,1,204,-1,99") '()) '(109)
                "opcode 9 moves rb; relative output reads rb-relative cell")

  ;; A relative *write*: 109,5 (rb=5) then 21101,7,8,0 writes 7+8 to
  ;; mem[rb+0]=mem[5], and 204,0 outputs mem[rb+0]. (21101: op 01, param
  ;; modes 1,1,2.)  Confirms `addr` honors relative mode on the write target.
  (check-equal? (run/inputs (prog "109,5,21101,7,8,0,204,0,99") '()) '(15)
                "relative-mode write target resolves through rb")

  ;; --- backward compatibility with the older VM subset ---
  ;; A Day 5 position/immediate program (8 == input?) still works unchanged:
  ;; 3,9,8,9,10,9,4,9,99,-1,8 outputs 1 iff input equals 8.
  (define eq8 "3,9,8,9,10,9,4,9,99,-1,8")
  (check-equal? (run (prog eq8) 8) '(1) "eq-8 program: input 8 -> 1")
  (check-equal? (run (prog eq8) 7) '(0) "eq-8 program: input 7 -> 0")

  ;; --- actual puzzle input ---
  (define program (parse-input (read-day-input 9)))
  (check-equal? (part1 program) 4080871669 "part 1 (BOOST keycode)")
  (check-equal? (part2 program) 75202 "part 2 (distress coordinates)"))
