#lang racket

;; Day 3, part A: the list, and the map / filter / fold toolkit.
;;
;; A Racket list is a singly-linked chain of cons cells ending in '().
;; That is the Haskell [a] model, NOT a Rust Vec<T> (that's a `vector`,
;; Day 7). Consequences: prepend with `cons` is O(1); indexing with
;; `list-ref` is O(n). You reach for lists when you stream front-to-back
;; and for vectors when you index.

(provide
 (contract-out
  [sum-list      (-> (listof number?) number?)]
  [evens         (-> (listof exact-integer?) (listof exact-integer?))]
  [doubled       (-> (listof number?) (listof number?))]
  [parse-and-sum (-> string? number?)]))

;; --- the toolkit, applied ---

;; foldl: left fold. (foldl + 0 xs) sums the list.
;; WATCH THE ARGUMENT ORDER: the combining fn is (element accumulator),
;; accumulator LAST -- the mirror image of Haskell's foldl, where the
;; accumulator comes first. (foldl cons '() xs) therefore REVERSES xs.
(define (sum-list xs)
  (foldl + 0 xs))

;; filter: keep the elements where the predicate holds.
;; Like Rust's .filter() / Haskell's filter. `even?` is built in.
(define (evens xs)
  (filter even? xs))

;; map: transform every element into a new list.
;; Like Rust's .map() / Haskell's map. `lambda` is the anonymous fn (Day 6).
(define (doubled xs)
  (map (lambda (x) (* 2 x)) xs))

;; A first taste of input parsing -- the shape every AoC day starts with.
;; "1 2 3 40"  --string-split-->  '("1" "2" "3" "40")
;;             --map string->number-->  '(1 2 3 40)
;;             --foldl +-->  46
(define (parse-and-sum line)
  (sum-list (map string->number (string-split line))))

(module+ main
  (define xs '(3 1 4 1 5 9 2 6))
  (printf "xs                  = ~a\n" xs)
  (printf "(first xs)          = ~a\n" (first xs))     ; head    -- car
  (printf "(rest xs)           = ~a\n" (rest xs))      ; tail    -- cdr
  (printf "(length xs)         = ~a\n" (length xs))
  (printf "(list-ref xs 2)     = ~a\n" (list-ref xs 2)); O(n) index
  (printf "(cons 0 xs)         = ~a\n" (cons 0 xs))    ; O(1) prepend
  (printf "(append xs '(0 0))  = ~a\n" (append xs '(0 0)))
  (printf "(reverse xs)        = ~a\n" (reverse xs))
  (printf "(member 4 xs)       = ~a\n" (member 4 xs))  ; tail from match, or #f
  (printf "(sum-list xs)       = ~a\n" (sum-list xs))
  (printf "(evens xs)          = ~a\n" (evens xs))
  (printf "(doubled xs)        = ~a\n" (doubled xs))
  (printf "(parse-and-sum ...) = ~a\n" (parse-and-sum "1 2 3 40")))
