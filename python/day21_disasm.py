"""Day 21 -- disassembling the springdroid console.

Companion to Problem_Statements/days/day21_disassembly.md. Six passes:

  1. RECURSIVE-DESCENT DISASSEMBLY with call discovery. Day 17's calling
     convention again (return address into `rb[0]`, `arb`-framed callees,
     `jnz #1 rb[0]` returns) -- plus one INDIRECT call: the bit-emitter
     recursion calls its per-digit callback through cell 1912, which the
     caller patches at run time (Day 19's trampoline move, aimed at a
     callback instead of a decoy).
  2. MEMORY MAP. Code, a 32-cell tile window, ten variables, the HULL as
     9-bit-packed cells, the 15 x 3 springscript store whose size IS the
     memory limit, a length-prefixed string table, and a one-char pushback
     buffer.
  3. STATIC HULL RECOVERY. The hull is not generated, it is STORED: two
     zero-terminated courses of 9-bit chunks (7 for WALK, 153 more for RUN).
     Each chunk is decoded MSB-first into window positions 10..18; positions
     0..9 and 19..31 are permanent ground, and the droid crosses each window
     from column 5 to column 21 -- so real hazards come quantised into 9-tile
     bursts separated by guaranteed footing.
  4. STATIC DAMAGE. The report is an arithmetic checksum over the holes:
     every hole tile the droid sails over adds `addr * value * column`,
     where addr is the chunk's own cell address, value its 9-bit payload and
     column its window position. A surviving droid overflies every hole
     exactly once, so both answers are sums over the data cells -- the VM
     never has to start (a faithful re-implementation of the stepper verifies
     the shipping scripts actually survive each chunk).
  5. CROSS-CHECK. Both static answers against the live machine.
  6. TWO USERS' FILES. Cell diff against inputs/day21_alt.txt, with every
     differing code cell proved to be an encoding coin-flip (add/mul spelling
     of the same constant, jnz#1/jz#0 unconditional jumps, commutative
     operand swaps) by canonicalising both instruction streams -- leaving the
     hull payload cells as the ONLY semantic difference between two users'
     puzzles.

Nothing here is hardcoded to one user's file: every recovered address and
constant is read out of the instruction that uses it (`imm_value` decodes
either add/mul spelling), so the alt file yields its own hull and answers.

Run:  python python/day21_disasm.py [path-to-program]
      python python/day21_disasm.py [path] --full   (the complete listing)
"""

from __future__ import annotations

import sys
from pathlib import Path

from day21 import parse_input, part1, part2, run_script

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
    667: "emit_tiles  -- decode one hull cell into 9 tiles at [726..734]",
    697: "put_tile    -- the emitter's callback: store one bit, advance [757]",
    1263: "peekc       -- next char into [1262], WITHOUT consuming it",
    1279: "getc        -- peekc, then clear the buffer: a consuming read",
    1301: "expect      -- getc must equal rb[1] or die with the error at rb[2]",
    1337: "skip_ws     -- peek past spaces and tabs (newlines are syntax)",
    1378: "puts        -- print the length-prefixed string at rb[1]",
    1421: "die         -- newline, the error string at rb[1], newline, halt",
    1444: "add_damage  -- damage += [593] * [753] * rb[1]  (addr * cell * col)",
    1463: "run_chunk   -- fly the droid across the current window; rb[1]=render",
    1694: "eval_script -- run the stored springscript; returns J",
    1889: "in_range    -- rb[1] in [rb[2], rb[3]]? (register letters, op codes)",
    1913: "emit_bits   -- clamp negatives, patch [1912] <- rb[3], recurse",
    1954: "bits_rec    -- double the power 9 times, emit digits on the unwind",
}

SYMBOLS = {
    748: "tmp",
    749: "ch",
    750: "op",
    751: "arg1",
    752: "arg2",
    753: "cell",
    754: "damage",
    755: "running",
    756: "saw_run_sensor",
    757: "tileptr",
    920: "count",
    1262: "buf",
    1912: "emit_fn",
}

