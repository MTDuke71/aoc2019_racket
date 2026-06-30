#lang racket

;; AoC 2019 Day 10 — Monitoring Station.
;;
;; A break from the Intcode VM ([Day 9](day09_function_guide.md)) into a
;; lattice-geometry puzzle. Two classic moves over grid points carry it:
;;
;;   * **Part 1 — primitive direction vectors.** From a candidate station,
;;     two asteroids share a single line of sight iff their *reduced* delta
;;     vectors are equal — divide (dx, dy) by gcd(|dx|, |dy|) and collinear
;;     points collapse to the same primitive direction. So the number an
;;     asteroid can *see* is the number of **distinct directions** to the
;;     others (only the nearest on each bearing is visible). Best = the
;;     asteroid maximizing that count.
;;
;;   * **Part 2 — angular sweep.** The laser starts pointing up and rotates
;;     **clockwise**, vaporizing the nearest asteroid on each bearing, one
;;     per bearing per rotation. Group the others by primitive direction,
;;     sort each group near→far, order the groups by clockwise-from-up angle
;;     (`atan2(dx, -dy)`), then **round-robin**: one sweep of the angle-
;;     ordered rays = one full rotation. The 200th vaporized gives
;;     `x*100 + y`.
;;
;; The gcd reduction is the same primitive-vector fact as "lattice points
;; strictly between two grid points = gcd(|dx|,|dy|) − 1"; see the function
;; guide. New Racket this day: `in-indexed` (enumerate), nested `for*/list`,
;; `argmax`, `hash-update!`, the two-argument `atan` (atan2), and `pi`.

(require "aoc.rkt")

(provide
 (contract-out
  [parse-input        (-> string? (listof (cons/c exact-integer? exact-integer?)))]
  [count-visible      (-> (cons/c exact-integer? exact-integer?)
                          (listof (cons/c exact-integer? exact-integer?))
                          exact-nonnegative-integer?)]
  [best               (-> (listof (cons/c exact-integer? exact-integer?))
                          (cons/c (cons/c exact-integer? exact-integer?)
                                  exact-nonnegative-integer?))]
  [vaporization-order (-> (cons/c exact-integer? exact-integer?)
                          (listof (cons/c exact-integer? exact-integer?))
                          (listof (cons/c exact-integer? exact-integer?)))]
  [part1              (-> (listof (cons/c exact-integer? exact-integer?))
                          exact-nonnegative-integer?)]
  [part2              (-> (listof (cons/c exact-integer? exact-integer?))
                          exact-integer?)]
  [solve              (-> string? void?)]))

;; The map is a grid of `.` (empty) and `#` (asteroid); we only ever care
;; about the asteroid coordinates, so parse straight to a list of `(x . y)`
;; pairs. `in-indexed` pairs each element of a sequence with its 0-based
;; index (Racket's `enumerate`), and the two parallel clauses of `for*/list`
;; *nest* (rows outer, columns inner) — the `*` is what makes it a nested
;; loop rather than a lockstep one.
(define (parse-input s)
  (for*/list ([(row y) (in-indexed (in-list (string-split s)))]
              [(ch  x) (in-indexed (in-string row))]
              #:when (char=? ch #\#))
    (cons x y)))

;; Reduce a delta to its primitive direction vector: (dx, dy) / gcd. Two
;; deltas that reduce to the same pair point along one ray from the origin,
;; so this is the equivalence class "same line of sight". `gcd` is never 0
;; here because callers exclude the zero delta (the station itself).
(define (direction dx dy)
  (define g (gcd (abs dx) (abs dy)))
  (cons (quotient dx g) (quotient dy g)))

;; How many asteroids `station` can see: the count of *distinct* primitive
;; directions to the others. Building a set folds every collinear cluster to
;; one element automatically — exactly the "blocked by a nearer asteroid"
;; rule, for free.
(define (count-visible station asteroids)
  (define sx (car station))
  (define sy (cdr station))
  (for/fold ([dirs (set)] #:result (set-count dirs))
            ([a (in-list asteroids)] #:unless (equal? a station))
    (set-add dirs (direction (- (car a) sx) (- (cdr a) sy)))))

;; The best monitoring station paired with its visible count. `argmax`
;; returns the *element* maximizing the key function (not the max value),
;; so we tag each asteroid with its count first and let `argmax` pick the
;; winning `(coord . count)` pair. Part 1's answer is the `cdr`.
(define (best asteroids)
  (argmax cdr
          (for/list ([a (in-list asteroids)])
            (cons a (count-visible a asteroids)))))

;; The order in which the rotating laser vaporizes every other asteroid,
;; starting from `station`. Three steps:
;;   1. group the others by primitive direction (each group is one bearing);
;;   2. sort each group near→far (squared distance — monotone, no sqrt);
;;   3. order the groups by clockwise-from-up angle, then round-robin them.
(define (vaporization-order station asteroids)
  (define sx (car station))
  (define sy (cdr station))
  (define (dist2 a) (+ (sqr (- (car a) sx)) (sqr (- (cdr a) sy))))
  ;; Angle of asteroid `a` measured CLOCKWISE from straight up, in [0, 2π).
  ;; Screen coords have y growing downward, so "up" is −dy. The argument
  ;; order `atan(dx, -dy)` puts up→0, right→π/2, down→π, left→3π/2; the
  ;; wrap fixes the negative half-plane that `atan` returns in (−π, π].
  (define (angle a)
    (define θ (atan (- (car a) sx) (- sy (cdr a))))
    (if (negative? θ) (+ θ (* 2 pi)) θ))
  ;; bearing (primitive direction) -> asteroids on it
  (define groups (make-hash))
  (for ([a (in-list asteroids)] #:unless (equal? a station))
    (hash-update! groups (direction (- (car a) sx) (- (cdr a) sy))
                  (λ (members) (cons a members)) '()))
  ;; Each ray as its near→far list, the rays themselves sorted by angle.
  ;; (Angle is computed from the nearest member; every member of a ray shares
  ;; the bearing, so any representative gives the same angle.)
  (define rays
    (sort (for/list ([members (in-hash-values groups)])
            (sort members < #:key dist2))
          < #:key (λ (ray) (angle (car ray)))))
  ;; Round-robin: each pass takes the head of every nonempty ray, in angle
  ;; order — that pass IS one clockwise rotation of the laser. Repeat until
  ;; every ray is drained. `order` is built reversed and flipped once.
  (let rotate ([rays rays] [order '()])
    (if (andmap null? rays)
        (reverse order)
        (rotate (map (λ (ray) (if (null? ray) ray (cdr ray))) rays)
                (for/fold ([order order]) ([ray (in-list rays)] #:when (pair? ray))
                  (cons (car ray) order))))))

(define (part1 asteroids)
  (cdr (best asteroids)))

;; Part 2: the 200th asteroid vaporized, encoded as x*100 + y.
(define (part2 asteroids)
  (define station (car (best asteroids)))
  (define target (list-ref (vaporization-order station asteroids) 199))
  (+ (* 100 (car target)) (cdr target)))

;; Dispatcher: parse once, print both parts. Mirrors Days 1–9.
(define (solve contents)
  (define asteroids (parse-input contents))
  (printf "  part 1: ~a\n" (part1 asteroids))
  (printf "  part 2: ~a\n" (part2 asteroids)))

(module+ main
  (solve (read-day-input 10)))
