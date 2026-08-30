"""Day 23 -- disassembling the Network Interface Controller.

Companion to Problem_Statements/days/day23_disassembly.md. Five passes:

  1. RECURSIVE-DESCENT DISASSEMBLY, seeded three ways. The image dispatches
     through (a) a boot jump whose operand is patched to `address + 11` --
     a 50-way computed goto through the table at 11..60, so every NIC runs
     its own entry stub; (b) Day 17's call idiom (return address into
     `rb[+0]`, jump, return via `jnz/jz .. rb[+0]`); and (c) an indirect
     call through the variable [69] -- a FUNCTION POINTER selecting the
     node's operator. Descent is seeded with the jump table, the idiom's
     targets and returns, and the four operator addresses.
  2. THE NODE TABLE. All 50 entry stubs share one shape -- six immediate
     stores into the variables at 66..72, then a jump into the shared
     receive loop -- and parsing them recovers a DATAFLOW GRAPH: each NIC
     is an operator node (sum / product / quotient / identity) with a slot
     table of operands (constants ship pre-filled) and a consumer list of
     (dest, X) packets, where X = salt_dest * slot is the receiver's own
     slot-addressing arithmetic.
  3. GRAPH VALIDATION. Every X routes exactly (a multiple of the receiver's
     salt, slot in range); every empty slot has exactly one feeder; every
     pre-filled slot has none; one node talks to 255, and its X is
     pre-addressed to land in node 0's seed slot when the NAT relays it.
  4. STATIC EVALUATION. Propagating polynomials in y (node 0's seed slot)
     through the graph collapses the whole network to one map
     y' = P(y) // D. On this input P(y) = (y - a)^3 + 10^8*(7y + 3a) with
     D = 10^9 and a = 11088 -- part 2 IS a coefficient of the input, the
     derivative at the fixed point is exactly 0.7, and part 1 = F(seed).
     Both answers with the VM never started.
  5. CROSS-CHECK. The static iterates against the live network's NAT
     deliveries, first packet included.

Nothing here is hardcoded to one user's file: stubs are parsed, not
pattern-matched at fixed addresses; the operator set is refused loudly on
any shape the tool does not understand; and the closed form is *checked*
against the recovered coefficients rather than assumed.

Run:  python python/day23_disasm.py [path-to-program] [--full]
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from day23 import parse_input, run_network
from intcode import VM

# ------------------------------------------------------- the program's layout

JUMP_TABLE = 11  # 50 entry addresses, indexed by the NIC's own address
FIRST_VAR = 61
RECEIVE = 73  # the shared receive loop
SEND = 210  # the shared send loop ([69]'s callees return here)
OP_SUM, OP_MUL, OP_DIV, OP_ID = 253, 302, 351, 556
RET_THUNK = 376  # op_div's landing pad after divide
POWERS = 385  # 2^0 .. 2^50, divide's bit table
DIVIDE = 436
NODES_BASE = 571  # first entry stub; stub+tables sections fill the rest

OP_NAMES = {OP_SUM: "sum", OP_MUL: "mul", OP_DIV: "div", OP_ID: "id"}

VARS = {
    61: "started",
    62: "t",
    63: "i",
    64: "x",
    65: "y",
    66: "salt",
    67: "n.slots",
    68: "slots",
    69: "op",
    70: "result",
    71: "n.out",
    72: "outs",
}

OPS = {
    1: ("add", 3),
    2: ("mul", 3),
    3: ("in", 1),
    4: ("out", 1),
    5: ("jnz", 2),
    6: ("jz", 2),
    7: ("lt", 3),
    8: ("eq", 3),
    9: ("arb", 1),
    99: ("hlt", 0),
}


# ------------------------------------------------------------ pass 1: descent


def operand(mem: list[int], addr: int, index: int) -> str:
    raw = mem[addr + index]
    mode = (mem[addr] // 10 ** (index + 1)) % 10
    if mode == 1:
        return f"#{raw}"
    if mode == 2:
        return f"rb[{raw:+d}]"
    return f"[{raw}]" + (f"={VARS[raw]}" if raw in VARS else "")


def render_instruction(mem: list[int], addr: int) -> tuple[str, int] | tuple[None, int]:
    op = mem[addr] % 100
    if op not in OPS:
        return None, 0
    name, count = OPS[op]
    if addr + count >= len(mem):
        return None, 0
    args = " ".join(operand(mem, addr, i) for i in range(1, count + 1))
    return f"{name:4}{' ' + args if args else ''}", count + 1


def call_sites(mem: list[int]) -> dict[int, tuple[int | None, int]]:
    """Every `rb[0] = ret; jmp ...` pair -> {call address: (target, ret)}.

    Day 17's convention, with one twist: the jump may be POSITION mode --
    `jz #0 [69]` is a call through a function pointer -- in which case the
    target is dynamic (None here; the stubs say what [69] can hold).
    """
    found = {}
    for addr in range(len(mem) - 7):
        if mem[addr] not in (21101, 21102) or mem[addr + 3] != 0:
            continue
        if mem[addr + 4] % 100 not in (5, 6) or (mem[addr + 4] // 100) % 10 != 1:
            continue
        a, b = mem[addr + 1], mem[addr + 2]
        ret = a + b if mem[addr] == 21101 else a * b
        jump_immediate = (mem[addr + 4] // 1000) % 10 == 1
        target = mem[addr + 6] if jump_immediate else None
        found[addr] = (target, ret)
    return found


def descend(mem: list[int], entries: list[int]) -> dict[int, tuple[str, int]]:
    """Disassemble forward from every entry point, following static jumps."""
    seen: dict[int, tuple[str, int]] = {}
    stack = list(entries)
    while stack:
        addr = stack.pop()
        while 0 <= addr < len(mem) and addr not in seen:
            text, size = render_instruction(mem, addr)
            if text is None:
                break
            seen[addr] = (text, size)
            op = mem[addr] % 100
            if op == 99:
                break
            if op in (5, 6):
                if (mem[addr] // 1000) % 10 == 1:
                    stack.append(mem[addr + 2])
                immediate = (mem[addr] // 100) % 10 == 1
                if immediate and (mem[addr + 1] != 0) == (op == 5):
                    break  # unconditional: nothing follows
            addr += size
    return seen


def entry_points(mem: list[int]) -> list[int]:
    """Everything descent needs: boot, loops, idiom calls, ops, all 50 stubs."""
    calls = call_sites(mem)
    ops = sorted({node.op_addr for node in recover_nodes(mem).values()})
    return sorted(
        {0, RECEIVE, SEND, *ops, RET_THUNK}
        | {t for t, _ in calls.values() if t is not None}
        | {r for _, r in calls.values()}
        | set(mem[JUMP_TABLE : JUMP_TABLE + 50])
    )


def full_descent(mem: list[int]) -> dict[int, tuple[str, int]]:
    return descend(mem, entry_points(mem))


def operand_patches(mem: list[int], listing: dict[int, tuple[str, int]]) -> list[tuple[int, int, int]]:
    """Stores whose destination lands inside another decoded instruction.

    Intcode has no indexed addressing, so array access patches the operand
    about to be executed (Days 15/17/19/21). New this day: ONE of the
    patched cells is a jump operand -- the boot dispatch -- so for the
    first time the self-modification carries control flow, not just data.
    """
    inside = {a + i: a for a, (_, size) in listing.items() for i in range(1, size)}
    found = []
    for addr in sorted(listing):
        if mem[addr] % 100 not in (1, 2, 7, 8):
            continue
        if (mem[addr] // 10000) % 10 != 0:
            continue  # relative destination: a frame slot, not a patch
        dest = mem[addr + 3]
        if dest in inside:
            found.append((addr, dest, inside[dest]))
    return found


def patch_kind(mem: list[int], dest: int, owner: int) -> str:
    """What a patched operand cell is to its owning instruction.

    Only a patched jump TARGET redirects control flow; a patched jump
    CONDITION is still just data a jump happens to read.
    """
    if mem[owner] % 100 in (5, 6):
        return "jump target" if dest == owner + 2 else "jump condition"
    return "data operand"


def pass1(mem: list[int]) -> dict[int, tuple[str, int]]:
    listing = full_descent(mem)
    covered = {a + i for a, (_, size) in listing.items() for i in range(size)}
    calls = call_sites(mem)
    patches = operand_patches(mem, listing)
    targets = [p for p in patches if patch_kind(mem, p[1], p[2]) == "jump target"]

    print("== pass 1: recursive descent ==")
    print(f"  {len(listing)} instructions covering {len(covered)} of {len(mem)} cells")
    print("  dispatch happens three ways:")
    print("    boot: [10] patched to address+11, then `jnz #1 [10]` -- a 50-way goto")
    print(f"    {len(calls)} rb[+0]-idiom call sites:")
    for a, (t, r) in sorted(calls.items()):
        target = f"target {t}" if t is not None else "target [69] (function pointer)"
        print(f"      {a:4}  {target}, ret {r}")
    print(f"  {len(patches)} self-modifying stores, every one an operand patch, and for")
    print(f"  the first time this year {len(targets)} of them patches a jump TARGET -- the")
    print("  boot dispatch is self-modified control flow, not just data addressing:")
    for store, dest, owner in patches:
        print(f"    {store:5} -> [{dest}], {patch_kind(mem, dest, owner)} of the instruction at {owner}")
    return listing


# --------------------------------------------------------- pass 2: the nodes


@dataclass(frozen=True)
class Node:
    address: int  # network address 0..49
    entry: int  # stub address, from the jump table
    salt: int  # [66]: incoming X is decoded as slot = X // salt
    op_addr: int  # [69]: 253 sum, 302 product, 351 quotient, 556 identity
    table: int  # [68]: slot table, n.slots * (flag, value) pairs
    slots: tuple[tuple[int, int], ...]
    outs: int  # [72]: consumer table, n.out * (dest, X) pairs
    consumers: tuple[tuple[int, int], ...]

    @property
    def op(self) -> str:
        return OP_NAMES[self.op_addr]


def parse_stub(mem: list[int], entry: int) -> dict[int, int]:
    """One entry stub: immediate stores into the variables, then `jmp 73`.

    Executed symbolically rather than pattern-matched, so operand order and
    add/mul spelling (the Day 21 encoding coin-flips) do not matter. Any
    other shape is refused.
    """
    regs: dict[int, int] = {}
    addr = entry
    while True:
        instr = mem[addr]
        op = instr % 100
        if op in (5, 6):
            if mem[addr + 2] != RECEIVE:
                raise ValueError(f"stub at {entry}: ends jumping to {mem[addr + 2]}, not {RECEIVE}")
            return regs
        if op not in (1, 2):
            raise ValueError(f"stub at {entry}: unexpected opcode {op} at {addr}")
        if (instr // 100) % 10 != 1 or (instr // 1000) % 10 != 1 or (instr // 10000) % 10 != 0:
            raise ValueError(f"stub at {entry}: non-immediate store at {addr}")
        a, b, dest = mem[addr + 1 : addr + 4]
        regs[dest] = a + b if op == 1 else a * b
        addr += 4


def recover_nodes(mem: list[int]) -> dict[int, Node]:
    nodes = {}
    for address in range(50):
        entry = mem[JUMP_TABLE + address]
        regs = parse_stub(mem, entry)
        if set(regs) != {66, 67, 68, 69, 71, 72}:
            raise ValueError(f"stub at {entry}: initialises {sorted(regs)}")
        if regs[69] not in OP_NAMES:
            raise ValueError(f"stub at {entry}: unknown operator address {regs[69]}")
        table, n = regs[68], regs[67]
        outs, n_out = regs[72], regs[71]
        nodes[address] = Node(
            address=address,
            entry=entry,
            salt=regs[66],
            op_addr=regs[69],
            table=table,
            slots=tuple((mem[table + 2 * i], mem[table + 2 * i + 1]) for i in range(n)),
            outs=outs,
            consumers=tuple((mem[outs + 2 * i], mem[outs + 2 * i + 1]) for i in range(n_out)),
        )
    return nodes


def slot_of(nodes: dict[int, Node], dest: int, x: int) -> int:
    """Which slot a packet (dest, x, _) lands in -- the receiver's own decode."""
    return x // nodes[dest].salt


