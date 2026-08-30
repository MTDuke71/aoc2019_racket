# Day 23 — Category Six (function guide)

> Code: [python/day23.py](../../python/day23.py). Tests:
> [python/tests/test_day23.py](../../python/tests/test_day23.py) (20 test
> functions, 27 with parametrization). Statement: [day23.md](day23.md).
> Disassembly: [day23_disassembly.md](day23_disassembly.md).
>
> **Answers: Part 1 = 18982, Part 2 = 11088** (both verified on
> adventofcode.com; `LOCKED = (18982, 11088)`).

## The puzzle in one paragraph

Fifty copies of the same Intcode program — a Network Interface Controller —
boot up, each reading its own address (0..49) as its first input, and then
talk to each other in packets: three outputs make a `(dest, X, Y)` triple,
two inputs consume a queued `(X, Y)` pair, and an input against an empty
queue must be answered with `-1` *immediately* — the statement is explicit
that neither direction ever blocks. Part 1: what is the Y of the first
packet sent to address 255? Part 2 gives address 255 a body: it is the NAT
("Not Always Transmitting"), a device that remembers only the *last*
packet sent to it, watches for the network going **idle** — the
statement's words: all computers have *empty incoming packet queues* and
are *continuously trying to receive packets* without sending — and on
idleness forwards its held packet to address 0 to restart the chatter;
the answer is the first Y the NAT delivers to address 0 *twice in a row*.

## The day in canonical vocabulary

The VM is untouched — frozen since [Day 9](day09_function_guide.md), the
same import [Days 13](day13_function_guide.md)–21 used. What is new is that
the *peripheral* is plural: this is the first day one Python loop juggles
fifty concurrent machines (Day 7 juggled five). Every piece of the day has
a standard name:

- The driver is a **cooperative round-robin scheduler** — an **event
  loop** over fifty **coroutines**. Nothing preempts a NIC; it runs until
  it *asks* for something the world doesn't have. This is `asyncio` /
  green-threads territory, built by hand in thirty lines.
- The `-1` protocol is **non-blocking I/O by polling**: "read, and if
  there is nothing, be told so and carry on" — `O_NONBLOCK` returning
  `EWOULDBLOCK`, as a puzzle.
