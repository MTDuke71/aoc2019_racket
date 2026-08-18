"""Day 16 -- Flawed Frequency Transmission.

The day ships an unusually rich set of worked examples -- a four-phase trace
digit by digit, three 100-phase Part One signals, three Part Two signals -- so
much of this module is `parametrize` over the statement.

The interesting tests are the ones pinning the two claims the fast paths rest
on. Both are stated in the function guide, and neither is visible in the
puzzle's own examples:

  * `phase` (prefix sums over runs) computes exactly what the statement's
    literal definition computes. `test_prefix_sums_match_the_definition` checks
    it against a transcription of that definition on every length up to 40, not
    only the 8 and 32 the puzzle hands out -- truncation of the last run in
    each row is precisely where an off-by-one would hide.
  * Below the midpoint the pattern matrix is unit upper triangular, so digits
    left of the offset cannot reach the answer. That is the entire licence for
    Part Two discarding 92% of the signal, and `test_prefix_cannot_reach_the_tail`
    demonstrates it by scribbling over the prefix and checking the answer does
    not move.

The precondition those rest on -- the message offset lands past the midpoint --
is checked on the real input (`test_offset_lands_in_the_lower_half`) and on
every published example (`test_example_offsets_land_in_the_lower_half`), and
`part2` refuses rather than lying when it does not hold.
"""

from __future__ import annotations

from itertools import pairwise

import day16
import pytest
from day16 import (
    PHASES,
    REPEATS,
    digits_to_str,
    message_offset,
    parse_input,
    part1,
    part2,
    phase,
    real_tail,
    suffix_transform,
    transform,
)

LOCKED = ("76795888", "84024125")  # verified on adventofcode.com


