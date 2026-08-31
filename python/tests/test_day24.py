"""Day 24 -- Planet of Discord.

The statement's ground truth for part 1: one example scan stepped through
four minutes (each pinned as a step-function transition), the first layout
that example repeats, and that layout's biodiversity rating 2129920 -- which
also pins the representation itself, since this module's grids ARE their
biodiversity ratings (bit i of the int = tile i of the scan). The
statement's worked arithmetic (16th tile worth 32768, 22nd worth 2097152)
is asserted digit for digit against `parse_input`.

For part 2 the statement gives six worked adjacencies (tiles 19, G, D, E,
14 and N) -- each pinned against `RECURSIVE_NEIGHBORS` -- and the same
example run ten recursive minutes: 99 bugs across depths -5..5, with every
depth's grid printed. All eleven grids are pinned verbatim. (The Part Two
text in day24.md lost Depth 1's bottom row in the copy-paste; the `#####`
now in the file is this suite's verified simulation output, not the
website's rendering.) The structural claims the solution leans on are
pinned too: every non-centre tile has exactly 4 or 8 neighbours, recursive
adjacency is symmetric across levels, and the infestation spreads at most
one level per minute.
"""

from __future__ import annotations

import pytest
from day24 import (
    CENTER,
    NEIGHBOR_MASKS,
    RECURSIVE_NEIGHBORS,
    parse_input,
    part1,
    part2,
    render,
    step,
    step_recursive,
)

LOCKED = (28717468, 2014)  # verified on adventofcode.com

INITIAL = """\
....#
#..#.
#..##
..#..
#....
"""

MINUTE1 = """\
#..#.
####.
###.#
##.##
.##..
"""

MINUTE2 = """\
#####
....#
....#
...#.
#.###
"""

MINUTE3 = """\
#....
####.
...##
#.##.
.##.#
"""

MINUTE4 = """\
####.
....#
##..#
.....
##...
"""

FIRST_REPEAT = """\
.....
.....
.....
#....
.#...
"""


@pytest.mark.parametrize(
    "before, after",
    [(INITIAL, MINUTE1), (MINUTE1, MINUTE2), (MINUTE2, MINUTE3), (MINUTE3, MINUTE4)],
    ids=["minute1", "minute2", "minute3", "minute4"],
)
def test_statement_minutes(before, after):
    assert step(parse_input(before)) == parse_input(after)


def test_statement_first_repeat():
    assert part1(parse_input(INITIAL)) == parse_input(FIRST_REPEAT) == 2129920


def test_statement_biodiversity_arithmetic():
    """The worked example: 16th tile = 32768, 22nd tile = 2097152 points."""
    assert parse_input(FIRST_REPEAT) == 32768 + 2097152
    assert 32768 == 2 ** (16 - 1) and 2097152 == 2 ** (22 - 1)


@pytest.mark.parametrize("text", [INITIAL, MINUTE3, FIRST_REPEAT])
def test_render_round_trips(text):
    assert render(parse_input(text)) == text.strip()


def test_neighbor_masks_shape():
    """Corners see 2 tiles, edges 3, interior 4 -- 80 directed adjacencies."""
    counts = sorted(mask.bit_count() for mask in NEIGHBOR_MASKS)
    assert counts == [2] * 4 + [3] * 12 + [4] * 9
    for i, mask in enumerate(NEIGHBOR_MASKS):
        assert not mask >> i & 1  # no tile neighbours itself
        for j in range(25):
            if mask >> j & 1:
                assert NEIGHBOR_MASKS[j] >> i & 1  # adjacency is symmetric


@pytest.mark.parametrize(
    "text", ["....#\n#..#.\n#..##\n..#..", "....#\n#..#.\n#..##\n..#..\n#...", "....#" * 5]
)
def test_parse_rejects_wrong_shape(text):
    with pytest.raises(ValueError, match="expected a 5x5 scan"):
        parse_input(text)


def test_parse_rejects_garbage_tiles():
    with pytest.raises(ValueError, match="unexpected tile"):
        parse_input(INITIAL.replace(".", "x"))


# ------------------------------------------------------------ part 2: recursion

