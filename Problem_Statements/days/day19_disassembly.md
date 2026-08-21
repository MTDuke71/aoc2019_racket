# Day 19 — disassembling the drone oracle

> Companion to the [Day 19 function guide](day19_function_guide.md). Tool:
> [python/day19_disasm.py](../../python/day19_disasm.py). Tests: the
> disassembly section of
> [python/tests/test_day19.py](../../python/tests/test_day19.py).
>
> 424 cells — the smallest program since [Day 15](day15_disassembly.md)'s
> 252, and the first one that is **pure computation**: no world data, no
> string table, no bitmap. The drone reads (x, y) and answers one bit,
> and everything between the `in` and the `out` is obfuscation wrapped
> around a single quadratic form:
>
>     lit(x, y)  ⇔  |76·x² − 100·y²| ≤ 17·x·y
>
> Three honest constants — 76, 100, 17 — and *everything else in the
> program is mined from its own code*: the literal 1 is the input
> instruction's operand, one call target is another instruction's
> operand, and another is recomputed by an algebraic identity that
> destroys the code behind it as it runs. Both answers come out of
> `math.isqrt` in about a millisecond with the VM never started.

## What is new since Day 17

|                     | [Day 15](day15_disassembly.md) | [Day 17](day17_disassembly.md) | Day 19 |
| ------------------- | ------------------ | ----------------------- | ---------------------------- |
| size                | 70 instr, 0–251    | 272 instr, 933/1481 cells | **119 instr + 4 vars, all 424 cells** |
| world data          | 39×20 edge table   | 55×35 RLE bitmap        | **none — pure function**     |
| subroutines         | none               | 4, frames + indirect return | 4, same convention, **one recursive, one an indirect-call trampoline** |
| self-modification   | 1 operand patch    | 20 operand patches      | **2 patches: a jump target, and one *destructive* operand negation** |
| obfuscation         | strength reduction | none to speak of        | **the whole program**        |
| answers off the disk | both, as literals | P1 as data, P2 as a formula | **both, as one inequality** |

The instruction set froze at [Day 9](day09_function_guide.md); the
calling convention is [Day 17](day17_disassembly.md)'s exactly — caller
writes the return address into the callee's `rb[+0]` slot and jumps,
callee opens a frame with `arb #n`, returns with `arb #-n` then the
indirect `jnz #1 rb[+0]`. What is new is *why* the program is hard to
read: Day 17 was a compiler's honest output; Day 19 is the same
compiler being deliberately evasive. It reads like an entry-level
crackme — and like [Day 5](day05_disassembly.md)'s self-modifying test
selector, it is the statement's own hint that the interesting layer is
under the surface.

## The map

```text
    0–220   main         read x, read y, evaluate the predicate, output
  221–224   variables    X, Y, quad, tmp  (four zero-initialised cells)
  225–258   apply(f,a,b,c)   indirect call: f(a, b, c)   [self-patching]
  259–281   abs(v)           |v|, branch-free
  282–302   reject_neg(v)    v < 0  →  output 0, halt
  303–423   mul3(a,b,c)      a·b·c, obfuscated recursion  [calls itself]
```

Stack: `arb #424` at address 0 parks the relative base one past the end
of the file, so frames grow into untouched memory — same layout as Day
17 (whose stack began exactly one cell past its bitmap). Every cell of
the file is accounted for: 119 instructions plus the four variables,
asserted cell-for-cell by `full_listing` and pinned by
`test_full_listing_accounts_for_every_cell`. The complete annotated
listing with raw cells is generated locally, in the
[Day 17](day17_disassembly.md) tradition —

    python python/day19_disasm.py --full > Problem_Statements/days/day19_listing.md

— and stays gitignored, because a listing that shows every raw cell
republishes the puzzle input. Linear disassembly works end to end —
with one caveat: cells 221–224 are *data between functions*, and a
decoder that doesn't know that reads `0` at 221 and stops. That is the
entire descent difficulty of this program; there is no other trap.

## Reading the main routine

The full listing is `python day19_disasm.py`'s pass 1; annotated:

