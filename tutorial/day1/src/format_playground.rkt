#lang racket

(provide
 (contract-out
  [greeting (-> string? string?)]
  [run-demo (-> void?)]))

(define (greeting name)
  (format "Welcome to Racket, ~a." name))

(define (show-format-examples)
  (displayln "format placeholders")
  (displayln (format "  ~a with string: ~a" "~a" (format "X=~a" "hi")))
  (displayln (format "  ~s with string: ~a" "~s" (format "X=~s" "hi")))
  (displayln (format "  ~a with number: ~a" "~a" (format "X=~a" 42)))
  (displayln (format "  ~s with list:   ~a" "~s" (format "X=~s" '(1 2 3)))))

(define (show-greeting-examples)
  (displayln "")
  (displayln "greeting examples")
  (displayln (format "  (greeting \"Matt\") => ~a" (greeting "Matt")))
  (displayln (format "  (greeting \"Racket\") => ~a" (greeting "Racket"))))

(define (show-contract-note)
  (displayln "")
  (displayln "contract note")
  (displayln "  contract-out checks crossing a module boundary.")
  (displayln "  In another module, (greeting 42) will fail with a contract error."))

(define (run-demo)
  (show-format-examples)
  (show-greeting-examples)
  (show-contract-note))

(module+ main
  (run-demo))
