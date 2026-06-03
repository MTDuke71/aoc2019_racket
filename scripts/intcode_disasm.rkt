#lang racket

;; Intcode disassembler + symbolic decompiler (Day 2 opcode subset: 1/2/99).
;;
;; Two passes over a Day 2 Intcode program:
;;
;;   1. LINEAR DISASSEMBLY — sweep the instruction pointer from 0, decode
;;      each 4-wide add/mul instruction into `mem[dst] = mem[a] OP mem[b]`,
;;      stop at the `99` halt, and dump whatever trails the halt as data.
;;
;;   2. SYMBOLIC EXECUTION — re-run the program in the abstract domain of
;;      *affine forms* `c0 + c1·noun + c2·verb`. Position 1 starts as the
;;      symbol `noun`, position 2 as `verb`, everything else as a constant.
;;      Every add/mul combines two affine forms. If a multiply ever has
;;      two non-constant operands the result is quadratic and the abstract
;;      interpretation *fails loudly* — completing the run without that
;;      failure is a PROOF that the program's output is affine in (noun,
;;      verb), which is the whole basis of Day 2's closed-form Part 2.
;;
;; This is the same machinery a real decompiler uses: abstract
;; interpretation, where you run the program over a lattice of approximate
;; values (here: linear polynomials) instead of concrete integers.
;;
;; Usage:  racket scripts/intcode_disasm.rkt [path-to-input]
;;         (defaults to inputs/day02.txt)

(require racket/runtime-path)

(define-runtime-path here ".")

(define (load-program path)
  (list->vector (map string->number
                     (string-split (string-trim (file->string path)) ","))))

;; ---------------------------------------------------------------------------
;; Affine forms: c0 + c1·noun + c2·verb, stored as (vector c0 c1 c2).
;; ---------------------------------------------------------------------------

(define (aff-const k)   (vector k 0 0))
(define noun-sym        (vector 0 1 0))
(define verb-sym        (vector 0 0 1))

(define (aff-const? f)  (and (zero? (vector-ref f 1)) (zero? (vector-ref f 2))))

(define (aff-add x y)
  (vector (+ (vector-ref x 0) (vector-ref y 0))
          (+ (vector-ref x 1) (vector-ref y 1))
          (+ (vector-ref x 2) (vector-ref y 2))))

;; Affine·affine is affine only if at least one side is a constant.
;; Two non-constant operands would be quadratic — refuse and report.
(define (aff-mul x y addr)
  (cond
    [(aff-const? x) (let ([k (vector-ref x 0)])
                      (vector (* k (vector-ref y 0))
                              (* k (vector-ref y 1))
                              (* k (vector-ref y 2))))]
    [(aff-const? y) (aff-mul y x addr)]
    [else (error 'symbolic
                 (string-append
                  "NONLINEAR multiply at address ~a: both operands depend "
                  "on noun/verb — output is not affine on this input")
                 addr)]))

