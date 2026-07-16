#lang racket

;; AoC 2019 Day 11 — Space Police.
;;
;; The Intcode VM ([Day 9](day09_function_guide.md)) returns as a *painting
;; robot*: the program reads the color of the panel it's sitting on as input,
;; then emits two outputs — paint color, turn direction — before moving
;; forward one panel. This is the first Intcode day where the program's next
;; input depends on its *own* prior output (via the world it just painted),
;; so [Day 9](day09_function_guide.md)'s batch `run/inputs` (all inputs known
;; up front) can't drive it. Instead this day fuses two prior days:
;;
;;   * **Day 9's instruction set** — relative mode, opcode 9, growable
;;     memory — is exactly what the robot's program needs.
;;   * **Day 7's cooperative-pause `vm-step!`** — a single-step machine that
;;     returns `'blocked` on an empty input queue instead of erroring — is
;;     exactly the shape that lets the *caller* supply input just-in-time.
;;
;; So `vm-step!` here is Day 9's `val`/`addr` operand resolution (position /
;; immediate / relative) transplanted into Day 7's step-and-report loop. The
;; hull is a hash keyed by `(x . y)` (the Day 10 grid-bookkeeping warm-up),
;; defaulting to unpainted = black; painting is a hash-set, so revisiting a
;; panel just overwrites its color and the panel count is `hash-count`.
;;
;; Part 1 starts the robot on a black hull and counts panels painted at
;; least once. Part 2 starts it on one white panel instead; the hull it
;; paints spells an 8-letter registration code, which `render` draws as a
;; `#`/`.` grid for a human to read — no OCR, matching the stance the 2018
;; Haskell repo's Day 10 ("The Stars Align") took on the identical
;; render-letters-for-a-human sub-problem: the rendering *is* the answer.

(require "aoc.rkt"
         (prefix-in d05: "day05.rkt"))

(provide
 (contract-out
  [parse-input (-> string? (vectorof exact-integer?))]
  [paint-hull  (->* ((vectorof exact-integer?)) ((integer-in 0 1))
                    (hash/c (cons/c exact-integer? exact-integer?) (integer-in 0 1)))]
  [render      (-> (hash/c (cons/c exact-integer? exact-integer?) (integer-in 0 1)) string?)]
  [part1       (-> (vectorof exact-integer?) exact-nonnegative-integer?)]
  [part2       (-> (vectorof exact-integer?) string?)]
  [solve       (-> string? void?)]))

(define parse-input d05:parse-input)

;; --- the Intcode VM, as a resumable single-step machine ---

