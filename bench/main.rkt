#lang racket

;; Benchmark harness for AoC 2019 (Racket).
;;
;; Racket has no criterion. The closest honest substitute is `time-apply`
;; (which returns cpu / real / gc milliseconds for a thunk) run over many
;; iterations and averaged. `collect-garbage` before each measurement
;; keeps GC pauses from one bench leaking into the next.
;;
;; Run:  racket bench/main.rkt
;;
;; Adding a day is two lines: a `require` at the top and a `bench-day`
;; call at the bottom.

(require racket/runtime-path
         "../src/aoc.rkt"
         (prefix-in d01: "../src/day01.rkt")
         (prefix-in d02: "../src/day02.rkt")
         (prefix-in d03:  "../src/day03.rkt")
         (prefix-in d03a: "../src/day03a.rkt")
         (prefix-in d04:  "../src/day04.rkt")
         (prefix-in d05:  "../src/day05.rkt")
         (prefix-in d06:  "../src/day06.rkt")
         (prefix-in d07:  "../src/day07.rkt")
         (prefix-in d08:  "../src/day08.rkt")
         (prefix-in d09:  "../src/day09.rkt")
         (prefix-in d10:  "../src/day10.rkt")
         (prefix-in d11:  "../src/day11.rkt"))

;; Mean wall-clock milliseconds for `thunk`, averaged over `iters` runs.
(define (bench-ms thunk #:iters [iters 100000])
  (collect-garbage)
  (define-values (_results _cpu real _gc)
    (time-apply (lambda () (for ([_ (in-range iters)]) (thunk))) '()))
  (/ real iters))

;; Format milliseconds with fixed precision for table alignment.
(define (ms x) (real->decimal-string x 4))

;; Time parse / part1 / part2 for one day and print a summary row.
;; `part1` and `part2` run on already-parsed input so the parse cost is
;; not double-counted; Total is the sum of the three means.
(define (bench-day name raw parse part1 part2 #:iters [iters 100000])
  (define parsed (parse raw))
  (define tp (bench-ms (lambda () (parse raw))   #:iters iters))
  (define t1 (bench-ms (lambda () (part1 parsed)) #:iters iters))
  (define t2 (bench-ms (lambda () (part2 parsed)) #:iters iters))
  (printf "| ~a | ~a | ~a | ~a | ~a |\n"
          name (ms tp) (ms t1) (ms t2) (ms (+ tp t1 t2))))

(printf "| Day | Parse (ms) | Part 1 (ms) | Part 2 (ms) | Total (ms) |\n")
(printf "|-----|-----------|-------------|-------------|------------|\n")

(bench-day "01" (read-day-input 1) d01:parse-input d01:part1 d01:part2)
;; Day 2's Part 2 brute-forces the full 100x100 (noun, verb) grid on every
;; call (~5300 program runs), so it gets a far smaller iteration count than
;; Day 1's microsecond kernels — 200 is plenty for a stable mean here.
(bench-day "02" (read-day-input 2) d02:parse-input d02:part1 d02:part2
           #:iters 200)
;; Day 3's part1 and part2 each rasterize both wires (~150k unit cells)
;; into immutable hashes, so a single part call is real work — 200
;; iterations is plenty for a stable mean without minutes of bench time.
(bench-day "03" (read-day-input 3) d03:parse-input d03:part1 d03:part2
           #:iters 200)
;; Day 4 brute-forces every number in the ~510k-wide range on each part
;; call (digits + run-length-encode per candidate), so a single part call
;; is tens of milliseconds — 50 iterations is plenty for a stable mean.
(bench-day "04" (read-day-input 4) d04:parse-input d04:part1 d04:part2
           #:iters 50)
;; Day 5 runs the ~680-int diagnostic program once per part — a few hundred
;; instructions, sub-millisecond — so 2000 iterations gives a stable mean.
(bench-day "05" (read-day-input 5) d05:parse-input d05:part1 d05:part2
           #:iters 2000)
;; Day 6's part1 re-walks each of ~900 nodes' ancestor chains (O(n*depth),
;; low single-digit ms); parse and part2 are sub-millisecond — 500
;; iterations gives a stable mean without dominating the bench run.
(bench-day "06" (read-day-input 6) d06:parse-input d06:part1 d06:part2
           #:iters 500)
;; Day 7 brute-forces 5! = 120 phase permutations per part; Part 2 runs five
;; cooperative VMs per permutation — low tens of ms total — 200 iters is plenty.
(bench-day "07" (read-day-input 7) d07:parse-input d07:part1 d07:part2
           #:iters 200)
;; Day 8's parts take explicit (digits width height); wrap them at the
;; puzzle's 25×6 so the harness sees the standard one-arg shape. Parse
;; builds a 15000-byte vector; Part 1 chunks 100 layers and histograms;
;; Part 2 resolves 150 pixels down ≤100 layers — all sub-millisecond, so
;; 2000 iterations gives a stable mean.
(bench-day "08" (read-day-input 8) d08:parse-input
           (lambda (d) (d08:part1 d 25 6))
           (lambda (d) (d08:part2 d 25 6))
           #:iters 2000)
;; Day 9 runs the BOOST program once per part — a few thousand instructions
;; against the grow-on-write memory, low single-digit ms — so 500 iterations
;; gives a stable mean without dominating the bench run.
(bench-day "09" (read-day-input 9) d09:parse-input d09:part1 d09:part2
           #:iters 500)
;; Day 10's parts are both O(n²) over ~310 asteroids: each `best` call runs
;; ~310 set-building visibility scans of ~310 others. Part 2 additionally
;; groups/sorts/round-robins the winning station's rays. Low tens of ms per
;; part call, so 100 iterations gives a stable mean.
(bench-day "10" (read-day-input 10) d10:parse-input d10:part1 d10:part2
           #:iters 100)

;; Day 11's parts both single-step the robot's Intcode program to
;; completion (a few thousand `vm-step!` calls plus hash bookkeeping);
;; Part 2 additionally walks the painted hash into a rendered string, which
;; is cheap next to the simulation itself. 200 iterations gives a stable
;; mean for both.
(bench-day "11" (read-day-input 11) d11:parse-input d11:part1 d11:part2
           #:iters 200)

;; The optimized variant (src/day03a.rkt) is a TRACE-ONCE restructure, and
;; that win only shows at solve granularity: the idiomatic solve runs part1
;; THEN part2 — each calls `crossings`, each `crossings` traces both wires,
;; so a solve rasterizes the pair 4 times. day03a's `both-parts` traces it
;; once. Compare like-for-like on the real input.
(let ([wires (d03:parse-input (read-day-input 3))])
  (printf "\nsolve-granularity (real input, mean of 200 iters):\n")
  (printf "  day03  part1 then part2 (crossings x2, 4 traces): ~a ms\n"
          (ms (bench-ms (lambda () (d03:part1 wires) (d03:part2 wires)) #:iters 200)))
  (printf "  day03a both-parts       (crossings x1, 2 traces): ~a ms\n"
          (ms (bench-ms (lambda () (d03a:both-parts wires)) #:iters 200))))
