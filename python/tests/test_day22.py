r"""Day 22 -- Slam Shuffle.

The statement's ground truth is thin but exact: three single-technique
walkthroughs and four combined examples, all on a 10-card deck, each giving
the ENTIRE resulting deck. All seven are pinned via `deck`, which exercises
the forward map at every position at once.

The pinned identities (standing rule: a shortcut the solution leans on is a
test, not a sentence):

  * `repeat` (square-and-multiply over affine composition) agrees with the
    literal k-fold composition, checked for every k up to 300 and for a
    handful of larger ones -- the O(log k) ladder against the O(k) truth.
  * The geometric-series CLOSED FORM (a^k, b*(a^k-1)/(a-1)) -- the guide's
    sidebar -- agrees with `repeat` on both real moduli at part 2's real
    exponent. The a = 1 branch is exercised separately (a cut-only shuffle).
  * `card_at` inverts `position` at every position of every example deck,
    and the composed real map is invertible mod BOTH deck sizes because
    each is prime and a mod m is nonzero -- `pow(a, -1, m)` is Fermat, and
    it is what part 2's final step stands on.
  * The affine group mod a prime p has order p*(p-1), so the real shuffle
    repeated 10007*10006 times must be the identity -- pinned with `repeat`
    doing the hundred-million-fold composition in 54 steps. (On the 10-card
    examples the group has order 10*phi(10) = 40; same pin.)

Part 2's constants (deck 119315717514047, 101741582076661 repeats, position
2020) are from the puzzle's Part Two text; `test_part2_constants_are_prime`
at least pins the primality both inverses rely on.
"""

from __future__ import annotations

import math

import day22
import pytest
from day22 import (
    BIG_DECK,
    DECK,
    IDENTITY,
    REPEATS,
    Affine,
    card_at,
    deck,
    parse_input,
    part1,
    position,
    repeat,
)

LOCKED = (6850, 13224103523662)  # verified on adventofcode.com

EX1 = "deal with increment 7\ndeal into new stack\ndeal into new stack\n"
EX2 = "cut 6\ndeal with increment 7\ndeal into new stack\n"
EX3 = "deal with increment 7\ndeal with increment 9\ncut -2\n"
EX4 = (
    "deal into new stack\ncut -2\ndeal with increment 7\ncut 8\ncut -4\n"
    "deal with increment 7\ncut 3\ndeal with increment 9\ndeal with increment 3\ncut -1\n"
)

EXAMPLES = [
    ("deal into new stack", [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]),
    ("cut 3", [3, 4, 5, 6, 7, 8, 9, 0, 1, 2]),
    ("cut -4", [6, 7, 8, 9, 0, 1, 2, 3, 4, 5]),
    ("deal with increment 3", [0, 7, 4, 1, 8, 5, 2, 9, 6, 3]),
    (EX1, [0, 3, 6, 9, 2, 5, 8, 1, 4, 7]),
    (EX2, [3, 0, 7, 4, 1, 8, 5, 2, 9, 6]),
    (EX3, [6, 3, 0, 7, 4, 1, 8, 5, 2, 9]),
    (EX4, [9, 2, 5, 8, 1, 4, 7, 0, 3, 6]),
]


@pytest.mark.parametrize("text, want", EXAMPLES)
def test_statement_decks(text, want):
    assert deck(parse_input(text), 10) == want


def test_parse_rejects_garbage():
    with pytest.raises(ValueError, match="unknown technique"):
        parse_input("riffle 3")


def test_parse_is_deck_size_agnostic():
    """The parse never sees a modulus: exact coefficients, one parse, any m."""
    shuffle = parse_input(EX3)  # increments 7 and 9, cut -2
    assert shuffle == Affine(63, 2)  # composed by hand: x -> 9*(7x) + 2
    assert position(shuffle, 10, 1) == 5  # the 10-card example above
    assert position(shuffle, 11, 1) == 10  # the same parse, another deck


# ---------------------------------------------------------------- the algebra


@pytest.mark.parametrize("text, _", EXAMPLES)
def test_card_at_inverts_position_everywhere(text, _):
    shuffle = parse_input(text)
    for pos in range(10):
        assert position(shuffle, 10, card_at(shuffle, 10, pos)) == pos


def naive_repeat(shuffle: Affine, times: int, m: int) -> Affine:
    out = Affine(1 % m, 0)
    for _ in range(times):
        out = out.then(shuffle, m)
    return out


@pytest.mark.parametrize("times", [*range(300), 1000, 4096, 12345])
def test_repeat_agrees_with_literal_composition(times):
    shuffle = parse_input(EX4)
    assert repeat(shuffle, times, DECK) == naive_repeat(shuffle, times, DECK)


def geometric(shuffle: Affine, times: int, m: int) -> Affine:
    """The guide's closed form: (a, b)^k = (a^k, b * (a^k - 1) / (a - 1))."""
    a, b = shuffle.a % m, shuffle.b % m
    if a == 1:
        return Affine(1, b * times % m)
    an = pow(a, times, m)
    return Affine(an, b * (an - 1) * pow(a - 1, -1, m) % m)


