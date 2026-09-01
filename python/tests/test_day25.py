r"""Day 25 -- Cryostasis.

The statement ships no worked example -- there is nothing to run except the
real ship. So, as on Days 17, 19, 21 and 23, the suite tests the LOGIC
without the puzzle input: the probe's three death verdicts are provoked on
purpose with tiny hand-assembled Intcode "games" (built by `game()` below,
opcode by opcode), and the Gray-code walk's coverage claim is checked as
arithmetic rather than asserted in prose.

What is pinned, per the repo rule that identities live as tests, not prose:

  * The probe's verdicts: a game that halts after `take`, one that never
    answers again (the step budget is the verdict -- the `infinite loop`
    item's fixture twin), and one that answers but never prints another
    room header (the electromagnet's) are all condemned; a game that still
    walks is not. This is also where PROBE_BUDGET's adequacy is pinned.
  * parse_room keeps the LAST room block: an ejection reply contains the
    pressure floor's header AND the checkpoint's re-description, and the
    droid is standing in the second.
  * The Gray-code walk visits all 2^n subsets toggling one item per trial.
  * On the real input: 19 rooms entered (the floor ejects, so it is mapped
    by its bounce, not entered), 8 items pocketed, and the 5 the probes
    condemn are exactly the 5 the DISASSEMBLY says carry an on-take hook
    -- the dynamic sandbox and the static table agree item for item.
  * From the disassembly (day25_disasm; see day25_disassembly.md): the
    checkpoint's target weight decodes off the disk from a 33-cell table
    (bit = cell > 84*52), the eight safe weights are eight DISTINCT POWERS
    OF TWO (so every load-out weighs differently and the answer's binary
    digits pick the items), the five traps weigh exactly 0, and the
    password the live game prints IS the static target -- part 1 with the
    VM never started, cross-checked against the played game.
  * The trap hooks, called in vitro on the live machine: three deaths that
    halt, one honest infinite loop, and one flag-setter whose flag makes
    the dispatcher refuse EVERY later command (pinned by taking the
    electromagnet in a fork and asking for `inv`).

Day 25 has no part 2 -- the fiftieth star is granted for the other
forty-nine -- so `part2` returns None by contract and the real-input test
locks part 1 alone (conftest's check_locked would nag forever about a part
that does not exist).
"""

from __future__ import annotations

import day25
import day25_disasm
import pytest
from day25 import Droid, parse_input, parse_room, take_is_survivable

# The airlock password, once adventofcode.com accepts it. None = unverified:
# the test reports what the code produces and skips instead of passing green.
LOCKED = None

# --------------------------------------------------------------- the fixtures
#
# game() assembles a toy ASCII peripheral: each step is executed in order,
# and the program counter simply falls through. Scratch cells for the read
# loop live above the code (the VM's memory is unbounded).

CHAR, FLAG = 900, 901


def game(*steps: tuple) -> list[int]:
    """('print', text) | ('read',) | ('loop',) | ('halt',) -> Intcode."""
    code: list[int] = []
    for step in steps:
        if step[0] == "print":
            for c in step[1]:
                code += [104, ord(c)]
        elif step[0] == "read":
            # L: in CHAR; eq CHAR #10 FLAG; jz FLAG L  -- swallow one line
            top = len(code)
            code += [3, CHAR, 1008, CHAR, 10, FLAG, 1006, FLAG, top]
        elif step[0] == "loop":
            code += [1105, 1, len(code)]
        elif step[0] == "halt":
            code += [99]
        else:
            raise ValueError(step)
    return code


ROOM_BLOCK = "== Somewhere ==\nDoors here lead:\n- north\n\nCommand?\n"

# Blocks for input immediately; takes anything; still walks. Survivable.
SAFE = game(("read",), ("print", "You take the thing.\n"), ("read",), ("print", ROOM_BLOCK), ("read",))

# Prints a death and halts: the escape pod / lava / photons shape.
DEATH = game(("read",), ("print", "You're launched into space! Bye!\n"), ("halt",))

# Never answers again: the `infinite loop` item's shape. The probe's step
# budget, not any reply, is what condemns it.
HANG = game(("read",), ("loop",))

