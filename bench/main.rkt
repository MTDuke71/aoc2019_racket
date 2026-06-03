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
         (prefix-in d02: "../src/day02.rkt"))

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