def feeders(nodes: dict[int, Node]) -> dict[int, dict[int, list[int]]]:
    """dest -> slot -> [source addresses]. NAT traffic maps onto node 0."""
    fed: dict[int, dict[int, list[int]]] = {a: {} for a in nodes}
    for node in nodes.values():
        for dest, x in node.consumers:
            key = 0 if dest == 255 else dest
            fed[key].setdefault(slot_of(nodes, key, x), []).append(node.address)
    return fed


def y_cone(nodes: dict[int, Node]) -> set[int]:
    """The nodes the loop value actually flows through, node 0 included."""
    cone, frontier = {0}, [0]
    while frontier:
        for dest, _ in nodes[frontier.pop()].consumers:
            if dest != 255 and dest not in cone:
                cone.add(dest)
                frontier.append(dest)
    return cone


def pass2(mem: list[int]) -> dict[int, Node]:
    nodes = recover_nodes(mem)
    print("\n== pass 2: the fifty nodes ==")
    print(f"  {'nic':>3} {'op':>4} {'salt':>7}  slots -> consumers")
    for a, node in sorted(nodes.items()):
        slots = " ".join(f"({f},{v})" if f else "_" for f, v in node.slots)
        cons = " ".join("NAT" if d == 255 else f"{d}.s{slot_of(nodes, d, x)}" for d, x in node.consumers)
        print(f"  {a:>3} {node.op:>4} {node.salt:>7}  [{slots}] -> {cons or '(decoy)'}")
    counts: dict[str, int] = {}
    for node in nodes.values():
        counts[node.op] = counts.get(node.op, 0) + 1
    print(f"  operator census: {counts}")
    return nodes


