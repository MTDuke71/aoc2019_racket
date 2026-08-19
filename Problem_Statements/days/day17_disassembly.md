# Day 17 — disassembling the ASCII controller

> Companion to the [Day 17 function guide](day17_function_guide.md). Tool:
> [python/day17_disasm.py](../../python/day17_disasm.py). Tests:
> [python/tests/test_day17.py](../../python/tests/test_day17.py).
>
> 1481 cells, and the most *architecturally* interesting program of the year so
> far. Where [Day 15](day15_disassembly.md)'s controller was 70 instructions
> with no subroutines and no stack, this one has a **calling convention** —
> return address in `rb[0]`, a frame opened with `arb +n`, an indirect return —
> four subroutines, a **string table**, a **run-length-compressed bitmap** of
> the scaffold, a **recursive-descent parser** with real error messages, and a
> **two-level bytecode interpreter** for the very grammar the puzzle asks you
> to write. The scaffold is *stored* in the file, not computed, so Part 1 comes
> out with the VM never started — and Part 2 does too, because the dust counter
> turns out to be a deterministic formula rather than a simulation artefact.

## What is new since Day 15

|                      | Day 15                  | Day 17                                          |
| -------------------- | ----------------------- | ----------------------------------------------- |
| size                 | 70 instructions, 0–251 | 272 instructions, 933 of 1481 cells             |
| subroutines          | none                    | **4**, with frames and an indirect return |
| stack                | none                    | relative base as frame pointer                  |
| self-modification    | one operand patch       | **20**, all operand patches               |
| world data           | 39×20 edge table, raw  | 55×35 bitmap,**run-length encoded**      |
| input handling       | one command code        | ASCII parser with five error messages           |
| answers off the disk | both, as literals       | Part 1 as data,**Part 2 as a formula**    |

The instruction set is identical — it froze at [Day 9](day09_function_guide.md).
Everything above is built out of `add`, `mul` and `jz`.

---

## The calling convention

Intcode has no `call` and no `return`. This program builds both out of the
relative base, and the idiom is worth recognising on sight:

```text
   51: add  #0 #58 rb[+0]     ; return address into the callee's slot 0
   55: jnz  #1 #786           ; ... then jump
```

and at the other end:

```text
  786: arb  #7                ; open a 7-cell frame
        ...                   ; locals live at rb[-1] .. rb[-6]
  974: arb  #-7               ; close it
  976: jnz  #1 rb[+0]         ; indirect jump back
```

`arb #7` moves the base *up*, so the caller's `rb[+0]` write lands exactly on
the callee's `rb[-7]`, and after the callee's own `arb #7` that same cell is
its `rb[+0]` again. The frame is the argument-passing area, the local slots and
the return address all at once — a stack frame in the ordinary sense, with the
relative base playing frame pointer.

**This is why plain recursive descent fails on this program.** The return is an
indirect jump through a runtime value, and a disassembler cannot follow it.
Descending from address 0 alone reaches 71 instructions and stops at the first
call. The fix is to recognise the *idiom* and seed the descent with both the
call targets and the return addresses:

```python
def call_sites(mem):
    """Every `rb[0] = ret; jmp target` pair -> {call address: (target, ret)}."""
    found = {}
    for addr in range(len(mem) - 7):
        if mem[addr] not in (21101, 21102) or mem[addr + 3] != 0:
            continue
        if mem[addr + 4] not in (1105, 1106):
            continue
        a, b = mem[addr + 1], mem[addr + 2]
        found[addr] = (mem[addr + 6], a + b if mem[addr] == 21101 else a * b)
    return found
```

Address 58 — everything the program does after its first call — is reachable no
other way. With returns seeded, descent covers **933 cells with no gaps**, and
the 548 cells left over are exactly the string table (330–578) and the
run-length table (1182–1480). Static descent is **complete** here, as it was on
Day 15 and unlike Day 11 (`test_static_descent_is_complete`).

Twenty call sites, four subroutines:

| entry | frame | what it is                                                           |
| ----: | ----: | -------------------------------------------------------------------- |
|   579 |     4 | `puts` — print the string at `rb[1]`                            |
|   622 |     5 | `interpret` — run a movement program; **calls itself once** |
|   786 |     7 | `draw` — render one frame, and vacuum the robot's cell            |
|   979 |     6 | `parse_line` — one ASCII line into the internal bytecode          |

---

## Memory map

