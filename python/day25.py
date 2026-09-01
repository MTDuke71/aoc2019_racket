"""AoC 2019 Day 25 -- Cryostasis.

The Intcode machine is unchanged (frozen at Day 9; see python/intcode.py).
The peripheral this time is a TEXT ADVENTURE -- the 1977 Colossal Cave
genre, spoken over opcodes 3 and 4 one ASCII code at a time -- and the
finale of the year's I/O saga: after a joystick, a camera, a springdroid
and a network, the last peripheral is a human. The solution replaces the
human with three classical pieces:

  1. EXPLORATION: depth-first search over an unknown graph, backtracking
     each edge as it is unwound (Tremaux's maze strategy). The droid walks
     every door once forward and once back, so the DFS ends where it began
     with the whole ship mapped.

  2. SAFETY PROBING: five of the thirteen items are traps (a droid that
     picks one up melts, hangs, is launched into space...). Rather than
     hardcode their names, take_is_survivable() forks the VM -- memory,
     ip, relative base -- takes the item in the SANDBOX, and watches what
     happens: a machine that halts, stops answering within a step budget
     (the aptly named `infinite loop` item), or answers but can no longer
     walk through a door, condemns the item; the real droid then never
     takes it. Speculative execution with rollback, priced at one dict
     copy per item.

  3. SUBSET SEARCH: the pressure floor wants an exact total weight, so
     finding the right load-out is SUBSET-SUM against an oracle that only
     says heavier/lighter/open. With 8 safe items that is 256 subsets, and
     walking them in REFLECTED GRAY CODE order means consecutive subsets
     differ by one item -- one take or drop plus one walk per trial
     instead of a full re-pack.

The game's text protocol has one wrinkle worth naming: stepping onto the
pressure floor with the wrong weight prints TWO room blocks -- the floor's
own header, then the alert, then the checkpoint re-described as the droid
is ejected back -- so parse_room() keeps the LAST `== ... ==` block, which
is always where the droid actually stands.

Day 25 has no part 2: the fiftieth star is granted for having the other
forty-nine. part2 returns None accordingly.

The engine itself -- rooms as seven-cell structs, items as a table with an
on-take trap hook, strings obfuscated by position, and the password
revealed as the droid's own WEIGHT, decodable off the disk -- is taken
apart in Problem_Statements/days/day25_disassembly.md (python/day25_disasm.py).

Run:  python python/day25.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

from intcode import VM

OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east"}

# Steps a forked probe may run before its silence convicts the item. The
# chattiest legitimate reply (a full room description) costs a few tens of
# thousands of steps; the `infinite loop` item never comes back at all, so
# any comfortable ceiling separates the two. Pinned by test_probe_verdicts.
PROBE_BUDGET = 100_000

# The success string is the engine's, not the input's, and the password is
# the only number the game ever prints (see the disassembly guide).
PASSWORD = re.compile(r"typing (\d+) on the keypad")


def parse_input(text: str) -> list[int]:
    return [int(t) for t in text.strip().split(",")]


class Droid(VM):
    """The VM speaking ASCII lines: run to the next prompt, send a command.

    Same block/resume protocol as every Intcode day since 7; the only new
    layer is decoding opcode-4 bytes to text and encoding commands the
    other way.
    """

    def run(self, budget: int | None = None) -> str | None:
        """Everything printed before the next input prompt (or the halt).

        None means the budget ran out first -- the probe's hang verdict.
        With no budget the call only returns when the machine blocks or
        halts, which the live game always does.
        """
        out: list[int] = []
        steps = 0
        while True:
            result = self.step()
            if result == "blocked" or result == "halted":
                return "".join(map(chr, out))
            if isinstance(result, tuple):
                out.append(result[1])
            steps += 1
            if budget is not None and steps > budget:
                return None

    def send(self, command: str, budget: int | None = None) -> str | None:
        self.inputs.extend(ord(c) for c in command + "\n")
        return self.run(budget)

    def fork(self) -> Droid:
        """An independent copy -- the sandbox the item probes run in."""
        clone = Droid([])
        clone.mem = self.mem.copy()
        clone.ip, clone.rb, clone.halted = self.ip, self.rb, self.halted
        clone.inputs = list(self.inputs)
        return clone


class Room(NamedTuple):
    name: str
    doors: list[str]
    items: list[str]


def parse_room(text: str) -> Room | None:
    """The LAST room block in `text` -- where the droid now stands.

    Ejection texts contain two blocks (see the module docstring); starting
    fresh at every `== name ==` line keeps the final one.
    """
    name = None
    doors: list[str] = []
    items: list[str] = []
    section: list[str] | None = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("== ") and line.endswith(" =="):
            name, doors, items = line[3:-3], [], []
        elif line == "Doors here lead:":
            section = doors
        elif line == "Items here:":
            section = items
        elif line.startswith("- ") and section is not None:
            section.append(line[2:])
        elif not line:
            section = None
    return None if name is None else Room(name, doors, items)


def take_is_survivable(droid: Droid, item: str, door: str) -> bool:
    """Take `item` in a forked sandbox; True if the droid can still walk.

    Three ways to die, three checks: the machine halts (lava, photons, the
    escape pod), never answers again (the infinite loop -- the budget is
    the verdict), or answers but no longer moves (the electromagnet: text
    comes back, but no `== room ==` header ever does).
    """
    probe = droid.fork()
    reply = probe.send(f"take {item}", PROBE_BUDGET)
    if reply is None or probe.halted:
        return False
    reply = probe.send(door, PROBE_BUDGET)
    if reply is None or probe.halted:
        return False
    return parse_room(reply) is not None


@dataclass
class Survey:
    """What exploration learned, with the droid back at its starting room."""

    rooms: dict[str, Room] = field(default_factory=dict)
    inventory: list[str] = field(default_factory=list)  # safe items, now carried
    rejected: list[str] = field(default_factory=list)  # items the probe condemned
    checkpoint_path: list[str] = field(default_factory=list)  # doors from the start
    test_door: str = ""  # the checkpoint door onto the pressure floor


def explore(droid: Droid) -> Survey:
    """Map the ship, pocketing every item a probe survives.

    DFS with backtracking: each unexplored door is walked, the room beyond
    recursed into, and the opposite door walked to unwind -- except the
    pressure floor, which ejects the droid all by itself and marks where
    part 1's finale happens. Terminates because a room is descended into
    only on first sight and the ship is finite.
    """
    survey = Survey()
    trail: list[str] = []

    def visit(room: Room) -> None:
        survey.rooms[room.name] = room
        for item in room.items:
            if take_is_survivable(droid, item, room.doors[0]):
                droid.send(f"take {item}")
                survey.inventory.append(item)
            else:
                survey.rejected.append(item)
        for door in room.doors:
            reply = droid.send(door)
            assert reply is not None
            there = parse_room(reply)
            assert there is not None, f"no room in reply to {door}:\n{reply}"
            if there.name == room.name:  # the floor weighed us and threw us back
                survey.checkpoint_path = [*trail]
                survey.test_door = door
                continue
            if there.name not in survey.rooms:
                trail.append(door)
                visit(there)
                trail.pop()
            droid.send(OPPOSITE[door])

    first = droid.run()
    assert first is not None
    start = parse_room(first)
    assert start is not None
    visit(start)
    if not survey.test_door:
        raise RuntimeError("explored the whole ship without being ejected once")
    return survey


def crack_floor(droid: Droid, survey: Survey) -> str:
    """Walk to the checkpoint and Gray-code the inventory until the door opens.

    Trial i carries (full set) XOR gray(i), so each failed trial costs one
    take-or-drop plus one step onto the floor; 2^n trials cover every
    subset, and the loop ends because the statement promises one of them
    is the droids' standard weight. Returns the airlock speech.
    """
    for door in survey.checkpoint_path:
        droid.send(door)
    carried = set(survey.inventory)
    for trial in range(2 ** len(survey.inventory)):
        if trial:  # toggle one item: the bit gray(i) flips is i's lowest set bit
            item = survey.inventory[(trial & -trial).bit_length() - 1]
            if item in carried:
                carried.remove(item)
                droid.send(f"drop {item}")
            else:
                carried.add(item)
                droid.send(f"take {item}")
        reply = droid.send(survey.test_door)
        assert reply is not None
        if "Alert!" not in reply:
            return reply
    raise RuntimeError("all subsets rejected -- no load-out matches the target weight")


def part1(program: list[int]) -> int:
    """The airlock password: explore, load up, and lean on the floor."""
    droid = Droid(program)
    survey = explore(droid)
    speech = crack_floor(droid, survey)
    match = PASSWORD.search(speech)
    assert match is not None, f"no password in the airlock speech:\n{speech}"
    return int(match.group(1))


def part2(program: list[int]) -> None:
    """There is no part 2: the fiftieth star is the other forty-nine."""


def solve(program: list[int]) -> tuple[int, None]:
    return part1(list(program)), part2(program)


def main() -> None:
    text = (Path(__file__).resolve().parent.parent / "inputs" / "day25.txt").read_text()
    password, _ = solve(parse_input(text))
    print(f"part 1: {password}")
    print("part 2: n/a -- the fiftieth star is the other forty-nine")


if __name__ == "__main__":
    main()
