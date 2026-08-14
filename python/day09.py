"""AoC 2019 Day 9 — Sensor Boost (the complete Intcode computer).

Interpreter-flavored companion to src/day09.rkt — the Day 5 CPU finished off
with its last missing feature, **relative mode**. Compared to day05.py the
diff is tiny and entirely in operand resolution:

  * `val` gains a third mode, 2 = relative: like position, but the address
    is offset by a movable `rb` (relative base, starts at 0);
  * `addr` (write targets) also honors relative mode — writes are never
    immediate, but they can be relative;
  * opcode 9 adjusts `rb` by a mode-aware operand;
  * memory is a defaultdict(int) so reads/writes past the program are 0,
    and Python ints are arbitrary precision (the "big numbers" requirement).

Part 1 feeds input 1 (test mode → BOOST keycode), Part 2 feeds input 2
(sensor-boost mode → distress coordinates); each emits a single value. The
eight Day 5 opcode handlers are untouched — only the seam moved.
"""

from __future__ import annotations

from collections import defaultdict


def parse_input(text: str) -> list[int]:
    return [int(t) for t in text.strip().split(",")]


def run(program: list[int], *inputs: int) -> list[int]:
    """Execute a copy of `program`, consuming `inputs` in order; return outputs."""
    mem: dict[int, int] = defaultdict(int, enumerate(program))
    ip = 0
    rb = 0  # relative base — the only new state
    pending = list(inputs)
    outs: list[int] = []

    def mode(n: int) -> int:  # mode digit for the nth parameter
        return (mem[ip] // 10 ** (n + 1)) % 10

    def val(n: int) -> int:  # read operand n, mode-aware
        raw = mem[ip + n]
        m = mode(n)
        if m == 1:  # immediate
            return raw
        if m == 2:  # relative
            return mem[rb + raw]
        return mem[raw]  # position

    def addr(n: int) -> int:  # write target: position or relative
        raw = mem[ip + n]
        return rb + raw if mode(n) == 2 else raw

    while True:
        op = mem[ip] % 100
        if op == 1:  # add
            mem[addr(3)] = val(1) + val(2)
            ip += 4
        elif op == 2:  # multiply
            mem[addr(3)] = val(1) * val(2)
            ip += 4
        elif op == 3:  # input
            mem[addr(1)] = pending.pop(0)
            ip += 2
        elif op == 4:  # output
            outs.append(val(1))
            ip += 2
        elif op == 5:  # jump-if-true
            ip = val(2) if val(1) != 0 else ip + 3
        elif op == 6:  # jump-if-false
            ip = val(2) if val(1) == 0 else ip + 3
        elif op == 7:  # less than
            mem[addr(3)] = 1 if val(1) < val(2) else 0
            ip += 4
        elif op == 8:  # equals
            mem[addr(3)] = 1 if val(1) == val(2) else 0
            ip += 4
        elif op == 9:  # adjust relative base
            rb += val(1)
            ip += 2
        elif op == 99:  # halt
            return outs
        else:
            raise ValueError(f"unknown opcode {op} at position {ip}")


def part1(program: list[int]) -> int:
    return run(program, 1)[-1]  # test mode → BOOST keycode


def part2(program: list[int]) -> int:
    return run(program, 2)[-1]  # sensor-boost mode → coordinates


if __name__ == "__main__":
    from pathlib import Path

    raw = (Path(__file__).resolve().parent.parent / "inputs" / "day09.txt").read_text()
    program = parse_input(raw)
    print("part 1:", part1(program))
    print("part 2:", part2(program))
