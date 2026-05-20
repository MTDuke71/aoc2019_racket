# Racket Tutorial - 12-Day Pre-AoC Ramp

A 12-day ramp from "fresh install" to "ready to read/write AoC-style Racket".
Each day gets its own folder and durable README notes.

## Plan

| Day | Topic | What you can do by the end |
|----:|-------|-----------------------------|
| 1 | Install + Hello World + REPL | Run Racket from file and REPL, read first contracts and module shape. |
| 2 | Values, bindings, functions | Write pure functions and reason about basic Racket data types. |
| 3 | Lists, strings, sequence toolkit | Use map/filter/fold and sequence loops for input-like data. |
| 4 | Conditionals and match | Dispatch on structure with match instead of nested conditionals. |
| 5 | Structs and result-shape design | Model state with structs and choose clear return conventions. |
| 6 | Recursion, accumulators, folds | Build linear reducers and tail-recursive loops safely. |
| 7 | Hashes, sets, vectors | Use AoC workhorse data structures and controlled mutation. |
| 8 | Parsing puzzle text | Build parse-input pipelines from raw text to typed shape. |
| 9 | Modules and composition | Split logic into reusable modules with explicit provides. |
| 10 | Testing with RackUnit | Lock examples and actual answers with repeatable tests. |
| 11 | Solve pipeline + timing harness | Standardize parse-input, part1, part2, solve, and timing flow. |
| 12 | Mini puzzle capstone (2019 Day 0) | Solve AoC 2018 Day 1 end-to-end with guide + tests + timing. |

## Notes

- This tutorial is language-first for early days.
- Contracts are the default discipline before any typed/racket branch.
- Day 12 is intentionally the first full puzzle to keep the early pace deliberate.
