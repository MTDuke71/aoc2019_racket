#lang racket

(provide
 (contract-out
  [square   (-> exact-integer? exact-integer?)]
  [cube     (-> exact-integer? exact-integer?)]
  [hypot    (-> real? real? real?)]
  [my-even? (-> exact-integer? boolean?)]
  [shout    (-> string? string?)]))

;; --- Values: top-level bindings -------------------------------------------
;; One keyword for all of them: define. No type annotation line, no let/var.

(define answer 42)                       ; exact integer
(define bignum (expt 2 100))             ; STILL an exact integer -- no overflow
(define pi-approx 3.141592653589793)     ; inexact (flonum)
(define ready #t)                        ; boolean: #t / #f
(define letter-a #\A)                    ; character literal
(define motto "Values first, parens always.")  ; string

;; --- Functions: a define whose head is a parameter list -------------------

(define (square x) (* x x))

(define (cube x) (* x (square x)))       ; one function calling another

(define (hypot a b) (sqrt (+ (* a a) (* b b))))

(define (my-even? n) (= (remainder n 2) 0))  ; built-in even? exists; this is the manual version

(define (shout s) (string-append s "!!!"))

;; --- IO shell -------------------------------------------------------------

(module+ main
  (printf "answer     = ~a\n" answer)
  (printf "bignum     = ~a\n" bignum)
  (printf "pi-approx  = ~a\n" pi-approx)
  (printf "ready      = ~a\n" ready)
  (printf "letter-a   = ~a\n" letter-a)
  (printf "motto      = ~a\n" motto)
  (printf "square 7   = ~a\n" (square 7))
  (printf "cube 3     = ~a\n" (cube 3))
  (printf "hypot 3 4  = ~a\n" (hypot 3 4))
  (printf "my-even? 10 = ~a\n" (my-even? 10))
  (displayln (shout "Day 2 complete")))
