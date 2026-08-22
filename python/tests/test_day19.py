r"""Day 19 -- Tractor Beam.

The statement ships one worked example: a 10x10 picture of the beam with 27
lit points -- and no Intcode program to draw it with, which is why day19's
scan/search functions take a plain `probe(x, y)` callable (the same split
that let Day 17 test against its ASCII picture). The picture tests the
census; everything Part 2 leans on is pinned separately, because the example
is too small to exercise it:

  * `find_square` checks only TWO corners of each candidate square and walks
    only the beam's LEFT edge. Both shortcuts are cone properties -- each row
    is one contiguous run whose left edge never moves left as y grows -- so
    the suite pins those properties where they are claims: on the statement's
    picture, on a synthetic wedge large enough to host a 10x10 square (with a
    brute-force first-fit oracle to compare against), and on the real input's
    visible 50x50 window plus deep rows along the walk.
  * The real beam is NARROWER than one cell near the origin (rows 1-3 carry
    no beam at all) -- the reason `find_square` starts its walk at row
    size-1 instead of row 0, and the reason `left_edge` carries a tripwire
    rather than trusting every row to be lit.

The closed form the program secretly evaluates (|76x^2 - 100y^2| <= 17xy for
this input) is recovered and verified in python/day19_disasm.py; the tests
here check the SOLUTION's contract only, so they would pass unchanged on any
other user's input file.
"""

from __future__ import annotations

import day19_disasm
import day19_program
import pytest
from day19 import (
    beam_probe,
    count_beam,
    find_square,
    left_edge,
    parse_input,
    part1,
    part2,
)

LOCKED = (209, 10450905)  # verified on adventofcode.com

# The statement's 10x10 scan of the example beam (27 points affected).
EXAMPLE = """\
#.........
.#........
..##......
...###....
....###...
.....####.
......####
......####
.......###
........##"""


def grid_probe(picture: str):
    """A probe backed by an ASCII picture instead of an Intcode program.

    `O` counts as beam: Part Two's worked picture marks the fitted square's
    cells with `O`, and those cells are lit -- that is the point of them.
    """
    lit = {(x, y) for y, row in enumerate(picture.splitlines()) for x, ch in enumerate(row) if ch in "#O"}
    return lambda x, y: (x, y) in lit


def first_fit_oracle(probe, size: int, bound: int):
    """Brute force: the first fully-lit square, scanning rows then columns.

    The same order `find_square` claims to search in -- smallest bottom row
    first, then smallest x -- but checking EVERY cell of every candidate
    square, with none of the two-corner or left-edge-only shortcuts.
    """
    for bottom in range(size - 1, bound):
        for x in range(bound):
            if all(probe(x + dx, bottom - dy) for dx in range(size) for dy in range(size)):
                return x, bottom - size + 1
    raise AssertionError(f"no {size}x{size} square below row {bound}")


# ------------------------------------------------------------------ the example


def test_example_count():
    assert count_beam(grid_probe(EXAMPLE), 10) == 27


def test_example_rows_are_single_runs_with_monotone_left_edge():
    """The cone shape `find_square` leans on, pinned on the statement's picture.

    Every row of the example is one contiguous run of `#`, and each row's run
    starts at or right of the row above's -- including row 0, whose run is the
    lone emitter cell.
    """
    rows = EXAMPLE.splitlines()
    previous_left = -1
    for row in rows:
        left, right = row.index("#"), row.rindex("#")
        assert set(row[left : right + 1]) == {"#"}, f"gap inside the run: {row!r}"
        assert left >= previous_left
        previous_left = left


@pytest.mark.parametrize("size, want", [(1, (0, 0)), (2, (4, 3)), (3, (6, 5))])
def test_example_squares(size, want):
    """Squares in the example picture, against the brute-force oracle.

    size=1 degenerates to the emitter cell itself; the 2x2 at (4, 3) and the
    3x3 at (6, 5) are read off the picture -- and re-derived by the oracle,
    so the hardcoded expectation and the shortcut-free search must agree.
    """
    probe = grid_probe(EXAMPLE)
    assert find_square(probe, size) == want
    assert first_fit_oracle(probe, size, 10) == want


# Part Two's worked example: a 40-wide scan in which the 10x10 square closest
# to the emitter sits at (25, 20) -- the `O` cells -- for an answer of 250020.
P2_EXAMPLE = """\
#.......................................
.#......................................
..##....................................
...###..................................
....###.................................
.....####...............................
......#####.............................
......######............................
.......#######..........................
........########........................
.........#########......................
..........#########.....................
...........##########...................
...........############.................
............############................
.............#############..............
..............##############............
...............###############..........
................###############.........
................#################.......
.................########OOOOOOOOOO.....
..................#######OOOOOOOOOO#....
...................######OOOOOOOOOO###..
....................#####OOOOOOOOOO#####
.....................####OOOOOOOOOO#####
.....................####OOOOOOOOOO#####
......................###OOOOOOOOOO#####
.......................##OOOOOOOOOO#####
........................#OOOOOOOOOO#####
.........................OOOOOOOOOO#####
..........................##############
..........................##############
...........................#############
............................############
.............................###########"""


