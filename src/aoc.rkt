#lang racket/base

;; Shared plumbing for every AoC 2019 day.
;;
;; The only thing every day needs in common is "find and read my input
;; file regardless of the current working directory". `define-runtime-path`
;; pins the path to *this source file's* location at compile time, so
;; `racket src/day01.rkt`, `raco test test/day01-test.rkt`, and
;; `racket bench/main.rkt` all resolve `inputs/dayNN.txt` identically.
;;
;; Rust analogue: this is the moral equivalent of `include_str!` /
;; `env!("CARGO_MANIFEST_DIR")` — a build-time anchor to the project
;; tree rather than a runtime cwd guess.

(require racket/runtime-path
         racket/format
         racket/file
         racket/contract)

;; The src/ directory, resolved at runtime to wherever this file lives.
(define-runtime-path src-dir ".")

;; "01", "02", ... "25" — zero-padded two-digit day labels.
(define (day-label day)
  (~a day #:min-width 2 #:pad-string "0" #:align 'right))

;; Absolute path to inputs/dayNN.txt (sibling of src/).
(define (day-input-path day)
  (build-path src-dir 'up "inputs" (string-append "day" (day-label day) ".txt")))

;; Whole-file contents of inputs/dayNN.txt as a string.
(define (read-day-input day)
  (file->string (day-input-path day)))

(provide
 (contract-out
  [day-label      (-> (integer-in 1 25) string?)]
  [day-input-path (-> (integer-in 1 25) path?)]
  [read-day-input (-> (integer-in 1 25) string?)]))
