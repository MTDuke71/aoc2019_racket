"""Day 15 -- Oxygen System.

The puzzle ships worked examples but *no Intcode program* to reach them with:
the statement draws its maze in ASCII and narrates the droid's replies. So the
tests supply a `MazeDroid` -- an ASCII maze wearing the VM's interface -- and
run the real `explore` against it. That is worth more than a mock: `_move` and
the backtracking loop are exercised for real, and the droid's own bookkeeping
(where it ends up, how many commands it took) becomes observable in a way the
Intcode program never is.

Three non-obvious claims from the function guide are pinned here rather than
merely asserted in prose:

  * `explore` leaves the droid back where it started -- the backtrack stack is
    a real route home, not just a recursion stack (`test_droid_returns_home`).
  * The walk costs exactly `2*(open - 1) + walls` movement commands
    (`test_command_count_identity`). Wall probes are free; every other open
    cell is entered once and retreated from once.
  * The real input's maze is a TREE -- 799 cells, 798 edges, no cycles
    (`test_real_maze_is_a_tree`). That is why DFS's trail depth to the oxygen
    equals the BFS distance on this input, and why the two-phase design still
    earns its keep: nothing in the statement promises it.

A second user's program, `inputs/day15_alt.txt`, is exercised alongside the
real input from `test_oxygen_is_a_literal_in_the_code` onwards. It is not there
for extra coverage of the solver -- `explore` cannot tell one maze from another
-- but to keep the DISASSEMBLY honest. Every constant the static recovery needs
is generated per user (the wall threshold is 37 in one file and 35 in the
other), so a fact hardcoded to Matt's input would produce a confidently wrong
maze on anyone else's. Its puzzle answers are not this account's to submit and
so are never asserted; the tests over it check only self-consistency and things
readable from the file itself.
"""

from __future__ import annotations

import day15
import day15_disasm
import pytest
from day15 import BACK, MOVES, OPEN, OXYGEN, WALL, distances, explore, parse_input

LOCKED = (254, 268)  # verified on adventofcode.com


class MazeDroid:
    """An ASCII maze answering the Intcode VM's protocol -- `.inputs`, `.step()`.

    `explore` cannot tell it from the real program, which is the point: taking a
    droid rather than a program is what makes the puzzle's own worked example
    reachable from a test at all.

    Art conventions match the statement: `#` wall, `.` open, `O` the oxygen
    system, `D` the droid's start (open). A space -- "unexplored" in the
    statement's drawings -- reads as wall, as does anything off the edge.
    """

    def __init__(self, art: str) -> None:
        self.cells = {
            (x, y): ch for y, row in enumerate(art.splitlines()) for x, ch in enumerate(row) if ch != " "
        }
        self.start = next(p for p, ch in self.cells.items() if ch == "D")
        self.pos = self.start
        self.inputs: list[int] = []
        self.halted = False
        self.commands = 0
        self.commands_before_oxygen: int | None = None

    def step(self):
        command = self.inputs.pop(0)
        self.commands += 1
        dx, dy = MOVES[command]
        target = (self.pos[0] + dx, self.pos[1] + dy)
        ch = self.cells.get(target, "#")
        if ch == "#":
            return ("output", WALL)  # status 0: the droid did NOT move
        self.pos = target
        if ch == "O":
            if self.commands_before_oxygen is None:
                self.commands_before_oxygen = self.commands
            return ("output", OXYGEN)
        return ("output", OPEN)


# The statement's example, drawn as the complete map Part Two supplies, with the
# droid's Part One starting cell (row 2, column 3) marked. Oxygen is 2 moves
# from the start; the region fills in 4 minutes.
EXAMPLE = " ##   \n#..## \n#.#D.#\n#.O.# \n ###  "

