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
             [ticks   #:mutable] [halted? #:mutable] [wedged? #:mutable]
             on-draw))

(define (make-cabinet program #:quarters [quarters 2] #:on-draw [on-draw void])
  (define machine (make-vm program))
  (when quarters (vm-poke! machine 0 quarters))
  (cab machine (hash) 0 '() 0 0 0 0 #f #f on-draw))

;; A tick that runs this many instructions without asking for the joystick is
;; never going to ask. The cabinet's collision resolution (address 161) is a
;; fixed-point loop with NO iteration bound: any bounce re-probes all three
;; axes, and if both x-neighbours are solid — the ball wedged between a side
;; wall and the paddle, on the paddle's own row — the probe flips `dx` forever
;; and the machine never reaches its next INPUT. It is a livelock in the
;; puzzle program, not here, and it is reachable in ordinary play (hold a
;; direction while the ball comes down the wall column). Faithful emulation
;; would hang the UI, so the driver gives up and lets the caller say so.
;;
;; Calibration on the real input: 4,778 ticks with a median of 112
;; instructions each, p99 321, max 17,109 (and that max is the opening repaint,
;; which `prime!` absorbs before the first tick). 200,000 is ~600x the p99.
(define instructions/tick-limit 200000)

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
  (let loop ([fed? #f] [steps 0])
    (cond
      [(> steps instructions/tick-limit) (set-cab-wedged?! c #t) c]
      [else
       (match (vm-step! (cab-machine c))
         ['blocked
          (cond
            [fed? c]                         ; asking again → this frame is done
            [else (vm-enqueue! (cab-machine c) (joystick c))
                  (set-cab-ticks! c (add1 (cab-ticks c)))
                  (loop #t 0)])]
         ['ran (loop fed? (add1 steps))]
         [`(output ,n) (absorb! c n) (loop fed? (add1 steps))]
         ['halted (set-cab-halted?! c #t) c])])))

;; Either kind of "stop driving this cabinet".
(define (cab-done? c) (or (cab-halted? c) (cab-wedged? c)))

;; Board geometry, read off the OPENING FRAME rather than out of the program.
;; The repaint `prime!` just absorbed draws every cell exactly once, so the
;; screen hash already knows how big the board is and where the paddle sits.
;; That matters because AoC ships a different board size per user — 40x25 here,
;; 45x24 on the second input the disassembly compares against — and asking the
;; data beats archaeology on the code. Returns (values W H paddle-row).
(define (screen-geometry c)
  (define ks (hash-keys (cab-screen c)))
  (define W (add1 (apply max (map car ks))))
  (define H (add1 (apply max (map cdr ks))))
  (define paddle-row
    (or (for/first ([(k v) (in-hash (cab-screen c))] #:when (= v 3)) (cdr k))
        (- H 2)))                        ; the generator always uses H-2
  (values W H paddle-row))

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

(provide (struct-out cab) make-cabinet prime! tick! cab-done? ai-joystick
         blocks-left screen-geometry instructions/tick-limit)

;; ===========================================================================
;; PERIPHERAL 1 — the terminal
;; ===========================================================================
;;
;; ANSI: `\e[2J` clear, `\e[H` cursor home, `\e[?25l/h` hide/show cursor.
;; Redrawing from home (rather than clearing each frame) avoids flicker.
;; Keyboard input is not portable without raw-mode support, so the terminal
;; peripheral is watch-only — the AI plays. Board selection therefore happens
;; at the "Press Enter" prompt rather than with a live key: type a number
;; first and that board is loaded instead. The window peripheral does the same
;; thing with the number keys on its start screen.

(define (run-terminal boards #:fps [fps 30] #:speed [speed 2] #:start [start 0])
  (define idx (box start))
  (define c (make-cabinet (cdr (list-ref boards (unbox idx)))))
  (printf "\e[2J\e[?25l")
  ;; `\e[J` erases from the cursor down, so a prompt printed under one frame is
  ;; wiped by the next one instead of lingering below a shorter redraw.
  (define (paint!)
    (printf "\e[H")
    (printf "AoC 2019 Day 13 [~a] — the AI plays  (tick ~a)\n\n"
            (car (list-ref boards (unbox idx)))
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
  ;; Offer the choice only when there is one; a single-board run keeps the
  ;; original bare prompt.
  (cond
    [(> (length boards) 1)
     (printf "\n  boards: ~a\n"
             (string-join (for/list ([b (in-list boards)] [i (in-naturals)])
                            (format "[~a] ~a" (add1 i) (car b)))
                          "   "))
     (printf "  Press Enter to start, or a number then Enter to switch board… ")
     (flush-output)
     (define answer (read-line))
     (define pick (and (string? answer) (string->number (string-trim answer))))
     (when (and pick (exact-integer? pick) (<= 1 pick (length boards)))
       (set-box! idx (sub1 pick))
       (set! c (make-cabinet (cdr (list-ref boards (unbox idx)))))
       (prime! c)
       (paint!))]
    [else
     (printf "\n  Press Enter to start… ")
     (flush-output)
     (void (read-line))])
  (let loop ()
    (for ([_ (in-range speed)] #:break (cab-done? c))
      (tick! c ai-joystick))
    (paint!)
    (when (positive? fps) (sleep (/ 1.0 fps)))
    (unless (cab-done? c) (loop)))
  (printf "\e[?25h")
  (printf "\n  ~a  final score ~a after ~a ticks.\n"
          (cond [(cab-wedged? c) "CABINET WEDGED —"]
                [(zero? (blocks-left c)) "CLEARED."]
                [else "Ball missed —"])
          (cab-score c) (cab-ticks c))
  (when (cab-wedged? c)
    (printf "  The collision fixed point at address 161 never converged.\n")
    (printf "  See Problem_Statements/days/day13_disassembly.md.\n"))
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

;; The immediate operand of the instruction at `ip`. Constants CANNOT be read
;; from fixed operand cells: the generator emits `li k` as any of `add #0,#k`,
;; `add #k,#0`, `mul #k,#1`, `mul #1,#k`, so which slot holds `k` varies per
;; user even though the instruction addresses do not. When both operands are
;; immediate, the constant is the one that isn't the operation's identity
;; element — which is what makes the templates interchangeable. See
;; day13_disassembly.md, "What changes between users' inputs".
(define (imm-operand program ip)
  (define instr (vector-ref program ip))
  (define identity (if (= 2 (modulo instr 100)) 1 0))
  (define (mode n) (modulo (quotient instr (* 100 (expt 10 (sub1 n)))) 10))
  (define (arg n) (vector-ref program (+ ip n)))
  (cond
    [(and (= 1 (mode 1)) (= 1 (mode 2)))
     (if (= (arg 1) identity) (arg 2) (arg 1))]
    [(= 1 (mode 1)) (arg 1)]
    [else (arg 2)]))

;; Blocks coloured by the point value the disassembly recovered from the
;; program's hidden table: slot(x,y) = tbase + ((colmul*x + y)*a + c) mod m,
;; every constant pulled out of the instruction that loads it. Cheap tiles
;; cold, expensive tiles hot — the score map made visible while you play it.
;; See day13_disassembly.md, "The hidden score map".
(define (heat-palette program)
  (define tbase  (imm-operand program 630))
  (define colmul (imm-operand program 603))
  (define a      (imm-operand program 611))
  (define c      (imm-operand program 615))
  (define m      (imm-operand program 619))
  (lambda (x y)
    (define v (vector-ref program
                          (+ tbase (modulo (+ (* (+ (* colmul x) y) a) c) m))))
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
(define (frame-image c bg paddle-row [banner #f])
  (define board
    (place-image (cell-image 4 #f) (cell-x (cab-ball c)) (cell-y (cab-bally c))
                 (place-image (cell-image 3 #f) (cell-x (cab-paddle c))
                              (cell-y paddle-row)
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

;; `boards` is a list of (label . program): the window opens on the first and
;; the number keys switch between them from the start screen. Board geometry is
;; per-program (40x25 and 45x24 are both real), so W/H/paddle-row are recomputed
;; on every load rather than closed over once.
(define (run-window boards #:human? [human? #f] #:speed [speed 2]
                    #:fps [fps 30] #:heat? [heat? #f])
  (define bg (box #f))
  (define geom (box '(40 25 23)))        ; W, H, paddle-row for the loaded board
  (define label (box ""))
  (define idx (box 0))
  (define stick (box 0))                 ; the human's current key direction
  (define auto? (box (not human?)))
  (define started? (box #f))             ; the opening board holds until a key
  (define quit? (box #f))                ; the ONLY thing that stops big-bang
  ;; Every broken block patches the cached background: draw an empty cell over
  ;; it and re-freeze. Ball/paddle updates are ignored here — they are sprites.
  (define (on-draw x y new old)
    (when (and (equal? old 2) (= new 0) (unbox bg))
      (set-box! bg (freeze (place-image (cell-image 0 #f) (cell-x x) (cell-y y)
                                        (unbox bg))))))
  ;; Load board `i` and return its cabinet, primed and paused: absorb the
  ;; opening repaint, measure the board from it, and flatten walls + blocks
  ;; into the cached background before anything is shown.
  (define (load-board i)
    (define program (cdr (list-ref boards i)))
    (define c (make-cabinet program #:on-draw on-draw))
    (set-box! bg #f)                     ; suppress patching during the repaint
    (prime! c)
    (define-values (W H paddle-row) (screen-geometry c))
    (set-box! geom (list W H paddle-row))
    (set-box! idx i)
    (set-box! label (car (list-ref boards i)))
    (set-box! started? #f)
    (set-box! stick 0)
    (set-box! auto? (not human?))
    (set-box! bg (build-background (cab-screen c) (and heat? (heat-palette program)) W H))
    c)
  (define (joystick c) (if (unbox auto?) (ai-joystick c) (unbox stick)))
  (define (advance c)
    (when (unbox started?)
      (for ([_ (in-range speed)] #:break (cab-done? c)) (tick! c joystick)))
    c)
  (define (banner c)
    (above/align
     "left"
     (text (format "SCORE ~a     BLOCKS ~a     TICK ~a"
                   (cab-score c) (blocks-left c) (cab-ticks c))
           16 "white")
     (text (cond
             [(cab-wedged? c)
              "CABINET WEDGED — collision fixed point at 161 never converged"]
             [(cab-halted? c)
              (if (zero? (blocks-left c))
                  "CLEARED — [q] or close the window to quit"
                  "BALL MISSED — [q] or close the window to quit")]
             [(not (unbox started?)) (start-screen-help)]
             [(unbox auto?) "[a] you play   [q] quit          tracking controller"]
             [else "[<-] [->] move   [a] autopilot   [q] quit"])
           12 "gray")))
  ;; On the start screen the number keys pick the board, so say so — and show
  ;; which one is loaded, since the boards differ in size and block count.
  (define (start-screen-help)
    (define choices
      (for/list ([b (in-list boards)] [i (in-naturals)])
        (format "[~a] ~a~a" (add1 i) (car b) (if (= i (unbox idx)) " *" ""))))
    (string-append "board: " (string-join choices "   ")
                   "     press space to start"))
  (define (draw c)
    (match-define (list W H paddle-row) (unbox geom))
    (frame-image c
                 (or (unbox bg) (empty-scene (* W CELL) (* H CELL) "black"))
                 paddle-row
                 (banner c)))
  (define (key c k)
    (define pick                          ; "1".."9" -> board index, else #f
      (for/first ([i (in-range (length boards))]
                  #:when (key=? k (number->string (add1 i))))
        i))
    (cond
      ;; Board selection only makes sense before the game starts; once running,
      ;; a stray number key must not silently restart a game in progress.
      [(and pick (not (unbox started?))) (load-board pick)]
      [(key=? k "left")  (set-box! started? #t) (set-box! stick -1) (set-box! auto? #f) c]
      [(key=? k "right") (set-box! started? #t) (set-box! stick  1) (set-box! auto? #f) c]
      [(key=? k "a")     (set-box! started? #t) (set-box! auto? (not (unbox auto?))) c]
      [(key=? k "q")     (set-box! quit? #t) c]
      [else (set-box! started? #t) c]))
  (define (release c k)
    (when (or (key=? k "left") (key=? k "right")) (set-box! stick 0))
    c)
  (define final
   (big-bang (load-board 0)
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
    [name "AoC 2019 Day 13 — Care Package"]))
  ;; big-bang hands back the final world, which is the cabinet last loaded —
  ;; the right one to report on even if the board was switched at the start.
  (printf "~a (~a)  final score ~a after ~a ticks.\n"
          (cond [(cab-wedged? final) "CABINET WEDGED —"]
                [(zero? (blocks-left final)) "CLEARED."]
                [else "Ball missed —"])
          (unbox label) (cab-score final) (cab-ticks final)))

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
     input))
  ;; With no argument, offer every day13 board sitting in inputs/ —
  ;; `day13.txt` plus anything like `day13_alt.txt` (a second user's program,
  ;; on a 45x24 board instead of 40x25; see the disassembly's "What changes
  ;; between users' inputs"). Sorted so the puzzle's own input is board 1.
  (define input-dir (build-path here 'up "inputs"))
  (define (label-of p) (regexp-replace #rx"\\.txt$" (path->string p) ""))
  (define board-paths
    (cond
      [path (list (string->path path))]
      [else
       (define found
         (sort (for/list ([p (in-list (directory-list input-dir))]
                          #:when (regexp-match? #rx"^day13.*\\.txt$" (path->string p)))
                 p)
               (lambda (a b) (< (string-length (path->string a))
                                (string-length (path->string b))))))
       (for/list ([p (in-list found)]) (build-path input-dir p))]))
  (when (null? board-paths)
    (error 'day13_arcade "no day13*.txt found in ~a" input-dir))
  (define boards
    (for/list ([p (in-list board-paths)])
      (cons (label-of (file-name-from-path p))
            (d05:parse-input (file->string p)))))
  ;; A human needs the ball to move at human speed; the AI can be watched a
  ;; little faster. Override either with --speed.
  (define ticks/frame (or (unbox speed) (if (unbox human?) 1 2)))
  (case (unbox mode)
    [(terminal) (run-terminal boards #:fps (unbox fps) #:speed ticks/frame)]
    [else (run-window boards #:human? (unbox human?) #:speed ticks/frame
                      #:fps (unbox fps) #:heat? (unbox heat?))]))
