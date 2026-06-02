#lang racket

;; Supplement to Day 2: Racket's numeric tower, the exact/inexact split.
;;
;; Haskell makes you choose Int vs Integer up front. Racket does not:
;; integer arithmetic is arbitrary-precision and EXACT by default, and the
;; thing you actually have to track is exact vs inexact (rational vs flonum).

(provide (contract-out [run-demo (-> void?)]))

(define (show label expr)
  (printf "  ~a => ~a\n" label expr))

(define (show-exactness)
  (displayln "exactness")
  (show "(expt 2 100)        " (expt 2 100))      ; bignum, exact, no overflow
  (show "(/ 1 3)             " (/ 1 3))           ; 1/3  -- an exact RATIONAL
  (show "(/ 1.0 3)           " (/ 1.0 3))         ; inexact: a float division
  (show "(+ 1/3 1/6)         " (+ 1/3 1/6))       ; 1/2  -- rationals add exactly
  (show "(exact? (/ 1 3))    " (exact? (/ 1 3)))
  (show "(exact? 1.0)        " (exact? 1.0)))

(define (show-coercion)
  (displayln "")
  (displayln "crossing the line")
  (show "(exact->inexact 1/3)" (exact->inexact 1/3))   ; 0.333...
  (show "(inexact->exact 0.5)" (inexact->exact 0.5))   ; 1/2 exactly
  (show "(sqrt 25)           " (sqrt 25))              ; 5     -- exact in, exact out
  (show "(sqrt 2)            " (sqrt 2))               ; 1.414 -- exact in, inexact out
  (show "(* 2 3.0)           " (* 2 3.0)))             ; contagion: any inexact -> inexact

(define (show-truthiness)
  (displayln "")
  (displayln "truthiness")
  (show "(if 0 'yes 'no)     " (if 0 'yes 'no))        ; 0 is TRUE in Racket
  (show "(if \"\" 'yes 'no)    " (if "" 'yes 'no))     ; empty string is TRUE
  (show "(if '() 'yes 'no)   " (if '() 'yes 'no))      ; empty list is TRUE
  (show "(if #f 'yes 'no)    " (if #f 'yes 'no)))      ; #f is the ONLY false value

(define (run-demo)
  (show-exactness)
  (show-coercion)
  (show-truthiness))

(module+ main
  (run-demo))
