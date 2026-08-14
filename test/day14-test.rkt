#lang racket/base

;; Tests for Day 14 — Space Stoichiometry.
;;
;; Pins:
;;   1. `parse-amount` and `parse-input` on the spec's first example, including
;;      the multi-input case and the fact that ORE is never a hash key,
;;   2. `topo-order` as a *property*, not a fixed list — the sort is not
;;      unique (any linearisation of the DAG is valid, and hash iteration
;;      order picks one), so the test asserts the invariant that actually
;;      matters: every consumer precedes what it consumes, FUEL is first and
;;      ORE is last, and every chemical appears exactly once,
;;   3. Part 1 on all five spec examples: 31, 165, 13312, 180697, 2210736.
;;      The first is the one where naive per-demand rounding overpays (it
;;      returns 41, not 31), so it is the regression test for the whole
;;      topological-order idea,
;;   4. `ore-for` at fuel = 0 (no ORE) and its subadditivity witness — bulk is
;;      never worse than the same amount bought one unit at a time, which is
;;      the property Part 2's lower bracket relies on,
;;   5. Part 2 on the three large spec examples: 82892753, 5586022, 460664,
;;      plus a boundary check that the answer is affordable and answer+1 is
;;      not (that pins the *off-by-one* of the bisection, which pinning the
;;      value alone would not distinguish from a lucky bracket),
;;   6. the actual answers for inputs/day14.txt.
;;
;; Run with:  raco test test/day14-test.rkt

(require rackunit
         racket/list
         "../src/aoc.rkt"
         "../src/day14.rkt")

