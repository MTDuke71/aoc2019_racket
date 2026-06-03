"""AoC 2019 Day 2 — 1202 Program Alarm.

Algorithm-flavored companion to src/day02.rkt. Two things make this day
worth a side-by-side:

  1. The *interpreter pattern* — a fetch/decode/execute loop over a flat
     array that is both code and data. This is the seed of the Intcode VM
     trilogy (Days 2, 5, 7, 9), so the shape is worth seeing plainly.

  2. The *affine shortcut* for Part 2. The puzzle wants the (noun, verb)
     pair that makes the program output a fixed target, and the obvious
     solution brute-forces all 100*100 pairs. But the program is affine in
     its two inputs — output = base + A*noun + B*verb — so three runs pin
     down base, A, B and the answer falls out of one division. The Racket
     source ships the honest brute force; this file shows both, and the
     function guide's "Possible optimization" section is the writeup.
"""

from __future__ import annotations


def parse_input(text: str) -> list[int]:
    return [int(tok) for tok in text.strip().split(",")]


def run(program: list[int]) -> list[int]:
    """Execute a *copy* of the program; return its final memory."""
    mem = program[:]
    ip = 0
    while True:
        op = mem[ip]
        if op == 99:
            return mem
        a, b, dst = mem[ip + 1], mem[ip + 2], mem[ip + 3]
        if op == 1:
            mem[dst] = mem[a] + mem[b]
        elif op == 2:
            mem[dst] = mem[a] * mem[b]
        else:
            raise ValueError(f"unknown opcode {op} at position {ip}")
        ip += 4


def run_with(program: list[int], noun: int, verb: int) -> int:
    mem = program[:]
    mem[1], mem[2] = noun, verb
    return run(mem)[0]


def part1(program: list[int]) -> int:
    return run_with(program, 12, 2)


TARGET = 19690720


def part2_brute(program: list[int]) -> int:
    """The shipped algorithm: scan the 100x100 grid for the target."""
    for noun in range(100):
        for verb in range(100):
            if run_with(program, noun, verb) == TARGET:
                return 100 * noun + verb
    raise ValueError("no (noun, verb) produced the target")


def part2_affine(program: list[int]) -> int:
    """The closed form: output = base + A*noun + B*verb, so three runs
    determine the whole plane and the answer is one division.

    Works because every opcode in *this* puzzle's input keeps the output
    linear in the two inputs (noun and verb never multiply each other).
    That is an empirical property of the input, not a guarantee of the
    opcode set — see the function guide for the caveat.
    """
    base = run_with(program, 0, 0)          # constant term
    a = run_with(program, 1, 0) - base      # d(output)/d(noun)
    b = run_with(program, 0, 1) - base      # d(output)/d(verb), usually 1
    noun, rem = divmod(TARGET - base, a)
    verb = rem // b
    return 100 * noun + verb


# Default to the brute force so this file matches the Racket source's
# behavior; swap in part2_affine to see the shortcut.
part2 = part2_brute


if __name__ == "__main__":
    from pathlib import Path

    raw = (Path(__file__).resolve().parent.parent / "inputs" / "day02.txt").read_text()
    program = parse_input(raw)
    print("part 1:", part1(program))
    print("part 2:", part2(program))
    print("part 2 (affine):", part2_affine(program))
