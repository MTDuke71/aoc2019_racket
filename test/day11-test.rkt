#lang racket/base

;; Tests for Day 11 — Space Police.
;;
;; Pins:
;;   1. the grid-walking driver (`paint-hull`) against the puzzle prose's own
;;      worked walkthrough — a synthetic Intcode program that ignores its
;;      camera input and just emits the prose's 7 scripted (paint, turn)
;;      pairs, so the test isolates the robot's turn/move/paint bookkeeping
;;      from the VM's opcode semantics (already pinned by Day 9's quine et
;;      al. — `vm-step!` here is that same operand resolution, just stepped).
;;   2. `paint-hull`'s `start-color` parameter, with a synthetic program that
;;      actually reads its camera input (unlike the walkthrough script above)
;;      so a black-start vs. white-start run visibly disagree.
;;   3. `render`'s bounding-box-over-lit-cells grid drawing, standalone.
;;   4. the actual answers for inputs/day11.txt — Part 2's exact rendered
;;      picture is pinned (not just the inferred letters), the same
;;      stronger-regression-test stance the 2018 Haskell repo's Day 10 took:
;;      a `render` bug that drops one cell would still look like a plausible
;;      wrong 8-letter code, but it can't hide from an exact picture diff.
;;
;; Run with:  raco test test/day11-test.rkt

(require rackunit
         racket/string
         "../src/aoc.rkt"
         "../src/day11.rkt")

(module+ test

  ;; --- paint-hull against the spec's worked example ---
  ;;
  ;; The prose narrates 7 decision cycles (ignoring the camera reading it
  ;; also describes, since this script always emits the same outputs
  ;; regardless of input): outputs (1,0) (0,0) (1,0) (1,0) (0,1) (1,0) (1,0)
  ;; — paint then turn, left=0/right=1. Each cycle is `3,100` (read camera,
  ;; discard into scratch cell 100) then two `104,n` immediate outputs.
  (define scripted-robot
    (list->vector
     '(3 100 104 1 104 0    ; cycle 1: paint white, turn left
       3 100 104 0 104 0    ; cycle 2: paint black, turn left
       3 100 104 1 104 0    ; cycle 3: paint white, turn left
       3 100 104 1 104 0    ; cycle 4: paint white, turn left
       3 100 104 0 104 1    ; cycle 5: paint black, turn right
       3 100 104 1 104 0    ; cycle 6: paint white, turn left
       3 100 104 1 104 0    ; cycle 7: paint white, turn left
       99)))

  (define panels (paint-hull scripted-robot))

  (check-equal? (hash-count panels) 6
                "prose: \"the robot painted 6 panels at least once\"")

  ;; The full hash pins the turn/move convention exactly, not just the
  ;; count: starting panel (0,0) is painted twice (white then repainted
  ;; black) but appears once; the panel the robot ends on, (0,-1), is
  ;; walked onto but never painted, so it has no key at all — both
  ;; specifically called out in the puzzle prose.
  (check-equal? panels
                (hash (cons 0 0) 0
                      (cons -1 0) 0
                      (cons -1 1) 1
                      (cons 0 1) 1
                      (cons 1 0) 1
                      (cons 1 -1) 1)
                "exact painted-panel map matches the walkthrough")
  (check-false (hash-has-key? panels (cons 0 -1))
               "prose: \"it also never painted the panel it ended on\"")

  ;; --- start-color: a one-cycle program that echoes its camera input ---
  ;;
  ;; `3,100` reads the camera into scratch cell 100; `4,100` outputs that
  ;; same cell (so the paint color literally *is* the camera reading);
  ;; `104,0` always turns left; `99` halts. One decision cycle, so the only
  ;; thing that can vary is what (0,0) reads as on its first, only visit.
  (define echo-camera (list->vector '(3 100 4 100 104 0 99)))

  (check-equal? (paint-hull echo-camera) (hash (cons 0 0) 0)
                "default start-color 0: panel (0,0) reads black, paints black")
  (check-equal? (paint-hull echo-camera 1) (hash (cons 0 0) 1)
                "start-color 1: panel (0,0) reads white, paints white")

  ;; --- render: bounding box over lit cells only ---
  (check-equal? (render (hash (cons 0 0) 1 (cons 1 0) 0 (cons 2 1) 1))
                "#..\n..#"
                "render's bounding box spans only the white cells")
  (check-equal? (render (hash)) "" "no white panels renders as the empty string")

  ;; --- actual puzzle input ---
  (define program (parse-input (read-day-input 11)))
  (check-equal? (part1 program) 2129 "part 1 (panels painted at least once)")
  (check-equal? (part2 program)
                (string-join
                 '("###..####..##..#..#.###...##..####.#..."
                   "#..#.#....#..#.#.#..#..#.#..#....#.#..."
                   "#..#.###..#....##...#..#.#......#..#..."
                   "###..#....#....#.#..###..#.##..#...#..."
                   "#....#....#..#.#.#..#.#..#..#.#....#..."
                   "#....####..##..#..#.#..#..###.####.####")
                 "\n")
                "part 2: rendered registration code reads PECKRGZL"))