```text
    0  arb  #424               ; stack above the program
    2  in   rb[+1]             ; x
    4  mul  #11 #1 rb[+0]      ; ret = 11 ─┐ call reject_neg(x)
    8  jnz  #1 #282            ;           ─┘  (negative → out 0, hlt)
   11  mul  #18 #1 rb[+0]      ; call abs(x)   -- a no-op after the guard
   15  jnz  #1 #259
   18  add  rb[+1] #0 [221]    ; X = x
   22  in   rb[+1]             ; y
   24  add  #31 #0 rb[+0]      ; call reject_neg(y)
   28  jnz  #1 #282
   31  add  #38 #0 rb[+0]      ; call abs(y)
   35  jz   #0 #259
   38  mul  [23] #1 rb[+2]     ; arg b = [23] = 1  -- MINED: the operand
                               ;   of `in rb[+1]` at address 22/2
   42  add  #0 rb[+1] rb[+3]   ; arg c = y
   46  mul  #1 #1 rb[+1]       ; arg a = 1
   50  add  #0 #57 rb[+0]      ; call mul3(1, 1, y)
   54  jnz  #1 #303
   57  add  rb[+1] #0 [222]    ; Y = 1·1·y = y

   61  mul  #1 [221] rb[+3]    ; args (X, X, ·)
   65  add  [221] #0 rb[+2]
   69  add  #259 #0 rb[+1]     ; f = abs
   73  add  #0 #80 rb[+0]      ; call apply(abs, X, X, ·)  →  X
   77  jnz  #1 #225
   80  mul  #1 #76 rb[+2]      ; ***  A = 76  ***
   84  add  #91 #0 rb[+0]      ; call mul3(X, 76, X)
   88  jz   #0 #303
   91  add  rb[+1] #0 [223]    ; quad = 76·X²

   95  add  [222] #0 rb[+4]    ; args (225, 259, Y)
   99  mul  #1 #259 rb[+3]
  103  add  #0 #225 rb[+2]     ; the DECOY immediate: the trampoline's
  107  mul  #1 #225 rb[+1]     ;   own address, twice
  111  mul  #1 #118 rb[+0]     ; call apply(apply, apply, abs, Y)
  115  jz   #0 #225            ;   = apply(apply, abs, Y) = abs(Y) = Y
  118  add  #0 [222] rb[+3]    ; arg c = Y
  122  add  #100 #0 rb[+2]     ; ***  B = 100  ***
  126  mul  #1 #133 rb[+0]     ; call mul3(Y, 100, Y)
  130  jnz  #1 #303
  133  mul  rb[+1] #-1 rb[+1]  ; −100·Y²
  137  add  [223] rb[+1] rb[+1]; 76·X² − 100·Y²
  141  add  #148 #0 rb[+0]     ; call abs(that)
  145  jnz  #1 #259
  148  mul  #1 rb[+1] [223]    ; quad = |76·X² − 100·Y²|

  152  mul  #1 [221] rb[+4]    ; args (·, 17, Y, X)
  156  add  [222] #0 rb[+3]
  160  add  #0 #17 rb[+2]      ; ***  C = 17  ***
  164  add  [132] #-2 [224]    ; tmp = [132] − 2        [132] = 303, the
  168  mul  [224] #2 [224]     ; tmp = tmp · 2            operand of the
  172  add  [224] #3 [224]     ; tmp = tmp + 3            call at 130
  176  mul  [132] #-1 [132]    ; [132] = −[132]   ← DESTRUCTIVE
  180  add  [224] [132] [224]  ; tmp = tmp − 303
  184  add  [224] #1 rb[+1]    ; f = tmp + 1 = 303 = mul3
  188  add  #0 #195 rb[+0]     ; call apply(mul3, 17, Y, X)
  192  jz   #0 [109]           ;   ...through [109] = 225, the operand
                               ;   of the instruction at 107
  195  lt   rb[+1] [223] rb[+2]; t = (17·X·Y < quad)      i.e. NOT lit
  199  mul  [23] #1 rb[+1]     ; args (1, t, −1)   -- cell 23 again
  203  mul  #1 #-1 rb[+3]
  207  add  #214 #0 rb[+0]     ; call mul3(1, t, −1) = −t
  211  jnz  #1 #303
  214  add  #1 rb[+1] rb[+1]   ; 1 − t
  218  out  rb[+1]             ; 1 if lit, 0 if not
  220  hlt
```

Stylistic tells worth recognising on sight:

* **Every constant load is coin-flipped** between `mul #k #1` and
  `add #k #0`, and every unconditional jump between `jnz #1` and
  `jz #0`. Two spellings for every idiom is compiler-generated
  variation for its own sake — Day 17's code never did this.
