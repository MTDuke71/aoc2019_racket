# Intcode — one-page quick reference

> The AoC 2019 VM, complete. The instruction set froze at
> [Day 9](day09_function_guide.md) and every later Intcode day is a *driver*
> problem, so this page is the whole language: 10 opcodes, 3 addressing modes,
> **99 legal instruction words**, and one memory model.
>
> Implementation: [src/intcode.rkt](../../src/intcode.rkt) (the frozen VM,
> imported from Day 13 on). Days 2/5/7/9/11 each keep their own copy, because
> the *diff* between consecutive copies is what those guides teach.

---

## The machine

| | |
|---|---|
| `mem` | one array of arbitrary-precision integers, **grow-on-write**: reads past the end are `0`, writes past the end extend it |
| `ip` | instruction pointer, starts at `0`, moves by the instruction's width unless a jump sets it |
| `rb` | relative base, starts at `0`, moved only by opcode `9` |
| input / output | two streams; how they're supplied is the caller's business (see *protocol* below) |

Programs are given as comma-separated integers and loaded at address `0`.
There is no separate code segment — **code and data share one address space**,
which is what makes self-modifying operands possible (and, from Day 5 on,
routine).

---

## Instruction word

The first cell of an instruction packs the opcode *and* the addressing mode of
each parameter:

```
    word  =  m3 m2 m1 OP        OP = word mod 100
              │  │  │  └── two-digit opcode
              │  │  └───── mode of parameter 1   (hundreds digit)
              │  └──────── mode of parameter 2   (thousands)
              └─────────── mode of parameter 3   (ten-thousands)
```

Leading zeros are omitted, so bare `1` is `add` with all three parameters in
position mode. Worked example — Day 13's program, address 0611:

```
    21102  1  547  2
    │
    └─ 2 1 1 02  ->  opcode 02 = mul,  p1 immediate,  p2 immediate,  p3 relative
                     rel[rb+2] = 1 * 547            ("load the constant 547")
```

---

## Opcodes

| op | mnemonic | width | effect | since |
|---:|---|---:|---|---|
| 1 | `add` | 4 | `p3 = p1 + p2` | Day 2 |
| 2 | `mul` | 4 | `p3 = p1 * p2` | Day 2 |
| 3 | `in` | 2 | `p1 = INPUT` (blocks if no input is available) | Day 5 |
| 4 | `out` | 2 | `OUTPUT p1` | Day 5 |
| 5 | `jump-if-true` | 3 | `if p1 != 0: ip = p2` (else fall through) | Day 5 |
| 6 | `jump-if-false` | 3 | `if p1 == 0: ip = p2` | Day 5 |
| 7 | `less-than` | 4 | `p3 = (p1 < p2) ? 1 : 0` | Day 5 |
| 8 | `equals` | 4 | `p3 = (p1 == p2) ? 1 : 0` | Day 5 |
| 9 | `adjust-rel-base` | 2 | `rb += p1` | Day 9 |
| 99 | `halt` | 1 | stop | Day 2 |

A jump that fires does **not** add its width to `ip`; everything else does.

## Parameter modes

| mode | name | a *read* parameter means | a *write* parameter means |
|---:|---|---|---|
| 0 | position | `mem[k]` | address `k` |
| 1 | immediate | the literal `k` | **illegal** — you cannot store into a literal |
| 2 | relative | `mem[rb + k]` | address `rb + k` |

Destination parameters are `p1` of `in`, and `p3` of `add`/`mul`/`less-than`/
`equals`. Mode 1 is legal for every other parameter, including jump targets —
and whether a jump target is immediate is exactly what decides if a static
disassembler can follow it.

---

## Every legal instruction word

99 of them. `P` position, `I` immediate, `R` relative.

```
3-param (p3 is a destination: never immediate)
  p1 p2 p3 |   add    mul     lt     eq          2-param (both read)
   P  P  P |     1      2      7      8            p1 p2 |    jt     jf
   I  P  P |   101    102    107    108             P  P |     5      6
   R  P  P |   201    202    207    208             I  P |   105    106
   P  I  P |  1001   1002   1007   1008             R  P |   205    206
   I  I  P |  1101   1102   1107   1108             P  I |  1005   1006
   R  I  P |  1201   1202   1207   1208             I  I |  1105   1106
   P  R  P |  2001   2002   2007   2008             R  I |  1205   1206
   I  R  P |  2101   2102   2107   2108             P  R |  2005   2006
   R  R  P |  2201   2202   2207   2208             I  R |  2105   2106
   P  P  R | 20001  20002  20007  20008             R  R |  2205   2206
   I  P  R | 20101  20102  20107  20108
   R  P  R | 20201  20202  20207  20208          1-param
   P  I  R | 21001  21002  21007  21008            p1 |    in    out    arb
   I  I  R | 21101  21102  21107  21108             P |     3      4      9
   R  I  R | 21201  21202  21207  21208             I |    --    104    109
   P  R  R | 22001  22002  22007  22008             R |   203    204    209
   I  R  R | 22101  22102  22107  22108
   R  R  R | 22201  22202  22207  22208          halt |    99
```

