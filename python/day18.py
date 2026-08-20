"""AoC 2019 Day 18 -- Many-Worlds Interpretation.

The map is a maze holding keys (lowercase) and doors (uppercase); a door is
passable only once its key is collected. Asked: the shortest walk from `@`
that collects every key.

The right reading: SHORTEST PATH IN A PRODUCT GRAPH. A walk's state is not
"where am I" but (where am I, which keys do I hold) -- position crossed with
the subset lattice 2^26 -- and collecting a key is just an edge into the next
mask layer. Dijkstra over that product is the whole algorithm; everything
else is keeping the product small enough to search:

  * The 81x81 grid is CONDENSED to a weighted graph over the 53 cells that
    matter (entrance, 26 keys, 26 doors) by one BFS per such cell that stops
    at the others; corridors collapse to edge weights. Crucially, DOORS STAY
    VERTICES rather than becoming annotations on key-to-key edges. An
    annotation records the doors on one chosen shortest path, and a longer
    detour around a locked door would be lost with it -- wrong answers on
    maps with cycles. With doors as vertices, every grid route survives
    condensation exactly, so nothing here assumes the maze is a tree.
    (test_day18.py pins this with a map built to break the annotation
    shortcut, and with an oracle that searches the raw grid.)
  * Between key pickups the mask is constant, so movement under a fixed mask
    is plain Dijkstra on the condensed graph -- and a walk may be cut at the
    FIRST uncollected key it touches, because collecting is free and opens
    doors monotonically: picking a key up the moment you stand on it is
    never worse than stepping over it. `reachable_keys` finds those "go
    collect key k" strides; the outer Dijkstra in `min_steps` orders them.

Part 2 is map surgery, not a new algorithm: the 3x3 around the entrance is
rewritten into four entrances sealed off from each other, and the state's
position component becomes a 4-tuple -- one robot per vault, and "only one
robot moves at a time" costs nothing to model because steps simply add. The
same `min_steps` runs unchanged; a robot whose next door is keyed from
another vault just has no stride until the shared mask catches up.

Run:  python python/day18.py
"""

from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass
from pathlib import Path

Pos = tuple[int, int]


@dataclass(frozen=True)
class Vault:
    """The parsed map: geometry, and where the letters sit.

    `doors` maps a door cell to the LOWERCASE letter of the key that opens
    it -- the case distinction is spelling, not information, and lowering it
    at parse time means nothing downstream ever calls `.upper()` to compare.
    Door and key cells are also in `open_cells`: they are floor you can
    stand on, walls are the only cells missing.
    """

    open_cells: frozenset[Pos]
    keys: dict[Pos, str]
    doors: dict[Pos, str]
    entrances: tuple[Pos, ...]


def parse_input(text: str) -> Vault:
    """Full parse: every non-wall cell classified, positions as (x, y).

    `splitlines()` is the CRLF guard -- it treats `\r\n` as one break, so a
    Windows-downloaded input parses identically to a Unix one. Without it a
    stray `\r` would become a phantom open cell hanging off every row's end.
    """
    open_cells: set[Pos] = set()
    keys: dict[Pos, str] = {}
    doors: dict[Pos, str] = {}
    entrances: list[Pos] = []
    for y, line in enumerate(text.splitlines()):
        for x, ch in enumerate(line):
            if ch == "#":
                continue
            pos = (x, y)
            open_cells.add(pos)
            if ch == "@":
                entrances.append(pos)
            elif ch.islower():
                keys[pos] = ch
            elif ch.isupper():
                doors[pos] = ch.lower()
    return Vault(frozenset(open_cells), keys, doors, tuple(entrances))


def all_keys_mask(vault: Vault) -> int:
    """The goal: one bit per key PRESENT IN THE MAP (`a` = bit 0).

    Built from the keys, not the doors -- a door whose key does not exist is
    merely a wall forever, it does not extend the goal.
    """
    mask = 0
    for ch in vault.keys.values():
        mask |= 1 << (ord(ch) - ord("a"))
    return mask


