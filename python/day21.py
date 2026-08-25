"""AoC 2019 Day 21 -- Springdroid Adventure.

The Intcode machine is unchanged (frozen at Day 9; see python/intcode.py). The
peripheral is Day 17's ASCII console again -- but this time we type a PROGRAM
into it. The Intcode program is an assembler and simulator for "springscript",
and the puzzle is to write the springscript.

What springscript actually is: a STRAIGHT-LINE BOOLEAN PROGRAM -- AND/OR/NOT
over two writable registers, no branches, no loops, at most 15 instructions.
That makes the droid a *memoryless reactive policy*: it re-runs the whole
script from T = J = false at every tile, so the jump decision is a pure
combinational function of the current sensor window and nothing else. The
droid cannot remember, plan, or count. Writing the script is therefore circuit
synthesis: pick a Boolean function of the sensors, then express it in the
three-opcode ISA within the instruction budget.

The physics, pinned by the statement's death rendering (and by
test_suicide_program_replays_the_statement_rendering): a jump launched from
tile x lands on tile x+4 -- exactly the tile register D sees. So:

  * Part 1 (WALK, sensors A..D): jump iff a hole is coming and the landing
    site is ground:  J = not(A and B and C) and D.  Jumping any earlier than
    "a hole within 3" is never needed, because a jump clears at most 3 holes.
  * Part 2 (RUN, sensors A..I): same jump, longer sight. The Part 1 policy
    now has a visible failure mode -- it can land on D with a hole at E *and*
    a hole at H, where neither stepping nor an immediate second jump is
    possible. The fix is one guard: only jump if the landing site has an exit,
    J = not(A and B and C) and D and (E or H)  -- either step off the landing
    tile, or chain straight into a second jump (H is D's own D).

Both scripts are verified two ways: exhaustively against their truth tables
(all 16 / 512 sensor combinations), and by walking ASCII hulls through the
simulator below -- the same split that let Days 17 and 19 test against
pictures instead of the machine.

Run:  python python/day21.py
"""

from __future__ import annotations

from pathlib import Path

from intcode import VM

MEMORY_LIMIT = 15  # springscript instructions the droid can hold
JUMP = 4  # a jump launched from x lands on x + 4: register D's tile
SIGHT_WALK = 4  # WALK exposes A..D
SIGHT_RUN = 9  # RUN exposes A..I

# J = not(A and B and C) and D
PART1_SCRIPT = (
    "OR A T",
    "AND B T",
    "AND C T",
    "NOT T J",
    "AND D J",
)

# J = not(A and B and C) and D and (E or H).
# T carries D and (E or H); J carries not(A and B and C); AND merges them.
PART2_SCRIPT = (
    "OR E T",
    "OR H T",
    "AND D T",
    "OR A J",
    "AND B J",
    "AND C J",
    "NOT J J",
    "AND T J",
)


def parse_input(text: str) -> list[int]:
    return [int(t) for t in text.strip().split(",")]


# ------------------------------------------------------- springscript itself


def run_script(script: tuple[str, ...] | list[str], sensors: dict[str, bool]) -> bool:
    """Evaluate a springscript program against one sensor reading.

    The whole language: three opcodes, second operand writable. T and J start
    false on every evaluation -- the droid has no state between tiles, which
    is precisely why the policy is memoryless. Enforces the same rules the
    Intcode assembler does (instruction budget, writable destination), so a
    script this interpreter accepts is a script the machine will accept.
    """
    if len(script) > MEMORY_LIMIT:
        raise ValueError(f"{len(script)} instructions; the droid holds {MEMORY_LIMIT}")
    regs = {"T": False, "J": False, **sensors}
    for line in script:
        op, x, y = line.split()
        if y not in ("T", "J"):
            raise ValueError(f"destination must be writable: {line!r}")
        a = regs[x]
        if op == "AND":
            regs[y] = a and regs[y]
        elif op == "OR":
            regs[y] = a or regs[y]
        elif op == "NOT":
            regs[y] = not a
        else:
            raise ValueError(f"unknown opcode: {line!r}")
    return regs["J"]


def run_droid(hull: str, script: tuple[str, ...] | list[str], sight: int) -> int | None:
    """Walk the droid across an ASCII hull row (`#` ground, `.` hole).

    Returns the index it fell into, or None if it crossed. Each tile the droid
    stands on, the script is re-evaluated from scratch on the window of the
    next `sight` tiles (tiles past the right edge read as ground -- the ship's
    hull continues beyond the hazard section), then the droid jumps 4 or steps
    1. Crossing means walking off the right end of the string.
    """
    pos = 0
    while pos < len(hull):
        if hull[pos] != "#":
            return pos
        window = {
            chr(ord("A") + k): pos + 1 + k >= len(hull) or hull[pos + 1 + k] == "#" for k in range(sight)
        }
        pos += JUMP if run_script(script, window) else 1
    return None


# ------------------------------------------------------------- the machine


def survey(program: list[int], script: tuple[str, ...] | list[str], command: str) -> tuple[str, int | None]:
    """Type the script into the Intcode console and run the survey.

    Returns `(transcript, damage)`: every ASCII output decoded as text, and
    the one output above 127 -- the hull-damage report -- if the droid made it
    across. A droid that falls produces no damage value; the transcript then
    ends with the rendering of its last moments, which is the debugging
    channel this day gives you.
    """
    vm = VM(program)
    text = "\n".join([*script, command]) + "\n"
    vm.inputs.extend(ord(ch) for ch in text)

    chars: list[str] = []
    damage = None
    while True:
        result = vm.step()
        if result == "halted":
            break
        if result == "blocked":
            raise RuntimeError("the console asked for more input than the script provides")
        if isinstance(result, tuple):
            code = result[1]
            if code > 127:
                damage = code
            else:
                chars.append(chr(code))
    return "".join(chars), damage


def _damage_or_die(program: list[int], script: tuple[str, ...], command: str) -> int:
    transcript, damage = survey(program, script, command)
    if damage is None:
        raise RuntimeError(f"the droid fell into space:\n{transcript}")
    return damage


def part1(program: list[int]) -> int:
    return _damage_or_die(program, PART1_SCRIPT, "WALK")


def part2(program: list[int]) -> int:
    return _damage_or_die(program, PART2_SCRIPT, "RUN")


def solve(program: list[int]) -> tuple[int, int]:
    return part1(program), part2(program)


def main() -> None:
    text = (Path(__file__).resolve().parent.parent / "inputs" / "day21.txt").read_text()
    program = parse_input(text)

    for label, script, command in (("part 1", PART1_SCRIPT, "WALK"), ("part 2", PART2_SCRIPT, "RUN")):
        transcript, damage = survey(program, script, command)
        print(transcript.rstrip("\n"))
        if damage is None:
            print(f"  {label}: the droid fell")
        else:
            print(f"  {label}: {damage}")


if __name__ == "__main__":
    main()
