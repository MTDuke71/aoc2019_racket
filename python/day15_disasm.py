"""Day 15 -- disassembling the repair droid's controller.

Companion to Problem_Statements/days/day15_disassembly.md. Four passes:

  1. RECURSIVE-DESCENT DISASSEMBLY. 70 instructions filling addresses 0-251
     with no gaps and no overlaps, and that is the entire program --
     everything from 252 up is data. The one self-modifying store patches an
     *operand*, never control flow, so descent is complete here (unlike
     Day 11, which needed a dynamic trace).
  2. MEMORY MAP. Code 0-251, a 39x20 wall table at 252-1031, thirteen
     variables at 1032-1044.
  3. STATIC MAZE RECOVERY. The maze is not drawn by the program, it is
     *stored* in it: cells at odd/odd, pillars at even/even, and one table
     entry per edge whose wall bit is hidden as `value < T`. Both puzzle
     answers come out of the file with the VM never started.
  4. CROSS-CHECK. The recovered maze is compared cell-for-cell against the
     map python/day15.py's droid walks.

Nothing here is hardcoded to one user's file. `T` is not a constant of the
puzzle -- it is generated per input, and it is read back out of the compare
instruction at 210 (`wall_threshold`), exactly as the oxygen's coordinates are
read out of 146 and 153. On inputs/day15.txt it is 37; on inputs/day15_alt.txt,
a second user's program, it is 35. Those two files differ in forty cells of the
code region and only THREE of them mean anything -- see
test_day15.py::test_only_three_code_cells_carry_meaning.

Run:  python python/day15_disasm.py [path-to-program]
"""

from __future__ import annotations

from pathlib import Path

from day15 import OPEN, OXYGEN, WALL, distances, explore, parse_input, render
from intcode import VM

# ------------------------------------------------------- the program's layout

CODE_END = 252  # first cell that is data, not code
TABLE_BASE = 252  # 39 x 20 wall table
TABLE_STRIDE = 39
TABLE_CELLS = 780
COMPARE_ADDR = 210  # the `table[idx] < T` instruction
THRESHOLD_ADDR = 212  # ... and T, its immediate operand
ARENA = 39  # legal coordinates are 1..39 on both axes

# Addresses 1032-1044, named from what the code does with them.
SYMBOLS = {
    1032: "tmp",
    1033: "cmd",
    1034: "x",
    1035: "y",
    1036: "xpar",
    1037: "row",
    1038: "ypar",
    1039: "nx",
    1040: "ny",
    1041: "nxpar",
    1042: "nrow",
    1043: "nypar",
    1044: "status",
}