def split_entrance(vault: Vault) -> Vault:
    """Part 2's map surgery: the 3x3 around `@` becomes four sealed vaults.

        ...        @#@
        .@.   ->   ###
        ...        @#@

    The four diagonal neighbours become entrances, the entrance and its four
    orthogonal neighbours become walls. The rewrite only makes sense over a
    fully open, letter-free 3x3 -- a property of the input, not a promise of
    the statement -- so it is checked rather than assumed: refusing beats
    silently deleting a key that happened to sit next to `@`.
    """
    ((ex, ey),) = vault.entrances
    block = {(ex + dx, ey + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    if not block <= vault.open_cells:
        raise ValueError("the 3x3 around the entrance is not fully open; cannot split it")
    lettered = block & (vault.keys.keys() | vault.doors.keys())
    if lettered:
        raise ValueError(f"keys or doors adjacent to the entrance would be overwritten: {sorted(lettered)}")
    corners = {(ex + dx, ey + dy) for dx in (-1, 1) for dy in (-1, 1)}
    return Vault(
        vault.open_cells - (block - corners),
        dict(vault.keys),
        dict(vault.doors),
        tuple(sorted(corners)),
    )


def condense(vault: Vault) -> dict[Pos, list[tuple[Pos, int]]]:
    """The grid as a weighted graph over entrances, keys and doors only.

    One BFS per such cell, expanding through plain floor but STOPPING at any
    other entrance/key/door: an edge (v, d) means "d steps of corridor with
    nothing of interest in between". A grid path that passes through a door
    or key therefore decomposes into graph edges at exactly the cells where
    the rules could have something to say -- condensation loses geometry,
    never routes. Parallel corridors between the same pair become parallel
    edges; Dijkstra simply never prefers the longer one.
    """
    pois = set(vault.entrances) | vault.keys.keys() | vault.doors.keys()
    graph: dict[Pos, list[tuple[Pos, int]]] = {}
    for source in pois:
        edges = []
        seen = {source}
        frontier = deque([(source, 0)])
        while frontier:
            (x, y), dist = frontier.popleft()
            for nbr in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if nbr not in vault.open_cells or nbr in seen:
                    continue
                seen.add(nbr)
                if nbr in pois:
                    edges.append((nbr, dist + 1))
                else:
                    frontier.append((nbr, dist + 1))
        graph[source] = edges
    return graph


def min_steps(vault: Vault) -> int:
    """Fewest steps to collect every key, however many robots are walking.

    Outer Dijkstra over states (positions, mask). A move is a whole stride
    "robot i goes and collects key k", supplied by `reachable_keys`: inner
    Dijkstra on the condensed graph under the current mask, refusing locked
    door vertices and cutting the search at each uncollected key (see the
    module docstring for why cutting there is lossless).

    The inner results are cached, and the cache key is the mask REDUCED TO
    THE BITS THAT CAN MATTER from that source: the keys and doors in the
    source's connected component (`relevant`, one flood per vertex, locks
    ignored). In Part 2 a robot's component holds only its own vault, so the
    other three robots' collecting -- which churns the full mask constantly
    -- stops invalidating its cache entries. Same answers, ~quarter the
    inner searches.
    """
    graph = condense(vault)
    key_bit = {pos: 1 << (ord(ch) - ord("a")) for pos, ch in vault.keys.items()}
    door_bit = {pos: 1 << (ord(ch) - ord("a")) for pos, ch in vault.doors.items()}
    goal = all_keys_mask(vault)

    relevant: dict[Pos, int] = {}
    for source in graph:
        seen = {source}
        stack = [source]
        bits = 0
        while stack:
            pos = stack.pop()
            bits |= key_bit.get(pos, 0) | door_bit.get(pos, 0)
            for nbr, _ in graph[pos]:
                if nbr not in seen:
                    seen.add(nbr)
                    stack.append(nbr)
        relevant[source] = bits

    strides: dict[tuple[Pos, int], dict[Pos, int]] = {}

    def reachable_keys(source: Pos, mask: int) -> dict[Pos, int]:
        cache_key = (source, mask & relevant[source])
        if cache_key not in strides:
            found: dict[Pos, int] = {}
            best = {source: 0}
            heap = [(0, source)]
            while heap:
                dist, pos = heapq.heappop(heap)
                if dist > best[pos]:
                    continue
                for nbr, weight in graph[pos]:
                    if door_bit.get(nbr, 0) & ~mask:
                        continue  # locked door: not passable, not even standable
                    ndist = dist + weight
                    if ndist >= best.get(nbr, ndist + 1):
                        continue
                    best[nbr] = ndist
                    if key_bit.get(nbr, 0) & ~mask:
                        found[nbr] = ndist  # stride ends here; do not search past it
                    else:
                        heapq.heappush(heap, (ndist, nbr))
            strides[cache_key] = found
        return strides[cache_key]

    start = (vault.entrances, 0)
    best_state = {start: 0}
    heap = [(0, *start)]
    while heap:
        dist, positions, mask = heapq.heappop(heap)
        if mask == goal:
            return dist
        if dist > best_state[(positions, mask)]:
            continue
        for i, pos in enumerate(positions):
            for key_pos, stride in reachable_keys(pos, mask).items():
                state = (
                    positions[:i] + (key_pos,) + positions[i + 1 :],
                    mask | key_bit[key_pos],
                )
                ndist = dist + stride
                if ndist < best_state.get(state, ndist + 1):
                    best_state[state] = ndist
                    heapq.heappush(heap, (ndist, *state))
    raise ValueError("some key is unreachable no matter what is collected first")


def part1(vault: Vault) -> int:
    return min_steps(vault)


def part2(vault: Vault) -> int:
    return min_steps(split_entrance(vault))


def solve(vault: Vault) -> tuple[int, int]:
    return part1(vault), part2(vault)


def main() -> None:
    text = (Path(__file__).resolve().parent.parent / "inputs" / "day18.txt").read_text()
    vault = parse_input(text)
    print(f"  map: {len(vault.open_cells)} open cells, {len(vault.keys)} keys, {len(vault.doors)} doors")
    print(f"  part 1: {part1(vault)}")
    print(f"  part 2: {part2(vault)}")


if __name__ == "__main__":
    main()