# A ring. DFS's N-S-W-E tie-break sends the droid the long way round, so the
# walk reaches the oxygen only after circling, while the answer is 2. The real
# input's maze has no cycles and so cannot show this; a maze that *may* have
# them is exactly why the walk maps and BFS answers.
RING = "#####\n#...#\n#.#.#\n#D.O#\n#####"

# A straight corridor: one run out, one run back, three wall probes.
CORRIDOR = "#####\n#D.O#\n#####"


def charted(art: str):
    """Explore an ASCII maze; return (droid, grid, oxygen)."""
    droid = MazeDroid(art)
    grid, oxygen = explore(droid)
    return droid, grid, oxygen


def counts(grid) -> tuple[int, int]:
    """(open cells, wall cells) in a charted map."""
    walls = sum(1 for tile in grid.values() if tile == WALL)
    return len(grid) - walls, walls


# --------------------------------------------------------- the worked example


@pytest.mark.parametrize(
    "art, want_part1, want_part2, want_open",
    [
        (EXAMPLE, 2, 4, 8),
        (RING, 2, 4, 8),
        (CORRIDOR, 2, 2, 3),
    ],
    ids=["statement-example", "ring", "corridor"],
)
def test_examples(art, want_part1, want_part2, want_open):
    _, grid, oxygen = charted(art)
    assert distances(grid, (0, 0))[oxygen] == want_part1
    assert max(distances(grid, oxygen).values()) == want_part2
    assert counts(grid)[0] == want_open


def test_example_charts_every_open_cell():
    """The map is complete: BFS from the start reaches every open cell there is."""
    _, grid, _ = charted(EXAMPLE)
    open_cells, _ = counts(grid)
    assert len(distances(grid, (0, 0))) == open_cells


def test_the_walk_is_not_the_answer():
    """On a maze with a cycle the droid meets the oxygen only after circling.

    The command count is not the puzzle's answer and never was -- which is the
    whole reason `explore` maps and `distances` answers, in two phases.
    """
    droid, grid, oxygen = charted(RING)
    assert droid.commands_before_oxygen > distances(grid, (0, 0))[oxygen]


# ------------------------------------------------ properties of the DFS walk


@pytest.mark.parametrize("art", [EXAMPLE, RING, CORRIDOR], ids=["example", "ring", "corridor"])
def test_droid_returns_home(art):
    """`trail` is a route home, not just a recursion stack: emptying it walks
    the droid physically back to its starting cell."""
    droid, _, _ = charted(art)
    assert droid.pos == droid.start


@pytest.mark.parametrize("art", [EXAMPLE, RING, CORRIDOR], ids=["example", "ring", "corridor"])
def test_command_count_identity(art):
    """Exactly `2*(open - 1) + walls` movement commands.

    A wall probe is free -- status 0 means the droid did not move, so there is
    nothing to undo (hence `+ walls`, not `+ 2*walls`). Every open cell other
    than the origin is stepped into once and retreated from once, and the origin
    is never stepped into at all (hence `open - 1`).
    """
    droid, grid, _ = charted(art)
    open_cells, walls = counts(grid)
    assert droid.commands == 2 * (open_cells - 1) + walls


def test_back_is_an_involution():
    """`BACK` is a table, not `(d + 2) % 4`: the puzzle numbers the directions
    N-S-W-E, pairing up the axes rather than going round the compass."""
    assert all(BACK[BACK[d]] == d for d in MOVES)
    assert all(day15._ahead(day15._ahead((0, 0), d), BACK[d]) == (0, 0) for d in MOVES)


# ------------------------------------------------------ Windows CRLF tolerance


@pytest.mark.parametrize(
    "text",
    ["3,1,4,99", "3,1,4,99\n", "3,1,4,99\r\n", "\r\n3,1,4,99\r\n"],
    ids=["bare", "lf", "crlf", "crlf-padded"],
)
def test_parse_input_tolerates_crlf(text):
    assert parse_input(text) == [3, 1, 4, 99]


# ------------------------------------------------------------- the real input