```text
    0.. 150  code   bootstrap: RLE decompressor, mode select, input reader
  151.. 188  code   error paths (unreached on a valid script)
  189.. 329  code   part 2 driver: prompt, parse, interpret, report dust
  330.. 557  data   string table (prompts and error messages)
  558.. 561  data   glyph table '^>v<'
  562.. 565  data   dx [0, 1, 0, -1]
  566.. 569  data   dy [-1, 0, 1, 0]
  570.. 578  vars   nine variables
  579.. 621  code   puts
  622.. 783  code   interpret
  786.. 978  code   draw
  979..1181  code   parse_line
 1182..1480  data   299 run lengths        <- consumed at boot, then RECYCLED
 1481..3405  heap   decompressed 55x35 bitmap (past the loaded image)
 3406..      stack  relative base starts here
```

Two things to notice before anything else.

**The heap begins at 1481, which is `len(program)`.** The decompressed bitmap
is written immediately above the loaded image, into cells that start life as
zeroes because the VM's memory is unbounded and default-zero.

**The stack begins at 3406, and 1481 + 55×35 = 3406 exactly.** The very first
instruction after the mode select is `arb #3406`, placing the frame pointer one
cell past the last bitmap byte. Nothing overlaps, and nothing is wasted
(`test_the_stack_starts_just_past_the_bitmap`).

---

## The poke, and what it actually does

```text
    0: add  [330] [331] [332]        ; mem[330..332] = [0, 1, 1]
        ...
   58: jz   [332] #62
   61: hlt
```

`mem[0] = 2` turns that `add` into a `mul`. Both operands are already in the
file: **0 and 1**. So the first instruction computes `0 + 1 = 1` normally and
`0 * 1 = 0` when poked, and `jz [332] #62` sends control to the halt at 61 in
the first case and into the robot in the second.

That is the *entire* mechanism. One cell, one arithmetic operator, one bit of
meaning — and address 61 is the only instruction in the whole program that runs
in Part 1 and not in Part 2. The puzzle's "change the value at address 0 from 1
to 2" is doing nothing more mysterious than picking `+` or `×`
(`test_the_poke_flips_one_cell`).

Compare [Day 13](day13_disassembly.md), where poking address 0 to 2 set the
quarter count and the program branched on a *value*. Here the poke does not
supply data at all; it rewrites an opcode.

---

## Bootstrap: a run-length decoder made of patched operands

```text
    4: arb  #3406              ; arb is adjust relative base
    6: mul  #1182 #1 [15]      ; source pointer  := 1182
   10: add  #0 #1481 [24]      ; dest pointer    := 1481
   14: mul  [***] #1 [570]     ; tmp := runs[src]        <- operand at 15
   18: jz   [570] #36          ;   zero-length run? skip
   21: mul  [571] #1 [***]     ; bitmap[dst] := bit      <- operand at 24
   25: add  [570] #-1 [570]    ;   tmp -= 1
   29: add  [24] #1 [24]       ;   dst += 1
   33: jz   #0 #18             ;   loop
   36: eq   [571] #0 [571]     ; bit = !bit
   40: add  [15] #1 [15]       ; src += 1
   44: eq   [15] #1481 [570]   ; done?
   48: jz   [570] #14
```

`[15]` and `[24]` are not variables. **They are the operand cells of the
instructions at 14 and 21**, incremented in place. Intcode has no indexed
addressing mode, so a moving pointer *is* a self-modifying operand — the same
technique Day 15 used for its one array read, here running the whole loop.

This program does that **20 times**, and the tool finds every one by looking
for a store whose destination lands inside another decoded instruction. Every
single one patches an **operand**; not one patches an opcode or a jump target.
(The unpatched placeholder is always the literal `0`, which is why an
uninstrumented read of the file shows `mul #1 #2 [0]` and similar — the address
arrives at run time.) So control flow is entirely static, which is the property
that makes descent complete and the disassembly trustworthy.

Note the consequence for the disassembler: the values sitting at cells 15 and
24 in the loaded image are `0`, not `1182` and `1481`. The starting values are
the **immediates at cells 7 and 12** that initialise them. Reading the operand
cells directly gives a confidently wrong memory map, which is exactly the bug
this tool hit on its first run.

The data itself:

```text
1182: 40 13 42 1 11 1 10 7 25 1 11 1 10 1 5 1 25 1 11 1 ...
```

**299 runs, alternating 0/1 starting from `mem[571] = 0`, summing to exactly
1925 = 55 × 35.** The scaffold is not drawn by the program; it is *stored* in
it, compressed. 299 cells for a 1925-cell bitmap is a 6.4× win, and on a
machine where every cell is a full integer that is the difference between a
plausible puzzle input and an absurd one.

---

## The map comes off the disk

Everything needed to rebuild the camera picture is a literal:

| what          | where                               | value                          |
| ------------- | ----------------------------------- | ------------------------------ |
| width         | immediate of`eq rb[-6] #W` at 933 | 55                             |
| height        | immediate of`eq rb[-5] #H` at 946 | 35                             |
| bitmap        | 299 runs at 1182                    | 1925 bits                      |
| robot x, y    | `[576]`, `[577]`                | 26, 16                         |
| robot heading | `[578]`                           | 0                              |
| glyphs        | 558–561                            | `^>v<`                       |
| dx, dy        | 562–565, 566–569                  | `[0,1,0,-1]`, `[-1,0,1,0]` |

