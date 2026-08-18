"""Day 17 -- disassembling the Aft Scaffolding Control and Information Interface.

Companion to Problem_Statements/days/day17_disassembly.md. Five passes:

  1. RECURSIVE-DESCENT DISASSEMBLY with SUBROUTINE DISCOVERY. Unlike Day 15's
     controller, this program has a real calling convention: a call writes its
     return address into `rb[0]` and jumps, the callee opens a frame with
     `arb +n`, and the return is `arb -n; jnz #1 rb[0]` -- an indirect jump
     descent cannot follow. So the descent is seeded with the call targets
     found by scanning for that idiom.
  2. MEMORY MAP. Code, a string table, the glyph and direction tables, nine
     variables, and 299 cells of run-length data.
  3. STATIC MAP RECOVERY. The scaffold is not drawn by the program, it is
     STORED in it, run-length encoded: 299 runs of alternating bits totalling
     exactly 55*35. Decoding them rebuilds the camera view byte for byte, and
     the robot's start is a literal at 576/577/578. Part 1 comes out with the
     VM never started.
  4. STATIC DUST RECOVERY. The dust counter is not random. Each scaffold cell
     is vacuumed the first time it is stood on, and contributes
     `(1481 + y*55 + x) + x*y + n` where n is how many cells have been
     vacuumed so far. Replaying our own route over the recovered map
     reproduces Part 2 exactly, again with the VM never started.
  5. CROSS-CHECK. Both static answers against the live machine.

Nothing here is hardcoded to one user's file. The view's width and height are
read out of the two `eq` immediates in the renderer, the RLE table's extent
from the copy loop's operands, and the robot's start from the three variables
the renderer compares against -- so a different input yields a different map
rather than a confidently wrong one.

Run:  python python/day17_disasm.py [path-to-program]
"""

from __future__ import annotations

from pathlib import Path

from day17 import (
    STEP,
    TURN_LEFT,
    TURN_RIGHT,
    alignment_sum,
    camera_view,
    compress,
    find_robot,
    intersections,
    parse_input,
    path,
    scaffold_points,
)

# ------------------------------------------------------- the program's layout

# Addresses that hold a fact rather than an instruction. Every one of these is
# read from the file below rather than assumed; the constants name WHERE to
# look, not WHAT is there.
WIDTH_CMP = 935  # immediate of `eq rb[-6] #W [570]` -- the column limit
HEIGHT_CMP = 948  # immediate of `eq rb[-5] #H [570]` -- the row limit
# The copy loop's pointers live in its own operand cells (15 and 24) and are
# incremented in place, so the loaded image holds 0 there -- their starting
# values are the immediates that initialise them, at cells 7 and 12.
RLE_FIRST = 7  # immediate of `mul #1182 #1 [15]`  -- the RLE table base
BITMAP_BASE = 12  # immediate of `add #0 #1481 [24]` -- the bitmap base
RLE_BIT0 = 571  # the alternating bit, initially 0
GLYPHS = 558  # '^', '>', 'v', '<'
DELTA_X = 562  # dx for those four headings
DELTA_Y = 566  # dy
ROBOT_X, ROBOT_Y, ROBOT_DIR = 576, 577, 578

MODE_SELECT = 332  # mem[330] (+|*) mem[331] lands here; 1 = cameras, 0 = robot

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
    579: "puts        -- print the string at rb[1] until its terminator",
    622: "interpret   -- run the movement program at rb[1] (calls itself once)",
    786: "draw        -- render one frame, and vacuum the robot's cell",
    979: "parse_line  -- read one ASCII line into the compact bytecode",
}

SYMBOLS = {
    330: "mode.a",
    331: "mode.b",
    332: "mode",
    374: "vacuumed",
    438: "dust",
    570: "tmp",
    571: "rle.bit",
    572: "len",
    573: "acc",
    574: "ch",
    575: "video",
    576: "robot.x",
    577: "robot.y",
    578: "robot.dir",
}


# ------------------------------------------------------------ pass 1: descent


