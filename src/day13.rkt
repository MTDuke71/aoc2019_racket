#lang racket

;; AoC 2019 Day 13 — Care Package.
;;
;; The Intcode VM ([Day 9](day09_function_guide.md), driven with
;; [Day 7](day07_function_guide.md)'s block/resume protocol) becomes an
;; *arcade cabinet*. Nothing about the machine changes — the instruction set
;; froze at Day 9, and this is the first day where the VM is imported as a
;; library (`intcode.rkt`) rather than re-derived. The whole day is the
;; peripheral you wire to it:
;;
;;   * **Output is a display protocol.** The program emits a flat stream of
;;     integers that is really a stream of *3-tuples*: `x`, `y`, `tile-id`.
;;     Framing that stream — chunking by 3 — is the entire Part 1 problem.
;;     Tiles: 0 empty, 1 wall, 2 block, 3 paddle, 4 ball.
;;   * **One out-of-band tuple.** Part 2 overloads the same channel: a tuple
;;     whose `(x, y)` is the *impossible* screen position `(-1, 0)` carries
;;     the score, not a tile. This is a sentinel-tagged union smuggled through
;;     an untyped wire — see the guide's "the escape hatch is a coordinate".
;;   * **Input is a control loop.** Part 2 sets memory address 0 to 2 (insert
;;     two quarters, free play), and the program now *reads* the joystick:
;;     -1 left, 0 neutral, 1 right. The reply has to be computed from the
;;     world the program itself just drew, which is exactly why the VM must
;;     be resumable rather than fed a precomputed input list.
;;
;; Part 1 counts block tiles on the screen when the game exits. Part 2 plays
;; the game to completion and reports the final score. The player is one
;; line: `(sgn (- ball paddle))` — keep the paddle under the ball. The guide
;; argues why that greedy tracking controller is not just adequate but
;; *optimal* here, and what would break it.

(require "aoc.rkt"
         "intcode.rkt"
         (prefix-in d05: "day05.rkt"))

(define tile-id/c (integer-in 0 4))
(define point/c (cons/c exact-integer? exact-integer?))
(define screen/c (hash/c point/c tile-id/c))

(provide
 (contract-out
  [parse-input (-> string? (vectorof exact-integer?))]
  [screen      (-> (vectorof exact-integer?) screen/c)]
  [render      (-> screen/c string?)]
  [count-tiles (-> screen/c tile-id/c exact-nonnegative-integer?)]
  [play        (->* ((vectorof exact-integer?))
                    (#:quarters (or/c #f exact-integer?))
                    exact-integer?)]
  [part1       (-> (vectorof exact-integer?) exact-nonnegative-integer?)]
  [part2       (-> (vectorof exact-integer?) exact-integer?)]
  [solve       (-> string? void?)]))

(define parse-input d05:parse-input)

;; --- tile vocabulary ---

(define EMPTY  0)
(define WALL   1)
(define BLOCK  2)
(define PADDLE 3)
(define BALL   4)

;; --- the display protocol: chunk the output stream into 3-tuples ---

;; Step `machine` until it has emitted three values (one complete draw
;; command) or halted, whichever comes first. Returns `(list x y id)` or #f
;; on halt.
;;
;; `joystick` is a *thunk*, not a value: it is called at the instant the
;; machine blocks on opcode 3, so it sees the caller's most recent world
;; state rather than a snapshot taken before the frame was drawn. That one
;; detail is why the paddle can react to the ball within the same frame.
;;
;; A trailing partial tuple (1 or 2 outputs then halt) can't happen with a
;; well-formed cabinet; treating halt as end-of-stream regardless keeps the
;; driver total instead of erroring on a malformed program.
(define (next-command! machine joystick)
  (let loop ([outs '()])
    (match (vm-step! machine)
      ['blocked (vm-enqueue! machine (joystick)) (loop outs)]
      ['ran     (loop outs)]
      [`(output ,n)
       (define outs* (cons n outs))
       (if (= 3 (length outs*)) (reverse outs*) (loop outs*))]
      ['halted  #f])))

;; A joystick for a machine that should never ask for one — Part 1 runs the
;; cabinet with its single default quarter, so it draws the board and halts
;; without reading input. If it ever does read, that's a real bug, not a
;; value to guess at.
(define (no-joystick)
  (error 'screen "the cabinet asked for joystick input before free play"))

;; --- Part 1: draw the board, count the blocks ---

;; Run `program` to completion and return the final screen as a
;; `(x . y)` -> tile-id hash. Later draws overwrite earlier ones at the same
;; coordinate — that's what makes this the screen "when the game exits"
;; rather than a log of everything ever drawn.
(define (screen program)
  (define machine (make-vm program))
  (let loop ([tiles (hash)])
    (match (next-command! machine no-joystick)
      [#f tiles]
      [(list x y id) (loop (hash-set tiles (cons x y) id))])))

(define (count-tiles tiles id)
  (for/sum ([t (in-hash-values tiles)]) (if (= t id) 1 0)))

(define (part1 program) (count-tiles (screen program) BLOCK))

;; --- rendering (for the human, not for the answer) ---

(define glyphs (hash EMPTY #\space WALL #\█ BLOCK #\# PADDLE #\= BALL #\o))

;; Draw the screen as text over the bounding box of the drawn tiles. Same
;; bounding-box-over-a-sparse-hash shape as
;; [Day 11](day11_function_guide.md)'s `render`, but every cell here is
;; drawn (walls included), so the box is the whole cabinet screen.
(define (render tiles)
  (cond
    [(zero? (hash-count tiles)) ""]
    [else
     (define xs (map car (hash-keys tiles)))
     (define ys (map cdr (hash-keys tiles)))
     (string-join
      (for/list ([y (in-range (apply min ys) (add1 (apply max ys)))])
        (list->string
         (for/list ([x (in-range (apply min xs) (add1 (apply max xs)))])
           (hash-ref glyphs (hash-ref tiles (cons x y) EMPTY)))))
      "\n")]))

;; --- Part 2: play the game ---

;; Play `program` to completion and return the final score.
;;
;; `#:quarters` is the value poked into memory address 0 before the first
;; instruction: 2 is the puzzle's free-play patch. Passing #f skips the poke
;; entirely, which is how the tests drive scripted cabinets whose address 0
;; is a real instruction.
;;
;; The loop carries exactly three integers: the latest `score`, and the
;; ball's and paddle's current *x*. It does NOT keep the screen — playing
;; needs no map of the board at all. The paddle moves only horizontally, so
;; the y of everything is irrelevant, and the blocks are irrelevant too:
;; they break on contact whether or not the player knows where they are.
;; A 1000-cell screen collapses to three numbers.
;;
;; Two subtleties, both about the sentinel tuple:
;;   * `(-1, 0, v)` sets the score. It has to be matched *before* the general
;;     tile clause, or `x = -1` would be read as a tile position.
;;   * The score is reported at halt, so the value returned is the score
;;     after the last block is broken (the program stops once the board is
;;     clear — or once the ball is missed, which the tracking joystick below
;;     never allows).
(define (play program #:quarters [quarters 2])
  (define machine (make-vm program))
  (when quarters (vm-poke! machine 0 quarters))
  (let loop ([score 0] [ball 0] [paddle 0])
    ;; The controller: chase the ball. Evaluated lazily, at block time, so
    ;; `ball` and `paddle` are as fresh as the frame just drawn.
    (match (next-command! machine (lambda () (sgn (- ball paddle))))
      [#f score]
      [(list -1 0 v) (loop v ball paddle)]
      [(list x _ id)
       (loop score
             (if (= id BALL)   x ball)
             (if (= id PADDLE) x paddle))])))

(define (part2 program) (play program))

;; Dispatcher: parse once, print both parts. The starting screen is printed
;; between them — it isn't an answer, but it's the picture that makes the
;; block count mean something (and it's how you'd notice a framing bug).
(define (solve contents)
  (define program (parse-input contents))
  (define board (screen program))
  (printf "  part 1: ~a\n" (count-tiles board BLOCK))
  (printf "  starting screen (~a x ~a):\n"
          (add1 (apply max (map car (hash-keys board))))
          (add1 (apply max (map cdr (hash-keys board)))))
  (for ([line (in-list (string-split (render board) "\n"))])
    (printf "    ~a\n" line))
  (printf "  part 2: ~a\n" (part2 program)))

(module+ main
  (solve (read-day-input 13)))
