r"""Day 21 -- Springdroid Adventure.

The statement ships no Intcode-free worked answer -- its example scripts are
a suicide jump and a hole detector, and the real hull lives inside the Intcode
program. So, as on Days 17 and 19, the suite tests the LOGIC without the
machine: `run_script` is a springscript interpreter and `run_droid` walks a
script across an ASCII hull row, which lets the statement's death rendering be
replayed as a test and lets hull patterns act as fixtures.

What is pinned, per the repo rule that identities live as tests, not prose:

  * Both shipping scripts equal their intended Boolean functions on EVERY
    sensor combination (16 for WALK, 512 for RUN) -- the scripts are circuits,
    so exhaustive truth-table equality is cheap and total.
  * A jump travels exactly 4 tiles: the statement's `NOT D J` rendering, in
    which the droid jumps from tile 1 and dies in the hole at tile 5, replays
    move for move.
  * The Part 1 policy genuinely NEEDS the Part 2 guard: hulls found by
    exhaustive search where `not(ABC) and D` falls and the `(E or H)` guard
    crosses.
  * The Part 2 policy is NOT universal: the shortest hull (in the family
    tested) that perfect planning can cross but the policy cannot is 15 tiles
    -- the doom past the landing site lies beyond what E and H can see. Below
    that length the policy is exhaustively complete. The machine accepting the
    script is therefore a fact about this input's hull, not a theorem.
  * The WALK script is MINIMAL: exhaustive BFS over (T, J) truth-table states
    (python/day21_synth.py) finds no 4-instruction script computing it and
    emits a 5-instruction one. The RUN guard reads exactly six sensors, which
    floors any script computing it at 6 instructions; the shipping script
    spends 8.
"""

from __future__ import annotations

from itertools import product

import day21_synth
import pytest
from day21 import (
    JUMP,
    MEMORY_LIMIT,
    PART1_SCRIPT,
    PART2_SCRIPT,
    SIGHT_RUN,
    SIGHT_WALK,
    parse_input,
    run_droid,
    run_script,
    survey,
)

LOCKED = (None, None)

# The hull under the statement's `NOT D J` death rendering.
STATEMENT_HULL = "#####.###########"

# The statement's example: jump if a three-tile-wide hole (with ground on the
# far side) is detected.
THREE_HOLE_SCRIPT = (
    "NOT A J",
    "NOT B T",
    "AND T J",
    "NOT C T",
    "AND T J",
    "AND D J",
)


def sensor_combos(sight: int):
    names = [chr(ord("A") + k) for k in range(sight)]
    for bits in product((False, True), repeat=sight):
        yield dict(zip(names, bits))


def dp_crossable(hull: str) -> bool:
    """Crossable with perfect planning: from a ground tile, step +1 or jump +4.

    This is what "crossable at all" MEANS -- a one-pass reachability DP, the
    upper bound no memoryless policy is guaranteed to reach.
    """
    reach = [False] * (len(hull) + JUMP)
    for i in reversed(range(len(hull) + JUMP)):
        if i >= len(hull):
            reach[i] = True
        elif hull[i] == "#":
            reach[i] = reach[i + 1] or reach[i + JUMP]
    return reach[0]


# ------------------------------------------------------------ the interpreter


def test_registers_start_false():
    """T and J begin false, so an empty script -- and a script that only
    copies T into J -- never jumps."""
    assert run_script((), {}) is False
    assert run_script(("OR T J",), {}) is False


@pytest.mark.parametrize("a, want", [(False, True), (True, False)])
def test_not_a_j(a, want):
    """The statement's one-instruction example: jump iff no ground at A."""
    assert run_script(("NOT A J",), {"A": a}) == want


def test_three_hole_example_truth_table():
    """The statement's hole-detector example is exactly (not A)(not B)(not C)D."""
    for s in sensor_combos(SIGHT_WALK):
        want = not s["A"] and not s["B"] and not s["C"] and s["D"]
        assert run_script(THREE_HOLE_SCRIPT, s) == want