def test_real_maze_is_a_tree(real_input):
    """799 open cells, 798 edges, zero independent cycles -- a *perfect maze*.

    Pinned because a consequence gets quoted in the guide: in a tree there is
    exactly one simple path between any two cells, so the droid's DFS trail to
    the oxygen IS the shortest route (measured depth 254; part 1 is 254). The
    solution deliberately does not lean on that -- the statement promises no
    such thing -- but the claim about the input should not be left to rot.
    """
    program = parse_input(real_input(15))
    grid, _ = explore(day15.VM(program))
    open_cells, _ = counts(grid)
    edges = sum(
        1
        for point, tile in grid.items()
        if tile != WALL
        for d in (day15.NORTH, day15.WEST)  # count each edge from one side only
        if grid.get(day15._ahead(point, d), WALL) != WALL
    )
    assert (open_cells, edges) == (799, 798)
    assert edges == open_cells - 1  # |E| = |V| - 1 and connected => acyclic


def test_real_input(check_locked):
    check_locked(15, LOCKED)


# ------------------------------------- the disassembly's claims about the file
#
# python/day15_disasm.py argues that the maze is not computed by the program but
# STORED in it, and reads both answers off the file without starting the VM. See
# Problem_Statements/days/day15_disassembly.md. Those are claims about the input
# and about an encoding, so they are pinned here rather than left to a script
# nobody runs.
#
# Each is checked against two programs. `ALT` carries no LOCKED answers, on
# purpose: see the module docstring.

ALT = "15_alt"

# (day, wall threshold, oxygen literal). All three are read out of the file by
# day15_disasm; the point of writing them down is that they DIFFER per user.
PROGRAMS = [
    pytest.param(15, 37, (37, 39), id="day15"),
    pytest.param(ALT, 35, (1, 9), id="day15_alt"),
]

START = (21, 21)  # x and y at addresses 1034/1035 -- the same in both programs

# Where the two programs genuinely differ, as opposed to merely spelling the
# same instruction another way: oxygen x, oxygen y, wall threshold.
SEMANTIC_CELLS = (146, 153, 212)


@pytest.mark.parametrize("day, threshold, oxygen", PROGRAMS)
def test_oxygen_is_a_literal_in_the_code(real_input, day, threshold, oxygen):
    """The oxygen sits in the compare immediates at 146 and 153, and the droid's
    start in the initial values of `x` and `y` -- so its start-relative position
    is arithmetic on four cells of the file, never a search."""
    program = parse_input(real_input(day))
    assert day15_disasm.oxygen_literal(program) == oxygen
    assert (program[1034], program[1035]) == START


@pytest.mark.parametrize("day, threshold, oxygen", PROGRAMS)
def test_wall_threshold_is_read_out_of_the_compare(real_input, day, threshold, oxygen):
    """T is not a constant of the puzzle -- it is generated per input.

    37 here, 35 in the other file. `wall_threshold` recovers it from the
    less-than at 210 instead of believing a hardcoded number, which is the only
    reason the static recovery works on a program it was not written against.
    """
    program = parse_input(real_input(day))
    assert (program[210], program[213]) == (1007, 1044)  # the compare is where we think
    assert day15_disasm.wall_threshold(program) == threshold


def test_wall_threshold_refuses_a_program_it_does_not_recognise():
    """Loudly, rather than returning a plausible integer and a wrong maze."""
    with pytest.raises(ValueError, match="not the wall compare"):
        day15_disasm.wall_threshold([0] * 1045)


