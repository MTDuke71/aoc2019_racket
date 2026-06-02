#lang racket

;; AoC 2019 Day 1 — The Tyranny of the Rocket Equation.
;;
;; The puzzle input is a list of module masses, one integer per line.
;; Both parts compute fuel:
;;
;;   * Part 1: fuel(mass) = floor(mass / 3) - 2, summed over all modules.
;;   * Part 2: fuel itself has mass, which needs its own fuel, and so on.
;;     Iterate fuel() to a fixed point (stopping once the next step is
;;     <= 0) and sum that whole chain for each module.
;;
;; This is the project's first real Racket day, so the shape it
;; establishes — `parse-input` / `part1` / `part2` / `solve`, all behind
;; `contract-out` — is the template every later day copies.

(require "aoc.rkt")

(provide
 (contract-out
  [parse-input (-> string? (listof exact-integer?))]
  [fuel        (-> exact-integer? exact-integer?)]
  [total-fuel  (-> exact-integer? exact-integer?)]
  [part1       (-> (listof exact-integer?) exact-integer?)]
  [part2       (-> (listof exact-integer?) exact-integer?)]
  [solve       (-> string? void?)]))

;; Each whitespace-delimited token is one module mass. `string-split`
;; with no separator splits on runs of whitespace and drops empty
;; pieces, so trailing newlines and CRLF line endings need no special
;; handling.
;;
;; Rust analogue: `input.split_whitespace().map(|s| s.parse().unwrap())`.
(define (parse-input s)
  (map string->number (string-split s)))

;; Fuel for a single mass: divide by three, round down, subtract two.
;; `quotient` is truncating integer division; on non-negative masses
;; that is exactly "round down".
(define (fuel mass)
  (- (quotient mass 3) 2))

;; Part 2's fixed-point iteration: fuel needs fuel needs fuel...
;; Each step feeds the previous step's fuel back through `fuel`, summing
;; until a step produces nothing positive. Tail-recursive, so it runs in
;; constant stack space.
(define (total-fuel mass)
  (let loop ([m mass] [acc 0])
    (define f (fuel m))
    (if (<= f 0)
        acc
        (loop f (+ acc f)))))

;; Part 1: naive per-module fuel, summed.
(define (part1 masses)
  (for/sum ([m (in-list masses)]) (fuel m)))

;; Part 2: fixed-point fuel per module, summed.
(define (part2 masses)
  (for/sum ([m (in-list masses)]) (total-fuel m)))

;; Dispatcher: parse once, print both parts. Mirrors the Haskell repo's
;; `solve :: String -> IO ()`.
(define (solve contents)
  (define puzzle (parse-input contents))
  (printf "  part 1: ~a\n" (part1 puzzle))
  (printf "  part 2: ~a\n" (part2 puzzle)))

;; `racket src/day01.rkt` runs this; `require`-ing the module does not.
(module+ main
  (solve (read-day-input 1)))