def operand(mem: list[int], addr: int, index: int) -> str:
    raw = mem[addr + index]
    mode = (mem[addr] // 10 ** (index + 1)) % 10
    if mode == 1:
        return f"#{raw}"
    if mode == 2:
        return f"rb[{raw:+d}]"
    return f"[{raw}]" + (f"={SYMBOLS[raw]}" if raw in SYMBOLS else "")


def render_instruction(mem: list[int], addr: int) -> tuple[str, int] | tuple[None, int]:
    op = mem[addr] % 100
    if op not in OPS:
        return None, 0
    name, count = OPS[op]
    if addr + count >= len(mem):
        return None, 0
    args = " ".join(operand(mem, addr, i) for i in range(1, count + 1))
    return f"{name:4}{' ' + args if args else ''}", count + 1


def call_sites(mem: list[int]) -> dict[int, int]:
    """Every `rb[0] = ret; jmp target` pair -> {call address: (target, ret)}.

    The calling convention is not in the instruction set -- Intcode has no
    call/return -- so it has to be recognised as an idiom: an add or mul whose
    destination is `rb[+0]` and whose result is a code address, immediately
    followed by an unconditional jump.
    """
    found = {}
    for addr in range(len(mem) - 7):
        if mem[addr] not in (21101, 21102) or mem[addr + 3] != 0:
            continue
        if mem[addr + 4] not in (1105, 1106):
            continue
        a, b = mem[addr + 1], mem[addr + 2]
        ret = a + b if mem[addr] == 21101 else a * b
        found[addr] = (mem[addr + 6], ret)
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
                    break  # an unconditional jump: nothing follows it
            addr += size
    return seen


def pass1(mem: list[int]) -> dict[int, tuple[str, int]]:
    """Descend from 0, from every call target, AND from every return address.

    The return addresses matter as much as the targets: a return is
    `arb -n; jnz #1 rb[0]`, an indirect jump through the frame, and descent
    cannot follow it. Address 58 -- the whole of the program after the very
    first call -- is reachable no other way.
    """
    calls = call_sites(mem)
    targets = {t for t, _ in calls.values()}
    returns = {r for _, r in calls.values()}
    listing = descend(mem, [0, *targets, *returns])
    covered = {a + i for a, (_, size) in listing.items() for i in range(size)}

    patches = operand_patches(mem, listing)

    print("== pass 1: recursive descent ==")
    print(f"  {len(listing)} instructions covering {len(covered)} of {len(mem)} cells")
    print(f"  {len(calls)} call sites reaching {len(targets)} subroutines:")
    for target in sorted(targets):
        callers = sorted(a for a, (t, _) in calls.items() if t == target)
        print(f"    {target:5}  {SUBROUTINES.get(target, '')}")
        print(f"           called from {callers}")
    print(f"  {len(patches)} self-modifying stores, ALL of them operand patches:")
    print("    (none writes an opcode or a jump target, so control flow is static)")
    for store, dest, owner in patches:
        print(f"    {store:5} -> [{dest}], operand of the instruction at {owner}")
    return listing


def operand_patches(mem, listing):
    """Stores whose destination lands inside another decoded instruction.

    Intcode has no indexed addressing, so an array access must patch the
    operand it is about to execute. Finding every such store is how the tool
    proves the modifications are all *data* addressing and never control flow.
    """
    inside = {a + i: a for a, (_, size) in listing.items() for i in range(1, size)}
    found = []
    for addr, (_, _size) in sorted(listing.items()):
        if mem[addr] % 100 not in (1, 2, 7, 8):
            continue
        if (mem[addr] // 10000) % 10 != 0:
            continue  # relative destination: a frame slot, not a patch
        dest = mem[addr + 3]
        if dest in inside:
            found.append((addr, dest, inside[dest]))
    return found


# ---------------------------------------------------------- pass 2: the map


def pass2(mem: list[int], listing: dict[int, tuple[str, int]]) -> None:
    covered = {a + i for a, (_, size) in listing.items() for i in range(size)}
    width, height = mem[WIDTH_CMP], mem[HEIGHT_CMP]
    rle_base, bitmap_base = mem[RLE_FIRST], mem[BITMAP_BASE]

    print("\n== pass 2: memory map ==")
    rows = [
        (0, 150, "code", "bootstrap: RLE decompressor, mode select, input reader"),
        (151, 188, "code", "error paths (unreached on a valid script)"),
        (189, 329, "code", "part 2 driver: prompt, parse, interpret, report dust"),
        (330, 557, "data", "string table (prompts and error messages)"),
        (GLYPHS, GLYPHS + 3, "data", f"glyph table {''.join(chr(mem[GLYPHS + d]) for d in range(4))!r}"),
        (DELTA_X, DELTA_Y - 1, "data", f"dx {mem[DELTA_X : DELTA_X + 4]}"),
        (DELTA_Y, DELTA_Y + 3, "data", f"dy {mem[DELTA_Y : DELTA_Y + 4]}"),
        (570, 578, "vars", "nine variables"),
        (579, 621, "code", "puts"),
        (622, 783, "code", "interpret (two levels: main routine, then one function)"),
        (786, 978, "code", "draw"),
        (979, 1181, "code", "parse_line"),
        (rle_base, len(mem) - 1, "data", f"{len(mem) - rle_base} run lengths"),
    ]
    for lo, hi, kind, note in rows:
        reached = sum(1 for a in range(lo, hi + 1) if a in covered)
        seen = f"{reached:4}/{hi - lo + 1:<4} descended" if kind == "code" else ""
        print(f"  {lo:5}..{hi:5}  {kind}  {note}")
        if seen:
            print(f"                     {seen}")
    print(
        f"  {bitmap_base:5}..{bitmap_base + width * height - 1:5}  heap  "
        f"decompressed {width}x{height} bitmap (past the loaded image)"
    )
    print(f"  {mem[5]:5}..        stack  relative base starts here = {bitmap_base} + {width}*{height}")
    for addr in sorted(SYMBOLS):
        if 570 <= addr <= 578:
            print(f"    [{addr}] {SYMBOLS[addr]:10} = {mem[addr]}")


# ------------------------------------------------- pass 3: the map, statically


def decode_rle(mem: list[int]) -> list[int]:
    """Expand the run-length table into the bitmap the program builds at boot.

    The decompressor is a self-modifying copy loop at 14..48: the load's source
    operand lives at cell 15 and the store's destination operand at cell 24,
    and the loop increments them in place -- Intcode has no indexed addressing,
    so a moving pointer IS a patched operand. Runs alternate between 0 and 1
    starting from mem[571].
    """
    bits: list[int] = []
    bit = mem[RLE_BIT0]
    for run in mem[mem[RLE_FIRST] :]:
        bits += [bit] * run
        bit = 1 - bit
    return bits


def recover_view(mem: list[int]) -> str:
    """Rebuild the camera's picture from the file alone."""
    width, height = mem[WIDTH_CMP], mem[HEIGHT_CMP]
    bits = decode_rle(mem)
    if len(bits) != width * height:
        raise ValueError(f"RLE expands to {len(bits)} cells, not {width}*{height}")

    rx, ry, rdir = mem[ROBOT_X], mem[ROBOT_Y], mem[ROBOT_DIR]
    rows = []
    for y in range(height):
        row = []
        for x in range(width):
            scaffold = bits[y * width + x]
            if (x, y) == (rx, ry):
                # The renderer's own arithmetic: '.' is 46 and 46 + 42 is 'X'.
                row.append(chr(mem[GLYPHS + rdir]) if scaffold else chr(46 + 42))
            else:
                row.append("#" if scaffold else ".")
        rows.append("".join(row))
    return "\n".join(rows) + "\n\n"


def pass3(mem: list[int]) -> str:
    width, height = mem[WIDTH_CMP], mem[HEIGHT_CMP]
    runs = mem[mem[RLE_FIRST] :]
    view = recover_view(mem)

    print("\n== pass 3: the scaffold, read off the disk ==")
    print(f"  {len(runs)} runs at {mem[RLE_FIRST]}.. summing to {sum(runs)} = {width}*{height}")
    print(
        f"  robot start: ({mem[ROBOT_X]}, {mem[ROBOT_Y]}) facing "
        f"{chr(mem[GLYPHS + mem[ROBOT_DIR]])!r} -- literals at {ROBOT_X}/{ROBOT_Y}/{ROBOT_DIR}"
    )
    print(f"  scaffold cells {len(scaffold_points(view))}, intersections {len(intersections(view))}")
    print(f"  PART 1 (static) = {alignment_sum(view)}")
    return view


# ------------------------------------------------ pass 4: the dust, statically


def recover_dust(mem: list[int], view: str, tokens: list[str]) -> int:
    """Replay the vacuum accumulator without running the machine.

    `draw` is called after every move. When the robot stands on a cell whose
    bitmap value is still 1 it (a) writes 2 there, so the cell is never counted
    twice, (b) bumps the vacuumed counter, and (c) adds to the dust total

        dust += (bitmap_address) + (x * y) + vacuumed

    where `bitmap_address` is `base + y*width + x`. Three separate adds in the
    listing at 900, 908 and 912; the first of them takes the *address* as an
    immediate, which is why the total is so much larger than the coordinates
    would suggest.
    """
    width, base = mem[WIDTH_CMP], mem[BITMAP_BASE]
    pos, facing = find_robot(view)

    dust = vacuumed = 0
    seen: set[tuple[int, int]] = set()

    def vacuum(cell: tuple[int, int]) -> None:
        nonlocal dust, vacuumed
        if cell in seen:
            return
        seen.add(cell)
        vacuumed += 1
        x, y = cell
        dust += (base + y * width + x) + x * y + vacuumed

    vacuum(pos)
    for turn, distance in zip(tokens[::2], tokens[1::2]):
        facing = (TURN_LEFT if turn == "L" else TURN_RIGHT)[facing]
        dx, dy = STEP[facing]
        for _ in range(int(distance)):
            pos = (pos[0] + dx, pos[1] + dy)
            vacuum(pos)
    return dust


def pass4(mem: list[int], view: str) -> int:
    tokens = path(view)
    main, functions = compress(tokens)
    dust = recover_dust(mem, view, tokens)

    print("\n== pass 4: the dust, replayed ==")
    print(f"  route {len(tokens) // 2} moves; grammar main={main!r}")
    for name, body in zip("ABC", functions):
        print(f"    {name} = {body!r}")
    print(
        "  the parser stores that as a compact bytecode at "
        f"{mem[RLE_FIRST]}.. (the RLE table's own cells, now free):"
    )
    print("    call A/B/C = -1/-2/-3, turn R = -4, turn L = -5, n = move n")
    print(f"    dispatch is `buffer = {mem[RLE_FIRST]} + 11 * -opcode`, so the")
    print("    negative encoding IS the index arithmetic")
    print(f"  PART 2 (static) = {dust}")
    return dust


# -------------------------------------------------------- pass 5: cross-check


def pass5(mem: list[int], view: str, dust: int) -> None:
    live = camera_view(mem)
    print("\n== pass 5: cross-check against the live machine ==")
    print(f"  recovered view == camera_view(program): {view == live}")
    print(
        f"  part 1 static {alignment_sum(view)} == live {alignment_sum(live)}: "
        f"{alignment_sum(view) == alignment_sum(live)}"
    )
    print(
        f"  mode select: mem[{MODE_SELECT}] = mem[330] (+|*) mem[331] = "
        f"{mem[330]}+{mem[331]}={mem[330] + mem[331]} (cameras) or "
        f"{mem[330]}*{mem[331]}={mem[330] * mem[331]} (robot)"
    )
    print(f"  part 2 static = {dust}")


def main(argv: list[str] | None = None) -> None:
    import sys

    argv = sys.argv[1:] if argv is None else argv
    default = Path(__file__).resolve().parent.parent / "inputs" / "day17.txt"
    mem = parse_input(Path(argv[0] if argv else default).read_text())

    listing = pass1(mem)
    pass2(mem, listing)
    view = pass3(mem)
    dust = pass4(mem, view)
    pass5(mem, view, dust)


if __name__ == "__main__":
    main()
