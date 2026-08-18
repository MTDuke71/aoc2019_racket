"""AoC 2019 Day 17 -- Set and Forget.

The Intcode machine is unchanged (frozen at Day 9; see python/intcode.py). What
changes, as on every Intcode day since 11, is the PERIPHERAL on opcodes 3/4 --
and this one is a joke the puzzle makes out loud: the outputs are ASCII codes,
so the program's "video feed" is literally a text file arriving one byte at a
time. `chr()` over the output stream and the frame draws itself.

That reframing is the whole of Part 1. Once the view is a string, no Intcode
concept survives into the answer: an intersection is a `#` with `#` on all four
sides, which is a 3x3 morphological probe over a character grid -- the same
neighbourhood test as a Game-of-Life step or an image-processing kernel. The VM
is a file format, not a participant.

Two consequences shape the code below:

  * `camera_view` returns a STRING, and everything after it takes a string.
    That is what lets the tests run the puzzle's own worked example, which
    ships an ASCII picture and no Intcode program at all -- the same split that
    made Day 15's `MazeDroid` possible.
  * The robot glyph (`^v<>`) sits ON a scaffold, so it counts as scaffold for
    the neighbourhood test. `X` -- the robot tumbling through space -- does not.

Run:  python python/day17.py
"""

from __future__ import annotations

from pathlib import Path

from intcode import VM

SCAFFOLD = "#"
ROBOT_GLYPHS = "^v<>"  # drawn on a scaffold, so they count as one
TUMBLING = "X"  # off the scaffold: NOT a scaffold cell

Point = tuple[int, int]


def parse_input(text: str) -> list[int]:
    return [int(t) for t in text.strip().split(",")]


def camera_view(program: list[int]) -> str:
    """Run the ASCII program to a halt and decode its output as text.

    The program emits one character code per opcode-4, so the whole frame is
    `"".join(map(chr, outputs))`. Values above 127 would mean the peripheral is
    saying something that is not a character; nothing in Part 1 does, and
    letting a stray large value through as `chr()` would corrupt the grid
    silently, so it is rejected.
    """
    vm = VM(program)
    chars = []
    while True:
        result = vm.step()
        if result == "halted":
            break
        if result == "blocked":
            raise RuntimeError("camera program asked for input; Part 1 sends none")
        if isinstance(result, tuple):
            code = result[1]
            if not 0 <= code < 128:
                raise ValueError(f"non-ASCII output {code} from the camera")
            chars.append(chr(code))
    return "".join(chars)


def scaffold_points(view: str) -> set[Point]:
    """Every `(x, y)` the robot could stand on.

    `#` plus the robot's own cell -- the statement is explicit that when the
    robot is drawn as `^v<>` it is on a scaffold. `X` is excluded: that glyph
    means it has already fallen off.
    """
    return {
        (x, y)
        for y, row in enumerate(view.splitlines())
        for x, ch in enumerate(row)
        if ch == SCAFFOLD or ch in ROBOT_GLYPHS
    }


def intersections(view: str) -> list[Point]:
    """Scaffold cells with scaffold on all four sides.

    A 3x3 plus-shaped probe over the grid. Edge cells can never qualify -- a
    neighbour off the picture is simply absent from the set -- so no bounds
    checking is needed beyond the `in` test itself.
    """
    cells = scaffold_points(view)
    return [(x, y) for (x, y) in cells if {(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)} <= cells]


def alignment_sum(view: str) -> int:
    """Sum of `x * y` over the intersections -- the camera calibration value."""
    return sum(x * y for x, y in intersections(view))


def part1(program: list[int]) -> int:
    return alignment_sum(camera_view(program))


# --------------------------------------------------------------- the walk

# Facing is stored as the glyph the camera would draw, so a turn is a table
# lookup and no angle arithmetic is needed anywhere.
TURN_LEFT = {"^": "<", "<": "v", "v": ">", ">": "^"}
TURN_RIGHT = {left: facing for facing, left in TURN_LEFT.items()}
STEP = {"^": (0, -1), "v": (0, 1), "<": (-1, 0), ">": (1, 0)}


def find_robot(view: str) -> tuple[Point, str]:
    """The robot's `((x, y), facing)`; `X` means it already fell off."""
    for y, row in enumerate(view.splitlines()):
        for x, ch in enumerate(row):
            if ch in ROBOT_GLYPHS:
                return (x, y), ch
            if ch == TUMBLING:
                raise ValueError(f"the robot is already tumbling, at ({x}, {y})")
    raise ValueError("no robot in the camera view")


def path(view: str) -> list[str]:
    """The greedy route as movement tokens: `['R', '8', 'R', '8', 'L', '6', ...]`.

    The rule is "go straight as far as you can, then turn the only way you
    can", which needs no search at all. It works because the scaffold is a
    single path that merely *crosses* itself: away from a crossing a scaffold
    cell has at most two neighbours, so once you are moving there is never a
    choice; at a crossing all four neighbours are scaffold, and going straight
    is both legal and the only way to leave the crossing without doubling back.

    So the walk is deterministic, and it terminates when the robot reaches the
    far end of the path -- no forward move and no legal turn.

    This covers every scaffold cell *on this input*, which is a property of the
    file and not a promise of the statement, so `part2` verifies it rather than
    assuming it (`test_greedy_walk_covers_every_cell`).
    """
    cells = scaffold_points(view)
    pos, facing = find_robot(view)

    def ahead(p: Point, f: str) -> Point:
        dx, dy = STEP[f]
        return (p[0] + dx, p[1] + dy)

    tokens: list[str] = []
    while True:
        for turn, table in (("L", TURN_LEFT), ("R", TURN_RIGHT)):
            if ahead(pos, table[facing]) in cells:
                facing = table[facing]
                break
        else:
            return tokens  # no way to turn: the end of the path

        distance = 0
        while ahead(pos, facing) in cells:
            pos = ahead(pos, facing)
            distance += 1
        tokens += [turn, str(distance)]