Anything else in an opcode position is a decode error — which is the cheapest
possible check that your disassembler hasn't lost instruction alignment.

---

## What the ISA does *not* have

No load-immediate, no move, no unconditional jump, no indexed addressing, no
subtraction, no division, no comparison other than `<` and `==`, no call/return.
Real programs synthesise all of them, and recognising the idioms is most of
what reading Intcode consists of:

| you want | emitted as | note |
|---|---|---|
| `dst = k` | `add #0,#k` · `add #k,#0` · `mul #k,#1` · `mul #1,#k` | the generator picks between these **at random** — see [what varies between inputs](day13_disassembly.md#what-changes-between-users-inputs) |
| `dst = src` | `add src,#0` · `mul #1,src` | same identity-element trick |
| `jmp t` | `jt #1,t` · `jf #0,t` | a constant condition |
| `dst = -src` | `mul src,#-1` | |
| `a - b` | `mul b,#-1` then `add a,tmp` | |
| `a > b` | `lt b,a` | swap the operands |
| `mem[mem[k]]` | write the address into a later instruction's operand cell, then execute it | the only indexed addressing there is; see [`draw` / `tile_at`](day13_disassembly.md#indexed-addressing-by-operand-patching) |
| `a mod m` | repeated subtraction, usually with a shift ladder (`64m`, `8m`, `m`) | [Day 13's `mod`](day13_disassembly.md#mod-at-456--octal-restoring-division) |
| `call` / `ret` | caller writes the return address into `rel[0]` and arguments into `rel[1..k]`; callee does `rb += frame`, so arguments become `rel[-frame..]`; returns with `jmp rel[0]` | the calling convention Days 9/11/13 all use |

---

## The I/O protocol

Opcode 3 is where the VM has to talk to the world, and the *shape* of that
conversation is what changes from day to day even though the opcode doesn't:

- **Day 5** — a single input known before the run. A list is enough.
- **Day 7** — amplifiers chained, then wired into a feedback loop, so a machine
  must *pause* mid-run and resume. The VM stops being a function and becomes a
  coroutine: `step` returns `ran` / `blocked` / `output v` / `halted`, and the
  caller decides what happens next.
- **Day 9** — still a fixed input, but the program now roams memory past its own
  image via `rb`.
- **Day 11 on** — the Nth input is a *question about the world the first N−1
  outputs built* (a camera reading, a joystick). No input list can exist ahead
  of the run; the driver must supply values just-in-time. In this repo that
  means passing input as a **thunk** evaluated at block time, not as a value.

`vm-step!` in [src/intcode.rkt](../../src/intcode.rkt) is that protocol: one
instruction per call, reporting what happened. Everything above Day 7 is built
on it.

---

## Reading an unfamiliar program

1. **Decode from address 0 following control flow**, not linearly — code and
   data are interleaved and only reachable cells are instructions
   (recursive descent).
2. **Immediate jump targets are static edges**; position/relative targets are
   not, and are where a static disassembler must stop.
3. **Watch for writes into the code region.** If an instruction's operand cell
   is a write destination anywhere, that instruction is incomplete on disk.
4. **`rb += <program length>`** is the giveaway that what follows is a heap or a
   call stack, not more code.
5. **When descent stalls, execute.** A dynamic trace is a complete disassembly
   of the path actually taken — and on the interactive days it is the *only*
   one available.

Worked examples of all five: [Day 2](day02_disassembly.md) ·
[Day 5](day05_disassembly.md) · [Day 7](day07_disassembly.md) ·
[Day 9](day09_disassembly.md) · [Day 11](day11_disassembly.md) ·
[Day 13](day13_disassembly.md), and the tooling in
[scripts/intcode_disasm.rkt](../../scripts/intcode_disasm.rkt).
