r"""Day 20 -- Donut Maze.

The statement ships two Part One examples (23 and 58 steps), parametrized
below -- and, unusually, it also narrates the 23-step walk leg by leg
("walk from AA to the inner BC portal (4 steps)", and so on). Those legs
are the only ground truth anywhere about which portal tile is INNER and
which is OUTER, so `test_ex1_walk_matches_the_statement_leg_by_leg` pins
the classification to the statement's own words rather than to the
implementation's opinion of itself.

Part Two ships one worked example of its own -- the interleaved EX3, 396
steps diving to level 10 -- and, like Part One, narrates the whole walk.
`test_part2_ex3_walk_matches_the_statement_leg_by_leg` replays all 33
legs: every walking distance, every transit's inner/outer sense, the
final level, and the deepest one. Three further pins predate the unlock
and stand on their own ground truth:

  * The first example's recursive answer must equal its PORTAL-FREE
    shortest path -- the statement itself says that path is 26 steps --
    because every warp shortcut in that maze digs monotonically deeper
    and can never return to level 0 (`test_part2_ex1...`).
  * The second example has no balanced route at all: recursion only ever
    descends, so `part2` must raise, and still raise with the depth cap
    at 50 (`test_part2_ex2_has_no_balanced_route`).
  * WELL is a hand-built donut where the two readings genuinely diverge:
    Part 1's best walk warps through QQ once (unbalanced -- it reaches ZZ
    one level down, where ZZ is just a dead tile) so Part 2 is forced
    through the longer inner-QQ / outer-YY round trip. Both distances are
    derived by hand in the docstring below, not taken from the code.

The real input's depth cap gets its own evidence: the default (27, one
level per portal pair) is a heuristic, so `test_real_depth_cap` shows the
answer is identical at caps 25, 27, and 54 and UNREACHABLE at 24 -- the
recursion genuinely needs 25 nested mazes, and the cap never binds.
"""

from __future__ import annotations

import dataclasses
from collections import deque

import day20
import pytest
from day20 import Maze, parse_input, part1, part2

LOCKED = (442, 5208)  # verified on adventofcode.com

EX1 = """\
         A
         A
  #######.#########
  #######.........#
  #######.#######.#
  #######.#######.#
  #######.#######.#
  #####  B    ###.#
BC...##  C    ###.#
  ##.##       ###.#
  ##...DE  F  ###.#
  #####    G  ###.#
  #########.#####.#
DE..#######...###.#
  #.#########.###.#
FG..#########.....#
  ###########.#####
             Z
             Z
"""

EX2 = """\
                   A
                   A
  #################.#############
  #.#...#...................#.#.#
  #.#.#.###.###.###.#########.#.#
  #.#.#.......#...#.....#.#.#...#
  #.#########.###.#####.#.#.###.#
  #.............#.#.....#.......#
  ###.###########.###.#####.#.#.#
  #.....#        A   C    #.#.#.#
  #######        S   P    #####.#
  #.#...#                 #......VT
  #.#.#.#                 #.#####
  #...#.#               YN....#.#
  #.###.#                 #####.#
DI....#.#                 #.....#
  #####.#                 #.###.#
ZZ......#               QG....#..AS
  ###.###                 #######
JO..#.#.#                 #.....#
  #.#.#.#                 ###.#.#
  #...#..DI             BU....#..LF
  #####.#                 #.#####
YN......#               VT..#....QG
  #.###.#                 #.###.#
  #.#...#                 #.....#
  ###.###    J L     J    #.#.###
  #.....#    O F     P    #.#...#
  #.###.#####.#.#####.#####.###.#
  #...#.#.#...#.....#.....#.#...#
  #.#####.###.###.#.#.#########.#
  #...#.#.....#...#.#.#.#.....#.#
  #.###.#####.###.###.#.#.#######
  #.#.........#...#.............#
  #########.###.###.#############
           B   J   C
           U   P   P
"""

