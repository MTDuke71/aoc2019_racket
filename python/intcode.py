"""The Intcode computer, extracted.

The instruction set froze at [Day 9](../Problem_Statements/days/day09_function_guide.md):
position / immediate / relative operand modes, opcode 9 for the relative base,
unbounded memory, arbitrary-precision integers. Days 11, 13, 15, 17, 19, 21,
23 and 25 do not extend the machine at all -- they only change the *peripheral*
wired to opcodes 3 and 4. So the VM belongs in one place, exactly as the Racket
tree moved it to src/intcode.rkt at Day 13.

python/day11.py and python/day13.py each still carry their own verbatim copy of
this class, deliberately: their function guides annotate those copies line by
line, and rewriting the code out from under a guide breaks the guide. New days
import from here.

The block/resume protocol is [Day 7](../Problem_Statements/days/day07_function_guide.md)'s.
`step()` runs exactly one instruction and reports what happened:

    "ran"              -- state advanced, nothing to see
    "blocked"          -- opcode 3 with an empty input queue; ip has NOT moved,
                          so appending to `.inputs` and stepping again resumes
    "halted"           -- opcode 99 (idempotent: stepping a halted VM re-reports)
    ("output", value)  -- opcode 4 produced `value`

Returning "blocked" instead of demanding an input list up front is what lets a
caller compute the next input *from the output it just saw* -- the difference
between a batch program and an interactive one.
"""

from __future__ import annotations

from collections import defaultdict


class VM:
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
