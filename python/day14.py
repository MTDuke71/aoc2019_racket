"""AoC 2019 Day 14 — Space Stoichiometry (algorithm reference).

The Racket solution in src/day14.rkt is the shipping artifact; this file is
the algorithm stated in the most boring language available, so the *idea*
can be read without Racket syntax in the way.

Two ideas, both named:

  1. TOPOLOGICAL SORT (Kahn's algorithm) of the recipe DAG, edges running
     output -> input. Expanding demand in that order guarantees a chemical's
     total is final before we round it up to whole reaction runs, which is
     what makes a single `ceil` per chemical correct.

  2. BINARY SEARCH ON THE ANSWER for part 2: ore_for(fuel) is monotone
     non-decreasing, so "largest fuel with ore_for(fuel) <= 1e12" is a
     predicate flip.

Run:  python python/day14.py
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

TRILLION = 1_000_000_000_000


# --------------------------------------------------------------- parsing


def parse_input(text: str) -> dict[str, tuple[int, list[tuple[int, str]]]]:
    """`3 A, 4 B => 1 AB` -> {"AB": (1, [(3, "A"), (4, "B")])}."""

    def amount(s: str) -> tuple[int, str]:
        n, chem = s.split()
        return int(n), chem

    reactions = {}
    for line in text.strip().splitlines():
        if not line.strip():
            continue
        lhs, rhs = line.split("=>")
        qty, out = amount(rhs)
        reactions[out] = (qty, [amount(part) for part in lhs.split(",")])
    return reactions


# ------------------------------------------------------ topological sort


def topo_order(reactions) -> list[str]:
    """Chemicals ordered so every consumer precedes what it consumes.

    Kahn's algorithm. in-degree of X = how many distinct reactions consume X;
    a chemical is safe to expand once all of them have been expanded.
    """
    succs = {out: sorted({chem for _, chem in ins}) for out, (_, ins) in reactions.items()}

    indeg: dict[str, int] = defaultdict(int)
    for out, ss in succs.items():
        indeg.setdefault(out, 0)
        for s in ss:
            indeg.setdefault(s, 0)
    for ss in succs.values():
        for s in ss:
            indeg[s] += 1

    ready = [c for c, d in indeg.items() if d == 0]
    order = []
    while ready:
        c = ready.pop()
        order.append(c)
        for s in succs.get(c, ()):
            indeg[s] -= 1
            if indeg[s] == 0:
                ready.append(s)
    return order


# ----------------------------------------------------------- the solver


def ore_for(reactions, fuel: int) -> int:
    """ORE needed for `fuel` FUEL.

    Because we visit in topological order, need[c] is complete when we get
    to c, so the round-up to whole runs happens exactly once per chemical.
    Leftovers are implicit -- nothing downstream asks for c again.
    """
    order = topo_order(reactions)
    need: dict[str, int] = defaultdict(int)
    need["FUEL"] = fuel
    for c in order:
        n = need[c]
        if n <= 0 or c not in reactions:
            continue
        per, ins = reactions[c]
        runs = -(-n // per)  # ceiling division
        for qty, chem in ins:
            need[chem] += runs * qty
    return need["ORE"]


def part1(reactions) -> int:
    return ore_for(reactions, 1)


def part2(reactions, budget: int = TRILLION) -> int:
    """Largest FUEL affordable with `budget` ORE, by bisection.

    lo starts at the naive per-unit rate estimate, which UNDERSHOOTS: bulk
    production amortizes leftovers, so the real answer is always >= it.
    """
    lo = max(1, budget // part1(reactions))
    hi = 2 * lo
    while ore_for(reactions, hi) <= budget:
        hi *= 2
    while hi - lo > 1:  # invariant: lo affordable, hi not
        mid = (lo + hi) // 2
        if ore_for(reactions, mid) <= budget:
            lo = mid
        else:
            hi = mid
    return lo


# ------------------------------------------------------------- examples

EXAMPLES = [
    (
        """10 ORE => 10 A
