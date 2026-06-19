#lang racket

;; AoC 2019 Day 7 — Amplification Circuit.
;;
;; Five copies of the [Day 5](day05_function_guide.md) Intcode program run
;; as amplifiers. Each copy reads its phase setting (0–4, used once per
;; permutation) and then an input signal; its output feeds the next amp.
;;
;;   * Part 1 — **series chain**: run A→B→C→D→E sequentially; brute-force
;;     all 5! phase permutations and take the maximum final output.
;;   * Part 2 — **feedback loop**: all five machines run concurrently;
;;     E's output loops back to A's input queue. Still brute-force phases;
;;     the answer is the maximum thruster signal E emits before all five halt.
;;
;; Part 1 reuses `run/inputs` from Day 5 (two reads per amp: phase, signal).
;; Part 2 needs a cooperative stepper that can pause on an empty input queue
;; and resume when a neighbour produces output — the I/O model Day 5's
;; single-shot `run` foreshadowed.

(require racket/list
         "aoc.rkt"
         (prefix-in d05: "day05.rkt"))

(provide
 (contract-out
  [parse-input       (-> string? (vectorof exact-integer?))]
  [thruster-series   (-> (vectorof exact-integer?) (listof (integer-in 0 4))
                         exact-integer?)]
  [thruster-feedback (-> (vectorof exact-integer?) (listof exact-integer?)
                         exact-integer?)]
  [part1             (-> (vectorof exact-integer?) exact-integer?)]
  [part2             (-> (vectorof exact-integer?) exact-integer?)]
  [solve             (-> string? void?)]))

(define parse-input d05:parse-input)

;; One amplifier: phase setting first, then the input signal from the left.
(define (amp-output program phase signal)
  (last (d05:run/inputs program (list phase signal))))

;; Part 1 signal for one phase permutation: fold the chain left-to-right,
;; seeding the first amp with input 0.
(define (thruster-series program phases)
  (for/fold ([signal 0]) ([phase (in-list phases)])
    (amp-output program phase signal)))

;; --- Part 2: five concurrent VMs with feedback ---

;; One Intcode instance that can block when its input queue is empty.
;; `mem` is a box — see `intcode-ref` / `intcode-set!` in Day 5.
(struct vm (mem ip inputs halted?) #:mutable)

;; Run one instruction on `machine`. Returns:
;;   'blocked  — opcode 3 with an empty input queue (wait for a neighbour)
;;   'ran      — any other instruction advanced the pointer
;;   `(output ,n) — opcode 4 emitted `n`
;;   'halted   — opcode 99
(define (vm-step! machine)
  (match-define (vm mem ip inputs halted?) machine)
  (if halted?
      'halted
      (let ()
        (define instr (d05:intcode-ref mem ip))
        (define op    (modulo instr 100))
        (define modes (quotient instr 100))
        (define (val n)
          (define raw (d05:intcode-ref mem (+ ip n)))
          (if (= 1 (modulo (quotient modes (expt 10 (sub1 n))) 10))
              raw
              (d05:intcode-ref mem raw)))
        (define (addr n) (d05:intcode-ref mem (+ ip n)))
        (case op
          [(1) (d05:intcode-set! mem (addr 3) (+ (val 1) (val 2)))
               (set-vm-ip! machine (+ ip 4))
               'ran]
          [(2) (d05:intcode-set! mem (addr 3) (* (val 1) (val 2)))
               (set-vm-ip! machine (+ ip 4))
               'ran]
          [(3) (if (null? inputs)
                   'blocked
                   (begin
                     (d05:intcode-set! mem (addr 1) (car inputs))
                     (set-vm-inputs! machine (cdr inputs))
                     (set-vm-ip! machine (+ ip 2))
                     'ran))]
          [(4) (set-vm-ip! machine (+ ip 2))
               `(output ,(val 1))]
          [(5) (set-vm-ip! machine (if (not (zero? (val 1))) (val 2) (+ ip 3)))
               'ran]
          [(6) (set-vm-ip! machine (if (zero? (val 1))       (val 2) (+ ip 3)))
               'ran]
          [(7) (d05:intcode-set! mem (addr 3) (if (< (val 1) (val 2)) 1 0))
               (set-vm-ip! machine (+ ip 4))
               'ran]
          [(8) (d05:intcode-set! mem (addr 3) (if (= (val 1) (val 2)) 1 0))
               (set-vm-ip! machine (+ ip 4))
               'ran]
          [(99) (set-vm-halted?! machine #t)
                'halted]
          [else (error 'vm-step! "unknown opcode ~a at position ~a" op ip)]))))

(define (vm-all-halted? vms)
  (for/and ([vm (in-list vms)]) (vm-halted? vm)))

(define (vm-enqueue! vm n)
  (set-vm-inputs! vm (append (vm-inputs vm) (list n))))

;; Feedback loop for one phase permutation. Each amp reads its phase on the
;; first opcode-3, then only signals. Amp A is seeded with the initial `0`
;; after its phase; E's outputs enqueue on A and become the thruster signal.
(define (thruster-feedback program phases)
  (define vms
    (for/list ([phase (in-list phases)] [i (in-naturals)])
      (vm (d05:intcode-mem program) 0
          (if (zero? i) (list phase 0) (list phase))
          #f)))
  (let loop ([thruster #f])
    (cond
      [(vm-all-halted? vms) thruster]
      [else
       (define-values (progressed? new-thruster)
         (for/fold ([progressed? #f] [thruster thruster])
                   ([i (in-range (length vms))] [machine (in-list vms)])
           (if (vm-halted? machine)
               (values progressed? thruster)
               (let loop-amp ([progressed? progressed?] [thruster thruster])
                 (if (vm-halted? machine)
                     (values progressed? thruster)
                     (match (vm-step! machine)
                       ['blocked (values progressed? thruster)]
                       ['ran (loop-amp #t thruster)]
                       ['halted (values #t thruster)]
                       [`(output ,n)
                        (if (= i 4)
                            (begin
                              (vm-enqueue! (list-ref vms 0) n)
                              (values #t n))
                            (begin
                              (vm-enqueue! (list-ref vms (+ i 1)) n)
                              (values #t thruster)))]))))))
       (unless progressed?
         (error 'thruster-feedback "deadlock with phases ~a" phases))
       (loop new-thruster)])))

;; Brute-force all 5! = 120 phase orderings; take the maximum thruster signal.
(define (part1 program)
  (apply max (for/list ([phases (in-list (permutations '(0 1 2 3 4)))])
               (thruster-series program phases))))

(define (part2 program)
  (apply max (for/list ([phases (in-list (permutations '(5 6 7 8 9)))])
               (thruster-feedback program phases))))

(define (solve contents)
  (define program (parse-input contents))
  (printf "  part 1: ~a\n" (part1 program))
  (printf "  part 2: ~a\n" (part2 program)))

(module+ main
  (solve (read-day-input 7)))