def test_destination_must_be_writable():
    with pytest.raises(ValueError, match="writable"):
        run_script(("NOT J A",), {"A": True})


def test_unknown_opcode_rejected():
    with pytest.raises(ValueError, match="opcode"):
        run_script(("XOR A J",), {"A": True})


def test_instruction_budget_enforced():
    over = ("NOT T T",) * (MEMORY_LIMIT + 1)
    with pytest.raises(ValueError, match="15"):
        run_script(over, {})
    assert run_script(("NOT T T",) * MEMORY_LIMIT, {}) is False


# ------------------------------------------- the shipping scripts, as circuits


def test_part1_script_truth_table():
    """All 16 sensor combinations: J = not(A and B and C) and D."""
    for s in sensor_combos(SIGHT_WALK):
        want = not (s["A"] and s["B"] and s["C"]) and s["D"]
        assert run_script(PART1_SCRIPT, s) == want


def test_part2_script_truth_table():
    """All 512 sensor combinations: J = not(A and B and C) and D and (E or H)."""
    for s in sensor_combos(SIGHT_RUN):
        want = not (s["A"] and s["B"] and s["C"]) and s["D"] and (s["E"] or s["H"])
        assert run_script(PART2_SCRIPT, s) == want


def test_scripts_fit_the_droid():
    assert len(PART1_SCRIPT) <= MEMORY_LIMIT
    assert len(PART2_SCRIPT) <= MEMORY_LIMIT


# ------------------------------------------------------------- the simulator


def test_suicide_program_replays_the_statement_rendering():
    """`NOT D J` on the statement's hull: walk one tile (D sees ground), jump
    from tile 1, die in the hole at tile 5. Falling at 5 = 1 + 4 is what pins
    the jump length the module claims."""
    assert run_droid(STATEMENT_HULL, ("NOT D J",), SIGHT_WALK) == 1 + JUMP


def test_three_hole_script_crosses_its_own_hull():
    assert run_droid("####...####", THREE_HOLE_SCRIPT, SIGHT_WALK) is None


@pytest.mark.parametrize(
    "hull",
    [
        STATEMENT_HULL,  # one-tile hole
        "####..####",  # two-tile hole
        "####...####",  # three-tile hole
        "####.##..##.####",  # mixed widths back to back
    ],
)
def test_part1_policy_crosses_walkable_hulls(hull, script=PART1_SCRIPT):
    assert run_droid(hull, script, SIGHT_WALK) is None


def test_four_wide_hole_is_impassable():
    """A jump always lands 4 ahead, so a 4-wide hole swallows every policy --
    the DP agrees no plan exists, and the Part 1 policy jumps and dies in it."""
    hull = "####....####"
    assert not dp_crossable(hull)
    assert run_droid(hull, PART1_SCRIPT, SIGHT_WALK) is not None


# --------------------------------------- why Part 2 needs the (E or H) guard


@pytest.mark.parametrize("hull, fall", [("####.#.##.##", 6), ("#####.#.##.#", 7)])
def test_walk_policy_dies_where_the_guard_survives(hull, fall):
    """Hulls (found by exhaustive search) where not(ABC)D jumps onto a landing
    tile with holes at both exits -- E and H -- and dies one step later, while
    the guarded policy waits one tile and lives."""
    assert run_droid(hull, PART1_SCRIPT, SIGHT_RUN) == fall
    assert run_droid(hull, PART2_SCRIPT, SIGHT_RUN) is None


def test_run_policy_is_not_universal():
    """The Part 2 policy is still just a circuit, and circuits cannot plan:
    on this hull the guard approves a jump (H is ground) whose landing region
    is doomed anyway, while stepping first and jumping later crosses. The
    machine accepting PART2_SCRIPT is a fact about the input's hull, not a
    theorem about the script."""
    hull = "####.#.###.##.#"
    assert dp_crossable(hull)
    assert run_droid(hull, PART2_SCRIPT, SIGHT_RUN) == 6


