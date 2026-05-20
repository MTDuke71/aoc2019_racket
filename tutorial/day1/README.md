# Day 1 - Install + Hello, World!

Goal: verify install, run your first Racket program a few ways, and read your first contract.

Source file: src/hello.rkt

## 1. Verify install

Run:

```powershell
racket --version
raco --version
```

If both print a version, you are ready.

What each tool does:

| Tool | Role | Rust analogue |
|------|------|---------------|
| racket | Runtime + interpreter + REPL entry point | closest to rustc + script runner combo |
| raco | Build/tooling command front-end | cargo |
| DrRacket | IDE/teaching REPL environment | no direct equivalent |

## 2. The program

Open src/hello.rkt:

```racket
#lang racket

(provide
 (contract-out
  [greeting (-> string? string?)]))

(define (greeting name)
  (format "Welcome to Racket, ~a." name))

(module+ main
  (displayln "Hello, World!")
  (displayln (greeting "Matt")))
```

## 3. Three ways to run

### 3a. Direct file run

```powershell
cd tutorial/day1
racket src/hello.rkt
```

### 3b. REPL load and call

```powershell
cd tutorial/day1
racket
```

In the REPL:

```racket
(require "src/hello.rkt")
(greeting "Racket")
(exit)
```

### 3c. DrRacket

Open src/hello.rkt in DrRacket and press Run.

## 4. Read the contract

This line:

```racket
[greeting (-> string? string?)]
```

reads as:

- greeting is a function
- it takes one string
- it returns one string

Rust analogue: this is close to writing an explicit function signature and then enforcing a runtime contract at the module boundary.

### Boundary behavior (important)

`contract-out` checks values when they cross a module boundary.

- If another module calls `greeting` with a non-string, the contract fails.
- If `greeting` returns a non-string, the contract fails.
- Internal calls inside the same module are not checked by `contract-out`.

That makes contracts ideal for exported API surfaces: they document the boundary and enforce it at runtime.

Example caller-side failure:

```racket
;; in some other module
(require "src/hello.rkt")
(greeting 42) ; contract violation: expected string?
```

### Rust analogue at a glance

- Rust type signatures: compile-time guarantees.
- Racket contracts: runtime guarantees at module boundaries.
- Both communicate intent; they differ in when enforcement happens.

## 5. What each piece means

- #lang racket: selects the language/runtime.
- provide: exports names for other modules.
- contract-out: attaches runtime boundary checks to exports.
- module+ main: code that runs when this file is executed directly.

## 5.1 About `~a` in `format`

In this function:

```racket
(define (greeting name)
  (format "Welcome to Racket, ~a." name))
```

`~a` is a placeholder in the format string. It means: insert the next argument in a human-readable way.

- `~a` consumes one argument from `format`.
- Here, that argument is `name`.
- So if `name` is `"Matt"`, the result is `"Welcome to Racket, Matt."`.

Useful contrast:

- `~a`: display-style, user-facing text.
- `~s`: write-style, representation-oriented text (closer to REPL/literal form).

Quick REPL examples:

```racket
(format "X=~a" "hi") ; => "X=hi"
(format "X=~s" "hi") ; => "X=\"hi\""
```

## 6. Try it

1. Call greeting with your own name.
2. Change the output text and rerun.
3. Add a second exported function with a contract:
   - (-> string? string?)
4. Require the file from REPL and call both functions.

## 7. What to remember

- Keep top-level exports explicit.
- Contracts give you signature-like guardrails in untyped Racket.
- module+ main keeps script execution separate from reusable library logic.

Next: Day 2 values, bindings, and pure function mechanics.