# A hand-built donut whose ring corridor is CUT at (3,6) and (13,6) into a
# top arc (holding AA, inner XX, inner QQ) and a bottom arc (holding ZZ,
# outer XX, outer QQ, outer YY, inner YY). No portal-free route exists.
#
# Part 1 by hand: AA(8,2) -> (8,3) -> inner QQ(8,4) is 2 steps; warp to
# outer QQ(2,10) is 3; then (3,10), three tiles down to (3,13), five tiles
# right to (8,13), and up into ZZ(8,14): 3 + 1 + 3 + 5 + 1 = 13 steps.
# That walk warps DOWN once and never back up, so recursively it ends at
# ZZ on level 1 -- a dead tile -- and Part 2 must balance the books:
# AA -> inner QQ (2), warp down to outer QQ at level 1 (3), (3,10) (4),
# then the long way round the bottom arc to outer YY(14,8) -- down 3,
# right 10, up 5, one more into (14,8): 19 steps (23) -- warp UP to inner
# YY(10,12) at level 0 (24), and 4 tiles to ZZ: (10,13),(9,13),(8,13),
# (8,14) = 28 steps. The rival route through XX first is 4 steps to inner
# XX + warp + the longer walk from (2,8): 32. So part1 = 13, part2 = 28.
WELL = """\
        A
        A
  ######.######
  #...........#
  #.##.#.####.#
  #.# X Q   #.#
  ### X Q   ###
  #.#       #.#
XX..#       #..YY
  #.#       #.#
QQ..#     Y #.#
  #.#     Y #.#
  #.######.##.#
  #...........#
  ######.######
        Z
        Z
"""

# Part Two's own worked example: 13 portal pairs, interleaved so the
# shortest route dives to level 10 and resurfaces twice. From day20.md.
EX3 = """\
             Z L X W       C
             Z P Q B       K
  ###########.#.#.#.#######.###############
  #...#.......#.#.......#.#.......#.#.#...#
  ###.#.#.#.#.#.#.#.###.#.#.#######.#.#.###
  #.#...#.#.#...#.#.#...#...#...#.#.......#
  #.###.#######.###.###.#.###.###.#.#######
  #...#.......#.#...#...#.............#...#
  #.#########.#######.#.#######.#######.###
  #...#.#    F       R I       Z    #.#.#.#
  #.###.#    D       E C       H    #.#.#.#
  #.#...#                           #...#.#
  #.###.#                           #.###.#
  #.#....OA                       WB..#.#..ZH
  #.###.#                           #.#.#.#
CJ......#                           #.....#
  #######                           #######
  #.#....CK                         #......IC
  #.###.#                           #.###.#
  #.....#                           #...#.#
  ###.###                           #.#.#.#
XF....#.#                         RF..#.#.#
  #####.#                           #######
  #......CJ                       NM..#...#
  ###.#.#                           #.###.#
RE....#.#                           #......RF
  ###.###        X   X       L      #.#.#.#
  #.....#        F   Q       P      #.#.#.#
  ###.###########.###.#######.#########.###
  #.....#...#.....#.......#...#.....#.#...#
  #####.#.###.#######.#######.###.###.#.#.#
  #.......#.......#.#.#.#.#...#...#...#.#.#
  #####.###.#####.#.#.#.#.###.###.#.###.###
  #.......#.....#.#...#...............#...#
  #############.#.#.###.###################
               A O F   N
               A A D   M
"""


def walk_dist(maze: Maze, source, target) -> int:
    """Plain walking BFS, warps ignored -- the statement's 'N steps' legs."""
    seen = {source}
    frontier = deque([(source, 0)])
    while frontier:
        (x, y), dist = frontier.popleft()
        if (x, y) == target:
            return dist
        for nbr in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if nbr in maze.open_tiles and nbr not in seen:
                seen.add(nbr)
                frontier.append((nbr, dist + 1))
    raise AssertionError(f"{target} not reachable from {source} on foot")


# ------------------------------------------------------------------- part one


@pytest.mark.parametrize("text, want", [(EX1, 23), (EX2, 58)])
def test_part1_examples(text, want):
    assert part1(parse_input(text)) == want


def test_ex1_structure():
    maze = parse_input(EX1)
    assert sorted(maze.labels) == ["AA", "BC", "DE", "FG", "ZZ"]
    assert len(maze.labels["AA"]) == len(maze.labels["ZZ"]) == 1
    for portal in ("BC", "DE", "FG"):
        assert len(maze.labels[portal]) == 2
    # 3 pairs = 6 warp tiles, each pointing at its twin with the deltas
    # summing to zero (one descent, one ascent per pair).
    assert len(maze.warps) == 6
    for tile, (dest, delta) in maze.warps.items():
        back, back_delta = maze.warps[dest]
        assert back == tile
        assert delta + back_delta == 0