# Where the program states its own facts. Each name is the address of an
# instruction whose immediate carries the fact; `imm_value` reads it out
# robustly against the add/mul spelling flips between users' files.
PROMPT_AT = 2  # boot: rb[+1] = address of "Input instructions:\n"
HULL_BASE_AT = 588  # sim driver: [593] = first hull cell
SCRIPT_LIMIT_AT = 500  # parser: `lt [920] #15` -- the 15-instruction budget
SCRIPT_BASE_AT = 522  # parser: slot = count*3 + base
TILE_DEST_AT = 669  # emit_tiles: [757] = first tile cell (window pos 10)
CHUNK_BITS_AT = 677  # emit_tiles: rb[+2] = 9 -- digits per hull cell
WINDOW_BASE_AT = 1510  # renderer: tile address = column + base
START_COL_AT = 1465  # run_chunk: the droid enters at column 5
END_COL_AT = 1569  # run_chunk: `eq col #21` -- crossing the window


def imm_value(mem: list[int], addr: int) -> int:
    """The value an `add`/`mul` at `addr` computes from immediate operands.

    The two files spell the same constant either way (`add #0 #966` vs
    `mul #966 #1`, operands in either order), so recovery must evaluate the
    instruction rather than read a fixed operand cell.
    """
    op = mem[addr] % 100
    modes = [(mem[addr] // 10 ** (i + 1)) % 10 for i in (1, 2)]
    if op not in (1, 2) or modes != [1, 1]:
        raise ValueError(f"cell {addr} is not an imm-imm add/mul: {mem[addr]}")
    a, b = mem[addr + 1], mem[addr + 2]
    return a + b if op == 1 else a * b


def imm_operand(mem: list[int], addr: int, index: int) -> int:
    """The immediate `index`-th operand of the instruction at `addr`."""
    if (mem[addr] // 10 ** (index + 1)) % 10 != 1:
        raise ValueError(f"operand {index} at {addr} is not immediate")
    return mem[addr + index]


# ------------------------------------------------------- pass 1: the descent


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


def call_sites(mem: list[int]) -> dict[int, tuple[int, int]]:
    """Every `rb[0] = ret; jmp #target` pair -> {call address: (target, ret)}."""
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


def entry_points(mem: list[int]) -> list[int]:
    """0, every call target and return, and the one patched-in callback.

    The callback is found, not assumed: `emit_bits` stores its rb[+3]
    argument into [1912] and the recursion later jumps `jnz #1 [1912]`, so
    the target is whatever the caller loaded into rb[+3] -- read from the
    call site's own immediate."""
    calls = call_sites(mem)
    callback = imm_value(mem, 681)  # emit_tiles: rb[+3] = put_tile
    return [0, callback, *(t for t, _ in calls.values()), *(r for _, r in calls.values())]


def operand_patches(mem, listing):
    """Position-mode stores whose destination is inside another instruction.

    Intcode has no indexed addressing, so every array access here -- hull
    cells, tile window, script store, string bodies -- must patch the operand
    it is about to execute. None of them writes an opcode or a jump target
    except [1912], the declared callback pointer."""
    inside = {a + i: a for a, (_, size) in listing.items() for i in range(1, size)}
    found = []
    for addr in sorted(listing):
        if mem[addr] % 100 not in (1, 2, 7, 8):
            continue
        if (mem[addr] // 10000) % 10 != 0:
            continue
        dest = mem[addr + 3]
        if dest in inside:
            found.append((addr, dest, inside[dest]))
    return found


def pass1(mem: list[int]) -> dict[int, tuple[str, int]]:
    calls = call_sites(mem)
    listing = descend(mem, entry_points(mem))
    covered = {a + i for a, (_, size) in listing.items() for i in range(size)}
    patches = operand_patches(mem, listing)

    print("== pass 1: recursive descent ==")
    print(f"  {len(listing)} instructions covering {len(covered)} of {len(mem)} cells")
    targets = sorted({t for t, _ in calls.values()})
    print(f"  {len(calls)} call sites reaching {len(targets)} subroutines (+1 indirect):")
    for target in targets:
        callers = sorted(a for a, (t, _) in calls.items() if t == target)
        print(f"    {target:5}  {SUBROUTINES.get(target, '')}")
        print(f"           called from {callers}")
    print(f"  {len(patches)} self-modifying stores, all operand patches or [1912]:")
    for store, dest, owner in patches:
        name = f" ={SYMBOLS[dest]}" if dest in SYMBOLS else ""
        print(f"    {store:5} -> [{dest}]{name}, operand of the instruction at {owner}")
    return listing


# ---------------------------------------------------------- pass 2: the map


def string_table(mem: list[int], base: int) -> dict[int, str]:
    """The length-prefixed strings, parsed until the run of them ends."""
    out = {}
    addr = base
    while True:
        length = mem[addr]
        body = mem[addr + 1 : addr + 1 + length]
        if not (0 < length < 100 and all(9 <= v < 127 for v in body)):
            return out
        out[addr] = "".join(chr(v) for v in body)
        addr += 1 + length


def pass2(mem: list[int], listing: dict[int, tuple[str, int]]) -> None:
    covered = {a + i for a, (_, size) in listing.items() for i in range(size)}
    prompt = imm_value(mem, PROMPT_AT)
    hull = imm_value(mem, HULL_BASE_AT)
    script_base = imm_operand(mem, SCRIPT_BASE_AT, 2)
    limit = imm_operand(mem, SCRIPT_LIMIT_AT, 2)
    window = imm_operand(mem, WINDOW_BASE_AT, 2)
    tiles = imm_value(mem, TILE_DEST_AT)
    strings = string_table(mem, prompt)
    strings_end = max(strings) + len(strings[max(strings)])

    print("\n== pass 2: memory map ==")
    rows = [
        (0, 26, "code", "boot: print the prompt, start the parse loop"),
        (27, 715, "code", "parser, one arm per keyword; sim driver; emit_tiles"),
        (window, hull - 11, "data", f"32-tile window (ground, 9 decoded at {tiles}.., ground)"),
        (hull - 10, hull - 1, "vars", "ten parser/simulator variables"),
        (hull, script_base - 2, "data", "the HULL: two zero-terminated courses of 9-bit cells"),
        (script_base - 1, script_base - 1, "vars", "count -- instructions stored so far"),
        (script_base, prompt - 1, "data", f"springscript store, {limit} x 3 cells (the memory limit)"),
        (prompt, strings_end, "data", f"{len(strings)} length-prefixed strings"),
        (strings_end + 1, strings_end + 1, "vars", "buf -- one-char pushback buffer"),
        (strings_end + 2, 1911, "code", "runtime: I/O, parser helpers, stepper, interpreter"),
        (1912, 1912, "vars", "emit_fn -- the patched callback pointer"),
        (1913, len(mem) - 1, "code", "emit_bits / bits_rec"),
    ]
    for lo, hi, kind, note in rows:
        reached = sum(1 for a in range(lo, hi + 1) if a in covered)
        tail = f"  ({reached}/{hi - lo + 1} descended)" if kind == "code" else ""
        print(f"  {lo:5}..{hi:5}  {kind:5} {note}{tail}")
    for addr, text in strings.items():
        print(f"    {addr:5}  {text!r}")


# ------------------------------------------------- pass 3: the hull, statically

GROUND_LEFT = 10  # window columns 0..9 are permanent ground
GROUND_RIGHT = 13  # columns 19..31 likewise (13 cells of the file)


def recover_courses(mem: list[int]) -> list[list[tuple[int, int]]]:
    """The two zero-terminated courses as [(cell address, 9-bit value), ...]."""
    base = imm_value(mem, HULL_BASE_AT)
    courses, current, addr = [], [], base
    while len(courses) < 2:
        if mem[addr] == 0:
            courses.append(current)
            current = []
        else:
            current.append((addr, mem[addr]))
        addr += 1
    return courses


def chunk_window(value: int, bits: int = 9) -> str:
    """One hull cell as the droid's 32-column window, MSB-first at column 10."""
    hazard = "".join("#" if (value >> (bits - 1 - k)) & 1 else "." for k in range(bits))
    return "#" * GROUND_LEFT + hazard + "#" * GROUND_RIGHT


def cross_chunk(window: str, script: tuple[str, ...] | list[str], start: int = 5, end: int = 21) -> bool:
    """A faithful Python `run_chunk` (1463..1693, render stripped).

    The droid is ballistic: altitude 1 on the ground, a jump loads a
    two-tick thrust counter, each step advances one column while thrust
    climbs (+1) or gravity falls (-1), and altitude 0 over ground snaps back
    to 1 -- which makes an ordinary walking step "fall one, land". The
    script runs only when standing on ground at altitude 1; over a hole the
    droid just coasts. Altitude 0 over a hole is the death the renderer
    draws. Sensors read the window directly, so past column 18 they see the
    padding's phantom ground, exactly as the machine's do.
    """
    col, alt, thrust = start, 1, 0
    while True:
        if alt < 1:
            return False
        if col == end:
            return True
        tile = window[col] == "#"
        jump = False
        if tile and alt == 1:
            sensors = {chr(ord("A") + k): window[col + 1 + k] == "#" for k in range(9)}
            jump = run_script(script, sensors)
        if jump:
            thrust = 2
        if alt > 1 or (tile and alt == 1):
            col += 1
        if thrust:
            thrust -= 1
            alt += 1
        else:
            alt -= 1
        if alt == 0 and window[col] == "#":
            alt = 1


def pass3(mem: list[int]) -> list[list[tuple[int, int]]]:
    courses = recover_courses(mem)
    print("\n== pass 3: the hull, statically ==")
    for label, course in zip(("WALK", "RUN"), courses):
        holes = sum(chunk_window(v).count(".") for _, v in course)
        print(f"  {label}: {len(course)} chunks, {holes} holes; hazard strips:")
        strip = "".join(chunk_window(v)[GROUND_LEFT : GROUND_LEFT + 9] for _, v in course)
        for i in range(0, len(strip), 72):
            print(f"    {strip[i : i + 72]}")
    return courses


# ---------------------------------------------- pass 4: the damage, statically


def static_damage(courses: list[list[tuple[int, int]]], bits: int = 9) -> int:
    """damage = sum over hole tiles of  cell address * cell value * column.

    A surviving droid overflies every hole exactly once (motion is one
    column per step and it cannot land in one), so the checksum does not
    depend on WHICH script crosses -- only that one does."""
    total = 0
    for course in courses:
        for addr, value in course:
            for k in range(bits):
                if not (value >> (bits - 1 - k)) & 1:
                    total += addr * value * (GROUND_LEFT + k)
    return total


def static_answers(mem: list[int], walk_script, run_script_) -> tuple[int, int]:
    """Both damage totals, VM never started; the scripts' survival verified
    chunk by chunk through the faithful stepper first."""
    walk, run = recover_courses(mem)
    for label, course, script in (("WALK", walk, walk_script), ("RUN", walk + run, run_script_)):
        for addr, value in course:
            if not cross_chunk(chunk_window(value), script):
                raise ValueError(f"{label} script dies in the chunk at cell {addr} ({value})")
    return static_damage([walk]), static_damage([walk, run])


def pass4(mem: list[int]) -> tuple[int, int]:
    from day21 import PART1_SCRIPT, PART2_SCRIPT

    one, two = static_answers(mem, PART1_SCRIPT, PART2_SCRIPT)
    print("\n== pass 4: the damage, statically ==")
    print(f"  part 1 = {one}, part 2 = {two} (pure arithmetic over the data cells)")
    return one, two


def pass5(mem: list[int], one: int, two: int) -> None:
    live_one, live_two = part1(list(mem)), part2(list(mem))
    assert (one, two) == (live_one, live_two), f"{(one, two)} != {(live_one, live_two)}"
    print("\n== pass 5: the live machine agrees ==")
    print(f"  part 1 = {live_one}, part 2 = {live_two}")


# --------------------------------------------- pass 6: two users' files


def canonical(mem: list[int], addr: int, patches: dict[int, int]) -> tuple:
    """The instruction at `addr` reduced past the encoders' coin-flips.

    Four flips appear between the files: the same immediate spelled
    `add #a #b` or `mul #a #b`, commutative operands in either order,
    unconditional jumps spelled `jnz #1` or `jz #0`, and -- consequence of
    the operand swaps -- a PATCHED operand cell riding at a different offset
    inside its instruction (`[1766]` vs `[1767]`, both "the operand of the
    fetch at 1765"). `patches` maps operand cell -> owning instruction, so a
    store into one canonicalises as a patch of the owner, not an address.
    Copies (`add #0 x` / `mul #1 x`) reduce to the operand itself, which
    also absorbs the spelling of constant loads."""
    op = mem[addr] % 100
    name, count = OPS[op]
    ops = []
    for i in range(1, count + 1):
        mode = (mem[addr] // 10 ** (i + 1)) % 10
        value = mem[addr + i]
        if mode == 0 and value in patches:
            ops.append((3, patches[value]))  # pseudo-mode 3: "operand of instruction N"
        else:
            ops.append((mode, value))

    if op in (1, 2):
        (m1, v1), (m2, v2), dest = ops
        if m1 == m2 == 1:
            return ("load", v1 + v2 if op == 1 else v1 * v2, dest)
        identity = (1, 0) if op == 1 else (1, 1)
        if ops[0] == identity:
            return ("copy", ops[1], dest)
        if ops[1] == identity:
            return ("copy", ops[0], dest)
        return (name, *sorted(ops[:2]), dest)
    if op == 8:  # eq is commutative too
        return (name, *sorted(ops[:2]), ops[2])
    if op in (5, 6):
        cond, target = ops
        if cond == (1, 1) if op == 5 else cond == (1, 0):
            return ("jmp", target)
        return (name, cond, target)
    return (name, *ops)


def classify_diffs(mem: list[int], alt: list[int]) -> dict[str, int]:
    """Prove the two files differ only in encoding and in hull payload.

    Every differing cell must fall inside either (a) a code instruction
    whose canonical form matches, or (b) the hull region. Anything else
    raises. Returns the counts that summarise the comparison."""
    if len(mem) != len(alt):
        raise ValueError(f"images differ in size: {len(mem)} vs {len(alt)}")
    diffs = {i for i in range(len(mem)) if mem[i] != alt[i]}

    listing = descend(mem, entry_points(mem))
    alt_listing = descend(alt, entry_points(alt))
    if set(listing) != set(alt_listing):
        raise ValueError("the two files decode to different instruction addresses")
    patches = {dest: owner for _, dest, owner in operand_patches(mem, listing)}
    alt_patches = {dest: owner for _, dest, owner in operand_patches(alt, alt_listing)}

    flip_cells, flip_instructions = set(), []
    for addr in listing:
        span = set(range(addr, addr + listing[addr][1]))
        if span & diffs:
            if canonical(mem, addr, patches) != canonical(alt, addr, alt_patches):
                raise ValueError(
                    f"semantic difference at {addr}: {mem[addr : addr + 4]} vs {alt[addr : addr + 4]}"
                )
            flip_cells |= span & diffs
            flip_instructions.append(addr)

    hull = imm_value(mem, HULL_BASE_AT)
    hull_end = imm_operand(mem, SCRIPT_BASE_AT, 2) - 2  # up to the RUN terminator
    hull_cells = {i for i in diffs if hull <= i <= hull_end}

    stray = diffs - flip_cells - hull_cells
    if stray:
        raise ValueError(f"diffs that are neither coin-flips nor hull: {sorted(stray)[:5]}")
    return {
        "differing cells": len(diffs),
        "encoding-flip cells": len(flip_cells),
        "flipped instructions": len(flip_instructions),
        "hull cells": len(hull_cells),
    }


def pass6(mem: list[int], alt_path: Path) -> None:
    print("\n== pass 6: two users' files ==")
    if not alt_path.is_file():
        print(f"  {alt_path.name} absent; skipped")
        return
    alt = parse_input(alt_path.read_text())
    stats = classify_diffs(mem, alt)
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print("  every non-hull diff is an encoding coin-flip; the hull is the puzzle")


# ------------------------------------------------------- the full listing


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def notes_for(mem: list[int]) -> dict[int, str]:
    """Terse per-address annotations, built from the file's own values."""
    prompt = imm_value(mem, PROMPT_AT)
    strings = string_table(mem, prompt)

    def s(addr: int) -> str:
        text = strings[addr]
        return repr(text if len(text) <= 24 else text[:21] + "...")

    return {
        0: "stack at 2050, one cell past the file",
        2: f"arg = {prompt} = {s(prompt)}",
        6: "call puts",
        13: "parse loop: skip blanks",
        20: "read the keyword's first letter",
        27: "'A'?  -> AND arm",
        34: "'O'?  -> OR arm",
        41: "'N'?  -> NOT arm",
        48: "'W'?  -> WALK arm",
        55: "'R'?  -> RUN arm",
        62: f"else die with {s(imm_value(mem, 62))}",
        73: "AND arm: expect 'N', then 'D'",
        103: "op = 1 (AND)",
        110: "OR arm: expect 'R'",
        125: "op = 2 (OR)",
        132: "NOT arm: expect 'O', then 'T'",
        162: "op = 3 (NOT)",
        169: "WALK arm: expect 'A', 'L', 'K'",
        221: "then the newline",
        236: "-> run the survey",
        239: "RUN arm: expect 'U', 'N'",
        276: "then the newline",
        291: "running = 1",
        295: "-> run the survey",
        298: "first argument: skip blanks, read it",
        327: "ch = the register letter",
        331: "'A' <= ch <= 'I' ?",
        346: "not a sensor -> J or T?",
        349: "sensor past 'D'?",
        356: "saw_run_sensor = 1",
        360: "arg1 = ch - 'A' + 1, in 1..9",
        367: "'J' -> arg1 = -1",
        381: "'T' -> arg1 = -2",
        395: f"else die with {s(imm_value(mem, 395))}",
        406: "expect the separating space",
        428: "second argument: read it",
        435: "ch = the register letter",
        439: "'J' -> arg2 = -1",
        453: "'T' -> arg2 = -2",
        467: f"else die with {s(imm_value(mem, 467))}",
        478: "skip blanks",
        485: "expect the newline",
        500: f"count < {imm_operand(mem, SCRIPT_LIMIT_AT, 2)} ?",
        507: f"full: die with {s(imm_value(mem, 507))}",
        518: f"slot = count*3 + {imm_operand(mem, SCRIPT_BASE_AT, 2)}",
        526: "slot[0] = op       (patched store)",
        530: "slot[1] = arg1     (patched store)",
        542: "slot[2] = arg2     (patched store)",
        546: "count += 1",
        550: "next instruction line",
        553: "WALK forbids sensors E..I:",
        559: f"die with {s(imm_value(mem, 559))}",
        570: f"arg = {s(imm_value(mem, 570))}",
        577: f"arg = {s(imm_value(mem, 577))}",
        581: "call puts",
        588: f"[593] <- {imm_value(mem, 588)}: the hull cursor (patched operand)",
        592: "cell = next hull cell (via the patch)",
        596: "0 terminates a course",
        599: "decode it into the window",
        610: "fly the droid, no rendering",
        621: "survived -> advance",
        624: f"arg = {s(imm_value(mem, 624))}",
        628: "call puts",
        635: "re-fly THE SAME chunk, rendering",
        646: "die mid-picture",
        647: "hull cursor += 1",
        654: "course done: WALK stops here...",
        657: "...RUN clears the flag and continues into course 2",
        664: "the damage report -- the answer",
        667: "emit_tiles(cell):",
        669: f"tileptr = {imm_value(mem, TILE_DEST_AT)} (window column {GROUND_LEFT})",
        673: "value to decompose",
        677: f"{imm_value(mem, 677)} digits",
        681: "per-digit callback = put_tile",
        685: "call emit_bits",
        694: "return",
        697: "put_tile(bit):",
        699: "store target = tileptr (patched operand)",
        703: "the tile itself",
        707: "tileptr += 1",
        713: "return",
        1263: "peekc: buffered?",
        1268: "read one char into buf",
        1270: "return it, buf kept",
        1279: "getc: peekc...",
        1288: "...take the char...",
        1292: "...and clear buf",
        1301: "expect(ch, err):",
        1310: "the char read",
        1314: "equal?",
        1321: "no: die with the caller's error string",
        1334: "return",
        1337: "skip_ws: peek",
        1346: "space?",
        1353: "tab?",
        1363: "consume it",
        1370: "and peek again",
        1373: "return (char still buffered)",
        1378: "puts(addr):",
        1380: "length = [addr] (patched operand)",
        1396: "printed == length?",
        1403: "char address = addr + i (patched operand)",
        1407: "one char",
        1416: "return",
        1421: "die(err): blank line,",
        1425: "the error string,",
        1436: "blank line, halt",
        1439: "(unreachable epilogue)",
        1444: "add_damage(col):",
        1446: "hull-cell address * cell value",
        1450: "* column",
        1454: "damage += it",
        1460: "return",
        1463: "run_chunk(render):",
        1465: f"col = {imm_value(mem, START_COL_AT)}",
        1469: "alt = 1",
        1473: "thrust = 0",
        1477: "rendering? then draw a frame:",
        1480: "3 sky rows +",
        1484: f"columns {imm_value(mem, START_COL_AT)}..{imm_operand(mem, END_COL_AT, 2)}",
        1488: "droid here?",
        1502: "'@'",
        1507: "sky row?",
        1510: f"tile = [{imm_operand(mem, WINDOW_BASE_AT, 2)} + col]",
        1514: "tile*-11 + 46: '#' or '.'",
        1522: "hull char",
        1527: "sky '.'",
        1540: "end of row",
        1553: "end of frame",
        1555: "alt < 1: fell -> return 0",
        1569: f"col == {imm_operand(mem, END_COL_AT, 2)}: crossed -> return 1",
        1583: "tile under the droid",
        1591: "standing on ground?",
        1599: "hole below:",
        1602: "damage += addr*cell*col",
        1613: "standing?",
        1616: "run the springscript",
        1627: "J false: walk on",
        1630: "J true: thrust = 2",
        1634: "airborne or standing:",
        1645: "col += 1",
        1649: "thrust burns -> climb...",
        1663: "...else gravity",
        1667: "alt 0 over ground",
        1682: "snaps back to alt 1",
        1686: "next step",
        1689: "return rb[1]",
        1694: "eval_script(col):",
        1696: "i = 0",
        1700: "J = 0",
        1704: "T = 0",
        1708: "i == count: done",
        1715: "slot = i*3",
        1719: "op (patched fetch)",
        1727: "arg1 (patched fetch)",
        1735: "sensor code? (1..9)",
        1754: "not a sensor:",
        1757: "sensor: tile at col+arg1 (patched fetch)",
        1772: "-1 -> J",
        1779: "value = J",
        1786: "value = T",
        1790: "arg2 (patched fetch)",
        1798: "-1 -> J",
        1805: "dest was J",
        1812: "dest was T",
        1816: "op 1: AND is *",
        1823: "op 2: OR is + then 0<",
        1830: "op 3: NOT is ==0",
        1855: "store to J...",
        1869: "...or to T",
        1873: "i += 1",
        1880: "return J",
        1889: "in_range(v, lo, hi):",
        1891: "v < lo",
        1895: "hi < v",
        1899: "either?",
        1903: "return ==0",
        1913: "emit_bits(v, n, fn):",
        1915: "emit_fn <- fn (the ONE control-flow patch)",
        1919: "negative v",
        1926: "clamps to 0",
        1930: "value",
        1934: "digit count",
        1938: "power = 1",
        1946: "call bits_rec",
        1951: "return",
        1954: "bits_rec(v, n, p):",
        1956: "digits exhausted -> return v",
        1963: "v < p: stop doubling",
        1977: "recurse with n-1, p*2",
        1996: "v = remainder from below",
        2000: "digit = 1...",
        2004: "...unless v < p",
        2015: "p = p*digit",
        2019: "digits left?",
        2026: "emit the digit",
        2034: "jnz #1 [1912]: the indirect callback",
        2037: "v -= p (p is 0 for a 0 digit)",
        2045: "return v",
    }


def full_listing(mem: list[int], source: str = "day21.txt") -> str:
    """The whole image, cell by cell, as one continuous annotated listing.

    Layout follows day17_listing.md. Every cell appears exactly once --
    asserted, not hoped. NOT committed: the raw cells republish a puzzle
    input (see .gitignore); regenerate with
    `python python/day21_disasm.py [inputs/day21_alt.txt] --full`.
    """
    calls = call_sites(mem)
    listing = descend(mem, entry_points(mem))
    notes = notes_for(mem)
    prompt = imm_value(mem, PROMPT_AT)
    hull = imm_value(mem, HULL_BASE_AT)
    script_base = imm_operand(mem, SCRIPT_BASE_AT, 2)
    limit = imm_operand(mem, SCRIPT_LIMIT_AT, 2)
    window = imm_operand(mem, WINDOW_BASE_AT, 2)
    strings = string_table(mem, prompt)
    strings_end = max(strings) + len(strings[max(strings)])
    courses = recover_courses(mem)

    covered: set[int] = set()
    lines: list[str] = []

    def emit(addr: int, raw: list[int], asm: str, note: str = "") -> None:
        cells = " ".join(str(v) for v in raw)
        text = f"{addr:04d}  {cells:<24} {asm}"
        lines.append(f"{text:<66}; {note}" if note else text.rstrip())

    def code(lo: int, hi: int) -> None:
        addr = lo
        while addr <= hi:
            if addr in SUBROUTINES:
                lines.append("")
                lines.append(f"{SUBROUTINES[addr].split()[0]}:")
            text, size = listing.get(addr, (None, 0))
            if text is None:
                # dead code the descent never reaches (die's epilogue after hlt)
                text, size = render_instruction(mem, addr)
            if text is None:
                raise ValueError(f"cell {addr} in code region {lo}..{hi} is not an instruction")
            note = notes.get(addr, "")
            if not note:
                if addr in calls:
                    target, ret = calls[addr]
                    note = f"call {SUBROUTINES.get(target, str(target)).split()[0]} -> ret {ret}"
                elif mem[addr : addr + 3] in ([2105, 1, 0], [2106, 0, 0]):
                    note = "return"
            emit(addr, mem[addr : addr + size], text, note)
            covered.update(range(addr, addr + size))
            addr += size

    def header(title: str) -> None:
        if lines:
            lines.extend(["```", ""])
        lines.extend([f"## {title}", "", "```"])

    def var(addr: int, note: str) -> None:
        emit(addr, [mem[addr]], f".int {mem[addr]}", note)
        covered.add(addr)

    header("0000 .. 0026 — boot: prompt, then the parse loop")
    code(0, 26)
    header("0027 .. 0552 — the springscript parser (recursive descent, five arms)")
    code(27, 552)
    header("0553 .. 0666 — the survey driver: course loop, damage report")
    code(553, 666)
    header("0667 .. 0715 — emit_tiles and its callback")
    code(667, 715)
    tiles = imm_value(mem, TILE_DEST_AT)
    header(f"{window:04d} .. {hull - 11:04d} — the 32-tile window")
    for addr in range(window, hull - 10):
        pos = addr - window
        kind = "decoded hazard tile" if tiles <= addr < tiles + 9 else "permanent ground"
        var(addr, f"column {pos}: {kind}")
    header(f"{hull - 10:04d} .. {hull - 1:04d} — variables")
    for addr in range(hull - 10, hull):
        var(addr, SYMBOLS.get(addr, ""))
    n_walk, n_run = (len(c) for c in courses)
    header(
        f"{hull:04d} .. {script_base - 2:04d} — the hull: {n_walk} WALK chunks, {n_run} RUN chunks, 9 bits each"
    )
    for course, label in zip(courses, ("WALK", "RUN")):
        for addr, value in course:
            hazard = chunk_window(value)[GROUND_LEFT : GROUND_LEFT + 9]
            emit(addr, [value], f".hull {value}", f"{label} {hazard}")
            covered.add(addr)
        terminator = course[-1][0] + 1
        emit(terminator, [0], ".int 0", f"end of the {label} course")
        covered.add(terminator)
    header(f"{script_base - 1:04d} .. {prompt - 1:04d} — the springscript store: {limit} slots of 3")
    var(script_base - 1, SYMBOLS.get(script_base - 1, "count"))
    for slot in range(limit):
        addr = script_base + slot * 3
        emit(addr, mem[addr : addr + 3], f".slot {slot}", "op arg1 arg2")
        covered.update(range(addr, addr + 3))
    header(f"{prompt:04d} .. {strings_end:04d} — the string table")
    for addr, text in strings.items():
        emit(addr, [mem[addr]], f'.str {mem[addr]} "{_escape(text)}"')
        covered.update(range(addr, addr + 1 + mem[addr]))
    header(f"{strings_end + 1:04d} .. 1911 — the runtime")
    var(strings_end + 1, SYMBOLS.get(strings_end + 1, "buf"))
    code(strings_end + 2, 1911)
    header(f"1912 .. {len(mem) - 1:04d} — the bit emitter, behind its patched callback cell")
    var(1912, SYMBOLS.get(1912, ""))
    code(1913, len(mem) - 1)
    lines.append("```")

    missing = set(range(len(mem))) - covered
    if missing:
        raise ValueError(f"{len(missing)} cells never listed, first {sorted(missing)[:5]}")

    intro = "\n".join(
        [
            f"# Day 21 — the complete listing (`{source}`)",
            "",
            f"> All {len(mem)} integers of `inputs/{source}`, every one accounted for:",
            f"> {len(listing)} instructions across boot, parser, driver and eleven",
            "> subroutines, then the data regions. Generated by",
            "> [python/day21_disasm.py](../../python/day21_disasm.py) —",
            "> `python python/day21_disasm.py --full`. Not committed: the raw cells",
            "> republish the puzzle input (see `.gitignore`).",
            ">",
            "> The analysis behind the annotations is in",
            "> [day21_disassembly.md](day21_disassembly.md); this file is the evidence",
            "> for it, in address order. Notation: `[a]` position, `#n` immediate,",
            "> `rb[+n]` relative; an `=name` suffix marks a known variable.",
            "",
            "At run time the stack occupies 2050 upward; nothing else is in the file.",
            "",
            "",
        ]
    )
    return intro + "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    full = "--full" in args
    args = [a for a in args if a != "--full"]
    inputs = Path(__file__).resolve().parent.parent / "inputs"
    path = Path(args[0]) if args else inputs / "day21.txt"
    mem = parse_input(path.read_text())

    if full:
        sys.stdout.reconfigure(encoding="utf-8")
        print(full_listing(mem, source=path.name), end="")
        return

    listing = pass1(mem)
    pass2(mem, listing)
    pass3(mem)
    one, two = pass4(mem)
    pass5(mem, one, two)
    pass6(mem, inputs / "day21_alt.txt")


if __name__ == "__main__":
    main()
