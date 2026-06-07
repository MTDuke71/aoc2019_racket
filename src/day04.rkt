#lang racket

;; AoC 2019 Day 4 — Secure Container.
;;
;; A change of pace from grids (Day 3) and Intcode (Day 2): a pure
;; number-theory / combinatorics filter. We're handed a numeric range and
;; asked how many six-digit numbers in it look like a valid password:
;;
;;   * Part 1: digits are **non-decreasing** left-to-right AND at least one
;;     pair of **adjacent equal** digits exists (e.g. 11 in 1*22*345).
;;   * Part 2: same, but the adjacent-equal group must be **exactly two**
;;     long — 123444 fails (the 44 is inside a run of three 4s), 112233
;;     passes, 111122 passes (the 22 is a clean double even though 1111
;;     isn't).
;;
;; Both rules become trivial once you **run-length encode the digits**: the
;; "non-decreasing" check is `(apply <= ds)`, and the double-rule is a
;; question about run *lengths* — Part 1 wants any run length >= 2, Part 2
;; wants any run length exactly = 2. Run-length encoding is the canonical
;; name for the collapse `(1 1 2 3 3 3) -> ((1 . 2) (2 . 1) (3 . 3))`, and
;; it's the whole trick of the day.
;;
;; The shipping solution brute-forces every number in the range (~510k of
;; them) and filters. The function guide sidebars the **combinatorial
;; count** — non-decreasing six-digit strings are "combinations with
;; repetition" (stars and bars), and the double-rules can be counted in
;; closed form without enumerating anything.

(require "aoc.rkt")

(provide
 (contract-out
  [parse-input       (-> string? (cons/c exact-nonnegative-integer?
                                          exact-nonnegative-integer?))]
  [digits            (-> exact-nonnegative-integer? (listof (integer-in 0 9)))]
  [run-length-encode (-> (listof exact-integer?)
                         (listof (cons/c exact-integer? exact-positive-integer?)))]
  [part1-ok?         (-> exact-nonnegative-integer? boolean?)]
  [part2-ok?         (-> exact-nonnegative-integer? boolean?)]
  [part1             (-> (cons/c exact-nonnegative-integer?
                                 exact-nonnegative-integer?)
                         exact-nonnegative-integer?)]
  [part2             (-> (cons/c exact-nonnegative-integer?
                                 exact-nonnegative-integer?)
                         exact-nonnegative-integer?)]
  [solve             (-> string? void?)]))

;; The input is one line, `lo-hi` (e.g. "172930-683082"). Split on the
;; hyphen, parse both ends, return the inclusive bounds as `(lo . hi)`.
;; `match` on the two-element list both destructures and documents the
;; expected shape — anything else is a contract/error, not a silent (cdr).
(define (parse-input s)
  (match (map string->number (string-split (string-trim s) "-"))
    [(list lo hi) (cons lo hi)]))

;; A number into its decimal digits, most-significant first:
;;   123 -> '(1 2 3). We round-trip through the string form because the
;; digits are then a `string->list` away, and subtracting the code point of
;; #\0 turns each digit character into its integer value. (Working purely
;; numerically with quotient/remainder would yield the digits least-
;; significant first, the wrong order for the non-decreasing test.)
(define (digits n)
  (map (lambda (c) (- (char->integer c) (char->integer #\0)))
       (string->list (number->string n))))

;; Run-length encode a list into (value . run-length) pairs, collapsing
;; maximal runs of CONSECUTIVE equal elements:
;;   '(1 1 2 3 3 3) -> '((1 . 2) (2 . 1) (3 . 3))
;;
;; The fold inspects the head of the accumulator (the run currently being
;; built): if the next element matches that run's value, bump its count;
;; otherwise the run is finished, so start a fresh `(x . 1)` run. Because
;; we cons new runs onto the front, the accumulator is in reverse order —
;; `#:result reverse` flips it back at the end. The `match` clause guard
;; `#:when (= v x)` is what distinguishes "extend the current run" from
;; "begin a new one".
(define (run-length-encode xs)
  (for/fold ([runs '()] #:result (reverse runs))
            ([x (in-list xs)])
    (match runs
      [(cons (cons v n) rest)
       #:when (= v x)
       (cons (cons v (add1 n)) rest)]
      [_ (cons (cons x 1) runs)])))

;; Part 1 validity: digits never decrease, and some run is at least a pair.
;; `(apply <= ds)` is the elegant non-decreasing test — `<=` is variadic,
;; so it checks the whole chain `d0 <= d1 <= ... <= d5` in one call. The
;; `and` short-circuits, so we only bother run-length encoding once the
;; cheap monotonicity check has passed.
(define (part1-ok? n)
  (define ds (digits n))
  (and (apply <= ds)
       (for/or ([run (in-list (run-length-encode ds))])
         (>= (cdr run) 2))))

;; Part 2 validity: same monotonicity, but now we need a run of length
;; *exactly* two — a digit that appears as a clean double, not buried in a
;; longer run. The only change from Part 1 is `>=` becoming `=`.
(define (part2-ok? n)
  (define ds (digits n))
  (and (apply <= ds)
       (for/or ([run (in-list (run-length-encode ds))])
         (= (cdr run) 2))))

;; Count the numbers in [lo, hi] (inclusive) satisfying `ok?`. `for/sum`
;; with a `#:when` guard adds 1 per matching number — a counting loop with
;; no explicit accumulator. `(add1 hi)` makes the half-open `in-range`
;; cover `hi` itself.
(define (count-in-range lohi ok?)
  (match-define (cons lo hi) lohi)
  (for/sum ([n (in-range lo (add1 hi))] #:when (ok? n)) 1))

(define (part1 lohi) (count-in-range lohi part1-ok?))
(define (part2 lohi) (count-in-range lohi part2-ok?))

;; Dispatcher: parse once, print both parts. Mirrors Days 1–3.
(define (solve contents)
  (define lohi (parse-input contents))
  (printf "  part 1: ~a\n" (part1 lohi))
  (printf "  part 2: ~a\n" (part2 lohi)))

(module+ main
  (solve (read-day-input 4)))
