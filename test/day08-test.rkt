#lang racket/base

;; Tests for Day 08 — Space Image Format.
;;
;; Pins:
;;   1. the parser (string of digits -> byte vector, newline tolerance),
;;   2. `image-layers` reshape on the puzzle's 3×2 worked example,
;;   3. Part 1's example: layer "123/456" has the fewest 0s, checksum 1×1=1,
;;   4. `decode-image` / `render` on the 2×2 transparency example,
;;   5. the actual answers for inputs/day08.txt (Part 2 spells UBUFP).
;;
;; Run with:  raco test test/day08-test.rkt

(require rackunit
         "../src/aoc.rkt"
         "../src/day08.rkt")

(module+ test

  ;; --- parser: digits -> byte vector, trailing newline absorbed ---
  (check-equal? (parse-input "123456789012")
                #(1 2 3 4 5 6 7 8 9 0 1 2) "each char becomes its digit value")
  (check-equal? (parse-input "120\n")
                #(1 2 0) "trailing newline is trimmed, not parsed")

  ;; --- image-layers: the 3×2 reshape from the puzzle text ---
  ;; "123456789012" at 3 wide, 2 tall -> two 6-pixel layers.
  (define ex1 (parse-input "123456789012"))
  (check-equal? (image-layers ex1 3 2)
                (list #(1 2 3 4 5 6) #(7 8 9 0 1 2))
                "layer 1 is 123/456, layer 2 is 789/012")

  ;; --- Part 1: fewest-zeros layer, #1s × #2s ---
  ;; Layer 1 has zero 0s (vs. layer 2's one), so it wins; it has one 1 and
  ;; one 2, giving 1 × 1 = 1.
  (check-equal? (part1 ex1 3 2) 1 "example checksum")

  ;; --- Part 2: front-to-back transparency resolve ---
  ;; "0222112222120000" at 2×2: pixel 0 opaque in layer 0 (black), pixel 1
  ;; first opaque in layer 1 (white), pixel 2 in layer 2 (white), pixel 3
  ;; in layer 3 (black) -> the checkerboard .#/#. .
  (define ex2 (parse-input "0222112222120000"))
  (check-equal? (decode-image ex2 2 2) #(0 1 1 0) "topmost opaque pixel wins")
  (check-equal? (render (decode-image ex2 2 2) 2 2)
                " #\n# " "1 -> '#', 0 -> ' '")

  ;; --- actual puzzle input ---
  (define digits (parse-input (read-day-input 8)))
  (check-equal? (vector-length digits) 15000 "100 layers of 25×6 = 15000 pixels")
  (check-equal? (part1 digits 25 6) 1677 "part 1")
  ;; Part 2 renders the letters UBUFP.
  (check-equal? (part2 digits 25 6)
                (string-append
                 "#  # ###  #  # #### ###  \n"
                 "#  # #  # #  # #    #  # \n"
                 "#  # ###  #  # ###  #  # \n"
                 "#  # #  # #  # #    ###  \n"
                 "#  # #  # #  # #    #    \n"
                 " ##  ###   ##  #    #    ")
                "part 2: UBUFP"))
