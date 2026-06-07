#lang racket

;; AoC 2019 Day 3 — Crossed Wires, OPTIMIZED variant (trace-once).
;;
;; The shipping [day03.rkt](day03.rkt) keeps `part1` and `part2` as
;; independent pure functions of the parsed input (matching Day 1 / Day 2),
;; which reads cleanly but means a full `solve` calls `crossings` twice —
;; once in `part1`, once in `part2` — and `crossings` traces BOTH wires, so
;; a solve rasterizes the wire pair four times over.
;;
;; This variant applies the one optimization the benchmark actually
;; rewards: **trace once**. `both-parts` computes the crossings list a
;; single time (two traces) and derives both answers from it, cutting a
;; solve's work in half — a measured ~2.0x on the real input (194 ms ->
;; 95 ms; see the function guide's optimization section).
;;
;; What this file deliberately does NOT do is switch to a mutable hash.
;; That looks like the obvious systems-programmer win — replace ~150k
;; allocating `hash-set` calls with in-place `hash-ref!` — but benchmarking
;; says otherwise: a mutable `equal?`-keyed hash is ~8% SLOWER end-to-end
;; here, because the crossing-scan phase pays back more on mutable-hash
;; lookups than the faster build saves, and Racket CS's immutable HAMT is
;; already excellent. So the trace stays immutable, reused verbatim from
;; day03; the mutable experiment is written up as a dead-end in the guide.
;;
;; Parity with day03 (same answers on every example + real input) is
;; pinned in test/day03a-test.rkt.

(require "aoc.rkt"
         (only-in "day03.rkt" parse-input crossings))

(provide
 (contract-out
  [both-parts (-> (listof any/c)
                  (values exact-nonnegative-integer? exact-positive-integer?))]
  [solve      (-> string? void?)]))

(define (manhattan p)
  (+ (abs (car p)) (abs (cdr p))))

;; Trace the wire pair ONCE (via a single `crossings`) and read both
;; answers off the shared list: Part 1 minimizes Manhattan distance of the
;; crossing point, Part 2 minimizes the combined step count.
(define (both-parts wires)
  (define cs (crossings wires))
  (values (apply min (map (lambda (c) (manhattan (car c))) cs))
          (apply min (map cdr cs))))

(define (solve contents)
  (define wires (parse-input contents))
  (define-values (p1 p2) (both-parts wires))
  (printf "  part 1: ~a\n" p1)
  (printf "  part 2: ~a\n" p2))

(module+ main
  (solve (read-day-input 3)))