* **`[23]`, `[109]`, `[132]` are code addresses used as data.** The
  program contains the literal `1` twice as an honest immediate (46,
  214) — and still fetches it from its own `in` instruction's operand
  at 38 and 199, purely to muddy the water.
* The sequence 164–184 computes `((v−2)·2 + 3) − v + 1` where
  `v = [132] = 303`. That is the identity function: `2v−4+3−v+1 = v`,
  for *any* v — an algebraic no-op whose only purpose is to make the
  call target look computed. On the way it executes
  `[132] = −[132]`, wrecking the call instruction at 130 — which
  already ran and never runs again. **Run-once code destroying its own
  past** is safe, and exactly the kind of thing that breaks a naive
  "diff the memory image to find self-modification" pass.

## The four subroutines

### `apply` (225) — an indirect call built from one operand patch

```text
  225  arb  #5
  227  add  rb[-4] #0 [249]    ; patch: jump target ← f
  231  add  #0 rb[-3] rb[+1]   ; shift args down one slot
  235  add  rb[-2] #0 rb[+2]
  239  mul  #1 rb[-1] rb[+3]
  243  add  #0 #250 rb[+0]     ; ret = 250
  247  jz   #0 #225            ; ← cell 249 now holds f, not 225
  250  add  #0 rb[+1] rb[-4]   ; return f's return value
  254  arb  #-5
  256  jnz  #1 rb[+0]
```

Intcode has no indirect jump through a register, so `apply` *writes the
callee's address into its own jump instruction* — the same
operand-patching move as [Day 17](day17_disassembly.md)'s array
indexing (there: no indexed addressing, so a moving pointer is a
patched operand; here: no indirect call, so a function pointer is a
patched jump). The disassembled file shows `jz #0 #225` only because
cell 249's *resting* value is 225 — a decoder that trusts the static
target sees `apply` calling itself, which it also genuinely does when
main passes `f = apply`: the call at 111 is
`apply(apply, apply, abs, Y)`, which unwinds two layers of trampoline
to reach `abs(Y)`. Three calls, one operand patch each, to compute the
identity of a non-negative number. This is the program's decoy — and
it is why constant recovery has to classify immediates by the *call
that consumes them* (see below).

### `abs` (259) — branch-free absolute value

```text
  261  lt   #0 rb[-2] rb[-1]   ; s = (v > 0)         ∈ {0, 1}
  265  mul  rb[-1] #2 rb[-1]   ; s = 2s
  269  add  rb[-1] #-1 rb[-1]  ; s = 2s − 1          ∈ {−1, +1}
  273  mul  rb[-1] rb[-2] rb[-2] ; v = s·v
```

`(0 < v)·2 − 1` maps the comparison bit to a sign — the same
"arithmetic on 0/1 comparison results" style as Day 15's `a·b`-as-AND.
Note both inputs already passed `reject_neg`, so both `abs` calls in
main are no-ops; the routine exists to be called through the
trampoline, as chaff.

### `reject_neg` (282) — the statement's "negative numbers confuse the drone"

The one honest routine: `v < 0` → `out #0`, `hlt`. The polite
implementation detail is that the *program* enforces the statement's
input contract, answering 0 rather than misbehaving —
`day19.beam_probe` refuses negatives before the VM ever sees them, so
this path is dead in our use.

### `mul3` (303) — multiplication hidden inside a sorting recursion

Pseudo-code of the listing:

```text
mul3(a, b, c):
    if a > b:  return mul3(b, a, c)      # additive swap, no temp:
    if b > c:  return mul3(a, c, b)      #   a += b; old = a − b; b = a − old
    # now a ≤ b ≤ c:
    c ← b·c
    a ← c·(b − a)          # = b·c·(b − a)
    b ← b·c                # = b²·c        (c already scaled)
    return b − a           # = b²c − bc(b−a) = b·c·a  ✓
```

Two things make this a nice little puzzle. The recursion *sorts* its
arguments — with swaps done additively (`a+b` then two subtractions),
since a swap needs a temporary and the program would rather not — and
then evaluates a telescoping expansion whose product only appears
after cancellation: `b²c − bc(b−a) = abc`. The sort is pointless
(the product is symmetric), which is the tell that it exists to defeat
pattern-matching the routine as "multiply". Termination: each adjacent
swap removes exactly one inversion, and three arguments hold at most
three, so the recursion is at most three self-calls deep.