# The statement's ten-minute recursive run of INITIAL: every depth, verbatim.
# (Depth 1's bottom row is restored from this suite's own verified output --
# see the module docstring.)
AFTER_10_RECURSIVE_MINUTES = {
    -5: "..#..\n.#.#.\n....#\n.#.#.\n..#..",
    -4: "...#.\n...##\n.....\n...##\n...#.",
    -3: "#.#..\n.#...\n.....\n.#...\n#.#..",
    -2: ".#.##\n....#\n....#\n...##\n.###.",
    -1: "#..##\n...##\n.....\n...#.\n.####",
    0: ".#...\n.#.##\n.#...\n.....\n.....",
    1: ".##..\n#..##\n....#\n##.##\n#####",
    2: "###..\n##.#.\n#....\n.#.##\n#.#..",
    3: "..###\n.....\n#....\n#....\n#...#",
    4: ".###.\n#..#.\n#....\n##.#.\n.....",
    5: "####.\n#..#.\n#..#.\n####.\n.....",
}


def ten_minutes() -> dict[int, int]:
    levels = {0: parse_input(INITIAL)}
    for _ in range(10):
        levels = step_recursive(levels)
    return levels


def test_statement_recursive_example():
    """99 bugs after 10 minutes, spread across depths -5..5, grids verbatim."""
    levels = ten_minutes()
    assert sum(mask.bit_count() for mask in levels.values()) == 99
    assert levels == {d: parse_input(text) for d, text in AFTER_10_RECURSIVE_MINUTES.items()}
    assert part2(parse_input(INITIAL), minutes=10) == 99


def test_infestation_spreads_one_level_per_minute():
    """A new level is reachable only through a portal, so depth grows by <= 1."""
    levels = {0: parse_input(INITIAL)}
    for minute in range(1, 11):
        levels = step_recursive(levels)
        assert -minute <= min(levels) and max(levels) <= minute
    assert (min(levels), max(levels)) == (-5, 5)


def test_center_never_infested():
    """The centre is the inner grid, not a tile: no level ever grows a bug there."""
    levels = ten_minutes()
    assert all(not mask >> CENTER & 1 for mask in levels.values())
    assert RECURSIVE_NEIGHBORS[CENTER] == ()
    with pytest.raises(ValueError, match="centre tile must be empty"):
        part2(1 << CENTER)


# The statement's worked adjacencies. Letters A..Y are one level INSIDE the
# numbered tiles 1..25, so from a letter tile a numbered neighbour is delta -1;
# from a numbered tile a lettered neighbour is delta +1.
letter = "ABCDEFGHIJKL?NOPQRSTUVWXY".index


def number(n: int) -> int:
    return n - 1


@pytest.mark.parametrize(
    "tile, want",
    [
        (number(19), {(0, number(14)), (0, number(18)), (0, number(20)), (0, number(24))}),
        (letter("G"), {(0, letter("B")), (0, letter("F")), (0, letter("H")), (0, letter("L"))}),
        (letter("D"), {(-1, number(8)), (0, letter("C")), (0, letter("E")), (0, letter("I"))}),
        (letter("E"), {(-1, number(8)), (0, letter("D")), (-1, number(14)), (0, letter("J"))}),
        (
            number(14),
            {(0, number(9)), (0, number(15)), (0, number(19))} | {(1, letter(ch)) for ch in "EJOTY"},
        ),
        (
            letter("N"),
            {(0, letter("I")), (0, letter("O")), (0, letter("S"))} | {(1, j) for j in range(25)},
        ),
    ],
    ids=["tile19", "tileG", "tileD", "tileE", "tile14", "tileN"],
)
def test_statement_adjacencies(tile, want):
    got = set(RECURSIVE_NEIGHBORS[tile])
    if tile == letter("N"):  # "five tiles within the sub-grid marked ?"
        inner = {pair for pair in got if pair[0] == 1}
        assert len(inner) == 5 and inner <= want
        want = (want - {(1, j) for j in range(25)}) | inner
    assert got == want


