#lang racket/base

;; Tests for Day 13 — Care Package.
;;
;; The VM itself is not re-pinned here: `src/intcode.rkt` is
;; [Day 11](../Problem_Statements/days/day11_function_guide.md)'s `vm-step!`
;; moved verbatim, and its opcode semantics are already nailed down by Day 9's
;; quine and Day 7's feedback loop. What's new on Day 13 is the *peripheral*,
;; so that's what's tested:
;;
;;   1. framing the flat output stream into (x, y, tile) triples, against the
;;      puzzle prose's own `1,2,3,6,5,4` example;
;;   2. "screen when the game exits" — a redrawn cell replaces, not appends;
;;   3. `render`'s glyph mapping;
;;   4. the `(-1, 0, v)` sentinel routing to the score instead of to a tile;
;;   5. the joystick controller's sign convention, driven by a scripted
;;      cabinet that draws a ball and a paddle and then echoes back whatever
;;      the joystick said;
;;   6. the free-play poke actually reaching memory address 0;
;;   7. the real answers for inputs/day13.txt, plus the starting board's tile
;;      histogram and geometry (a framing bug that shifted every triple by one
;;      would still yield a plausible-looking block count, but it cannot
;;      survive an exact 40x25 / 88-wall / one-ball-one-paddle check).
;;
;; Every scripted program below uses `104` (output-immediate) so the fixtures
;; read as literal display commands rather than as Intcode puzzles of their own.
;;
;; Run with:  raco test test/day13-test.rkt

(require rackunit
         racket/string
         "../src/aoc.rkt"
         "../src/day13.rkt")

