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
  [parse-input  (-> string? (vectorof exact-integer?))]
  [run          (-> (vectorof exact-integer?) exact-integer?
                    (listof exact-integer?))]
  [run/inputs   (-> (vectorof exact-integer?) (listof exact-integer?)
                    (listof exact-integer?))]
  [intcode-mem   (-> (vectorof exact-integer?) box?)]
  [intcode-ref   (-> box? exact-integer? exact-integer?)]
  [intcode-set!  (-> box? exact-integer? exact-integer? void?)]
  [part1        (-> (vectorof exact-integer?) exact-integer?)]
  [part2        (-> (vectorof exact-integer?) exact-integer?)]
  [solve        (-> string? void?)]))

;; Comma-separated integers into a vector — identical to Day 2. The program
;; is random-access by position, so a vector (not a list) is its home.
(define (parse-input s)
  (list->vector (map string->number (string-split (string-trim s) ","))))

;; Intcode memory grows with zeros on read/write past the initial program —
;; required from [Day 7](day07_function_guide.md) onward when programs use
;; addresses as scratch space beyond the loaded image.
(define (intcode-mem program) (box (vector-copy program)))

(define (intcode-ref mem-box addr)
  (define mem (unbox mem-box))
  (if (and (>= addr 0) (< addr (vector-length mem)))
      (vector-ref mem addr)
      0))

(define (intcode-set! mem-box addr val)
  (when (< addr 0)
    (error 'intcode-set! "negative address ~a" addr))
  (define mem (unbox mem-box))
  (unless (< addr (vector-length mem))
    (define bigger (make-vector (max (add1 addr) (* 2 (vector-length mem))) 0))
    (vector-copy! bigger 0 mem 0 (vector-length mem))
    (set-box! mem-box bigger)
    (set! mem bigger))
  (vector-set! mem addr val))

;; Execute `program`, consuming `inputs` in order on each opcode-3 read.
;; Returns emitted outputs in order. A fresh memory copy is used so the
;; caller's program vector is left pristine — [Day 7](day07_function_guide.md)
;; chains many such runs with different input lists.
(define (run/inputs program inputs)
  (define mem (intcode-mem program))
  (let loop ([ip 0] [outs '()] [pending inputs])
    (define instr (intcode-ref mem ip))
    (define op    (modulo instr 100))
    (define modes (quotient instr 100))
    (define (val n)
      (define raw (intcode-ref mem (+ ip n)))
      (if (= 1 (modulo (quotient modes (expt 10 (sub1 n))) 10))
          raw
          (intcode-ref mem raw)))
    (define (addr n) (intcode-ref mem (+ ip n)))
    (case op
      [(1)  (intcode-set! mem (addr 3) (+ (val 1) (val 2))) (loop (+ ip 4) outs pending)]
      [(2)  (intcode-set! mem (addr 3) (* (val 1) (val 2))) (loop (+ ip 4) outs pending)]
      [(3)  (unless (pair? pending)
               (error 'run/inputs "input exhausted at opcode 3, ip ~a" ip))
             (intcode-set! mem (addr 1) (car pending))
             (loop (+ ip 2) outs (cdr pending))]
      [(4)  (loop (+ ip 2) (cons (val 1) outs) pending)]
      [(5)  (loop (if (not (zero? (val 1))) (val 2) (+ ip 3)) outs pending)]
      [(6)  (loop (if (zero? (val 1))       (val 2) (+ ip 3)) outs pending)]
      [(7)  (intcode-set! mem (addr 3) (if (< (val 1) (val 2)) 1 0)) (loop (+ ip 4) outs pending)]
      [(8)  (intcode-set! mem (addr 3) (if (= (val 1) (val 2)) 1 0)) (loop (+ ip 4) outs pending)]
      [(99) (reverse outs)]
      [else (error 'run/inputs "unknown opcode ~a at position ~a" op ip)])))

;; Single-input convenience wrapper used by Day 5's diagnostic runs.
(define (run program input)
  (run/inputs program (list input)))

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
