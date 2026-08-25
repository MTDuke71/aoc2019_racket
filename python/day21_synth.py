r"""Day 21 sidebar -- springscript synthesis: the computer writes the program.

A springscript register, viewed denotationally, is not a bit -- it is a
BOOLEAN FUNCTION of the sensors, i.e. a truth table, i.e. a 2^n-bit integer
for n sensors. The machine state is the pair (T, J) of tables, every
instruction is a deterministic map state -> state, and "write a script
computing f" becomes a SHORTEST-PATH question: BFS from (const-false,
const-false) to any state whose J-table equals f. The instruction that
relaxed each state is remembered, so walking the parent chain back emits an
actual program -- synthesis, not just a length.

Two facts this module lets the tests pin (see test_day21.py):

  * The WALK function not(A and B and C) and D takes EXACTLY 5 instructions:
    the BFS meets only 6,924 distinct states within 4 instructions and none
    of them carries the target in J, then finds it at depth 5. Minimality by
    exhaustion, in milliseconds -- the whole 4-sensor universe dedupes to
    almost nothing.
  * The RUN guard depends on exactly six of its nine sensors (A-E and H).
    Every sensor a function depends on must appear as some instruction's X
    operand -- values enter the registers no other way -- so six live sensors
    put a floor of 6 under any script computing it. The shipping script does
    it in 8.

Between those two sits a result too expensive for the suite, reproduced by
running this file (documented in the function guide): over sources restricted
to the six live sensors plus T and J, exhaustive BFS clears depth 7 with no
hit, making 8 minimal for the RUN guard in that source universe.

Run:  python python/day21_synth.py         (the cheap p1 proof)
      python python/day21_synth.py deep    (the depth-7 RUN-guard exhaustion)
"""

from __future__ import annotations

import sys
from collections.abc import Callable

SOURCES_PER_STATE = ("T", "J")  # writable destinations, always available as sources


def table_of(fn: Callable[..., bool], n_sensors: int) -> int:
    """The truth table of `fn` over n sensors, as a 2^n-bit integer.

    Bit i of the table is fn's value on the assignment whose k-th sensor is
    bit k of i -- the same variable order A, B, C, ... everywhere here.
    """
    t = 0
    for i in range(1 << n_sensors):
        if fn(*[bool((i >> k) & 1) for k in range(n_sensors)]):
            t |= 1 << i
    return t


def sensor_table(k: int, n_sensors: int) -> int:
    """The truth table of the bare sensor variable k: 'copy bit k of the index'."""
    t = 0
    for i in range(1 << n_sensors):
        if (i >> k) & 1:
            t |= 1 << i
    return t


def live_sensors(table: int, n_sensors: int) -> set[str]:
    """The sensors the function actually depends on, by name.

    Sensor k is live iff flipping it changes the output on some assignment --
    iff the table restricted to k=0 differs from the table restricted to k=1.
    """
    live = set()
    for k in range(n_sensors):
        sk = sensor_table(k, n_sensors)
        # f with sensor k forced to 0 vs forced to 1, both laid out on the
        # k=0 assignment positions (the shift pairs each k=1 index with its
        # k=0 partner, and always lands on k=0 positions)
        lo = table & ~sk
        hi = (table & sk) >> (1 << k)
        if lo != hi:
            live.add(chr(ord("A") + k))
    return live


def synthesize(
    target: int, n_sensors: int, max_depth: int, sensors: str | None = None
) -> tuple[str, ...] | None:
    """Shortest springscript whose final J computes `target`, or None.

    BFS over (T-table, J-table) states. `sensors` restricts which sensor
    registers may appear as sources (default: all n); T and J are always
    available. Every visited state remembers the (previous state, instruction)
    that first reached it, so a hit is walked back into a real program.
    """
    names = sensors or "".join(chr(ord("A") + k) for k in range(n_sensors))
    mask = (1 << (1 << n_sensors)) - 1
    tables = {name: sensor_table(ord(name) - ord("A"), n_sensors) for name in names}

    start = (0, 0)
    if start[1] == target:
        return ()
    parent: dict[tuple[int, int], tuple[tuple[int, int], str]] = {start: None}  # type: ignore[dict-item]
    frontier = [start]

    def emit(state: tuple[int, int]) -> tuple[str, ...]:
        script: list[str] = []
        while parent[state] is not None:
            state, line = parent[state]
            script.append(line)
        return tuple(reversed(script))

    for _ in range(max_depth):
        nxt = []
        for state in frontier:
            T, J = state
            for name in (*names, *SOURCES_PER_STATE):
                a = {"T": T, "J": J}.get(name)
                if a is None:
                    a = tables[name]
                for line, s in (
                    (f"AND {name} T", (a & T, J)),
                    (f"AND {name} J", (T, a & J)),
                    (f"OR {name} T", (a | T, J)),
                    (f"OR {name} J", (T, a | J)),
                    (f"NOT {name} T", (~a & mask, J)),
                    (f"NOT {name} J", (T, ~a & mask)),
                ):
                    if s not in parent:
                        parent[s] = (state, line)
                        if s[1] == target:
                            return emit(s)
                        nxt.append(s)
        frontier = nxt
    return None


def exhaust(
    target: int, n_sensors: int, max_depth: int, sensors: str | None = None
) -> list[tuple[int, int, bool]]:
    """The verdict-only version of `synthesize`, for depths where remembering
    parents would cost gigabytes: per depth, (frontier size, states seen so
    far, target found?). Stops early on a hit."""
    names = sensors or "".join(chr(ord("A") + k) for k in range(n_sensors))
    mask = (1 << (1 << n_sensors)) - 1
    tables = [sensor_table(ord(name) - ord("A"), n_sensors) for name in names]

    seen = {(0, 0)}
    frontier = [(0, 0)]
    stats = []
    for _ in range(max_depth):
        nxt = []
        for T, J in frontier:
            for a in (*tables, T, J):
                na = ~a & mask
                for s in (
                    (a & T, J),
                    (T, a & J),
                    (a | T, J),
                    (T, a | J),
                    (na, J),
                    (T, na),
                ):
                    if s not in seen:
                        seen.add(s)
                        nxt.append(s)
        hit = any(J == target for _, J in nxt)
        stats.append((len(nxt), len(seen), hit))
        if hit:
            break
        frontier = nxt
    return stats


def walk_target() -> int:
    return table_of(lambda a, b, c, d: not (a and b and c) and d, 4)


def run_guard_target_live_only() -> int:
    """The RUN guard as a function of its six live sensors A, B, C, D, E, H
    -- renamed to the first six variable slots for a 64-bit table."""
    return table_of(lambda a, b, c, d, e, h: not (a and b and c) and d and (e or h), 6)


def main() -> None:
    target = walk_target()
    for depth in range(1, 6):
        script = synthesize(target, 4, depth)
        print(f"depth <= {depth}: {script if script else 'no script'}")

    if "deep" in sys.argv[1:]:
        print("\nRUN guard over live sensors A-E,H (renamed A..F), depth-7 exhaustion:")
        for depth, (frontier, total, hit) in enumerate(exhaust(run_guard_target_live_only(), 6, 7), start=1):
            print(
                f"depth {depth}: frontier {frontier:,}, seen {total:,}, target {'FOUND' if hit else 'absent'}"
            )
        print("(shipping script: 8 instructions)")


if __name__ == "__main__":
    main()