# Answers politely but no `== room ==` header ever comes back: the
# electromagnet's shape (stuck, not dead).
STUCK = game(
    ("read",), ("print", "The thing is stuck to you.\n"), ("read",), ("print", "You can't move!\n"), ("read",)
)


def booted(program: list[int]) -> Droid:
    droid = Droid(program)
    assert droid.run() is not None  # up to the first input prompt
    return droid


# ------------------------------------------------------------ probe verdicts


@pytest.mark.parametrize(
    ("program", "survivable"),
    [(SAFE, True), (DEATH, False), (HANG, False), (STUCK, False)],
    ids=["safe", "death", "hang", "stuck"],
)
def test_probe_verdicts(program, survivable):
    """The sandbox condemns all three trap shapes and passes the safe one.

    The hang fixture is also PROBE_BUDGET's adequacy pin: the budget must
    be small enough to convict silence and large enough that the safe
    game's chatter never trips it.
    """
    droid = booted(program)
    assert take_is_survivable(droid, "thing", "north") is survivable


def test_probe_leaves_the_droid_untouched():
    """The probe runs in a fork: the real droid is still at its prompt."""
    droid = booted(DEATH)
    take_is_survivable(droid, "thing", "north")
    assert not droid.halted
    assert droid.send("hello") == "You're launched into space! Bye!\n"


# ---------------------------------------------------------------- parse_room


def test_parse_room():
    room = parse_room(
        "== Hull Breach ==\nYou got in through a hole.\n\n"
        "Doors here lead:\n- north\n- east\n\n"
        "Items here:\n- red ball\n\nCommand?\n"
    )
    assert room == ("Hull Breach", ["north", "east"], ["red ball"])


def test_parse_room_keeps_the_last_block():
    """An ejection reply describes TWO rooms; the droid stands in the last."""
    room = parse_room(
        "== Pressure-Sensitive Floor ==\nAnalyzing...\n\nDoors here lead:\n- north\n\n"
        'A loud, robotic voice says "Alert!..." and you are ejected back.\n\n'
        "== Security Checkpoint ==\nIn the next room, a sensor.\n\n"
        "Doors here lead:\n- south\n- west\n\nCommand?\n"
    )
    assert room == ("Security Checkpoint", ["south", "west"], [])


def test_parse_room_without_a_block():
    assert parse_room("You can't go that way.\n\nCommand?\n") is None


# ------------------------------------------------------------- the Gray walk


def test_gray_walk_covers_every_subset_one_toggle_apart():
    """crack_floor's schedule: trial i toggles item (i & -i).bit_length()-1.

    Starting from the full set, that walks the complemented reflected Gray
    code: 2^n distinct subsets, consecutive ones differing by exactly one
    item. Pinned here as arithmetic so the in-game walk can rely on it.
    """
    n = 8
    carried = set(range(n))
    seen = {frozenset(carried)}
    for trial in range(1, 2**n):
        item = (trial & -trial).bit_length() - 1
        carried ^= {item}
        seen.add(frozenset(carried))
    assert len(seen) == 2**n


# ----------------------------------------------------------------- plumbing


def test_crlf():
    assert parse_input("109,4807,21101\r\n") == [109, 4807, 21101]


def test_part2_is_the_free_star():
    assert day25.part2([99]) is None


# ------------------------------------------------- the real ship, played


def test_live_exploration_agrees_with_the_disassembly(real_input):
    """One live sweep of the ship, checked against the static engine.

    The dynamic side knows nothing about the item table; the static side
    never runs the game. They agree on the map, the item placement, and
    -- item for item -- on which five are traps.
    """
    program = parse_input(real_input(25))
    droid = Droid(list(program))
    survey = day25.explore(droid)
    engine = day25_disasm.recover_engine(program)

    entered = {r.name for r in engine.rooms.values() if r.addr != engine.floor}
    assert set(survey.rooms) == entered  # 19 rooms; the floor only ejects
    assert len(survey.inventory) == 8
    assert set(survey.rejected) == {i.name for i in engine.items if i.hook}
    assert set(survey.rejected) == {
        "escape pod",
        "molten lava",
        "photons",
        "infinite loop",
        "giant electromagnet",
    }
    placed = {i.name: engine.rooms[i.location].name for i in engine.items}
    for name, room in survey.rooms.items():
        for item in room.items:
            assert placed[item] == name

    # doors are reciprocal pointers: the ship graph is undirected
    for room in engine.rooms.values():
        for slot, dest in enumerate(room.doors):
            if dest:
                assert engine.rooms[dest].doors[(slot + 2) % 4] == room.addr


