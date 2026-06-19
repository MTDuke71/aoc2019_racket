#lang racket

;; Intcode disassembler + symbolic decompiler.
;;
;; Two eras of Intcode, two strategies:
;;
;;   * DAY 2 subset (opcodes 1/2/99, all position mode, no branches). A
;;     LINEAR sweep is a complete disassembly because the code is one
;;     straight basic block. A second pass does SYMBOLIC EXECUTION over the
;;     abstract domain of affine forms `c0 + c1·noun + c2·verb` to *prove*
;;     the output is affine (the basis of Day 2's closed-form Part 2). If a
;;     multiply ever has two non-constant operands the result is quadratic
;;     and the abstract interpreter fails loudly.
;;
;;   * DAY 5+ subset (opcodes 1–8/99, parameter modes, jumps). A linear
;;     sweep stops being correct: jump opcodes (5/6) make the next
;;     instruction address data-dependent, and the program interleaves code
;;     with jump-table data, so decode order no longer matches address
;;     order. We switch to RECURSIVE-DESCENT (control-flow-following)
;;     disassembly: start at the entry point, decode, and follow each
;;     instruction's successors — fall-through for sequential ops, and BOTH
;;     the fall-through and the (static, immediate-mode) target for jumps.
;;     Only cells actually reachable as code get decoded; the rest are data.
;;
;; The script auto-detects which era a program belongs to (by opcodes and
;; filename) and runs the matching passes:
;;   Day 2  — linear sweep + affine symbolic proof
;;   Day 5  — recursive descent (shows self-mod limits) + dynamic trace
;;   Day 7  — phase dispatch table + module disassembly + per-phase trace
;;
;; Usage:  racket scripts/intcode_disasm.rkt [path-to-input]
;;         (defaults to inputs/day02.txt)

(require racket/runtime-path
         (prefix-in d05: "../src/day05.rkt"))

(define-runtime-path here ".")

(define (load-program path)
  (list->vector (map string->number
                     (string-split (string-trim (file->string path)) ","))))

(define (pad n)  (~a n #:min-width 4 #:align 'right))
(define (pad3 n) (~a n #:min-width 3 #:align 'right))

;; ===========================================================================
;; DAY 2 ERA — linear disassembly + affine symbolic execution
;; ===========================================================================

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
;; Pass 1: linear disassembly (Day 2 subset).
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

;; ---------------------------------------------------------------------------
;; Pass 2: symbolic execution over affine forms (Day 2 subset).
;; ---------------------------------------------------------------------------

(define (symbolic prog #:trace? [trace? #f])
  (printf "\n=== SYMBOLIC EXECUTION (abstract interpretation) ===\n")
  (printf "mem[1] := noun,  mem[2] := verb,  all else constant.\n")
  (when trace?
    (printf "Only steps whose result depends on noun/verb are shown.\n"))
  (printf "\n")
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

;; ===========================================================================
;; DAY 5+ ERA — mode-aware decode + recursive-descent disassembly
;; ===========================================================================

;; opcode -> (mnemonic . width), where width counts the opcode cell.
(define op-table
  (hash 1 '(add . 4) 2 '(mul . 4) 3 '(in . 2) 4 '(out . 2)
        5 '(jt  . 3) 6 '(jf  . 3) 7 '(lt . 4) 8 '(eq  . 4) 99 '(halt . 1)))

;; Parameter mode of the nth (1-based) parameter of instruction word `instr`:
;; the nth digit above the two-digit opcode. 0 = position, 1 = immediate.
(define (param-mode instr n)
  (modulo (quotient instr (* 100 (expt 10 (sub1 n)))) 10))

;; Render a READ operand (mode-aware): #k for immediate, mem[k] for position.
(define (render-read prog ip n)
  (define raw (vector-ref prog (+ ip n)))
  (if (= 1 (param-mode (vector-ref prog ip) n))
      (format "#~a" raw)
      (format "mem[~a]" raw)))

;; Render a WRITE operand — always position mode by spec.
(define (render-write prog ip n)
  (format "mem[~a]" (vector-ref prog (+ ip n))))

;; Decode one instruction at ip: return (values text width successors).
;; `successors` are the addresses control can flow to next. For jumps we
;; include the fall-through AND the target when the target is an immediate
;; (statically known); a position-mode target is data-dependent and omitted.
(define (decode prog ip)
  (define instr (vector-ref prog ip))
  (define op (modulo instr 100))
  (define entry (hash-ref op-table op #f))
  (cond
    [(not entry) (values (format "??? raw=~a" instr) 1 '())]
    [else
     (define (R n) (render-read prog ip n))
     (define (W n) (render-write prog ip n))
     (case op
       [(1)  (values (format "~a = ~a + ~a"  (W 3) (R 1) (R 2)) 4 (list (+ ip 4)))]
       [(2)  (values (format "~a = ~a * ~a"  (W 3) (R 1) (R 2)) 4 (list (+ ip 4)))]
       [(3)  (values (format "~a = INPUT"    (W 1))             2 (list (+ ip 2)))]
       [(4)  (values (format "OUTPUT ~a"     (R 1))             2 (list (+ ip 2)))]
       [(5)  (values (format "if ~a != 0 jump ~a" (R 1) (R 2))  3 (jump-succs prog ip))]
       [(6)  (values (format "if ~a == 0 jump ~a" (R 1) (R 2))  3 (jump-succs prog ip))]
       [(7)  (values (format "~a = (~a < ~a)"  (W 3) (R 1) (R 2)) 4 (list (+ ip 4)))]
       [(8)  (values (format "~a = (~a == ~a)" (W 3) (R 1) (R 2)) 4 (list (+ ip 4)))]
       [(99) (values "HALT" 1 '())])]))

(define (jump-succs prog ip)
  (define fall (+ ip 3))
  (if (= 1 (param-mode (vector-ref prog ip) 2))
      (list fall (vector-ref prog (+ ip 2)))   ; immediate target is static
      (list fall)))                            ; position target: unknown

;; Recursive-descent: follow control flow from address 0, returning a hash
;; ip -> (text . width) for every instruction reachable as code.
(define (trace-code prog)
  (define n (vector-length prog))
  (define starts (make-hash))
  (let loop ([work (list 0)])
    (unless (null? work)
      (define ip (car work))
      (cond
        [(or (< ip 0) (>= ip n) (hash-has-key? starts ip))
         (loop (cdr work))]
        [else
         (define-values (text width succs) (decode prog ip))
         (hash-set! starts ip (cons text width))
         (loop (append succs (cdr work)))])))
  starts)

;; Print the reachable code in address order, with non-code cells shown as
;; data runs. Returns the list of decoded opcodes (for the summary).
(define (disassemble-cfg prog starts)
  (printf "=== RECURSIVE-DESCENT DISASSEMBLY (control-flow-following) ===\n")
  (printf "addr | raw                      | operation\n")
  (printf "-----+--------------------------+-------------------------------------\n")
  (define n (vector-length prog))
  (define (flush data)            ; data: indices accumulated in reverse
    (unless (null? data)
      (define idxs (reverse data))
      (define vals (for/list ([i (in-list idxs)]) (vector-ref prog i)))
      (define shown
        (if (> (length vals) 12)
            (string-append (string-join (map number->string (take vals 12)) ", ")
                           (format ", … (~a data cells)" (length vals)))
            (string-join (map number->string vals) ", ")))
      (printf "~a | ~a | data: ~a\n"
              (pad (first idxs)) (~a "" #:min-width 24) shown)))
  (let loop ([i 0] [data '()] [ops '()])
    (cond
      [(>= i n) (flush data) (reverse ops)]
      [(hash-has-key? starts i)
       (flush data)
       (match-define (cons text width) (hash-ref starts i))
       (define raw (string-join (for/list ([k (in-range width)])
                                  (number->string (vector-ref prog (+ i k)))) " "))
       (printf "~a | ~a | ~a\n" (pad i) (~a raw #:min-width 24) text)
       (loop (+ i width) '() (cons (modulo (vector-ref prog i) 100) ops))]
      [else (loop (+ i 1) (cons i data) ops)])))

(define op-name (hash 1 "add" 2 "mul" 3 "in" 4 "out"
                      5 "jump-if-true" 6 "jump-if-false"
                      7 "less-than" 8 "equals" 99 "halt"))

(define (summarize-ops ops)
  (printf "\n=== REACHABLE-CODE OPCODE HISTOGRAM ===\n")
  (define counts (make-hash))
  (for ([o (in-list ops)]) (hash-update! counts o add1 0))
  (printf "~a instructions reachable from entry.\n\n" (length ops))
  (for ([o (in-list (sort (hash-keys counts) <))])
    (printf "  ~a  ~a (~a)\n"
            (~a (hash-ref counts o) #:min-width 4 #:align 'right)
            (hash-ref op-name o "?") o))
  (define cmp (+ (hash-ref counts 7 0) (hash-ref counts 8 0)))
  (define jmp (+ (hash-ref counts 5 0) (hash-ref counts 6 0)))
  (printf "\n  comparisons (less-than + equals): ~a\n" cmp)
  (printf "  jumps       (jit + jif):          ~a\n" jmp))

;; ---------------------------------------------------------------------------
;; Dynamic disassembly: execute the program (so self-modification resolves),
;; decoding each instruction against LIVE memory. This is the correct
;; disassembly when static descent is defeated by self-modifying code.
;; Returns (values executed-opcodes outputs instruction-count).
;; ---------------------------------------------------------------------------
(define (trace-exec prog input #:log? [log? #f] #:limit [limit 1000000])
  (define mem (vector-copy prog))
  (define (val ip n)
    (define raw (vector-ref mem (+ ip n)))
    (if (= 1 (param-mode (vector-ref mem ip) n)) raw (vector-ref mem raw)))
  (define (dst ip n) (vector-ref mem (+ ip n)))
  (let loop ([ip 0] [ops '()] [outs '()] [count 0])
    (when (> count limit) (error 'trace-exec "instruction limit exceeded"))
    (when log?
      (define-values (text _w _s) (decode mem ip))
      (printf "~a | ~a\n" (pad ip) text))
    (define op (modulo (vector-ref mem ip) 100))
    (define (step ip* o) (loop ip* (cons op ops) o (add1 count)))
    (case op
      [(1)  (vector-set! mem (dst ip 3) (+ (val ip 1) (val ip 2))) (step (+ ip 4) outs)]
      [(2)  (vector-set! mem (dst ip 3) (* (val ip 1) (val ip 2))) (step (+ ip 4) outs)]
      [(3)  (vector-set! mem (dst ip 1) input)                     (step (+ ip 2) outs)]
      [(4)  (step (+ ip 2) (cons (val ip 1) outs))]
      [(5)  (step (if (not (zero? (val ip 1))) (val ip 2) (+ ip 3)) outs)]
      [(6)  (step (if (zero? (val ip 1))       (val ip 2) (+ ip 3)) outs)]
      [(7)  (vector-set! mem (dst ip 3) (if (< (val ip 1) (val ip 2)) 1 0)) (step (+ ip 4) outs)]
      [(8)  (vector-set! mem (dst ip 3) (if (= (val ip 1) (val ip 2)) 1 0)) (step (+ ip 4) outs)]
      [(99) (values (reverse ops) (reverse outs) count)]
      [else (error 'trace-exec "bad opcode ~a at ~a" op ip)])))

;; Dynamic trace with an input queue (Day 7 amplifiers). Uses growable memory.
;; Returns (values executed-opcodes outputs instruction-count).
(define (trace-exec/inputs prog inputs #:log? [log? #f] #:limit [limit 1000000])
  (define mem (d05:intcode-mem prog))
  (define (val ip n)
    (define raw (d05:intcode-ref mem (+ ip n)))
    (if (= 1 (param-mode (d05:intcode-ref mem ip) n)) raw (d05:intcode-ref mem raw)))
  (define (dst ip n) (d05:intcode-ref mem (+ ip n)))
  (let loop ([ip 0] [pending inputs] [ops '()] [outs '()] [count 0])
    (when (> count limit) (error 'trace-exec/inputs "instruction limit exceeded"))
    (when log?
      (define-values (text _w _s) (decode (unbox mem) ip))
      (printf "~a | ~a\n" (pad ip) text))
    (define op (modulo (d05:intcode-ref mem ip) 100))
    (define (step ip* o p) (loop ip* p (cons op ops) o (add1 count)))
    (case op
      [(1)  (d05:intcode-set! mem (dst ip 3) (+ (val ip 1) (val ip 2))) (step (+ ip 4) outs pending)]
      [(2)  (d05:intcode-set! mem (dst ip 3) (* (val ip 1) (val ip 2))) (step (+ ip 4) outs pending)]
      [(3)  (unless (pair? pending) (error 'trace-exec/inputs "input exhausted at ~a" ip))
             (d05:intcode-set! mem (dst ip 1) (car pending))
             (step (+ ip 2) outs (cdr pending))]
      [(4)  (step (+ ip 2) (cons (val ip 1) outs) pending)]
      [(5)  (step (if (not (zero? (val ip 1))) (val ip 2) (+ ip 3)) outs pending)]
      [(6)  (step (if (zero? (val ip 1))       (val ip 2) (+ ip 3)) outs pending)]
      [(7)  (d05:intcode-set! mem (dst ip 3) (if (< (val ip 1) (val ip 2)) 1 0)) (step (+ ip 4) outs pending)]
      [(8)  (d05:intcode-set! mem (dst ip 3) (if (= (val ip 1) (val ip 2)) 1 0)) (step (+ ip 4) outs pending)]
      [(99) (values (reverse ops) (reverse outs) count)]
      [else (error 'trace-exec/inputs "bad opcode ~a at ~a" op ip)])))

;; Static disassembly of one straight-line module from `start` until HALT.
(define (disasm-module prog start [max 30])
  (printf "--- module entry ~a ---\n" start)
  (let loop ([ip start] [n 0])
    (when (< n max)
      (define-values (text width _s) (decode prog ip))
      (define op (modulo (vector-ref prog ip) 100))
      (define raw (string-join (for/list ([k (in-range width)])
                                 (number->string (vector-ref prog (+ ip k)))) " "))
      (printf "~a | ~a | ~a\n" (pad ip) (~a raw #:min-width 24) text)
      (unless (= op 99) (loop (+ ip width) (add1 n))))))

(define (day7-amplifier? path prog)
  (define s (if (path? path) (path->string path) path))
  (and (regexp-match? #rx"day07" s)
       (>= (vector-length prog) 21)
       (= (vector-ref prog 0) 3)
       (= (vector-ref prog 1) 8)))

(define (run-day7-disasm prog)
  (printf "=== AMPLIFIER DISPATCH PROLOGUE (static) ===\n")
  (printf "addr | raw                      | operation\n")
  (printf "-----+--------------------------+-------------------------------------\n")
  (for ([ip '(0 2 6)])
    (define-values (text width _s) (decode prog ip))
    (define raw (string-join (for/list ([k (in-range width)])
                               (number->string (vector-ref prog (+ ip k)))) " "))
    (printf "~a | ~a | ~a\n" (pad ip) (~a raw #:min-width 24) text))
  (printf "\nThe jump at address 6 uses position-mode target mem[8]. Static decode\n")
  (printf "shows mem[0] (the on-disk value at address 8 is 0), but the prior\n")
  (printf "instruction just wrote phase+10 into mem[8], so at runtime the jump\n")
  (printf "goes to mem[phase+10] — the dispatch table entry. Operand overlap.\n")
  (printf "\n=== PHASE DISPATCH TABLE (mem[10..19]) ===\n")
  (for ([p (in-range 10)])
    (printf "  phase ~a  ->  ip ~a\n" p (vector-ref prog (+ 10 p))))
  (printf "\n=== PART 1 MODULES (phases 0–4): static disassembly ===\n")
  (printf "Each module: INPUT signal -> affine arithmetic -> one OUTPUT -> HALT\n\n")
  (for ([p (in-range 5)])
    (disasm-module prog (vector-ref prog (+ 10 p))))
  (printf "\n=== PART 2 MODULES (phases 5–9): static disassembly (first lines) ===\n")
  (printf "Each module: repeated INPUT -> transform -> OUTPUT loops (feedback I/O)\n\n")
  (for ([p (in-range 5 10)])
    (disasm-module prog (vector-ref prog (+ 10 p)) 12))
  (printf "\n=== DYNAMIC TRACE — single amp, inputs [phase, signal=0] ===\n")
  (printf "(Part 1 path: two inputs suffice. Part 2 modules need a signal stream.)\n\n")
  (for ([p (in-range 10)])
    (with-handlers ([exn:fail? (lambda (e)
                                  (printf "phase ~a: blocked after ~a inputs (~a)\n"
                                          p 2 (exn-message e)))])
      (define-values (ops outs count) (trace-exec/inputs prog (list p 0)))
      (printf "phase ~a: ~a instructions, output ~a\n" p count (last outs))
      (summarize-ops ops)))
  (printf "\nAffine symbolic pass skipped: phase dispatch + I/O streams.\n"))

;; ===========================================================================

;; A program is "Day 2 era" iff its reachable code uses only opcodes 1/2/99.
(define (day2-era? starts prog)
  (for/and ([ip (in-list (hash-keys starts))])
    (memv (modulo (vector-ref prog ip) 100) '(1 2 99))))

(module+ main
  (define path
    (let ([args (current-command-line-arguments)])
      (if (zero? (vector-length args))
          (build-path here 'up "inputs" "day02.txt")
          (vector-ref args 0))))
  (define prog (load-program path))
  (printf "Program: ~a cells from ~a\n\n" (vector-length prog) path)
  (define starts (trace-code prog))
  (cond
    [(day7-amplifier? path prog)
     (run-day7-disasm prog)]
    [(day2-era? starts prog)
     ;; Branchless Day 2 code: linear sweep + affine proof.
     (disassemble prog)
     (void (symbolic prog #:trace? #t))]
    [else
     ;; Day 5+ : static recursive descent first (to expose its limits),
     ;; then the dynamic trace that actually disassembles the program.
     (define static-ops (disassemble-cfg prog starts))
     (printf "\nStatic descent decoded only ~a instruction(s) before control\n"
             (length static-ops))
     (printf "flowed into a cell modified at runtime: this program is\n")
     (printf "SELF-MODIFYING, so static disassembly is incomplete. Executing\n")
     (printf "the program is the only faithful disassembly.\n")
     (for ([in (in-list '(1 5))])
       (define-values (exec-ops outs count) (trace-exec prog in))
       (printf "\n=== DYNAMIC TRACE — input ~a ===\n" in)
       (printf "~a instructions executed.\n" count)
       (printf "outputs (~a): ~a\n" (length outs) outs)
       (summarize-ops exec-ops))
     (printf "\nAffine symbolic pass skipped: this program branches, so its\n")
     (printf "output is not a single affine form of the input (Day 2 only).\n")]))