def test_ex1_walk_matches_the_statement_leg_by_leg():
    """The statement's narrated 23-step walk, leg by leg.

    'Walk from AA to the inner BC portal (4 steps), warp (1), walk to the
    inner DE (6), warp (1), walk to the outer FG (4), warp (1), walk to
    ZZ (6).' Each leg is a plain walking distance, and each named portal
    end is a claim about which tile is inner (+1) and which outer (-1) --
    the only external check on the classification anywhere in the puzzle.
    """
    maze = parse_input(EX1)

    def tile_of(label: str, sense: int):
        (candidate,) = [t for t in maze.labels[label] if maze.warps[t][1] == sense]
        return candidate

    inner_bc, inner_de = tile_of("BC", +1), tile_of("DE", +1)
    outer_bc, outer_de, outer_fg = tile_of("BC", -1), tile_of("DE", -1), tile_of("FG", -1)
    legs = [
        (maze.start, inner_bc, 4),
        (outer_bc, inner_de, 6),
        (outer_de, outer_fg, 4),
        (maze.warps[outer_fg][0], maze.end, 6),
    ]
    for source, target, want in legs:
        assert walk_dist(maze, source, target) == want
    assert sum(want for _, _, want in legs) + 3 == 23  # three warps at 1 step each


def test_parse_rejects_a_label_touching_two_open_tiles():
    with pytest.raises(ValueError, match="touches 2 open tiles"):
        parse_input(".XX.")


def test_parse_rejects_a_maze_without_aa():
    with pytest.raises(ValueError, match="exactly one AA"):
        parse_input("ZZ.")


# ------------------------------------------------------------------- part two


def test_part2_ex1_is_the_portal_free_path():
    """Recursively, example 1's answer is its portal-free walk: 26 steps.

    The statement gives 26 itself ('down 1, right 8, down 12, left 4, and
    down 1... a total of 26 steps'). Every portal shortcut here descends
    -- the 23-step walk transits inner BC, inner DE, inner FG and ends at
    ZZ three levels deep -- so no warp ever pays for itself and the
    surface walk stands. Pinned by stripping the warps and re-running
    part1: the recursive answer must equal it exactly.
    """
    maze = parse_input(EX1)
    portal_free = part1(dataclasses.replace(maze, warps={}))
    assert portal_free == 26
    assert part2(maze) == 26


def test_part2_ex2_has_no_balanced_route():
    maze = parse_input(EX2)
    with pytest.raises(ValueError, match="no route"):
        part2(maze)
    with pytest.raises(ValueError, match="within 50 nested mazes"):
        part2(maze, max_depth=50)


def test_part2_ex3():
    assert part2(parse_input(EX3)) == 396  # the statement's own total


# The statement's narrated walk, one row per "Walk from X to Y (N steps)":
# (destination label, walking steps, then the transit -- +1 "Recurse into",
# -1 "Return to", 0 for the final portal-less walk to ZZ).
# fmt: off
EX3_LEGS = [
    ("XF", 16, +1), ("CK", 10, +1), ("ZH", 14, +1), ("WB", 10, +1),
    ("IC", 10, +1), ("RF", 10, +1), ("NM", 8, +1), ("LP", 12, +1),
    ("FD", 24, +1), ("XQ", 8, +1), ("WB", 4, -1), ("ZH", 10, -1),
    ("CK", 14, -1), ("XF", 10, -1), ("OA", 14, -1), ("CJ", 8, -1),
    ("RE", 8, -1), ("IC", 4, +1), ("RF", 10, +1), ("NM", 8, +1),
    ("LP", 12, +1), ("FD", 24, +1), ("XQ", 8, +1), ("WB", 4, -1),
    ("ZH", 10, -1), ("CK", 14, -1), ("XF", 10, -1), ("OA", 14, -1),
    ("CJ", 8, -1), ("RE", 8, -1), ("XQ", 14, -1), ("FD", 8, -1),
    ("ZZ", 18, 0),
]
# fmt: on


def test_part2_ex3_walk_matches_the_statement_leg_by_leg():
    """Replay Part Two's narrated 396-step walk, leg by leg.

    The same treatment example 1's walk got, at scale: each walking leg
    is checked as a plain warp-blind BFS distance to the inner (+1) or
    outer (-1) end the narration names, each transit costs 1, and the
    books must close exactly -- 364 walked + 32 warped = 396, ending at
    ZZ on level 0 after touching level 10 and resurfacing twice. This
    pins the inner/outer classification across all 13 pairs of a maze
    the bounding-box rule never saw before, against the statement's own
    words rather than the implementation's opinion of itself.
    """
    maze = parse_input(EX3)
    pos, level, total, deepest = maze.start, 0, 0, 0
    for label, steps, sense in EX3_LEGS:
        if sense == 0:
            target = maze.end
        else:
            (target,) = (t for t in maze.labels[label] if maze.warps[t][1] == sense)
        assert walk_dist(maze, pos, target) == steps, (label, steps)
        total += steps
        if sense == 0:
            pos = target
        else:
            pos = maze.warps[target][0]
            level += sense
            deepest = max(deepest, level)
            total += 1
    assert (total, level, deepest) == (396, 0, 10)
    assert part2(maze) == total


