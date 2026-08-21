"""Day 19 -- disassembling the tractor-beam drone oracle.

Companion to Problem_Statements/days/day19_disassembly.md. Five passes:

  1. LINEAR DISASSEMBLY. 424 cells, ALL of them code -- no data tables, no
     strings, unlike Day 15 and Day 17. One main routine and four
     subroutines on Day 17's calling convention (return address in rb[0],
     `arb`-framed locals, indirect `jnz #1 rb[0]` return) -- one of which
     is a TRAMPOLINE that patches its own jump operand to call a function
     whose address arrives as an argument.
  2. CONSTANT RECOVERY. The drone's answer is the predicate
         |A*x^2 - B*y^2| <= C*x*y
     and A, B, C are the only honest immediates in the program. Everything
     else is mined from its own code: the literal 1 is the input
     instruction's operand, and the two call targets used indirectly are
     laundered through an algebraic no-op ((v-2)*2 + 3 - v + 1 == v).
     Recovery is structural -- each immediate is classified by the call
     that consumes it -- so a different user's input yields different
     constants rather than a confidently wrong formula.
  3. FORMULA vs VM. The closed form against the live machine: the full
     50x50 window, plus bands straddling BOTH beam edges at depth, where
     an off-by-one in the boundary would actually show.
  4. STATIC ANSWERS. Both parts by integer arithmetic (math.isqrt), no VM:
     each row's beam is the integer interval between two rays of
     irrational slope, so the census is a sum of interval widths and the
     square search is a walk down two exact edge functions.
  5. CROSS-CHECK. Both static answers against the live machine.

Run:  python python/day19_disasm.py [path-to-program]
"""

from __future__ import annotations

import sys
from math import isqrt
from pathlib import Path

from day19 import beam_probe, count_beam, find_square, parse_input, part1, part2

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

SUBROUTINES = {
    225: "apply       -- call the function at [rb+1] with args rb+2..rb+4 (patches its own jump)",
    259: "abs         -- rb[1] * (sign of rb[1]); a no-op after reject_negative",
    282: "reject_neg  -- a negative coordinate outputs 0 and halts the drone",
    303: "mul3        -- a*b*c, obfuscated as sort-then-expand recursion",
}

SYMBOLS = {221: "X", 222: "Y", 223: "quad", 224: "tmp"}


# ------------------------------------------------------- pass 1: disassembly


