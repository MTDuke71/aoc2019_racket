"""Day 19 -- the drone's Intcode program, decompiled to Python.

Companion to Problem_Statements/days/day19_disassembly.md, which derives
each routine from the listing. One Python function per Intcode routine,
each written as what the routine *computes* -- the obfuscation (additive
swaps, the telescoping multiply, the self-patching trampoline, the mined
literals) is documented, not re-enacted.

    Intcode address   Python
    ---------------   ----------------------------------
      0-220  main     drone(x, y)  via make_drone(A, B, C)
    225-258  apply    apply(f, *args)
    259-281  abs      abs (the builtin -- see below)
    282-302  reject   reject_neg(v)
    303-423  mul3     mul3(a, b, c)

The three honest constants A, B, C (76, 100, 17 in inputs/day19.txt) are
per-user; `drone_from_program` recovers them from any user's program.

Run:  python python/day19_program.py [path-to-program]   (prints the window)
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

Drone = Callable[[int, int], int]


class Halt(Exception):
    """`out #v; hlt` executed inside a subroutine (cells 291-293): the
    machine stops with main's frame still open. Raised by `reject_neg`,
    caught by `drone`."""

    def __init__(self, output: int) -> None:
        super().__init__(output)
        self.output = output


def apply(f: Callable[..., int], *args: int) -> int:
    """225-258: call `f(*args)`.

    Intcode has no indirect jump, so the routine writes `f` into the
    operand of its own `jz` (cell 249) and jumps through it. Python has
    first-class functions; the patch is just a call. Main passes
    `apply` as `f` once (cell 111) purely as a decoy.
    """
    return f(*args)


# 259-281: |v| by arithmetic on the comparison bit -- ((0 < v)*2 - 1) * v.
# It is exactly the builtin, and both calls in main follow `reject_neg`,
# so they are no-ops; the routine exists to be called through `apply`.
abs_ = abs


def reject_neg(v: int) -> int:
    """282-302: the statement's "negative numbers confuse the drone".

    Non-negative `v` returns unchanged; negative `v` outputs 0 and halts
    the whole machine from inside the callee.
    """
    if v < 0:
        raise Halt(0)
    return v


def mul3(a: int, b: int, c: int) -> int:
    """303-423: a * b * c.

    The Intcode sorts its arguments by recursive adjacent swaps (done as
    a+b, then two subtractions, to avoid a temporary) and then evaluates
    b^2*c - b*c*(b - a), which telescopes to a*b*c. The sort is
    pointless -- the product is symmetric -- and the identity holds for
    all integers, so the routine is plain multiplication.
    """
    return a * b * c


def make_drone(a_coef: int, b_coef: int, c_coef: int) -> Drone:
    """0-220: main, for the constants (A, B, C). Returns drone(x, y) -> 0|1."""

    def drone(x: int, y: int) -> int:
        try:
            x = abs_(reject_neg(x))  # cells 2-18:  X = x
            y = abs_(reject_neg(y))  # cells 22-35
        except Halt as halted:
            return halted.output

        y = mul3(1, 1, y)  # 38-57:  Y = y   (the 1 at [23] is `in`'s operand)
        x = apply(abs_, x)  # 61-77:  apply(abs, X) = X
        quad = mul3(x, a_coef, x)  # 80-91:  A*X^2
        y = apply(apply, abs_, y)  # 95-115: apply(apply, abs, Y) = Y, the decoy
        quad = abs_(quad - mul3(y, b_coef, y))  # 118-148: |A*X^2 - B*Y^2|
        # 152-192: the call target 303 is laundered through (v-2)*2+3-v+1 == v,
        # negating cell 132 on the way; then apply(mul3, C, Y, X) through [109].
        cross = apply(mul3, c_coef, y, x)
        lit = not (cross < quad)  # 195-214: 1 - (C*X*Y < quad), via mul3(1, t, -1)
        return int(lit)  # 218: out

    return drone


def drone_from_program(program: list[int]) -> Drone:
    """The Python drone for whichever user's program this is."""
    from day19_disasm import recover_constants

    return make_drone(*recover_constants(program))


def main(argv: list[str] | None = None) -> None:
    from day19 import parse_input

    argv = sys.argv[1:] if argv is None else argv
    path = Path(argv[0]) if argv else Path(__file__).resolve().parents[1] / "inputs" / "day19.txt"
    drone = drone_from_program(parse_input(path.read_text()))
    for y in range(50):
        print("".join("#" if drone(x, y) else "." for x in range(50)))
    print(sum(drone(x, y) for y in range(50) for x in range(50)))


if __name__ == "__main__":
    main()
