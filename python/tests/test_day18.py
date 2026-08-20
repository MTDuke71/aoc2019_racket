r"""Day 18 -- Many-Worlds Interpretation.

The statement ships five Part One examples (8 / 86 / 132 / 136 / 81 steps),
parametrized below. The interesting tests are the ones pinning the two claims
the solver's structure rests on, neither of which the examples exercise:

  * Condensing the grid to an entrance/key/door graph loses no routes, and
    cutting a stride at the first uncollected key loses no optimal walk.
    Pinned by `oracle` -- a breadth-first search over (positions, key mask)
    states on the RAW GRID, transcribed straight from the rules with no
    condensation and no strides -- which must agree with `min_steps` on
    every map small enough to grind (`test_part1_matches_the_oracle`,
    `test_part2_matches_the_oracle_on_a_four_vault_map`).
  * Keeping doors as VERTICES of the condensed graph (rather than as
    annotations on key-to-key edges) is what makes the solver exact on maps
    with cycles. `test_detour_around_a_locked_door` is a map where every
    key's geodesic from `@` crosses door A, yet a longer detour solves it --
    a solver that recorded "the doors on the shortest path" would deadlock
    there, reporting every key locked. The real input is where this stops
    being theoretical: `test_real_maze_is_not_a_tree` shows it has cycles.

Part Two ships four worked examples of its own (8 / 24 / 32 / 72 steps).
Their maps arrive PRE-SPLIT -- four `@`s already in place -- so they run
through `min_steps` directly rather than `part2`, whose job includes the
3x3 rewrite; the rewrite itself is checked by construction
(`test_split_entrance_*`) and end-to-end on the unsplit form of the
statement's own first Part Two map (`test_part2_matches_the_oracle_on_a_four_vault_map`).
"""

from __future__ import annotations

from collections import deque

import day18
import pytest
from day18 import (
    Vault,
    all_keys_mask,
    condense,
    min_steps,
    parse_input,
    part1,
    part2,
    split_entrance,
)

LOCKED = (5450, 2020)  # verified on adventofcode.com

EX1 = """#########
#b.A.@.a#
#########"""

EX2 = """########################
#f.D.E.e.C.b.A.@.a.B.c.#
######################.#
#d.....................#
########################"""

EX3 = """########################
#...............b.C.D.f#
#.######################
#.....@.a.B.c.d.A.e.F.g#
########################"""

EX4 = """#################
#i.G..c...e..H.p#
########.########
#j.A..b...f..D.o#
########@########
#k.E..a...g..B.n#
########.########
#l.F..d...h..C.m#
#################"""

EX5 = """########################
#@..............ac.GI.b#
###d#e#f################
###A#B#C################
###g#h#i################
########################"""

EXAMPLES = [(EX1, 8), (EX2, 86), (EX3, 132), (EX4, 136), (EX5, 81)]


def oracle(vault: Vault) -> int:
    """Fewest steps by brute force: BFS over (positions, mask) on the raw grid.

    A transcription of the rules and nothing else -- every state is a cell
    per robot plus the keys held, every move is one robot one step, a door
    cell is a wall until its key is held, stepping on a key collects it.
    No condensed graph, no strides, no assumption to share with the code
    under test. Exponential in keys, so only small maps can afford it.
    """
    key_bit = {pos: 1 << (ord(ch) - ord("a")) for pos, ch in vault.keys.items()}
    door_bit = {pos: 1 << (ord(ch) - ord("a")) for pos, ch in vault.doors.items()}
    goal = all_keys_mask(vault)
    start = (vault.entrances, 0)
    seen = {start}
    frontier = deque([(*start, 0)])
    while frontier:
        positions, mask, dist = frontier.popleft()
        if mask == goal:
            return dist
        for i, (x, y) in enumerate(positions):
            for nbr in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if nbr not in vault.open_cells or door_bit.get(nbr, 0) & ~mask:
                    continue
                state = (positions[:i] + (nbr,) + positions[i + 1 :], mask | key_bit.get(nbr, 0))
                if state not in seen:
                    seen.add(state)
                    frontier.append((*state, dist + 1))
    raise ValueError("oracle: some key is unreachable")


# ------------------------------------------------------------------- part one


@pytest.mark.parametrize("text, want", EXAMPLES)
def test_part1_examples(text, want):
    assert part1(parse_input(text)) == want


@pytest.mark.parametrize("text, want", [(EX1, 8), (EX2, 86), (EX3, 132), (EX5, 81)])
def test_part1_matches_the_oracle(text, want):
    """Condensation + strides equals brute force over the raw grid.

    EX4 is excluded on cost alone: 16 keys make the oracle's state space
    ~2^16 masks wide, minutes of grinding for no extra coverage.
    """
    assert oracle(parse_input(text)) == want


