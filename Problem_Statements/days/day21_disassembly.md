# Day 21 — disassembling the springdroid console

> Companion to the [Day 21 function guide](day21_function_guide.md). Tool:
> [python/day21_disasm.py](../../python/day21_disasm.py). Tests: the
> disassembly section of
> [python/tests/test_day21.py](../../python/tests/test_day21.py). Full
> listings (generated locally, gitignored):
> `day21_listing.md` / `day21_alt_listing.md` via
> `python python/day21_disasm.py [inputs/day21_alt.txt] --full`.
>
> 2,050 cells — the second-largest program of the year after
> [Day 13](day13_disassembly.md)'s 2,640, and the most *conventional*
> software yet: a recursive-descent parser with real error diagnostics, a
> bytecode store, a string table, a physics stepper, and an interpreter —
> the springscript machine the statement describes, implemented straight.
> No obfuscation this time. The two secrets are in the data, not the code:
> the hull ships **inside the program** as 9-bit-packed cells, and the
> damage report is an **arithmetic checksum over the holes** —
>
>     damage  =  Σ  (cell address) · (cell value) · (window column)
>
> summed over every hole tile the droid sails over. Both answers come off
> the disk with the VM never started.

## What is new since Day 19

|                     | [Day 17](day17_disassembly.md) | [Day 19](day19_disassembly.md) | Day 21 |
| ------------------- | ------------------------- | ----------------------- | ------ |
| size                | 272 instr, 933/1481 cells | 119 instr + 4 vars, all 424 cells | **431 instr + 300 data cells, all 2,050** |
| world data          | 55×35 RLE bitmap          | none — pure function    | **the hull: 160 nine-bit chunks, two zero-terminated courses** |
| subroutines         | 4, frames + indirect return | 4, one a trampoline   | **13 + an indirect callback — getc/peekc, expect, die, puts, a stepper, an interpreter** |
| self-modification   | 20 operand patches        | 2, one destructive      | **17 operand patches + 1 patched callback pointer** |
| obfuscation         | none to speak of          | the whole program       | **none — honest, even documented (the error strings)** |
| answers off the disk | P1 as data, P2 as formula | both, as one inequality | **both, as one checksum over the hull cells** |

The instruction set froze at [Day 9](day09_function_guide.md); the calling
convention is [Day 17](day17_disassembly.md)'s exactly — return address into
the callee's `rb[+0]`, `arb #n` frames, `arb #-n; jnz #1 rb[+0]` returns.
What is genuinely new is a *program that reads a program*: Day 17's robot
took a movement script as flat input; Day 21 carries a five-keyword
grammar, a token pushback buffer, typed operands, and four distinct error
diagnoses. It is a small assembler, and disassembling it means reading a
parser somebody compiled to Intcode.

## The map