- Part 2's idle test is **distributed termination detection** — the
  textbook problem (Dijkstra–Scholten is the canonical algorithm) of an
  outside observer deciding that a set of communicating processes has
  collectively finished, when "finished" is a *global* predicate no single
  process can see. Here the observer is handed a synchronous scheduler, so
  the full machinery collapses to a fixed-point test — but the trap it
  collapses *around* (see [the boot round](#the-boot-round-trap)) is the
  same in-flight-message hazard the real algorithms exist to handle.
- The NAT itself is a **watchdog**: a one-packet register that turns
  detected quiescence back into work. The network never terminates; it
  *parks*, and the NAT unparks it. Part 2's "same Y twice in a row" is the
  watchdog noticing the network has stopped changing — convergence
  detection, not deadlock detection.

One layering point worth savouring: our frozen VM's opcode 3 *does* block —
`step()` returns `"blocked"` and refuses to advance
([Day 7](day07_function_guide.md)'s protocol). The statement's "input never
blocks" is implemented entirely in the scheduler, which converts every
starved read into a fed `-1`. Non-blocking I/O is not a property of the
machine; it is a property of the operating system around it — which is
exactly where real kernels put it.

## `parse_input`

One line of comma-separated integers, `strip()`ed for the usual CRLF
reasons. 2,243 cells — mid-sized for the year (Day 21 was 2,050,
[Day 13](day13_function_guide.md) 2,640).

## `run_network` — the scheduler

The whole day lives in this one generator. Design decisions, in order:

**The scheduling quantum is "run until starved".** One slice steps a VM
until it requests input the queue cannot answer; then it is fed a single
`-1` and set aside until the next round. While it runs, everything it can
make progress on, it does: queued packets are delivered the moment it asks
(both values at once — the statement promises the second input instruction
follows), and completed output triples are dispatched immediately. The
alternative — lockstep, one instruction per VM per turn — is discussed
[below](#design-alternatives); run-until-starved is safe because the NICs
are *cooperative* (a NIC that computed forever without polling would hang
any scheduler) and it makes every slice boundary a **starved read**, which
is what the idle argument below stands on.

**Packets are framed by counting, not by trusting timing.** Each VM has a
persistent 3-slot `triple` buffer; every output lands there, and the triple
dispatches when full. Nothing assumes a NIC emits its three outputs without
pausing for input in between — the buffer survives across slices.
[Day 13](day13_function_guide.md) framed its output stream the same way
(flat outputs → `(x, y, tile)`), and Day 23 adds routing: the first field
is an *address*, and one of the fifty-one addresses (255) is a register,
not a computer.

**The NAT holds one packet, not a queue.** `nat = (x, y)` — assignment *is*
the semantics. Every packet to 255 overwrites the previous one; the tests'
`BROADCAST` fixture pins that (fifty senders, and every wake replays only
the last).

**The caller sees events, not machinery.** `run_network` yields an endless
stream — `("nat", x, y)` when a packet reaches 255, `("wake", x, y)` when
idleness triggers the NAT's forward — and both parts are folds over that
one stream. Part 1 never mentions idleness; part 2 never mentions how
packets move. The same structural move as [Day 19](day19_function_guide.md)
hiding the VM behind `probe(x, y)`: everything above the generator is
testable with no real input in sight, which is what the hand-assembled
fixture NICs in the test module exploit.

## The boot-round trap

The first version of this scheduler declared the network idle in **round
1**, before a single packet had been sent, and died with an empty NAT. That
bug is the day's most instructive moment, so here is the full argument.

The obvious idle test — *no packet moved this round and every queue is
empty* — is a statement about the past, but idleness is a claim about the
**future**: "this network will never do anything again unless the NAT
intervenes." The gap between the two is a VM that absorbed something this
round and hasn't answered yet.

Run-until-starved closes the gap. Every slice ends with its VM parked at an
input instruction, one fed `-1` pending. So in any round from 2 onward,
each VM's slice begins by consuming a `-1` — and if the round then passes
with no output and no delivery, the network has *witnessed* the fixed
point: all fifty machines were offered "nothing for you" simultaneously,
and all fifty said nothing back. Feeding more `-1`s can only repeat that
experiment. A quiet round *is* the proof, **provided the token each VM
absorbed really was a `-1`**.

Round 1 is the one round where it isn't: the token is the NIC's own
**address**. On the real input every NIC reads its address, polls once
before saying anything, and starves — a round that moves no packet and
fills no queue, one instruction away from a 58-packet burst in round 2.
Hence the `rounds >= 2` guard, and hence the `BOOTSLOW` fixture
(`test_boot_quiet_round_is_not_idle`): a five-instruction NIC that polls
once before its first send, which a round-1 idle test misjudges as dead.

Two failure modes stay fatal on purpose: a network that reaches the fixed
point with an empty NAT, and a network of halted VMs (a halted NIC stops
absorbing `-1`s, so normal idleness can never be declared again). Both
raise `RuntimeError` rather than spin — pinned by the `DEADLOCK` and `[99]`
fixtures.

## `part1`, `part2`, `solve`

Three folds over the event stream:

- `part1`: Y of the first `"nat"` event.
- `part2`: first Y two *consecutive* `"wake"` events share. "Twice in a
  row" is doing work — the `CONVERGE` fixture's wake Ys climb
  25, 26, 27, 28, 29, 30, 30, and the answer must be the plateau, not the
  first wake. (On the real input the distinction happens not to bite; see
  the next section.)
- `solve`: both from **one** network run. Safe because 255-traffic always
  precedes wake-traffic — an idle network can only replay the NAT's held
  packet, so the NAT must have been written before the first wake — and
  measurably worthwhile: part 1 alone stops at round 7 of the 83 the full
  run takes (11.7 ms of the 153).

## What the fifty computers actually do (measured)

Everything below is instrumented from the real run (the recon script's
numbers; the durable ones are pinned in `test_real_traffic_shape`).

The run to part 2's answer: **83 rounds, 665 packets, 26 wakes, 172,850
`step()` calls**. The first packet to 255 arrives in round 7 — the 65th
and *last* packet of the boot cascade (the disassembly explains why it
must be: it is the output of the graph's final node); the first idle
follows in round 8, so the first wake replays part 1's own packet —
`wake_ys[0] == part 1`, pinned. After the boot burst (58 of those 65
packets land in rounds 2–3, fanning over edges that never speak again),
the steady state is a **pipeline**:

```
            ┌─→ 25 ─┐  (×3 per wake)
  NAT → 0 ──┼─→ 19 ─┼─→ 43 ─→ 10 ─→ 255 → NAT …
            └─→ 34 ─┘  (×2, ×1)
```

Each wake, NIC 0 fans out six packets — three to 25, two to 19, one to 34,
the same 3/2/1 split as its boot burst — each worker forwards to 43, 43
funnels everything to 10, and **10 is the only NIC that ever addresses
255** (all 151 packets, every one carrying the same X, 29569). The edge
counts over the whole run: 43→10 and 10→255 both 151, 0→25/25→43 78/76,
0→19/19→43 52/51, 0→34/34→43 26/26.

And the Y the NAT sees *descends monotonically to a fixed point*:

```
18982 17105 15517 14275 13351 12683 12208 11873 11637 11472
11356 11275 11218 11179 11151 11132 11118 11109 11102 11097
11094 11092 11090 11089 11088 11088   ← part 2
```

Successive differences 1877, 1588, 1242, 924, 668, 475, … shrink by a
ratio hovering around **0.70** — geometric convergence, the signature of a
distributed relaxation / fixed-point iteration. The strict descent is
pinned as a test (it is an input property, not a promise — the `CONVERGE`
fixture climbs instead), and it means the classic wrong-part-2 bug —
tracking "any Y seen before" in a set instead of "same Y twice in a row" —
happens to produce the right answer on this input: in a monotone sequence
the first repeat *is* consecutive. The fixture suite is where the
distinction is enforced.

So part 2's fixed point 11088 is not an accident of scheduling; it is the
value this little distributed computation converges to, with the NAT as
its convergence detector. What function the network iterates — the boot X
values were the tell (0's three payloads to 25 are exact multiples
18253/36506/54759) — is now fully answered by the disassembly.

## The NIC, disassembled

The full teardown lives in [day23_disassembly.md](day23_disassembly.md)
(tool: [python/day23_disasm.py](../../python/day23_disasm.py)), and it
reframes the whole day. The 2,243-cell image is **fifty programs behind a
50-way computed goto** — the year's first self-modified jump *target* —
each entry stub declaring one node of a **dataflow graph**: an operator
(sum, product, quotient, or identity), a slot table of operands
(constants ship pre-filled; the suggestive X multiples are the receiver's
own slot-addressing arithmetic, slot = X // salt), and a consumer list of
pre-addressed packets. The duplicate-check in the shared receive loop is
change propagation — the network is a chaotic-iteration fixed-point
solver, and the quiescence part 2 detects is the solver converging.
Collapsing the graph by propagating polynomials through it yields the
whole network as one map,

> F(y) = ((y − 11088)³ + 10⁸·(7y + 3·11088)) // 10⁹

iterated from seed 20982: **part 2's answer is a coefficient of the
input**, F′(11088) = 0.7 exactly (the measured delta ratio above, revealed
as a design dial), part 1 = F(seed), and the static iteration matches the
live wake sequence element for element — both answers off the disk with
the VM never started, in the [Day 15](day15_disassembly.md)/
[17](day17_disassembly.md)/[19](day19_disassembly.md)/
[21](day21_disassembly.md) tradition.

## Design alternatives

**Lockstep scheduling** — one instruction per VM per turn — is the other
defensible quantum. It simulates true concurrency (no NIC can burn
unbounded time inside one slice) at ~50× the dispatch overhead, and it
*loses* the property the idle proof used: slice boundaries are no longer
starved reads, so "quiet round = fixed point" stops holding and you are
back to heuristics. With cooperative NICs, run-until-starved is both
faster and easier to reason about.

**Idle-streak heuristics** — "declare idle after every VM has read `-1`
N times in a row", for some N ≥ 2 — are what most Day 23 solutions in the
wild use. They work (for large enough N) but N is a guess standing in for
an argument. The fixed-point framing replaces the guess with a proof
obligation — *the token absorbed in a quiet round must be a `-1`* — which
run-until-starved discharges for every round but the first, leaving
`rounds >= 2` as the entire correction. When a heuristic and an invariant
disagree about where the magic number goes, prefer the invariant.

## If I were writing this in Rust

The scheduler is where the borrow checker would earn its keep: the delivery
`queues[dest].append(...)` *while iterating* `zip(vms, queues, triples)` is
exactly the aliasing pattern Rust refuses (`&mut queues[i]` held while
`&mut queues[dest]` is needed). The standard resolutions map the design
space nicely: index-based access (`for i in 0..vms.len()`, borrowing one
element at a time — the literal translation), draining each triple into a
local `Vec<Packet>` and routing after the slice ends (cleaner: it makes
"packets sent this round" a first-class value instead of a `busy` flag), or
going full message-passing with `std::sync::mpsc` channels per NIC and the
NAT as a `Mutex<Option<Packet>>` — at which point idle detection stops
being a loop invariant and becomes the *hard* version of termination
detection, which is precisely why the single-threaded round-robin is the
right architecture and the threaded one is a trap. `enum Event { Nat(i64,
i64), Wake(i64, i64) }` replaces the string-tagged tuples, and
`VecDeque<(i64, i64)>` is the queue verbatim.

## Tests

Twenty test functions (27 with parametrization). No worked example exists
in the statement, so — as on [Days 17](day17_function_guide.md),
[19](day19_function_guide.md) and [21](day21_function_guide.md) — the
suite tests the logic without the puzzle input, here via five
**hand-assembled Intcode NICs** (each listed opcode-by-opcode in the test
module): `BROADCAST` (round-robin order, last-packet-wins NAT), `RELAY`
(a packet crosses the network intact), `BOOTSLOW` (the boot round is not
idle — the day's trap, as a five-line program), `CONVERGE` (wake Ys climb
to a plateau; "twice in a row" must wait for it), `DEADLOCK` and `[99]`
(fatal idleness raises). On the real input, one full instrumented run
pins the strict descent of the wake sequence, the
first-wake-replays-part-1 identity, the 151-packets/one-X shape of the
255 traffic, and `solve`'s agreement with the stream it summarises;
`check_locked` holds the verified answers. The disassembly adds eight
more — the node census and routing arithmetic, the closed-form
coefficients, the fixed-point ladder, the divide subroutine called in
vitro on the live machine, the one patched jump target, full-listing
coverage, and both answers recovered statically — catalogued at the end
of [day23_disassembly.md](day23_disassembly.md).

## Benchmarks

`python\bench.py 23 -n 15`, best / median ms:

| Day | Parse | Part 1 | Part 2 | Total |
|----:|------:|-------:|-------:|------:|
| 23 | 0.155 / 0.166 | 11.679 / 11.876 | 141.286 / 143.158 | 153.120 |

Part 1 stops at round 7 of part 2's 83 — the 12× between them is runway,
not algorithm. The cost model is [Day 15](day15_function_guide.md)'s,
unchanged for the sixth Intcode day running: 172,850 `step()` calls in
141 ms ≈ **1.2 M steps/s**, and the scheduling logic above the VMs costs
nothing measurable. `solve` shares one run, so the day as shipped is
~141 ms, not the 153 of the parts benched separately.
