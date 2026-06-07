#lang racket

;; AoC 2019 Day 3 — Crossed Wires.
;;
;; Two wires are traced from a central port onto an integer grid, each
;; described by a comma-separated path like `R8,U5,L5,D3` (go Right 8, Up
;; 5, Left 5, Down 3). The wires cross at some grid cells, and we want the
;; "best" crossing under two different cost functions:
;;
;;   * Part 1: the crossing closest to the origin by **Manhattan distance**
;;     (|x| + |y|).
;;   * Part 2: the crossing reached in the fewest **combined steps** —
;;     steps-along-wire-1 + steps-along-wire-2 to first arrive there.
;;
;; The shape of the solution is a **spatial hash**: rasterize each wire one
;; unit cell at a time into a hash mapping point -> first-arrival step
;; count, then the crossings are exactly the keys the two hashes share.
;; Part 1 minimizes a function of the *point*; Part 2 minimizes a function
;; of the *step counts*. Because we already record step counts for Part 2,
;; one `trace` serves both parts.
;;
;; This is the project's first day to lean on **immutable hash tables**
;; (`hash` / `hash-set`, persistent and `equal?`-keyed) and on a 2D point
;; as a plain `(cons x y)` pair destructured with `match-define`. The
;; function guide sidebars two alternatives: representing points as Racket
;; **complex numbers** (translation = addition), and trading the
;; rasterization for **segment-intersection** geometry.

(require "aoc.rkt")

(provide
 (contract-out
  [parse-input (-> string? (listof (listof (cons/c char? exact-positive-integer?))))]
  [trace       (-> (listof (cons/c char? exact-positive-integer?))
                   (hash/c (cons/c exact-integer? exact-integer?) exact-positive-integer?))]
  [crossings   (-> (listof any/c)
                   (listof (cons/c (cons/c exact-integer? exact-integer?)
                                   exact-positive-integer?)))]
  [part1       (-> (listof any/c) exact-nonnegative-integer?)]
  [part2       (-> (listof any/c) exact-positive-integer?)]
  [solve       (-> string? void?)]))

;; Each direction letter maps to a unit step `(cons dx dy)`. Up is +y; the
;; sign convention doesn't matter for either part since both costs are
;; symmetric, but matching the puzzle's picture keeps debugging sane.
(define dirs
  (hash #\R (cons  1  0)
        #\L (cons -1  0)
        #\U (cons  0  1)
        #\D (cons  0 -1)))

;; A path token like "R1008" -> `(cons #\R 1008)`: the first character is
;; the direction, the rest is the (always positive) distance.
(define (parse-move tok)
  (cons (string-ref tok 0)
        (string->number (substring tok 1))))

;; The whole input -> a list of two wires, each a list of moves.
;;
;; `(string-split (string-trim s))` with no separator splits on runs of
;; whitespace, so it cleanly cuts the two lines apart (and tolerates CRLF)
;; *because path tokens never contain spaces* — the only whitespace in the
;; file is the line break. Each line is then split on commas into tokens.
(define (parse-input s)
  (for/list ([line (in-list (string-split (string-trim s)))])
    (map parse-move (string-split line ","))))

;; Rasterize one wire into a hash mapping every visited cell (the origin
;; excluded) to the step count at which the wire *first* arrives there.
;;
;; `for*/fold` threads three accumulators — current position, total steps
;; so far, and the growing hash — across a *nested* iteration: the outer
;; sequence walks the moves, and `(in-range (cdr mv))` walks the magnitude
;; of each move one unit cell at a time. The accumulators persist across
;; both loop levels, so position and step count carry over from the end of
;; one move into the start of the next. `#:result seen` discards the
;; bookkeeping accumulators and returns just the hash.
;;
;; Steps only ever increase, so the first time a cell is seen is also the
;; cheapest: we keep the existing entry and never overwrite (a wire that
;; self-crosses records the earlier arrival, which is what Part 2 wants).
(define (trace wire)
  (for*/fold ([pos (cons 0 0)]
              [steps 0]
              [seen (hash)]
              #:result seen)
             ([mv (in-list wire)]
              [_  (in-range (cdr mv))])
    (match-define (cons dx dy) (hash-ref dirs (car mv)))
    (define next (cons (+ (car pos) dx) (+ (cdr pos) dy)))
    (define n    (add1 steps))
    (values next
            n
            (if (hash-has-key? seen next) seen (hash-set seen next n)))))

;; Manhattan (taxicab) distance from the origin to a point.
(define (manhattan p)
  (+ (abs (car p)) (abs (cdr p))))

;; Trace both wires and return one entry per crossing: `(point . combined)`
;; where `combined` is the summed first-arrival step count of the two
;; wires. A crossing is any cell present in *both* step-hashes; iterating
;; the smaller hash and probing the larger would shave constant factors,
;; but the inputs are close in size so we just walk wire 1's cells.
(define (crossings wires)
  (define h1 (trace (first wires)))
  (define h2 (trace (second wires)))
  (for/list ([(p s1) (in-hash h1)]
             #:when (hash-has-key? h2 p))
    (cons p (+ s1 (hash-ref h2 p)))))

;; Part 1: the crossing nearest the origin, by Manhattan distance.
(define (part1 wires)
  (apply min (map (lambda (c) (manhattan (car c))) (crossings wires))))

;; Part 2: the crossing reachable in the fewest combined wire-steps.
(define (part2 wires)
  (apply min (map cdr (crossings wires))))

;; Dispatcher: parse once, print both parts. Mirrors Day 1 / Day 2.
(define (solve contents)
  (define wires (parse-input contents))
  (printf "  part 1: ~a\n" (part1 wires))
  (printf "  part 2: ~a\n" (part2 wires)))

(module+ main
  (solve (read-day-input 3)))