def test_part_two_example():
    """The statement's own Part Two picture, through the real search AND the
    shortcut-free oracle, then through the answer encoding: 250020."""
    probe = grid_probe(P2_EXAMPLE)
    assert find_square(probe, 10) == (25, 20)
    assert first_fit_oracle(probe, 10, 40) == (25, 20)
    x, y = find_square(probe, 10)
    assert 10000 * x + y == 250020


# ------------------------------------------------------------- a bigger cone


def wedge(x: int, y: int) -> bool:
    """A synthetic beam: lit iff 5y <= 6x <= 9y (slopes x/y in [5/6, 3/2])."""
    return 5 * y <= 6 * x <= 9 * y


def test_wedge_square_matches_the_oracle():
    """A cone big enough for a 10x10 square, which the example cannot host.

    The oracle window (60) comfortably covers the answer; the point is that
    the two-corner walk and the every-cell scan land on the same square.
    """
    assert find_square(wedge, 10) == first_fit_oracle(wedge, 10, 60)


def test_wedge_square_is_fully_lit():
    x, y = find_square(wedge, 10)
    assert all(wedge(x + dx, y + dy) for dx in range(10) for dy in range(10))


# ------------------------------------------------------------------ the pieces


def test_left_edge_resumes_without_loss():
    """Resuming the scan from the previous row's edge finds the same edge."""
    for y in range(2, 30):
        assert left_edge(wedge, y, start=left_edge(wedge, y - 1)) == left_edge(wedge, y)


def test_left_edge_tripwire_on_an_empty_row():
    with pytest.raises(ValueError, match="no beam"):
        left_edge(lambda x, y: False, 7)


def test_probe_rejects_negative_coordinates():
    probe = beam_probe([99])
    with pytest.raises(ValueError, match="negative"):
        probe(-1, 0)
    with pytest.raises(ValueError, match="negative"):
        probe(0, -1)


def test_probe_requires_an_output():
    """A program that halts silently is a broken drone, not a 0."""
    with pytest.raises(RuntimeError, match="halted"):
        beam_probe([99])(0, 0)


def test_probe_does_not_consume_the_program():
    """One list serves many probes: the VM copies memory, `probe` reuses it."""
    program = [3, 100, 3, 101, 104, 1, 99]  # read x, read y, always report 1
    probe = beam_probe(program)
    assert probe(5, 7) and probe(2, 3)
    assert program == [3, 100, 3, 101, 104, 1, 99]


# ------------------------------------------------------------------- the input


def test_crlf():
    r"""A Windows-downloaded input ends `\r\n`; `parse_input` must survive it."""
    assert parse_input("104,1,99\r\n") == [104, 1, 99]


def test_crlf_real_input(real_input):
    text = real_input(19)
    assert parse_input(text) == parse_input(text.replace("\r\n", "\n"))


@pytest.fixture(scope="module")
def real_window(request):
    """The real beam's 50x50 window as a set, probed once for the module."""
    path = request.config.rootpath / "inputs" / "day19.txt"
    if not path.is_file():
        pytest.skip("inputs/day19.txt is absent (inputs are gitignored)")
    probe = beam_probe(parse_input(path.read_text()))
    return {(x, y) for y in range(50) for x in range(50) if probe(x, y)}


def test_real_beam_starts_narrower_than_a_cell(real_window):
    """Row 0 is the emitter alone and rows 1-3 are EMPTY: near the origin the
    cone is thinner than the pixel grid. This is why `find_square` starts at
    row size-1 and why `left_edge` cannot assume every row is lit."""
    assert {x for x, y in real_window if y == 0} == {0}
    for y in (1, 2, 3):
        assert not {x for x, w in real_window if w == y}


def test_real_rows_are_single_runs_with_monotone_left_edge(real_window):
    """The cone properties, pinned on the real input's visible window.

    Rows 4-47 each hold one contiguous run starting at or right of the run
    above. Rows 48-49 are empty AGAIN -- not because the beam stops, but
    because its left edge has already walked past x=49: the 50-wide window
    clips the cone at the bottom just as the cone's thinness clipped it at
    the top."""
    previous_left = 0
    for y in range(4, 48):
        xs = sorted(x for x, w in real_window if w == y)
        assert xs, f"row {y} lost the beam"
        assert xs == list(range(xs[0], xs[-1] + 1)), f"row {y} has a gap"
        assert xs[0] >= previous_left
        previous_left = xs[0]
    for y in (48, 49):
        assert not {x for x, w in real_window if w == y}