def test_no_keys_means_no_steps():
    assert part1(parse_input("###\n#@#\n###")) == 0


def test_unreachable_key_raises():
    with pytest.raises(ValueError, match="unreachable"):
        part1(parse_input("#####\n#@#a#\n#####"))


DETOUR = """###########
#@.A.b...a#
#.#######.#
#.........#
###########"""


def test_detour_around_a_locked_door():
    """The map that separates exact solvers from tree-shaped shortcuts.

    Row 1 is @ .. A .. b .. a; the only way into that corridor without key
    `a` is the ring through row 3. The shortest path from @ to EITHER key
    crosses door A (b in 4 steps, a in 8), so a solver that condenses to
    key-to-key edges annotated with "the doors on the shortest path" sees
    both keys locked at the start and deadlocks. With doors as vertices the
    detour survives: down and around to a (12 steps), then back along the
    corridor to b (4 more, or equivalently through the now-open A) -- 16.
    """
    vault = parse_input(DETOUR)
    assert part1(vault) == 16
    assert oracle(vault) == 16
    graph = condense(vault)
    entrance = vault.entrances[0]
    door = next(pos for pos, ch in vault.doors.items() if ch == "a")
    assert (door, 2) in graph[entrance], "sanity: the door really is adjacent-ish to @"


# ------------------------------------------------------------------- part two

# The statement's first Part Two example, in its UNSPLIT form (the statement
# shows this map on both sides of the rewrite arrow) -- exercising the whole
# part2 pipeline, split included, where the pre-split examples below cannot.
FOUR_VAULTS = """#######
#a.#Cd#
##...##
##.@.##
##...##
#cB#Ab#
#######"""

# Part Two's remaining worked examples arrive pre-split -- four @s already in
# place -- so they run through `min_steps` directly rather than `part2`.
P2EX2 = """###############
#d.ABC.#.....a#
######@#@######
###############
######@#@######
#b.....#.....c#
###############"""

P2EX3 = """#############
#DcBa.#.GhKl#
#.###@#@#I###
#e#d#####j#k#
###C#@#@###J#
#fEbA.#.FgHi#
#############"""

P2EX4 = """#############
#g#f.D#..h#l#
#F###e#E###.#
#dCba@#@BcIJ#
#############
#nK.L@#@G...#
#M###N#H###.#
#o#m..#i#jk.#
#############"""


@pytest.mark.parametrize("text, want", [(P2EX2, 24), (P2EX3, 32), (P2EX4, 72)])
def test_part2_examples(text, want):
    assert min_steps(parse_input(text)) == want


def test_part2_examples_match_the_oracle():
    """The 24-step example, ground raw as well.

    The only pre-split example the oracle can afford: the 32- and 72-step
    maps carry 12 and 15 keys, putting the raw-grid state space in the
    millions. Coverage there comes from `min_steps` itself, whose machinery
    the smaller maps already check against the oracle piece by piece.
    """
    assert oracle(parse_input(P2EX2)) == 24


def test_split_entrance_geometry():
    """The 3x3 around @ becomes four sealed entrances.

    ...        @#@
    .@.   ->   ###
    ...        @#@
    """
    vault = parse_input(FOUR_VAULTS)
    assert vault.entrances == ((3, 3),)
    after = split_entrance(vault)
    assert after.entrances == ((2, 2), (2, 4), (4, 2), (4, 4))
    assert (3, 3) not in after.open_cells
    for orthogonal in ((2, 3), (4, 3), (3, 2), (3, 4)):
        assert orthogonal not in after.open_cells
    assert after.keys == vault.keys
    assert after.doors == vault.doors
    # exactly the five rewritten cells disappeared, nothing else moved
    assert vault.open_cells - after.open_cells == {(3, 3), (2, 3), (4, 3), (3, 2), (3, 4)}


def test_split_entrance_refuses_a_cramped_entrance():
    """EX1's @ has walls above and below -- the 3x3 is not open, so refuse."""
    with pytest.raises(ValueError, match="not fully open"):
        split_entrance(parse_input(EX1))


def test_split_entrance_refuses_to_overwrite_a_letter():
    """A key inside the 3x3 would be silently deleted by the rewrite -- refuse."""
    cramped = """#####
#...#
#.@a#
#...#
#####"""
    with pytest.raises(ValueError, match="overwritten"):
        split_entrance(parse_input(cramped))


def test_part2_matches_the_oracle_on_a_four_vault_map():
    """The statement's first Part Two example, run end to end: 8 steps.

    Every door here is opened from a DIFFERENT vault (C top-right vs c
    bottom-left, and so on), so no robot can finish alone: progress is
    robots taking turns while the shared mask catches up. The oracle -- the
    same raw-grid BFS, now over 4-cell position tuples -- must agree with
    `part2`, and both must land on the statement's 8.
    """
    vault = parse_input(FOUR_VAULTS)
    want = oracle(split_entrance(vault))
    assert want == 8
    assert part2(vault) == want