The self-calls at 340/381 use the same `rb[+0]`-and-jump convention as
main's calls, so `mul3` is genuinely recursive. With probes reaching
(1144, 1004), the returned products top out near 10⁸ ≈ 2²⁷ and the
telescoping intermediates (`b²c`) near 10⁹ ≈ 2³⁰ — either way nowhere
near needing Intcode's bignums, unlike
[Day 9](day09_function_guide.md)'s self-test.

## Constant recovery, structurally

The formula's skeleton is fixed but the three constants are per-input,
so [python/day19_disasm.py](../../python/day19_disasm.py) refuses to
hardcode offsets. The observation that makes recovery clean: **main
stores an immediate into `rb[+2]` — mul3's middle argument slot —
exactly four times**, and each store is classified by the jump that
consumes it:

| store | consumed by | classification |
| --- | --- | --- |
| `#76` at 80 | direct `j.. #303` | **A**, the x² coefficient |
| `#225` at 103 | direct `j.. #225` | the decoy (the trampoline's own address) |
| `#100` at 122 | direct `j.. #303` | **B**, the y² coefficient |
| `#17` at 160 | indirect `jz #0 [109]` → 225 | **C**, the xy coefficient |

Anything else — a fifth store, a jump that fits no row — raises
instead of guessing, in the [Day 16](day16_function_guide.md) tradition
of verifying input properties rather than assuming them. The recovered
`(A, B, C)` then has to survive pass 3: the closed form must agree
with the live VM on the full 50×50 window *and* on 44 probes
straddling both edges at y = 500 and y = 1000, where a boundary
off-by-one would actually show. (Pinned as
`test_recovered_formula_matches_the_vm_window`.)

The section [below](#a-second-users-file) validates all of this against
a second user's actual input file.

## The geometry of `|76x² − 100y²| ≤ 17xy`

Factor the two halves of the absolute value:

    76x² − 17xy − 100y² ≤ 0        (the right edge)
    76x² + 17xy − 100y² ≥ 0        (the left edge)

Both are homogeneous quadratics, so each vanishes on a pair of rays
through the origin; the beam is the wedge between the positive-quadrant
roots:

    1.040676…  =  (√30689 − 17) / 152   ≤   x/y   ≤   (√30689 + 17) / 152  =  1.264360…

with `disc = C² + 4AB = 17² + 4·76·100 = 30689`. Two facts fall out:

* **30689 is not a perfect square** (175² = 30625, 176² = 30976), so
  both edge slopes are irrational and the rays pass through *no*
  lattice point except the origin — the program's `≤` comparisons can
  never actually tie away from (0, 0). Every lit/unlit call is made
  with slack. Pinned as `test_the_rays_never_touch_the_lattice`.
* The beam's width at row y is (slope difference)·y ≈ 0.2237·y, which
  is why rows 1–3 are empty (width < 1 and no lattice point lands in
  the wedge). For the square, solve the fit condition on the rays
  themselves — `α·y + 99 ≤ β·(y − 99)` with α, β the two slopes —
  giving `y ≥ 99·(1 + β)/(β − α) ≈ 1002.2`; the lattice pushes the
  actual first fit to bottom row 1004. The function guide's
  [two-corner argument](day19_function_guide.md#part-2-ride-the-left-edge-check-two-corners)
  is this wedge's convexity, used with the VM as oracle.

Both answers then reduce to integer arithmetic
(`left_edge_static` / `right_edge_static`: an `isqrt`, a division, and
a one-step fix-up loop that absorbs the floor's slack exactly —
`test_static_edges_agree_with_the_formula` checks the flip happens at
precisely the named cell):

    part 1  =  Σ  width of [L(y), R(y)] ∩ [0, 49]   over y < 50      =  209        (0.054 ms)
    part 2  :  first y with L(y) + 99 ≤ R(y − 99)  →  y = 1004,
               L(1004) = 1045  →  10000·1045 + 905                    =  10450905   (0.994 ms)

— the VM never started, verified against the live machine by pass 5
and `test_static_answers_match_the_live_machine`. The fit is tuned
tight on both sides: R(905) = 1144 is exactly the square's top-right
corner, and one row earlier misses by a single cell
(L(1003) + 99 = 1143 > R(904) = 1142).

## A second user's file

`inputs/day19_alt.txt` is another user's program — gitignored like
every input, in the [Day 15](day15_disassembly.md) `day15_alt.txt`
tradition. Same 424 cells, same skeleton, same 119 instructions; a
different formula and a differently-leaning beam:

| | `day19.txt` | `day19_alt.txt` |
| --- | --- | --- |
| predicate | \|76x² − 100y²\| ≤ 17xy | \|167x² − 93y²\| ≤ 21xy |
| disc = C² + 4AB | 30689 (isqrt 175) | 62565 (isqrt 250) — also no square |
| beam slopes x/y | 1.0407 … 1.2644 | 0.6860 … 0.8118 |
| 100×100 square at | (1045, 905) | (979, 1328) |
| part 1 / part 2 | 209 / 10450905 | 154 / 9791328 |

The alt beam leans the *other* side of the diagonal (x < y), so its
square lands mirrored — a healthy reminder that nothing in the solver
may assume which way the cone tips.

**113 of the 424 cells differ, spread across 49 instructions — and
only three values mean anything.** The rest is the same coin-flip
spelling machinery [Day 15](day15_disassembly.md) documented (`x·1` vs
`x+0` copies, `jnz #1` vs `jz #0` jumps), with one twist that makes
Day 19's version strictly harder: flipping `add #0 #167` to
`mul #1 #76` moves the payload to a *different cell* (B rides at 123
in one file and 124 in the other; C at 162 vs 161), and the decoy's
operand shuffle likewise moves the indirect jump's source from `[109]`
to `[108]`. So there is no fixed set of meaningful *cells* at all —
the meaningful unit is the instruction, which is exactly why
`recover_constants` evaluates whole instructions and classifies them
by their consuming call. `test_only_the_three_constant_sites_carry_meaning`
proves it by splicing: move just the three 4-cell constant loads from
the alt file into this one and the machine *is* the alt drone,
verified against the alt formula — with 104 cells still textually
different.

All five passes run unchanged on either file
(`python python/day19_disasm.py inputs/day19_alt.txt`), the constant
and static-answer tests parametrize over both, and the alt file gets
its own honest listing — `notes_for` builds the annotations from each
program's *recovered* constants rather than this file's:

    python python/day19_disasm.py inputs/day19_alt.txt --full > Problem_Statements/days/day19_alt_listing.md

(gitignored, like every full listing).

## How the tool fared

The vendored Rust toolkit (`intcode-disasm-master/`, gitignored) was
run per the Day 17 protocol: `hlr` first for reconnaissance, Python
passes for verification. Two findings:

* **Both of its Day-17-era assumptions about call sites broke.** Its
  argument extractor required every call to be preceded by consecutive
  stores to `rb[+1]..rb[+N]` — but Day 19's main routinely *leaves the
  previous call's return value sitting in `rb[+1]`* and stores only the
  higher slots (e.g. `mul3([R+1], #76, [R+3])` at 80). Two local
  patches (commented `Local patch (aoc2019 day19)` in
  `src/disasm/v3/lir/converter.rs`) degrade the panics: a
  non-consecutive store now ends the argument scan, and missing lower
  slots are synthesized as stack references. With those, `hlr` runs
  clean; the annotated output is saved as
  `intcode-disasm-master/day19_hlr.txt` with names fed back through
  `data/19.symbols`.
* **Its output still drops arguments silently** — the decompiled calls
  read `mul3(1)` and `apply(225)` where three or four arguments flow —
  the same class of omission that dropped a dust-formula addend on Day
  17. The standing rule held: every formula above was re-derived from
  the raw listing and verified by the Python passes; the `hlr` output
  served as a map, not as evidence.

`data/25.symbols` (the text adventure) remains pre-annotated for when
Day 25 arrives.

## Tests pinned by this analysis

| claim | test |
| --- | --- |
| recovered (A, B, C) reproduce the VM bit-for-bit on the window | `test_recovered_formula_matches_the_vm_window` |
| disc is not a perfect square → rays never touch the lattice | `test_the_rays_never_touch_the_lattice` |
| the isqrt edges flip exactly where the formula flips | `test_static_edges_agree_with_the_formula` |
| static part 1 and part 2 equal the live machine's | `test_static_answers_match_the_live_machine` |

plus the tool's own five passes, which assert everything they print.
