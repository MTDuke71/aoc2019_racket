"""AoC 2019 Day 7 — Amplification Circuit.

Algorithm-flavored companion to src/day07.rkt. Five copies of the Day 5
Intcode program act as amplifiers. Each reads a phase setting (used once per
permutation) and then input signals; outputs chain A→B→C→D→E.

  * Part 1 — **series chain**: run each amp to completion in order; brute-force
    all permutations of phases 0–4; take the maximum final output.
  * Part 2 — **feedback loop**: five VMs run concurrently; E's output loops back
    to A. Brute-force permutations of phases 5–9; answer is E's last output.

The canonical technique name is brute-force over permutations with an Intcode
I/O queue (Part 2 is cooperative multitasking / coroutine-style scheduling).
"""

from __future__ import annotations

from itertools import permutations


def parse_input(text: str) -> list[int]:
    return list(map(int, text.strip().split(",")))


def run_inputs(program: list[int], inputs: list[int]) -> list[int]:
    """Day 5 Intcode with a growable memory and a list of inputs."""
    mem = program[:]

    def ref(addr: int) -> int:
        return mem[addr] if 0 <= addr < len(mem) else 0

    def store(addr: int, val: int) -> None:
        if addr < 0:
            raise ValueError(addr)
        while addr >= len(mem):
            mem.append(0)
        mem[addr] = val

    ip = 0
    pending = list(inputs)
    outs: list[int] = []
    while True:
        instr = ref(ip)
        op = instr % 100
        modes = instr // 100

        def val(n: int, ip: int = ip, modes: int = modes) -> int:
            raw = ref(ip + n)
            mode = (modes // (10 ** (n - 1))) % 10
            return raw if mode == 1 else ref(raw)

        def addr(n: int, ip: int = ip) -> int:
            return ref(ip + n)

        if op == 1:
            store(addr(3), val(1) + val(2))
            ip += 4
        elif op == 2:
            store(addr(3), val(1) * val(2))
            ip += 4
        elif op == 3:
            store(addr(1), pending.pop(0))
            ip += 2
        elif op == 4:
            outs.append(val(1))
            ip += 2
        elif op == 5:
            ip = val(2) if val(1) else ip + 3
        elif op == 6:
            ip = val(2) if not val(1) else ip + 3
        elif op == 7:
            store(addr(3), int(val(1) < val(2)))
            ip += 4
        elif op == 8:
            store(addr(3), int(val(1) == val(2)))
            ip += 4
        elif op == 99:
            return outs
        else:
            raise ValueError(f"unknown opcode {op} at {ip}")


def thruster_series(program: list[int], phases: list[int]) -> int:
    signal = 0
    for phase in phases:
        signal = run_inputs(program[:], [phase, signal])[-1]
    return signal


def thruster_feedback(program: list[int], phases: list[int]) -> int:
    mems = [program[:] for _ in phases]
    ips = [0] * 5
    halted = [False] * 5
    queues = [[phase] + ([0] if i == 0 else []) for i, phase in enumerate(phases)]
    thruster = None

    def ref(mem: list[int], addr: int) -> int:
        return mem[addr] if 0 <= addr < len(mem) else 0

    def store(mem: list[int], addr: int, val: int) -> None:
        while addr >= len(mem):
            mem.append(0)
        mem[addr] = val

    def step(i: int) -> str:
        nonlocal thruster
        mem = mems[i]
        ip = ips[i]

        def do() -> str:
            # `thruster` as well as `ip`: without this, `thruster = out` below
            # would bind a fresh local in `do` and the final value would never
            # reach thruster_feedback, which returned None on every permutation.
            nonlocal ip, thruster
            instr = ref(mem, ip)
            op = instr % 100
            modes = instr // 100

            def val(n: int) -> int:
                raw = ref(mem, ip + n)
                mode = (modes // (10 ** (n - 1))) % 10
                return raw if mode == 1 else ref(mem, raw)

            def addr(n: int) -> int:
                return ref(mem, ip + n)

            if op == 3:
                if not queues[i]:
                    return "blocked"
                store(mem, addr(1), queues[i].pop(0))
                ip += 2
                return "ran"
            if op == 99:
                return "halt"
            if op == 4:
                out = val(1)
                ip += 2
                if i == 4:
                    thruster = out
                    queues[0].append(out)
                else:
                    queues[i + 1].append(out)
                return "out"
            if op == 1:
                store(mem, addr(3), val(1) + val(2))
                ip += 4
                return "ran"
            if op == 2:
                store(mem, addr(3), val(1) * val(2))
                ip += 4
                return "ran"
            if op == 5:
                ip = val(2) if val(1) else ip + 3
                return "ran"
            if op == 6:
                ip = val(2) if not val(1) else ip + 3
                return "ran"
            if op == 7:
                store(mem, addr(3), int(val(1) < val(2)))
                ip += 4
                return "ran"
            if op == 8:
                store(mem, addr(3), int(val(1) == val(2)))
                ip += 4
                return "ran"
            raise ValueError(f"bad op {op} at {ip}")

        while True:
            st = do()
            ips[i] = ip
            if st == "ran":
                continue
            if st == "halt":
                halted[i] = True
            return st

    while not all(halted):
        progressed = False
        for i in range(5):
            if halted[i]:
                continue
            while not halted[i]:
                st = step(i)
                if st == "blocked":
                    break
                progressed = True
                if st in ("halt", "out"):
                    break
        if not progressed:
            raise RuntimeError("deadlock")
    return thruster  # type: ignore[return-value]


def part1(program: list[int]) -> int:
    return max(thruster_series(program, list(p)) for p in permutations(range(5)))


def part2(program: list[int]) -> int:
    return max(thruster_feedback(program, list(p)) for p in permutations(range(5, 10)))


if __name__ == "__main__":
    from pathlib import Path

    prog = parse_input(Path("inputs/day07.txt").read_text())
    print("part 1:", part1(prog))
    print("part 2:", part2(prog))
