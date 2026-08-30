# Day 23 — disassembling the Network Interface Controller

> Companion to the [Day 23 function guide](day23_function_guide.md). Tool:
> [python/day23_disasm.py](../../python/day23_disasm.py). Tests: the
> disassembly section of
> [python/tests/test_day23.py](../../python/tests/test_day23.py). Full
> listing (generated locally, gitignored): `day23_listing.md` via
> `python python/day23_disasm.py --full`.
>
> 2,243 cells, and the headline is that they are not one program: the
> image opens with a **50-way computed goto**, so each of the fifty
> "identical" NICs runs its own entry stub and becomes a different node of
> a **dataflow graph that ships in the file** — operator nodes (sum,
> product, quotient, identity) wired by packets whose X field is the
> receiver's own slot-addressing arithmetic. Collapse the graph and the
> entire network is one map,
>
>     y' = ( (y − 11088)³ + 10⁸·(7y + 3·11088) ) // 10⁹
>
> iterated from the seed 20982 through the NAT's feedback loop. **Part 2's
> answer is a coefficient of the puzzle input**, the derivative at the
> fixed point is exactly 0.7 (the live wake deltas' measured ratio), part
> 1 = F(seed), and both answers come off the disk with the VM never
> started — the static iterates match the live NAT's deliveries element
> for element.

## What is new since Day 21

|                     | [Day 19](day19_disassembly.md) | [Day 21](day21_disassembly.md) | Day 23 |
| ------------------- | ----------------------- | ------------------------ | ------ |
| size                | 119 instr + 4 vars, all 424 cells | 431 instr + 300 data cells, all 2,050 | **481 instr + 435 data cells, all 2,243** |
| program identity    | one pure function       | one interpreter + data   | **fifty programs in one image, dispatched by network address** |
| world data          | none                    | the hull, 9-bit-packed   | **a dataflow graph: 96 operand slots + 65 routed edges** |
| self-modification   | 2 patches, one destructive | 17 patches + a callback pointer | **22 patches — and one is a jump TARGET, the year's first self-modified control flow** |
| calling convention  | Day 17's + a trampoline | Day 17's, 13 subroutines | **Day 17's + a function POINTER in a variable ([69])** |
| answers off the disk | both, as one inequality | both, as one checksum   | **both, as one cubic map and its fixed point** |

The instruction set froze at [Day 9](day09_function_guide.md). What is
genuinely new is that the *machine being disassembled is distributed*: no
single NIC computes anything interesting, and the object worth recovering
is not a subroutine but the graph the fifty of them form — the program
counter of the real computation is the network traffic itself.

## One image, fifty programs

The whole boot sequence is four instructions:

```
0000  in   [62]              ; the NIC's network address — the only input boot reads
0002  add  [62] #11 [10]     ; patch the dispatch: [10] = address + 11
0006  arb  #2243             ; rb = one past the image: frames live in the heap
0008  jnz  #1 [0]            ; jump through the patched operand
```

The store at 2 writes the jump's *target operand* (cell 10), and the table
at 11..60 holds fifty entry addresses — `goto table[address]`, a computed
goto built the only way Intcode allows, by patching the instruction about
to run. Days [15](day15_disassembly.md)–[21](day21_disassembly.md) all
self-modified, but always *data* operands (array indexing) — every
previous program's control flow was static once the idioms were known.
This is the year's first patched **jump target**, and it is why the
vendored decompiler's `hlr` pass dies here ("Expected immediate value for
GOTO address") and plain descent recovers 78 instructions of 2,243: the
program's very fourth instruction goes somewhere no static reading of one
cell can name. (Of the other 21 patches, two feed a jump's *condition* —
the barrier test below — which is still just data a jump happens to read;
`patch_kind` in the tool makes the distinction.)

The fifty stubs the table points at all share one shape — six immediate
stores and a jump into the shared runtime:

```
1485  mul  #18253 #1 [66]    ; salt   — incoming X decodes as slot = X // salt
1489  add  #3 #0 [67]        ; n.slots
1493  add  #1512 #0 [68]     ; slots  — the operand table, n × (flag, value)
1497  mul  #1 #302 [69]      ; op     — a FUNCTION POINTER: 253/302/351/556
1501  add  #0 #1 [71]        ; n.out
1505  mul  #1518 #1 [72]     ; outs   — the consumer table, n.out × (dest, X)
1509  jnz  #1 #73
```

(NIC 25's, as it happens.) The tool executes stubs symbolically rather
than pattern-matching them, so the add/mul spellings and operand swaps —
[Day 21](day21_disassembly.md)'s encoding coin-flips, present here too —
cost nothing, and any stub that isn't six stores plus that jump is
refused loudly. The six values are a node description: this NIC is a
**product node** with three operand slots and one consumer. Address is
identity; the "50 copies of the same NIC software" of the statement is
true only the way "every process runs the same kernel" is true.

## The shared runtime

Twelve variables at 61..72 are the whole per-node state — a process
control block. The receive loop at 73 is the half the statement describes:

```
0073  in   [64]              ; poll: X, or -1 for an empty queue
0088  in   [65]              ; a real packet: Y
0098  call divide(x, salt)   ; → slot number v
0113  drop if v < 1          ; (divide returns -1 for X < 0)
0120  drop if v−1 ≥ n.slots
0131  t  = slots[v].flag     ; patched operands from here on
0139  t2 = (slots[v].value == Y)
0147  drop if t · t2         ; a DUPLICATE changes nothing — and quiescence is the point
0158  slots[v].flag  := 1
0166  slots[v].value := Y
0170  started := 1
0178  barrier: if any slot's flag is 0, back to polling
0203  ret := 210; call [69]  ; all operands present: fire the operator
```

Three details carry the day:

- **X is slot addressing.** A packet's X field is decoded by the
  *receiver* as `X // salt`, and every sender's consumer table stores X
  values pre-multiplied — node 0's fan-out to NIC 25 carries X = 18253,
  36506, 54759, which are salt×1, ×2, ×3: the same value delivered to
  three different operand slots. The multiplies live in the data; the
  divide lives in the code; and the statement's mysterious X/Y pair
  resolves as **(address-within-the-node, actual value)**.
- **The duplicate check is change propagation.** A packet whose Y equals
  what its slot already holds is dropped before the barrier, so it fires
  nothing and sends nothing. That single `eq` is why the network can go
  idle at all — it is semi-naive evaluation, "only propagate deltas", the
  same discipline that makes Datalog engines and Bellman–Ford terminate.
  Part 2's whole NAT mechanism exists to detect the quiescence this
  comparison creates.
- **The operator is a function pointer.** `[69]` holds one of four code
  addresses and the call is `ret := 210; jz #0 [69]` —
  [Day 17](day17_disassembly.md)'s calling convention with the target read
  from a variable. The four callees (sum at 253, product at 302, quotient
  at 351, identity at 556) each walk the slot table through patched
  operands and return to the send loop at 210, which emits one
  `(dest, X, result)` triple per consumer-table pair and goes back to
  polling.

The boot behaviour the [function guide](day23_function_guide.md#the-boot-round-trap)
hit from the outside is visible in the code: a constant node's slot table
ships **pre-filled** (flag already 1), but the stub still enters the
receive loop at 73, whose first act is a *poll*. So every NIC reads one
`-1` before its barrier ever runs — round 1 of the live network is quiet
because all fifty processes are parked at instruction 73, one `-1` away
from the 65-packet boot cascade. The scheduler bug that declared round 1
idle mistook that gateway poll for quiescence.

## The divide at 436

The only real arithmetic subroutine: `divide(x, d)` — restoring binary
long division against the powers-of-two table at 385 (2⁰..2⁵⁰), with a
repeated-subtraction fast path for x < 10d. Two things worth keeping:

- **Negative x returns −1, not floor.** A negative x falls through the
  fast path's guard untouched and comes back −1 (`divide(-5, 2) = -1`,
  where floor is −3). That looks like a bug until you see the caller: the
  receive loop's first drop-check is `v − 1 < 0`, so −1 is exactly
  "invalid slot, discard packet" — the broken case is the *designed*
  rejection path for garbage X. Division is only ever performed on
  non-negative slot arithmetic and on the numerator of the one quotient
  node, which stays positive over the whole trajectory (the tool refuses
  to model anything else).
- **It can be called in vitro.** The calling convention is data, so the
  tests run the real subroutine on the real machine with nothing else
  alive: plant `hlt` at a fake return address, store it in `rb[+0]`, put
  the arguments in `rb[+1..2]`, set `ip = 436`, and read the result back
  out of `rb[+1]` (`call_subroutine` in the tool). Eight cases pin the
  floor behaviour and the −1 quirk against the live machine — the
  disassembly's claims about 120 cells of division condensed to a
  fixture-free test.

## The graph

Parsing all fifty stubs and their tables gives the census:

- **32 identity nodes** — 25 of them constants (pre-filled slot, one or
  more consumers): the numbers 2, 13, 5, 7, 1, 256, 8867, −176, −3333,
  −23027 … shipped as data and broadcast at boot. **Seven are decoys**
  (NICs 5, 9, 17, 31, 44, 45, 48): pre-filled constants with an *empty
  consumer table* — they compute at boot, the send loop iterates zero
  times, and they poll forever. Dead code, as network nodes.
- **15 product nodes, 2 sum nodes** (NICs 21 and 43), **1 quotient node**
  (NIC 10) — the only NIC whose consumer table names 255.
- **65 consumer entries** collapsing to 59 distinct (src, dest) pairs —
  exactly the 59 edges the live traffic exhibits, the difference being
  parallel edges like node 0's triple feed to NIC 25.
- Routing is airtight, and `validate` raises otherwise: every X is an
  exact multiple of its receiver's salt with the slot in range, every
  empty slot has exactly one feeder, every pre-filled slot has none.

Boot is then a topological evaluation of the constant part of the graph:
each node's barrier opens when its last operand lands, each node fires
exactly once, and the cascade is 65 packets — the live run's boot burst,
with **the 65th and last being NIC 10's quotient to address 255: part 1
is the final packet of the boot cascade.**

And one packet closes the loop. NIC 10's consumer entry is
`(255, 29569)` — and 29569 is *node 0's salt* × 1. The NAT relays the
packet to address 0 verbatim, where X = 29569 decodes to node 0's slot 1:
**the packet to 255 is pre-addressed for the node it will eventually be
bounced back to.** The puzzle input encodes the NAT into the graph as an
edge; the "idle network" mechanic of the statement is this program's
back-edge, implemented by the puzzle around the program.

## The whole network is one cubic

Node 0 is an identity node whose slot ships pre-filled with 20982 — the
**seed** — and whose six consumers fan the value y into the only cycle in
the graph, the **y-cone** {0 → 25, 19, 34 → 43 → 10 → 255 → (NAT) → 0}:

```
              ┌─→ 25: y·y·y      = y³        ┐
  y (node 0) ─┼─→ 19: −33264·y·y = −33264·y² ┼─→ 43: Σ + 1963199766528
              └─→ 34: 1068831232·y           ┘         │
                                        10: (Σ) // 10⁹ ─→ 255
```

The tool recovers this by propagating *polynomials in y* through the
graph instead of numbers (`recover_map`): constants are degree-0, node
0's seed slot is the indeterminate, sum/product nodes are polynomial
arithmetic, and the one quotient node must divide by a constant or the
tool refuses. Out falls

> **F(y) = (y³ − 33264·y² + 1068831232·y + 1963199766528) // 10⁹**

Every coefficient is a verifiable factor chain through the boot DAG (all
values below are the tool's, not hand arithmetic):

- **y³'s coefficient is 1** because NIC 25 multiplies three copies of y
  and nothing else.
- **−33264** is NIC 23's product (−176)·9·3·7 feeding NIC 19's y².
- **1068831232** reaches NIC 34 as 2·76345088·7 via NIC 38, where
  76345088 = 298223·256 (NIC 3) and 298223 is the *sum* node 21's
  74793 − 3333 + 16130 + 302741 − 92108 — sums of products of the little
  shipped constants.
- **1963199766528** is NIC 42's seven-slot product
  7·11·8867·3·2·36864·13 (36864 = 192·8·2·12 via NIC 39), landing in the
  sum as the constant term.
- **10⁹**, the divisor, is NIC 12's six-slot product 5·10·160·2·31250·2,
  with 31250 = 125·5·5·10 computed by NIC 37. A billion, factored across
  the graph so it appears nowhere in the file.

### The map is built from the answer

Read the coefficients again with a = 11088:

> **P(y) = (y − a)³ + 10⁸·(7y + 3a)**

— the tool checks this identity against the recovered coefficients
(`closed_form`), and it is exact: c₂ = −3a, c₁ = 3a² + 7·10⁸,
c₀ = −a³ + 3a·10⁸. Two consequences drop out:

- **F(a) = a with zero remainder**: P(a) = 10⁸·(7a + 3a) = 10⁹·a. The
  fixed point is not approximately 11088; the input was *generated from
  the answer*, the same way [Day 22](day22_function_guide.md)'s deck
  sizes were chosen for the algebra.
- **F′(a) = 7·10⁸ / 10⁹ = 0.7 exactly.** The live wake deltas' measured
  ratio ≈ 0.70 ([function guide](day23_function_guide.md#what-the-fifty-computers-actually-do-measured))
  is not an emergent property — it is the literal 7 in the generator's
  polynomial. Convergence speed was a design dial: 26 wake cycles from
  this seed, ~0.7ᵏ decay, puzzle runs in seconds by construction.

Part 1 is then F(20982) = 18982, part 2 the fixed point, and
`wake_sequence` — pure integer iteration of F — reproduces the live NAT's
26 deliveries element for element, final repeat included.

### The fixed-point ladder

In exact arithmetic F(y) = y means (y − a)³ = 3·10⁸·(y − a), whose roots
are a and a ± 10⁴√3 — and 3·10⁸ is not a perfect square, so **a is the
only integer fixed point** and its neighbours at ±17320.5… are where the
basin of attraction ends (|F′| crosses 1 there). Floor division smears
that picture: any y with 0 ≤ P(y) − 10⁹y < 10⁹ also satisfies
F(y) = y, which adds a short ladder of pseudo-fixed points. Scanning
±20000 around the answer (`floored_fixed_points`) finds exactly

> −6232, −6231, **11085, 11086, 11087, 11088**, 28409, 28410

— four attracting rungs at the bottom of the bowl and two stray pairs out
by the repelling roots. The live network descends from 20982 (inside the
basin: 20982 − a = 9894 < 17320) and **steps down onto the top rung**:
F(11089) = 11088, F(11088) = 11088, done. Seeded from *below*, the same
network would climb F(11084) = 11085 and freeze there — a different
puzzle answer from the same graph. "First Y delivered twice in a row" is,
precisely, "which rung of the floor-division ladder does your seed's
trajectory hit first", and the generator picked the seed so that every
user approaches from above.

That is also the full story of why the network idles: at the fixed point,
node 0 fans out a y equal to what every cone slot already holds, six
duplicate checks drop six packets, nothing fires, the queues drain, and
the NAT's next relay is the repeat. The Category Six network is a
chaotic-iteration fixed-point solver whose termination detector the
statement made you build.

## Tests pinned by this analysis

The disassembly section of
[test_day23.py](../../python/tests/test_day23.py), all against the live
input file (skipped on a clone without it):

- `test_node_table_shape` — 50 stubs parsed; census {id 32, mul 15,
  sum 2, div 1}; the seven decoys; the y-cone; NIC 10 as the sole
  255-talker with X = node 0's salt.
- `test_routing_is_exact` — `validate` clean; 65 consumer entries, 59
  distinct edges.
- `test_recovered_map_is_built_from_the_answer` — divisor 10⁹, the
  coefficients equal to the (y−a)³ + 10⁸(7y+3a) expansion with
  a = `LOCKED[1]`, F(a) = a, F(seed) = `LOCKED[0]`.
- `test_fixed_point_ladder` — 3·10⁸ not a square (a unique in exact
  arithmetic); the eight floored rungs; top rung from above, bottom rung
  from below.
- `test_static_answers_locked` — both answers off the disk.
- `test_divide_in_vitro` — eight calls straight into 436 on the live
  machine: floor for x ≥ 0, −1 for negatives.
- `test_self_modifying_stores_all_patch_operands` — 22 stores, all
  operand patches; exactly one jump *target* (the boot dispatch), two
  jump *conditions* (the barrier).
- `test_full_listing_accounts_for_every_cell` — 2,243 cells, every one
  listed exactly once; 11 runtime sections + 50 node sections.
- and in `test_real_traffic_shape`, the static/live splice: the iterated
  map equals the live wake sequence, and `static_answers` equals what the
  network delivers.
