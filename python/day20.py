"""AoC 2019 Day 20 -- Donut Maze.

A maze drawn as a donut: walls, corridors, and two-letter labels stuck to
the outer rim and the inner hole. Each labelled pair of tiles is a portal;
`AA` and `ZZ` are the start and the end. Part 1 asks for the shortest walk
from `AA` to `ZZ`. Part 2 reinterprets the same picture recursively: an
inner portal descends into a nested copy of the maze, an outer portal
climbs back out, and only the outermost copy has a working `AA` and `ZZ`.

The right reading: BOTH PARTS ARE ONE BFS, ON DIFFERENT GRAPHS.

  * Part 1 is breadth-first search over tiles, where a portal tile simply
    has a fifth neighbour -- its twin, one step away. Nothing else about
    portals matters once the parse has paired them up.
  * Part 2 is the same BFS over states (tile, level). A warp now carries a
    level delta: +1 through an inner portal (deeper), -1 through an outer
    one (back out), and an outer portal at level 0 is a wall. The maze
    layers are IDENTICAL from level 1 down -- level 0 is the only special
    layer -- so this is shortest reachability in an infinite periodic
    graph, or in automata vocabulary a ONE-COUNTER SYSTEM: the level is a
    unary counter the walk increments and decrements, and `ZZ` accepts
    only at counter zero. BFS handles it because the counter enters the
    state, not the graph.

The infinite counter needs a floor under termination: a maze with no
balanced route (the statement's second example, in the recursive reading)
would otherwise let BFS descend forever. `part2` caps the depth at the
number of portal pairs -- a heuristic bound, not a theorem, so the cap is
a keyword the tests can raise: test_day20.py shows that doubling it
changes no answer on the real input, which is the evidence the cap never
binds where it matters.

Parsing is the only fussy part of the day. Labels are two letters read
left-to-right or top-to-bottom; the portal tile is the one open tile the
pair touches; a portal is OUTER exactly when its tile lies on the bounding
box of all open tiles (the corridor pokes through the rim wall only at
portals, so rim tiles sit where walls otherwise would). Leading spaces are
load-bearing -- they position the labels -- so lines must never be
stripped; `splitlines()` alone is the CRLF guard.

Run:  python python/day20.py
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path

Pos = tuple[int, int]


@dataclass(frozen=True)
class Maze:
    """The parsed donut: geometry plus the portal structure.

    `warps` is the whole day in one dict: portal tile -> (landing tile,
    level delta), where the delta is +1 leaving an inner portal and -1
    leaving an outer one. Part 1 ignores the delta; Part 2 is defined by
    it. `labels` keeps tile positions per label purely for tests and
    introspection -- nothing in the solving path reads it.
    """

    open_tiles: frozenset[Pos]
    start: Pos
    end: Pos
    warps: dict[Pos, tuple[Pos, int]]
    labels: dict[str, tuple[Pos, ...]]


def parse_input(text: str) -> Maze:
    """Full parse: open tiles, start, end, and every warp with its level delta.

    `splitlines()` handles CRLF; beyond that lines are consumed exactly as
    written -- no stripping, because a label's meaning is its coordinates.
    Every structural promise the solver relies on is checked here: `AA`
    and `ZZ` label exactly one tile each, every other label exactly two,
    one on the outer rim and one on the hole. A maze violating any of
    those raises rather than warping somewhere quietly wrong.
    """
    grid: dict[Pos, str] = {}
    for y, line in enumerate(text.splitlines()):
        for x, ch in enumerate(line):
            if ch != " ":
                grid[(x, y)] = ch

    open_tiles = frozenset(pos for pos, ch in grid.items() if ch == ".")
    if not open_tiles:
        raise ValueError("no open tiles in the maze")
    min_x = min(x for x, _ in open_tiles)
    max_x = max(x for x, _ in open_tiles)
    min_y = min(y for _, y in open_tiles)
    max_y = max(y for _, y in open_tiles)

    def is_outer(pos: Pos) -> bool:
        x, y = pos
        return x in (min_x, max_x) or y in (min_y, max_y)

    # A label is a letter whose right or down neighbour is also a letter --
    # the second letter of a pair never starts one, since ITS next cell is
    # floor, wall, or void. The portal tile is whichever end of the
    # three-in-a-row is open.
    tiles_by_label: dict[str, list[Pos]] = {}
    for (x, y), ch in grid.items():
        if not ch.isalpha():
            continue
        for dx, dy in ((1, 0), (0, 1)):
            second = grid.get((x + dx, y + dy), " ")
            if not second.isalpha():
                continue
            label = ch + second
            ends = [(x - dx, y - dy), (x + 2 * dx, y + 2 * dy)]
            tiles = [pos for pos in ends if pos in open_tiles]
            if len(tiles) != 1:
                raise ValueError(f"label {label} at {(x, y)} touches {len(tiles)} open tiles, not 1")
            tiles_by_label.setdefault(label, []).append(tiles[0])

    for terminal in ("AA", "ZZ"):
        if len(tiles_by_label.get(terminal, [])) != 1:
            raise ValueError(f"expected exactly one {terminal} tile")
    (start,) = tiles_by_label["AA"]
    (end,) = tiles_by_label["ZZ"]

    warps: dict[Pos, tuple[Pos, int]] = {}
    for label, tiles in tiles_by_label.items():
        if label in ("AA", "ZZ"):
            continue
        if len(tiles) != 2:
            raise ValueError(f"portal {label} labels {len(tiles)} tiles, not 2")
        outers = [pos for pos in tiles if is_outer(pos)]
        if len(outers) != 1:
            raise ValueError(f"portal {label} tiles {tiles} are not one outer + one inner")
        (outer,) = outers
        (inner,) = (pos for pos in tiles if pos != outer)
        warps[inner] = (outer, +1)  # descending: into the nested maze
        warps[outer] = (inner, -1)  # ascending: back toward level 0

    labels = {label: tuple(sorted(tiles)) for label, tiles in sorted(tiles_by_label.items())}
    return Maze(open_tiles, start, end, warps, labels)


def _shortest(maze: Maze, *, recursive: bool, max_depth: int = 0) -> int:
    """BFS over (tile, level); flat mode pins the level at 0 forever.

    Every edge costs 1 -- a walking step and a portal transit are both
    "a single step" in the statement -- so plain BFS is exact and the
    first time `ZZ` is popped at level 0 is the answer. In recursive mode
    an outer warp at level 0 is skipped (it is a wall there) and an inner
    warp past `max_depth` is skipped (the termination floor); exhausting
    the frontier means no balanced route exists within the cap.
    """
    seen = {(maze.start, 0)}
    frontier = deque([(maze.start, 0, 0)])
    while frontier:
        pos, level, dist = frontier.popleft()
        if pos == maze.end and level == 0:
            return dist
        x, y = pos
        steps = [
            ((nx, ny), level)
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
            if (nx, ny) in maze.open_tiles
        ]
        if pos in maze.warps:
            dest, delta = maze.warps[pos]
            if not recursive:
                steps.append((dest, 0))
            elif 0 <= level + delta <= max_depth:
                steps.append((dest, level + delta))
        for state in steps:
            if state not in seen:
                seen.add(state)
                frontier.append((*state, dist + 1))
    if not recursive:
        raise ValueError("ZZ is unreachable from AA")
    raise ValueError(f"no route from AA to ZZ returns to the outer level within {max_depth} nested mazes")


def part1(maze: Maze) -> int:
    """Shortest AA -> ZZ walk with portals as plain one-step edges."""
    return _shortest(maze, recursive=False)


def part2(maze: Maze, max_depth: int | None = None) -> int:
    """Shortest AA -> ZZ walk in the recursive reading.

    The default depth cap -- one level per portal pair -- is a heuristic
    floor under termination, not a proven bound; the tests double it and
    show every answer unmoved. A maze with no balanced route (recursion
    only ever digs deeper) raises instead of descending forever.
    """
    if max_depth is None:
        max_depth = len(maze.warps) // 2
    return _shortest(maze, recursive=True, max_depth=max_depth)


def solve(maze: Maze) -> tuple[int, int]:
    return part1(maze), part2(maze)


def main() -> None:
    text = (Path(__file__).resolve().parent.parent / "inputs" / "day20.txt").read_text()
    maze = parse_input(text)
    print(f"  maze: {len(maze.open_tiles)} open tiles, {len(maze.warps) // 2} portal pairs + AA/ZZ")
    print(f"  part 1: {part1(maze)}")
    print(f"  part 2: {part2(maze)}")


if __name__ == "__main__":
    main()
