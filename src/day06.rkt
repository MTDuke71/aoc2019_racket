#lang racket

;; AoC 2019 Day 6 — Universal Orbit Map.
;;
;; The input is a list of `A)B` facts ("B orbits A"). Every object except
;; COM orbits exactly one other object — which makes the whole map a
;; **rooted tree**: COM is the root, and each `A)B` line is the edge
;; "B's parent is A". Both parts are classic tree queries in disguise:
;;
;;   * Part 1: the orbit-count checksum (direct + indirect orbits) is the
;;     **sum of the depths of every node** — each node contributes one
;;     orbit per ancestor on its path to the root.
;;   * Part 2: minimum orbital transfers from the object YOU orbits to the
;;     object SAN orbits is a **lowest common ancestor (LCA)** query:
;;     walk both ancestor chains to the root, find the deepest node they
;;     share, and the answer is the distance from each starting orbit down
;;     to that meeting point.
;;
;; The only data structure needed is a child -> parent hash. A tree stored
;; this way (each node knows only its parent) is sometimes called a
;; "spaghetti stack" or parent-pointer tree; it's exactly the right shape
;; here because both queries only ever walk *up*.

(require "aoc.rkt")

(provide
 (contract-out
  [parse-input (-> string? (and/c hash? immutable?))]
  [ancestors   (-> hash? string? (listof string?))]
  [part1       (-> hash? exact-nonnegative-integer?)]
  [part2       (-> hash? exact-nonnegative-integer?)]
  [solve       (-> string? void?)]))

;; Each line `A)B` means "B orbits A", i.e. B's parent is A. `for/hash`
;; builds an immutable hash from one (key, value) pair per iteration —
;; `(values child parent)` sets the key to the child, so looking up any
;; object yields the one object it orbits. The argument-free
;; `(string-split s)` splits on whitespace runs, which handles newlines,
;; CRLF, and a trailing newline in one stroke.
(define (parse-input s)
  (for/hash ([line (in-list (string-split s))])
    (match (string-split line ")")
      [(list parent child) (values child parent)])))

;; The chain of objects `obj` orbits, nearest first:
;;   (ancestors parents "L") = '("K" "J" "E" "D" "C" "B" "COM")
;; Walk parent pointers until an object with no parent (COM) ends the
;; climb. `hash-ref` with a `#f` default turns "key absent" into a value
;; we can match on instead of an exception. The named `let` loop is
;; Racket's idiomatic tail-recursive while-loop; consing builds the chain
;; root-first, so one `reverse` at the end restores nearest-first order.
(define (ancestors parents obj)
  (let loop ([obj obj] [acc '()])
    (match (hash-ref parents obj #f)
      [#f (reverse acc)]
      [parent (loop parent (cons parent acc))])))

;; Total direct + indirect orbits = sum of every node's depth. Each
;; object's orbit count is exactly the length of its ancestor chain, and
;; `in-hash-keys` iterates the objects (every object that orbits something
;; appears as a key). This is O(n * depth) — each node re-walks its own
;; path — which is nothing at this input size; the function guide sidebars
;; the O(n) memoized version.
(define (part1 parents)
  (for/sum ([obj (in-hash-keys parents)])
    (length (ancestors parents obj))))

;; Minimum orbital transfers from YOU's orbit to SAN's orbit. Index each
;; of YOU's ancestors with its distance from YOU's current orbit (the
;; nearest ancestor is distance 0), then walk SAN's chain outward until it
;; hits any of them. The first hit is the LOWEST common ancestor — SAN's
;; chain is scanned nearest-first, and `for/first` stops at the first
;; match — and the transfer count is the two distances added together:
;;   d(YOU-orbit, SAN-orbit) = d(YOU-orbit, LCA) + d(SAN-orbit, LCA).
(define (part2 parents)
  (define you-dist
    (for/hash ([obj (in-list (ancestors parents "YOU"))]
               [i (in-naturals)])
      (values obj i)))
  (for/first ([obj (in-list (ancestors parents "SAN"))]
              [i (in-naturals)]
              #:when (hash-has-key? you-dist obj))
    (+ i (hash-ref you-dist obj))))

;; Dispatcher: parse once, print both parts. Mirrors Days 1–5.
(define (solve contents)
  (define parents (parse-input contents))
  (printf "  part 1: ~a\n" (part1 parents))
  (printf "  part 2: ~a\n" (part2 parents)))

(module+ main
  (solve (read-day-input 6)))
