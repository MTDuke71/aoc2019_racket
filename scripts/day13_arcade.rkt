#lang racket

;; Day 13 — watching the arcade cabinet run. Two peripherals, one driver.
;;
;;   racket scripts/day13_arcade.rkt              window, the AI plays
;;   racket scripts/day13_arcade.rkt --human      window, YOU play (arrow keys)
;;   racket scripts/day13_arcade.rkt --terminal   ANSI animation in the console
;;
;; Both peripherals open on the *starting board* and wait — any key in the
;; window, Enter in the terminal — and both hold the final frame until they are
;; dismissed, so neither the opening nor the ending flashes past.
;;
;; Why this file is short: [src/day13.rkt](../src/day13.rkt) already made the
;; only decision that matters for a UI. Its `next-command!` takes the joystick
;; as a **thunk**, evaluated at the instant the machine blocks on opcode 3 —
;; not as a value computed in advance. That means "who plays" is a parameter,
;; not a rewrite:
;;
;;   (lambda () (sgn (- ball paddle)))     the tracking controller (the solve)
;;   (lambda () (unbox key-direction))     a human at the keyboard (this file)
;;
;; Nothing about the VM ([src/intcode.rkt](../src/intcode.rkt)), the framing of
;; the output stream, or the block/resume protocol changes. The cabinet cannot
;; tell the difference.
;;
;; A "frame" is also already well defined, which is the other thing a UI needs:
;; the draw commands between two joystick reads are exactly one game tick, so
;; there is no guessing about when the picture is complete. The disassembly
;; ([Problem_Statements/days/day13_disassembly.md](../Problem_Statements/days/day13_disassembly.md))
;; explains why: the program's `draw(x, y, tile)` subroutine at address 549
;; emits its three outputs *inside* the routine that stores to the screen
;; array, so the output stream is a write-through log of a memory-mapped
;; display. Every draw command is a complete cell update, and no partial
;; triple can ever be pending when the machine stops to ask for input.
;;
;; The `cab` struct below is the same idea generalised: one driver, plus an
;; `on-draw` callback that fires for every cell update. The terminal renderer
;; ignores it and redraws wholesale; the window renderer uses it to patch its
;; cached background. That callback is this file's version of the cabinet's
;; own write-through display.

(require racket/runtime-path
         2htdp/image
         2htdp/universe
         (prefix-in d05: "../src/day05.rkt")
         "../src/intcode.rkt")

(define-runtime-path here ".")

;; ===========================================================================
;; THE DRIVER — shared by both peripherals
;; ===========================================================================