def test_recursive_adjacency_shape():
    """4 or 8 neighbours everywhere, and symmetric across level boundaries."""
    for i, pairs in enumerate(RECURSIVE_NEIGHBORS):
        if i == CENTER:
            continue
        assert len(pairs) in (4, 8)
        assert len(set(pairs)) == len(pairs)
        for dd, j in pairs:
            assert (-dd, i) in RECURSIVE_NEIGHBORS[j]

    # The census the guide cites. Degrees: only the four tiles ringing the
    # centre reach 8 (three flat + a whole inner edge). Each junction between
    # adjacent levels carries exactly 20 edges -- 4 corners x2 + 12 edge tiles
    # x1 pointing out equals 4 portal tiles x5 fanning in -- and in-level the
    # graph keeps 72 of the flat 80 directed adjacencies (8 led to the centre).
    degrees = sorted(len(pairs) for i, pairs in enumerate(RECURSIVE_NEIGHBORS) if i != CENTER)
    assert degrees == [4] * 20 + [8] * 4
    by_delta = {dd: 0 for dd in (-1, 0, 1)}
    for pairs in RECURSIVE_NEIGHBORS:
        for dd, _ in pairs:
            by_delta[dd] += 1
    assert by_delta == {-1: 20, 0: 72, 1: 20}


def rho(grid: int) -> tuple[int, int, int, int]:
    """(mu, lam, t, entry): tail length, cycle length, minute of the first
    repeat, and the repeated layout -- Floyd's rho vocabulary for `part1`."""
    seen: dict[int, int] = {}
    t = 0
    while grid not in seen:
        seen[grid] = t
        grid = step(grid)
        t += 1
    return seen[grid], t - seen[grid], t, grid


def test_example_trajectory_is_rho_shaped():
    """The example's first repeat (minute 86) closes a 12-cycle entered at 74."""
    mu, lam, t, entry = rho(parse_input(INITIAL))
    assert (mu, lam, t) == (74, 12, 86)
    assert entry == parse_input(FIRST_REPEAT)


def test_real_trajectory_is_rho_shaped(real_input):
    """The real scan repeats at minute 19: a 13-minute tail into a 6-cycle.

    mu > 0 is the interesting bit -- the first repeated layout is NOT the
    initial scan, so the flat step map is not injective (contrast Day 12,
    where invertibility forced the first repeat to be the start). The
    cycle entry then has two distinct predecessors, one on the tail and
    one on the cycle, exhibited below.
    """
    mu, lam, t, entry = rho(parse_input(real_input(24)))
    assert (mu, lam, t) == (13, 6, 19)
    assert mu > 0
    assert entry == LOCKED[0]

    traj = [parse_input(real_input(24))]
    for _ in range(t):
        traj.append(step(traj[-1]))
    assert traj[t] == traj[mu] == entry
    tail_pred, cycle_pred = traj[mu - 1], traj[t - 1]
    assert tail_pred != cycle_pred and step(tail_pred) == step(cycle_pred)


def test_step_is_not_gf2_linear():
    """No Day 16/22-style operator shortcut exists: step is not additive.

    Bugs on tiles 0 and 2: tile 1 sees two bugs and spawns, but in each
    singleton run it sees one and spawns there too, so the XOR of the two
    runs cancels it. The threshold rule is nonlinear over GF(2), which is
    why 200 minutes is 200 honest steps and not one matrix power.
    """
    a, b = 1 << 0, 1 << 2
    assert step(a ^ b) == 0b10101010  # tiles 1, 3, 5, 7
    assert step(a) ^ step(b) == 0b10101000  # tile 1 cancelled out
    assert step(a ^ b) != step(a) ^ step(b)


def test_extinction_is_a_fixed_point():
    """No bugs, no spawns: the empty board stays empty at every layer of the API."""
    assert step(0) == 0
    assert step_recursive({0: 0}) == {}
    assert step_recursive({}) == {}
    assert part2(0, minutes=5) == 0


# ------------------------------------------------------------------ the input


def test_crlf():
    crlf = INITIAL.replace("\n", "\r\n")
    assert parse_input(crlf) == parse_input(INITIAL)


def test_crlf_real_input(real_input):
    text = real_input(24)
    assert parse_input(text) == parse_input(text.replace("\r\n", "\n"))


def test_real_input(check_locked):
    check_locked(24, LOCKED)