(module+ test

  ;; --- 1. framing: the prose's worked example ---
  ;;
  ;; "a sequence of output values like 1,2,3,6,5,4 would draw a horizontal
  ;; paddle tile (1 from the left, 2 from the top) and a ball tile (6 from
  ;; the left, 5 from the top)."
  (define prose-example
    (list->vector '(104 1 104 2 104 3
                    104 6 104 5 104 4
                    99)))

  (check-equal? (screen prose-example)
                (hash (cons 1 2) 3 (cons 6 5) 4)
                "1,2,3,6,5,4 = paddle at (1,2), ball at (6,5)")

  ;; --- 2. the screen is the final frame, not a draw log ---
  ;;
  ;; Two blocks drawn, then (0,0) redrawn as empty. If draws accumulated
  ;; instead of overwriting, the block count would still read 2.
  (define redrawn
    (list->vector '(104 0 104 0 104 2      ; block at (0,0)
                    104 1 104 0 104 2      ; block at (1,0)
                    104 0 104 0 104 0      ; (0,0) cleared
                    99)))

  (define board (screen redrawn))
  (check-equal? (hash-count board) 2 "two distinct coordinates were drawn")
  (check-equal? (count-tiles board 2) 1 "the cleared block is no longer a block")
  (check-equal? (count-tiles board 0) 1 "and reads as empty instead")

  ;; --- 3. render: one glyph per tile id, over the drawn bounding box ---
  (check-equal? (render (hash (cons 0 0) 1 (cons 1 0) 2
                              (cons 0 1) 4 (cons 1 1) 3))
                "█#\no="
                "wall/block on row 0, ball/paddle on row 1")
  (check-equal? (render (hash)) "" "nothing drawn renders as the empty string")

  ;; --- 4. the (-1, 0) sentinel is a score, not a tile ---
  ;;
  ;; `#:quarters #f` suppresses the free-play poke so these scripted programs
  ;; keep their own instruction at address 0.
  (define score-only
    (list->vector '(104 -1 104 0 104 12345
                    99)))

  (check-equal? (play score-only #:quarters #f) 12345
                "prose: \"-1,0,12345 would show 12345 as the player's score\"")

  ;; A later score supersedes an earlier one; the answer is the last value.
  (check-equal? (play (list->vector '(104 -1 104 0 104 7
                                      104 -1 104 0 104 99
                                      99))
                      #:quarters #f)
                99
                "the reported score is the most recent one, at halt")

  ;; --- 5. the joystick: sgn(ball - paddle) ---
  ;;
  ;; A scripted cabinet: draw the ball at `ball-x`, draw the paddle at
  ;; `paddle-x`, read the joystick into scratch cell 100 (past the end of the
  ;; program — grow-on-write memory handles it), then emit it back as the
  ;; score. So `play`'s return value here IS the joystick reading.
  (define (joystick-probe ball-x paddle-x)
    (list->vector
     (list 104 ball-x   104 10 104 4     ; ball   at (ball-x, 10)
           104 paddle-x 104 11 104 3     ; paddle at (paddle-x, 11)
           3 100                         ; read joystick -> mem[100]
           104 -1 104 0 4 100            ; report it as the score
           99)))

  (check-equal? (play (joystick-probe 5 2) #:quarters #f) 1
                "ball right of paddle: tilt right (+1)")
  (check-equal? (play (joystick-probe 2 5) #:quarters #f) -1
                "ball left of paddle: tilt left (-1)")
  (check-equal? (play (joystick-probe 4 4) #:quarters #f) 0
                "ball above paddle: neutral (0)")

  ;; --- 6. the free-play poke lands on memory address 0 ---
  ;;
  ;; As written, address 0 holds 99 and the program halts immediately with no
  ;; score. Poking 2 there turns it into `2,0,0,0` (a multiply into cell 0),
  ;; after which control falls into the display commands at address 4. Same
  ;; bytes, two behaviors — which is exactly the puzzle's own trick.
  (define quarter-gated
    (list->vector '(99 0 0 0
                    104 -1 104 0 104 42
                    99)))

  (check-equal? (play quarter-gated #:quarters #f) 0
                "unpoked: address 0 is HALT, the game never starts")
  (check-equal? (play quarter-gated) 42
                "poked with 2: the cabinet runs and reports its score")

  ;; --- 7. the real puzzle input ---
  (define program (parse-input (read-day-input 13)))
  (define start (screen program))

  (check-equal? (part1 program) 348 "part 1 (block tiles on the starting screen)")
  (check-equal? (part2 program) 16999 "part 2 (score after the last block breaks)")

  ;; Geometry of the starting board: a 40x25 screen, fully drawn (1000 cells,
  ;; one draw command each), 88 walls, exactly one ball and one paddle.
  (check-equal? (hash-count start) 1000 "40 x 25 = 1000 cells, all drawn")
  (check-equal? (add1 (apply max (map car (hash-keys start)))) 40 "screen width")
  (check-equal? (add1 (apply max (map cdr (hash-keys start)))) 25 "screen height")
  (check-equal? (count-tiles start 1) 88 "wall tiles")
  (check-equal? (count-tiles start 3) 1 "exactly one paddle")
  (check-equal? (count-tiles start 4) 1 "exactly one ball")
  (check-equal? (+ (count-tiles start 0) (count-tiles start 1)
                   (count-tiles start 2) (count-tiles start 3)
                   (count-tiles start 4))
                1000
                "every cell holds a tile id in 0..4")

  ;; The ball starts up and to the LEFT of the paddle, so the very first
  ;; joystick reading of the real game is -1, not 0 — a controller that only
  ;; reacted after the ball moved would already be a frame behind.
  (check-equal? (for/first ([(pos id) (in-hash start)] #:when (= id 4)) pos)
                (cons 18 20)
                "ball starts at (18,20)")
  (check-equal? (for/first ([(pos id) (in-hash start)] #:when (= id 3)) pos)
                (cons 20 23)
                "paddle starts at (20,23)")

  ;; The rendered starting board's top row is solid wall, and the row holding
  ;; the ball has exactly one non-space glyph.
  (define rows (string-split (render start) "\n" #:trim? #f))
  (check-equal? (length rows) 25 "render emits one line per screen row")
  (check-equal? (string-ref (list-ref rows 0) 0) #\█ "top-left corner is wall")
  (check-equal? (string-ref (list-ref rows 20) 18) #\o "the ball is drawn at (18,20)"))