`recover_view` decodes the runs, paints `#` and `.`, and drops the robot glyph
at `(576, 577)`. The result is **byte-for-byte identical to `camera_view`**,
and `alignment_sum` over it gives **3888** with the machine never started
(`test_view_recovered_without_running_the_vm`).

The renderer's own glyph arithmetic is worth a line, because it explains the
one odd constant in the tool:

```text
  845: mul  rb[-2] #42 rb[-4]     ; robot_here * 42
  849: add  #46 rb[-4] rb[-4]     ; + 46
```

46 is `.` and 46 + 42 = 88 is `X`. **The off-scaffold glyph is computed, not
looked up** — one multiply-add covers both "empty space" and "the robot is
tumbling through it", because those are the only two things an off-scaffold
cell can be. On-scaffold takes the other branch and either loads `#` (35) or
indexes the glyph table by heading.

---

## The parser, and the internal bytecode

`parse_line` (979) reads an ASCII line and writes a compact encoding into the
buffers at 1182. **Those are the run-length table's own cells** — consumed once
at boot and then recycled, because nothing needs them again
(`test_the_parsed_program_reuses_the_rle_cells`).

The layout is an 11-cell stride: one length cell plus ten slots, ten being the
most tokens a 20-character line can hold (`L,1,L,1,L,1,L,1,L,1` is 19
characters).

```text
1182  main routine   len + up to 10 calls
1193  function A     len + up to 10 tokens
1204  function B
1215  function C
```

The encoding:

| token               |     stored as |
| ------------------- | ------------: |
| `A`, `B`, `C` | −1, −2, −3 |
| `R`               |           −4 |
| `L`               |           −5 |
| a distance          |        itself |

Our grammar goes in as exactly that:

```text
main A,B,A,C,B,C,B,C,A,C  ->  [-1,-2,-1,-3,-2,-3,-2,-3,-1,-3]
A    L,10,R,12,R,12       ->  [-5,10,-4,12,-4,12]
B    R,6,R,10,L,10        ->  [-4,6,-4,10,-5,10]
C    R,10,L,10,L,12,R,6   ->  [-4,10,-5,10,-5,12,-4,6]
```

**The negative numbering is not cosmetic.** Dispatch to a function is

```text
  759: mul  rb[-1] #-11 rb[+1]     ; -opcode * 11
  763: add  #1182 rb[+1] rb[+1]    ; + base
```

so `-1 → 1193`, `-2 → 1204`, `-3 → 1215`. **The opcode *is* the index
arithmetic** — choose the numbering well and the dispatch table disappears.
That is the same instinct behind a jump-table opcode layout in a bytecode VM,
and it is why the call opcodes are −1/−2/−3 rather than, say, 1/2/3 (which
would collide with distances) or 65/66/67 (which would need a subtraction).

The parser also *validates*, and its error strings are sitting in the table at
330–557 in plain text:

```text
Expected function name but got:
Expected R, L, or distance but got:
Expected comma or newline but got:
Definitions may be at most 20 characters!
```

**The 20-character limit is enforced by the program itself**, not by the
puzzle's honour system.

---

## The interpreter is two levels deep, and the parser is why

```text
  622: arb  #5                      ; frame
  624: mul  #1 rb[-4] [629]         ; patch: fetch the length
  628: add  [***] #0 rb[-2]         ;   rb[-2] = length
  632: add  #1 rb[-4] rb[-4]        ; rb[-4] = first slot
  636: mul  #1 #0 rb[-3]            ; rb[-3] = pc = 0
  640: eq   rb[-3] rb[-2] [570]     ; pc == length?
  644: jnz  [570] #781              ;   -> return
  647: add  rb[-4] rb[-3] [653]     ; patch: fetch buffer[pc]
  651: mul  #1 [***] rb[-1]         ;   rb[-1] = opcode
  655: eq   rb[-1] #-4 [570]        ; -4 -> turn right
  662: eq   rb[-1] #-5 [570]        ; -5 -> turn left
  669: lt   rb[-1] #0  [570]        ; still negative -> call
  676: jz   rb[-1] #774             ; zero -> next instruction
        ...                          ; otherwise: move forward
  759: mul  rb[-1] #-11 rb[+1]      ; CALL: compute the callee's buffer
  767: add  #774 #0 rb[+0]
  771: jz   #0 #622                 ;   ... and recurse
  774: add  rb[-3] #1 rb[-3]        ; pc += 1
  778: jz   #0 #640                 ; loop
  781: arb  #-5
  783: jz   #0 rb[+0]               ; return
```