# ----------------------------------------------------- pass 3: graph validity


def validate(nodes: dict[int, Node]) -> None:
    """Raise unless the routing arithmetic and slot accounting are airtight."""
    for node in nodes.values():
        for dest, x in node.consumers:
            key = 0 if dest == 255 else dest
            receiver = nodes[key]
            if x % receiver.salt != 0:
                raise ValueError(f"{node.address}->{dest}: X {x} not a multiple of salt {receiver.salt}")
            if not 1 <= x // receiver.salt <= len(receiver.slots):
                raise ValueError(f"{node.address}->{dest}: slot {x // receiver.salt} out of range")
    fed = feeders(nodes)
    for a, node in nodes.items():
        for i, (flag, _) in enumerate(node.slots, start=1):
            sources = fed[a].get(i, [])
            if flag == 1 and sources and a != 0:
                raise ValueError(f"node {a} slot {i}: pre-filled AND fed by {sources}")
            if flag == 0 and len(sources) != 1:
                raise ValueError(f"node {a} slot {i}: fed by {sources}, not exactly once")
    nat = [n for n in nodes.values() if any(d == 255 for d, _ in n.consumers)]
    if len(nat) != 1:
        raise ValueError(f"nodes talking to 255: {[n.address for n in nat]}")
    if nodes[0].op != "id" or nodes[0].slots[0][0] != 1:
        raise ValueError("node 0 is not an identity node with a pre-filled seed")