def covered(view: str, tokens: list[str]) -> set[Point]:
    """Every cell the token route actually drives over, start included."""
    pos, facing = find_robot(view)
    seen = {pos}
    for turn, distance in zip(tokens[::2], tokens[1::2]):
        facing = (TURN_LEFT if turn == "L" else TURN_RIGHT)[facing]
        dx, dy = STEP[facing]
        for _ in range(int(distance)):
            pos = (pos[0] + dx, pos[1] + dy)
            seen.add(pos)
    return seen


# -------------------------------------------------------- the compression

MEMORY_LIMIT = 20  # ASCII characters per line, newline not counted
FUNCTION_NAMES = "ABC"


def _encode(tokens: list[str]) -> str:
    return ",".join(tokens)


def compress(
    tokens: list[str], limit: int = MEMORY_LIMIT, names: str = FUNCTION_NAMES
) -> tuple[str, list[str]] | None:
    """Factor the route into a main routine plus <=3 movement functions.

    This is **grammar-based compression**: find a straight-line program (a
    context-free grammar deriving exactly one string) for the token sequence,
    subject to at most `len(names)` non-terminals, no nesting -- "movement
    functions may not call other movement functions", so the grammar is exactly
    two levels deep -- and every line at most `limit` characters once
    comma-joined. The unrestricted version is the Smallest Grammar Problem and
    is NP-hard; this version is so tightly bounded that exhaustive backtracking
    settles it immediately.

    The search: at each position either an already-defined function matches
    here and is consumed, or a new function is coined from some prefix starting
    here. Two prunes do all the work -- a candidate body longer than `limit`
    characters ends the prefix loop (bodies only grow), and a main routine that
    has already reached `limit` cannot be extended.

    Returns `(main, [body, ...])` or `None` if no factorisation exists.
    """

    def search(i: int, functions: list[list[str]], main: list[str]):
        if i == len(tokens):
            return (_encode(main), [_encode(body) for body in functions])
        if len(_encode([*main, "A"])) > limit:
            return None  # the main routine is full

        for name, body in zip(names, functions):
            if tokens[i : i + len(body)] == body:
                found = search(i + len(body), functions, [*main, name])
                if found:
                    return found

        if len(functions) < len(names):
            for length in range(1, len(tokens) - i + 1):
                body = tokens[i : i + length]
                if len(_encode(body)) > limit:
                    break  # bodies only get longer from here
                found = search(i + length, [*functions, body], [*main, names[len(functions)]])
                if found:
                    return found
        return None

    return search(0, [], [])


def expand(main: str, functions: list[str]) -> list[str]:
    """Inverse of `compress` -- the grammar's one derivation, as tokens."""
    bodies = dict(zip(FUNCTION_NAMES, functions))
    return [token for name in main.split(",") for token in bodies[name].split(",")]


# ----------------------------------------------------------- driving it


def run_robot(program: list[int], main: str, functions: list[str], video: str = "n") -> int:
    """Wake the robot, feed it the program, return the dust report.

    `mem[0] = 2` is a MEMORY POKE, not an opcode -- the same channel Day 13
    used to buy a free play. It is written into the VM's memory rather than the
    caller's program list so the input stays reusable.

    Every line is ASCII plus a newline, in the order the statement prompts for
    them: main routine, A, B, C, then the video-feed answer. The dust report is
    identified structurally, not positionally: it is the one output above 127,
    everything below being the prompts and (if enabled) the video frames.
    """
    vm = VM(program)
    vm.mem[0] = 2

    script = "\n".join([main, *functions, video]) + "\n"
    vm.inputs.extend(ord(ch) for ch in script)

    dust = None
    while True:
        result = vm.step()
        if result == "halted":
            break
        if result == "blocked":
            raise RuntimeError("the robot asked for more input than the script provides")
        if isinstance(result, tuple) and result[1] > 127:
            dust = result[1]
    if dust is None:
        raise RuntimeError("the robot halted without reporting any dust")
    return dust


def part2(program: list[int]) -> int:
    view = camera_view(program)
    tokens = path(view)

    missed = scaffold_points(view) - covered(view, tokens)
    if missed:
        raise ValueError(f"the greedy route misses {len(missed)} scaffold cells")

    factored = compress(tokens)
    if factored is None:
        raise ValueError(f"no {MEMORY_LIMIT}-character factorisation of a {len(tokens)}-token route")
    main, functions = factored
    return run_robot(program, main, functions)


def solve(program: list[int]) -> tuple[int, int]:
    return part1(program), part2(program)


def main() -> None:
    text = (Path(__file__).resolve().parent.parent / "inputs" / "day17.txt").read_text()
    program = parse_input(text)

    view = camera_view(program)
    print(view)

    crossings = intersections(view)
    rows = view.strip("\n").splitlines()
    print(f"  view: {len(rows[0])} x {len(rows)}")
    print(f"  scaffold cells: {len(scaffold_points(view))}")
    print(f"  intersections:  {len(crossings)}")
    print(f"  part 1: {alignment_sum(view)}")


if __name__ == "__main__":
    main()
