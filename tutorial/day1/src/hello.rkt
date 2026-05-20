#lang racket

(provide
 (contract-out
  [greeting (-> string? string?)]))

(define (greeting name)
  (format "Welcome to Racket, ~a." name))

(module+ main
  (displayln "Hello, World!")
  (displayln (greeting "Matt")))
