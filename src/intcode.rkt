#lang racket

;; The resumable Intcode machine, as a library.
;;
;; Days 2 → 5 → 7 → 9 each *changed* the VM, so each of those days owns its
;; own copy: the diff between consecutive copies is the lesson, and the
;; function guides annotate them line by line. That era is over. The
;; instruction set froze at [Day 9](day09_function_guide.md) — relative mode,
;; opcode 9, grow-on-write memory — and every Intcode day from
;; [Day 13](day13_function_guide.md) on is a *driver* problem: the puzzle is
;; the world you wire around an unchanging CPU, not the CPU.
;;
;; So the machine moves here once, verbatim from
;; [Day 11](day11_function_guide.md)'s `vm-step!`, and Days 13/15/17/19/21/23/25
;; require it instead of re-pasting it. Day 11's copy deliberately stays put:
;; its guide walks that code as the day's content, and rewriting it to a
;; `require` would strand the annotation.
;;
;; The interface is [Day 7](day07_function_guide.md)'s cooperative-pause
;; protocol: `vm-step!` runs exactly one instruction and *reports* what
;; happened, so the caller — not the VM — decides where input comes from and
;; what outputs mean. That inversion is what lets a program's Nth input
;; depend on its own (N−1)th output, which is the defining feature of every
;; remaining Intcode day.
;;
;; Rust analogue: a `struct Vm { mem: Vec<i64>, ip: usize, rb: i64, inputs:
;; VecDeque<i64>, halted: bool }` with `fn step(&mut self) -> Step`, where
;; `enum Step { Ran, Blocked, Output(i64), Halted }`. Racket's tagged-list
;; return `` `(output ,n) `` is that enum without the type declaration —
;; `match` on the caller's side plays the role of `match` on the enum.

(require (prefix-in d05: "day05.rkt"))

(define step-result/c
  (or/c 'ran 'blocked 'halted (list/c 'output exact-integer?)))

(provide
 step-result/c
 (contract-out
  [vm?         (-> any/c boolean?)]
  [make-vm     (-> (vectorof exact-integer?) vm?)]
  [vm-halted?  (-> vm? boolean?)]
  [vm-enqueue! (-> vm? exact-integer? void?)]
  [vm-poke!    (-> vm? exact-integer? exact-integer? void?)]
  [vm-step!    (-> vm? step-result/c)]))

;; `mem` is a box holding a vector ([Day 5](day05_function_guide.md)'s
;; grow-on-write memory — reads past the end are 0, writes past the end
;; reallocate); `ip` is the instruction pointer; `rb` is the relative base
;; ([Day 9](day09_function_guide.md)); `inputs` is a pending-input queue that
;; is typically empty except for the instant between the caller noticing a
;; `'blocked` and enqueuing a reply.
(struct vm (mem ip rb inputs halted?) #:mutable)

;; A fresh machine over a *copy* of `program`, so the caller's vector is left
;; pristine and one parsed program can seed many runs.
(define (make-vm program) (vm (d05:intcode-mem program) 0 0 '() #f))

(define (vm-enqueue! machine n)
  (set-vm-inputs! machine (append (vm-inputs machine) (list n))))

;; Write directly into a machine's memory. Used for pre-run patches that the
;; puzzle states as memory edits rather than as input — Day 2's (noun, verb)
;; and Day 13's "set address 0 to 2 to play for free".
(define (vm-poke! machine addr val)
  (d05:intcode-set! (vm-mem machine) addr val))

;; Execute exactly one instruction. Returns:
;;   'ran          — the machine advanced; nothing for the caller to do
;;   'blocked      — opcode 3 with an empty input queue. The ip has NOT
;;                   moved, so enqueuing a value and stepping again re-runs
;;                   the same read. This is the whole cooperative protocol.
;;   `(output ,n)  — opcode 4 emitted `n`
;;   'halted       — opcode 99 (idempotent: stepping a halted machine again
;;                   just reports 'halted, so driving loops don't need a
;;                   separate halted? check)
;;
;; The eight arithmetic/jump handlers are Day 5's; `val`/`addr` carry Day 9's
;; third addressing mode; opcode 9 is Day 9's. Nothing here is new.
(define (vm-step! machine)
  (if (vm-halted? machine)
      'halted
      (let ()
        (define mem (vm-mem machine))
        (define ip  (vm-ip machine))
        (define instr (d05:intcode-ref mem ip))
        (define op    (modulo instr 100))
        (define modes (quotient instr 100))
        (define (mode n) (modulo (quotient modes (expt 10 (sub1 n))) 10))
        (define (val n)
          (define raw (d05:intcode-ref mem (+ ip n)))
          (case (mode n)
            [(0) (d05:intcode-ref mem raw)]                    ; position
            [(1) raw]                                          ; immediate
            [(2) (d05:intcode-ref mem (+ (vm-rb machine) raw))])) ; relative
        (define (addr n)
          (define raw (d05:intcode-ref mem (+ ip n)))
          (if (= 2 (mode n)) (+ (vm-rb machine) raw) raw))
        (case op
          [(1) (d05:intcode-set! mem (addr 3) (+ (val 1) (val 2)))
               (set-vm-ip! machine (+ ip 4)) 'ran]
          [(2) (d05:intcode-set! mem (addr 3) (* (val 1) (val 2)))
               (set-vm-ip! machine (+ ip 4)) 'ran]
          [(3) (if (null? (vm-inputs machine))
                   'blocked
                   (begin
                     (d05:intcode-set! mem (addr 1) (car (vm-inputs machine)))
                     (set-vm-inputs! machine (cdr (vm-inputs machine)))
                     (set-vm-ip! machine (+ ip 2))
                     'ran))]
          [(4) (set-vm-ip! machine (+ ip 2)) `(output ,(val 1))]
          [(5) (set-vm-ip! machine (if (not (zero? (val 1))) (val 2) (+ ip 3))) 'ran]
          [(6) (set-vm-ip! machine (if (zero? (val 1))       (val 2) (+ ip 3))) 'ran]
          [(7) (d05:intcode-set! mem (addr 3) (if (< (val 1) (val 2)) 1 0))
               (set-vm-ip! machine (+ ip 4)) 'ran]
          [(8) (d05:intcode-set! mem (addr 3) (if (= (val 1) (val 2)) 1 0))
               (set-vm-ip! machine (+ ip 4)) 'ran]
          [(9) (set-vm-rb! machine (+ (vm-rb machine) (val 1)))
               (set-vm-ip! machine (+ ip 2)) 'ran]
          [(99) (set-vm-halted?! machine #t) 'halted]
          [else (error 'vm-step! "unknown opcode ~a at position ~a" op ip)]))))