def definition(digits: list[int]) -> list[int]:
    """One phase, transcribed straight from the statement -- the O(n^2) oracle.

    Element j (0-based) of the input is multiplied by the pattern value for
    output row k, which the statement builds by repeating each of 0, 1, 0, -1
    exactly k times and then shifting left by one. Taking `(j + 1) // k` mod 4
    IS that shift: index 0 of the shifted pattern sees repeated-pattern index 1.
    """
    n = len(digits)
    out = []
    for k in range(1, n + 1):
        total = 0
        for j, value in enumerate(digits):
            slot = ((j + 1) // k) % 4
            if slot == 1:
                total += value
            elif slot == 3:
                total -= value
        out.append(abs(total) % 10)
    return out


def pseudo_random(n: int) -> list[int]:
    """A deterministic digit signal of length n -- no seed, no `random` import."""
    return [(7 * i * i + 3 * i + 1) % 10 for i in range(n)]


# ------------------------------------------------------- the four-phase trace

TRACE = ["48226158", "34040438", "03415518", "01029498"]


@pytest.mark.parametrize("count, want", list(enumerate(TRACE, start=1)))
def test_worked_trace(count, want):
    """`12345678` after 1, 2, 3 and 4 phases."""
    assert digits_to_str(transform(parse_input("12345678"), count)) == want


def test_trace_is_a_chain():
    """Each line of the trace is one phase applied to the line above it."""
    signals = ["12345678", *TRACE]
    for before, after in pairwise(signals):
        assert digits_to_str(phase(parse_input(before))) == after


def test_answer_is_a_string_because_of_leading_zeros():
    """`01029498` is not 1029498.

    The statement's own trace lands on a leading zero after four phases, which
    is why every answer here is a string and `digits_to_str` exists at all.
    """
    assert digits_to_str(transform(parse_input("12345678"), 4)) == "01029498"


# ------------------------------------------------------------------- part one


@pytest.mark.parametrize(
    "signal, want",
    [
        ("80871224585914546619083218645595", "24176176"),
        ("19617804207202209144916044189917", "73745418"),
        ("69317163492948606335995924319873", "52432133"),
    ],
)
def test_part1_examples(signal, want):
    assert part1(parse_input(signal)) == want


@pytest.mark.parametrize("n", range(1, 41))
def test_prefix_sums_match_the_definition(n):
    """The run/prefix-sum phase equals the statement's literal definition."""
    digits = pseudo_random(n)
    assert phase(digits) == definition(digits)


def test_phase_is_triangular():
    """Row k of the pattern matrix is zero left of column k.

    Changing digit j can move output digit i only when i <= j. Demonstrated by
    bumping one digit and checking nothing to its right in the output moves.
    """
    digits = pseudo_random(30)
    before = phase(digits)
    for j in range(30):
        bumped = list(digits)
        bumped[j] = (bumped[j] + 5) % 10
        after = phase(bumped)
        assert after[j + 1 :] == before[j + 1 :]


# ------------------------------------------------------------------- part two

PART2_EXAMPLES = [
    ("03036732577212944063491565474664", "84462026"),
    ("02935109699940807407585447034323", "78725270"),
    ("03081770884921959731165446850517", "53553731"),
]


@pytest.mark.parametrize("signal, want", PART2_EXAMPLES)
def test_part2_examples(signal, want):
    assert part2(parse_input(signal)) == want


@pytest.mark.parametrize("signal, want", PART2_EXAMPLES)
def test_example_offsets_land_in_the_lower_half(signal, want):
    """Every published example shares the precondition the real input relies on."""
    digits = parse_input(signal)
    total = len(digits) * REPEATS
    assert message_offset(digits) >= total // 2


def test_upper_half_offset_is_refused():
    """An offset in the UPPER half raises rather than returning a wrong answer.

    Offset 1 against a 2000-digit signal repeated 10000 times: in range, but
    nowhere near the midpoint, so the suffix shortcut does not apply.
    """
    digits = parse_input("0000001" + "2" * 1993)
    assert message_offset(digits) == 1
    assert len(digits) * REPEATS == 20_000_000
    with pytest.raises(ValueError, match="upper half"):
        part2(digits)


def test_real_tail_matches_the_honest_construction():
    """`real_tail` equals `(digits * REPEATS)[offset:]`, without building it."""
    digits = parse_input("03036732577212944063491565474664")
    offset = message_offset(digits)
    tail = real_tail(digits, offset)
    assert len(tail) == len(digits) * REPEATS - offset
    assert tail == (digits * REPEATS)[offset:]


def test_suffix_transform_agrees_with_full_phases():
    """On a small signal, the suffix shortcut reproduces what `phase` produces.

    `phase` is the general algorithm and knows nothing about midpoints; running
    it over the whole signal and slicing the tail off the result must match
    running `suffix_transform` on the tail alone. This is the claim "below the
    midpoint a phase is a suffix sum", checked rather than asserted.
    """
    digits = pseudo_random(101)
    offset = 60  # comfortably past 101 // 2
    assert suffix_transform(digits[offset:], PHASES) == transform(digits, PHASES)[offset:]


def test_prefix_cannot_reach_the_tail():
    """Digits left of the offset never influence digits at or after it.

    Unit upper triangularity, demonstrated: scribble over the entire prefix and
    the tail's 100-phase output is unchanged. Without this, Part Two would have
    to build and grind all 6,500,000 digits.
    """
    digits = pseudo_random(101)
    offset = 60
    scribbled = [(d + 7) % 10 for d in digits[:offset]] + digits[offset:]
    assert transform(scribbled, PHASES)[offset:] == transform(digits, PHASES)[offset:]


# ------------------------------------------------------------------ the input


def test_crlf():
    r"""A Windows-downloaded input ends `\r\n`; `parse_input` must survive it.

    Constructed here rather than loaded from disk, because `Path.read_text()`
    rewrites CRLF to LF and a fixture-loaded "CRLF case" would assert nothing.
    """
    assert parse_input("12345678\r\n") == [1, 2, 3, 4, 5, 6, 7, 8]
    assert parse_input("12345678\n") == parse_input("12345678\r\n")


def test_crlf_real_input(real_input):
    """The same, over whatever line ending the real file actually carries."""
    text = real_input(16)
    assert parse_input(text) == parse_input(text.replace("\r\n", "\n"))


def test_real_signal_shape(real_input):
    digits = parse_input(real_input(16))
    assert len(digits) == 650
    assert all(0 <= d <= 9 for d in digits)


def test_offset_lands_in_the_lower_half(real_input):
    """The real input's message offset is past the midpoint of the real signal.

    5,972,877 of 6,500,000 -- the message sits in the last 8.1% of the signal,
    which is why Part Two is a two-second sweep rather than an afternoon.
    """
    digits = parse_input(real_input(16))
    total = len(digits) * REPEATS
    offset = message_offset(digits)
    assert offset < total, "the offset must land inside the repeated signal at all"
    assert offset >= total // 2


def test_solve_agrees_with_the_parts(real_input):
    digits = parse_input(real_input(16))
    assert day16.solve(digits) == (part1(digits), part2(digits))


def test_real_input(check_locked):
    check_locked(16, LOCKED)


# ------------------------------------- carry-free arithmetic, and where it ends


def pattern_matrix(n: int) -> list[list[int]]:
    """M, so the algebra can be checked against the code rather than described."""
    return [
        [1 if (j // k) % 4 == 1 else -1 if (j // k) % 4 == 3 else 0 for j in range(1, n + 1)]
        for k in range(1, n + 1)
    ]


def test_abs_is_a_no_op_below_the_midpoint():
    """In the tail region no row total can be negative, so `abs` does nothing.

    Every coefficient there is +1 and every digit is >= 0. This is what lets
    `suffix_transform` omit the `abs` that `phase` needs -- and, more
    importantly, it is what makes the operator genuinely LINEAR over Z/10Z
    down there, which the binomial identity in the function guide rests on.
    The tail half of the claim is UNIVERSAL and is checked as such. The head
    half is not: whether any row above the midpoint actually goes negative
    depends on the digits, and `pseudo_random(20)` happens never to. So the
    head is demonstrated with the statement's own `12345678`, whose first two
    row totals are -4 and -8 -- the two places `abs` changes the answer
    (`abs(-4) % 10` is 4; Python's `-4 % 10` is 6).
    """
    for n in range(2, 41):
        digits = pseudo_random(n)
        totals = [sum(c * v for c, v in zip(row, digits)) for row in pattern_matrix(n)]
        assert all(t >= 0 for t in totals[n // 2 :]), f"negative row total below midpoint at n={n}"

    example = parse_input("12345678")
    totals = [sum(c * v for c, v in zip(row, example)) for row in pattern_matrix(8)]
    assert totals == [-4, -8, 12, 22, 26, 21, 15, 8]
    assert [abs(t) % 10 for t in totals] == phase(example)
    assert [t % 10 for t in totals] != phase(example)  # abs is not decoration


def test_phases_equal_the_matrix_power_only_on_the_tail():
    """100 phases == (M^100 mod 10) @ x on the tail, and NOT on the head.

    `mod 10` is applied coordinate-wise with no carry between positions, so it
    is a ring homomorphism and commutes with the operator -- that is the whole
    licence for discarding everything above the ones digit at every step (the
    exact 100-phase coefficient runs to 411 decimal digits).

    `abs` is the nonlinearity that survives, and this test locates it: the two
    computations agree exactly where `abs` is a no-op and disagree where it is
    not. It is why Part 2 has a closed form and Part 1 does not.
    """
    n = 20
    matrix = [[v % 10 for v in row] for row in pattern_matrix(n)]

    power = [[int(i == j) for j in range(n)] for i in range(n)]
    for _ in range(PHASES):
        columns = list(zip(*matrix))
        power = [[sum(a * b for a, b in zip(row, col)) % 10 for col in columns] for row in power]

    digits = pseudo_random(n)
    linear = [sum(c * v for c, v in zip(row, digits)) % 10 for row in power]
    real = transform(digits, PHASES)

    assert real[n // 2 :] == linear[n // 2 :]
    assert real[: n // 2] != linear[: n // 2]