def test_closed_form_agrees_with_repeat(real_input):
    shuffle = parse_input(real_input(22))
    for m in (DECK, BIG_DECK):
        for k in (0, 1, 2, REPEATS, REPEATS + 1):
            assert geometric(shuffle, k, m) == repeat(shuffle, k, m)


def test_closed_form_a_equals_1_branch():
    """Cut-only shuffles keep a = 1; the geometric sum degenerates to k*b."""
    shuffle = parse_input("cut 3\ncut -5\ncut 9\n")
    assert shuffle.a == 1
    for k in (0, 1, 7, 12345):
        assert geometric(shuffle, k, DECK) == repeat(shuffle, k, DECK) == Affine(1, -7 * k % DECK)


@pytest.mark.parametrize("m, order", [(10, 40), (DECK, DECK * (DECK - 1))])
def test_shuffle_order_divides_the_affine_group_order(m, order, real_input):
    """|Aff(Z_m)| = m * phi(m); Lagrange makes every shuffle's order divide it.

    For the 10-card examples that is 10 * 4 = 40; for the prime 10,007 deck
    it is 10007 * 10006 -- `repeat` runs that hundred-million-fold
    composition in 54 doublings, which is the whole point of the ladder.
    """
    text = EX4 if m == 10 else real_input(22)
    shuffle = parse_input(text)
    assert repeat(shuffle, order, m) == IDENTITY
    assert repeat(shuffle, order + 1, m) == repeat(shuffle, 1, m)


def test_part2_constants_are_prime():
    """Both moduli must be prime for pow(a, -1, m) to be Fermat-guaranteed."""
    for m in (DECK, BIG_DECK):
        assert m % 2 == 1
        assert all(m % d for d in range(3, math.isqrt(m) + 1, 2))


# ------------------------------------------------------------------ the input


def test_crlf():
    crlf = EX4.replace("\n", "\r\n")
    assert parse_input(crlf) == parse_input(EX4)


def test_crlf_real_input(real_input):
    text = real_input(22)
    assert parse_input(text) == parse_input(text.replace("\r\n", "\n"))


def test_real_shuffle_shape(real_input):
    """100 techniques; the composed map is invertible mod both deck sizes."""
    text = real_input(22)
    lines = text.strip().splitlines()
    counts = {
        "deal with increment": sum(ln.startswith("deal with increment") for ln in lines),
        "cut": sum(ln.startswith("cut") for ln in lines),
        "deal into new stack": sum(ln.strip() == "deal into new stack" for ln in lines),
    }
    assert len(lines) == sum(counts.values()) == 100
    shuffle = parse_input(text)
    for m in (DECK, BIG_DECK):
        assert math.gcd(shuffle.a, m) == 1
        assert card_at(shuffle, m, position(shuffle, m, 2019)) == 2019


def _is_prime(n: int) -> bool:
    return n > 1 and (n == 2 or n % 2 == 1 and all(n % d for d in range(3, math.isqrt(n) + 1, 2)))


def test_real_shuffle_order(real_input):
    """The real shuffle's exact order in each affine group -- both extremes.

    An affine map's order equals the multiplicative order of a (at a's order
    the geometric-series b-term vanishes with a^k - 1). Mod 10,007 this
    input's order is 5003 = (m-1)/2: five thousand and three shuffles
    restore factory order. Mod the big deck it is the theoretical maximum,
    m - 1 -- a is a PRIMITIVE ROOT. Both m-1 factor as 2*q with q prime, so
    the order is pinned exactly: it divides m-1, the q-and-below divisors
    are excluded by a^((m-1)/2) != 1 and a != +-1, and 5003's primality
    plus shuffle != identity nails the small deck.
    """
    shuffle = parse_input(real_input(22))

    assert _is_prime(5003) and DECK - 1 == 2 * 5003
    assert repeat(shuffle, 5003, DECK) == IDENTITY
    assert repeat(shuffle, 1, DECK) != IDENTITY  # so the order is exactly 5003

    q = (BIG_DECK - 1) // 2
    assert _is_prime(q)  # m-1 = 2q: divisors are 1, 2, q, 2q only
    a = shuffle.a % BIG_DECK
    assert a not in (1, BIG_DECK - 1)  # order not 1 or 2
    assert pow(a, q, BIG_DECK) != 1  # order not q (and not 1); with q odd, not 2
    # ...so ord(a) = 2q = BIG_DECK - 1: a is a primitive root mod the big deck.


def test_solve_agrees_with_the_parts(real_input):
    shuffle = parse_input(real_input(22))
    assert day22.solve(shuffle) == (part1(shuffle), day22.part2(shuffle))


def test_real_input(check_locked):
    check_locked(22, LOCKED)
