#lang racket

;; AoC 2019 Day 14 — Space Stoichiometry.
;;
;; A nanofactory recipe book: every line is `3 A, 4 B => 1 AB`, and exactly
;; one reaction produces each chemical except `ORE`, the raw material. Part 1
;; asks for the ORE cost of 1 FUEL; Part 2 asks how much FUEL a trillion ORE
;; buys.
;;
;; The whole day hangs on one wrinkle in the prose: **reactions cannot be
;; partially run**. Producing 3 units from a `=> 2 D` reaction costs two
;; whole runs and wastes one D. That single `ceiling` is what makes the
;; problem interesting — without it the answer would be a linear-algebra
;; one-liner (multiply the recipe matrix down to ORE and stop), and Part 2
;; would be exactly `10¹² / (ore for 1 fuel)`.
;;
;; With it, the naïve recursion is *wrong*: expand each demand the moment you
;; see it and you round up separately for every consumer, paying again for
;; leftovers you already had. The fix is the day's real algorithm, and it has
;; a name:
;;
;;   * **Topological sort** (Kahn's algorithm) of the recipe DAG, with edges
;;     running from a reaction's *output* to each of its *inputs*. Process
;;     chemicals in that order and every consumer of a chemical has already
;;     logged its demand by the time we expand it — so we round up exactly
;;     once, on the total. No leftover bookkeeping at all.
;;
;;   * **Part 2** is then a **binary search on the answer**: `ore-for` is
;;     monotone non-decreasing in fuel, so "the largest f with
;;     `ore-for(f) ≤ 10¹²`" is a predicate flip, and bisection finds it in
;;     ~40 evaluations. The economy of scale (leftovers get absorbed at
;;     volume) puts the true answer *above* the naïve
;;     `10¹² / ore-for(1)` estimate — which is exactly why that estimate is a
;;     sound lower bracket to start from.
;;
;; New Racket this day: an immutable `struct` ([Day 11](day11_function_guide.md)
;; used a `#:mutable` one), `match-define`, `hash-update!` with a default,
;; `hash-ref!`, `remove-duplicates`, and the `(quotient (+ n per -1) per)`
;; exact-integer ceiling-division idiom.

(require "aoc.rkt")

;; A reaction: `qty` units of the output chemical are produced by consuming
;; `inputs`, a list of `(qty . chemical)` pairs. The output chemical is not
;; stored in the struct — it is the hash key that points at it.
(struct reaction (qty inputs) #:transparent)

(define chem/c      string?)
(define amount/c    (cons/c exact-positive-integer? chem/c))
(define reactions/c (hash/c chem/c reaction?))

(provide
 (struct-out reaction)
 (contract-out
  [parse-amount (-> string? amount/c)]
  [parse-input  (-> string? reactions/c)]
  [topo-order   (-> reactions/c (listof chem/c))]
  [ore-for      (-> reactions/c exact-nonnegative-integer? exact-nonnegative-integer?)]
  [part1        (-> reactions/c exact-nonnegative-integer?)]
  [part2        (->* (reactions/c) (exact-positive-integer?) exact-nonnegative-integer?)]
  [solve        (-> string? void?)]))

;; ---------------------------------------------------------------- parsing

;; `"7 A"` → `'(7 . "A")`. Every quantity in this puzzle is a positive
;; integer, so one shape covers both sides of the arrow.
(define (parse-amount s)
  (match (string-split (string-trim s))
    [(list n chem) (cons (string->number n) chem)]))

;; `"7 A, 1 B => 1 C"` → one hash entry, keyed by the output chemical.
;;
;; The puzzle guarantees "almost every chemical is produced by exactly one
;; reaction", so a hash keyed by output is lossless — no multimap needed, and
;; `ORE` simply never appears as a key. That guarantee is doing real work: it
;; is what makes the recipe book a *function* from chemical to recipe, and
;; therefore what makes the demand propagation below deterministic.
;;
;; `match-define` destructures in a definition position — the pattern binds
;; its variables in the enclosing scope instead of a `match` clause body.
;; Rust analogue: `let (lhs, rhs) = ...;` with an irrefutable pattern.
(define (parse-input s)
  (for/hash ([line (in-list (string-split (string-trim s) "\n"))]
             #:unless (string=? (string-trim line) ""))
    (match-define (list lhs rhs) (string-split line "=>"))
    (define out (parse-amount rhs))
    (values (cdr out)
            (reaction (car out) (map parse-amount (string-split lhs ","))))))

;; ------------------------------------------------------- topological sort

;; The chemicals, ordered so that every consumer of a chemical appears
;; strictly before the chemical itself. FUEL comes first (nothing consumes
;; it); ORE comes last (everything reaches it, nothing produces it).
;;
;; This is **Kahn's algorithm**: repeatedly emit a node whose in-degree has
;; fallen to zero, then decrement the in-degree of its successors. Edges run
;; output → input, so a node's in-degree reads as "how many distinct
;; reactions still have to be expanded before this chemical's total demand is
;; known".
;;
;; `remove-duplicates` matters for correctness, not tidiness: a reaction that
;; listed the same input twice must contribute *one* edge, because the loop
;; below decrements once per successor entry. Count and decrement have to
;; agree or a node never reaches zero.
(define (topo-order reactions)
  ;; Successors of each chemical: the distinct inputs of its reaction.
  (define succs
    (for/hash ([(out r) (in-hash reactions)])
      (values out (remove-duplicates (map cdr (reaction-inputs r))))))
  ;; In-degrees. Seed every chemical seen on either side at 0 first — ORE has
  ;; no `succs` entry of its own — so no key is missing during the sweep.
  ;; `hash-ref!` reads a key, inserting the default if it is absent.
  (define indeg (make-hash))
  (for ([(out ss) (in-hash succs)])
    (hash-ref! indeg out 0)
    (for ([s (in-list ss)]) (hash-ref! indeg s 0)))
  (for* ([(_out ss) (in-hash succs)] [s (in-list ss)])
    (hash-update! indeg s add1))
  ;; Kahn's loop. `ready` is the frontier of zero-in-degree chemicals; the
  ;; DAG is small (a few dozen nodes), so a list-as-stack is plenty.
  (let loop ([ready (for/list ([(c d) (in-hash indeg)] #:when (zero? d)) c)]
             [order '()])
    (cond
      [(null? ready) (reverse order)]
      [else
       (define c (car ready))
       (define ready*
         (for/fold ([acc (cdr ready)]) ([s (in-list (hash-ref succs c '()))])
           (hash-update! indeg s sub1)
           (if (zero? (hash-ref indeg s)) (cons s acc) acc)))
       (loop ready* (cons c order))])))

;; ------------------------------------------------------------- the solver

;; Ceiling division on exact non-negative integers: how many whole runs of a
;; `=> per`-unit reaction cover a demand of `n`. Racket has `ceiling`, but
;; `(ceiling (/ n per))` routes through an exact rational; the integer idiom
;; stays in fixnums for as long as it can. Same trick as Rust's
;; `n.div_ceil(per)` and the C `(n + per - 1) / per`.
(define (ceil-div n per) (quotient (+ n per -1) per))

;; ORE required to produce `fuel` units of FUEL.
;;
;; Walk the chemicals in topological order carrying a `need` table. When we
;; reach chemical `c`, every reaction that consumes it has already been
;; expanded, so `need[c]` is its *final* total — round that up to whole runs
;; ONCE, and push the resulting input demands forward. Leftovers never need a
;; ledger: the wasted `runs*qty − need` units are simply never charged for
;; again, because by construction nothing downstream will ask for `c` a
;; second time.
(define (ore-for reactions fuel)
  (define need (make-hash))
  (hash-set! need "FUEL" fuel)
  (for ([c (in-list (topo-order reactions))])
    (define n (hash-ref need c 0))
    (when (and (positive? n) (hash-has-key? reactions c))
      (define r (hash-ref reactions c))
      (define runs (ceil-div n (reaction-qty r)))
      (for ([in (in-list (reaction-inputs r))])
        (hash-update! need (cdr in) (λ (v) (+ v (* runs (car in)))) 0))))
  (hash-ref need "ORE" 0))

(define (part1 reactions) (ore-for reactions 1))

;; The largest FUEL buildable from `budget` ORE (one trillion by default).
;;
;; `ore-for` is monotone non-decreasing in fuel — more FUEL can never demand
;; fewer runs of any reaction — so `(λ (f) (<= (ore-for f) budget))` is true
;; on a prefix of the naturals and false ever after. **Binary search** finds
;; that flip; the guide proves the monotonicity.
;;
;; Bracketing without magic constants: `lo0` is the naïve
;; `budget / ore-for(1)` rate estimate. It is a *lower* bound, and provably
;; so — `ore-for` is subadditive (`ore-for(k·f) ≤ k·ore-for(f)`, since
;; batching merges round-ups and can only save), hence
;; `ore-for(lo0) ≤ lo0·ore-for(1) ≤ budget`. Then double `hi` until it
;; overshoots and bisect on the invariant "`lo` is affordable, `hi` is not".
;;
;; Note `lo0` is NOT floored at 1: a budget too small for a single FUEL gives
;; `lo0 = 0`, and 0 is the honest answer (and `ore-for(0) = 0` keeps the
;; invariant true). Flooring at 1 would seed the search with an unaffordable
;; `lo` and report 1 FUEL you cannot build.
(define (part2 reactions [budget 1000000000000])
  (define (affordable? f) (<= (ore-for reactions f) budget))
  (define lo0 (quotient budget (part1 reactions)))
  (let grow ([hi (max 1 (* 2 lo0))])
    (if (affordable? hi)
        (grow (* 2 hi))
        (let bisect ([lo lo0] [hi hi])
          ;; Invariant: `lo` is affordable, `hi` is not.
          (if (<= (- hi lo) 1)
              lo
              (let ([mid (quotient (+ lo hi) 2)])
                (if (affordable? mid) (bisect mid hi) (bisect lo mid))))))))

;; Dispatcher: parse once, print both parts. Mirrors Days 1–13.
(define (solve contents)
  (define reactions (parse-input contents))
  (printf "  part 1: ~a\n" (part1 reactions))
  (printf "  part 2: ~a\n" (part2 reactions)))

(module+ main
  (solve (read-day-input 14)))
