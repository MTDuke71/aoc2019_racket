#lang racket

;; AoC 2019 Day 5 — Sunny with a Chance of Asteroids.
;;
;; The second Intcode day, and the one that turns the Day 2 adder into a
;; real little CPU. Three upgrades land at once:
;;
;;   * **Parameter modes.** The opcode is now only the rightmost two digits
;;     of the instruction; the digits above it are per-parameter *modes*,
;;     read right-to-left. Mode 0 (position) dereferences the parameter as
;;     an address (the Day 2 behavior); mode 1 (immediate) uses it as a
;;     literal value. So `1002,4,3,4,33` is `mem[4] <- mem[4] * 3`.
;;   * **I/O opcodes.** `3 dst` reads one input and stores it; `4 src`
;;     emits a value. The diagnostic program reads a single system-ID input
;;     and prints a stream of test results ending in the diagnostic code.
;;   * **Control flow.** `5`/`6` are jump-if-true / jump-if-false (they set
;;     the instruction pointer instead of advancing it), and `7`/`8` are
;;     less-than / equals (they store a 0/1 flag). With these the machine is
;;     Turing-ish: it can branch and loop.
;;
;;   * Part 1: run with input 1 (air-conditioner ID); the answer is the
;;     last output (the diagnostic code; every earlier output should be 0).
;;   * Part 2: run with input 5 (thermal-radiator ID); the single output is
;;     the diagnostic code.
;;
;; The decode is the heart of the day: split the instruction into
;; `(op . modes)`, then a per-parameter `val` that consults the right mode
;; digit. Write targets (`dst`) are *always* position mode by spec, so they
;; read the raw cell without dereferencing. The function guide walks the
;; digit arithmetic and contrasts this with [Day 2](day02_function_guide.md)'s
;; fixed 4-wide decode.

(require "aoc.rkt")

(provide
 (contract-out
  [parse-input (-> string? (vectorof exact-integer?))]
  [run         (-> (vectorof exact-integer?) exact-integer?
                   (listof exact-integer?))]
  [part1       (-> (vectorof exact-integer?) exact-integer?)]
  [part2       (-> (vectorof exact-integer?) exact-integer?)]
  [solve       (-> string? void?)]))

;; Comma-separated integers into a vector — identical to Day 2. The program
;; is random-access by position, so a vector (not a list) is its home.
(define (parse-input s)
  (list->vector (map string->number (string-split (string-trim s) ","))))

;; Execute `program` against a single integer `input`, returning the list of
;; emitted outputs in order. A fresh copy is run so the caller's program is
;; left pristine (Part 1 and Part 2 reuse the same vector).
;;
;; The loop is tail-recursive on `(ip outs)`. Each iteration re-decodes the
;; instruction at `ip`:
;;   * `op`    — the opcode, rightmost two digits.
;;   * `modes` — everything above, i.e. the stacked mode digits.
;;   * `(val n)` — the value of the nth parameter: pull the mode digit at
;;     position `n` (ones digit of `modes` for n=1, tens for n=2, …) and
;;     either use the cell literally (immediate) or dereference it
;;     (position).
;;   * `(addr n)` — a *write* target: the raw cell, never dereferenced,
;;     because write parameters are always position mode by spec.
(define (run program input)
  (define mem (vector-copy program))
  (let loop ([ip 0] [outs '()])
    (define instr (vector-ref mem ip))
    (define op    (modulo instr 100))
    (define modes (quotient instr 100))
    (define (val n)
      (define raw (vector-ref mem (+ ip n)))
      (if (= 1 (modulo (quotient modes (expt 10 (sub1 n))) 10))
          raw                              ; immediate: the literal
          (vector-ref mem raw)))           ; position: dereference
    (define (addr n) (vector-ref mem (+ ip n)))
    (case op
      [(1)  (vector-set! mem (addr 3) (+ (val 1) (val 2))) (loop (+ ip 4) outs)]
      [(2)  (vector-set! mem (addr 3) (* (val 1) (val 2))) (loop (+ ip 4) outs)]
      [(3)  (vector-set! mem (addr 1) input)               (loop (+ ip 2) outs)]
      [(4)  (loop (+ ip 2) (cons (val 1) outs))]
      [(5)  (loop (if (not (zero? (val 1))) (val 2) (+ ip 3)) outs)]
      [(6)  (loop (if (zero? (val 1))       (val 2) (+ ip 3)) outs)]
      [(7)  (vector-set! mem (addr 3) (if (< (val 1) (val 2)) 1 0)) (loop (+ ip 4) outs)]
      [(8)  (vector-set! mem (addr 3) (if (= (val 1) (val 2)) 1 0)) (loop (+ ip 4) outs)]
      [(99) (reverse outs)]
      [else (error 'run "unknown opcode ~a at position ~a" op ip)])))

;; The diagnostic code is the final value the program emits.
(define (diagnostic program input)
  (last (run program input)))

;; Part 1: system ID 1.  Part 2: system ID 5.
(define (part1 program) (diagnostic program 1))
(define (part2 program) (diagnostic program 5))

;; Dispatcher: parse once, print both parts. Mirrors Days 1–4.
(define (solve contents)
  (define program (parse-input contents))
  (printf "  part 1: ~a\n" (part1 program))
  (printf "  part 2: ~a\n" (part2 program)))

(module+ main
  (solve (read-day-input 5)))