A **fetch–decode–dispatch loop with a program counter, a frame and recursion**.
If you have been through *Crafting Interpreters*' VM chapters this is entirely
familiar furniture: `rb[-3]` is the `ip`, `rb[-2]` the chunk length, `rb[-1]`
the decoded instruction, and 640–778 is `run()`.

The interesting part is what bounds the recursion. **Nothing in the interpreter
does.** The dispatch at 669 is uniform — any negative opcode that is not −4 or
−5 is treated as a call, at any depth. So the puzzle's rule that "movement
functions may not call other movement functions" is not an interpreter
limitation.

It is a **parser** rule, and the program says so out loud. Feeding it a
function body containing `A`:

```text
Main:
Function A:

Expected R, L, or distance but got: A
```

The main routine is parsed by one grammar (function names only) and the bodies
by another (turns and distances only). The two-level structure of the puzzle's
answer is a fact about the firmware's *front end*, and the interpreter would
happily run a deeper grammar if the parser would accept one.

---

## Part 2 comes off the disk too

`draw` is called after every step and every turn — 368 times on the real route.
Each call, if the robot is standing on a cell whose bitmap value is still 1:

```text
  884: add  [374] #1 [374]        ; vacuumed += 1
  888: mul  #1 rb[-3] [895]       ; patch...
  892: mul  #1 #2 [***]           ;   bitmap[cell] := 2   <- never counted again
  896: add  #0 rb[-3] [902]       ; patch...
  900: add  [438] #*** [438]      ;   dust += the cell's ADDRESS
  904: mul  rb[-6] rb[-5] [570]   ; x * y
  908: add  [570] [374] [570]     ;   + vacuumed
  912: add  [570] [438] [438]     ;   dust += that
```

Writing **2** into the bitmap is the "squeaky clean" bookkeeping: the guard is
`== 1`, so each cell contributes exactly once no matter how often it is driven
over. That is why the counter ends at **319**, the number of scaffold cells,
and not 333, the number of steps.

So the dust is

    dust = Σ over cells, in visit order:  (1481 + y·55 + x) + x·y + n

where `n` is how many cells have been vacuumed so far. The first addend being
the cell's *memory address* is the part no amount of staring at the puzzle text
would suggest, and it is why the total is ~10⁶ rather than ~10⁵.

Replaying that over the statically recovered map, using our own route, gives
**927809** — the accepted answer, with the machine never started
(`test_both_answers_come_off_the_disk`).

**Both of Day 17's answers are therefore readable from the file**, as on
[Day 15](day15_disassembly.md) — but by a different route. Day 15's answers
were *literals* (the oxygen's coordinates were a pair of compare immediates).
Here Part 1 is *data* that has to be decompressed, and Part 2 is a *formula*
that has to be reproduced exactly, addend for addend. The disassembly has to
understand the program rather than merely read it.

---

## Running it

```
.venv\Scripts\python.exe python\day17_disasm.py [path-to-program]
```

Five passes: descent with subroutine discovery, memory map, static map
recovery, static dust recovery, cross-check against the live machine.

For a single continuous listing to read beside this guide -- every cell of
the image in address order, minimally annotated -- generate the companion
file (gitignored, as all full listings are, because the raw cells republish
the puzzle input):

```
.venv\Scripts\python.exe python\day17_disasm.py --full > Problem_Statements\days\day17_listing.md
```

Nothing is hardcoded to one user's file. The width and height are read from the
renderer's two compare immediates, the table bases from the bootstrap's
initialising immediates, the robot's start from the three cells the renderer
compares against, and the glyphs and deltas from their tables. A different
input yields a different map rather than a confidently wrong one — the lesson
[Day 15's disassembly](day15_disassembly.md) learned the hard way when its wall
threshold turned out to be generated per user (37 in one file, 35 in another).

---

## What this program is, as a program

It is a small embedded system, and it is built like one:

- a **boot loader** that decompresses a resource into RAM and then reuses the
  compressed copy's memory as working storage;
- a **frame-based calling convention** synthesised on an ISA with no call
  instruction;
- **strength reduction everywhere** — glyphs by multiply-add rather than table
  lookup, dispatch by opcode-as-index rather than a jump table;
- a **hand-written recursive-descent parser** with real diagnostics;
- and a **bytecode interpreter** for a small domain-specific language.

Day 15's controller was a state machine with a lookup table. This is a
*program*. The Intcode instruction set stopped growing at
[Day 9](day09_function_guide.md), and what the puzzle author did with the
remaining days was not extend the machine but demonstrate how much fits inside
it — which is, in the end, the same argument *Crafting Interpreters* makes
about a 30-opcode VM.