def pass3(nodes: dict[int, Node]) -> None:
    validate(nodes)
    decoys = sorted(a for a, n in nodes.items() if not n.consumers)
    cone = y_cone(nodes)
    edges = sum(len(n.consumers) for n in nodes.values())
    nat_node = next(n for n in nodes.values() if any(d == 255 for d, _ in n.consumers))
    nat_x = next(x for d, x in nat_node.consumers if d == 255)

    print("\n== pass 3: graph validation ==")
    print("  every X is salt * slot for its receiver, every empty slot fed exactly once")
    print(f"  {edges} consumer edges over {len(nodes)} nodes")
    print(f"  decoy nodes (no consumers, computed and discarded): {decoys}")
    print(f"  the y-cone -- nodes the loop value flows through: {sorted(cone)}")
    print(
        f"  node {nat_node.address} alone talks to 255, X = {nat_x} "
        f"= node 0's salt * {nat_x // nodes[0].salt} -- the packet is pre-addressed"
    )
    print("  so the NAT's verbatim relay lands in node 0's seed slot: the loop closes")


# ------------------------------------------------- pass 4: the map, statically


def _padd(p: list[int], q: list[int]) -> list[int]:
    n = max(len(p), len(q))
    return [(p[i] if i < len(p) else 0) + (q[i] if i < len(q) else 0) for i in range(n)]


def _pmul(p: list[int], q: list[int]) -> list[int]:
    out = [0] * (len(p) + len(q) - 1)
    for i, a in enumerate(p):
        for j, b in enumerate(q):
            out[i + j] += a * b
    return out


