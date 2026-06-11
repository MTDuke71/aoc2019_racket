#lang racket/base

;; Tests for Day 06 — Universal Orbit Map.
;;
;; Pins:
;;   1. the parser (child -> parent orientation, CRLF tolerance),
;;   2. `ancestors` on the worked example (the chain both parts walk),
;;   3. Part 1's worked example: the 12-object map checksums to 42,
;;   4. Part 2's worked example: adding K)YOU and I)SAN gives 4 transfers,
;;   5. the actual answers for inputs/day06.txt.
;;
;; Run with:  raco test test/day06-test.rkt

(require rackunit
         "../src/aoc.rkt"
         "../src/day06.rkt")

;; The Part 1 example map from the puzzle text.
(define example-map
  "COM)B\nB)C\nC)D\nD)E\nE)F\nB)G\nG)H\nD)I\nE)J\nJ)K\nK)L\n")

;; The Part 2 example: same map plus YOU orbiting K and SAN orbiting I.
(define example-map+you/san
  (string-append example-map "K)YOU\nI)SAN\n"))

(module+ test

  ;; --- parser: child -> parent orientation ---
  (define parents (parse-input example-map))
  (check-equal? (hash-ref parents "B") "COM" "A)B stores B's parent as A")
  (check-equal? (hash-ref parents "L") "K"   "deepest leaf points at its parent")
  (check-equal? (hash-count parents) 11 "one entry per orbit line; COM is no one's child")
  (check-equal? (hash-ref (parse-input "COM)B\r\nB)C\r\n") "C") "B"
                "tolerates CRLF line endings")

  ;; --- ancestors: nearest-first chain to COM ---
  (check-equal? (ancestors parents "L")
                '("K" "J" "E" "D" "C" "B" "COM")
                "L's chain, nearest ancestor first")
  (check-equal? (ancestors parents "COM") '() "the root has no ancestors")
  (check-equal? (length (ancestors parents "D")) 3 "D orbits 3 objects (C, B, COM)")

  ;; --- Part 1: the worked example ---
  (check-equal? (part1 parents) 42 "example checksum: 42 direct+indirect orbits")

  ;; --- Part 2: the worked example ---
  ;; YOU's chain is K J E D C B COM; SAN's is I D C B COM. They first meet
  ;; at D (the lowest common ancestor): 3 transfers up from K plus 1 up
  ;; from I = 4.
  (check-equal? (part2 (parse-input example-map+you/san)) 4
                "example: 4 transfers (K->J->E->D->I)")

  ;; --- actual puzzle input ---
  (define real-parents (parse-input (read-day-input 6)))
  (check-equal? (part1 real-parents) 140608 "part 1")
  (check-equal? (part2 real-parents) 337 "part 2"))