# Instruction table: opcode -> (mnemonic, operand count).
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
    """Render one operand in the mode its instruction's digits select."""
    mode = (mem[addr] // 10 ** (index + 1)) % 10
    raw = mem[addr + index]
    if mode == 1:
        return f"#{raw}"
    if mode == 2:
        return f"rel[{raw}]"
    return SYMBOLS.get(raw, f"mem[{raw}]")


def render_instruction(mem: list[int], addr: int) -> tuple[str, int, list[int]]:
    """Return (text, width, successor addresses) for the instruction at `addr`."""
    op = mem[addr] % 100
    name, count = OPS[op]
    width = count + 1
    args = [operand(mem, addr, i) for i in range(1, count + 1)]
    fall = [addr + width]

    if name == "add":
        text = f"{args[2]} = {args[0]} + {args[1]}"
    elif name == "mul":
        text = f"{args[2]} = {args[0]} * {args[1]}"
    elif name == "in":
        text = f"{args[0]} = INPUT"
    elif name == "out":
        text = f"OUTPUT {args[0]}"
    elif name == "lt":
        text = f"{args[2]} = ({args[0]} < {args[1]})"
    elif name == "eq":
        text = f"{args[2]} = ({args[0]} == {args[1]})"
    elif name == "arb":
        text = f"rel_base += {args[0]}"
    elif name == "hlt":
        text, fall = "HALT", []
    elif name in ("jnz", "jz"):
        test = "!=" if name == "jnz" else "=="
        text = f"if {args[0]} {test} 0 goto {args[1]}"
        # Follow only statically-known targets. Every jump in this program has
        # an immediate destination, which is why descent recovers all of it.
        if args[1].startswith("#"):
            target = int(args[1][1:])
            fall = [addr + width, target]
            if args[0].startswith("#"):  # unconditional: #1 != 0 / #0 == 0
                taken = (args[0] != "#0") if name == "jnz" else (args[0] == "#0")
                fall = [target] if taken else [addr + width]
    else:  # pragma: no cover - OPS has no other entries
        raise ValueError(name)

    return text, width, fall


def descend(mem: list[int], entry: int = 0) -> dict[int, tuple[str, int]]:
    """Control-flow-following disassembly from `entry`. Returns addr -> (text, width)."""
    seen: dict[int, tuple[str, int]] = {}
    pending = [entry]
    while pending:
        addr = pending.pop()
        if addr in seen or addr >= CODE_END:
            continue
        text, width, successors = render_instruction(mem, addr)
        seen[addr] = (text, width)
        pending.extend(successors)
    return seen


ANNOTATIONS = {
    0: "read a movement command",
    2: "--- dispatch: 1 north, 2 south, 3 west, 4 east, anything else halts",
    30: "an invalid command is fatal -- the droid program has no other exit",
    31: "--- NORTH: y-1, flip ypar, borrow a cell-row when leaving an even row",
    58: "--- SOUTH: y+1, flip ypar, carry a cell-row when leaving an odd row",
    81: "--- WEST: x-1, flip xpar; y untouched, so row is untouched",
    104: "--- EAST: x+1, flip xpar; y untouched, so row is untouched",
    124: "--- bounds: coordinate 0 or 40 on either axis is the arena border",
    144: "--- is the target the oxygen system? THE ANSWER IS A LITERAL PAIR",
    165: "odd x AND odd y -> a maze cell, always open",
    179: "even x AND even y -> a pillar, always wall",
    186: "one odd, one even -> an EDGE; index the wall table",
    206: "SELF-MODIFYING STORE: patch the operand of the load at 210",
    210: "the patched load. `mem[0]` is a placeholder; 252+idx is written in",
    217: "wall",
    224: "--- commit the move, or don't",
    247: "reply, then loop forever",
}


def pass1(mem: list[int]) -> dict[int, tuple[str, int]]:
    code = descend(mem)
    print("=== PASS 1 -- RECURSIVE-DESCENT DISASSEMBLY ===\n")
    print(" addr | raw                  | operation")
    print("------+----------------------+" + "-" * 52)
    for addr in sorted(code):
        text, width = code[addr]
        if addr in ANNOTATIONS:
            note = ANNOTATIONS[addr]
            print(
                f"      |                      |   ; {note}"
                if not note.startswith("---")
                else f"\n{note[4:]}"
            )
        raw = " ".join(str(v) for v in mem[addr : addr + width])
        print(f" {addr:>4} | {raw:<20} | {text}")
    decoded = sum(w for _, w in code.values())
    last = max(code)
    end = last + code[last][1]
    print(f"\n{len(code)} instructions covering {decoded} cells, addresses 0-{end - 1}.")
    assert decoded == end, "decoded cells overlap or leave a gap"
    print("No gaps and no overlaps: the code region is exactly 0-251, and every cell")
    print(f"from {CODE_END} up is data. Descent is COMPLETE -- every jump in this program")
    print("has an immediate target, and the one self-modifying store patches an")
    print("operand (address 211), never a jump.")
    return code


# --------------------------------------------------------- pass 2: memory map


def pass2(mem: list[int]) -> None:
    print("\n\n=== PASS 2 -- MEMORY MAP ===\n")
    code = descend(mem)
    rows = [
        ("0-251", "code", f"{len(code)} instructions: dispatch, four move blocks, the tile test"),
        (
            f"{TABLE_BASE}-{TABLE_BASE + TABLE_CELLS - 1}",
            "wall table",
            f"{TABLE_STRIDE} x {TABLE_CELLS // TABLE_STRIDE}; entry < {wall_threshold(mem)} means passage",
        ),
        ("1032-1044", "variables", ", ".join(f"{a}={SYMBOLS[a]}" for a in sorted(SYMBOLS))),
    ]
    for span, kind, note in rows:
        print(f"  {span:<11} {kind:<11} {note}")
    print("\n  initial state:")
    for addr in (1034, 1035, 1036, 1037, 1038):
        print(f"    {SYMBOLS[addr]:<7} = {mem[addr]}")
    print(f"\n  The droid starts at ({mem[1034]}, {mem[1035]}) in the program's own")
    print("  coordinates, which is why every map this repo prints is centred there.")


# ------------------------------------------------- pass 3: static maze recovery


def wall_threshold(mem: list[int]) -> int:
    """T, read out of the instruction that uses it rather than hardcoded.

        210 | 1007 <patched> T 1044 | status = (mem[<patched>] < #T)

    `1007` is less-than with operand 1 in position mode -- the address the store
    at 206 patches in -- and operand 2 immediate. That immediate is T, and it is
    generated per input: 37 in inputs/day15.txt, 35 in inputs/day15_alt.txt. The
    opcode and the destination are checked first, so a file that does not have
    this instruction here fails loudly instead of yielding a plausible integer
    and a silently wrong maze.
    """
    opcode, destination = mem[COMPARE_ADDR], mem[COMPARE_ADDR + 3]
    if (opcode, destination) != (1007, 1044):
        raise ValueError(
            f"address {COMPARE_ADDR} is not the wall compare: {mem[COMPARE_ADDR : COMPARE_ADDR + 4]}"
        )
    return mem[THRESHOLD_ADDR]


def is_open(mem: list[int], x: int, y: int, threshold: int) -> bool:
    """Decide one cell WITHOUT running the machine -- the code at 124..214, read.

    Three cases, exactly as the program branches:
      * outside 1..39 on either axis        -> arena border          (addr 124)
      * odd x and odd y                     -> a maze cell, open     (addr 165)
      * even x and even y                   -> a pillar, wall        (addr 179)
      * otherwise it is an edge between two cells, and the wall bit is
        `table[((y - 1) // 2) * 39 + x - 1] < T`                     (addr 186)

    `threshold` is passed in rather than looked up per cell: `recover_maze`
    calls this 1681 times and T is a property of the file, not of the cell.
    """
    if not (1 <= x <= ARENA and 1 <= y <= ARENA):
        return False
    odd_x, odd_y = x & 1, y & 1
    if odd_x and odd_y:
        return True
    if not odd_x and not odd_y:
        return False
    return mem[TABLE_BASE + ((y - 1) // 2) * TABLE_STRIDE + x - 1] < threshold


def oxygen_literal(mem: list[int]) -> tuple[int, int]:
    """The oxygen system's coordinates, read out of the compare instructions at
    144 (`nx == X`) and 151 (`ny == Y`) -- (37, 39) on inputs/day15.txt."""
    return mem[146], mem[153]


def recover_maze(mem: list[int]) -> tuple[dict[tuple[int, int], int], tuple[int, int]]:
    """The whole maze, straight off the disk, in the droid's start-relative
    coordinates so it can be compared with `day15.explore`'s output."""
    start = (mem[1034], mem[1035])
    oxygen = oxygen_literal(mem)
    threshold = wall_threshold(mem)
    grid: dict[tuple[int, int], int] = {}
    for y in range(ARENA + 2):
        for x in range(ARENA + 2):
            here = (x - start[0], y - start[1])
            if is_open(mem, x, y, threshold):
                grid[here] = OXYGEN if (x, y) == oxygen else OPEN
            else:
                grid[here] = WALL
    return grid, (oxygen[0] - start[0], oxygen[1] - start[1])


def pass3(mem: list[int]) -> tuple[dict[tuple[int, int], int], tuple[int, int]]:
    print("\n\n=== PASS 3 -- STATIC MAZE RECOVERY (the VM is never started) ===\n")
    grid, oxygen = recover_maze(mem)
    threshold = wall_threshold(mem)
    open_cells = sum(1 for tile in grid.values() if tile != WALL)
    cells = sum(1 for x in range(1, ARENA + 1) for y in range(1, ARENA + 1) if x & 1 and y & 1)
    passages = sum(1 for v in mem[TABLE_BASE : TABLE_BASE + TABLE_CELLS] if v < threshold)

    print(f"  wall threshold, read off address {THRESHOLD_ADDR}     {threshold}")
    print(f"  maze cells (odd x, odd y)          {cells}")
    print(f"  table entries < {threshold} (open edges)      {passages}")
    print(f"  open squares = cells + open edges   {open_cells}")
    print(f"  |E| = |V| - 1 ?                     {passages == cells - 1}  <- a SPANNING TREE")
    print(f"\n  oxygen system, read off addresses 146 and 153: {oxygen_literal(mem)}")

    print(render(grid))
    print(f"\n  STATIC part 1 = {distances(grid, (0, 0))[oxygen]}")
    print(f"  STATIC part 2 = {max(distances(grid, oxygen).values())}")
    return grid, oxygen


# ------------------------------------------------------------ pass 4: check it


def pass4(
    mem: list[int],
    static: dict[tuple[int, int], int],
    oxygen: tuple[int, int],
    locked: tuple[int, int] | None = None,
) -> None:
    print("\n\n=== PASS 4 -- CROSS-CHECK AGAINST THE DROID'S OWN WALK ===\n")
    walked, walked_oxygen = explore(VM(list(mem)))

    static_open = {p for p, t in static.items() if t != WALL}
    walked_open = {p for p, t in walked.items() if t != WALL}
    print(f"  open squares  static {len(static_open)}   walked {len(walked_open)}")
    print(f"  identical set of open squares:  {static_open == walked_open}")
    print(f"  oxygen        static {oxygen}   walked {walked_oxygen}")

    answers = (distances(static, (0, 0))[oxygen], max(distances(static, oxygen).values()))
    print(f"  answers       static {answers}   locked {locked or '-- none on file'}")
    assert static_open == walked_open, "static recovery disagrees with the walk"
    assert oxygen == walked_oxygen
    if locked is not None:
        assert answers == locked
    print("\n  Both agree. The 66 ms walk was never necessary on this input --")
    print("  though nothing in the puzzle says the maze has to be stored as data.")


# Answers verified on adventofcode.com, keyed by input file. A second user's
# program is carried here to prove the disassembly is not fitted to one file;
# its answers are not this account's to submit, so they are deliberately
# absent. Pass 4 still cross-checks the static recovery against the walk, and
# that comparison needs no oracle at all.
LOCKED = {"day15.txt": (254, 268)}


def main(argv: list[str] | None = None) -> None:
    inputs = Path(__file__).resolve().parent.parent / "inputs"
    path = Path(argv[0]) if argv else inputs / "day15.txt"
    mem = parse_input(path.read_text())
    print(f"Program: {len(mem)} cells from {path.name}\n")
    pass1(mem)
    pass2(mem)
    static, oxygen = pass3(mem)
    pass4(mem, static, oxygen, LOCKED.get(path.name))


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
