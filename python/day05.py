"""AoC 2019 Day 5 — Sunny with a Chance of Asteroids.

Interpreter-flavored companion to src/day05.rkt — the Day 2 Intcode machine
grown to a real CPU. Three upgrades over Day 2:

  * parameter modes: the opcode is the rightmost two digits of the
    instruction; the digits above it are per-parameter modes (0 = position,
    dereference as an address; 1 = immediate, use as a literal);
  * I/O opcodes: 3 reads an input, 4 emits an output;
  * control flow: 5/6 jump (set the instruction pointer), 7/8 store a 0/1
    comparison flag.

Part 1 feeds input 1, Part 2 feeds input 5; the answer is the final output
(the diagnostic code). The Racket version is the same fetch/decode/execute
loop with a vector for memory and tail recursion for the pointer.
"""

from __future__ import annotations


def parse_input(text: str) -> list[int]:
    return [int(t) for t in text.strip().split(",")]


def run(program: list[int], input_value: int) -> list[int]:
    """Execute a copy of `program` with one input; return outputs in order."""
    mem = program[:]  # don't clobber the caller's program
    ip = 0
    outs: list[int] = []

    def val(n: int) -> int:  # nth parameter, mode-aware
        raw = mem[ip + n]
        mode = (mem[ip] // 10 ** (n + 1)) % 10  # digit above the 2-digit opcode
        return raw if mode == 1 else mem[raw]

    def addr(n: int) -> int:  # write target: always position mode
        return mem[ip + n]

    while True:
        op = mem[ip] % 100
        if op == 1:  # add
            mem[addr(3)] = val(1) + val(2)
            ip += 4
        elif op == 2:  # multiply
            mem[addr(3)] = val(1) * val(2)
            ip += 4
        elif op == 3:  # input
            mem[addr(1)] = input_value
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
        elif op == 99:  # halt
            return outs
        else:
            raise ValueError(f"unknown opcode {op} at position {ip}")


def part1(program: list[int]) -> int:
    return run(program, 1)[-1]  # system ID 1; diagnostic = last output


def part2(program: list[int]) -> int:
    return run(program, 5)[-1]  # system ID 5


if __name__ == "__main__":
    from pathlib import Path

    raw = (Path(__file__).resolve().parent.parent / "inputs" / "day05.txt").read_text()
    program = parse_input(raw)
    print("part 1:", part1(program))
    print("part 2:", part2(program))