;; `mem` is a box (Day 5's grow-on-write memory); `rb` is the relative base
;; (Day 9); `inputs` is a pending-input queue that's empty except for the one
;; instant between the caller noticing a `'blocked` and enqueuing a reply.
(struct vm (mem ip rb inputs halted?) #:mutable)

(define (make-vm program) (vm (d05:intcode-mem program) 0 0 '() #f))

(define (vm-enqueue! machine n)
  (set-vm-inputs! machine (append (vm-inputs machine) (list n))))

;; One instruction. Returns:
;;   'blocked      — opcode 3 with an empty input queue (caller must enqueue)
;;   'ran          — any other instruction advanced the machine
;;   `(output ,n)  — opcode 4 emitted `n`
;;   'halted       — opcode 99 (idempotent: stepping a halted machine again
;;                   just reports 'halted, so the driving loop below doesn't
;;                   need a separate halted? check)
;;
;; The eight arithmetic/jump handlers are byte-for-byte Day 7's; the only
;; changes are Day 9's operand seam (`val`/`addr` grow a relative-mode
;; clause) and the new opcode 9. Same split Day 9's guide draws out: adding
;; an addressing mode touches operand resolution and nothing else.
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
            [(0) (d05:intcode-ref mem raw)]
            [(1) raw]
            [(2) (d05:intcode-ref mem (+ (vm-rb machine) raw))]))
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

;; --- the hull-painting robot ---

;; Facing, clockwise, indices 0..3 — same up/right/down/left cycle and
;; screen-coords-y-grows-down convention as Day 10's laser-angle sweep.
(define dirs (vector (cons 0 -1) (cons 1 0) (cons 0 1) (cons -1 0)))

;; signal 0 = turn left (CCW, -1 mod 4), 1 = turn right (CW, +1 mod 4).
(define (turn dir signal) (modulo (+ dir (if (zero? signal) 3 1)) 4))

(define (step-forward pos dir)
  (define d (vector-ref dirs dir))
  (cons (+ (car pos) (car d)) (+ (cdr pos) (cdr d))))

;; Feed `camera` to `machine` the instant it blocks wanting input, and collect
;; outputs until a (paint, turn) pair is complete or the machine halts first
;; (returning fewer than 2 outputs, which the caller treats as "done").
(define (run-to-outputs! machine camera)
  (let loop ([outs '()])
    (match (vm-step! machine)
      ['blocked (vm-enqueue! machine camera) (loop outs)]
      ['ran (loop outs)]
      [`(output ,n)
       (define outs* (cons n outs))
       (if (= 2 (length outs*)) (reverse outs*) (loop outs*))]
      ['halted (reverse outs)])))

;; Run `program` as the hull-painting robot from (0,0) facing up, and return
;; the final panel->color hash. `start-color` is the color of panel (0,0)
;; *before* the robot has painted anything — Part 1's hull starts all black
;; (the default, 0), Part 2's starts with that one panel white (1). It is
;; only ever consulted on the very first camera read: `panels` itself starts
;; empty (no pre-seeded key), so a panel — including (0,0) — gets a key only
;; once the robot's program explicitly paints it via `hash-set`.
;;
;; That "empty hash, one conditional default" choice is what makes
;; `hash-count` exactly "panels painted at least once": a panel that was
;; never painted has no key (reads as its default color but was never
;; *painted*); a repainted panel just keeps its latest color under the same
;; key — matching the puzzle's own clarification that a twice-painted
;; starting panel counts once and a never-repainted final panel still counts
;; if it was ever painted.
(define (paint-hull program [start-color 0])
  (define machine (make-vm program))
  (define start (cons 0 0))
  (let loop ([pos start] [dir 0] [panels (hash)])
    (define default (if (equal? pos start) start-color 0))
    (define outs (run-to-outputs! machine (hash-ref panels pos default)))
    (if (< (length outs) 2)
        panels
        (let* ([panels* (hash-set panels pos (car outs))]
               [dir*     (turn dir (cadr outs))])
          (loop (step-forward pos dir*) dir* panels*)))))

(define (part1 program) (hash-count (paint-hull program)))

;; Render the white (1) panels of `panels` as a `#`/`.` grid, one row per y
;; from the topmost painted row to the bottommost — the same bounding-box-
;; over-lit-cells approach as the 2018 Haskell repo's Day 10 `render`. No
;; letter decoder: the grid IS the answer, read by a human.
(define (render panels)
  (define whites (for/list ([(pos color) (in-hash panels)] #:when (= color 1)) pos))
  (cond
    [(null? whites) ""]
    [else
     (define xs (map car whites))
     (define ys (map cdr whites))
     (define x0 (apply min xs)) (define x1 (apply max xs))
     (define y0 (apply min ys)) (define y1 (apply max ys))
     (string-join
      (for/list ([y (in-range y0 (add1 y1))])
        (list->string
         (for/list ([x (in-range x0 (add1 x1))])
           (if (= 1 (hash-ref panels (cons x y) 0)) #\# #\.))))
      "\n")]))

;; Part 2: start the robot on one white panel; the registration code is
;; spelled out in the panels it paints white.
(define (part2 program) (render (paint-hull program 1)))

;; Dispatcher: parse once, print both parts. Part 2's answer is a multi-line
;; picture, so it's indented onto its own lines rather than inlined.
(define (solve contents)
  (define program (parse-input contents))
  (printf "  part 1: ~a\n" (part1 program))
  (printf "  part 2:\n")
  (for ([line (in-list (string-split (part2 program) "\n"))])
    (printf "    ~a\n" line)))

(module+ main
  (solve (read-day-input 11)))
