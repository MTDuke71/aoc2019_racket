#lang racket

;; AoC 2019 Day 2 — 1202 Program Alarm.
;;
;; The first **Intcode** day, and the seed of AoC 2019's VM trilogy
;; (Days 2, 5, 7, 9 all extend the same machine). An Intcode program is a
;; flat list of integers — both the code AND the data live in one mutable
;; array, von-Neumann style. The machine is a classic fetch/decode/execute
;; loop over three opcodes:
;;
;;   * 1  a b dst : mem[dst] <- mem[a] + mem[b]   (positions, not values)
;;   * 2  a b dst : mem[dst] <- mem[a] * mem[b]
;;   * 99         : halt
;;
;; Every non-halt opcode is 4 cells wide; the instruction pointer steps by
;; 4. The crucial wrinkle is *indirect addressing*: the three cells after
;; the opcode are the **positions** of the operands, not the operands.
;;
;;   * Part 1: set mem[1]=12, mem[2]=2 ("1202"), run, read mem[0].
;;   * Part 2: find the noun/verb in [0,99] that makes mem[0]=19690720,
;;     report 100*noun + verb.
;;
;; This day introduces the project's first **mutable `vector`** — the
;; Racket analogue of Haskell's `STUArray` (AoC 2018 Day 9). The function
;; guide's "Possible optimization" section turns Part 2's 10000-run brute
;; force into a 3-run closed form by exploiting the program's affine
;; structure.

(require "aoc.rkt")

(provide
 (contract-out
  [parse-input (-> string? (vectorof exact-integer?))]
  [run         (-> (vectorof exact-integer?) (vectorof exact-integer?))]
  [run-with    (-> (vectorof exact-integer?) exact-integer? exact-integer?
                   exact-integer?)]
  [part1       (-> (vectorof exact-integer?) exact-integer?)]
  [part2       (-> (vectorof exact-integer?) exact-integer?)]
  [solve       (-> string? void?)]))

;; The output Part 2 hunts for. Same for every player's input.
(define target 19690720)

;; Comma-separated integers into a vector. `string-trim` strips the
;; trailing newline/CRLF first so the last token parses cleanly; the
;; program is then random-access by position, which is the whole point of
;; Intcode, so a vector (not a list) is the right home for it.
;;
;; Rust analogue: `s.trim().split(',').map(|t| t.parse().unwrap()).collect()`.
(define (parse-input s)
  (list->vector (map string->number (string-split (string-trim s) ","))))

;; One binary opcode step, mutating `mem` in place. Reads the two source
;; *positions* from cells ip+1 and ip+2, dereferences them to get the
;; operand values, and stores `(op a b)` at the *position* named in cell
;; ip+3. This double-dereference IS the indirect addressing the puzzle
;; describes.
(define (binop! mem ip op)
  (define a   (vector-ref mem (vector-ref mem (+ ip 1))))
  (define b   (vector-ref mem (vector-ref mem (+ ip 2))))
  (define dst (vector-ref mem (+ ip 3)))
  (vector-set! mem dst (op a b)))

;; The fetch/decode/execute loop, mutating `mem` in place and returning it.
;; Tail-recursive on the instruction pointer, so it runs as a constant-
;; stack loop. Kept private: callers go through `run` (which copies first)
;; so a program vector is never clobbered by being executed.
(define (run! mem)
  (let loop ([ip 0])
    (case (vector-ref mem ip)
      [(99) mem]
      [(1)  (binop! mem ip +) (loop (+ ip 4))]
      [(2)  (binop! mem ip *) (loop (+ ip 4))]
      [else (error 'run "unknown opcode ~a at position ~a"
                   (vector-ref mem ip) ip)])))

;; Public entry: execute a *fresh copy* so the caller's program is left
;; pristine and reusable (Part 2 runs the same program 10000 times).
;; Returns the final memory state — the example tests inspect it directly.
(define (run program)
  (run! (vector-copy program)))

;; Load noun/verb into positions 1 and 2, run, read the result off
;; position 0. The "1202" setup of Part 1 is just `(run-with prog 12 2)`.
(define (run-with program noun verb)
  (define mem (vector-copy program))
  (vector-set! mem 1 noun)
  (vector-set! mem 2 verb)
  (run! mem)
  (vector-ref mem 0))

;; Part 1: the 1202 program alarm state.
(define (part1 program)
  (run-with program 12 2))

;; Part 2: brute-force the 100x100 (noun, verb) grid for the pair that
;; yields `target`. `for*/first` is nested iteration that short-circuits on
;; the first body value for a matching pair — no manual break flag.
(define (part2 program)
  (for*/first ([noun (in-range 100)]
               [verb (in-range 100)]
               #:when (= (run-with program noun verb) target))
    (+ (* 100 noun) verb)))

;; Dispatcher: parse once, print both parts. Mirrors Day 1's `solve`.
(define (solve contents)
  (define program (parse-input contents))
  (printf "  part 1: ~a\n" (part1 program))
  (printf "  part 2: ~a\n" (part2 program)))

(module+ main
  (solve (read-day-input 2)))
