"""AoC 2019 Day 6 — Universal Orbit Map.

Algorithm-flavored companion to src/day06.rkt. The orbit map is a **rooted
tree** dressed up in space clothes: every object orbits exactly one other,
so each ``A)B`` line is the edge "B's parent is A" and ``COM`` is the root.
A plain child -> parent dict is the whole data structure (a parent-pointer
tree); both parts only ever walk *upward*.

  * Part 1 — the orbit-count checksum is the **sum of every node's
    depth**: each object contributes one orbit per ancestor on its path
    to COM.
  * Part 2 — minimum orbital transfers is a **lowest common ancestor
    (LCA)** distance:  d(u, v) = d(u, LCA) + d(v, LCA).  Index one
    ancestor chain by distance, walk the other nearest-first, and the
    first chain element already seen IS the LCA.

The shipped Part 1 re-walks each node's path (O(n * depth)); the memoized
O(n) version is sidebar'd in the function guide.
"""

from __future__ import annotations

from itertools import count


def parse_input(text: str) -> dict[str, str]:
    """``A)B`` lines -> child -> parent dict (B orbits A)."""
    parents = {}
    for line in text.split():
        parent, child = line.split(")")
        parents[child] = parent
    return parents


def ancestors(parents: dict[str, str], obj: str) -> list[str]:
    """Everything ``obj`` orbits, nearest first: L -> [K, J, E, D, C, B, COM]."""
    chain = []
    while obj in parents:
        obj = parents[obj]
        chain.append(obj)
    return chain


def part1(parents: dict[str, str]) -> int:
    """Sum of depths: each object's orbit count is its ancestor-chain length."""
    return sum(len(ancestors(parents, obj)) for obj in parents)


def part2(parents: dict[str, str]) -> int:
    """Transfers from YOU's orbit to SAN's orbit via the LCA.

    ``you_dist`` maps each of YOU's ancestors to its distance from YOU's
    current orbit (nearest = 0). Scanning SAN's chain nearest-first, the
    first object already in ``you_dist`` is the *lowest* common ancestor;
    the answer is the two distances summed.
    """
    you_dist = {obj: i for i, obj in enumerate(ancestors(parents, "YOU"))}
    for i, obj in zip(count(), ancestors(parents, "SAN")):
        if obj in you_dist:
            return i + you_dist[obj]
    raise ValueError("YOU and SAN share no ancestor (not a single tree?)")


if __name__ == "__main__":
    from pathlib import Path

    raw = (Path(__file__).resolve().parent.parent / "inputs" / "day06.txt").read_text()
    parents = parse_input(raw)
    print("part 1:", part1(parents))
    print("part 2:", part2(parents))
