# AoC 2019 in Racket

This repository is the Racket leg of a four-language Advent of Code rotation.

## Current defaults (Day 1 decisions)

- Language mode: untyped Racket first, with explicit contracts on top-level exports.
- Tutorial pacing: 12-day ramp, with the first full mini puzzle on Day 12.
- Day 12 capstone puzzle: AoC 2018 Day 1 treated as the 2019 tutorial "Day 0" puzzle.

## Project layout

- tutorial/day1 ... tutorial/day12
- src
- test
- bench
- Problem_Statements/days
- python
- reference
- inputs

## Quick start

1. Install Racket for Windows: https://download.racket-lang.org/
2. Verify tools:
   - racket --version
   - raco --version
3. Run tutorial Day 1:
   - cd tutorial/day1
   - racket src/hello.rkt
4. Open REPL:
   - racket

## Tutorial index

See tutorial plan in tutorial/README.md.