(module+ test

  ;; --- the spec's five example recipe books ---

  (define example1 "10 ORE => 10 A
1 ORE => 1 B
7 A, 1 B => 1 C
7 A, 1 C => 1 D
7 A, 1 D => 1 E
7 A, 1 E => 1 FUEL")

  (define example2 "9 ORE => 2 A
8 ORE => 3 B
7 ORE => 5 C
3 A, 4 B => 1 AB
5 B, 7 C => 1 BC
4 C, 1 A => 1 CA
2 AB, 3 BC, 4 CA => 1 FUEL")

  (define example3 "157 ORE => 5 NZVS
165 ORE => 6 DCFZ
44 XJWVT, 5 KHKGT, 1 QDVJ, 29 NZVS, 9 GPVTF, 48 HKGWZ => 1 FUEL
12 HKGWZ, 1 GPVTF, 8 PSHF => 9 QDVJ
179 ORE => 7 PSHF
177 ORE => 5 HKGWZ
7 DCFZ, 7 PSHF => 2 XJWVT
165 ORE => 2 GPVTF
3 DCFZ, 7 NZVS, 5 HKGWZ, 10 PSHF => 8 KHKGT")

  (define example4 "2 VPVL, 7 FWMGM, 2 CXFTF, 11 MNCFX => 1 STKFG
17 NVRVD, 3 JNWZP => 8 VPVL
53 STKFG, 6 MNCFX, 46 VJHF, 81 HVMC, 68 CXFTF, 25 GNMV => 1 FUEL
22 VJHF, 37 MNCFX => 5 FWMGM
139 ORE => 4 NVRVD
144 ORE => 7 JNWZP
5 MNCFX, 7 RFSQX, 2 FWMGM, 2 VPVL, 19 CXFTF => 3 HVMC
5 VJHF, 7 MNCFX, 9 VPVL, 37 CXFTF => 6 GNMV
145 ORE => 6 MNCFX
1 NVRVD => 8 CXFTF
1 VJHF, 6 MNCFX => 4 RFSQX
176 ORE => 6 VJHF")

  (define example5 "171 ORE => 8 CNZTR
7 ZLQW, 3 BMBT, 9 XCVML, 26 XMNCP, 1 WPTQ, 2 MZWV, 1 RJRHP => 4 PLWSL
114 ORE => 4 BHXH
14 VRPVC => 6 BMBT
6 BHXH, 18 KTJDG, 12 WPTQ, 7 PLWSL, 31 FHTLT, 37 ZDVW => 1 FUEL
6 WPTQ, 2 BMBT, 8 ZLQW, 18 KTJDG, 1 XMNCP, 6 MZWV, 1 RJRHP => 6 FHTLT
15 XDBXC, 2 LTCX, 1 VRPVC => 6 ZLQW
13 WPTQ, 10 LTCX, 3 RJRHP, 14 XMNCP, 2 MZWV, 1 ZLQW => 1 ZDVW
5 BMBT => 4 WPTQ
189 ORE => 9 KTJDG
1 MZWV, 17 XDBXC, 3 XCVML => 2 XMNCP
12 VRPVC, 27 CNZTR => 2 XDBXC
15 KTJDG, 12 BHXH => 5 XCVML
3 BHXH, 2 VRPVC => 7 MZWV
121 ORE => 7 VRPVC
7 XCVML => 6 RJRHP
5 BHXH, 4 VRPVC => 5 LTCX")

  (define rs1 (parse-input example1))
  (define rs2 (parse-input example2))
  (define rs3 (parse-input example3))
  (define rs4 (parse-input example4))
  (define rs5 (parse-input example5))

  ;; --- parsing ---

  (check-equal? (parse-amount "7 A")   '(7 . "A"))
  (check-equal? (parse-amount " 44 XJWVT ") '(44 . "XJWVT")
                "leading/trailing whitespace from the `=>` and `,` splits")

  (check-equal? (reaction-qty (hash-ref rs1 "A")) 10
                "`10 ORE => 10 A` produces ten at a time — the source of the waste")
  (check-equal? (reaction-inputs (hash-ref rs1 "C"))
                '((7 . "A") (1 . "B"))
                "multi-input left-hand side keeps its order and quantities")
  (check-false (hash-has-key? rs1 "ORE")
               "ORE is produced by no reaction, so it is never a key")
  (check-equal? (hash-count rs2) 7 "one entry per line")

  ;; --- topo-order: assert the invariant, not a particular linearisation ---
  ;;
  ;; Kahn's algorithm reads its initial frontier out of a hash, so the exact
  ;; sequence is unspecified. What must hold for `ore-for` to be correct is
  ;; that no chemical is expanded before all of its consumers.
  (define (check-topo rs name)
    (define order (topo-order rs))
    (define pos (for/hash ([c (in-list order)] [i (in-naturals)]) (values c i)))
    (check-equal? (length order) (length (remove-duplicates order))
                  (string-append name ": every chemical appears exactly once"))
    (check-equal? (first order) "FUEL"
                  (string-append name ": nothing consumes FUEL, so it sorts first"))
    (check-equal? (last order) "ORE"
                  (string-append name ": nothing produces ORE, so it sorts last"))
    (for* ([(out r) (in-hash rs)] [in (in-list (reaction-inputs r))])
      (check-true (< (hash-ref pos out) (hash-ref pos (cdr in)))
                  (format "~a: ~a must be expanded before its input ~a"
                          name out (cdr in)))))

  (check-topo rs1 "example 1")
  (check-topo rs2 "example 2")
  (check-topo rs5 "example 5")

  ;; --- Part 1 on all five examples ---
  ;;
  ;; Example 1 is the regression test for the whole approach. A recursion
  ;; that rounds up each demand for A as it meets it pays for 4 separate
  ;; batches of 10 A (40 A, 40 ORE) and returns 41; batching the demand into
  ;; a single 28 → 30 A round-up returns the correct 31.
  (check-equal? (part1 rs1) 31      "example 1: 31 ORE")
  (check-equal? (part1 rs2) 165     "example 2: 165 ORE")
  (check-equal? (part1 rs3) 13312   "example 3: 13312 ORE")
  (check-equal? (part1 rs4) 180697  "example 4: 180697 ORE")
  (check-equal? (part1 rs5) 2210736 "example 5: 2210736 ORE")

  ;; --- ore-for: degenerate case and subadditivity ---

  (check-equal? (ore-for rs1 0) 0 "no fuel demanded, no ORE consumed")

  ;; ore-for(k·f) ≤ k·ore-for(f): buying in bulk merges the round-ups, so it
  ;; can never cost more than buying the same amount one batch at a time.
  ;; This is the property Part 2's lower bracket leans on, so it gets pinned
  ;; rather than merely asserted in a comment.
  (check-true (<= (ore-for rs1 10) (* 10 (ore-for rs1 1)))
              "bulk is never worse than ten singles")
  ;; 10 FUEL demands 280 A and 10 B. Batched, that is ⌈280/10⌉ = 28 runs of
  ;; the A reaction (280 ORE) plus 10 ORE for B = 290. Ten separate single-
  ;; FUEL builds pay 31 each = 310: the 20 ORE difference is the wasted A
  ;; from ten independent ⌈28/10⌉ = 3-run round-ups collapsing into one.
  (check-equal? (ore-for rs1 10) 290
              "…and here it is strictly better: 310 as ten singles, 290 batched")

  ;; --- Part 2: a trillion ORE ---

  (check-equal? (part2 rs3) 82892753 "example 3: 82892753 FUEL per 10^12 ORE")
  (check-equal? (part2 rs4) 5586022  "example 4: 5586022 FUEL")
  (check-equal? (part2 rs5) 460664   "example 5: 460664 FUEL")

  ;; The bisection's off-by-one, pinned directly: the reported answer must be
  ;; affordable and one more must not be. Pinning only the value would let a
  ;; search that happens to land one short pass on a lucky bracket.
  (define trillion 1000000000000)
  (for ([rs (in-list (list rs3 rs4 rs5))] [n (in-naturals 3)])
    (define f (part2 rs))
    (check-true  (<= (ore-for rs f) trillion)
                 (format "example ~a: the answer is affordable" n))
    (check-true  (> (ore-for rs (add1 f)) trillion)
                 (format "example ~a: one more FUEL is not" n)))

  ;; A smaller budget exercises the optional argument and the `grow` phase's
  ;; lower bracket on a case where the answer is small.
  (check-equal? (part2 rs1 31) 1  "exactly one FUEL's worth of ORE buys one FUEL")
  (check-equal? (part2 rs1 30) 0  "…and one ORE short buys none")

  ;; --- actual puzzle input ---
  (define reactions (parse-input (read-day-input 14)))
  (check-equal? (part1 reactions) 628586  "part 1 (ORE for 1 FUEL)")
  (check-equal? (part2 reactions) 3209254 "part 2 (FUEL from 10^12 ORE)"))