def operand(mem: list[int], addr: int, index: int) -> str:
    raw = mem[addr + index]
    mode = (mem[addr] // 10 ** (index + 1)) % 10
    if mode == 1:
        return f"#{raw}"
    if mode == 2:
        return f"rb[{raw:+d}]"
    return f"[{raw}]" + (f"={SYMBOLS[raw]}" if raw in SYMBOLS else "")


def decode(mem: list[int], addr: int) -> tuple[str, int, int]:
    """(rendered instruction, opcode, length) at `addr`; raises off the rails."""
    op = mem[addr] % 100
    if op not in OPS:
        raise ValueError(f"cell {addr} is not an instruction: {mem[addr]}")
    name, count = OPS[op]
    args = " ".join(operand(mem, addr, i) for i in range(1, count + 1))
    return (f"{name:4}{' ' + args if args else ''}", op, count + 1)


def listing(mem: list[int]) -> dict[int, str]:
    """The whole file decoded linearly. The only non-code cells are the four
    variables at 221-224, wedged between the main routine and the
    subroutines; everything else is straight-line instructions."""
    out: dict[int, str] = {}
    addr = 0
    while addr < len(mem):
        if addr in SYMBOLS:
            out[addr] = f".var {SYMBOLS[addr]} = {mem[addr]}"
            addr += 1
            continue
        text, _, length = decode(mem, addr)
        out[addr] = text
        addr += length
    return out


def pass1(mem: list[int]) -> dict[int, str]:
    asm = listing(mem)
    variables = sum(1 for text in asm.values() if text.startswith(".var"))
    print(
        f"pass 1: {len(mem)} cells decode as {len(asm) - variables} instructions"
        f" + {variables} variable cells (221-224); no other data regions"
    )
    for addr, text in asm.items():
        note = SUBROUTINES.get(addr)
        if note:
            print(f"      ---- {addr}: {note}")
        print(f"      {addr:5}  {text}")
    return asm


# -------------------------------------------------- pass 2: the constants


def imm_imm_store(mem: list[int], addr: int) -> tuple[int, int] | None:
    """If `addr` holds `add/mul #a #b -> rb[+k]`, return (k, computed value)."""
    op = mem[addr] % 100
    modes = [(mem[addr] // 10 ** (i + 1)) % 10 for i in (1, 2, 3)]
    if op not in (1, 2) or modes[0] != 1 or modes[1] != 1 or modes[2] != 2:
        return None
    a, b, k = mem[addr + 1], mem[addr + 2], mem[addr + 3]
    return k, (a + b if op == 1 else a * b)


def recover_constants(mem: list[int]) -> tuple[int, int, int]:
    """(A, B, C) of the predicate |A*x^2 - B*y^2| <= C*x*y.

    The main routine stores an immediate into rb[+2] exactly four times --
    the three constants plus one decoy (the trampoline's own address, fed to
    a pointless apply(apply(apply(abs)))) chain). Each store is classified by
    the jump that consumes it: A and B feed direct calls to mul3 (the x^2 and
    y^2 terms, in that skeleton order), C feeds the indirect call that
    reaches mul3 through the trampoline, and the decoy feeds a direct call
    to the trampoline itself. Anything else refuses loudly.
    """
    main_end = min(SYMBOLS)  # main's `hlt` sits right before the variable cells
    stores: list[tuple[int, int]] = []  # (address, value) of rb[+2] immediates
    addr = 0
    while addr < main_end:
        _, _op, length = decode(mem, addr)
        hit = imm_imm_store(mem, addr)
        if hit and hit[0] == 2:
            stores.append((addr, hit[1]))
        addr += length

    def consuming_jump(store_addr: int) -> tuple[int, int]:
        """(opcode-derived kind, target) of the next jump after `store_addr`:
        kind 0 = direct `jnz #1 #target`, kind 1 = indirect `jnz #1 [cell]`."""
        addr = store_addr
        while addr < main_end:
            text, op, length = decode(mem, addr)
            if op in (5, 6):
                mode2 = (mem[addr] // 1000) % 10
                target_raw = mem[addr + 2]
                if mode2 == 1:
                    return 0, target_raw
                if mode2 == 0:
                    return 1, mem[target_raw]
                raise ValueError(f"unclassifiable jump at {addr}: {text}")
            addr += length
        raise ValueError(f"no jump consumes the store at {store_addr}")

    direct_mul3, via_trampoline, decoys = [], [], []
    for store_addr, value in stores:
        kind, target = consuming_jump(store_addr)
        if kind == 0 and target == 303:
            direct_mul3.append(value)
        elif kind == 1 and target == 225:
            via_trampoline.append(value)
        elif kind == 0 and target == 225 and value == 225:
            decoys.append(value)
        else:
            raise ValueError(f"unexpected rb[+2] store at {store_addr}: {value} -> {target}")
    if len(direct_mul3) != 2 or len(via_trampoline) != 1 or len(decoys) != 1:
        raise ValueError(f"skeleton mismatch: {direct_mul3=} {via_trampoline=} {decoys=}")
    a, b = direct_mul3
    return a, b, via_trampoline[0]


def pass2(mem: list[int]) -> tuple[int, int, int]:
    a, b, c = recover_constants(mem)
    print(f"pass 2: the drone answers  |{a}*x^2 - {b}*y^2| <= {c}*x*y")
    assert mem[23] == 1, "the mined literal (the input instruction's operand) should be 1"
    print("      the literal 1 is mined from cell 23 -- the operand of `in rb[+1]` itself")
    disc = c * c + 4 * a * b
    assert isqrt(disc) ** 2 != disc, f"disc {disc} is a perfect square: rays hit the lattice"
    print(
        f"      disc = C^2 + 4AB = {disc} (isqrt {isqrt(disc)}: not a perfect square,"
        " so the rays pass through no lattice point and <= never ties)"
    )
    return a, b, c


# ----------------------------------------------- pass 3: formula vs machine


def formula_probe(a: int, b: int, c: int):
    return lambda x, y: abs(a * x * x - b * y * y) <= c * x * y


def pass3(mem: list[int], a: int, b: int, c: int) -> None:
    vm, closed = beam_probe(mem), formula_probe(a, b, c)
    window = [(x, y) for y in range(50) for x in range(50)]
    bands = [
        (x, y)
        for y in (500, 1000)
        for edge in (left_edge_static(a, b, c, y), right_edge_static(a, b, c, y))
        for x in range(edge - 5, edge + 6)
    ]
    disagreements = [(x, y) for x, y in window + bands if vm(x, y) != closed(x, y)]
    assert not disagreements, f"formula disagrees with the VM at {disagreements[:5]}"
    print(f"pass 3: formula == VM on the 50x50 window and {len(bands)} edge-band probes")


# ------------------------------------------------- pass 4: static answers


def left_edge_static(a: int, b: int, c: int, y: int) -> int:
    """Smallest x with A*x^2 + C*x*y - B*y^2 >= 0: the beam's left ray,
    x = y*(sqrt(disc) - C) / 2A, rounded up -- isqrt gives the floor of
    y*sqrt(disc), and the fix-up loop absorbs the floor's slack exactly."""
    x = max(0, (isqrt((c * c + 4 * a * b) * y * y) - c * y) // (2 * a))
    while a * x * x + c * x * y - b * y * y < 0:
        x += 1
    while x > 0 and a * (x - 1) * (x - 1) + c * (x - 1) * y - b * y * y >= 0:
        x -= 1
    return x


def right_edge_static(a: int, b: int, c: int, y: int) -> int:
    """Largest x with A*x^2 - C*x*y - B*y^2 <= 0: the right ray, rounded down.
    Can undershoot the left edge (rows 1-3 here), which encodes 'row empty'."""
    x = max(0, (isqrt((c * c + 4 * a * b) * y * y) + c * y) // (2 * a))
    while a * x * x - c * x * y - b * y * y <= 0:
        x += 1
    return x - 1


def static_part1(a: int, b: int, c: int, size: int = 50) -> int:
    total = 0
    for y in range(size):
        lo = left_edge_static(a, b, c, y)
        hi = min(right_edge_static(a, b, c, y), size - 1)
        total += max(0, hi - lo + 1)
    return total


def static_part2(a: int, b: int, c: int, size: int = 100) -> int:
    """The same walk as day19.find_square, but each row costs O(1) arithmetic
    instead of VM probes: a square with its bottom-left corner on the left
    edge fits as soon as the top row still reaches size cells to the right."""
    y = size - 1
    while left_edge_static(a, b, c, y) + size - 1 > right_edge_static(a, b, c, y - size + 1):
        y += 1
    return 10000 * left_edge_static(a, b, c, y) + (y - size + 1)


def pass4(a: int, b: int, c: int) -> tuple[int, int]:
    one, two = static_part1(a, b, c), static_part2(a, b, c)
    print(f"pass 4: static part 1 = {one}, static part 2 = {two} (no VM, pure isqrt)")
    return one, two


def pass5(mem: list[int], one: int, two: int) -> None:
    live_one, live_two = part1(list(mem)), part2(list(mem))
    assert (one, two) == (live_one, live_two), f"{(one, two)} != {(live_one, live_two)}"
    print(f"pass 5: the live machine agrees: part 1 = {live_one}, part 2 = {live_two}")


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else Path(__file__).resolve().parent.parent / "inputs" / "day19.txt"
    mem = parse_input(path.read_text())

    pass1(mem)
    a, b, c = pass2(mem)
    pass3(mem, a, b, c)
    one, two = pass4(a, b, c)
    pass5(mem, one, two)

    probe = beam_probe(mem)
    assert count_beam(probe, 50) == one
    x, y = find_square(probe, 100)
    assert 10000 * x + y == two


if __name__ == "__main__":
    main()
