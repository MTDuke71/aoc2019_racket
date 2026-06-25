#lang racket

;; AoC 2019 Day 9 — Sensor Boost.
;;
;; The Intcode finale ([Day 2](day02_function_guide.md) →
;; [Day 5](day05_function_guide.md) → here): the BOOST program refuses to
;; run until the machine is a *complete* Intcode computer, and "complete"
;; means exactly one missing feature — **relative mode**:
;;
;;   * **Mode 2 (relative).** A new parameter mode alongside position (0)
;;     and immediate (1). Like position it names an address, but the
;;     address is offset by a movable **relative base** that starts at 0.
;;     Reads and writes both honor it.
;;   * **Opcode 9 (adjust relative base).** `9 p` moves the relative base by
;;     `p` (mode-aware, so usually immediate). This is the only new opcode.
;;   * **Big memory, big numbers.** Memory past the loaded image reads as 0
;;     and is writable; values can exceed 32 bits. Day 5's `intcode-mem` /
;;     `intcode-ref` / `intcode-set!` already grow-on-write and read-OOB-as-0,
;;     and Racket integers are bignums, so both come for free.
;;
;; Part 1 runs BOOST in test mode (input `1`) and emits the BOOST keycode;
;; Part 2 runs it in sensor-boost mode (input `2`) and emits the distress
;; coordinates. Each is a single output.
;;
;; The whole day is the **relative base**: thread one extra accumulator (`rb`)
;; through the fetch-decode loop exactly as Day 5 threads the instruction
;; pointer. The opcode handlers are byte-for-byte Day 5's — every change
;; lives in the operand-resolution seam (`val` / `addr`). See the function
;; guide's "operand resolution is the orthogonal axis" section.

(require "aoc.rkt"
         (prefix-in d05: "day05.rkt"))

(provide
 (contract-out
  [parse-input (-> string? (vectorof exact-integer?))]
  [run/inputs  (-> (vectorof exact-integer?) (listof exact-integer?)
                   (listof exact-integer?))]
  [run         (-> (vectorof exact-integer?) exact-integer?
                   (listof exact-integer?))]
  [part1       (-> (vectorof exact-integer?) exact-integer?)]
  [part2       (-> (vectorof exact-integer?) exact-integer?)]
  [solve       (-> string? void?)]))

;; Comma-separated integers into a vector — the program is random-access by
;; position, so a vector is its home. Identical to Days 2/5/7.
(define parse-input d05:parse-input)

;; Execute `program`, consuming `inputs` in order on each opcode-3 read, and
;; return the emitted outputs in order. The loop carries two pieces of CPU
;; state as functional accumulators: the instruction pointer `ip` (since
;; Day 5) and now the **relative base** `rb` (new this day, starts at 0).
;;
;; Compare against Day 5's `run/inputs`: the eight arithmetic/IO/jump
;; handlers are unchanged except for passing `rb` along; the *only* new
;; logic is (1) mode 2 in `val`, (2) the relative-aware `addr`, and
;; (3) opcode 9. Adding an addressing mode touched the operand seam and
;; nothing else — the point the function guide draws out.
(define (run/inputs program inputs)
  (define mem (d05:intcode-mem program))
  (let loop ([ip 0] [rb 0] [outs '()] [pending inputs])
    (define instr (d05:intcode-ref mem ip))
    (define op    (modulo instr 100))
    (define modes (quotient instr 100))
    ;; The mode digit for parameter `n` (1-based): the n-th digit of `modes`.
    (define (mode n) (modulo (quotient modes (expt 10 (sub1 n))) 10))
    ;; Read operand `n`, mode-aware. The single new clause vs. Day 5 is the
    ;; relative case `[(2) ...]` — same dereference as position, offset by rb.
    (define (val n)
      (define raw (d05:intcode-ref mem (+ ip n)))
      (case (mode n)
        [(0) (d05:intcode-ref mem raw)]          ; position
        [(1) raw]                                ; immediate
        [(2) (d05:intcode-ref mem (+ rb raw))])) ; relative
    ;; Resolve a *write* target `n`. Writes are never immediate; mode 0 uses
    ;; the cell as an address, mode 2 offsets it by rb. This is the mirror of
    ;; `val`'s new branch — the structural reason writes can't be immediate is
    ;; that they go through `addr`, not `val`.
    (define (addr n)
      (define raw (d05:intcode-ref mem (+ ip n)))
      (if (= 2 (mode n)) (+ rb raw) raw))
    (case op
      [(1)  (d05:intcode-set! mem (addr 3) (+ (val 1) (val 2))) (loop (+ ip 4) rb outs pending)]
      [(2)  (d05:intcode-set! mem (addr 3) (* (val 1) (val 2))) (loop (+ ip 4) rb outs pending)]
      [(3)  (unless (pair? pending)
              (error 'run/inputs "input exhausted at opcode 3, ip ~a" ip))
            (d05:intcode-set! mem (addr 1) (car pending))
            (loop (+ ip 2) rb outs (cdr pending))]
      [(4)  (loop (+ ip 2) rb (cons (val 1) outs) pending)]
      [(5)  (loop (if (not (zero? (val 1))) (val 2) (+ ip 3)) rb outs pending)]
      [(6)  (loop (if (zero? (val 1))       (val 2) (+ ip 3)) rb outs pending)]
      [(7)  (d05:intcode-set! mem (addr 3) (if (< (val 1) (val 2)) 1 0)) (loop (+ ip 4) rb outs pending)]
      [(8)  (d05:intcode-set! mem (addr 3) (if (= (val 1) (val 2)) 1 0)) (loop (+ ip 4) rb outs pending)]
      ;; The only new opcode: adjust the relative base by a mode-aware operand.
      [(9)  (loop (+ ip 2) (+ rb (val 1)) outs pending)]
      [(99) (reverse outs)]
      [else (error 'run/inputs "unknown opcode ~a at position ~a" op ip)])))

;; Single-input convenience wrapper, mirroring Day 5's `run`.
(define (run program input)
  (run/inputs program (list input)))

;; The BOOST keycode / distress coordinates is the program's final (and, on
;; a correct machine, only) output.
(define (boost program input)
  (last (run program input)))

;; Part 1: test mode (input 1).  Part 2: sensor-boost mode (input 2).
(define (part1 program) (boost program 1))
(define (part2 program) (boost program 2))

;; Dispatcher: parse once, print both parts. Mirrors Days 1–8.
(define (solve contents)
  (define program (parse-input contents))
  (printf "  part 1: ~a\n" (part1 program))
  (printf "  part 2: ~a\n" (part2 program)))

(module+ main
  (solve (read-day-input 9)))
