"""AoC 2019 Day 24 -- Planet of Discord.

A 5x5 Game-of-Life variant (B12/S1 in Golly's rule notation: a bug survives
with exactly one neighbour, an empty tile spawns with one or two) run until
the first repeated layout. The load-bearing observation is about the ANSWER
format: the "biodiversity rating" assigns tile i (row-major) the value 2^i,
which is precisely the value of the grid read as a 25-bit integer. So the
natural state representation -- one int, bit i = tile i -- IS the answer,
and part 1 reduces to Brent/Floyd territory with none of the machinery:
iterate, remember every state in a set, return the first revisit verbatim.

The step function never scans the grid as text. `NEIGHBOR_MASKS[i]` is the
bitmask of tile i's orthogonal neighbours (edge tiles simply have smaller
masks -- the statement's "missing tiles count as empty" falls out for free),
so a neighbour count is one AND plus a popcount, and one minute is 25 of
them over a state space of 2^25.

Part 2 replaces the flat edge condition with a RECURSIVE one: the centre
tile is a portal to an inner 5x5 grid and the whole scan sits in the centre
of an outer one, so the board is a bi-infinite stack of levels and only the
adjacency changed -- the life rule is untouched. `RECURSIVE_NEIGHBORS[i]`
is the flat mask re-derived once with the two portal cases spliced in: a
step off the outer edge lands on ONE tile of the level outside (the four
tiles ringing that level's centre), and a step onto the centre fans out to
FIVE tiles of the level inside (a whole edge row/column). Every tile still
has exactly 4 or 8 neighbours, adjacency stays symmetric, and one minute is
the same count-then-update over a dict of level -> 25-bit mask. Bugs spread
one level per minute at most (a new outermost/innermost level is reachable
only via those portals), so 200 minutes touch about 201 levels -- the
"infinite" board is a lazily-grown dict, and part 2 is a bug census after
200 steps.

Run:  python python/day24.py
"""

from __future__ import annotations

from pathlib import Path

SIZE = 5
TILES = SIZE * SIZE
CENTER = TILES // 2  # tile 12: part 2's portal to the inner level
MINUTES = 200  # part 2: how long the recursive infestation runs
BUG, EMPTY = "#", "."


def _neighbor_masks() -> list[int]:
    masks = []
    for row in range(SIZE):
        for col in range(SIZE):
            mask = 0
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                r, c = row + dr, col + dc
                if 0 <= r < SIZE and 0 <= c < SIZE:
                    mask |= 1 << (r * SIZE + c)
            masks.append(mask)
    return masks


NEIGHBOR_MASKS = _neighbor_masks()


def _recursive_neighbors() -> list[tuple[tuple[int, int], ...]]:
    """Part 2's adjacency: per tile, the (level delta, tile) pairs it touches.

    Level +1 is the grid INSIDE the centre tile (the statement's "level 1"),
    level -1 the grid this one sits in. The four flat cases become:

      * in-bounds, not centre  -> the flat neighbour, delta 0;
      * off the grid           -> one tile of the outer level: the tile on
                                  the corresponding side of ITS centre;
      * onto the centre        -> five tiles of the inner level: the whole
                                  edge row/column facing the direction moved.
    """
    inner_edges = {
        (1, 0): range(SIZE),  # moving down into the centre: inner top row
        (-1, 0): range(TILES - SIZE, TILES),  # moving up: inner bottom row
        (0, 1): range(0, TILES, SIZE),  # moving right: inner left column
        (0, -1): range(SIZE - 1, TILES, SIZE),  # moving left: inner right column
    }
    out: list[tuple[tuple[int, int], ...]] = []
    for row in range(SIZE):
        for col in range(SIZE):
            pairs: list[tuple[int, int]] = []
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                r, c = row + dr, col + dc
                if not 0 <= r < SIZE:
                    pairs.append((-1, CENTER + dr * SIZE))  # tile above/below outer centre
                elif not 0 <= c < SIZE:
                    pairs.append((-1, CENTER + dc))  # tile left/right of outer centre
                elif r * SIZE + c == CENTER:
                    pairs.extend((1, j) for j in inner_edges[dr, dc])
                else:
                    pairs.append((0, r * SIZE + c))
            out.append(tuple(pairs) if row * SIZE + col != CENTER else ())
    return out


RECURSIVE_NEIGHBORS = _recursive_neighbors()


def parse_input(text: str) -> int:
    """The scan as a 25-bit integer: bit row*5+col is set iff that tile has a bug.

    Row-major with increasing bit weights is exactly the statement's
    biodiversity numbering, so this int doubles as the rating.
    """
    rows = [line.strip() for line in text.strip().splitlines()]
    if len(rows) != SIZE or any(len(row) != SIZE for row in rows):
        raise ValueError(f"expected a {SIZE}x{SIZE} scan, got {rows!r}")
    grid = 0
    for i, tile in enumerate(ch for row in rows for ch in row):
        if tile == BUG:
            grid |= 1 << i
        elif tile != EMPTY:
            raise ValueError(f"unexpected tile {tile!r}")
    return grid


def render(grid: int) -> str:
    """The inverse of `parse_input`, for tests and eyeballs."""
    tiles = [BUG if grid >> i & 1 else EMPTY for i in range(TILES)]
    return "\n".join("".join(tiles[r * SIZE : (r + 1) * SIZE]) for r in range(SIZE))


def step(grid: int) -> int:
    """One simultaneous minute: survive on exactly 1, spawn on 1 or 2."""
    new = 0
    for i in range(TILES):
        bugs = (grid & NEIGHBOR_MASKS[i]).bit_count()
        if bugs == 1 or (bugs == 2 and not grid >> i & 1):
            new |= 1 << i
    return new


def part1(grid: int) -> int:
    """Biodiversity of the first layout to appear twice -- i.e. the layout itself."""
    seen = set()
    while grid not in seen:
        seen.add(grid)
        grid = step(grid)
    return grid


def step_recursive(levels: dict[int, int]) -> dict[int, int]:
    """One minute over the level stack; empty levels are never stored.

    New levels appear only one step beyond the current extremes -- an empty
    level's only occupiable tiles are the four around its centre (fed from
    inside) and its outer ring (fed from outside) -- so scanning
    [min-1, max+1] loses nothing.
    """
    if not levels:  # extinction: the empty board is a fixed point
        return {}
    new: dict[int, int] = {}
    for depth in range(min(levels) - 1, max(levels) + 2):
        grid, mask = levels.get(depth, 0), 0
        for i in range(TILES):
            bugs = sum(levels.get(depth + dd, 0) >> j & 1 for dd, j in RECURSIVE_NEIGHBORS[i])
            if bugs == 1 or (bugs == 2 and not grid >> i & 1):
                mask |= 1 << i
        if mask:
            new[depth] = mask
    return new


def part2(grid: int, minutes: int = MINUTES) -> int:
    """Total bugs after `minutes` on the recursive board seeded at level 0."""
    if grid >> CENTER & 1:
        raise ValueError("the scan's centre tile must be empty -- it is the inner grid")
    levels = {0: grid}
    for _ in range(minutes):
        levels = step_recursive(levels)
    return sum(mask.bit_count() for mask in levels.values())


def solve(grid: int) -> tuple[int, int]:
    return part1(grid), part2(grid)


def main() -> None:
    text = (Path(__file__).resolve().parent.parent / "inputs" / "day24.txt").read_text()
    grid = parse_input(text)
    print(f"part 1: first repeated layout has biodiversity {part1(grid)}")
    print(f"part 2: {part2(grid)} bugs after {MINUTES} minutes of recursion")


if __name__ == "__main__":
    main()