;; `machine` is the resumable VM; everything else is the world it draws.
;; `pending` holds 0, 1 or 2 outputs of an incomplete (x, y, tile) triple.
;; `ball`/`bally`/`paddle` are tracked as draw commands arrive rather than
;; searched for in `screen`, because the joystick has to answer in constant
;; time. (src/day13.rkt's `play` tracks only the two *x* values — a renderer
;; needs the ball's y as well, which is the whole of the difference between
;; solving this day and watching it.)
;; `on-draw` : (x y new-tile old-tile) -> void, called after `screen` updates.
(struct cab (machine
             [screen  #:mutable] [score  #:mutable] [pending #:mutable]
             [ball    #:mutable] [bally  #:mutable] [paddle  #:mutable]
             [ticks   #:mutable] [halted? #:mutable]
             on-draw))

(define (make-cabinet program #:quarters [quarters 2] #:on-draw [on-draw void])
  (define machine (make-vm program))
  (when quarters (vm-poke! machine 0 quarters))
  (cab machine (hash) 0 '() 0 0 0 0 #f on-draw))

;; Absorb one output value. Completing a triple either sets the score (the
;; `(-1, 0, v)` sentinel) or updates one screen cell.
(define (absorb! c n)
  (define p (cons n (cab-pending c)))
  (cond
    [(< (length p) 3) (set-cab-pending! c p)]
    [else
     (set-cab-pending! c '())
     (match-define (list x y v) (reverse p))
     (cond
       [(and (= x -1) (= y 0)) (set-cab-score! c v)]
       [else
        (define old (hash-ref (cab-screen c) (cons x y) #f))
        (set-cab-screen! c (hash-set (cab-screen c) (cons x y) v))
        (when (= v 4) (set-cab-ball! c x) (set-cab-bally! c y))
        (when (= v 3) (set-cab-paddle! c x))
        ((cab-on-draw c) x y v old)])]))

;; Run one game tick: step until the machine asks for the joystick, hand it
;; `(joystick c)` at that instant, then step on until it asks again (or halts).
;; Returns the cabinet, mutated.
;;
;; The first call also absorbs the 1,000-command initial repaint, since that
;; happens before the program's first opcode 3.
(define (tick! c joystick)
  (let loop ([fed? #f])
    (match (vm-step! (cab-machine c))
      ['blocked
       (cond
         [fed? c]                            ; asking again → this frame is done
         [else (vm-enqueue! (cab-machine c) (joystick c))
               (set-cab-ticks! c (add1 (cab-ticks c)))
               (loop #t)])]
      ['ran (loop fed?)]
      [`(output ,n) (absorb! c n) (loop fed?)]
      ['halted (set-cab-halted?! c #t) c])))

;; Step until the machine *first* asks for the joystick, absorbing the opening
;; 1,000-command repaint but playing no tick. That leaves a complete starting
;; board to show while the viewer waits for the go-ahead. (Without this, the
;; opening board and the first tick arrive together in `tick!`.)
(define (prime! c)
  (let loop ()
    (match (vm-step! (cab-machine c))
      ['blocked c]
      ['ran (loop)]
      [`(output ,n) (absorb! c n) (loop)]
      ['halted (set-cab-halted?! c #t) c])))

;; The solution's controller, verbatim: chase the ball.
(define (ai-joystick c) (sgn (- (cab-ball c) (cab-paddle c))))

(define (blocks-left c)
  (for/sum ([t (in-hash-values (cab-screen c))]) (if (= t 2) 1 0)))

(provide (struct-out cab) make-cabinet prime! tick! ai-joystick blocks-left)

;; ===========================================================================
;; PERIPHERAL 1 — the terminal
;; ===========================================================================
;;
;; ANSI: `\e[2J` clear, `\e[H` cursor home, `\e[?25l/h` hide/show cursor.
;; Redrawing from home (rather than clearing each frame) avoids flicker.
;; Keyboard input is not portable without raw-mode support, so the terminal
;; peripheral is watch-only — the AI plays.

(define (run-terminal program #:fps [fps 30] #:speed [speed 2])
  (define c (make-cabinet program))
  (printf "\e[2J\e[?25l")
  ;; `\e[J` erases from the cursor down, so a prompt printed under one frame is
  ;; wiped by the next one instead of lingering below a shorter redraw.
  (define (paint!)
    (printf "\e[H")
    (printf "AoC 2019 Day 13 — the AI plays  (tick ~a)\n\n"
            (~a (cab-ticks c) #:min-width 5 #:align 'right))
    (displayln (d13-render (cab-screen c)))
    (printf "\n  score ~a    blocks left ~a\n\e[J"
            (~a (cab-score c) #:min-width 6)
            (~a (blocks-left c) #:min-width 4))
    (flush-output))
  ;; Show the starting board and wait, so the opening frame is readable rather
  ;; than gone in one tick. `read-line` returns eof immediately on a piped or
  ;; closed stdin, which keeps the script usable non-interactively.
  (prime! c)
  (paint!)
  (printf "\n  Press Enter to start… ")
  (flush-output)
  (void (read-line))
  (let loop ()
    (for ([_ (in-range speed)] #:break (cab-halted? c))
      (tick! c ai-joystick))
    (paint!)
    (when (positive? fps) (sleep (/ 1.0 fps)))
    (unless (cab-halted? c) (loop)))
  (printf "\e[?25h")
  (printf "\n  ~a  final score ~a after ~a ticks.\n"
          (if (zero? (blocks-left c)) "CLEARED." "Ball missed —")
          (cab-score c) (cab-ticks c))
  (printf "  Press Enter to exit… ")
  (flush-output)
  (void (read-line))
  (newline))

;; src/day13.rkt's `render`, inlined rather than imported, because that one is
;; contracted to a complete `screen/c` hash and this one has to survive being
;; called mid-frame, before the first repaint has drawn every cell.
(define glyphs (hash 0 #\space 1 #\█ 2 #\# 3 #\= 4 #\o))

(define (d13-render tiles)
  (cond
    [(zero? (hash-count tiles)) ""]
    [else
     (define xs (map car (hash-keys tiles)))
     (define ys (map cdr (hash-keys tiles)))
     (string-join
      (for/list ([y (in-range (max 0 (apply min ys)) (add1 (apply max ys)))])
        (list->string
         (for/list ([x (in-range (max 0 (apply min xs)) (add1 (apply max xs)))])
           (hash-ref glyphs (hash-ref tiles (cons x y) 0) #\space))))
      "\n")]))

;; ===========================================================================
;; PERIPHERAL 2 — a window, via 2htdp/universe
;; ===========================================================================
;;
;; `big-bang` is HtDP's world-programming loop: a value, a clock, and three
;; handlers (`on-tick`, `on-key`, `to-draw`) that map world -> world or
;; world -> image. It ships with Racket, so this needs no packages.
;;
;; The impedance mismatch worth naming: big-bang's world is meant to be a
;; *functional* value that each handler replaces, while `cab` is a mutable
;; struct wrapped around a mutable VM. Racket lets the handlers return the
;; same (mutated) struct, so the loop works — but the shape is a lie about
;; where the state lives. The honest reading is that big-bang here is being
;; used as an event loop, not as a world machine, which is exactly what an
;; emulator front-end is. (A `racket/gui` canvas with a timer would say the
;; same thing without the pretence, at ~2x the code.)
;;
;; Rendering cost: `place-image` is lazy (a 440-image composite builds in ~3
;; ms), but rasterising that composite costs ~25 ms more per frame than
;; blitting a pre-`freeze`d bitmap, and 25 ms will not hold 30 fps. So the
;; walls and blocks are composed once and
;; `freeze`d into a single bitmap, and the `on-draw` callback patches that
;; bitmap in place when a block is broken — one composite per break, 348 per
;; game, instead of 440 per frame. Ball and paddle are drawn on top as sprites.
;; This is the classic background/sprite split, and the cabinet's own
;; write-through display protocol is what makes it possible: the program tells
;; us exactly which cell changed.

(define CELL 18)

(define (cell-image id heat-color)
  (define s (- CELL 2))
  (case id
    [(1) (rectangle CELL CELL "solid" "dimgray")]                ; wall
    [(2) (overlay (rectangle (- s 2) (- s 4) "solid" (or heat-color "steelblue"))
                  (rectangle CELL CELL "solid" "black"))]        ; block
    [(3) (overlay (rectangle s 6 "solid" "gold")
                  (rectangle CELL CELL "solid" "black"))]        ; paddle
    [(4) (overlay (circle (quotient s 2) "solid" "white")
                  (rectangle CELL CELL "solid" "black"))]        ; ball
    [else (rectangle CELL CELL "solid" "black")]))

(define (cell-x x) (+ (* x CELL) (quotient CELL 2)))
(define (cell-y y) (+ (* y CELL) (quotient CELL 2)))

;; Blocks coloured by the point value the disassembly recovered from the
;; program's hidden table: slot(x,y) = tbase + ((25x + y)*a + c) mod m.
;; Cheap tiles cold, expensive tiles hot — the score map made visible while
;; you play it. See day13_disassembly.md, "The hidden score map".
(define (heat-palette program)
  (define (const a) (vector-ref program a))
  (lambda (x y)
    (define slot (+ (const 632)
                    (modulo (+ (* (+ (* (const 604) x) y) (const 613)) (const 616))
                            (const 621))))
    (define v (vector-ref program slot))            ; 1..98
    (make-color (min 255 (+ 40 (* 2 v))) 60 (max 0 (- 220 (* 2 v))))))

;; Walls + blocks, composed once and flattened to a bitmap.
(define (build-background screen palette W H)
  (freeze
   (for*/fold ([img (empty-scene (* W CELL) (* H CELL) "black")])
              ([y (in-range H)] [x (in-range W)])
     (define t (hash-ref screen (cons x y) 0))
     (if (memv t '(1 2))
         (place-image (cell-image t (and palette (palette x y))) (cell-x x) (cell-y y) img)
         img))))

;; One frame: the cached background bitmap plus the two sprites, optionally
;; under a banner. Hoisted out of `run-window` so a headless script can
;; snapshot frames to PNG without opening a window.
(define (frame-image c bg [banner #f])
  (define board
    (place-image (cell-image 4 #f) (cell-x (cab-ball c)) (cell-y (cab-bally c))
                 (place-image (cell-image 3 #f) (cell-x (cab-paddle c)) (cell-y 23)
                              bg)))
  (cond
    [(not banner) board]
    [else
     ;; `above` pads with transparency, which leaves light text unreadable when
     ;; the window is saved or composited — give the banner its own black bar.
     (above (overlay/align
             "left" "middle"
             (beside (rectangle 10 1 "solid" "black") banner)
             (rectangle (image-width board) (+ 10 (image-height banner))
                        "solid" "black"))
            board)]))

(provide cell-image cell-x cell-y build-background heat-palette frame-image CELL)

(define (run-window program #:human? [human? #f] #:speed [speed 2]
                    #:fps [fps 30] #:heat? [heat? #f])
  (define W 40) (define H 25)
  (define palette (and heat? (heat-palette program)))
  (define bg (box #f))
  (define stick (box 0))                 ; the human's current key direction
  (define auto? (box (not human?)))
  ;; Every broken block patches the cached background: draw an empty cell over
  ;; it and re-freeze. Ball/paddle updates are ignored here — they are sprites.
  (define (on-draw x y new old)
    (when (and (equal? old 2) (= new 0) (unbox bg))
      (set-box! bg (freeze (place-image (cell-image 0 #f) (cell-x x) (cell-y y)
                                        (unbox bg))))))
  (define c (make-cabinet program #:on-draw on-draw))
  (define started? (box #f))             ; the opening board holds until a key
  (define quit? (box #f))                ; the ONLY thing that stops big-bang
  ;; Absorb the opening repaint and flatten it into the cached background
  ;; before the window opens, so the first thing shown is the full board.
  (prime! c)
  (set-box! bg (build-background (cab-screen c) palette W H))
  (define (joystick c) (if (unbox auto?) (ai-joystick c) (unbox stick)))
  (define (advance c)
    (when (unbox started?)
      (for ([_ (in-range speed)] #:break (cab-halted? c)) (tick! c joystick)))
    c)
  (define (banner c)
    (above/align
     "left"
     (text (format "SCORE ~a     BLOCKS ~a     TICK ~a"
                   (cab-score c) (blocks-left c) (cab-ticks c))
           16 "white")
     (text (cond
             [(cab-halted? c)
              (if (zero? (blocks-left c))
                  "CLEARED — [q] or close the window to quit"
                  "BALL MISSED — [q] or close the window to quit")]
             [(not (unbox started?)) "press any key to start"]
             [(unbox auto?) "[a] you play   [q] quit          tracking controller"]
             [else "[<-] [->] move   [a] autopilot   [q] quit"])
           12 "gray")))
  (define blank (empty-scene (* W CELL) (* H CELL) "black"))
  (define (draw c) (frame-image c (or (unbox bg) blank) (banner c)))
  (define (key c k)
    (set-box! started? #t)               ; any key starts the game
    (cond
      [(key=? k "left")  (set-box! stick -1) (set-box! auto? #f) c]
      [(key=? k "right") (set-box! stick  1) (set-box! auto? #f) c]
      [(key=? k "a")     (set-box! auto? (not (unbox auto?))) c]
      [(key=? k "q")     (set-box! quit? #t) c]
      [else c]))
  (define (release c k)
    (when (or (key=? k "left") (key=? k "right")) (set-box! stick 0))
    c)
  (big-bang c
    [on-tick advance (/ 1.0 fps)]
    [to-draw draw]
    [on-key key]
    [on-release release]
    ;; NOT `[stop-when cab-halted? ...]`. Stopping makes `big-bang` RETURN, and
    ;; when this module is run by `racket` (rather than from DrRacket's REPL,
    ;; which stays alive) returning means the process exits and takes the
    ;; window with it — the final frame would flash past. `close-on-stop`
    ;; doesn't help: it only controls whether big-bang itself hides the frame.
    ;; So game-over is not a stop condition at all. `advance` no-ops once the
    ;; machine has halted, the final frame keeps being drawn, and the only way
    ;; out is an explicit quit — the GUI equivalent of the terminal's
    ;; "Press Enter to exit…".
    [stop-when (lambda (_) (unbox quit?)) draw]
    [name "AoC 2019 Day 13 — Care Package"])
  (printf "~a  final score ~a after ~a ticks.\n"
          (if (zero? (blocks-left c)) "CLEARED." "Ball missed —")
          (cab-score c) (cab-ticks c)))

;; ===========================================================================

(module+ main
  (define mode (box 'window))
  (define human? (box #f))
  (define heat? (box #f))
  (define speed (box #f))
  (define fps (box 30))
  (define path
    (command-line
     #:program "day13_arcade"
     #:once-each
     [("--terminal") "ANSI animation in the console (watch-only)"
                     (set-box! mode 'terminal)]
     [("--human") "you play: arrow keys move the paddle (window only)"
                  (set-box! human? #t)]
     [("--heat") "colour blocks by their hidden point value"
                 (set-box! heat? #t)]
     [("--speed") n "game ticks per rendered frame"
                  (set-box! speed (string->number n))]
     [("--fps") n "frames per second (0 = as fast as possible)"
                (set-box! fps (string->number n))]
     #:args ([input #f])
     (or input (build-path here 'up "inputs" "day13.txt"))))
  (define program (d05:parse-input (file->string path)))
  ;; A human needs the ball to move at human speed; the AI can be watched a
  ;; little faster. Override either with --speed.
  (define ticks/frame (or (unbox speed) (if (unbox human?) 1 2)))
  (case (unbox mode)
    [(terminal) (run-terminal program #:fps (unbox fps) #:speed ticks/frame)]
    [else (run-window program #:human? (unbox human?) #:speed ticks/frame
                      #:fps (unbox fps) #:heat? (unbox heat?))]))