def recover_map(mem: list[int]) -> tuple[list[int], int, int]:
    """Collapse the dataflow graph to y' = P(y) // D.

    Node 0's seed slot is given the indeterminate y; every other pre-filled
    slot is a numeric (degree-0) polynomial; each node fires once in
    topological order, exactly as the boot cascade does. Returns
    (coefficients of P, D, seed). Division by anything non-constant, or a
    quotient flowing anywhere but 255, is refused.
    """
    nodes = recover_nodes(mem)
    validate(nodes)
    slotvals: dict[int, dict[int, list[int]]] = {a: {} for a in nodes}
    for a, node in nodes.items():
        for i, (flag, value) in enumerate(node.slots, start=1):
            if flag == 1:
                slotvals[a][i] = [0, 1] if a == 0 else [value]

    result: tuple[list[int], int] | None = None
    fired: set[int] = set()
    progress = True
    while progress:
        progress = False
        for a, node in sorted(nodes.items()):
            if a in fired or len(slotvals[a]) < len(node.slots):
                continue
            operands = [slotvals[a][i] for i in range(1, len(node.slots) + 1)]
            if node.op == "div":
                num, den = operands
                if len(den) != 1:
                    raise ValueError(f"node {a}: division by a non-constant")
                if {d for d, _ in node.consumers} != {255}:
                    raise ValueError(f"node {a}: a quotient flows onward, not just to 255")
                result = (num, den[0])
                value = None
            elif node.op == "id":
                value = operands[0]
            elif node.op == "sum":
                value = [0]
                for p in operands:
                    value = _padd(value, p)
            else:  # mul
                value = [1]
                for p in operands:
                    value = _pmul(value, p)
            fired.add(a)
            progress = True
            for dest, x in node.consumers:
                if dest != 255:
                    slotvals[dest][slot_of(nodes, dest, x)] = value
    if len(fired) != len(nodes):
        raise ValueError(f"nodes never firing: {sorted(set(nodes) - fired)}")
    if result is None:
        raise ValueError("no quotient node reached 255")
    coeffs, divisor = result
    return coeffs, divisor, nodes[0].slots[0][1]


def map_value(coeffs: list[int], divisor: int, y: int) -> int:
    """One application of the recovered map, with the MACHINE's division.

    divide() is floor division for a non-negative numerator and -1
    otherwise (pinned live in the tests), so a negative P(y) is refused
    rather than silently mis-modelled.
    """
    numerator = sum(c * y**i for i, c in enumerate(coeffs))
    if numerator < 0:
        raise ValueError(f"P({y}) < 0: the machine's divide would return -1 here")
    return numerator // divisor


def wake_sequence(mem: list[int]) -> list[int]:
    """The NAT's deliveries, statically: iterate F from the seed to the
    fixed point. Matches the live network's wake Ys element for element,
    final repeat included."""
    coeffs, divisor, seed = recover_map(mem)
    ys = [map_value(coeffs, divisor, seed)]
    while len(ys) < 2 or ys[-1] != ys[-2]:
        ys.append(map_value(coeffs, divisor, ys[-1]))
    return ys


def static_answers(mem: list[int]) -> tuple[int, int]:
    """(part 1, part 2) off the disk: F(seed), and F's reached fixed point."""
    ys = wake_sequence(mem)
    return ys[0], ys[-1]


def closed_form(coeffs: list[int], divisor: int) -> int | None:
    """If P(y) == (y - a)^3 + (divisor/10)*(7y + 3a), return a; else None.

    a is read off the recovered coefficients (c2 = -3a), then the whole
    identity is verified -- so a match is a fact, not a fit.
    """
    if len(coeffs) != 4 or coeffs[3] != 1 or coeffs[2] % 3 or divisor % 10:
        return None
    a, tenth = -coeffs[2] // 3, divisor // 10
    expected = [a * 3 * tenth - a**3, 3 * a * a + 7 * tenth, -3 * a, 1]
    return a if coeffs == expected else None


def floored_fixed_points(coeffs: list[int], divisor: int, around: int, radius: int = 20000) -> list[int]:
    """Every integer y in [around-radius, around+radius] with F(y) == y."""
    return [
        y
        for y in range(around - radius, around + radius + 1)
        if sum(c * y**i for i, c in enumerate(coeffs)) // divisor == y
    ]


def pass4(mem: list[int]) -> None:
    coeffs, divisor, seed = recover_map(mem)
    terms = " + ".join(f"{c}*y^{i}" if i else str(c) for i, c in enumerate(coeffs) if c)
    ys = wake_sequence(mem)
    part1, part2 = ys[0], ys[-1]

    print("\n== pass 4: the map, statically ==")
    print(f"  the whole network is  y' = ({terms}) // {divisor}")
    a = closed_form(coeffs, divisor)
    if a is not None:
        print(f"  which is exactly  ((y - {a})^3 + {divisor // 10}*(7y + 3*{a})) // {divisor}")
        print(f"  so F({a}) = {a} by construction and F'({a}) = 0.7 exactly --")
        print("  part 2 is a COEFFICIENT of the input, convergence tuned by design")
    print(f"  seed (node 0's pre-filled slot) = {seed}")
    print(f"  PART 1 (static) = F(seed) = {part1}")
    print(f"  PART 2 (static) = fixed point = {part2}, reached in {len(ys)} evaluations")
    fps = floored_fixed_points(coeffs, divisor, part2)
    print(f"  floor-division fixed points near the answer: {fps}")
    print("  (the exact map has one integer fixed point; flooring widens it to a")
    print("   short ladder, and the descent from the seed lands on the TOP rung)")