1 ORE => 1 B
7 A, 1 B => 1 C
7 A, 1 C => 1 D
7 A, 1 D => 1 E
7 A, 1 E => 1 FUEL""",
        31,
        None,
    ),
    (
        """9 ORE => 2 A
8 ORE => 3 B
7 ORE => 5 C
3 A, 4 B => 1 AB
5 B, 7 C => 1 BC
4 C, 1 A => 1 CA
2 AB, 3 BC, 4 CA => 1 FUEL""",
        165,
        None,
    ),
    (
        """157 ORE => 5 NZVS
165 ORE => 6 DCFZ
44 XJWVT, 5 KHKGT, 1 QDVJ, 29 NZVS, 9 GPVTF, 48 HKGWZ => 1 FUEL
12 HKGWZ, 1 GPVTF, 8 PSHF => 9 QDVJ
179 ORE => 7 PSHF
177 ORE => 5 HKGWZ
7 DCFZ, 7 PSHF => 2 XJWVT
165 ORE => 2 GPVTF
3 DCFZ, 7 NZVS, 5 HKGWZ, 10 PSHF => 8 KHKGT""",
        13312,
        82892753,
    ),
    (
        """2 VPVL, 7 FWMGM, 2 CXFTF, 11 MNCFX => 1 STKFG
17 NVRVD, 3 JNWZP => 8 VPVL
53 STKFG, 6 MNCFX, 46 VJHF, 81 HVMC, 68 CXFTF, 25 GNMV => 1 FUEL
22 VJHF, 37 MNCFX => 5 FWMGM
139 ORE => 4 NVRVD
144 ORE => 7 JNWZP
5 MNCFX, 7 RFSQX, 2 FWMGM, 2 VPVL, 19 CXFTF => 3 HVMC
5 VJHF, 7 MNCFX, 9 VPVL, 37 CXFTF => 6 GNMV
145 ORE => 6 MNCFX
1 NVRVD => 8 CXFTF
1 VJHF, 6 MNCFX => 4 RFSQX
176 ORE => 6 VJHF""",
        180697,
        5586022,
    ),
    (
        """171 ORE => 8 CNZTR
7 ZLQW, 3 BMBT, 9 XCVML, 26 XMNCP, 1 WPTQ, 2 MZWV, 1 RJRHP => 4 PLWSL
114 ORE => 4 BHXH
14 VRPVC => 6 BMBT
6 BHXH, 18 KTJDG, 12 WPTQ, 7 PLWSL, 31 FHTLT, 37 ZDVW => 1 FUEL
6 WPTQ, 2 BMBT, 8 ZLQW, 18 KTJDG, 1 XMNCP, 6 MZWV, 1 RJRHP => 6 FHTLT
15 XDBXC, 2 LTCX, 1 VRPVC => 6 ZLQW
13 WPTQ, 10 LTCX, 3 RJRHP, 14 XMNCP, 2 MZWV, 1 ZLQW => 1 ZDVW
5 BMBT => 4 WPTQ
189 ORE => 9 KTJDG
1 MZWV, 17 XDBXC, 3 XCVML => 2 XMNCP
12 VRPVC, 27 CNZTR => 2 XDBXC
15 KTJDG, 12 BHXH => 5 XCVML
3 BHXH, 2 VRPVC => 7 MZWV
121 ORE => 7 VRPVC
7 XCVML => 6 RJRHP
5 BHXH, 4 VRPVC => 5 LTCX""",
        2210736,
        460664,
    ),
]


if __name__ == "__main__":
    for i, (text, want1, want2) in enumerate(EXAMPLES, 1):
        rs = parse_input(text)
        got1 = part1(rs)
        assert got1 == want1, f"example {i}: part 1 {got1} != {want1}"
        if want2 is not None:
            got2 = part2(rs)
            assert got2 == want2, f"example {i}: part 2 {got2} != {want2}"
        print(f"example {i}: part 1 {got1}" + (f", part 2 {want2}" if want2 else ""))

    text = (Path(__file__).resolve().parent.parent / "inputs" / "day14.txt").read_text()
    reactions = parse_input(text)
    print(f"  part 1: {part1(reactions)}")
    print(f"  part 2: {part2(reactions)}")
