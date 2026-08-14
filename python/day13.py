"""AoC 2019 Day 13 — Care Package.

Interpreter-flavored companion to src/day13.rkt. The Day 9 Intcode VM
(python/day09.py, driven with Day 7's block/resume protocol as in
python/day11.py) becomes an arcade cabinet. The machine is unchanged — the
instruction set froze at Day 9 — so everything here is the peripheral:

  * Output is a *display protocol*: a flat integer stream that is really a
    stream of (x, y, tile_id) triples. Framing it is the whole of Part 1.
  * One triple is out of band: (x, y) == (-1, 0) carries the score instead
    of a tile — a sentinel-tagged union smuggled through an untyped wire.
  * Input is a *control loop*: poke memory[0] = 2 for free play, then answer
    each joystick read with -1 / 0 / +1. The reply must be computed from the
    world the program itself just drew, which is why the VM has to be
    resumable rather than fed a precomputed input list.

Part 1 counts block tiles (id 2) on the board the program draws before it
exits. Part 2 plays to completion; the controller is one line —
sign(ball_x - paddle_x), keep the paddle under the ball — and the answer is
the score once the last block is gone.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable, Iterator

EMPTY, WALL, BLOCK, PADDLE, BALL = range(5)


def parse_input(text: str) -> list[int]:
    return [int(t) for t in text.strip().split(",")]


class VM:
    """Day 9's operand resolution (position / immediate / relative, opcode 9)
    stepped one instruction at a time like Day 7's amplifiers, so the caller
    supplies input just-in-time. Identical to python/day11.py's VM."""

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


def commands(vm: VM, joystick: Callable[[], int]) -> Iterator[tuple[int, int, int]]:
    """Yield the cabinet's (x, y, tile) draw commands until it halts.

    `joystick` is a *callback*, not a value: it runs at the instant the VM
    blocks on opcode 3, so it sees the consumer's most recent world state
    rather than a snapshot taken before the frame was drawn. As a generator,
    the consumer's `for` body runs between yields — Python's coroutines give
    for free the interleaving src/day13.rkt spells out as an explicit loop.
    """
    outs: list[int] = []
    while True:
        result = vm.step()
        if result == "blocked":
            vm.inputs.append(joystick())
        elif result == "halted":
            return
        elif isinstance(result, tuple):
            outs.append(result[1])
            if len(outs) == 3:
                yield (outs[0], outs[1], outs[2])
                outs = []


def screen(program: list[int]) -> dict[tuple[int, int], int]:
    """The board as drawn when the program exits. Redrawing a coordinate
    replaces its tile, so this is the final frame, not a draw log."""

    def unreachable() -> int:
        raise AssertionError("cabinet asked for joystick input before free play")

    tiles: dict[tuple[int, int], int] = {}
    for x, y, tile in commands(VM(program), unreachable):
        tiles[(x, y)] = tile
    return tiles


def part1(program: list[int]) -> int:
    return sum(1 for tile in screen(program).values() if tile == BLOCK)


GLYPHS = {EMPTY: " ", WALL: "█", BLOCK: "#", PADDLE: "=", BALL: "o"}


def render(tiles: dict[tuple[int, int], int]) -> str:
    if not tiles:
        return ""
    xs = [x for x, _ in tiles]
    ys = [y for _, y in tiles]
    return "\n".join(
        "".join(GLYPHS[tiles.get((x, y), EMPTY)] for x in range(min(xs), max(xs) + 1))
        for y in range(min(ys), max(ys) + 1)
    )


def play(program: list[int], quarters: int | None = 2) -> int:
    """Play to completion and return the final score.

    `quarters` is poked into memory address 0 before the first instruction
    (2 = free play). Only the ball's and paddle's *x* are tracked: the paddle
    moves horizontally, so tracking is a one-dimensional problem.
    """
    vm = VM(program)
    if quarters is not None:
        vm.mem[0] = quarters

    score = 0
    ball = paddle = 0

    for x, y, tile in commands(vm, lambda: (ball > paddle) - (ball < paddle)):
        if (x, y) == (-1, 0):
            score = tile  # the sentinel triple carries a score, not a tile
        elif tile == BALL:
            ball = x
        elif tile == PADDLE:
            paddle = x

    return score


def part2(program: list[int]) -> int:
    return play(program)


if __name__ == "__main__":
    from pathlib import Path

    raw = (Path(__file__).resolve().parent.parent / "inputs" / "day13.txt").read_text()
    program = parse_input(raw)
    print("part 1:", part1(program))
    print(render(screen(program)))
    print("part 2:", part2(program))