# -------------------------------------------------------- pass 5: cross-check


def live_wakes(mem: list[int]) -> tuple[int, list[int]]:
    """(first Y to 255, all wake Ys) from the real network, run to part 2."""
    first = None
    wakes: list[int] = []
    for kind, _x, y in run_network(list(mem)):
        if kind == "nat" and first is None:
            first = y
        elif kind == "wake":
            wakes.append(y)
            if len(wakes) >= 2 and wakes[-1] == wakes[-2]:
                assert first is not None
                return first, wakes
    raise AssertionError("run_network never returns")


def pass5(mem: list[int]) -> None:
    static = wake_sequence(mem)
    first, wakes = live_wakes(mem)
    print("\n== pass 5: cross-check against the live machine ==")
    print(f"  static iterates == live wake Ys ({len(wakes)} of them): {static == wakes}")
    print(f"  first live packet to 255 == F(seed): {first == static[0]}")
    print(f"  static answers = {static_answers(mem)}")


# ------------------------------------------------ the in-vitro call harness


def call_subroutine(program: list[int], addr: int, *args: int, limit: int = 100_000) -> int:
    """Run one subroutine of the image on the live VM, nothing else.

    The calling convention recovered in pass 1, replayed by hand: return
    address into rb[+0], arguments into rb[+1..], jump to the entry. The
    return address holds a hand-planted `hlt`, so the subroutine's own
    return ends the machine; the result is where the convention leaves it,
    rb[+1]. This is how the divide at 436 is pinned as a test without
    booting the network around it.
    """
    vm = VM(list(program))
    ret, base = 9_999, 10_000
    vm.mem[ret] = 99
    vm.rb = base
    vm.mem[base] = ret
    for i, value in enumerate(args, start=1):
        vm.mem[base + i] = value
    vm.ip = addr
    for _ in range(limit):
        if vm.step() == "halted":
            return vm.mem[base + 1]
    raise RuntimeError(f"subroutine at {addr} still running after {limit} steps")


# ------------------------------------------------------- the full listing

NOTES = {
    0: "the only input boot reads: the NIC's network address",
    2: "patch the dispatch: [10] = address + 11",
    6: "rb = one past the image: the ops' frames live in the heap",
    8: "jump through the patched operand -- goto table[address]",
    73: "poll: X, or -1 for an empty queue",
    79: "a real packet: go read Y",
    82: "-1 before the boot barrier has run: go run it",
    85: "-1 and already started: keep polling",
    88: "Y",
    90: "arg 1 = X",
    94: "arg 2 = salt",
    98: "call divide -> slot number v",
    105: "v - 1: slots count from 1",
    113: "v < 1 (divide returns -1 for X < 0): drop the packet",
    120: "v - 1 >= n.slots: drop the packet",
    123: "patch: [133] = slots + 2(v-1), the slot's flag cell",
    131: "t = flag (patched operand)",
    135: "patch: [140] = the slot's value cell",
    139: "t2 = (stored value == Y) (patched operand)",
    143: "flag AND unchanged ->",
    147: "-> drop: a duplicate changes nothing, and QUIESCENCE IS THE POINT",
    158: "flag := 1 (patched destination)",
    166: "value := Y (patched destination)",
    170: "started := 1",
    178: "the barrier: scan every slot",
    189: "patch: [194] = slot i's flag cell",
    193: "any slot still empty -> back to polling (patched operand)",
    203: "all slots full: ret := 210",
    207: "indirect call through the function pointer [69]",
    210: "the op left its result in rb[+1]",
    218: "for each consumer pair",
    225: "patch: [234] = outs + 2i, the dest cell",
    233: "out dest (patched operand)",
    235: "patch: [240] = the X cell",
    239: "out X (patched operand)",
    241: "out result -- the Y",
    250: "back to polling",
    253: "op_sum: fold + over the slot values",
    263: "for each slot",
    270: "patch: [283] = slots + 2i + 1, the value cell",
    282: "acc += value (patched operand)",
    293: "no-op move: the result is already in rb[-3]",
    299: "return (jz spelling)",
    302: "op_mul: fold * over the slot values",
    319: "patch: [332] = the value cell",
    331: "acc *= value (patched operand)",
    342: "no-op move, again",
    348: "return (jnz spelling)",
    351: "op_div: quotient of slot 1 by slot 2",
    353: "patch: [358] = slot 1's value cell",
    357: "arg 1 = slot 1 (patched operand)",
    361: "patch: [367] = slot 2's value cell",
    365: "arg 2 = slot 2 (patched operand)",
    369: "call divide -> ret 376",
    376: "hoist the quotient into rb[+1] for the send loop",
    382: "return to 210",
    436: "divide(x, d): restoring binary long division",
    438: "d * 10",
    446: "x < 10d: subtraction is cheaper than 51 rounds of bits",
    449: "q := 0",
    453: "r := 0",
    457: "i := 51",
    465: "patch: [470] = 385 + i, the power cell",
    469: "p := 2^i (patched operand)",
    473: "r := r * 2",
    477: "x < 2^i: bit i of x is 0",
    484: "bit i is 1: r += 1 ...",
    492: "... and strip it: x -= 2^i",
    496: "r < d: no subtraction this round",
    503: "restoring step:",
    507: "r -= d",
    511: "q += 2^i",
    515: "loop while i > 0",
    521: "q := -1  -- x < 0 lands here untouched: divide(negative) = -1, NOT floor",
    529: "x < 0: done counting",
    536: "x -= d",
    540: "q += 1",
    547: "result into rb[-7], the caller's rb[+1]",
    553: "return",
    556: "op_id: forward slot 1 unchanged",
    558: "patch: [563] = slot 1's value cell",
    562: "result := value (patched operand)",
    568: "return to 210 (the arb slid the result into rb[+1])",
}


