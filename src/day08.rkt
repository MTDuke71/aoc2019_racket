#lang racket

;; AoC 2019 Day 8 — Space Image Format.
;;
;; A flat string of digits is really a stack of identically sized image
;; **layers**: width × height pixels each, filled row-major, layers
;; back-to-front. The whole day is one act of reshaping that 1-D string
;; into a 3-D (layer, row, col) array and asking two questions about it:
;;
;;   * Part 1 — a **corruption checksum**: find the layer with the fewest
;;     `0` digits, then report (count of `1`s) × (count of `2`s) on it.
;;     Pure per-layer histogramming; no geometry needed.
;;   * Part 2 — **decode the image**: the layers are stacked front-to-back
;;     and each pixel is the first *non-transparent* (`2`) value seen from
;;     the front — `0` = black, `1` = white. Render the W×H result and the
;;     lit pixels spell out letters a human reads off.
;;
;; The one idea worth naming is the index arithmetic: a pixel at
;; (layer L, row r, col c) lives at flat offset `L·(W·H) + r·W + c`. Part 1
;; only needs the layer chunking (`L·(W·H)`); Part 2 needs the full
;; back-to-front scan down the `L` axis at each fixed (r, c).

(require "aoc.rkt")

(provide
 (contract-out
  [parse-input   (-> string? (vectorof byte?))]
  [image-layers  (-> (vectorof byte?) exact-positive-integer? exact-positive-integer?
                     (listof (vectorof byte?)))]
  [decode-image  (-> (vectorof byte?) exact-positive-integer? exact-positive-integer?
                     (vectorof byte?))]
  [render        (-> (vectorof byte?) exact-positive-integer? exact-positive-integer?
                     string?)]
  [part1         (-> (vectorof byte?) exact-positive-integer? exact-positive-integer?
                     exact-nonnegative-integer?)]
  [part2         (-> (vectorof byte?) exact-positive-integer? exact-positive-integer?
                     string?)]
  [solve         (-> string? void?)]))

;; The real image is 25 wide by 6 tall; the worked examples use other
;; sizes, so the dimensions are *arguments* to every shape function rather
;; than baked in. Only `solve` commits to the puzzle's 25×6.
(define WIDTH 25)
(define HEIGHT 6)

;; The flat digit string -> a vector of single-digit bytes. `string-trim`
;; drops the trailing newline; `in-string` walks the characters; the
;; `#\0`-relative subtraction is the ASCII digit-to-value trick (Rust's
;; `c.to_digit(10)`). A vector (not a list) because both parts index into
;; it by computed offset.
(define (parse-input s)
  (for/vector ([c (in-string (string-trim s))]
               #:when (char-numeric? c))
    (- (char->integer c) (char->integer #\0))))

;; Chop the flat vector into its layers, each `width·height` pixels.
;; `(in-range 0 N size)` strides by a full layer, and `vector-copy` slices
;; `[start, start+size)` — so this is the 1-D → list-of-layers reshape.
(define (image-layers digits width height)
  (define size (* width height))
  (for/list ([start (in-range 0 (vector-length digits) size)])
    (vector-copy digits start (+ start size))))

;; How many times digit `d` appears in one layer. `vector-count` (from
;; racket/vector) is the vector sibling of `count` — it tallies elements
;; satisfying the predicate.
(define (digit-count layer d)
  (vector-count (lambda (x) (= x d)) layer))

;; Part 1: the layer with the fewest 0s is the least-corrupted one;
;; `argmin` returns the *element* minimizing the key (here its zero-count),
;; not the index. On that layer, the checksum is #1s × #2s.
(define (part1 digits width height)
  (define fewest-zeros
    (argmin (lambda (layer) (digit-count layer 0))
            (image-layers digits width height)))
  (* (digit-count fewest-zeros 1)
     (digit-count fewest-zeros 2)))

;; Stack the layers front-to-back and resolve each pixel. For a fixed
;; position `p` (a row-major offset within a layer), scan down the layer
;; axis and take the first value that isn't 2 (transparent) — that's the
;; topmost opaque pixel. `for/first` with the `#:unless` guard is exactly
;; "first layer where this pixel is opaque"; the puzzle guarantees every
;; pixel is opaque in *some* layer, so the search always succeeds.
(define (decode-image digits width height)
  (define size (* width height))
  (define n-layers (quotient (vector-length digits) size))
  (for/vector ([p (in-range size)])
    (for/first ([l (in-range n-layers)]
                #:unless (= 2 (vector-ref digits (+ (* l size) p))))
      (vector-ref digits (+ (* l size) p)))))

;; A flat W·H pixel vector -> a printable block of `height` rows. Lit (1)
;; pixels become `#`, black (0) become a space; the lit shapes spell the
;; answer. `string-join` with "\n" stitches the rows.
(define (render pixels width height)
  (string-join
   (for/list ([row (in-range height)])
     (list->string
      (for/list ([col (in-range width)])
        (if (= 1 (vector-ref pixels (+ (* row width) col))) #\# #\space))))
   "\n"))

;; Part 2: decode, then render to the human-readable text block.
(define (part2 digits width height)
  (render (decode-image digits width height) width height))

;; Dispatcher: parse once, print both parts. Part 2 is a multi-line image,
;; so it prints under a header on its own lines.
(define (solve contents)
  (define digits (parse-input contents))
  (printf "  part 1: ~a\n" (part1 digits WIDTH HEIGHT))
  (printf "  part 2:\n~a\n" (part2 digits WIDTH HEIGHT)))

(module+ main
  (solve (read-day-input 8)))