Recursive descent (seeded from 0, every call target, every return address,
and the one patched-in callback) decodes 431 instructions and covers every
code cell except `die`'s five-cell epilogue — dead code after a `hlt` that
nothing can reach. The 17 self-modifying stores are all operand patches
(Intcode's substitute for indexed addressing) plus the one store into
`[1912]`, the callback pointer — control flow is otherwise static.

```
    0 ..   26   boot: print "Input instructions:", enter the parse loop
   27 ..  552   the parser: keyword dispatch, five arms, argument parsing,
                and the 3-cell store into the script table
  553 ..  666   the survey driver: course loop, damage report at 664
  667 ..  715   emit_tiles + put_tile: one hull cell -> 9 window tiles
  716 ..  747   the 32-tile window (10 ground, 9 decoded, 13 ground)
  748 ..  757   ten variables (tmp, ch, op, arg1, arg2, cell, damage,
                running, saw_run_sensor, tileptr)
  758 ..  919   THE HULL: 7 WALK chunks, 0, 153 RUN chunks, 0
  920           count — springscript instructions stored so far
  921 ..  965   the springscript store: 15 slots × 3 cells — the
                15-instruction memory limit is literally this array's size
  966 .. 1261   eight length-prefixed strings (3 prompts, the death
                banner, 4 parser errors)
 1262           buf — a one-character pushback buffer
 1263 .. 1911   the runtime: peekc/getc, expect, skip_ws, puts, die,
                add_damage, run_chunk (stepper + renderer), eval_script,
                in_range
 1912           emit_fn — the patched callback pointer
 1913 .. 2049   emit_bits / bits_rec: 9-digit binary expansion
```

## The parser

The parse loop reads one keyword letter and dispatches on it — `A`, `O`,
`N`, `W`, `R` — then each arm `expect`s the rest of its word letter by
letter. `expect` is two calls deep: `getc` must return the expected
character or the arm `die`s with the address of its error string; `die`
prints a blank line, the diagnosis, another blank line, and halts. The
four diagnoses are exactly the statement's contract, pinned live by
`test_assembler_rejects_bad_scripts`:

* `Invalid operation; expected something like AND, OR, or NOT` — any
  unknown keyword letter;
* `Invalid first argument; expected something like A, B, C, D, J, or T`
  — a bad register, **or a RUN-only sensor in a WALK program**: parsing
  `E`..`I` sets the `saw_run_sensor` flag, and the `WALK` arm checks it
  before starting the survey. The error text is how the machine says
  "you only have four sensors when walking";
* `Invalid second argument; expected J or T` — a read-only destination;
* `Out of memory; at most 15 instructions can be stored` — the count
  check before the store. The "memory" is real: 45 cells at 921,
  three per instruction (`op`, `arg1`, `arg2`), indexed by
  `slot = count*3 + 921` through patched stores.

Registers encode as small integers: sensors `A`..`I` as 1..9 (their
sensing distance!), `J` as −1, `T` as −2. Ops: AND 1, OR 2, NOT 3.

Character input is `peekc`/`getc` over a one-cell pushback buffer at 1262:
`peekc` fills the buffer without clearing it, `getc` takes and clears.
`skip_ws` peeks past spaces and tabs but leaves newlines — a newline is
syntax (it terminates an instruction), which is why `expect(10)` closes
every arm.

## The hull is in the file

The driver walks a cursor over the cells at 758, one per "chunk", zero
terminated — twice. The `WALK` command stops at the first zero (7 chunks)
and reports; `RUN` clears its flag at the zero and keeps going through the
second course (153 more chunks, terminated by the zero at 919). That
single flag test at 654 is the entire difference between Part 1 and
Part 2's worlds — and it is why Part 2 costs 24× the VM instructions.

Each chunk is one cell holding a **9-bit big-endian hazard strip**.
`emit_tiles` hands the value to `emit_bits`, which patches its per-digit
callback into `[1912]`, doubles a power-of-two nine times, and emits
digits MSB-first on the recursion's unwind — each digit landing through
`put_tile` into window cells 726..734. The 32-tile window is otherwise
constant: columns 0..9 and 19..31 are permanent ground baked into the
file. The droid enters every window at column 5 and leaves at column 21,
so between any two 9-bit strips there are **seven guaranteed ground
tiles** (columns 19-20 plus the next window's 5-9).

That quantisation is the day's hidden mercy — see
[guard completeness](#guard-completeness-the-machines-mercy) below.

## The droid is ballistic

`run_chunk` (1463) flies the droid across the current window with three
state variables: column, altitude, and a thrust counter. Every step
advances one column (if standing or airborne), then thrust burns (+1
altitude) or gravity pulls (−1); altitude 0 over ground snaps back to 1.
So an ordinary walking step is literally *fall one tile and land*, and a
jump is `thrust = 2`: up, up, down, down — four columns, landing exactly
on sensor D's tile. Walking into a hole is the same fall with nothing to
snap onto; altitude < 1 is death. The springscript runs **only when the
droid stands on ground at altitude 1** — over a hole it just coasts.

`eval_script` (1694) is the springscript interpreter: J and T zeroed *per
evaluation* (the memoryless property is enforced by the machine, not just
described by the statement), then one pass over the stored triples: AND
is `mul`, OR is `add` then `0 <`, NOT is `== 0`; sensor operand `k` reads
the window tile at `column + k` through a patched fetch — sensing
distance is literally the register's encoded value.

The death replay the puzzle shows is the same stepper re-run with its
render flag up (the driver re-flies the fatal chunk after printing the
banner): three sky rows plus the hull row, columns 5..21, `@` where
`row == altitude`, and the tile glyph computed as `tile*(-11) + 46` —
46 is `.`, 35 is `#`. The renderer is why the statement's pictures are
17 characters wide.

## The damage checksum

`add_damage` (1444) is three instructions:

    damage += [593] * [753] * rb[1]     ; hull-cell ADDRESS × cell VALUE × COLUMN

called once for every step the droid spends over a hole. Motion is one
column per step and a droid cannot land in a hole, so a *surviving* droid
overflies every hole exactly once — the total is a pure function of the
hull data, independent of which script crosses
(`test_damage_is_script_independent` pins it live: the 9-instruction RUN
variant reports the same damage as the shipping 8). Part 1, decomposed:

| cell | value | strip | hole columns | addr·val·Σcols |
|-----:|------:|:------|:-------------|---------------:|
| 758 | 255 | `.########` | 10 | 1,932,900 |
| 759 | 63 | `...######` | 10, 11, 12 | 1,577,961 |
| 760 | 191 | `.#.######` | 10, 12 | 3,193,520 |
| 761 | 95 | `..#.#####` | 10, 11, 13 | 2,458,030 |
| 762 | 223 | `.##.#####` | 10, 13 | 3,908,298 |
| 763 | 159 | `.#..#####` | 10, 12, 13 | 4,246,095 |
| 764 | 127 | `..#######` | 10, 11 | 2,037,588 |
| | | | | **19,354,392** |

`static_answers` does this for both courses — with the faithful Python
stepper first verifying, chunk by chunk, that the shipping scripts
actually survive — and matches the live machine on both parts of both
files (`test_static_answers_match_the_machine`). The first chunk's window
is, verbatim, the statement's example rendering: the 255 at cell 758
decodes to `#####.###########`.

## Guard completeness: the machine's mercy

The function guide proved the RUN guard `¬(A·B·C)·D·(E∨H)` is **not** a
planner: a 15-tile synthetic hull defeats it. The encoding explains why
the machine never gets to play that card. A chunk is 9 free tiles between
guaranteed footing, and over the whole 512-pattern chunk universe:

* **344** patterns are crossable at all (the rest contain a 4-wide hole
  or an unreachable landing);
* the guard crosses **all 344** — zero mismatches against the
  reachability DP (`test_guard_is_complete_for_the_chunk_universe`);
* the unguarded WALK policy dies in 22 of them, and each input's RUN
  course actually contains **10 trap chunks** of that family
  (`.#.##.##.`-shaped: forced early jump onto a landing with both exits
  bad) — which is why Part 2 exists at all.

The synthetic killer hull needs an 11-tile hazard span; 9 bits cannot
express it. So *given this hull encoding*, "the guard survives every hull
the generator can emit" is a theorem, and the machine accepting the
script was never in doubt. The statement's difficulty is calibrated by
the chunk width.

## A second user's file

`inputs/day21_alt.txt`: same 2,050 cells, **540 differ** — and the
classifier (`classify_diffs`) proves every one of them is one of two
things:

* **383 cells across 175 instructions: encoding coin-flips.** The same
  constant spelled `add #a #b` vs `mul #a #b`, commutative operands
  swapped, unconditional jumps spelled `jnz #1` vs `jz #0` — and one
  subtler consequence: at 1765 the operand swap moves the *patched*
  operand cell (`[1766]` in one file, `[1767]` in the other), so the two
  patch stores at 1757/1761 aim at different addresses while meaning the
  identical thing ("the operand of the fetch at 1765").
  [Day 19](day19_disassembly.md)'s identity-operand shuffle, seen from
  the patching side. Canonicalising both streams — constants evaluated,
  copies reduced, commutative operands sorted, patch targets named by
  their owning instruction — makes the 431-instruction programs equal.
* **157 hull cells.** The payload.

And the payload is more constrained than "random": both files carry a
7-chunk WALK course with **16 holes**, a 153-chunk RUN course with
**674 holes**, and exactly **10 trap chunks**
(`test_recovered_courses_share_one_profile`,
`test_run_course_needs_the_guard`). The generator fixes the whole
difficulty profile and shuffles only where the holes fall; two users'
puzzles differ in *arrangement*, nothing else. Alt answers, recovered
statically and confirmed live: 19362822 / 1143625214.

## Tests pinned by this analysis

* `test_static_answers_match_the_machine` — the checksum, over both
  users' files, against the live VM.
* `test_recovered_courses_share_one_profile` — 7/16 and 153/674 on both
  files.
* `test_first_walk_chunk_is_the_statement_window` — cell 758's 255 *is*
  the statement's example rendering.
* `test_stepper_replays_the_suicide_and_the_crossing` — the faithful
  Python stepper agrees with the machine on the statement's own death.
* `test_guard_is_complete_for_the_chunk_universe` — 344/344, and 22
  chunks where the unguarded policy dies.
* `test_run_course_needs_the_guard` — 10 live traps per file.
* `test_damage_is_script_independent` — a different surviving script,
  same damage.
* `test_assembler_rejects_bad_scripts` — all four parser diagnoses,
  provoked through the console.
* `test_diff_classification` — 540 = 383 (coin-flips, proved) + 157
  (hull).
* `test_full_listing_accounts_for_every_cell` — 2,050 cells, once each,
  160 of them hull chunks.