def test_real_deep_left_edges_stay_monotone(real_input):
    """The walk leaves the 50x50 window far behind; spot-check that the left
    edge keeps its no-retreat promise at depth, and that resuming the scan
    from the previous edge agrees with scanning from zero."""
    probe = beam_probe(parse_input(real_input(19)))
    edges = [left_edge(probe, y) for y in (100, 200, 300)]
    assert edges == sorted(edges)
    assert left_edge(probe, 300, start=edges[1]) == edges[2]


def test_real_square_is_lit_and_flush_left(real_input):
    """Whatever square `find_square` returns must actually hold: all four
    corners lit, a sample of interior cells lit, and the bottom-left corner
    flush against the beam's edge (one cell left is dark). Property-based on
    purpose -- the answer's VALUE is `check_locked`'s job, not this test's."""
    probe = beam_probe(parse_input(real_input(19)))
    x, y = find_square(probe, 100)
    assert probe(x, y + 99) and probe(x + 99, y)  # the corners the walk checked
    assert probe(x, y) and probe(x + 99, y + 99)  # the two it inferred
    assert all(probe(x + d, y + d) for d in range(7, 99, 13))  # the diagonal
    assert not probe(x - 1, y + 99)


# ------------------------------------------------- the disassembly (day19_disasm)


def test_recovered_formula_matches_the_vm_window(real_input, real_window):
    """The predicate |A*x^2 - B*y^2| <= C*x*y, with A, B, C recovered from the
    program's own immediates, reproduces the VM's 50x50 window exactly."""
    a, b, c = day19_disasm.recover_constants(parse_input(real_input(19)))
    closed = day19_disasm.formula_probe(a, b, c)
    assert {(x, y) for y in range(50) for x in range(50) if closed(x, y)} == real_window


def test_the_rays_never_touch_the_lattice(real_input):
    """disc = C^2 + 4AB is not a perfect square, so the beam's two boundary
    rays have irrational slope and pass through no integer point but (0, 0):
    the program's <= comparisons never actually tie away from the origin."""
    from math import isqrt

    a, b, c = day19_disasm.recover_constants(parse_input(real_input(19)))
    disc = c * c + 4 * a * b
    assert isqrt(disc) ** 2 != disc


def test_static_edges_agree_with_the_formula(real_input):
    """left/right_edge_static are exact: at several depths, the closed-form
    probe flips exactly at the cells the isqrt arithmetic names."""
    a, b, c = day19_disasm.recover_constants(parse_input(real_input(19)))
    closed = day19_disasm.formula_probe(a, b, c)
    for y in (10, 99, 500, 1000):
        lo = day19_disasm.left_edge_static(a, b, c, y)
        hi = day19_disasm.right_edge_static(a, b, c, y)
        assert closed(lo, y) and closed(hi, y)
        assert not closed(lo - 1, y) and not closed(hi + 1, y)


def test_full_listing_accounts_for_every_cell(real_input):
    """The complete listing covers all 424 cells exactly once -- 119
    instruction lines plus the 4 variable cells. `full_listing` asserts
    exact coverage internally (any gap or overlap raises); this pins the
    counts the listing's own header claims."""
    mem = parse_input(real_input(19))
    text = day19_disasm.full_listing(mem)
    assert len(mem) == 424
    rows = [line for line in text.splitlines() if line[:4].isdigit()]
    assert len(rows) == 119 + 4
    assert sum(1 for row in rows if ".var" in row) == 4


def test_static_answers_match_the_live_machine(real_input):
    """Both answers by pure isqrt arithmetic equal both answers by VM probing
    -- Day 17's 'answers off the disk' cross-check, in miniature."""
    mem = parse_input(real_input(19))
    a, b, c = day19_disasm.recover_constants(mem)
    assert day19_disasm.static_part1(a, b, c) == part1(mem)
    assert day19_disasm.static_part2(a, b, c) == part2(mem)


# -------------------------------------------- a second user's file (day19_alt)

# inputs/day19_alt.txt is another user's program -- gitignored like every
# input, so all of these skip on a clone that lacks it. Same 424-cell
# skeleton; different constants; every encoding coin-flip re-rolled.


@pytest.mark.parametrize("day, want", [(19, (76, 100, 17)), ("19_alt", (167, 93, 21))])
def test_recovered_constants(real_input, day, want):
    """Structural recovery reads each file's own constants -- the alt file's
    coin-flips (swapped immediates, jnz/jz spellings, the indirect jump
    reading a different operand cell) must not matter."""
    assert day19_disasm.recover_constants(parse_input(real_input(day))) == want