def test_static_password_matches_the_live_game(real_input):
    """TARGET IS ANSWER: the weight the bit table demands is the password
    the airlock speech prints. Static analysis vs the played game."""
    program = parse_input(real_input(25))
    assert day25_disasm.static_password(program) == day25.part1(list(program))


def test_safe_weights_are_distinct_powers_of_two(real_input):
    """Why the load-out is unique: subset sums are all distinct, and the
    target's binary digits literally pick the items. The five traps all
    weigh exactly 0 -- their weight cell IS the affine zero point."""
    program = parse_input(real_input(25))
    engine = day25_disasm.recover_engine(program)
    safe = [i.weight for i in engine.items if not i.hook]
    assert all(w > 0 and w & (w - 1) == 0 for w in safe)
    assert len(set(safe)) == len(safe) == 8
    assert all(i.weight == 0 for i in engine.items if i.hook)
    subset = day25_disasm.static_subset(program, engine)
    target = day25_disasm.decode_target(program, engine)
    weights = {i.name: i.weight for i in engine.items}
    assert sum(weights[name] for name in subset) == target


def test_trap_hooks_in_vitro(real_input):
    """Each trap's on-take hook, called alone on the live machine."""
    program = parse_input(real_input(25))
    engine = day25_disasm.recover_engine(program)
    hooks = {i.name: i.hook for i in engine.items if i.hook}

    outcome, text, _ = day25_disasm.call_hook(program, hooks["escape pod"])
    assert (outcome, "launched into space" in text) == ("halted", True)
    outcome, text, _ = day25_disasm.call_hook(program, hooks["molten lava"])
    assert (outcome, "You melt" in text) == ("halted", True)
    outcome, text, _ = day25_disasm.call_hook(program, hooks["photons"])
    assert (outcome, "eaten by a Grue" in text) == ("halted", True)
    outcome, text, _ = day25_disasm.call_hook(program, hooks["infinite loop"])
    assert outcome == "hung"
    assert text.count("You take the infinite loop.") > 100  # the loop IS the message

    # the electromagnet merely returns -- but the flag it sets makes the
    # dispatcher refuse every later command, even `inv`
    outcome, text, changed = day25_disasm.call_hook(program, hooks["giant electromagnet"])
    assert (outcome, text) == ("returned", "")
    assert list(changed.values()) == [1]  # one cell, set to 1: the stuck flag


def test_electromagnet_locks_the_dispatcher(real_input):
    """The one trap that kills the SESSION rather than the machine."""
    program = parse_input(real_input(25))
    engine = day25_disasm.recover_engine(program)
    magnet = next(i for i in engine.items if "electromagnet" in i.name)
    droid = Droid(list(program))
    day25.explore(droid)  # ends back at the start room, magnet left behind

    # route to the magnet's room over the STATIC map (DFS, floor excluded)
    rooms = engine.rooms
    path, seen, stack = None, {engine.start_room}, [(engine.start_room, [])]
    while stack:
        addr, route = stack.pop()
        if addr == magnet.location:
            path = route
            break
        for slot, dest in enumerate(rooms[addr].doors):
            if dest and dest != engine.floor and dest not in seen:
                seen.add(dest)
                stack.append((dest, [*route, day25_disasm.DIRECTIONS[slot]]))
    assert path is not None
    for door in path:
        droid.send(door)
    droid.send(f"take {magnet.name}")
    reply = droid.send("inv")
    assert reply is not None and "stuck" in reply


def test_full_listing_accounts_for_every_cell(real_input):
    """The generated listing tiles all 4807 cells or raises -- run it."""
    program = parse_input(real_input(25))
    text = day25_disasm.full_listing(program)
    assert "every one accounted for" in text


def test_real_input(real_input):
    """Part 1 against the locked answer; there is no part 2 to lock."""
    password = day25.part1(parse_input(real_input(25)))
    if LOCKED is None:
        pytest.skip(
            f"day25: UNVERIFIED -- part 1 = {password!r}. "
            "Submit it, then put it in LOCKED to turn this into a real check."
        )
    assert password == LOCKED