;; Pretty-print "521344 + 368640·noun + verb" (drop zero / unit terms).
(define (aff->string f)
  (define c0 (vector-ref f 0))
  (define c1 (vector-ref f 1))
  (define c2 (vector-ref f 2))
  (define (term coeff sym)
    (cond [(zero? coeff) #f]
          [(= coeff 1)  sym]
          [(= coeff -1) (string-append "-" sym)]
          [else         (string-append (number->string coeff) "·" sym)]))
  (define parts (filter values (list (and (not (zero? c0)) (number->string c0))
                                     (term c1 "noun")
                                     (term c2 "verb"))))
  (cond [(null? parts) "0"]
        [else (string-join parts " + ")]))

;; ---------------------------------------------------------------------------
;; Pass 1: linear disassembly.
;; ---------------------------------------------------------------------------

(define (disassemble prog)
  (printf "=== LINEAR DISASSEMBLY ===\n")
  (printf "addr | raw            | operation\n")
  (printf "-----+----------------+----------------------------------\n")
  (define halt
    (let loop ([ip 0])
      (define op (vector-ref prog ip))
      (cond
        [(= op 99)
         (printf "~a | 99             | HALT\n" (pad ip))
         (+ ip 1)]
        [(or (= op 1) (= op 2))
         (define a   (vector-ref prog (+ ip 1)))
         (define b   (vector-ref prog (+ ip 2)))
         (define dst (vector-ref prog (+ ip 3)))
         (define sym (if (= op 1) "+" "*"))
         (printf "~a | ~a ~a ~a ~a | mem[~a] = mem[~a] ~a mem[~a]\n"
                 (pad ip)
                 (pad3 op) (pad3 a) (pad3 b) (pad3 dst)
                 dst a sym b)
         (loop (+ ip 4))]
        [else (error 'disassemble "bad opcode ~a at ~a" op ip)])))
  (when (< halt (vector-length prog))
    (printf "\nTrailing data after halt (never executed):\n  ")
    (printf "~a\n"
            (string-join
             (for/list ([i (in-range halt (vector-length prog))])
               (format "mem[~a]=~a" i (vector-ref prog i)))
             ", "))))

(define (pad n)  (~a n #:min-width 4 #:align 'right))
(define (pad3 n) (~a n #:min-width 3 #:align 'right))

;; ---------------------------------------------------------------------------
;; Pass 2: symbolic execution over affine forms.
;; ---------------------------------------------------------------------------

(define (symbolic prog #:trace? [trace? #f])
  (printf "\n=== SYMBOLIC EXECUTION (abstract interpretation) ===\n")
  (printf "mem[1] := noun,  mem[2] := verb,  all else constant.\n")
  (when trace?
    (printf "Only steps whose result depends on noun/verb are shown.\n"))
  (printf "\n")
  ;; Abstract memory: each cell is an affine form. Addresses are still read
  ;; from the *concrete* program (operand positions are always literals).
  (define amem (build-vector (vector-length prog)
                             (lambda (i) (aff-const (vector-ref prog i)))))
  (vector-set! amem 1 noun-sym)
  (vector-set! amem 2 verb-sym)
  (let loop ([ip 0])
    (define op (vector-ref prog ip))
    (cond
      [(= op 99) (void)]
      [else
       (define a   (vector-ref prog (+ ip 1)))
       (define b   (vector-ref prog (+ ip 2)))
       (define dst (vector-ref prog (+ ip 3)))
       (define va  (vector-ref amem a))
       (define vb  (vector-ref amem b))
       (define res (if (= op 1) (aff-add va vb) (aff-mul va vb ip)))
       (when (and trace? (not (aff-const? res)))
         (printf "  [~a] mem[~a] := (~a) ~a (~a)  ->  ~a\n"
                 (pad ip) dst (aff->string va) (if (= op 1) "+" "*")
                 (aff->string vb) (aff->string res)))
       (vector-set! amem dst res)
       (loop (+ ip 4))]))
  (define out (vector-ref amem 0))
  (printf "\nSymbolic output at mem[0]:\n  output(noun, verb) = ~a\n"
          (aff->string out))
  (printf "\nThis is affine — abstract interpretation completed with no\n")
  (printf "nonlinear multiply, which PROVES the closed form is exact:\n")
  (printf "  base = ~a,  A = ~a,  B = ~a\n"
          (vector-ref out 0) (vector-ref out 1) (vector-ref out 2))
  out)

;; ---------------------------------------------------------------------------

(module+ main
  (define path
    (let ([args (current-command-line-arguments)])
      (if (zero? (vector-length args))
          (build-path here 'up "inputs" "day02.txt")
          (vector-ref args 0))))
  (define prog (load-program path))
  (printf "Program: ~a cells from ~a\n\n" (vector-length prog) path)
  (disassemble prog)
  (void (symbolic prog #:trace? #t)))