def test_run_policy_is_complete_below_the_counterexample_length():
    """Exhaustive: over every hull `####` + {#,.}* + `#` of length < 15, the
    Part 2 policy crosses exactly the hulls perfect planning can cross -- so
    the 15-tile counterexample above is minimal for this family."""
    for n in range(6, 15):
        for bits in product("#.", repeat=n - 5):
            hull = "####" + "".join(bits) + "#"
            crossed = run_droid(hull, PART2_SCRIPT, SIGHT_RUN) is None
            assert crossed == dp_crossable(hull), hull


# ------------------------------------- the synthesis sidebar (day21_synth)


def script_table(script, sight: int) -> int:
    """A script's truth table by brute evaluation -- the independent check on
    day21_synth's algebra, which never runs the interpreter at all."""
    t = 0
    for i in range(1 << sight):
        s = {chr(ord("A") + k): bool((i >> k) & 1) for k in range(sight)}
        if run_script(script, s):
            t |= 1 << i
    return t


def test_walk_function_takes_exactly_five_instructions():
    """Minimality by exhaustion: BFS over (T, J) truth-table states finds NO
    script of length <= 4 computing not(ABC) and D, and emits one at 5 --
    which the interpreter confirms computes the same function as the
    shipping script."""
    target = day21_synth.walk_target()
    assert script_table(PART1_SCRIPT, SIGHT_WALK) == target
    assert day21_synth.synthesize(target, SIGHT_WALK, 4) is None
    found = day21_synth.synthesize(target, SIGHT_WALK, 5)
    assert found is not None and len(found) == 5
    assert script_table(found, SIGHT_WALK) == target


def test_run_guard_reads_exactly_six_sensors():
    """The RUN guard depends on A-E and H and nothing else. A sensor's value
    can only enter the registers as some instruction's X operand, so six live
    sensors floor any script computing this function at SIX instructions --
    the shipping script spends 8. (Exhaustive BFS over the live-sensor
    universe, too slow for the suite, finds nothing at 7 either; see
    python/day21_synth.py and the guide.)"""
    table = script_table(PART2_SCRIPT, SIGHT_RUN)
    assert day21_synth.live_sensors(table, SIGHT_RUN) == {"A", "B", "C", "D", "E", "H"}
    assert len(PART2_SCRIPT) == 8


def test_synth_tables_match_the_interpreter():
    """day21_synth's sensor tables and table_of agree with brute evaluation
    through the real interpreter, so the BFS searches the right space."""
    for k, name in enumerate("ABCD"):
        assert day21_synth.sensor_table(k, 4) == script_table((f"OR {name} J",), SIGHT_WALK)
    assert day21_synth.table_of(lambda a, b, c, d: not (a and b and c) and d, 4) == script_table(
        PART1_SCRIPT, SIGHT_WALK
    )


# --------------------------------------------------------------- the machine


def test_failed_survey_renders_the_last_moments(real_input):
    """The statement's suicide script against the real machine: no damage
    value, and the transcript ends with the droid's last moments -- the
    debugging channel this day gives you."""
    transcript, damage = survey(parse_input(real_input(21)), ("NOT D J",), "WALK")
    assert damage is None
    assert "Didn't make it across" in transcript
    assert "@" in transcript
    # The machine's rendering opens on the very window the statement's own
    # NOT D J example shows -- hull line included, on this input.
    assert STATEMENT_HULL in transcript


# ------------------------------------------------------------------ the input


def test_crlf():
    r"""A Windows-downloaded input ends `\r\n`; `parse_input` must survive it."""
    assert parse_input("104,1,99\r\n") == [104, 1, 99]


def test_crlf_real_input(real_input):
    text = real_input(21)
    assert parse_input(text) == parse_input(text.replace("\r\n", "\n"))


def test_real_input(check_locked):
    check_locked(21, LOCKED)