def test_part2_where_one_vault_must_wait_out_a_chain():
    """A dependency chain a -> A -> b -> B -> c spanning three vaults.

    The top-right robot is boxed in behind A, the bottom-right behind B;
    only the top-left robot can move at first, and the bottom-left robot
    never moves at all (its vault holds nothing). The order of pickups is
    completely forced; any interleaving must still sum the same steps.
    """
    chained = """#######
#a.#Ab#
##...##
##.@.##
##...##
#..#Bc#
#######"""
    vault = parse_input(chained)
    want = oracle(split_entrance(vault))
    assert part2(vault) == want


# ------------------------------------------------------------------ the input


def test_crlf():
    r"""A Windows-downloaded input ends `\r\n`; `parse_input` must survive it.

    Constructed here rather than loaded from disk, because `Path.read_text()`
    rewrites CRLF to LF and a fixture-loaded "CRLF case" would assert nothing.
    """
    crlf = EX1.replace("\n", "\r\n") + "\r\n"
    assert parse_input(crlf) == parse_input(EX1)
    assert part1(parse_input(crlf)) == 8


def test_crlf_real_input(real_input):
    """The same, over whatever line ending the real file actually carries."""
    text = real_input(18)
    assert parse_input(text) == parse_input(text.replace("\r\n", "\n"))


def test_real_map_shape(real_input):
    """81x81, all 26 keys, all 26 doors, one entrance dead centre.

    The centred entrance with a fully open 3x3 around it is Part Two's
    precondition -- `split_entrance` would refuse anything else.
    """
    vault = parse_input(real_input(18))
    assert len(vault.entrances) == 1
    assert vault.entrances == ((40, 40),)
    assert sorted(vault.keys.values()) == [chr(c) for c in range(ord("a"), ord("z") + 1)]
    assert sorted(vault.doors.values()) == [chr(c) for c in range(ord("a"), ord("z") + 1)]
    split = split_entrance(vault)  # does not raise
    assert len(split.entrances) == 4


def test_real_maze_is_not_a_tree(real_input):
    """The real maze has cycles -- the doors-as-vertices design is load-bearing.

    3201 open cells and 3204 corridor edges: at least one cycle exists no
    matter how the cells are connected (a forest never has as many edges as
    vertices), so alternate routes around doors are a real feature of this
    input, not a hypothetical.
    """
    vault = parse_input(real_input(18))
    edges = sum(
        1 for (x, y) in vault.open_cells for nbr in ((x + 1, y), (x, y + 1)) if nbr in vault.open_cells
    )
    assert len(vault.open_cells) == 3201
    assert edges == 3204
    assert edges >= len(vault.open_cells)


def _forest_census(cells: set) -> tuple[int, int, int]:
    """(vertices, edges, components) of the grid graph on `cells`; a forest has E == V - C."""
    edges = sum(1 for (x, y) in cells for nbr in ((x + 1, y), (x, y + 1)) if nbr in cells)
    seen: set = set()
    components = 0
    for start in cells:
        if start in seen:
            continue
        components += 1
        seen.add(start)
        stack = [start]
        while stack:
            x, y = stack.pop()
            for nbr in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if nbr in cells and nbr not in seen:
                    seen.add(nbr)
                    stack.append(nbr)
    return len(cells), edges, components


def test_real_cycles_all_sit_in_the_entrance_3x3(real_input):
    """Where those cycles are: all four are the 2x2 blocks of the open 3x3
    around `@`. Delete that 3x3 and what remains is a forest (3192 cells,
    3184 edges, 8 pieces -- each vault touches the block at two cells), and
    Part 2's surgery, which keeps the corners, is a forest of exactly four
    trees. Two things follow. The doors-as-annotations shortcut survives
    THIS input only because its cycles hold no doors; and the split maze is
    literally a tree per vault. (The condensed graph still has cycles -- a
    door-free junction condenses to a clique -- but those are artefacts of
    condensation, not alternate grid routes.)
    """
    vault = parse_input(real_input(18))
    ((ex, ey),) = vault.entrances
    block = {(ex + dx, ey + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    assert block <= vault.open_cells
    v, e, c = _forest_census(vault.open_cells - block)
    assert (v, e, c) == (3192, 3184, 8)
    assert e == v - c
    v, e, c = _forest_census(set(split_entrance(vault).open_cells))
    assert (v, e, c) == (3196, 3192, 4)
    assert e == v - c


def test_solve_agrees_with_the_parts(real_input):
    vault = parse_input(real_input(18))
    assert day18.solve(vault) == (part1(vault), part2(vault))


def test_real_input(check_locked):
    check_locked(18, LOCKED)