@pytest.mark.parametrize("day, threshold, oxygen", PROGRAMS)
def test_wall_threshold_is_a_hole_in_the_value_set(real_input, day, threshold, oxygen):
    """The wall bit is stored as a random number and recovered by `< T`.

    T is the *only* integer in 1..99 absent from the 780-entry table, which is
    why `< T` and `< T+1` give the same partition and no other threshold does.
    The generator reserves it so the comparison can never be ambiguous -- and it
    reserves a different one for every user.
    """
    program = parse_input(real_input(day))
    base, count = day15_disasm.TABLE_BASE, day15_disasm.TABLE_CELLS
    table = program[base : base + count]

    assert sorted(set(range(1, 100)) - set(table)) == [threshold]
    partitions = {t: sum(1 for v in table if v < t) for t in range(1, 101)}
    assert [t for t in partitions if partitions[t] == partitions[threshold]] == [
        threshold,
        threshold + 1,
    ]


@pytest.mark.parametrize("day, threshold, oxygen", PROGRAMS)
def test_the_maze_is_a_spanning_tree_of_a_20x20_cell_grid(real_input, day, threshold, oxygen):
    """400 cells at odd/odd, 399 open edges, so |E| = |V| - 1: a perfect maze.

    This is the *reason* for `test_real_maze_is_a_tree` -- that test observes
    acyclicity by walking, this one reads it out of the generator's output. Both
    programs land on exactly 399/381, so the split is a fixed parameter of the
    generator even though the threshold that encodes it is not.
    """
    program = parse_input(real_input(day))
    cells = sum(1 for x in range(1, 40) for y in range(1, 40) if x & 1 and y & 1)
    base, count = day15_disasm.TABLE_BASE, day15_disasm.TABLE_CELLS
    table = program[base : base + count]
    passages = sum(1 for v in table if v < threshold)

    assert (cells, passages) == (400, 399)
    assert passages == cells - 1
    assert count - passages == 381


@pytest.mark.parametrize("day, threshold, oxygen", PROGRAMS)
def test_static_recovery_matches_the_walk(real_input, day, threshold, oxygen):
    """The maze read out of the data region is the maze the droid walks.

    Cell for cell, oxygen included, with the VM started only for the comparison.
    Note what this needs from the puzzle site: nothing. Two independent methods
    over the same file have to agree, which is checkable on a program whose
    answers nobody here has submitted.
    """
    program = parse_input(real_input(day))
    static, static_oxygen = day15_disasm.recover_maze(program)
    walked, walked_oxygen = explore(day15.VM(program))

    assert {p for p, t in static.items() if t != WALL} == {p for p, t in walked.items() if t != WALL}
    assert static_oxygen == walked_oxygen == (oxygen[0] - START[0], oxygen[1] - START[1])

    answers = (
        distances(static, (0, 0))[static_oxygen],
        max(distances(static, static_oxygen).values()),
    )
    if day == 15:
        assert answers == LOCKED


def test_only_three_code_cells_carry_meaning(real_input):
    """Forty cells of the code region differ between the two programs; three mean
    something. The other thirty-seven are the generator spelling the same
    instruction another way.

    Intcode has no `mov`, so a copy is written as `x * 1`, `1 * x`, `x + 0` or
    `0 + x`, and an unconditional jump as `jnz 1` or `jz 0`. Which one gets
    emitted is randomised per user -- `status = 0` at 217 is `1102 0 1 1044` in
    one file and `1101 0 0 1044` in the other. That is a second obfuscation
    layer over the randomised wall table, and like the table it costs nothing:
    every variant is the same width.

    Proved by splicing rather than by reading: take one program's code region,
    move only SEMANTIC_CELLS across, bolt on the other's data, and the machine
    walks the other's maze exactly.
    """
    a = parse_input(real_input(15))
    b = parse_input(real_input(ALT))
    end = day15_disasm.CODE_END

    differing = [i for i in range(end) if a[i] != b[i]]
    assert len(differing) == 40
    assert set(SEMANTIC_CELLS) < set(differing)

    hybrid = a[:end] + b[end:]
    for cell in SEMANTIC_CELLS:
        hybrid[cell] = b[cell]
    assert sum(1 for i in range(end) if hybrid[i] != b[i]) == 37  # still textually different

    assert explore(day15.VM(hybrid)) == explore(day15.VM(list(b)))