def test_alt_static_answers_match_the_alt_machine(real_input):
    """The whole pipeline on the foreign file: recovered formula -> isqrt
    edges -> both answers, against that file's live machine."""
    mem = parse_input(real_input("19_alt"))
    a, b, c = day19_disasm.recover_constants(mem)
    assert day19_disasm.static_part1(a, b, c) == part1(mem)
    assert day19_disasm.static_part2(a, b, c) == part2(mem)


def test_only_the_three_constant_sites_carry_meaning(real_input):
    """113 of 424 cells differ between the two files, spread over 49
    instructions -- but splice just the three constant-loading instructions
    (12 cells) from the alt file into this one and the machine IS the alt
    drone. Cell-level splicing is impossible by design: the identity-operand
    shuffle moves the payload between cells (B rides at 123 vs 124, C at 162
    vs 161), so the meaningful unit is the instruction, not the cell --
    [Day 15](day15_disassembly.md)'s three-cells result, one notch harder."""
    mem = parse_input(real_input(19))
    alt = parse_input(real_input("19_alt"))
    assert sum(1 for x, y in zip(mem, alt) if x != y) == 113
    spliced = list(mem)
    for site in (80, 122, 160):
        spliced[site : site + 4] = alt[site : site + 4]
    assert day19_disasm.recover_constants(spliced) == day19_disasm.recover_constants(alt)
    probe = beam_probe(spliced)
    closed = day19_disasm.formula_probe(*day19_disasm.recover_constants(alt))
    assert all(probe(x, y) == closed(x, y) for y in range(0, 50, 7) for x in range(0, 50, 7))


def test_real_input(check_locked):
    check_locked(19, LOCKED)


# ------------------------------------- the decompiled program (day19_program)


@pytest.mark.parametrize("args", [(2, 3, 5), (5, 3, 2), (3, 5, 2), (0, 4, 9), (-3, 7, -2), (1, 1, 1004)])
def test_mul3_is_multiplication(args):
    """The sort-then-telescope routine at 303-423 is a*b*c for any integers:
    b^2 c - b c (b - a) == a b c holds regardless of order or sign."""
    a, b, c = args
    assert day19_program.mul3(*args) == a * b * c


def test_apply_is_an_indirect_call():
    """The trampoline is f(*args), and main's decoy apply(apply, abs, v) is
    two unwinds to abs(v)."""
    assert day19_program.apply(day19_program.mul3, 2, 3, 7) == 42
    assert day19_program.apply(day19_program.apply, day19_program.abs_, -9) == 9


def test_reject_neg_halts_with_zero():
    assert day19_program.reject_neg(5) == 5
    with pytest.raises(day19_program.Halt) as halted:
        day19_program.reject_neg(-1)
    assert halted.value.output == 0


@pytest.mark.parametrize("day", [19, "19_alt"])
def test_python_drone_matches_the_vm(real_input, day):
    """drone(x, y) from the decompilation agrees with the live Intcode on the
    full 50x50 window and on bands straddling both beam edges at depth --
    the same probe set as day19_disasm's pass 3."""
    mem = parse_input(real_input(day))
    a, b, c = day19_disasm.recover_constants(mem)
    vm, py = beam_probe(mem), day19_program.drone_from_program(mem)
    window = [(x, y) for y in range(50) for x in range(50)]
    bands = [
        (x, y)
        for y in (500, 1000)
        for edge in (day19_disasm.left_edge_static(a, b, c, y), day19_disasm.right_edge_static(a, b, c, y))
        for x in range(edge - 5, edge + 6)
    ]
    assert all(py(x, y) == int(vm(x, y)) for x, y in window + bands)


@pytest.mark.parametrize("x, y", [(-1, 5), (5, -1), (-1, -1)])
def test_python_drone_rejects_negatives_like_the_machine(real_input, x, y):
    """The real machine answers 0 and halts on a negative coordinate
    (reject_neg, 282-302); beam_probe refuses before the VM runs, so drive
    the VM directly here."""
    from intcode import VM

    vm = VM(parse_input(real_input(19)))
    vm.inputs.extend((x, y))
    outputs = []
    while (result := vm.step()) != "halted":
        if isinstance(result, tuple):
            outputs.append(result[1])
    assert outputs == [0]
    assert day19_program.drone_from_program(parse_input(real_input(19)))(x, y) == 0


@pytest.mark.parametrize("day", [19, "19_alt"])
def test_python_drone_answers_match_the_machine(real_input, day):
    """End to end: the decompiled drone, driven by the very same count_beam /
    find_square as the shipping solution, yields both answers the Intcode
    machine does -- on both users' files."""
    mem = parse_input(real_input(day))
    drone = day19_program.drone_from_program(mem)

    def py(x: int, y: int) -> bool:
        return bool(drone(x, y))

    x, y = find_square(py, 100)
    assert (count_beam(py, 50), 10000 * x + y) == (part1(mem), part2(mem))
