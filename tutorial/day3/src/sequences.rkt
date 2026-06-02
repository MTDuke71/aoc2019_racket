#lang racket

;; Day 3, part B: the `for` sequence toolkit.
;;
;; map/filter/fold cover most one-shot transforms, but Racket's `for`
;; family is the workhorse for AoC-style iteration. These are NOT C-style
;; for-loops: each one is an EXPRESSION that BUILDS a value -- a list, a
;; sum, a folded accumulator -- from one or more SEQUENCES.
;;
;; Closest Rust analogue: iterator adapters finished with
;; .collect() / .sum() / .fold().
;; Closest Haskell analogue: list comprehensions and foldl'.

(provide (contract-out [run-demo (-> void?)]))

(define (show label expr)
  (printf "  ~a => ~a\n" label expr))

;; for/list builds a list; in-range is the sequence generator.
;; #:when is the comprehension guard -- the Haskell `| p x` / Rust .filter().
(define (show-comprehensions)
  (displayln "for/list and ranges")
  (show "(for/list ([i (in-range 5)]) (* i i))"
        (for/list ([i (in-range 5)]) (* i i)))
  (show "(for/list ([i (in-range 1 6)] #:when (odd? i)) i)"
        (for/list ([i (in-range 1 6)] #:when (odd? i)) i))
  (show "(for/sum ([i (in-range 1 101)]) i)"
        (for/sum ([i (in-range 1 101)]) i)))

;; for/fold is the general reducer: you name the accumulator(s) and their
;; seeds, and the body's value becomes the next accumulator. It is for/sum,
;; for/list, and friends all generalized -- and the closest reading of
;; Haskell's foldl' over a sequence.
(define (show-fold)
  (displayln "")
  (displayln "for/fold")
  (show "(for/fold ([acc 0]) ([x '(3 1 4 1 5)]) (+ acc x))"
        (for/fold ([acc 0]) ([x '(3 1 4 1 5)]) (+ acc x)))
  (show "(for/fold ([acc '()]) ([x '(1 2 3)]) (cons x acc))"
        (for/fold ([acc '()]) ([x '(1 2 3)]) (cons x acc))))

;; Strings are their own type (Day 2), but they convert to/from lists of
;; chars, and they ARE a sequence you can iterate with in-string. The last
;; line is the digit-sum shape the Day 12 capstone leans on directly.
(define (show-strings)
  (displayln "")
  (displayln "strings as data")
  (show "(string->list \"abc\")" (string->list "abc"))
  (show "(list->string (list #\\h #\\i))" (list->string (list #\h #\i)))
  (show "(string-split \"1 2 3\")" (string-split "1 2 3"))
  (show "(map string->number (string-split \"1 2 3\"))"
        (map string->number (string-split "1 2 3")))
  (show "(for/sum ([c (in-string \"12345\")]) (- (char->integer c) 48))"
        (for/sum ([c (in-string "12345")]) (- (char->integer c) 48))))

;; A `for` clause list can name MORE THAN ONE sequence; they advance in
;; lockstep and stop at the shortest -- this is Rust's .zip() / Haskell's
;; zipWith. in-naturals is the infinite 0,1,2,... stream, safe to zip
;; against a finite one because the finite one ends the iteration.
(define (show-parallel)
  (displayln "")
  (displayln "parallel sequences")
  (show "(for/list ([x '(1 2 3)] [y '(10 20 30)]) (+ x y))"
        (for/list ([x '(1 2 3)] [y '(10 20 30)]) (+ x y)))
  (show "(for/list ([i (in-naturals)] [c (in-string \"abc\")]) (list i c))"
        (for/list ([i (in-naturals)] [c (in-string "abc")]) (list i c))))

(define (run-demo)
  (show-comprehensions)
  (show-fold)
  (show-strings)
  (show-parallel))

(module+ main
  (run-demo))