def _node_title(nodes: dict[int, Node], a: int) -> str:
    node = nodes[a]
    cone = y_cone(nodes)
    if a == 0:
        return f"NIC 0: the loop node -- identity, seed {node.slots[0][1]}, fans out to the cone"
    kind = {"sum": "sum node", "mul": "product node", "div": "quotient node", "id": "constant node"}[node.op]
    if node.op == "id" and node.slots[0][0] == 1:
        kind = f"constant node ({node.slots[0][1]})"
    tags = []
    if not node.consumers:
        tags.append("DECOY: no consumers")
    if a in cone:
        tags.append("in the y-cone")
    if any(d == 255 for d, _ in node.consumers):
        tags.append("talks to 255")
    return f"NIC {a}: {kind}, salt {node.salt}" + (f" -- {', '.join(tags)}" if tags else "")


def full_listing(mem: list[int]) -> str:
    """The whole image, cell by cell, as one continuous annotated listing.

    Layout follows the Day 17/21 listings (address, raw cells, assembly,
    terse comment). Every cell of the image appears exactly once --
    asserted, not hoped.
    """
    nodes = recover_nodes(mem)
    validate(nodes)
    listing = full_descent(mem)
    calls = call_sites(mem)
    fed = feeders(nodes)

    covered: set[int] = set()
    lines: list[str] = []

    def emit(addr: int, raw: list[int], asm: str, note: str = "") -> None:
        cells = " ".join(str(v) for v in raw)
        text = f"{addr:04d}  {cells:<26} {asm}"
        lines.append(f"{text:<66}; {note}" if note else text.rstrip())

    def code(lo: int, hi: int) -> None:
        addr = lo
        while addr <= hi:
            text, size = listing.get(addr, (None, 0))
            if text is None:
                raise ValueError(f"cell {addr} in code region {lo}..{hi} is not an instruction")
            note = NOTES.get(addr, "")
            if addr in calls and not note:
                target, ret = calls[addr]
                note = f"call {target if target is not None else '[69]'} -> ret {ret}"
            emit(addr, mem[addr : addr + size], text, note)
            covered.update(range(addr, addr + size))
            addr += size

    def ints(lo: int, count: int, per_row: int, note_for=None) -> None:
        for start in range(lo, lo + count, per_row):
            end = min(start + per_row, lo + count)
            note = note_for(start) if note_for else ""
            emit(start, mem[start:end], "", note)
            covered.update(range(start, end))

    def header(title: str) -> None:
        if lines:
            lines.append("```")
            lines.append("")
        lines.append(f"## {title}")
        lines.append("")
        lines.append("```")

    header("0000 .. 0010 — boot: read the address, dispatch through the jump table")
    code(0, 10)
    header("0011 .. 0060 — the jump table: one entry stub per network address")
    ints(JUMP_TABLE, 50, 5, lambda a: f"addresses {a - JUMP_TABLE}..{min(a - JUMP_TABLE + 4, 49)}")
    header("0061 .. 0072 — the twelve variables")
    for addr in sorted(VARS):
        emit(addr, [mem[addr]], f".int {mem[addr]}", VARS[addr])
        covered.add(addr)
    header("0073 .. 0209 — the receive loop: poll, decode X to a slot, store, barrier")
    code(RECEIVE, SEND - 1)
    header("0210 .. 0252 — the send loop: one (dest, X, result) triple per consumer")
    code(SEND, OP_SUM - 1)
    header("0253 .. 0301 — op_sum")
    code(OP_SUM, OP_MUL - 1)
    header("0302 .. 0350 — op_mul")
    code(OP_MUL, OP_DIV - 1)
    header("0351 .. 0384 — op_div: two loads, then divide; the landing pad at 376")
    code(OP_DIV, POWERS - 1)
    header("0385 .. 0435 — powers of two, 2^0 .. 2^50: divide's bit table")
    ints(POWERS, 51, 4)
    header("0436 .. 0555 — divide(x, d): restoring binary long division")
    code(DIVIDE, OP_ID - 1)
    header("0556 .. 0570 — op_id")
    code(OP_ID, NODES_BASE - 1)

    for node in sorted(nodes.values(), key=lambda n: n.entry):
        end = (
            node.outs + 2 * len(node.consumers) - 1
            if node.consumers
            else node.table + 2 * len(node.slots) - 1
        )
        header(f"{node.entry:04d} .. {end:04d} — {_node_title(nodes, node.address)}")
        code(node.entry, node.table - 1)
        for i, (flag, value) in enumerate(node.slots, start=1):
            addr = node.table + 2 * (i - 1)
            if flag == 1:
                note = f"slot {i}: pre-filled, value {value}" + (" (the seed)" if node.address == 0 else "")
            else:
                sources = fed[node.address].get(i, [])
                note = f"slot {i}: awaits NIC {sources[0]}" if sources else f"slot {i}: never fed"
            emit(addr, mem[addr : addr + 2], f".int {flag} {value}", note)
            covered.update((addr, addr + 1))
        for i, (dest, x) in enumerate(node.consumers):
            addr = node.outs + 2 * i
            if dest == 255:
                note = f"-> 255; X = node 0's salt * {slot_of(nodes, 0, x)}, ready for the NAT relay"
            else:
                note = f"-> NIC {dest} slot {slot_of(nodes, dest, x)} (X = {nodes[dest].salt} * {slot_of(nodes, dest, x)})"
            emit(addr, mem[addr : addr + 2], f".int {dest} {x}", note)
            covered.update((addr, addr + 1))
    lines.append("```")

    missing = set(range(len(mem))) - covered
    if missing:
        raise ValueError(f"{len(missing)} cells never listed, first {sorted(missing)[:5]}")
    extra = covered - set(range(len(mem)))
    if extra:
        raise ValueError(f"listed cells beyond the image: {sorted(extra)[:5]}")

    coeffs, divisor, seed = recover_map(mem)
    intro = "\n".join(
        [
            "# Day 23 — the complete listing (`day23.txt`)",
            "",
            f"> All {len(mem)} integers of `inputs/day23.txt`, every one accounted for:",
            f"> {len(listing)} instructions across the boot dispatch, the shared runtime,",
            "> the four operators and fifty entry stubs, then the per-node slot and",
            "> consumer tables. Generated by",
            "> [python/day23_disasm.py](../../python/day23_disasm.py) —",
            "> `python python/day23_disasm.py --full`. Not committed: the raw cells",
            "> republish the puzzle input (see `.gitignore`).",
            ">",
            "> The analysis behind the annotations is in",
            "> [day23_disassembly.md](day23_disassembly.md); this file is the evidence",
            "> for it, in address order. Notation: `[a]` position, `#n` immediate,",
            "> `rb[+n]` relative; an `=name` suffix marks a known variable.",
            "",
            (
                f"The graph these tables encode collapses to y' = P(y) // {divisor} with"
                f" P = {coeffs} (low degree first), iterated from seed {seed}."
            ),
            "",
            "",
        ]
    )
    return intro + "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    import sys

    argv = sys.argv[1:] if argv is None else argv
    full = "--full" in argv
    argv = [a for a in argv if a != "--full"]
    default = Path(__file__).resolve().parent.parent / "inputs" / "day23.txt"
    mem = parse_input(Path(argv[0] if argv else default).read_text())

    if full:
        sys.stdout.reconfigure(encoding="utf-8")
        print(full_listing(mem), end="")
        return

    pass1(mem)
    nodes = pass2(mem)
    pass3(nodes)
    pass4(mem)
    pass5(mem)


if __name__ == "__main__":
    main()
