"""AoC 2019 Day 11 — Space Police.

Interpreter-flavored companion to src/day11.rkt. The Day 9 Intcode VM
(python/day09.py) drives a hull-painting robot: it reads the color of its
current panel as input, then emits (paint_color, turn) and moves forward one
panel. Because the robot's next input depends on where its own prior output
just moved it, the VM can't run to completion up front the way Day 9's
`run` does — it needs Day 7's step-and-block protocol (python/day07.py's
`step`), extended with Day 9's relative-mode addressing and opcode 9.

Part 1: start on an all-black hull; the answer is the number of distinct
panels painted at least once, regardless of final color. Part 2: start on
one white panel instead; the panels painted white spell an 8-letter
registration code, rendered as a #/. grid for a human to read (no OCR).
"""

from __future__ import annotations

from collections import defaultdict


def parse_input(text: str) -> list[int]:
    return [int(t) for t in text.strip().split(",")]


class VM:
    """A resumable Intcode machine: Day 9's operand resolution (position /
    immediate / relative, opcode 9), stepped one instruction at a time like
    Day 7's amplifiers so the caller can supply input just-in-time."""

    def __init__(self, program: list[int]) -> None:
        self.mem: dict[int, int] = defaultdict(int, enumerate(program))
        self.ip = 0
        self.rb = 0
        self.inputs: list[int] = []
        self.halted = False

    def step(self) -> str | tuple[str, int]:
        if self.halted:
            return "halted"
        mem, ip = self.mem, self.ip

        def mode(n: int) -> int:
            return (mem[ip] // 10 ** (n + 1)) % 10

        def val(n: int) -> int:
            raw = mem[ip + n]
            m = mode(n)
            if m == 1:
                return raw
            if m == 2:
                return mem[self.rb + raw]
            return mem[raw]

        def addr(n: int) -> int:
            raw = mem[ip + n]
            return self.rb + raw if mode(n) == 2 else raw

        op = mem[ip] % 100
        if op == 1:
            mem[addr(3)] = val(1) + val(2)
            self.ip += 4
            return "ran"
        if op == 2:
            mem[addr(3)] = val(1) * val(2)
            self.ip += 4
            return "ran"
        if op == 3:
            if not self.inputs:
                return "blocked"
            mem[addr(1)] = self.inputs.pop(0)
            self.ip += 2
            return "ran"
        if op == 4:
            self.ip += 2
            return ("output", val(1))
        if op == 5:
            self.ip = val(2) if val(1) else ip + 3
            return "ran"
        if op == 6:
            self.ip = val(2) if not val(1) else ip + 3
            return "ran"
        if op == 7:
            mem[addr(3)] = int(val(1) < val(2))
            self.ip += 4
            return "ran"
        if op == 8:
            mem[addr(3)] = int(val(1) == val(2))
            self.ip += 4
            return "ran"
        if op == 9:
            self.rb += val(1)
            self.ip += 2
            return "ran"
        if op == 99:
            self.halted = True
            return "halted"
        raise ValueError(f"unknown opcode {op} at {ip}")


# Clockwise facing cycle, matching src/day11.rkt: 0=up 1=right 2=down 3=left.
DELTAS = [(0, -1), (1, 0), (0, 1), (-1, 0)]


def turn(facing: int, signal: int) -> int:
    return (facing + (3 if signal == 0 else 1)) % 4


def run_to_outputs(vm: VM, camera: int) -> list[int]:
    """Step `vm` until it either emits a (paint, turn) pair or halts first.
    Input is supplied lazily, the instant the VM blocks wanting it — not
    pushed ahead of time — mirroring src/day11.rkt's `run-to-outputs!`."""
    outs: list[int] = []
    while True:
        result = vm.step()
        if result == "blocked":
            vm.inputs.append(camera)
        elif result == "halted":
            return outs
        elif isinstance(result, tuple):
            outs.append(result[1])
            if len(outs) == 2:
                return outs


def paint_hull(program: list[int], start_color: int = 0) -> dict[tuple[int, int], int]:
    """`start_color` is panel (0,0)'s color before the robot paints anything
    (Part 1: black/0, Part 2: white/1) — consulted only on the very first
    camera read, since `panels` starts empty rather than pre-seeded."""
    vm = VM(program)
    pos = (0, 0)
    facing = 0
    panels: dict[tuple[int, int], int] = {}

    while True:
        default = start_color if pos == (0, 0) else 0
        outs = run_to_outputs(vm, panels.get(pos, default))
        if len(outs) < 2:
            return panels
        panels[pos] = outs[0]
        facing = turn(facing, outs[1])
        dx, dy = DELTAS[facing]
        pos = (pos[0] + dx, pos[1] + dy)


def part1(program: list[int]) -> int:
    return len(paint_hull(program))


def render(panels: dict[tuple[int, int], int]) -> str:
    """Bounding box over the lit (white) panels, drawn as a #/. grid."""
    whites = [pos for pos, color in panels.items() if color == 1]
    if not whites:
        return ""
    xs, ys = [p[0] for p in whites], [p[1] for p in whites]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    return "\n".join(
        "".join("#" if panels.get((x, y), 0) == 1 else "." for x in range(x0, x1 + 1))
        for y in range(y0, y1 + 1)
    )


def part2(program: list[int]) -> str:
    return render(paint_hull(program, start_color=1))


if __name__ == "__main__":
    from pathlib import Path

    raw = (Path(__file__).resolve().parent.parent / "inputs" / "day11.txt").read_text()
    program = parse_input(raw)
    print("part 1:", part1(program))
    print("part 2:")
    for line in part2(program).split("\n"):
        print("   ", line)
