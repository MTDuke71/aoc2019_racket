"""AoC 2019 Day 22 -- Slam Shuffle.

No Intcode today. The puzzle hands you a hundred shuffle "techniques" and two
deck sizes chosen to kill simulation: part 1's 10,007 cards would simulate
fine, but part 2 runs the same shuffle 101,741,582,076,661 times over a deck
of 119,315,717,514,047 cards and asks for one position. The day is a
disguised algebra exam, and the single load-bearing observation is:

    every technique is an AFFINE MAP on positions, x -> a*x + b  (mod m).

    deal into new stack     x -> -x - 1        (a, b) = (-1, -1)
    cut n                   x ->  x - n        (a, b) = ( 1, -n)
    deal with increment n   x ->  n*x          (a, b) = ( n,  0)

Affine maps compose into affine maps, so the whole hundred-line input
collapses to ONE pair (a, b) -- `parse_input` does that fold and nothing
downstream ever looks at a technique again. Both deck sizes are prime and
every increment is coprime to them, so a is invertible mod m and the shuffle
lives in the affine group mod m: it composes, inverts and exponentiates.

  * Part 1 applies the map forward once: position of card 2019 in a 10,007
    deck is a*2019 + b mod m.
  * Part 2 REVERSES THE QUESTION -- not "where does card 2020 go" but "which
    card LANDS on position 2020" -- after 101 trillion applications. That is
    the composed map raised to the k-th power, then inverted:
    card = (2020 - B) * A^-1 mod m, where (A, B) = (a, b)^k. The power is
    square-and-multiply over affine composition, O(log k) -- exactly the
    jump-ahead trick for linear congruential generators, since one LCG step
    IS x -> a*x + b mod m. A closed form via the geometric series exists
    (see the function guide); the shipping code sticks to the group
    operation it already has.

`parse_input` folds over exact integers -- no modulus appears in the input
file, so the parsed shuffle is deck-size-agnostic and one parse serves both
parts. Every apply/invert/power takes m explicitly.

Run:  python python/day22.py
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DECK = 10007  # part 1: deck size (prime), factory order
CARD = 2019  # part 1: the tracked card
BIG_DECK = 119315717514047  # part 2: deck size (prime)
REPEATS = 101741582076661  # part 2: shuffle applications
POSITION = 2020  # part 2: the watched position


@dataclass(frozen=True)
class Affine:
    """The position map x -> a*x + b of a shuffle (or of any composition).

    Coefficients are exact integers until a modulus is supplied: the input
    file never states a deck size, so the parsed shuffle must not bake one
    in. `then` is composition in application order -- self first.
    """

    a: int
    b: int

    def then(self, other: Affine, m: int | None = None) -> Affine:
        a, b = other.a * self.a, other.a * self.b + other.b
        return Affine(a % m, b % m) if m else Affine(a, b)


IDENTITY = Affine(1, 0)

TECHNIQUES = {
    "deal into new stack": lambda arg: Affine(-1, -1),
    "cut": lambda arg: Affine(1, -arg),
    "deal with increment": lambda arg: Affine(arg, 0),
}


def parse_input(text: str) -> Affine:
    """Fold the technique list into the one affine map it denotes."""
    shuffle = IDENTITY
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        name = line.rstrip("-0123456789 ")
        if name not in TECHNIQUES:
            raise ValueError(f"unknown technique: {line!r}")
        arg = int(line[len(name) :]) if line[len(name) :].strip() else 0
        shuffle = shuffle.then(TECHNIQUES[name](arg))
    return shuffle


def position(shuffle: Affine, m: int, card: int) -> int:
    """Where `card` ends up: the map applied forward."""
    return (shuffle.a * card + shuffle.b) % m


def card_at(shuffle: Affine, m: int, pos: int) -> int:
    """Which card ends up at `pos`: the map inverted.

    Needs gcd(a, m) = 1; both real deck sizes are prime and a is a signed
    product of increments, so `pow(a, -1, m)` exists (pinned by
    test_composed_map_is_invertible_mod_both_decks).
    """
    return (pos - shuffle.b) * pow(shuffle.a, -1, m) % m


def repeat(shuffle: Affine, times: int, m: int) -> Affine:
    """The shuffle applied `times` times, as one map mod m.

    Square-and-multiply over affine composition -- LCG jump-ahead. The
    modulus is applied at every step because after the first squaring the
    exact coefficients would double in size each round.
    """
    result, square = Affine(1 % m, 0), Affine(shuffle.a % m, shuffle.b % m)
    while times:
        if times & 1:
            result = result.then(square, m)
        square = square.then(square, m)
        times >>= 1
    return result


def deck(shuffle: Affine, m: int) -> list[int]:
    """The whole shuffled deck, top first -- the statement's example format."""
    out = [0] * m
    for card in range(m):
        out[position(shuffle, m, card)] = card
    return out


def part1(shuffle: Affine) -> int:
    return position(shuffle, DECK, CARD)


def part2(shuffle: Affine) -> int:
    return card_at(repeat(shuffle, REPEATS, BIG_DECK), BIG_DECK, POSITION)


def solve(shuffle: Affine) -> tuple[int, int]:
    return part1(shuffle), part2(shuffle)


def main() -> None:
    text = (Path(__file__).resolve().parent.parent / "inputs" / "day22.txt").read_text()
    shuffle = parse_input(text)
    one, two = solve(shuffle)
    print(f"part 1: card {CARD} of {DECK} ends at position {one}")
    print(f"part 2: position {POSITION} of {BIG_DECK} holds card {two} after {REPEATS} shuffles")


if __name__ == "__main__":
    main()
