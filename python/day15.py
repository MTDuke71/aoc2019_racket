"""AoC 2019 Day 15 — Oxygen System.

The Intcode machine is unchanged (it froze at Day 9; see python/intcode.py).
What is new is the *shape of the interface*: for the first time the program is
not a source of data but a **hidden world behind a keyhole**. You may ask it
exactly one question -- "may I step north?" -- and the only reply is 0/1/2. The
droid has a position, and that position is state you cannot set, only walk.

That single constraint is the whole day:

  * You cannot BFS the maze directly. BFS wants to jump to an arbitrary frontier
    cell each iteration, and there is no teleport instruction. What you *can* do
    cheaply is take one step and take it back, so the natural traversal is
    DEPTH-FIRST SEARCH WITH AN EXPLICIT BACKTRACK STACK -- the stack holds the
    moves that got you here, and popping one means physically walking it in
    reverse.
  * A wall probe is free of charge: status 0 means the droid did *not* move, so
    you learn a cell without paying a step to undo.
  * In general the path DFS happens to take to the oxygen is not the shortest
    one, so the walk is a MAPPING phase rather than a search; once the map is a
    plain dict[(x, y)] -> tile, both parts are ordinary BFS over that dict, and
    they differ only in where the BFS is rooted.

Separating those two phases -- explore once, then reason offline -- is what
keeps the day honest. Fusing them (trying to make the droid's own walk report
the distance) is where this puzzle eats an evening.

On THIS input the two happen to agree, because the maze turns out to be a tree
(799 open squares, 798 edges) and a tree has exactly one simple path between
any two cells. That is a property of the file, not of the puzzle -- the maze is
stored in the program as a table of edge bits, 399 passages over 400 cells, a
spanning tree by construction. See Problem_Statements/days/day15_disassembly.md.
Leaning on it would be betting on the input, so the code does not.

Run:  python python/day15.py
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

from intcode import VM

# Reply codes from the droid, which double as our tile ids: the status the
# program hands back for a move *is* the contents of the target cell.
WALL, OPEN, OXYGEN = 0, 1, 2

# Movement commands. The numbering is the puzzle's, and note that it is NOT
# the usual clockwise order -- 1/2/3/4 is north/south/west/east, i.e. the two
# axes paired up, which is why `BACK` is a table and not `(d + 2) % 4`.
NORTH, SOUTH, WEST, EAST = 1, 2, 3, 4
MOVES = {NORTH: (0, -1), SOUTH: (0, 1), WEST: (-1, 0), EAST: (1, 0)}
BACK = {NORTH: SOUTH, SOUTH: NORTH, WEST: EAST, EAST: WEST}

Point = tuple[int, int]


def parse_input(text: str) -> list[int]:
    return [int(t) for t in text.strip().split(",")]


def _ahead(pos: Point, command: int) -> Point:
    dx, dy = MOVES[command]
    return (pos[0] + dx, pos[1] + dy)


def _move(vm: VM, command: int) -> int:
    """Send one movement command; return the status code.

    One request, one reply -- the program's loop is strictly synchronous, so we
    can run the VM to its next output and stop there rather than framing a
    stream the way Day 13 had to.
    """
    vm.inputs.append(command)
    while True:
        result = vm.step()
        if isinstance(result, tuple):
            return result[1]
        if result == "halted":
            raise RuntimeError("droid program halted mid-walk")


def explore(droid: VM) -> tuple[dict[Point, int], Point]:
    """Walk the whole maze and return (map, oxygen position).

    Iterative DFS. `trail` is the list of commands taken from the origin to the
    droid's current cell; it is simultaneously the recursion stack and the route
    home, which is the point -- in an embodied search those are the same object.

    Loop invariant: `grid` holds every cell whose status we have observed, and
    the droid stands at the cell reached by following `trail` from (0, 0). Each
    iteration either discovers an unseen neighbour (extending `trail` on a step,
    leaving it alone on a wall) or, finding none, retreats one link. Every cell
    is stepped into at most once and retreated from at most once, so the walk
    costs at most 2 moves per open cell and terminates with `trail` empty only
    after the entire reachable component is known.

    `droid` is anything answering the VM protocol -- `.inputs` and `.step()`.
    Taking the machine rather than the program is what lets the test module hand
    in an ASCII-maze stand-in and exercise this walk against the puzzle's own
    worked example, which ships no Intcode program at all.
    """
    grid: dict[Point, int] = {(0, 0): OPEN}
    pos: Point = (0, 0)
    oxygen: Point | None = None
    trail: list[int] = []

    while True:
        unseen = next((d for d in MOVES if _ahead(pos, d) not in grid), None)

        if unseen is None:  # dead end (or fully-charted junction): back out
            if not trail:
                break
            command = BACK[trail.pop()]
            _move(droid, command)
            pos = _ahead(pos, command)
            continue

        target = _ahead(pos, unseen)
        status = _move(droid, unseen)
        grid[target] = status
        if status != WALL:  # a wall probe costs nothing and moves nothing
            pos = target
            trail.append(unseen)
            if status == OXYGEN:
                oxygen = target

    if oxygen is None:
        raise RuntimeError("explored the whole maze without finding the oxygen system")
    return grid, oxygen


def distances(grid: dict[Point, int], start: Point) -> dict[Point, int]:
    """BFS over the charted maze: every reachable cell -> its step count.

    Unit edge weights, so the first time BFS reaches a cell it reaches it by a
    shortest path. Unknown cells default to WALL, which is safe because
    `explore` leaves nothing reachable uncharted.
    """
    dist = {start: 0}
    queue = deque([start])
    while queue:
        here = queue.popleft()
        for command in MOVES:
            there = _ahead(here, command)
            if there in dist or grid.get(there, WALL) == WALL:
                continue
            dist[there] = dist[here] + 1
            queue.append(there)
    return dist


def render(grid: dict[Point, int]) -> str:
    """The charted maze as text: `#` wall, `.` open, `O` oxygen, `D` origin."""
    glyph = {WALL: "#", OPEN: ".", OXYGEN: "O"}
    xs = [x for x, _ in grid]
    ys = [y for _, y in grid]
    rows = []
    for y in range(min(ys), max(ys) + 1):
        rows.append(
            "".join(
                "D" if (x, y) == (0, 0) else glyph.get(grid.get((x, y)), " ")
                for x in range(min(xs), max(xs) + 1)
            )
        )
    return "\n".join(rows)


def part1(program: list[int]) -> int:
    """Fewest movement commands from the droid's start to the oxygen system.

    Not the length of the walk the droid actually took. On this input the two
    happen to coincide -- the maze turns out to be a tree, so the DFS trail is
    the unique simple path -- but nothing in the statement promises that, and a
    single loop in the maze would break it silently. Hence: map, then search.
    """
    grid, oxygen = explore(VM(program))
    return distances(grid, (0, 0))[oxygen]


def part2(program: list[int]) -> int:
    """Minutes for oxygen to fill the region, starting from the repaired system.

    "One minute to spread to every adjacent open location" is precisely one BFS
    layer, so the fill time is the number of layers -- the ECCENTRICITY of the
    oxygen cell, `max` over the distance map rooted there. No simulation loop is
    needed: a flood fill and a breadth-first search are the same traversal, and
    the minute counter is the level number BFS already computes.
    """
    grid, oxygen = explore(VM(program))
    return max(distances(grid, oxygen).values())


def solve(program: list[int]) -> tuple[int, int]:
    """Both answers from ONE exploration.

    `part1` and `part2` each explore independently, because the test and bench
    harnesses require parts that can be called in isolation -- sharing state
    between them is exactly the coupling those harnesses exist to prevent. But
    the walk is 99% of the cost (65 ms against 0.58 ms for a BFS) and the two
    parts differ only in where the BFS is rooted, so anything that wants both
    answers should ask here and pay for the droid once.
    """
    grid, oxygen = explore(VM(program))
    return distances(grid, (0, 0))[oxygen], max(distances(grid, oxygen).values())


def main() -> None:
    text = (Path(__file__).resolve().parent.parent / "inputs" / "day15.txt").read_text()
    program = parse_input(text)

    grid, oxygen = explore(VM(program))
    print(render(grid))

    walls = sum(1 for tile in grid.values() if tile == WALL)
    print(f"\n  charted {len(grid)} cells: {len(grid) - walls} open, {walls} wall")
    print(f"  oxygen system at {oxygen}")
    print(f"  part 1: {distances(grid, (0, 0))[oxygen]}")
    print(f"  part 2: {max(distances(grid, oxygen).values())}")


if __name__ == "__main__":
    main()