def test_well_part1():
    assert part1(parse_input(WELL)) == 13  # hand count in the WELL comment


def test_well_part2_must_balance_its_warps():
    """13 flat vs 28 recursive -- the smallest map where the readings split.

    Part 1's walk ends one level deep, so Part 2 pays for a round trip:
    down through QQ, around the bottom arc at level 1, back up through
    YY. Both numbers are counted tile by tile in the WELL comment above.
    """
    maze = parse_input(WELL)
    assert part2(maze) == 28
    # With descent forbidden outright there is no route at all: the two
    # arcs only meet through portals, and every portal move needs a level.
    with pytest.raises(ValueError, match="within 0 nested mazes"):
        part2(maze, max_depth=0)


# ------------------------------------------------------------------ the input


def test_crlf():
    r"""A Windows-downloaded input ends `\r\n`; `parse_input` must survive it.

    Constructed here rather than loaded from disk, because `Path.read_text()`
    rewrites CRLF to LF and a fixture-loaded "CRLF case" would assert nothing.
    Leading spaces are semantic in this maze (they position the labels), so
    the CRLF guard must be `splitlines()`, never a per-line `.strip()`.
    """
    crlf = EX1.replace("\n", "\r\n")
    assert parse_input(crlf) == parse_input(EX1)
    assert part1(parse_input(crlf)) == 23


def test_crlf_real_input(real_input):
    """The same, over whatever line ending the real file actually carries."""
    text = real_input(20)
    assert parse_input(text) == parse_input(text.replace("\r\n", "\n"))


def test_real_maze_shape(real_input):
    """109x109 donut, 3868 open tiles, 27 portal pairs plus AA and ZZ.

    AA sits on the bottom rim and ZZ on the left rim -- both are rim
    OPENINGS, not warps, so `warps` holds exactly the 54 paired tiles.
    Six open tiles are unreachable from AA even flat: decorative dead
    pockets, which is why `part1` counts distance, never coverage.
    """
    maze = parse_input(real_input(20))
    assert len(maze.open_tiles) == 3868
    assert len(maze.labels) == 29
    assert len(maze.warps) == 54
    assert maze.start == (73, 106)
    assert maze.end == (2, 77)
    xs = [x for x, _ in maze.open_tiles]
    ys = [y for _, y in maze.open_tiles]
    assert (min(xs), max(xs), min(ys), max(ys)) == (2, 106, 2, 106)
    for tile, (dest, delta) in maze.warps.items():
        assert maze.warps[dest] == (tile, -delta)

    seen = {maze.start}
    frontier = deque([maze.start])
    while frontier:
        x, y = frontier.popleft()
        for nbr in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if nbr in maze.open_tiles and nbr not in seen:
                seen.add(nbr)
                frontier.append(nbr)
        if (x, y) in maze.warps:
            dest = maze.warps[(x, y)][0]
            if dest not in seen:
                seen.add(dest)
                frontier.append(dest)
    assert len(maze.open_tiles) - len(seen) == 6


def test_real_depth_cap(real_input):
    """The default cap (27 = one level per pair) is heuristic; show it holds.

    The recursion genuinely needs 25 nested mazes -- at 24 there is no
    route at all -- and past that the answer is cap-invariant: 25, the
    default 27, and 54 all agree. Deeper copies only ever add steps, so
    a binding cap would announce itself here, not silently mis-answer.
    """
    maze = parse_input(real_input(20))
    with pytest.raises(ValueError, match="within 24 nested mazes"):
        part2(maze, max_depth=24)
    at_25 = part2(maze, max_depth=25)
    assert part2(maze) == at_25
    assert part2(maze, max_depth=54) == at_25


def test_solve_agrees_with_the_parts(real_input):
    maze = parse_input(real_input(20))
    assert day20.solve(maze) == (part1(maze), part2(maze))


def test_real_input(check_locked):
    check_locked(20, LOCKED)
